"""fit_exafs —— EXAFS 路径拟合（larch feffit 封装）。

模型用字典 / JSON 描述（先写清模型，再拟合）：
{
  "name": "IrO2_1shell",
  "kmin": 3, "kmax": 12.5, "dk": 1, "window": "hanning", "kweight": [1, 2, 3],
  "rmin": 1.0, "rmax": 2.1, "fitspace": "r",
  "params": {                                 # 名称: 初值或 {value, vary, min, max, expr}
     "s02": {"value": 0.8, "vary": true, "min": 0.3, "max": 1.5},
     "e0":  {"value": 0.0, "vary": true},
     "dr1": 0.0, "ss1": 0.003
  },
  "paths": [
     {"file": "output/feff/IrO2_IrL3/site0/feff0001.dat", "label": "Ir-O", "N": "2", "s02": "s02",
      "e0": "e0", "deltar": "dr1", "sigma2": "ss1"},
     ...
  ]
}
路径的 N：给出时 degen 置 1，振幅 = s02 × N（N 可为数字或参数表达式）；不给则用 FEFF 简并度。
数值型 "params" 条目默认 vary=True；字符串条目视为表达式（约束）。

输出：参数±误差（larch 已乘 sqrt(χ²_ν)），R 因子、χ²_ν、N_idp、变量数；
      write_result_row() 追加到 output/fits/exafs_fits.csv（一行一个拟合）。
F 检验：hamilton_test(fit_small, fit_large)。

用法：
  python -m xafsmith.fit_exafs <数据文件> <model.json> [--out output/fits/]
"""
from xafsmith import logs
import argparse
import json
from collections.abc import Callable
from pathlib import Path

import numpy as np
import pandas as pd
from larch import Group

from .common import ETOK, n_idp, write_params


def _mkparam(name, spec):
    from larch.fitting import param, guess  # larch.xafs 导入约 2 秒：用到时才导入，加快启动
    if isinstance(spec, str):
        return param(expr=spec, name=name)
    if isinstance(spec, (int, float)):
        return guess(float(spec), name=name)
    spec = dict(spec)
    if spec.get("expr"):
        return param(expr=spec["expr"], name=name)
    kw = {}
    if spec.get("min") is not None:
        kw["min"] = spec["min"]
    if spec.get("max") is not None:
        kw["max"] = spec["max"]
    if spec.get("vary", True):
        return guess(float(spec.get("value", 0.0)), name=name, **kw)
    return param(float(spec.get("value", 0.0)), name=name, vary=False, **kw)


def build_paths(model, root=None):
    """路径文件名相对项目根目录（数据标准：output/feff/...）"""
    from .paths import ROOT
    root = ROOT if root is None else root
    from larch.xafs import feffpath
    paths = {}
    used = set()
    for i, ps in enumerate(model["paths"]):
        f = Path(ps["file"])
        if root and not f.is_absolute():
            f = Path(root) / f
        lab = ps.get("label") or f"p{i + 1}"
        # larch 按 label 存路径，重复的 label 会互相覆盖 → 加文件号区分
        if lab in used:
            lab = f"{lab}#{f.stem.replace('feff', '')}"
        used.add(lab)
        key = f"p{i + 1}"
        kw = dict(e0=ps.get("e0", "e0"), sigma2=ps.get("sigma2", "0.003"),
                  deltar=ps.get("deltar", "0"))
        amp = ps.get("s02", "s02")
        if ps.get("N") not in (None, ""):
            kw["degen"] = 1.0
            amp = f"({amp})*({ps['N']})"
        kw["s02"] = amp
        for extra in ("third", "fourth", "ei"):
            if ps.get(extra):
                kw[extra] = ps[extra]
        paths[key] = feffpath(str(f), label=lab, **kw)
    return paths


# ------------------------------------------------------------------ 模型规范化（B1：多数据集）
_RANGE_KEYS = ("kmin", "kmax", "rmin", "rmax", "kweight")
_FIT_KEYS = ("kmin", "kmax", "dk", "window", "kweight", "rmin", "rmax", "fitspace")
_BUILTIN = dict(dk=1, window="hanning", fitspace="r")     # 与 v1.1 run_fit 的默认相同


def is_multi(model: dict) -> bool:
    """有 datasets 键 = 多数据集模型；没有 = 旧格式（单数据集）。"""
    return "datasets" in model


def _normalize_restraints(raw) -> list:
    """B3：规范化软约束列表 → [{name, expr, value, sigma, note}]；格式错误 → ValueError（双语，指出 restraints[i].字段）。"""
    import math
    if raw in (None, ""):
        return []
    if not isinstance(raw, list):
        raise ValueError("restraints 必须是数组 / restraints must be an array")
    out, seen = [], set()
    for i, r in enumerate(raw):
        at = f"restraints[{i}]"
        if not isinstance(r, dict):
            raise ValueError(f"{at} 不是对象 / {at} is not an object")
        for k in ("expr", "value", "sigma"):
            if k not in r:
                raise ValueError(f"{at}.{k} 缺失 / {at}.{k} is missing")
        expr = r["expr"]
        if not isinstance(expr, str) or not expr.strip():
            raise ValueError(f"{at}.expr 必须是非空字符串 / {at}.expr must be a non-empty string")
        vals = {}
        for k in ("value", "sigma"):
            try:
                if isinstance(r[k], bool):
                    raise TypeError
                vals[k] = float(r[k])
            except (TypeError, ValueError):
                raise ValueError(f"{at}.{k} 不是数字 / {at}.{k} is not a number") from None
            if not math.isfinite(vals[k]):
                raise ValueError(f"{at}.{k} 不是有限数 / {at}.{k} is not finite")
        if vals["sigma"] <= 0:
            raise ValueError(f"{at}.sigma 必须 > 0 / {at}.sigma must be > 0")
        name = r.get("name", f"r{i + 1}")
        if not isinstance(name, str) or not name:
            raise ValueError(f"{at}.name 为空 / {at}.name is empty")
        if name in seen:
            raise ValueError(f"{at}.name 重复：{name} / duplicate {at}.name: {name}")
        seen.add(name)
        out.append(dict(name=name, expr=expr, value=vals["value"], sigma=vals["sigma"],
                        note=str(r.get("note", "") or "")))
    return out


