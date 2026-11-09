"""IrTa_series：从 Ta_raw 挑出的 4 条趋势一致的谱（IrTa_0–3）+ 同机时标样（Ta_foil、KTaO3、Ta2O5）。

文件对应见 IrTa_series/文件对应.csv（IrTa_0 = Ta_raw/100-2，IrTa_1 = 50-long，IrTa_2 = 100-1，IrTa_3 = 200）。
样品为荧光（Lytle），标样为透射；校准用本文件夹 Ta_foil（ΔE = +0.14 eV）；S0² = 0.68 固定。
模型与 Ta_Time_resolved 分析相同（scripts/analysis_Ta_time_resolved.py 的 model()）。
输出：IrTa_series/analysis/（趋势图、拟合表、拟合模型、处理后的谱）

用法：
  .venv\\Scripts\\python scripts\\analysis_IrTa_series.py
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
from xafstool import pipeline as pl, report as rp, wavelet as xwav, ft as xft, io as xio   # noqa: E402
from xafstool.fit_exafs import run_fit, hamilton_test, model_curves                       # noqa: E402
from xafstool.common import PROJECT_ROOT, write_params                                    # noqa: E402
import analysis_Ta_time_resolved as tr                                                    # noqa: E402

OUT = PROJECT_ROOT / "IrTa_series" / "analysis"
FIG = OUT / "figs"
for d in (OUT, FIG, OUT / "models", OUT / "data"):
    d.mkdir(parents=True, exist_ok=True)

SAMPLES = ["IrTa_0", "IrTa_1", "IrTa_2", "IrTa_3"]
REF_K, REF_O = "KTaO3_IrTa_series", "Ta2O5_IrTa_series"
ALL = SAMPLES + [REF_K, REF_O]
NAME = {REF_K: "KTaO3", REF_O: "Ta2O5"}
COL = {s: plt.get_cmap("plasma")(i / 3.6) for i, s in enumerate(SAMPLES)}
COL.update({REF_K: "k", REF_O: "0.55"})
REP = 0.02          # 共角链比的重复性（Ta_raw 中 200 与 200_0 截断复测）
CAP = ("Ta L3 | IrTa_0–3：荧光（Lytle），1 次扫描；标样：透射 | 本文件夹 Ta_foil 校准 ΔE=+0.14 eV | E0=导数最大值 | "
       "pre −150…−30, norm 100…end, nnorm=2 | rbkg=1.0 | FT k 3–11, k², Hanning dk=1")
KINDS = ("1shellN6e0", "1shellN6", "1shell", "A", "B", "BK", "BS")


def nm(s):
    return NAME.get(s, s)


def savefig(fig, fn):
    fig.text(0.01, 0.005, CAP, fontsize=7, va="bottom")
    fig.tight_layout(rect=(0, 0.04, 1, 0.96))
    fig.savefig(FIG / fn, dpi=rp.DPI)
    plt.close(fig)


def indicators(G):
    rows = []
    for s in ALL:
        g = G[s]
        e = np.linspace(g.e0 - 20, g.e0 + 80, 4001)
        f = np.interp(e, g.energy, g.flat)
        i = np.argmax(np.where(e < g.e0 + 15, f, 0))
        a = (e >= g.e0 - 5) & (e <= g.e0 + 15)
        xft.forward(g, kmin=3, kmax=11, dk=1, window="hanning", kweight=2)
        p1 = g.chir_mag[(g.r >= 1.0) & (g.r <= 2.0)].max()
        p3 = g.chir_mag[(g.r >= 3.5) & (g.r <= 4.0)].max()
        sel = (g.k >= 2.5) & (g.k <= 11.5)
        kk = g.k[sel]
        w = np.clip(kk - 2.5, 0, 1) * np.clip(11.5 - kk, 0, 1)
        k, r, W = xwav.morlet(kk, g.chi[sel] * w, kweight=2, rmax=4.5)
        W = np.abs(W)
        b = (r >= 3.4) & (r <= 4.1); kb = (k >= 3.5) & (k <= 10.5); Wb = W[b][:, kb]
        rows.append(dict(sample=nm(s), mode=g.mode, E0=round(g.e0, 2), WL_E=round(e[i], 2),
                         WL_height=round(f[i], 3), WL_area=round(np.trapezoid(np.clip(f[a] - 1, 0, None), e[a]), 2),
                         peak1=round(p1, 3), peak_chain=round(p3, 3), chain_ratio=round(p3 / p1, 3),
                         wavelet_kc=round(float((Wb.sum(0) * k[kb]).sum() / Wb.sum()), 2)))
        G[s].wt = (k, r, W)
    df = pd.DataFrame(rows)
    df.to_csv(OUT / "indicators.csv", index=False, encoding="utf-8-sig")
    return df


def fits(G):
    rows, res, curves = [], {}, {}
    for s in ALL:
        for kind in KINDS:
            m = tr.model(s, kind)
            m["name"] = m["name"].replace("TR_", "SER_")
            (OUT / "models" / f"{m['name']}.json").write_text(json.dumps(m, ensure_ascii=False, indent=2), encoding="utf-8")
            r, ds, summ = run_fit(G[s], m)
            res[(s, kind)] = r
            curves[(s, kind)] = (model_curves(ds), summ)
            p = summ["params"]
            row = dict(sample=nm(s), model=kind, k=f"{m['kmin']:g}–{m['kmax']:g}", R=f"{m['rmin']:g}–{m['rmax']:g}",
                       nvarys=summ["nvarys"], n_idp=round(summ["n_idp"], 1), rfactor=round(summ["rfactor"], 4),
                       chi2r=round(summ["chi2_reduced"], 2))
            for k_ in ("e0", "n1", "dr1", "ss1", "nT", "drT", "nK", "nS", "drS"):
                if k_ in p:
                    row[k_] = round(p[k_]["value"], 4)
                    row[k_ + "_err"] = None if p[k_]["stderr"] is None else round(p[k_]["stderr"], 4)
            if "dr1" in p:
                row["R_TaO"] = round(1.9943 + p["dr1"]["value"], 3)
            if "drT" in p:
                row["R_TaTa"] = round(3.9885 + p["drT"]["value"], 3)
            row["warnings"] = "; ".join(summ["warnings"])
            rows.append(row)
        for a, b in (("A", "B"), ("B", "BK"), ("B", "BS")):
            rows.append(dict(sample=nm(s), model=f"F检验 {a}→{b}", p_value=round(hamilton_test(res[(s, a)], res[(s, b)])["p"], 4)))
    df = pd.DataFrame(rows)
    df.to_csv(OUT / "fits_all.csv", index=False, encoding="utf-8-sig")

    # 精简拟合表（每个样品一行）
    def g_(s, kind, c):
        r = df[(df["sample"] == nm(s)) & (df.model == kind)]
        return r[c].iloc[0] if len(r) and c in r else np.nan

    def p_(s, t):
        r = df[(df["sample"] == nm(s)) & (df.model == f"F检验 {t}")]
        return r.p_value.iloc[0]

    tab = []
    for s in ALL:
        tab.append({"样品": nm(s), "模式": G[s].mode,
                    "N(Ta–O)": f"{g_(s, '1shell', 'n1'):.1f} ± {g_(s, '1shell', 'n1_err'):.1f}",
                    "R(Ta–O) Å": f"{g_(s, '1shellN6e0', 'R_TaO'):.3f} ± {g_(s, '1shellN6e0', 'dr1_err'):.3f}",
                    "σ²(Ta–O) Å²": f"{g_(s, '1shellN6e0', 'ss1'):.4f} ± {g_(s, '1shellN6e0', 'ss1_err'):.4f}",
                    "R因子(第一壳层)": g_(s, "1shellN6e0", "rfactor"),
                    "共角链 N_T": f"{g_(s, 'B', 'nT'):.1f} ± {g_(s, 'B', 'nT_err'):.1f}",
                    "R(Ta–Ta) Å": f"{g_(s, 'B', 'R_TaTa'):.3f} ± {g_(s, 'B', 'drT_err'):.3f}",
                    "R因子(B)": g_(s, "B", "rfactor"),
                    "p 共角链(A→B)": p_(s, "A→B"), "p Ta–K(B→BK)": p_(s, "B→BK"), "p 边共享(B→BS)": p_(s, "B→BS")})
    tab = pd.DataFrame(tab)
    tab.to_csv(OUT / "拟合表.csv", index=False, encoding="utf-8-sig")

    fig, axs = plt.subplots(2, 3, figsize=rp.FIGSIZE)
    for ax, s in zip(axs.flat, ALL):
        c, summ = curves[(s, "B")]
        ax.plot(c["r"], c["chir_mag"], "k", label="|χ(R)| 数据")
        ax.plot(c["rfit"], c["chir_mag_fit"], "r--", label="|χ(R)| 拟合")
        ax.plot(c["r"], c["chir_re"], "b", lw=0.7, label="Re 数据")
        ax.plot(c["rfit"], c["chir_re_fit"], "m--", lw=0.7, label="Re 拟合")
        ax.axvspan(1.0, 4.0, color="0.93")
        ax.set_xlim(0, 5); ax.set_title(f"{nm(s)}  R因子={summ['rfactor']:.3f}", fontsize=10)
        ax.set_xlabel("R (Å) — 未相移校正")
    axs.flat[0].legend(fontsize=7)
    fig.suptitle("模型 B：Ta–O + 共角 Ta–O–Ta 链，k 3–11，kw 1,2,3，S0²=%.2f 固定（图中 k² 加权）" % tr.S02)
    savefig(fig, "03_fits_modelB.png")
    return df, tab


def figures(G, ind, df):
    # 01 谱图
    fig, ax = plt.subplots(1, 3, figsize=rp.FIGSIZE)
    for s in ALL:
        g = G[s]
        ls = "--" if s in (REF_K, REF_O) else "-"
        ax[0].plot(g.energy, g.flat, ls, color=COL[s], label=nm(s))
        ax[1].plot(g.k, g.chi * g.k ** 2, ls, color=COL[s], lw=1)
        ax[2].plot(g.r, g.chir_mag, ls, color=COL[s], label=nm(s))
    ax[0].set_xlim(9860, 9960); ax[0].set_xlabel("E (eV)"); ax[0].set_ylabel("归一化 μ(E)"); ax[0].legend(fontsize=8)
    ax[1].set_xlim(2, 13); ax[1].set_xlabel("k (Å$^{-1}$)"); ax[1].set_ylabel("k²χ(k)")
    ax[2].set_xlim(0, 5); ax[2].set_xlabel("R (Å) — 未相移校正"); ax[2].set_ylabel("|χ(R)|")
    ax[2].axvspan(3.5, 4.0, color="0.93"); ax[2].annotate("共角 Ta–O–Ta 链", (3.45, 0.55), fontsize=8)
    fig.suptitle("IrTa_0 → IrTa_3（实线，荧光）与标样（虚线，透射）")
    savefig(fig, "01_spectra.png")

    # 02 趋势
    x = np.arange(4)
    I = ind.set_index("sample")
    T = df[df.model == "1shellN6e0"].set_index("sample")
    B = df[df.model == "B"].set_index("sample")
    fig, ax = plt.subplots(2, 3, figsize=rp.FIGSIZE)
    panels = [
        (ax[0, 0], I.loc[SAMPLES, "chain_ratio"], [REP] * 4, "共角链比 |χ(R)|$_{3.5–4.0}$/第一壳层峰", "chain_ratio", I),
        (ax[0, 1], I.loc[SAMPLES, "wavelet_kc"], None, "小波 k 质心（R 3.4–4.1 Å，Å$^{-1}$）", "wavelet_kc", I),
        (ax[0, 2], B.loc[SAMPLES, "nT"], B.loc[SAMPLES, "nT_err"], "共角链有效 N_T（σ² 固定为 KTaO3 值）", "nT", B),
        (ax[1, 0], T.loc[SAMPLES, "ss1"], T.loc[SAMPLES, "ss1_err"], "Ta–O σ² (Å²)（N=6，ΔE0 固定）", "ss1", T),
        (ax[1, 1], T.loc[SAMPLES, "R_TaO"], T.loc[SAMPLES, "dr1_err"], "R(Ta–O) (Å)（N=6，ΔE0 固定）", "R_TaO", T),
        (ax[1, 2], I.loc[SAMPLES, "WL_height"], None, "XANES 白线高度", "WL_height", I),
    ]
    for a, y, e, title, c, src in panels:
        a.errorbar(x, y, yerr=e, fmt="o-", color="C3", capsize=3, ms=7)
        if c not in ("WL_height",):        # 标样为透射；白线高度跨模式不可比，不画标样线
            a.axhline(src.loc["KTaO3", c], color="k", ls="--", lw=0.8, label="KTaO3（透射）")
            a.axhline(src.loc["Ta2O5", c], color="0.55", ls=":", lw=0.8, label="Ta2O5（透射）")
        a.set_xticks(x); a.set_xticklabels(SAMPLES); a.set_title(title, fontsize=10)
    ax[0, 0].legend(fontsize=8)
    fig.suptitle("IrTa_0 → IrTa_3 的结构指标（误差棒：共角链比 = 重复性 ±0.02，其余 = 拟合误差）")
    savefig(fig, "02_trends.png")

    # 04 小波
    fig, axs = plt.subplots(2, 3, figsize=rp.FIGSIZE)
    for a, s in zip(axs.flat, SAMPLES + [REF_K, REF_O]):
        k, r, W = G[s].wt
        a.contourf(k, r, W, 30, cmap="jet")
        a.set_xlim(3, 11); a.set_ylim(0.8, 4.5); a.set_title(nm(s), fontsize=10)
        a.set_xlabel("k (Å$^{-1}$)"); a.set_ylabel("R (Å) — 未相移校正")
    fig.suptitle("Morlet 小波（η=10, σ=1, k²）")
    savefig(fig, "04_wavelet.png")


def export(G):
    for s in ALL:
        g = G[s]
        xio.write_group_columns(g, OUT / "data" / f"{nm(s)}.nor", cols=("energy", "mu", "flat"))
        np.savetxt(OUT / "data" / f"{nm(s)}.chik", np.column_stack([g.k, g.chi, g.chi * g.k ** 2]), header="k chi k2chi", fmt="%.6g")
        xft.forward(g, kmin=3, kmax=11, dk=1, window="hanning", kweight=2)
        np.savetxt(OUT / "data" / f"{nm(s)}.chir", np.column_stack([g.r, g.chir_mag, g.chir_re, g.chir_im]),
                   header="R(未相移校正) |chi(R)| Re Im ; k 3-11 k^2 hanning dk=1", fmt="%.6g")


if __name__ == "__main__":
    G = {s: pl.build_sample(s)[0] for s in ALL}
    ind = indicators(G)
    df, tab = fits(G)
    figures(G, ind, df)
    export(G)
    pd.set_option("display.width", 250); pd.set_option("display.max_columns", 40)
    print(ind.to_string()); print(tab.to_string())
    write_params(OUT / "analysis.params.json", dict(samples=SAMPLES, refs=[REF_K, REF_O], S02=tr.S02,
                                                    k="3-11", models=list(KINDS)), "analysis_IrTa_series")
