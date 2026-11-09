"""pubfig —— 期刊风格出图：统一字体、线宽、尺寸与配色，导出 600 dpi TIFF/PNG 与矢量 SVG/PDF。

尺寸（宽 × 高，英寸）：单栏 85 mm、1.5 栏 120 mm、双栏 178 mm；另有 16:9 汇报尺寸（2666×1500 像素）。
字体 Arial（无则 DejaVu Sans）；配色为色盲友好的 Okabe–Ito 色板；坐标轴标签用英文（期刊通用）。
R 空间图的横轴一律注明 “not phase-corrected”。每张图同时写出一个 .txt 图注（样品、边、模式、处理参数）。
"""
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt      # noqa: E402
import numpy as np                   # noqa: E402

SIZES = {
    "单栏 85 mm": dict(w=3.35, h=2.6, font=8, lw=1.0),
    "1.5 栏 120 mm": dict(w=4.72, h=3.3, font=8, lw=1.0),
    "双栏 178 mm": dict(w=7.0, h=3.0, font=8, lw=1.0),
    "汇报 16:9": dict(w=13.333, h=7.5, font=18, lw=2.2),
}
COLORS = ["#000000", "#0072B2", "#D55E00", "#009E73", "#CC79A7", "#E69F00", "#56B4E9", "#F0E442"]
RLABEL = "R (Å, not phase-corrected)"


def chem(label, on=True):
    """化学式数字下标：IrO2 → IrO$_2$（只处理紧跟在字母或右括号后的数字；名称中含 - _ 空格的不处理）"""
    import re
    if not on or re.search(r"[-_\s]", str(label)):
        return str(label)
    return re.sub(r"(?<=[A-Za-z)])(\d+(?:\.\d+)?)", lambda m: "$_{" + m.group(1) + "}$", str(label))


def style(size="单栏 85 mm"):
    s = SIZES[size]
    plt.rcParams.update({
        "font.family": "sans-serif", "font.sans-serif": ["Arial", "Helvetica", "DejaVu Sans"],
        "font.size": s["font"], "axes.labelsize": s["font"], "xtick.labelsize": s["font"] - 1,
        "ytick.labelsize": s["font"] - 1, "legend.fontsize": s["font"] - 1, "axes.linewidth": 0.8 * s["lw"],
        "lines.linewidth": s["lw"], "xtick.direction": "in", "ytick.direction": "in", "xtick.top": True,
        "ytick.right": True, "xtick.major.width": 0.8 * s["lw"], "ytick.major.width": 0.8 * s["lw"],
        "legend.frameon": False, "axes.prop_cycle": plt.cycler(color=COLORS), "axes.unicode_minus": False,
        "savefig.bbox": "tight", "savefig.pad_inches": 0.03, "mathtext.default": "regular",
    })
    return s


def _fig(size, ncols=1):
    s = style(size)
    fig, axs = plt.subplots(1, ncols, figsize=(s["w"], s["h"]))
    return fig, np.atleast_1d(axs), s


def _caption_group(g):
    fp = getattr(g, "ft_params", {}) or {}
    bp = getattr(g, "bkg_params", {}) or {}
    s = f"{g.label}: {g.element} {g.edge}-edge, {g.mode}, {getattr(g, 'nscans', 1)} scan(s)"
    if hasattr(g, "e0"):
        s += f", E0 = {g.e0:.2f} eV (max. of first derivative; calibration shift {getattr(g, 'e_shift', 0):+.2f} eV)"
    if bp:
        s += f", Rbkg = {bp.get('rbkg')} Å"
    if fp:
        s += (f", FT over k = {fp.get('kmin')}–{fp.get('kmax')} Å⁻¹ ({fp.get('window')} window, dk = {fp.get('dk')}),"
              f" k-weight {fp.get('kweight')}")
    return s


def xanes(groups, size="单栏 85 mm", xlim=(-20, 60), offset=0.0, relative=True, deriv=False, sub=True):
    """归一化 XANES 叠加图（可错开）。relative=True 时横轴为 E − E0(第一条谱)。"""
    fig, (ax,), s = _fig(size)
    e_ref = groups[0].e0
    for i, g in enumerate(groups):
        x = g.energy - (e_ref if relative else 0)
        y = np.gradient(g.flat, g.energy) if deriv else g.flat
        ax.plot(x, y + i * offset, label=chem(g.label, sub))
    x0 = (0 if relative else e_ref)
    ax.set_xlim(x0 + xlim[0], x0 + xlim[1])
    ax.set_xlabel(f"E − {e_ref:.1f} (eV)" if relative else "Energy (eV)")
    ax.set_ylabel("d(norm. μ)/dE" if deriv else "Normalized μ(E)" + (" (offset)" if offset else ""))
    ax.legend(loc="best")
    cap = "Normalized XANES. " + "; ".join(_caption_group(g) for g in groups)
    return fig, cap


def chik(groups, size="单栏 85 mm", kweight=2, offset=0.0, kmax=None, sub=True):
    fig, (ax,), s = _fig(size)
    for i, g in enumerate(groups):
        ax.plot(g.k, g.chi * g.k ** kweight + i * offset, label=chem(g.label, sub))
    if kmax:
        ax.set_xlim(0, kmax)
    ax.set_xlabel("k (Å$^{-1}$)")
    ax.set_ylabel(f"k$^{kweight}$χ(k) (Å$^{{-{kweight}}}$)" + (" (offset)" if offset else ""))
    ax.axhline(0, color="0.6", lw=0.5 * s["lw"])
    ax.legend(loc="best")
    return fig, f"k$^{kweight}$-weighted EXAFS. " + "; ".join(_caption_group(g) for g in groups)