def normalize_model(model: dict) -> dict:
    """把旧格式或多数据集模型统一成
    {name, params, multi, restraints, datasets: [{id, sample, kmin, kmax, dk, window, kweight, rmin, rmax, fitspace, epsilon_k, paths}]}。
    纯函数（深拷贝，不改输入）。取值顺序：数据集自己的值 → 顶层值 → 内置默认。缺必填 → ValueError。"""
    import copy
    m = copy.deepcopy(model)
    out = dict(name=m.get("name", ""), params=m.get("params", {}), multi=is_multi(m), datasets=[],
               restraints=_normalize_restraints(m.get("restraints")))
    if not out["multi"]:
        ds = dict(id=m.get("sample") or "data", sample=m.get("sample", ""))
        for k in _FIT_KEYS:
            ds[k] = m.get(k, _BUILTIN.get(k, 2 if k == "kweight" else None))   # kweight 缺省 2（v1.1）
        miss = [k for k in _RANGE_KEYS if ds[k] is None]
        if miss:
            raise ValueError(f"模型缺少 {', '.join(miss)} / model is missing {', '.join(miss)}")
        ds["epsilon_k"] = None                      # 旧格式从不传 epsilon_k（与 v1.1 相同）
        ds["paths"] = m.get("paths", [])
        out["datasets"].append(ds)
        return out
    dl = m["datasets"]
    if not isinstance(dl, list) or not dl:
        raise ValueError("datasets 必须是非空数组 / datasets must be a non-empty array")
    for k in ("sample", "paths"):
        if k in m:
            raise ValueError(f"多数据集模型不得有顶层 {k}（写进 datasets[i]） / "
                             f"a multi-dataset model must not have a top-level '{k}' (put it in datasets[i])")
    seen = set()
    for i, d in enumerate(dl):
        if not isinstance(d, dict):
            raise ValueError(f"datasets[{i}] 不是对象 / datasets[{i}] is not an object")
        for k in ("sample", "paths"):
            if not d.get(k):
                raise ValueError(f"datasets[{i}].{k} 缺失或为空 / datasets[{i}].{k} is missing or empty")
        ds = dict(id=d.get("id", d["sample"]), sample=d["sample"])
        if not isinstance(ds["id"], str) or not ds["id"]:
            raise ValueError(f"datasets[{i}].id 为空 / datasets[{i}].id is empty")
        if ds["id"] in seen:
            raise ValueError(f"datasets[{i}].id 重复：{ds['id']} / duplicate datasets[{i}].id: {ds['id']}")
        seen.add(ds["id"])
        for k in _FIT_KEYS:
            ds[k] = d[k] if k in d else m.get(k, _BUILTIN.get(k))
        miss = [k for k in _RANGE_KEYS if ds[k] is None]
        if miss:
            raise ValueError(f"datasets[{i}].{'/'.join(miss)} 缺失（数据集与顶层都没有） / "
                             f"datasets[{i}].{'/'.join(miss)} missing (neither in the dataset nor at top level)")
        ds["epsilon_k"] = d.get("epsilon_k")
        ds["paths"] = d["paths"]
        out["datasets"].append(ds)
    return out


def dataset_of(model: dict, key: str) -> dict:
    """按 id 或样品名取规范化后的数据集；旧格式返回唯一的数据集。"""
    nm = normalize_model(model)
    if not nm["multi"]:
        return nm["datasets"][0]
    for f in ("id", "sample"):
        for d in nm["datasets"]:
            if d[f] == key:
                return d
    raise KeyError(f"模型 {nm['name']} 中没有数据集 {key} / no dataset {key} in model {nm['name']}")


def model_path_files(model: dict) -> list[str]:
    """全部数据集的路径文件（不要求模型完整，供 methods_text / si_text 用）。"""
    blocks = model.get("datasets") if is_multi(model) else [model]
    return [p["file"] for b in (blocks or []) if isinstance(b, dict)
            for p in (b.get("paths") or []) if isinstance(p, dict) and "file" in p]


# ------------------------------------------------------------------ 拟合
def _build(groups: list, nm: dict, root=None) -> tuple:
    """建参数组与各数据集（每次调用都新建 Group 与路径对象；顺序与 v1.1 run_fit 相同）。"""
    from larch.fitting import param_group
    from larch.xafs import feffit_transform, feffit_dataset
    pars = param_group(**{k: _mkparam(k, v) for k, v in nm["params"].items()})
    dsets = []
    for data, d in zip(groups, nm["datasets"]):
        paths = build_paths(d, root)              # 每个数据集各自的 FeffPathGroup（larch 会写 path.dataset）
        trans = feffit_transform(kmin=d["kmin"], kmax=d["kmax"], dk=d["dk"],
                                 window=d["window"], kweight=d["kweight"],
                                 rmin=d["rmin"], rmax=d["rmax"],
                                 fitspace=d["fitspace"])
        kw = {} if d["epsilon_k"] is None else dict(epsilon_k=d["epsilon_k"])
        dsets.append(feffit_dataset(data=data, pathlist=list(paths.values()), transform=trans, **kw))
    return pars, dsets


