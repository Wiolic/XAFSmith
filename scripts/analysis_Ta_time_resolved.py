"""Ta_Time_resolved 分析：KTaO3 负载 Ir 催化剂在 MEA 中运行不同约化时间后的 Ta L3 XAFS。

样品：IrTa-50 = 新样品（仅通水、未通电，起点）；IrTa-100/200/300 = 运行后，编号为约化时间（只表示先后）。
全部为透射（IrTa-300 文件头写成荧光，用户确认实为透射）。

数据：data/raw/Ta_Time_resolved（原始文件来自项目根目录 Ta_Time_resolved/，只读副本）
校准：同批 Ta_foil（meta.csv ref_file）；S0² = config.json Ta_L3 s02_recommended（0.68，KTaO3 多壳层）
输出：Ta_Time_resolved/analysis/（图、CSV、模型 JSON、params.json）

用法：
  .venv\\Scripts\\python scripts\\analysis_Ta_time_resolved.py [xanes|exafs|wavelet|all]
"""
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

sys.path.insert(0, str(Path(__file__).resolve().parent))
from xafstool import pipeline as pl, report as rp, fit_lcf as xlcf, fit_exafs as xfit   # noqa: E402
from xafstool import wavelet as xwav                                                     # noqa: E402
from xafstool.common import PROJECT_ROOT, write_params                                   # noqa: E402

OUT = PROJECT_ROOT / "Ta_Time_resolved" / "analysis"
FIG = OUT / "figs"
for d in (OUT, FIG):
    d.mkdir(parents=True, exist_ok=True)

REF_K, REF_O = "KTaO3_Ta_Time_resolved", "Ta2O5_Ta_Time_resolved"
SAMPLES = ["IrTa-50", "IrTa-100", "IrTa-200", "IrTa-300"]
TIME = {"IrTa-50": 50, "IrTa-100": 100, "IrTa-200": 200, "IrTa-300": 300}
ALL = [REF_K] + SAMPLES + [REF_O]
SHORT = {REF_K: "KTaO3", REF_O: "Ta2O5", "IrTa-50": "IrTa-50(新样品)"}
COLORS = {REF_K: "k", REF_O: "0.5", "IrTa-50": "#1f77b4", "IrTa-100": "#2ca02c",
          "IrTa-200": "#ff7f0e", "IrTa-300": "#d62728"}
CAP = ("Ta L3 | 透射 | 1 次扫描 | 同批 Ta_foil 校准 ΔE=+0.14 eV | "
       "E0=导数最大值 | pre −150…−30, norm 100…end, nnorm=2 | rbkg=1.0")
S02 = pl.load_config()["edges"]["Ta_L3"]["s02_recommended"]["value"]


def name(s):
    return SHORT.get(s, s)


def load(samples=ALL):
    return {s: pl.build_sample(s)[0] for s in samples}


def savefig(fig, fn, cap=CAP):
    fig.text(0.01, 0.005, cap, fontsize=7, va="bottom")
    fig.tight_layout(rect=(0, 0.04, 1, 0.96))
    fig.savefig(FIG / fn, dpi=rp.DPI)
    plt.close(fig)