def chir(groups, size="单栏 85 mm", kweight=2, rmax=6.0, offset=0.0, show_re=False, sub=True):
    from larch import Group
    from larch.xafs import xftf
    fig, (ax,), s = _fig(size)
    for i, g in enumerate(groups):
        fp = dict(getattr(g, "ft_params", {}) or {})
        t = Group(k=g.k, chi=g.chi)
        xftf(t, kmin=fp.get("kmin", 3), kmax=fp.get("kmax", 12), dk=fp.get("dk", 1),
             window=fp.get("window", "hanning"), kweight=kweight)
        line, = ax.plot(t.r, t.chir_mag + i * offset, label=chem(g.label, sub))
        if show_re:
            ax.plot(t.r, t.chir_re + i * offset, color=line.get_color(), lw=0.6 * s["lw"], ls="--")
    ax.set_xlim(0, rmax)
    ax.set_xlabel(RLABEL)
    ax.set_ylabel(f"|χ(R)| (Å$^{{-{kweight + 1}}}$)" + (" (offset)" if offset else ""))
    ax.legend(loc="best")
    return fig, (f"Fourier-transformed EXAFS (k$^{kweight}$-weighted, not phase-corrected"
                 + ("; dashed: real part" if show_re else "") + "). "
                 + "; ".join(_caption_group(g) for g in groups))


def fit(curves, summ, size="双栏 178 mm", kweight=2, rmax=6.0, model=None):
    """拟合图：左 k^n χ(k)，右 |χ(R)| 与 Re χ(R)，标出拟合窗口"""
    from larch import Group
    from larch.xafs import xftf
    fig, (a1, a2), s = _fig(size, 2)
    c = curves
    a1.plot(c["k"], c["chi"] * c["k"] ** kweight, color="k", label="data")
    a1.plot(c["kfit"], c["chifit"] * c["kfit"] ** kweight, color=COLORS[2], ls="--", label="fit")
    a1.set_xlim(max(0, summ["kmin"] - 0.5), summ["kmax"] + 0.5)
    a1.set_xlabel("k (Å$^{-1}$)"); a1.set_ylabel(f"k$^{kweight}$χ(k) (Å$^{{-{kweight}}}$)")
    a1.legend(loc="best")
    md = model or {}
    gd, gf = Group(k=c["k"], chi=c["chi"]), Group(k=c["kfit"], chi=c["chifit"])
    for gg in (gd, gf):
        xftf(gg, kmin=summ["kmin"], kmax=summ["kmax"], dk=md.get("dk", 1), window=md.get("window", "hanning"),
             kweight=kweight)
    a2.axvspan(summ["rmin"], summ["rmax"], color="0.92", lw=0)
    a2.plot(gd.r, gd.chir_mag, color="k", label="|χ(R)| data")
    a2.plot(gf.r, gf.chir_mag, color=COLORS[2], ls="--", label="|χ(R)| fit")
    a2.plot(gd.r, gd.chir_re, color=COLORS[1], lw=0.6 * s["lw"], label="Re data")
    a2.plot(gf.r, gf.chir_re, color=COLORS[4], lw=0.6 * s["lw"], ls="--", label="Re fit")
    a2.set_xlim(0, rmax); a2.set_xlabel(RLABEL); a2.set_ylabel(f"χ(R) (Å$^{{-{kweight + 1}}}$)")
    a2.legend(loc="best", ncol=2)
    cap = (f"EXAFS fit of {summ['sample']} (model {summ['model']}): k = {summ['kmin']}–{summ['kmax']} Å⁻¹, "
           f"R = {summ['rmin']}–{summ['rmax']} Å (shaded), k-weights {summ['kweight']}, "
           f"R-factor = {summ['rfactor']:.4f}, reduced χ² = {summ['chi2_reduced']:.1f}, "
           f"N_idp = {summ['n_idp']:.1f}, {summ['nvarys']} variables; R axis not phase-corrected.")
    return fig, cap


def wavelet(k, r, W, label="", size="单栏 85 mm", rmax=6.0, kweight=2):
    fig, (ax,), s = _fig(size)
    m = ax.contourf(k, r, W, 40, cmap="viridis")
    cb = fig.colorbar(m, ax=ax)
    cb.ax.tick_params(direction="in")
    ax.set_ylim(r[0], rmax)
    ax.set_xlabel("k (Å$^{-1}$)"); ax.set_ylabel(RLABEL)
    if label:
        ax.set_title(label, fontsize=plt.rcParams["font.size"])
    return fig, f"Wavelet transform (k$^{kweight}$-weighted) of {label}; R not phase-corrected."


def save(fig, caption, base, formats=("tiff", "png", "svg"), dpi=600):
    """保存到 base.<fmt>（TIFF 用 LZW 压缩），并写 base.txt 图注；返回文件列表"""
    base = Path(base)
    base.parent.mkdir(parents=True, exist_ok=True)
    out = []
    for f in formats:
        p = base.with_suffix("." + f)
        kw = dict(dpi=dpi)
        if f == "tiff":
            kw["pil_kwargs"] = {"compression": "tiff_lzw"}
        fig.savefig(p, **kw)
        out.append(p)
    t = base.with_suffix(".txt")
    t.write_text(caption, encoding="utf-8")
    out.append(t)
    plt.close(fig)
    return out