def _fit_core(groups: list, nm: dict, root=None) -> tuple:
    """groups 与 nm["datasets"] 一一对应。调用顺序与 v1.1 run_fit 相同（逐位一致的前提）。返回 (res, dsets)。
    B3：nm["restraints"] 为空 → 只走 larch feffit（与 B3 之前逐位相同）；非空 → 先无约束预拟合得 c0，再走带软约束的驱动。"""
    from larch.xafs import feffit
    pars, dsets = _build(groups, nm, root)
    restraints = nm.get("restraints") or []
    if not restraints:
        res = feffit(pars, dsets)
        return res, dsets
    res0 = feffit(pars, dsets)
    c0 = float(res0.chi2_reduced)
    if not np.isfinite(c0) or c0 <= 0:
        raise ValueError("无约束预拟合的 χ²_ν 无效（变量数 ≥ N_idp？），无法确定软约束权重 / "
                         "the unrestrained pre-fit has an invalid χ²_ν (variables ≥ N_idp?); "
                         "cannot set the restraint weight")
    from ._feffit_restrained import feffit_restrained
    pars, dsets = _build(groups, nm, root)        # 新的 Group 与路径对象，不复用预拟合的
    res = feffit_restrained(pars, dsets, restraints, c0)
    return res, dsets


def run_fit(data, model: dict, root=None) -> tuple:
    """data: 已做 autobk 的 Group（含 k, chi）。返回 (result, dataset, summary dict)。只接受旧格式（单数据集）模型。"""
    if is_multi(model):
        raise ValueError("多数据集模型请用 fit_multi / xafsmith fit / "
                         "use fit_multi / xafsmith fit for a multi-dataset model")
    nm = normalize_model(model)
    res, ds = _fit_core([data], nm, root)
    summ = summarize(res, model, data)
    _add_restraints(summ, res)
    return res, ds[0], summ


def fit_multi(groups, model: dict, root=None) -> tuple:
    """多数据集同时拟合。groups: {数据集 id: Group}；旧格式模型也接受（1 个数据集，id = sample）。
    返回 (result, [dataset…], 多数据集形状的 summary)。不修改传入的 Group。"""
    nm = normalize_model(model)
    miss = [d["id"] for d in nm["datasets"] if d["id"] not in groups]
    if miss:
        raise KeyError(f"缺少数据集的数据：{', '.join(miss)} / no data for dataset(s): {', '.join(miss)}")
    res, dsets = _fit_core([groups[d["id"]] for d in nm["datasets"]], nm, root)
    return res, dsets, summarize_multi(res, nm, groups)


PULL_WARN = 2.0       # B3：|pull| 超过它给警告（设计档定，约 95% 双侧）


def _restraint_summary(res) -> dict:
    """B3：软约束的摘要键（res 来自 feffit_restrained）。"""
    return dict(restraints=[dict(r) for r in res.restraints], restraint_chi2=float(res.restraint_chi2),
                restraint_c0=float(res.restraint_c0), chi2_data=float(res.chi2_data))


def _add_restraints(summ: dict, res) -> dict:
    """B3：有软约束时在摘要里加键并追加警告；没有则原样返回（不多任何键）。"""
    if not getattr(res, "restraints", None):
        return summ
    summ.update(_restraint_summary(res))
    for r in summ["restraints"]:
        if abs(r["pull"]) > PULL_WARN:
            summ["warnings"].append(f"软约束 {r['name']}（{r['expr']}）偏离先验 {r['pull']:+.1f}σ："
                                    "数据与先验值矛盾，检查先验来源或模型")
    return summ


def _param_table(res, user):
    """与 summarize 中参数表的代码相同（summarize 本身保持 v1.1 原样）。"""
    pars = {}
    for name, p in res.params.items():
        if name not in user:
            continue
        pars[name] = dict(value=float(p.value), stderr=None if p.stderr is None else float(p.stderr),
                          vary=bool(p.vary), expr=p.expr)
    return pars


def _dataset_stats(res):
    """逐数据集残差平方和（用最终参数重算；依赖 larch 私有 _residual，T5 检查其与合计值一致）。

    _residual → ff2chi → create_path_params 会把路径参数重新 add 进传入的 Parameters（stderr 丢失），
    并把 path.params 指向它 → 用 res.params 的深拷贝计算，算完把每条路径的 params 指回 res.params，res 不受影响。"""
    import copy
    saved = [(p, p.params) for ds in res.datasets for p in ds.paths.values()]
    pc = copy.deepcopy(res.params)
    num, den, npts = [], [], []
    try:
        for ds in res.datasets:
            r = ds._residual(pc)
            d = ds._residual(pc, data_only=True)
            num.append(float((r ** 2).sum()))
            den.append(float((d ** 2).sum()))
            npts.append(len(r))
    finally:
        for p, prm in saved:
            p.params = prm
    return num, den, npts


