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


def report_text(res) -> str:
    from larch.xafs import feffit_report
    return feffit_report(res)


def write_result_row(summ, csv=None):
    """一行一个拟合：样品、路径、N、R、σ²、ΔE0、S0²、R 因子、χ²_ν、N_idp、参数个数"""
    from .paths import FITS_CSV
    csv = Path(csv or FITS_CSV)
    csv.parent.mkdir(parents=True, exist_ok=True)
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
    from .common import append_csv
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
