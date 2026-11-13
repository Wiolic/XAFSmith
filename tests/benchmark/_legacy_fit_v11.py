"""冻结副本，禁止修改。

来源：git show c80380a:src/xafsmith/fit_exafs.py（v1.1）的 _mkparam、build_paths、run_fit、summarize、_s02val 原样复制，
仅把 import 改成 from xafsmith.common import n_idp，build_paths 里的相对导入 from .paths 改成 from xafsmith.paths（tests 不是包，相对导入无法运行）。B1 的 T1 / T10 用它检查新 run_fit 与 v1.1 逐位一致。
"""
from pathlib import Path

from xafsmith.common import n_idp


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
    from xafsmith.paths import ROOT
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


def run_fit(data, model: dict, root=None) -> tuple:
    """data: 已做 autobk 的 Group（含 k, chi）。返回 (result, dataset, summary dict)"""
    from larch.fitting import param_group
    from larch.xafs import feffit_transform, feffit_dataset, feffit
    pars = param_group(**{k: _mkparam(k, v) for k, v in model["params"].items()})
    paths = build_paths(model, root)
    kw = model.get("kweight", 2)
    trans = feffit_transform(kmin=model["kmin"], kmax=model["kmax"], dk=model.get("dk", 1),
                             window=model.get("window", "hanning"), kweight=kw,
                             rmin=model["rmin"], rmax=model["rmax"],
                             fitspace=model.get("fitspace", "r"))
    dset = feffit_dataset(data=data, pathlist=list(paths.values()), transform=trans)
    res = feffit(pars, dset)
    summ = summarize(res, model, data)
    return res, dset, summ


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