def summarize_multi(res, nm: dict, groups=None) -> dict:
    """多数据集拟合摘要。合计值（n_idp、rfactor、chi2、chi2_reduced）取 larch；逐数据集统计在 datasets 里。
    逐数据集不报 χ²_ν（变量共享，无法分摊）；chi2_share、chi2_per_idp 用来看哪个数据集失配大。"""
    dl = nm["datasets"]
    samples = list(dict.fromkeys(d["sample"] for d in dl))
    nform = [n_idp(d["kmin"], d["kmax"], d["rmin"], d["rmax"]) for d in dl]
    out = dict(model=nm.get("name", ""), multi=True, n_datasets=len(dl), sample="+".join(samples),
               n_idp=float(res.n_independent), n_idp_formula=float(sum(nform)), nvarys=int(res.nvarys),
               rfactor=float(res.rfactor), chi2=float(res.chi_square), chi2_reduced=float(res.chi2_reduced))
    user = set(nm.get("params", {}))
    out["params"] = _param_table(res, user)
    num, den, npts = _dataset_stats(res)
    ntot, ptot = float(res.n_independent), float(sum(npts))
    rows = []
    for d, ds, nf, a, b, n in zip(dl, res.datasets, nform, num, den, npts):
        c2 = a * ntot / ptot
        rows.append(dict(id=d["id"], sample=d["sample"], kmin=d["kmin"], kmax=d["kmax"], rmin=d["rmin"],
                         rmax=d["rmax"], dk=d["dk"], window=d["window"], kweight=str(d["kweight"]),
                         fitspace=d["fitspace"], n_idp=float(ds.n_idp), n_idp_formula=nf, npts=int(n),
                         rfactor=a / b if b > 0 else float("nan"), chi2=c2,
                         chi2_share=c2 / out["chi2"] if out["chi2"] > 0 else float("nan"),
                         chi2_per_idp=c2 / float(ds.n_idp), resid2_per_point=a / n if n else float("nan")))
    out["datasets"] = rows
    warn = []
    if getattr(res, "restraints", None):       # B3：chi2_share 的分母是含约束的总 χ² → Σchi2_share + restraint_share = 1
        out["restraint_share"] = float(res.restraint_chi2) / out["chi2"] if out["chi2"] > 0 else float("nan")
    if res.nvarys > res.n_independent / 2:
        warn.append(f"变量数 {res.nvarys} > N_idp/2 = {res.n_independent / 2:.1f}（全部数据集合计）")
    for name, p in res.params.items():
        if name not in user:
            continue
        if "e0" in name.lower() and p.vary and abs(p.value) > 10:
            warn.append(f"{name}={p.value:.1f} eV 超出 ±10 eV，检查 E0 定义或模型")
        if ("ss" in name.lower() or "sig" in name.lower()) and p.value < 0:
            warn.append(f"{name}={p.value:.4f} < 0，非物理")
    for s in samples:
        ids = [d["id"] for d in dl if d["sample"] == s]
        if len(ids) > 1:
            warn.append(f"样品 {s} 在数据集 {'、'.join(ids)} 中重复使用：同一数据计入两次，误差会被低估")
    if len(rows) > 1:
        # 失配比较用“每个拟合点的残差平方均值”（残差已除以 ε）：与 k 权重个数、ΔR 无关。
        # 不用 χ²/N_idp：k 权重 [1,2,3] 使拟合点数 ×3 而 N_idp 不变，两个都在噪声水平的数据集比值中位数约 3、最大约 10（误报）。
        cp = [r["resid2_per_point"] for r in rows]
        hi, lo = int(np.argmax(cp)), int(np.argmin(cp))
        if cp[lo] > 0 and cp[hi] / cp[lo] > 4:
            a, b = rows[hi]["id"], rows[lo]["id"]
            warn.append(f"数据集 {a} 每个拟合点的残差（以噪声 ε 为单位）平方均值是 {b} 的 {cp[hi] / cp[lo]:.1f} 倍（失配）："
                        f"误差按合计 χ²_ν 统一缩放，{a} 的失配会放大所有参数（包括只属于 {b} 的参数）的误差；"
                        f"先检查 {a} 的模型、k/R 范围或 ε_k")
    out["warnings"] = warn
    # 每条路径：N 的参考 S0² 用该路径自己的振幅参数（若它就是一个参数名），否则同旧格式
    s02g = _s02val(res)
    prows = []
    for d, ds in zip(dl, res.datasets):
        specs = d["paths"]
        if len(specs) != len(ds.paths):        # larch 按 label 存路径，label 冲突时会少路径 → 不能按位置对应
            specs = [{}] * len(ds.paths)        # 退回旧格式的参考 S0²
        for spec, path in zip(specs, ds.paths.values()):
            v = path.path_paramvals()

            def err(pn, path=path):
                p = path.params.get(path.pathpar_name(pn)) if path.params else None
                return None if p is None or p.stderr is None else float(p.stderr)
            aname = spec.get("s02", "s02")
            s02ref = res.params[aname].value if aname in res.params else s02g
            amp = float(path.degen) * float(v["s02"])
            prows.append(dict(path=path.label, reff=float(path.reff), degen=float(path.degen),
                              N=amp / max(s02ref, 1e-9), amp=amp,
                              R=float(path.reff + v["deltar"]), R_err=err("deltar"),
                              sigma2=float(v["sigma2"]), sigma2_err=err("sigma2"),
                              e0=float(v["e0"]), e0_err=err("e0"), deltar=float(v["deltar"]),
                              dataset=d["id"]))
    out["paths"] = prows
    _add_restraints(out, res)
    return out


def dataset_view(summ: dict, ds_id: str) -> dict:
    """把多数据集摘要切成旧形状的单数据集摘要（作图、诊断、质量检查复用）。
    n_idp / n_idp_formula / rfactor 取该数据集；nvarys / chi2 / chi2_reduced / params / warnings 取联合值。"""
    if not summ.get("multi"):
        return summ
    row = next((r for r in summ["datasets"] if r["id"] == ds_id), None)
    if row is None:
        raise KeyError(f"没有数据集 {ds_id} / no dataset {ds_id}")
    extra = {k: summ[k] for k in ("restraints", "restraint_chi2", "restraint_c0", "chi2_data") if k in summ}
    return dict(extra, model=f"{summ['model']}[{ds_id}]", sample=row["sample"], dataset=ds_id,
                kmin=row["kmin"], kmax=row["kmax"], rmin=row["rmin"], rmax=row["rmax"],
                kweight=row["kweight"], fitspace=row["fitspace"],
                n_idp=row["n_idp"], n_idp_formula=row["n_idp_formula"], nvarys=summ["nvarys"],
                rfactor=row["rfactor"], chi2=summ["chi2"], chi2_reduced=summ["chi2_reduced"],
                params=summ["params"], warnings=summ["warnings"],
                paths=[p for p in summ["paths"] if p.get("dataset") == ds_id],
                joint=dict(n_datasets=summ["n_datasets"], rfactor=summ["rfactor"], n_idp=summ["n_idp"]))