# ------------------------------------------------------------------ XANES
def xanes(G):
    rows = []
    for s in ALL:
        g = G[s]
        e = np.linspace(g.e0 - 20, g.e0 + 80, 4001)
        f = np.interp(e, g.energy, g.flat)
        i = np.argmax(np.where(e < g.e0 + 15, f, 0))
        win = (e > g.e0 + 20) & (e < g.e0 + 40)              # 白线后第一个极小（~9913 eV）
        j = np.where(win)[0][np.argmin(f[win])]
        win2 = (e > g.e0 + 45) & (e < g.e0 + 70)             # 第二个宽峰（~9940 eV）
        k2 = np.where(win2)[0][np.argmax(f[win2])]
        a = (e >= g.e0 - 5) & (e <= g.e0 + 15)
        rows.append(dict(sample=name(s), time=TIME.get(s, ""), mode=g.mode, E0=round(g.e0, 2),
                         edge_step=round(g.edge_step, 3),
                         WL_E=round(e[i], 2), WL_height=round(f[i], 3),
                         WL_area_eV=round(np.trapezoid(np.clip(f[a] - 1, 0, None), e[a]), 2),
                         min1_E=round(e[j], 1), min1_height=round(f[j], 3),
                         peak2_E=round(e[k2], 1), peak2_height=round(f[k2], 3)))
    met = pd.DataFrame(rows)
    met.to_csv(OUT / "xanes_metrics.csv", index=False, encoding="utf-8-sig")

    # LCF：端点 = 实测 KTaO3、Ta2O5（同批）
    lrows = []
    for space, lo, hi in (("norm", -20, 40), ("dmude", -15, 25)):
        for s in SAMPLES:
            r = xlcf.lcf(G[s], [G[REF_K], G[REF_O]], xmin=lo, xmax=hi, space=space,
                         labels=["KTaO3", "Ta2O5"])
            lrows.append(dict(sample=name(s), time=TIME.get(s, ""), space=f"{space} {lo}..{hi}",
                              w_KTaO3=round(r["weights"]["KTaO3"], 3),
                              err_KTaO3=round(r["weights_err"]["KTaO3"], 3),
                              w_Ta2O5=round(r["weights"]["Ta2O5"], 3),
                              err_Ta2O5=round(r["weights_err"]["Ta2O5"], 3),
                              rfactor=round(r["rfactor"], 5)))
            for single in ("KTaO3", "Ta2O5"):
                g1 = G[REF_K] if single == "KTaO3" else G[REF_O]
                r1 = xlcf.lcf(G[s], [g1], xmin=lo, xmax=hi, space=space, labels=[single])
                lrows[-1][f"R_only_{single}"] = round(r1["rfactor"], 5)
            if space == "norm":
                rp.plot_lcf(r, out=FIG / f"lcf_xanes_{s}.png")
    lcf = pd.DataFrame(lrows)
    lcf.to_csv(OUT / "xanes_lcf.csv", index=False, encoding="utf-8-sig")

    # 图：XANES 叠图 + 导数 + 差谱
    fig, ax = plt.subplots(1, 3, figsize=rp.FIGSIZE)
    for s in ALL:
        g = G[s]
        ls = "--" if "fluo" in s else "-"
        ax[0].plot(g.energy, g.flat, ls, color=COLORS[s], label=name(s))
        ax[1].plot(g.energy, np.gradient(g.flat, g.energy), ls, color=COLORS[s])
        if s != REF_K:
            ax[2].plot(g.energy, g.flat - np.interp(g.energy, G[REF_K].energy, G[REF_K].flat), ls,
                       color=COLORS[s], label=name(s))
    ax[0].set_xlim(9860, 9980); ax[1].set_xlim(9870, 9905); ax[2].set_xlim(9860, 9980)
    ax[0].set_xlabel("E (eV)"); ax[0].set_ylabel("归一化 μ(E)"); ax[0].legend(fontsize=8)
    ax[1].set_xlabel("E (eV)"); ax[1].set_ylabel("dμ/dE")
    ax[2].axhline(0, color="k", lw=0.5); ax[2].set_xlabel("E (eV)"); ax[2].set_ylabel("样品 − KTaO3")
    ax[2].legend(fontsize=8)
    fig.suptitle("Ta L3 XANES：Ir/KTaO3 催化剂随约化时间（IrTa-50 = 新样品）")
    savefig(fig, "01_xanes.png")
    return met, lcf


# ------------------------------------------------------------------ EXAFS
FK = "feff/KTaO3_TaL3/site0/feff%04d.dat"          # 立方 KTaO3
FS = "feff/Ta2O5 (1)_TaL3/site0/feff%04d.dat"      # 用户提供的 Ta2O5 结构：Ta–Ta 3.332 Å（短，边共享型）
CHAIN = [(4, 6), (6, 12), (7, 6), (8, 6), (9, 6), (10, 24)]   # Ta–Ta 3.99 Å 及共线 Ta–O–Ta 多重散射（文件号, 简并度）
KW = dict(kmin=3.0, kmax=11.0, dk=1, window="hanning", kweight=[1, 2, 3], fitspace="r")
SS_T, SS_K = 0.0058, 0.020                         # KTaO3 多壳层拟合的 σ²（固定，见 notes/2026-11-05）
E0_KTAO3 = 6.42                                    # KTaO3 第一壳层（N=6）拟合的 ΔE0


