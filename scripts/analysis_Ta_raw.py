"""Ta_raw 分析：编号被混淆的一组 Ir/KTaO3 样品（Ta L3，荧光），按结构演变程度排序并剔除异常测量。

数据：data/raw/Ta_raw（原始文件来自项目根目录 Ta_raw/，只读副本）；每个文件作为独立样品（raw_<文件名>）
校准：同一机时 Ta_Time_resolved/Ta_foil（本批无参比）；S0² = 0.68
排序依据：主指标 = 共角链峰/第一壳层峰比（与测量模式和振幅绝对值无关；在 Ta_Time_resolved 中随约化时间单调下降）；
  重复性由同一样品的 200 与 200_0（截断到掉束前）估计；差别小于重复性的样品归为一组。
  辅助指标：共角链有效 N（σ² 固定）、第一壳层 σ²、小波 R 3.4–4.1 Å 的 k 质心
输出：Ta_raw/analysis/

用法：
  .venv\\Scripts\\python scripts\\analysis_Ta_raw.py
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
from xafstool.fit_exafs import run_fit, hamilton_test                                     # noqa: E402
from xafstool.common import PROJECT_ROOT, write_params                                    # noqa: E402
import analysis_Ta_time_resolved as tr                                                    # noqa: E402

OUT = PROJECT_ROOT / "Ta_raw" / "analysis"
FIG = OUT / "figs"
for d in (OUT, FIG, OUT / "models", OUT / "data"):
    d.mkdir(parents=True, exist_ok=True)

meta = pl.load_meta()
RAW = meta[meta.batch == "Ta_raw"].sort_values("time", key=lambda s: pd.to_datetime(s, format="%Y/%m/%d %H:%M:%S"))
USED = [s for s, u in zip(RAW["sample"], RAW["use"]) if u != "0"]
REFS = ["KTaO3_Ta_Time_resolved", "Ta2O5_Ta_Time_resolved"]
CAP = ("Ta L3 | 荧光（Lytle）| 1 次扫描 | 同机时 Ta_foil 校准 ΔE=+0.14 eV | E0=导数最大值 | "
       "pre −150…−30, norm 100…end, nnorm=2 | rbkg=1.0 | FT k 3–11, k², Hanning dk=1")


def short(s):
    return s.replace("raw_", "").replace("_Ta_Time_resolved", "(透射参考)")


def savefig(fig, fn):
    fig.text(0.01, 0.005, CAP, fontsize=7, va="bottom")
    fig.tight_layout(rect=(0, 0.04, 1, 0.96))
    fig.savefig(FIG / fn, dpi=rp.DPI)
    plt.close(fig)


def quality():
    """测量质量：I0 掉束、截断、本底、噪声"""
    q = pd.read_csv(PROJECT_ROOT / "results" / "qc_report.csv")
    rows = []
    for _, r in RAW.iterrows():
        g = xio.read_bsrf(PROJECT_ROOT / r.file)
        e = g.energy
        i0n = g.i0 / g.i0[:20].mean()
        zero = np.where((g.ifl <= 0) | (g.i1 <= 0))[0]
        pre = np.mean((g.ifl / g.i0)[(e > 9840) & (e < 9870)])
        post = np.mean((g.ifl / g.i0)[(e > 9920) & (e < 9960)])
        qq = q[q.label == r.file].iloc[0]
        rows.append(dict(file=Path(r.file).name, 测量时间=r.time, use=r["use"], I0最小相对值=round(i0n.min(), 3),
                         零计数起始E=round(e[zero[0]], 1) if len(zero) else "",
                         荧光边前本底=round(pre, 3), 荧光边跳=round(post - pre, 3),
                         本底_边跳比=round(pre / (post - pre), 2), 毛刺=qq.glitch_E if isinstance(qq.glitch_E, str) else "",
                         噪声_epsilon_k=round(qq.epsilon_k, 5), k_snr3=qq.k_snr3, 备注=r.note))
    df = pd.DataFrame(rows)
    df.to_csv(OUT / "quality.csv", index=False, encoding="utf-8-sig")
    return df


REP = 0.02     # 共角链比的重复性（200 vs 200_0 截断：0.185 vs 0.168）


def repeat_200_0():
    from xafstool import calib as xcal, normalize as xn, autobk as xb
    c = pl.edge_cfg(pl.load_config(), "Ta_L3")
    g = xio.read_bsrf(PROJECT_ROOT / "data/raw/Ta_raw/200_0")
    xcal.apply_shift([g], pl.load_calib()["data/raw/Ta_Time_resolved/Ta_foil"]["delta_e"])
    keep = g.energy < 10540.0
    for a in ("energy", "energy_raw", "mu", "i0", "i1", "ifl"):
        v = getattr(g, a, None)
        if isinstance(v, np.ndarray) and len(v) == len(keep):
            setattr(g, a, v[keep])
    xn.normalize(g, **c["norm"]); xb.autobk(g, **c["bkg"])
    return g


def indicators(G):
    rows = []
    for s in USED + REFS:
        g = G[s]
        # XANES
        e = np.linspace(g.e0 - 20, g.e0 + 80, 4001)
        f = np.interp(e, g.energy, g.flat)
        i = np.argmax(np.where(e < g.e0 + 15, f, 0))
        a = (e >= g.e0 - 5) & (e <= g.e0 + 15)
        # FT 指标
        xft.forward(g, kmin=3, kmax=11, dk=1, window="hanning", kweight=2)
        p1 = g.chir_mag[(g.r >= 1.0) & (g.r <= 2.0)].max()
        p3 = g.chir_mag[(g.r >= 3.5) & (g.r <= 4.0)].max()
        # 小波
        sel = (g.k >= 2.5) & (g.k <= 11.5)
        kk = g.k[sel]
        w = np.clip(kk - 2.5, 0, 1) * np.clip(11.5 - kk, 0, 1)
        k, r, W = xwav.morlet(kk, g.chi[sel] * w, kweight=2, rmax=4.5)
        W = np.abs(W)
        b = (r >= 3.4) & (r <= 4.1); kb = (k >= 3.5) & (k <= 10.5); Wb = W[b][:, kb]
        kc = float((Wb.sum(0) * k[kb]).sum() / Wb.sum())
        row = dict(sample=short(s), 测量时间=meta.set_index("sample").loc[s, "time"], mode=g.mode,
                   E0=round(g.e0, 2), WL_E=round(e[i], 2), WL_height=round(f[i], 3),
                   WL_area=round(np.trapezoid(np.clip(f[a] - 1, 0, None), e[a]), 2),
                   peak1=round(p1, 3), peak_chain=round(p3, 3), chain_ratio=round(p3 / p1, 3), wavelet_kc=round(kc, 2))
        # 拟合：第一壳层（N=6, ΔE0 固定）与 A/B（共角链）
        res = {}
        for kind in ("1shellN6e0", "A", "B"):
            m = tr.model(s, kind)
            m["name"] = m["name"].replace("TR_", "RAW_")
            (OUT / "models" / f"{m['name']}.json").write_text(json.dumps(m, ensure_ascii=False, indent=2), encoding="utf-8")
            rr, ds, summ = run_fit(g, m)
            res[kind] = rr
            p = summ["params"]
            if kind == "1shellN6e0":
                row.update(R_TaO=round(1.9943 + p["dr1"]["value"], 3), ss1=round(p["ss1"]["value"], 4),
                           ss1_err=round(p["ss1"]["stderr"], 4), rf_1shell=round(summ["rfactor"], 4))
            if kind == "B":
                row.update(nT=round(p["nT"]["value"], 2), nT_err=round(p["nT"]["stderr"], 2),
                           R_TaTa=round(3.9885 + p["drT"]["value"], 3), rf_B=round(summ["rfactor"], 4))
        row["p_chain"] = round(hamilton_test(res["A"], res["B"])["p"], 4)
        rows.append(row)
        np.savetxt(OUT / "data" / f"{short(s)}.chik", np.column_stack([g.k, g.chi]), header="k chi", fmt="%.6g")
        np.savetxt(OUT / "data" / f"{short(s)}.chir", np.column_stack([g.r, g.chir_mag, g.chir_re]),
                   header="R(未相移校正) |chi(R)| Re ; k 3-11 k^2", fmt="%.6g")
        xio.write_group_columns(g, OUT / "data" / f"{short(s)}.nor", cols=("energy", "mu", "flat"))
    # 重复性：200_0 与 200 是同一样品，截断到掉束前（E < 10540 eV）
    g0 = repeat_200_0()
    xft.forward(g0, kmin=3, kmax=11, dk=1, window="hanning", kweight=2)
    p1 = g0.chir_mag[(g0.r >= 1.0) & (g0.r <= 2.0)].max(); p3 = g0.chir_mag[(g0.r >= 3.5) & (g0.r <= 4.0)].max()
    rows.append(dict(sample="200_0（截断复测，仅估计重复性）", 测量时间=meta.set_index("file").loc["data/raw/Ta_raw/200_0", "time"],
                     mode="fluo_repeat", peak1=round(p1, 3), peak_chain=round(p3, 3), chain_ratio=round(p3 / p1, 3)))
    df = pd.DataFrame(rows)
    # 综合排序（只用本批荧光样品）：有序度越高 → 越接近初始 KTaO3 → 运行时间越短（假设单调演变）
    sub = df[df["mode"] == "fluo"].copy()
    ranks = pd.DataFrame({
        "chain_ratio": sub.chain_ratio.rank(ascending=False),
        "nT": sub.nT.rank(ascending=False),
        "wavelet_kc": sub.wavelet_kc.rank(ascending=False),
        "ss1": sub.ss1.rank(ascending=True),
    })
    sub["辅助_平均名次"] = ranks.mean(axis=1).round(2)
    sub["辅助_名次分散"] = ranks.std(axis=1).round(2)
    sub = sub.sort_values("chain_ratio", ascending=False)
    sub["推断顺序"] = range(1, len(sub) + 1)
    # 分组：相邻差 > 重复性（REP）才断开
    grp, gi, prev = [], 1, None
    for v in sub.chain_ratio:
        if prev is not None and prev - v > REP:
            gi += 1
        grp.append(gi); prev = v
    sub["组"] = grp
    df = df.merge(sub[["sample", "推断顺序", "组", "辅助_平均名次", "辅助_名次分散"]], on="sample", how="left")
    df.to_csv(OUT / "indicators.csv", index=False, encoding="utf-8-sig")
    return df, sub


def figures(G, order):
    cmap = plt.get_cmap("viridis")
    cols = {s: cmap(i / max(1, len(order) - 1)) for i, s in enumerate(order)}
    fig, ax = plt.subplots(1, 3, figsize=rp.FIGSIZE)
    for s in order:
        g = G["raw_" + s]
        xft.forward(g, kmin=3, kmax=11, dk=1, window="hanning", kweight=2)
        ax[0].plot(g.energy, g.flat, color=cols[s], label=s)
        ax[1].plot(g.k, g.chi * g.k ** 2, color=cols[s], lw=1)
        ax[2].plot(g.r, g.chir_mag, color=cols[s], label=s)
    ax[0].set_xlim(9860, 9960); ax[0].set_xlabel("E (eV)"); ax[0].set_ylabel("归一化 μ(E)")
    ax[1].set_xlim(2, 13); ax[1].set_xlabel("k (Å$^{-1}$)"); ax[1].set_ylabel("k²χ(k)")
    ax[2].set_xlim(0, 5); ax[2].set_xlabel("R (Å) — 未相移校正"); ax[2].set_ylabel("|χ(R)|")
    ax[2].axvspan(3.5, 4.0, color="0.92"); ax[2].annotate("共角 Ta–O–Ta 链", (3.5, 0.5), fontsize=8)
    ax[0].legend(fontsize=8, title="按推断顺序（深→浅）")
    fig.suptitle("Ta_raw（荧光）：按推断的演变顺序着色")
    savefig(fig, "01_spectra_ordered.png")

    ind = pd.read_csv(OUT / "indicators.csv").set_index("sample")
    fig, ax = plt.subplots(1, 4, figsize=rp.FIGSIZE)
    x = np.arange(len(order))
    for a, (c, e, lab) in zip(ax, (("chain_ratio", None, "共角链峰 / 第一壳层峰"), ("nT", "nT_err", "共角链有效 N"),
                                    ("wavelet_kc", None, "小波 k 质心 (R 3.4–4.1 Å)"), ("ss1", "ss1_err", "Ta–O σ² (Å²)"))):
        a.errorbar(x, ind.loc[order, c], yerr=None if e is None else ind.loc[order, e], fmt="o-", capsize=3)
        a.set_xticks(x); a.set_xticklabels(order, rotation=45, ha="right", fontsize=8); a.set_title(lab, fontsize=10)
    tr_pk = pd.read_csv(PROJECT_ROOT / "Ta_Time_resolved" / "analysis" / "chir_peaks.csv")
    for _, r in tr_pk.iterrows():
        if r["sample"].startswith("IrTa"):
            ax[0].axhline(r.peak_3p5_4p0 / r.peak1, color="0.6", ls=":", lw=0.8)
            ax[0].annotate(f"时间序列 {r['sample'].replace('(新样品)', '新')}", (len(order) - 1, r.peak_3p5_4p0 / r.peak1),
                           fontsize=7, color="0.4", ha="right", va="bottom")
    ax[0].errorbar(x, ind.loc[order, "chain_ratio"], yerr=REP, fmt="none", ecolor="C0", capsize=3)
    fig.suptitle("排序指标（横轴为推断顺序：左 = 共角链保留最多；主指标为左一，误差棒 = 重复性 ±0.02）")
    savefig(fig, "02_order_indicators.png")

    fig, ax = plt.subplots(1, 2, figsize=rp.FIGSIZE)
    for _, r in RAW.iterrows():
        g = xio.read_bsrf(PROJECT_ROOT / r.file)
        lab = Path(r.file).name + ("（剔除）" if r["use"] == "0" else "")
        ax[0].plot(g.energy, g.i0 / g.i0[:20].mean(), label=lab)
        ax[1].semilogy(g.energy, np.where(g.ifl > 0, g.ifl / g.i0, np.nan), label=lab)
    ax[0].set_xlabel("E (eV)"); ax[0].set_ylabel("I0 / I0(起点)"); ax[0].legend(fontsize=8)
    ax[1].set_xlabel("E (eV)"); ax[1].set_ylabel("If / I0（对数）")
    fig.suptitle("原始通道：200_0 在 10550 eV 后 I0 掉束；IrTa-mem-200 在 10300 eV 有单点 I0 毛刺")
    savefig(fig, "03_raw_channels.png")


if __name__ == "__main__":
    G = {s: pl.build_sample(s)[0] for s in USED + REFS}
    qdf = quality()
    df, sub = indicators(G)
    order = list(sub["sample"])
    figures(G, order)
    pd.set_option("display.width", 250); pd.set_option("display.max_columns", 40)
    print(qdf.drop(columns=["备注"]).to_string())
    print(df.to_string())
    write_params(OUT / "analysis.params.json", dict(samples=USED, refs=REFS, order=order), "analysis_Ta_raw")