def model_curves_all(dsets, nm) -> dict:
    """{数据集 id: model_curves(ds)}"""
    return {d["id"]: model_curves(ds) for d, ds in zip(nm["datasets"], dsets)}


def summarize(res, model, data=None):
    nidp = n_idp(model["kmin"], model["kmax"], model["rmin"], model["rmax"])
    out = dict(model=model.get("name", ""), sample=getattr(data, "label", ""),
               kmin=model["kmin"], kmax=model["kmax"], rmin=model["rmin"], rmax=model["rmax"],
               kweight=str(model.get("kweight")), fitspace=model.get("fitspace", "r"),
               n_idp=float(res.n_independent), n_idp_formula=nidp, nvarys=int(res.nvarys),
               rfactor=float(res.rfactor), chi2=float(res.chi_square),
               chi2_reduced=float(res.chi2_reduced))
    pars = {}
    user = set(model.get("params", {}))
    for name, p in res.params.items():
        if name not in user:          # 跳过 larch 内部的逐路径参数
            continue
        pars[name] = dict(value=float(p.value), stderr=None if p.stderr is None else float(p.stderr),
                          vary=bool(p.vary), expr=p.expr)
    out["params"] = pars
    warn = []
    if res.nvarys > res.n_independent / 2:
        warn.append(f"变量数 {res.nvarys} > N_idp/2 = {res.n_independent / 2:.1f}")
    for name, p in res.params.items():
        if name not in user:
            continue
        if "e0" in name.lower() and p.vary and abs(p.value) > 10:
            warn.append(f"{name}={p.value:.1f} eV 超出 ±10 eV，检查 E0 定义或模型")
        if ("ss" in name.lower() or "sig" in name.lower()) and p.value < 0:
            warn.append(f"{name}={p.value:.4f} < 0，非物理")
    out["warnings"] = warn
    # 每条路径的结果
    prows = []
    s02g = _s02val(res)
    for ds in res.datasets:
        for path in ds.paths.values():
            v = path.path_paramvals()

            def err(pn):
                p = path.params.get(path.pathpar_name(pn)) if path.params else None
                return None if p is None or p.stderr is None else float(p.stderr)
            amp = float(path.degen) * float(v["s02"])
            prows.append(dict(path=path.label, reff=float(path.reff), degen=float(path.degen),
                              N=amp / max(s02g, 1e-9), amp=amp,
                              R=float(path.reff + v["deltar"]), R_err=err("deltar"),
                              sigma2=float(v["sigma2"]), sigma2_err=err("sigma2"),
                              e0=float(v["e0"]), e0_err=err("e0"), deltar=float(v["deltar"])))
    out["paths"] = prows
    return out


def _s02val(res):
    for k in ("s02", "amp", "s0_2", "S02"):
        if k in res.params:
            return res.params[k].value
    return 1.0


def report_text(res) -> str:
    from larch.xafs import feffit_report
    txt = feffit_report(res)
    rs = getattr(res, "restraints", None)
    if not rs:
        return txt
    L = ["", "[[Restraints / 软约束]]",
         f"   c0 (unrestrained chi2_reduced) = {res.restraint_c0:.6g}",
         "   term = c0 * ((expr - value)/sigma)^2"]
    for r in rs:
        L.append(f"   {r['name']}: {r['expr']}  prior {r['value']:.6g} +/- {r['sigma']:.6g}  "
                 f"fitted {r['fitted']:.6g}  pull {r['pull']:+.3f}  c0*t^2 = {r['chi2']:.6g}")
    L.append(f"   chi_square = chi2_data + restraint_chi2 = {res.chi2_data:.6g} + {res.restraint_chi2:.6g}"
             f" = {res.chi_square:.6g}")
    return txt.rstrip("\n") + "\n" + "\n".join(L) + "\n"


def write_result_row(summ, csv=None):
    """一行一个拟合：样品、路径、N、R、σ²、ΔE0、S0²、R 因子、χ²_ν、N_idp、参数个数"""
    from .paths import FITS_CSV
    csv = Path(csv or FITS_CSV)
    csv.parent.mkdir(parents=True, exist_ok=True)
    if summ.get("multi"):
        return _write_multi_rows(summ, csv)
    rows = []
    s02 = summ["params"].get("s02", {}).get("value", np.nan)
    for p in summ["paths"]:
        rows.append(dict(sample=summ["sample"], model=summ["model"], path=p["path"],
                         N=round(p["N"], 3), R=round(p["R"], 4), sigma2=round(p["sigma2"], 5),
                         dE0=round(p["e0"], 2), S02=s02, rfactor=summ["rfactor"],
                         chi2_reduced=summ["chi2_reduced"], n_idp=summ["n_idp"],
                         nvarys=summ["nvarys"],
                         k_range=f"{summ['kmin']}-{summ['kmax']}",
                         R_range=f"{summ['rmin']}-{summ['rmax']}", kweight=summ["kweight"],
                         params=json.dumps({k: [v["value"], v["stderr"]]
                                            for k, v in summ["params"].items()},
                                           ensure_ascii=False)))
    _csv_restraint_cols(rows, summ)
    df = pd.DataFrame(rows)
    csv = Path(csv)
    csv.parent.mkdir(parents=True, exist_ok=True)
    from .common import append_csv
    append_csv(df, csv)
    return df


def _csv_restraint_cols(rows, summ):
    """B3：有软约束时加列 restraint_chi2、restraint_c0、restraints（JSON {name: [拟合值, 先验值, sigma, pull]}）。"""
    if not summ.get("restraints"):
        return
    js = json.dumps({r["name"]: [r["fitted"], r["value"], r["sigma"], r["pull"]] for r in summ["restraints"]},
                    ensure_ascii=False)
    for row in rows:
        row.update(restraint_chi2=summ["restraint_chi2"], restraint_c0=summ["restraint_c0"], restraints=js)


