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
     {"file": "feff/IrO2/feff0001.dat", "label": "Ir-O", "N": "2", "s02": "s02",
      "e0": "e0", "deltar": "dr1", "sigma2": "ss1"},
     ...
  ]
}
路径的 N：给出时 degen 置 1，振幅 = s02 × N（N 可为数字或参数表达式）；不给则用 FEFF 简并度。
数值型 "params" 条目默认 vary=True；字符串条目视为表达式（约束）。

输出：参数±误差（larch 已乘 sqrt(χ²_ν)），R 因子、χ²_ν、N_idp、变量数；
      write_result_row() 追加到 results/exafs_fits.csv（一行一个拟合）。
F 检验：hamilton_test(fit_small, fit_large)。

用法：
  python -m xafstool.fit_exafs <数据文件> <model.json> [--out results/]
"""
import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd
from larch import Group
from larch.fitting import param, guess, param_group
from larch.xafs import feffpath, feffit_transform, feffit_dataset, feffit, feffit_report

from .common import n_idp, write_params


def _mkparam(name, spec):
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


def run_fit(data, model, root=None):
    """data: 已做 autobk 的 Group（含 k, chi）。返回 (result, dataset, summary dict)"""
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


def report_text(res):
    return feffit_report(res)


def write_result_row(summ, csv="results/exafs_fits.csv"):
    """一行一个拟合：样品、路径、N、R、σ²、ΔE0、S0²、R 因子、χ²_ν、N_idp、参数个数"""
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
    df = pd.DataFrame(rows)
    csv = Path(csv)
    csv.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(csv, mode="a", header=not csv.exists(), index=False, encoding="utf-8-sig")
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
    ap.add_argument("--out", default="results")
    a = ap.parse_args()
    model = json.loads(Path(a.model).read_text(encoding="utf-8"))
    g = read_any(a.data)
    normalize(g, **model.get("norm", {}))
    autobk(g, **model.get("bkg", {}))
    res, dset, summ = run_fit(g, model, root=Path(a.model).parent)
    print(report_text(res))
    write_result_row(summ, Path(a.out) / "exafs_fits.csv")
    write_params(Path(a.out) / f"{model.get('name', 'fit')}.params.json", model, "fit_exafs")


if __name__ == "__main__":
    main()