def P(v, lo, hi, vary=True):
    return {"value": v, "vary": vary, "min": lo, "max": hi}


def model(sample, kind):
    """kind: 1shell | 1shellN6（N=6）| 1shellN6e0（N=6，ΔE0 固定为 KTaO3 值，检验 R–ΔE0 相关）
          A（只 Ta–O，宽窗口）| B（Ta–O + 共角 Ta–Ta 链）| BK（+Ta–K）| BS（+短 Ta–Ta）| BKS"""
    pars = dict(s02={"value": S02, "vary": False}, e0=P(0, -15, 15), n1=P(6, 2, 10),
                dr1=P(0, -0.2, 0.2), ss1=P(0.005, 0.0005, 0.03))
    paths = [dict(file=FK % 1, label="Ta-O", N="n1", deltar="dr1", sigma2="ss1")]
    if kind.startswith("1shellN6"):                 # N 固定 6（3 个变量 ≤ N_idp/2）
        pars["n1"] = {"value": 6, "vary": False}
    if kind == "1shellN6e0":
        pars["e0"] = {"value": E0_KTAO3, "vary": False}
    if kind.startswith("1shell"):
        return dict(name=f"TR_{sample}_{kind}", sample=sample, rmin=1.0, rmax=2.1, params=pars,
                    paths=paths, **KW)
    if kind == "A":
        return dict(name=f"TR_{sample}_A", sample=sample, rmin=1.0, rmax=4.0, params=pars,
                    paths=paths, **KW)
    pars.update(nT=P(4, 0, 12), drT=P(-0.04, -0.12, 0.12), ssT={"value": SS_T, "vary": False})
    paths += [dict(file=FK % i, label=f"Ta-Ta链{i}", N=f"nT*{d}/6", deltar="drT", sigma2="ssT")
              for i, d in CHAIN]
    if "K" in kind:
        pars.update(nK=P(4, 0, 12), ssK={"value": SS_K, "vary": False})
        paths.append(dict(file=FK % 3, label="Ta-K", N="nK", deltar="dr1*sqrt(3)", sigma2="ssK"))
    if "S" in kind:
        pars.update(nS=P(1, 0, 8), drS=P(0, -0.15, 0.15), ssS={"value": SS_T, "vary": False})
        paths.append(dict(file=FS % 9, label="Ta-Ta短", N="nS", deltar="drS", sigma2="ssS"))
    return dict(name=f"TR_{sample}_{kind}", sample=sample, rmin=1.0, rmax=4.0, params=pars,
                paths=paths, **KW)