def _write_multi_rows(summ, csv):
    """多数据集：每条路径一行；sample / k_range / R_range / kweight 取该行所属数据集，
    rfactor / chi2_reduced / n_idp / nvarys 为联合值；另有 dataset、n_datasets、rfactor_dataset、n_idp_dataset、chi2_share。"""
    from .common import append_csv
    s02 = summ["params"].get("s02", {}).get("value", np.nan)
    by_id = {r["id"]: r for r in summ["datasets"]}
    rows = []
    for p in summ["paths"]:
        d = by_id[p["dataset"]]
        rows.append(dict(sample=d["sample"], model=summ["model"], path=p["path"],
                         N=round(p["N"], 3), R=round(p["R"], 4), sigma2=round(p["sigma2"], 5),
                         dE0=round(p["e0"], 2), S02=s02, rfactor=summ["rfactor"],
                         chi2_reduced=summ["chi2_reduced"], n_idp=summ["n_idp"],
                         nvarys=summ["nvarys"],
                         k_range=f"{d['kmin']}-{d['kmax']}",
                         R_range=f"{d['rmin']}-{d['rmax']}", kweight=d["kweight"],
                         params=json.dumps({k: [v["value"], v["stderr"]]
                                            for k, v in summ["params"].items()},
                                           ensure_ascii=False),
                         dataset=d["id"], n_datasets=summ["n_datasets"], rfactor_dataset=d["rfactor"],
                         n_idp_dataset=d["n_idp"], chi2_share=d["chi2_share"]))
    _csv_restraint_cols(rows, summ)
    df = pd.DataFrame(rows)
    append_csv(df, csv)
    return df


def hamilton_test(small, large):
    """比较嵌套模型（small 参数少）。返回 F 统计量与 p 值（Hamilton 1965 / Downward 2007）。"""
    from scipy.stats import f as fdist
    nidp = large.n_independent
    b = large.nvarys - small.nvarys
    dof = nidp - large.nvarys
    if b <= 0 or dof <= 0:
        return dict(F=np.nan, p=np.nan, note="自由度不足")
    rr = small.chi_square / large.chi_square
    F = (rr - 1.0) * dof / b
    p = 1 - fdist.cdf(F, b, dof)
    return dict(F=float(F), p=float(p), b=int(b), dof=float(dof),
                note="p<0.05 时加入的参数/路径显著")


def _fit_ranges(model):
    return [tuple(str(d[k]) for k in ("sample", "kmin", "kmax", "rmin", "rmax", "kweight", "fitspace"))
            for d in normalize_model(model)["datasets"]]


def ftest_blockers(model_small, model_large) -> list[str]:
    """F 检验不适用的原因（双语）；空列表 = 无已知障碍。文字与 `xafsmith ftest` 的提示逐字相同。"""
    out = []
    if _fit_ranges(model_small) != _fit_ranges(model_large):
        out.append("两个模型的数据或拟合范围不同，F 检验不适用 / the two models use different data or fit ranges: "
                   "the F-test does not apply")
    if normalize_model(model_small)["restraints"] != normalize_model(model_large)["restraints"]:
        out.append("两个模型的软约束不同，χ² 含不同的约束项，F 检验不适用 / the two models have different restraints: "
                   "their χ² contain different restraint terms, the F-test does not apply")
    return out


COMPARE_NOTE = ("F 检验只对嵌套模型有效（小模型是大模型的特例），软件不检查嵌套关系，须自行保证 / "
                "The F-test is valid only for nested models; nesting is not checked by the software.")


def compare_models(entries) -> pd.DataFrame:
    """多模型比较表。entries: [dict(name, model, result, summ)]；按 nvarys 升序（稳定排序），
    第 i 行与第 i-1 行做 F 检验（调用 hamilton_test，数值不另算）。"""
    order = sorted(entries, key=lambda e: e["summ"]["nvarys"])
    cols = ["model", "n_datasets", "samples", "nvarys", "n_idp", "rfactor", "chi2_reduced", "chi_square",
            "n_restraints", "vs", "F", "p", "b", "dof", "note"]
    rows = []
    for i, e in enumerate(order):
        nm = normalize_model(e["model"])
        s = e["summ"]
        row = dict(model=e["name"], n_datasets=len(nm["datasets"]),
                   samples=";".join(dict.fromkeys(d["sample"] for d in nm["datasets"])),
                   nvarys=s["nvarys"], n_idp=s["n_idp"], rfactor=s["rfactor"], chi2_reduced=s["chi2_reduced"],
                   chi_square=e["result"].chi_square, n_restraints=len(nm["restraints"] or []),
                   vs=None, F=None, p=None, b=None, dof=None, note=None)
        if i > 0:
            prev = order[i - 1]
            row["vs"] = prev["name"]
            blockers = ftest_blockers(prev["model"], e["model"])
            if blockers:
                row["note"] = "；".join(blockers)
            elif s["nvarys"] == prev["summ"]["nvarys"]:
                row["note"] = "变量数相同，不做 F 检验 / same number of variables: no F-test"
            else:
                h = hamilton_test(prev["result"], e["result"])
                for k in ("F", "p", "b", "dof", "note"):
                    row[k] = h.get(k)
        rows.append(row)
    return pd.DataFrame(rows, columns=cols)


def robustness_variants(model, dk_lo=0.5, dk_hi=1.0, dr=0.2):
    """稳健性检查的拟合条件变化：k 下限 ±dk_lo、k 上限 ±dk_hi、R 上限 ±dr、单一 k 权重 1/2/3"""
    base = dict(kmin=model["kmin"], kmax=model["kmax"], rmax=model["rmax"], kweight=model.get("kweight", 2))
    out = [("基准", {})]
    out += [(f"kmin={base['kmin'] + s:g}", dict(kmin=base["kmin"] + s)) for s in (-dk_lo, dk_lo)
            if base["kmin"] + s >= 1.0]
    out += [(f"kmax={base['kmax'] + s:g}", dict(kmax=base["kmax"] + s)) for s in (-dk_hi, dk_hi)]
    out += [(f"Rmax={base['rmax'] + s:g}", dict(rmax=round(base["rmax"] + s, 3))) for s in (-dr, dr)
            if base["rmax"] + s > model["rmin"] + 0.3]
    kws = base["kweight"] if isinstance(base["kweight"], (list, tuple)) else [base["kweight"]]
    if len(kws) > 1:
        out += [(f"kw={w}", dict(kweight=[w])) for w in (1, 2, 3)]
    return out


def robustness(data, model: dict, root=None, variants=None,
               progress: Callable[[float, str], None] | None = None) -> tuple[pd.DataFrame, pd.DataFrame]:
    """改变拟合条件重复拟合，检查参数是否稳定。

    返回 (table, verdict)：table 每行一个条件，列为 R 因子与各变量的值；
    verdict 每个变量一行：基准值、基准误差、各条件下的最小/最大值、离散度（标准差）、
    离散度/基准误差（> 1 记为“不稳”，即参数随拟合条件的变化超过统计误差）。
    """
    if is_multi(model):            # 不静默降级：下面逐条件 try/except 会把每个条件都变成“错误”行
        raise ValueError("多数据集模型暂不支持稳健性检查（计划在 B2 之后） / "
                         "robustness checks are not yet supported for multi-dataset models (planned after B2)")
    variants = variants or robustness_variants(model)
    rows = []
    for i, (name, change) in enumerate(variants):
        m = json.loads(json.dumps(model))
        m.update(change)
        m["name"] = f"{model.get('name', '')}[{name}]"
        try:
            _, _, s = run_fit(data, m, root)
            row = dict(条件=name, R因子=s["rfactor"], 变量数=s["nvarys"], N_idp=s["n_idp"])
            for k, v in s["params"].items():
                if v["vary"] and not v["expr"]:
                    row[k] = v["value"]
                    row[k + "_err"] = v["stderr"]
        except Exception as ex:
            logs.log.warning("fit_exafs.robustness 出错（已忽略或已提示）", exc_info=True)
            row = dict(条件=name, 错误=str(ex))
        rows.append(row)
        if progress:
            progress((i + 1) / len(variants), name)
    tab = pd.DataFrame(rows)
    base = tab.iloc[0]
    ver = []
    for k in [c for c in tab.columns if c + "_err" in tab.columns]:
        vals = pd.to_numeric(tab[k], errors="coerce")
        err = base.get(k + "_err")
        sd = float(np.nanstd(vals, ddof=1)) if vals.notna().sum() > 1 else np.nan
        ratio = sd / err if err and np.isfinite(err) and err > 0 else np.nan
        ver.append(dict(参数=k, 基准值=base[k], 基准误差=err, 最小=float(np.nanmin(vals)),
                        最大=float(np.nanmax(vals)), 离散度=sd, 离散度_误差比=ratio,
                        判断="不稳" if np.isfinite(ratio) and ratio > 1 else ("稳定" if np.isfinite(ratio) else "—")))
    return tab, pd.DataFrame(ver)