def exafs(G):
    from xafstool.fit_exafs import run_fit, hamilton_test, model_curves
    MD = OUT / "models"
    MD.mkdir(exist_ok=True)
    rows, res, curves = [], {}, {}
    for s in [REF_K] + SAMPLES:
        for kind in ("1shellN6", "1shellN6e0", "1shell", "A", "B", "BK", "BS", "BKS"):
            m = model(s, kind)
            (MD / f"{m['name']}.json").write_text(json.dumps(m, ensure_ascii=False, indent=2), encoding="utf-8")
            r, ds, summ = run_fit(G[s], m)
            res[(s, kind)] = r
            curves[(s, kind)] = (model_curves(ds), summ)
            p = summ["params"]
            row = dict(sample=name(s), time=TIME.get(s, ""), model=kind, rfactor=round(summ["rfactor"], 4),
                       chi2r=round(summ["chi2_reduced"], 2), nvarys=summ["nvarys"], n_idp=round(summ["n_idp"], 1),
                       warnings="; ".join(summ["warnings"]))
            for k_ in ("e0", "n1", "dr1", "ss1", "nT", "drT", "nK", "nS", "drS"):
                if k_ in p:
                    row[k_] = round(p[k_]["value"], 4)
                    row[k_ + "_err"] = None if p[k_]["stderr"] is None else round(p[k_]["stderr"], 4)
            if "dr1" in p:
                row["R_TaO"] = round(1.9943 + p["dr1"]["value"], 3)
            if "drT" in p:
                row["R_TaTa_chain"] = round(3.9885 + p["drT"]["value"], 3)
            if "drS" in p:
                row["R_TaTa_short"] = round(3.3319 + p["drS"]["value"], 3)
            rows.append(row)
        for a, b in (("A", "B"), ("B", "BK"), ("B", "BS"), ("BK", "BKS")):
            h = hamilton_test(res[(s, a)], res[(s, b)])
            rows.append(dict(sample=name(s), time=TIME.get(s, ""), model=f"F检验 {a}→{b}", p_value=round(h["p"], 4)))
    df = pd.DataFrame(rows)
    df.to_csv(OUT / "exafs_fits.csv", index=False, encoding="utf-8-sig")

    # 图：模型 B（Ta–O + 共角 Ta–Ta 链）的 R 空间拟合，逐样品
    ss = [REF_K] + SAMPLES
    fig, axs = plt.subplots(2, 3, figsize=rp.FIGSIZE)
    for ax, s in zip(axs.flat, ss):
        c, summ = curves[(s, "B")]
        ax.plot(c["r"], c["chir_mag"], "k", label="|χ(R)| 数据")
        ax.plot(c["rfit"], c["chir_mag_fit"], "r--", label="|χ(R)| 拟合")
        ax.plot(c["r"], c["chir_re"], "b", lw=0.7, label="Re 数据")
        ax.plot(c["rfit"], c["chir_re_fit"], "m--", lw=0.7, label="Re 拟合")
        ax.axvspan(1.0, 4.0, color="0.93")
        ax.set_xlim(0, 5); ax.set_title(f"{name(s)}  R因子={summ['rfactor']:.3f}", fontsize=10)
        ax.set_xlabel("R (Å) — 未相移校正")
    axs.flat[0].legend(fontsize=7)
    fig.suptitle("模型 B：Ta–O + 共角 Ta–O–Ta 链（KTaO3 拓扑），k 3–11，kw 1,2,3，S0²=%.2f 固定" % S02)
    savefig(fig, "03_exafs_fits_modelB.png", CAP + " | 图中显示 k² 加权")
    return df, curves


def kspace(G):
    """χ(k) LCF（KTaO3 + Ta2O5，k 3–11，k²）与二壳层强度指标"""
    rows = []
    for s in SAMPLES:
        r = xlcf.lcf(G[s], [G[REF_K], G[REF_O]], xmin=3, xmax=11, space="chik", kweight=2,
                     labels=["KTaO3", "Ta2O5"])
        g = G[s]
        rows.append(dict(sample=name(s), time=TIME.get(s, ""), w_KTaO3=round(r["weights"]["KTaO3"], 3),
                         err=round(r["weights_err"]["KTaO3"], 3), w_Ta2O5=round(r["weights"]["Ta2O5"], 3),
                         rfactor=round(r["rfactor"], 4)))
        rp.plot_lcf(r, out=FIG / f"lcf_chik_{s}.png")
    lk = pd.DataFrame(rows)
    lk.to_csv(OUT / "chik_lcf.csv", index=False, encoding="utf-8-sig")
    # 同一 FT 参数（k 3–11, k², Hanning dk=1）下的 |χ(R)| 指标
    from xafstool import ft as xft
    irows = []
    for s in ALL:
        g = G[s]
        xft.forward(g, kmin=3, kmax=11, dk=1, window="hanning", kweight=2)
        def mx(lo, hi):
            m = (g.r >= lo) & (g.r <= hi)
            return float(g.chir_mag[m].max()), float(g.r[m][np.argmax(g.chir_mag[m])])
        a1, r1 = mx(1.0, 2.0); a2, r2 = mx(2.5, 3.3); a3, r3 = mx(3.5, 4.0)
        irows.append(dict(sample=name(s), time=TIME.get(s, ""), peak1=round(a1, 3), R1=round(r1, 2),
                          peak_2p5_3p3=round(a2, 3), R2=round(r2, 2), peak_3p5_4p0=round(a3, 3), R3=round(r3, 2)))
    ind = pd.DataFrame(irows)
    ind.to_csv(OUT / "chir_peaks.csv", index=False, encoding="utf-8-sig")
    return lk, ind