def diagnose(curves, model, e0=None, kweight=2):
    """拟合诊断：残差在哪里、是否已到噪声水平、可能的原因。

    返回 dict：
      k, resid_k        —— k^kw·(数据−拟合)，用于作图
      k_segments        —— DataFrame：k 分段的残差 RMS 与相对中位数的倍数
      r_segments        —— DataFrame：R 分段（窗口内每 0.5 Å，加窗口外 1 Å）局部失配 Σ|Δχ(R)|²/Σ|χ(R)|²
      noise_R           —— 数据在 R 15–25 Å 的 |χ(R)| RMS（白噪声估计）
      resid_R           —— 窗口内 |Δχ(R)| RMS
      ratio             —— resid_R / noise_R（≈1–2：已到噪声；≫2：系统偏差）
      spikes            —— 残差尖峰 [(k, 对应能量 eV 或 None, 偏离倍数)]
      hints             —— 建议（中文，界面会翻译）
    """
    from larch.xafs import xftf
    k, chi = np.asarray(curves["k"]), np.asarray(curves["chi"])
    fit = np.interp(k, curves["kfit"], curves["chifit"])
    kmin, kmax = model["kmin"], model["kmax"]
    rmin, rmax = model["rmin"], model["rmax"]
    res = (chi - fit) * k ** kweight
    inw = (k >= kmin) & (k <= kmax)
    # k 分段
    edges = np.linspace(kmin, kmax, max(3, int(round((kmax - kmin) / 1.5))) + 1)
    seg = []
    for a, b in zip(edges[:-1], edges[1:]):
        w = (k >= a) & (k < b)
        seg.append(dict(k段=f"{a:.1f}–{b:.1f}", 残差RMS=float(np.sqrt(np.mean(res[w] ** 2))) if w.any() else np.nan))
    kseg = pd.DataFrame(seg)
    med = float(np.nanmedian(kseg["残差RMS"]))
    kseg["相对中位数"] = kseg["残差RMS"] / med if med > 0 else np.nan
    # R 空间
    gd, gf, gr = Group(k=k, chi=chi), Group(k=k, chi=fit), Group(k=k, chi=chi - fit)
    for gg in (gd, gf, gr):
        xftf(gg, kmin=kmin, kmax=kmax, dk=model.get("dk", 1), window=model.get("window", "hanning"),
             kweight=kweight, rmax_out=26)
    r = gd.r
    redges = list(np.arange(rmin, rmax - 1e-6, 0.5)) + [rmax]
    rs = []
    for a, b in list(zip(redges[:-1], redges[1:])) + [(rmax, rmax + 1.0)]:
        w = (r >= a) & (r < b)
        num = float(np.sum(np.abs(gd.chir[w] - gf.chir[w]) ** 2))
        den = float(np.sum(np.abs(gd.chir[w]) ** 2))
        rs.append(dict(R段=f"{a:.1f}–{b:.1f}" + ("（窗口外）" if a >= rmax else ""),
                       局部失配=num / den if den > 0 else np.nan, 数据强度=float(np.sqrt(den / max(w.sum(), 1)))))
    rseg = pd.DataFrame(rs)
    wn = (r >= 15) & (r <= 25)
    noise = float(np.sqrt(np.mean(np.abs(gd.chir[wn]) ** 2))) if wn.any() else np.nan
    win = (r >= rmin) & (r <= rmax)
    rres = float(np.sqrt(np.mean(np.abs(gr.chir[win]) ** 2)))
    ratio = rres / noise if noise > 0 else np.nan
    # 尖峰：相对局部平滑的残差
    spikes = []
    if inw.sum() > 10:
        rr = res[inw]
        sm = np.convolve(rr, np.ones(5) / 5, mode="same")
        hf = rr - sm
        mad = float(np.median(np.abs(hf - np.median(hf)))) * 1.4826 or 1e-12
        for i in np.argsort(-np.abs(hf))[:3]:
            if abs(hf[i]) > 5 * mad:
                kk = float(k[inw][i])
                spikes.append((round(kk, 2), None if e0 is None else round(e0 + kk ** 2 / ETOK, 1),
                               round(abs(hf[i]) / mad, 1)))
    hints = []
    if np.isfinite(ratio):
        if ratio < 2:
            hints.append(f"窗口内残差约为噪声的 {ratio:.1f} 倍：已接近噪声水平，继续加路径/参数只会过拟合。")
        else:
            hints.append(f"窗口内残差约为白噪声估计的 {ratio:.1f} 倍：残差主要是系统性的（模型、理论或数据处理），"
                         "不是随机噪声。按下面各条逐一排查。")
    if len(kseg) and kseg["相对中位数"].iloc[0] > 1.5:
        hints.append(f"低 k 段（{kseg['k段'].iloc[0]} Å⁻¹）残差是中位数的 {kseg['相对中位数'].iloc[0]:.1f} 倍："
                     "低 k 受背景扣除与近边效应影响最大。试：kmin 提高 0.5（看稳健性检查）、调 rbkg、或换 FEFF8L 自洽势。")
    if len(kseg) and kseg["相对中位数"].iloc[-1] > 1.5:
        hints.append("高 k 段残差偏大：多为噪声。考虑降低 kmax（看 ② 质量检查的 k_snr3）或多次扫描合并。")
    for kk, ee, sig in spikes:
        hints.append(f"k = {kk} Å⁻¹ 处残差尖峰（{sig:.0f}× 局部噪声）" +
                     (f"，约对应 E = {ee} eV：到 ② 质量检查 → 去毛刺，与平滑趋势比较其前后各点，区间要包含所有偏离点。"
                      if ee else "：检查是否为毛刺。"))
    inside = rseg[~rseg["R段"].str.contains("窗口外")]
    # 谷底（数据强度 < 窗口内中位数的一半）局部失配天然偏大，不据此提示加路径
    strong = inside[inside["数据强度"] >= 0.5 * inside["数据强度"].median()] if len(inside) else inside
    if len(strong):
        worst = strong.loc[strong["局部失配"].idxmax()]
        if worst["局部失配"] > 0.3:
            hints.append(f"R {worst['R段']} Å 局部失配 {worst['局部失配']:.2f}：该处可能缺路径或无序分布不是高斯型。"
                         "加路径前先在已知结构的标样上验证，加入后用 F 检验（⑨ 页），p < 0.05 才保留。")
    out_ = rseg[rseg["R段"].str.contains("窗口外")]
    if len(out_) and out_["局部失配"].iloc[0] > 0.8:
        hints.append("窗口外失配大是正常的（那里不参与拟合）；若想拟合更远的壳层，扩大 Rmax 并加入相应路径，N_idp 也随之增加。")
    return dict(k=k, resid_k=res, k_segments=kseg, r_segments=rseg, noise_R=noise, resid_R=rres,
                ratio=ratio, spikes=spikes, hints=hints)


def model_curves(dset):
    """取出数据与拟合的 k、R 空间曲线（用于作图）。"""
    d, m = dset.data, dset.model
    return dict(k=d.k, chi=d.chi, kfit=m.k, chifit=m.chi, r=d.r, chir_mag=d.chir_mag,
                chir_re=d.chir_re, rfit=m.r, chir_mag_fit=m.chir_mag, chir_re_fit=m.chir_re,
                kwin=d.kwin)


def main():
    from .io import read_any
    from .normalize import normalize
    from .autobk import autobk
    ap = argparse.ArgumentParser()
    ap.add_argument("data")
    ap.add_argument("model")
    ap.add_argument("--out", default=None)
    a = ap.parse_args()
    model = json.loads(Path(a.model).read_text(encoding="utf-8-sig"))
    g = read_any(a.data)
    normalize(g, **model.get("norm", {}))
    autobk(g, **model.get("bkg", {}))
    from .paths import FITS
    out = Path(a.out or FITS)
    res, dset, summ = run_fit(g, model)
    print(report_text(res))
    write_result_row(summ, out / "exafs_fits.csv")
    write_params(out / f"{model.get('name', 'fit')}.params.json", model, "fit_exafs")


if __name__ == "__main__":
    main()