def export(G):
    """处理后的数据：归一化 μ(E)、χ(k)、χ(R)（k 3–11, k²）"""
    from xafstool import io as xio, ft as xft
    D = OUT / "data"
    D.mkdir(exist_ok=True)
    for s in ALL:
        g = G[s]
        xio.write_group_columns(g, D / f"{s}.nor", cols=("energy", "mu", "norm", "flat"))
        np.savetxt(D / f"{s}.chik", np.column_stack([g.k, g.chi, g.chi * g.k ** 2]), header="k chi k2chi", fmt="%.6g")
        xft.forward(g, kmin=3, kmax=11, dk=1, window="hanning", kweight=2)
        np.savetxt(D / f"{s}.chir", np.column_stack([g.r, g.chir_mag, g.chir_re, g.chir_im]),
                   header="R(未相移校正) |chi(R)| Re Im ; k=3-11 k^2 hanning dk=1", fmt="%.6g")


def figures(G):
    from xafstool import ft as xft
    ss = ALL
    # 02：χ(k) 与 |χ(R)|
    fig, ax = plt.subplots(1, 3, figsize=rp.FIGSIZE)
    for s in ss:
        g = G[s]
        xft.forward(g, kmin=3, kmax=11, dk=1, window="hanning", kweight=2)
        ls = "--" if "fluo" in s else "-"
        ax[0].plot(g.k, g.chi * g.k ** 2, ls, color=COLORS[s], lw=1, label=name(s))
        ax[1].plot(g.r, g.chir_mag, ls, color=COLORS[s], label=name(s))
        ax[2].plot(g.r, g.chir_re, ls, color=COLORS[s], lw=1)
    ax[0].set_xlim(2, 13); ax[0].set_xlabel("k (Å$^{-1}$)"); ax[0].set_ylabel("k²χ(k)"); ax[0].legend(fontsize=8)
    for a in ax[1:]:
        a.set_xlim(0, 5); a.set_xlabel("R (Å) — 未相移校正")
        for x, t in ((3.8, "共角 Ta–O–Ta 链"), (2.9, "Ta–K / Ta–O–O")):
            a.axvline(x, color="0.7", lw=0.6, ls=":")
    ax[1].set_ylabel("|χ(R)|"); ax[2].set_ylabel("Re χ(R)")
    ax[1].annotate("Ta–O", (1.5, 1.3)); ax[1].annotate("共角 Ta–O–Ta 链\n(KTaO3)", (3.6, 0.55), fontsize=8)
    fig.suptitle("Ta L3 EXAFS：k 3–11，k²，Hanning dk=1")
    savefig(fig, "02_chi_k_R.png")

    # 04：参数随约化时间（以新样品 IrTa-50 为起点）
    d = pd.read_csv(OUT / "exafs_fits.csv")
    lk = pd.read_csv(OUT / "chik_lcf.csv").set_index("sample")
    pk = pd.read_csv(OUT / "chir_peaks.csv").set_index("sample")
    wv = pd.read_csv(OUT / "wavelet_centroids.csv").set_index("sample")
    t = np.array([50, 100, 200, 300])
    names = [name(s_) for s_ in SAMPLES]
    XL = "约化时间（50 = 新样品，仅通水未通电）"

    def col(model, c, err=None):
        sub = d[d.model == model].set_index("sample")
        return sub.loc[names, c].astype(float).values, (sub.loc[names, err].astype(float).values if err else None),             float(sub.loc["KTaO3", c])

    fig, ax = plt.subplots(2, 3, figsize=rp.FIGSIZE)
    panels = [("1shellN6e0", "ss1", "ss1_err", "Ta–O σ² (Å²)（N=6，ΔE0 固定）"),
              ("1shellN6e0", "R_TaO", "dr1_err", "R(Ta–O) (Å)（N=6，ΔE0 固定）"),
              ("B", "nT", "nT_err", "共角 Ta–Ta 链 N（σ² 固定为 KTaO3 值）")]
    for a_, (mdl, c, e, lab) in zip(ax[0], panels):
        y, ye, kv = col(mdl, c, e)
        if mdl == "B":
            kv = float(d[(d.model == "BK") & (d["sample"] == "KTaO3")]["nT"].iloc[0])
        a_.errorbar(t, y, yerr=ye, fmt="o-", capsize=3)
        a_.axhline(kv, color="k", ls="--", lw=0.8, label="KTaO3")
        a_.set_title(lab, fontsize=10); a_.set_xlabel(XL, fontsize=8)
    ax[0, 0].legend(fontsize=8)
    for a_, (c, lab, src) in zip(ax[1], (("peak_3p5_4p0", "|χ(R)| 3.5–4.0 Å 峰高（共角链）", pk),
                                          ("w_KTaO3", "χ(k) LCF 中 KTaO3 权重（k 3–11）", lk),
                                          ("kc_3p4_4p1", "小波 R 3.4–4.1 Å 区 k 质心", wv))):
        if c == "w_KTaO3":
            a_.errorbar(t, src.loc[names, c], yerr=src.loc[names, "err"], fmt="o-", capsize=3)
            a_.set_ylim(0, 1.05)
        else:
            a_.plot(t, src.loc[names, c], "o-")
            a_.axhline(src.loc["KTaO3", c], color="k", ls="--", lw=0.8, label="KTaO3")
            a_.axhline(src.loc["Ta2O5", c], color="0.5", ls=":", lw=0.8, label="Ta2O5")
        a_.set_title(lab, fontsize=10); a_.set_xlabel(XL, fontsize=8)
    ax[1, 0].legend(fontsize=8)
    fig.suptitle("结构参数随约化时间（虚线 = KTaO3，点线 = Ta2O5）")
    savefig(fig, "04_trends.png")


def wavelets(G):
    ss = [REF_K] + SAMPLES + [REF_O]
    fig, axs = plt.subplots(2, 3, figsize=rp.FIGSIZE)
    rows = []
    for ax, s in zip(axs.flat, ss):
        g = G[s]
        sel = (g.k >= 2.5) & (g.k <= 11.5)
        kk = g.k[sel]
        w = np.clip((kk - 2.5), 0, 1) * np.clip((11.5 - kk), 0, 1)
        k, r, W = xwav.morlet(kk, g.chi[sel] * w, kweight=2, rmax=4.5)
        W = np.abs(W)
        m = ax.contourf(k, r, W, 30, cmap="jet")
        ax.set_ylim(0.8, 4.5); ax.set_xlim(3, 11); ax.set_title(name(s), fontsize=10)
        ax.set_xlabel("k (Å$^{-1}$)"); ax.set_ylabel("R (Å) — 未相移校正")
        row = dict(sample=name(s))
        for lo, hi, tag in ((1.0, 2.0, "1p0_2p0"), (2.4, 3.3, "2p4_3p3"), (3.4, 4.1, "3p4_4p1")):
            b = (r >= lo) & (r <= hi); kb = (k >= 3.5) & (k <= 10.5); Wb = W[b][:, kb]
            row[f"kc_{tag}"] = round(float((Wb.sum(0) * k[kb]).sum() / Wb.sum()), 2)
            row[f"Wmax_{tag}"] = round(float(Wb.max()), 3)
        rows.append(row)
    fig.suptitle("Morlet 小波（η=10, σ=1, k²，k 3–11）")
    savefig(fig, "05_wavelet.png")
    pd.DataFrame(rows).to_csv(OUT / "wavelet_centroids.csv", index=False, encoding="utf-8-sig")


# ------------------------------------------------------------------ main
if __name__ == "__main__":
    what = sys.argv[1] if len(sys.argv) > 1 else "all"
    G = load()
    if what in ("xanes", "all"):
        met, lcf = xanes(G)
        print(met.to_string()); print(lcf.to_string())
    if what in ("exafs", "all"):
        df, curves = exafs(G)
        pd.set_option("display.width", 250); pd.set_option("display.max_columns", 40)
        print(df.to_string())
    if what in ("kspace", "all"):
        lk, ind = kspace(G)
        print(lk.to_string()); print(ind.to_string())
    if what in ("wavelet", "all"):
        wavelets(G)
    if what in ("export", "all"):
        export(G)
    if what in ("figures", "all"):
        figures(G)
    write_params(OUT / "analysis.params.json", dict(S02=S02, samples=ALL, step=what),
                 "analysis_Ta_time_resolved")
