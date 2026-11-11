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

# 配色方案（命名与配色同 PeakForge：六个风景家族，每族四种）。
# mono：同一色相由深到浅，适合同一系列样品（如不同价态、不同时间点）；poly：色相分明；soft：低饱和、适合印刷；
# cvd：色盲友好。refs：参比 / 标样（金属箔等）的颜色——参照作者 Origin 工程：样品用彩色，标样用灰色。
_GREY = ["#808080", "#C0C0C0", "#A0A0A0", "#606060"]
FAMILIES = {"waters": ("水域", "Waters"), "forests": ("森林", "Forests"), "earth": ("大地", "Earth"),
            "skies": ("天穹", "Skies"), "stone": ("山岩", "Stone"), "fields": ("原野", "Fields")}
KIND_NAMES = {"mono": ("单色渐变", "monochrome"), "poly": ("多色对比", "contrast"), "soft": ("柔和期刊", "soft"),
              "cvd": ("色盲友好", "colour-blind safe")}


def _m(stops):
    """单色：取深到浅的中间 5 档"""
    return stops[1:6]


_RAW = [  # (键, 家族, 类型, 中文, 英文, 颜色)
    ("glacier", "waters", "mono", "冰川", "Glacier", ["#1E5FBF", "#4F83CF", "#709BD9", "#92B3E4", "#B3CCEF"]),
    ("fjord", "waters", "mono", "峡湾", "Fjord", _m(["#0F3D56", "#1F5673", "#2E6F8E", "#5FA3BF", "#A9D3E2", "#DCEFF5"])),
    ("lagoon", "waters", "mono", "泻湖", "Lagoon", _m(["#0B4F4C", "#126B67", "#2A9D8F", "#76C7B7", "#B8E3D6", "#E3F4EE"])),
    ("abyss", "waters", "mono", "深海", "Abyss", _m(["#141E46", "#22306A", "#3B4E92", "#6878B8", "#A3AEDB", "#D6DBF1"])),
    ("moss", "forests", "mono", "苔原", "Moss", _m(["#2E3820", "#4A5A30", "#6B7D45", "#9AAA68", "#C6D09A", "#E6EBCF"])),
    ("pinewood", "forests", "mono", "松林", "Pinewood", _m(["#16301F", "#244A33", "#3A6B4F", "#6E9C80", "#A8C8B3", "#DCEBE1"])),
    ("bamboo", "forests", "soft", "竹林", "Bamboo", ["#4E8B57", "#2F6B6B", "#A8C686", "#D9C77A", "#7FA7A0", "#6B7F3A", "#8C6F4E"]),
    ("rainforest", "forests", "poly", "雨林", "Rainforest", ["#1B6E58", "#D08C2E", "#3E7CB1", "#A2456E", "#6A994E", "#C25B3F", "#4C9A9A", "#8F7FC0"]),
    ("desert", "earth", "mono", "沙漠", "Desert", _m(["#5A3A20", "#7A4E2D", "#B07A45", "#D4A373", "#E9C99A", "#F5E6CA"])),
    ("canyon", "earth", "mono", "峡谷", "Canyon", _m(["#4F2116", "#6B2E1F", "#A4452C", "#CF7445", "#E4A47C", "#F3D3BC"])),
    ("loess", "earth", "soft", "黄土", "Loess", ["#A07A3B", "#7B6A4F", "#C9B07A", "#D9A066", "#8C8C5A", "#B5835A", "#6E5B44"]),
    ("badlands", "earth", "poly", "恶地", "Badlands", ["#A4452C", "#4F6D7A", "#C6893F", "#7E6B8F", "#A9A34E", "#5C4033", "#D28A7C", "#3F5E5A"]),
    ("dawn", "skies", "soft", "晨曦", "Dawn", ["#E08E6D", "#9AA8D8", "#E59BAA", "#F2C38F", "#B79CCF", "#7FB3C8", "#F0A9A0", "#C9B6E4"]),
    ("dusk", "skies", "poly", "暮色", "Dusk", ["#3B2C5A", "#D56E6B", "#6D3F79", "#EDA06A", "#A5507A", "#F4C987", "#4E5D94", "#C98BB0"]),
    ("aurora", "skies", "poly", "极光", "Aurora", ["#1F9E89", "#3E4A89", "#6CCE59", "#7B4FA8", "#2C728E", "#B4DE2C", "#482878", "#35B779"]),
    ("twilight", "skies", "mono", "薄暮", "Twilight", _m(["#1E2540", "#2E3A59", "#4F5D85", "#7F86B0", "#A9A6CC", "#DCD7EC"])),
    ("basalt", "stone", "mono", "玄武（灰度）", "Basalt (greyscale)", ["#000000", "#4F555C", "#7B8189", "#AEB2B8", "#C8CBD0"]),
    ("granite", "stone", "mono", "花岗", "Granite", _m(["#3A3331", "#4A4341", "#7A6E6A", "#A8988F", "#C9B9AF", "#EAE0DA"])),
    ("slate", "stone", "mono", "板岩", "Slate", _m(["#1C262B", "#263238", "#455A64", "#607D8B", "#90A4AE", "#D5DEE2"])),
    ("highland", "stone", "soft", "高地（Tol 柔和）", "Highland (Tol muted)", ["#332288", "#88CCEE", "#44AA99", "#117733", "#999933", "#DDCC77", "#CC6677", "#882255"]),
    ("lavender", "fields", "mono", "薰衣草田", "Lavender", _m(["#2E1F47", "#3E2A5C", "#6A4C93", "#9A7BC2", "#C5B3E0", "#ECE5F6"])),
    ("meadow", "fields", "soft", "草甸", "Meadow", ["#5B8E7D", "#F4A259", "#8CB369", "#BC4B51", "#E9D16B", "#6C91BF", "#A27EA8", "#E0A890"]),
    ("autumn", "fields", "poly", "秋野", "Autumn", ["#9C2C2C", "#E09F3E", "#3E5641", "#D1603D", "#A3A847", "#7B4B3A", "#C9A66B", "#5E7B8C"]),
    ("prairie", "fields", "cvd", "草原（Okabe–Ito）", "Prairie (Okabe–Ito)", ["#000000", "#0072B2", "#D55E00", "#009E73", "#CC79A7", "#E69F00", "#56B4E9"]),
]
PALETTES = {}
for _k, _fam, _kind, _zh, _en, _cs in _RAW:
    _fz, _fe = FAMILIES[_fam]
    PALETTES[_k] = dict(zh=f"{_fz} · {_zh}（{KIND_NAMES[_kind][0]}）", en=f"{_fe} · {_en} ({KIND_NAMES[_kind][1]})",
                        family=_fam, kind=_kind, colors=_cs, ramp=_kind == "mono",
                        refs=None if _k == "basalt" else _GREY)
PALETTES["glacier"]["zh"] = "水域 · 冰川（单色渐变；参照 IrCoOx 工程：样品蓝、标样灰）"
PALETTES["glacier"]["en"] = "Waters · Glacier (monochrome; reference project: blue samples, grey standards)"
DEFAULT_PALETTE = "glacier"
REF_PATTERN = r"foil|powder|metal|箔|标样|std|standard"


def default_refs(labels):
    """名称像参比 / 标样的谱（foil、powder、metal …）"""
    import re
    return [x for x in labels if re.search(REF_PATTERN, str(x), re.I)]


def series_colors(labels, palette="glacier", refs=()):
    """每条谱的 (颜色, 是否标样)。渐变色板按样品数在色带上均匀取色；有 refs 色的方案把标样画成灰色"""
    P = PALETTES.get(palette, PALETTES[DEFAULT_PALETTE])
    refs = set(refs or ())
    has_ref = bool(P.get("refs"))
    smp = [x for x in labels if not (has_ref and x in refs)]
    cs = P["colors"]
    if P.get("ramp") and 1 < len(smp) <= len(cs):
        idx = np.round(np.linspace(0, len(cs) - 1, len(smp))).astype(int)
        pick = [cs[i] for i in idx]
    else:
        pick = [cs[i % len(cs)] for i in range(len(smp))]
    out, i_s, i_r = [], 0, 0
    for x in labels:
        if has_ref and x in refs:
            out.append((P["refs"][i_r % len(P["refs"])], True))
            i_r += 1
        else:
            out.append((pick[i_s], False))
            i_s += 1
    return out


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
        "ytick.labelsize": s["font"] - 1, "legend.fontsize": s["font"], "axes.linewidth": 0.8 * s["lw"],
        "lines.linewidth": s["lw"],
        # 与导出的 Origin 工程一致：四边框线，刻度只在左、下（朝外），上、右框线无刻度，带次刻度
        "xtick.direction": "out", "ytick.direction": "out", "xtick.top": False, "ytick.right": False,
        "xtick.bottom": True, "ytick.left": True, "xtick.minor.visible": True, "ytick.minor.visible": True,
        "xtick.major.size": 0.4 * s["font"], "ytick.major.size": 0.4 * s["font"],
        "xtick.minor.size": 0.2 * s["font"], "ytick.minor.size": 0.2 * s["font"],
        "xtick.major.width": 0.8 * s["lw"], "ytick.major.width": 0.8 * s["lw"],
        "xtick.minor.width": 0.6 * s["lw"], "ytick.minor.width": 0.6 * s["lw"],
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


def _style_of(i, s, colors):
    """colors: series_colors() 的结果；标样线稍细（参照工程：样品 3.5 pt、标样 3 pt）"""
    if not colors:
        return {}
    c, ref = colors[i]
    return dict(color=c, lw=s["lw"] * (0.85 if ref else 1.0))


def xanes(groups, size="单栏 85 mm", xlim=(-20, 60), offset=0.0, relative=True, deriv=False, sub=True, colors=None):
    """归一化 XANES 叠加图（可错开）。relative=True 时横轴为 E − E0(第一条谱)。"""
    fig, (ax,), s = _fig(size)
    e_ref = groups[0].e0
    for i, g in enumerate(groups):
        x = g.energy - (e_ref if relative else 0)
        y = np.gradient(g.flat, g.energy) if deriv else g.flat
        ax.plot(x, y + i * offset, label=chem(g.label, sub), **_style_of(i, s, colors))
    x0 = (0 if relative else e_ref)
    ax.set_xlim(x0 + xlim[0], x0 + xlim[1])
    ax.set_xlabel(f"E − {e_ref:.1f} (eV)" if relative else "Energy (eV)")
    ax.set_ylabel("d(norm. μ)/dE" if deriv else "Normalized μ(E)" + (" (offset)" if offset else ""))
    ax.legend(loc="best")
    cap = "Normalized XANES. " + "; ".join(_caption_group(g) for g in groups)
    return fig, cap


def _fit_color(c, single=False):
    """拟合虚线的颜色逻辑：只有一条谱叠加拟合时用红色（数据黑/蓝，拟合红，最易分辨）；
    多条谱时每条拟合取"自己数据色加深"，一眼看出哪条拟合属于哪条数据；数据为黑色时用红色。"""
    import colorsys
    from matplotlib.colors import to_rgb, to_hex
    rgb = to_rgb(c)
    if single or rgb == (0.0, 0.0, 0.0):
        return COLORS[2]
    h, l, sat = colorsys.rgb_to_hls(*rgb)
    return to_hex(colorsys.hls_to_rgb(h, max(0.0, l * 0.6), min(1.0, sat * 1.1)))


def _fit_caption(groups, fits):
    out = ""
    for g in groups:
        f = (fits or {}).get(g.label)
        if f is not None:
            m = f["summ"]
            out += (f" Fit of {g.label} (model {m['model']}): k = {m['kmin']}–{m['kmax']} Å⁻¹, R = {m['rmin']}–{m['rmax']} Å,"
                    f" R-factor = {m['rfactor']:.4f}, N_idp = {m['n_idp']:.1f}, {m['nvarys']} variables.")
    return out


def chik(groups, size="单栏 85 mm", kweight=2, offset=0.0, kmax=None, sub=True, colors=None, fits=None):
    """fits: {谱名: 拟合 dict(curves, summ, model)}；给出时在对应谱上叠加拟合曲线（虚线）"""
    fig, (ax,), s = _fig(size)
    for i, g in enumerate(groups):
        line, = ax.plot(g.k, g.chi * g.k ** kweight + i * offset, label=chem(g.label, sub), **_style_of(i, s, colors))
        f = (fits or {}).get(g.label)
        if f is not None:
            c = f["curves"]
            ax.plot(c["kfit"], c["chifit"] * c["kfit"] ** kweight + i * offset, color=_fit_color(line.get_color(), len(fits) == 1),
                    ls="--", lw=0.9 * s["lw"], label=chem(g.label, sub) + " fit")
    if kmax:
        ax.set_xlim(0, kmax)
    ax.set_xlabel("k (Å$^{-1}$)")
    ax.set_ylabel(f"k$^{kweight}$χ(k) (Å$^{{-{kweight}}}$)" + (" (offset)" if offset else ""))
    ax.axhline(0, color="0.6", lw=0.5 * s["lw"])
    ax.legend(loc="best")
    return fig, (f"k$^{kweight}$-weighted EXAFS" + ("; dashed: EXAFS fit" if fits else "") + ". "
                 + "; ".join(_caption_group(g) for g in groups) + _fit_caption(groups, fits))


def chir(groups, size="单栏 85 mm", kweight=2, rmax=6.0, offset=0.0, show_re=False, sub=True, colors=None, fits=None):
    from larch import Group
    from larch.xafs import xftf
    fig, (ax,), s = _fig(size)
    for i, g in enumerate(groups):
        fp = dict(getattr(g, "ft_params", {}) or {})
        t = Group(k=g.k, chi=g.chi)
        xftf(t, kmin=fp.get("kmin", 3), kmax=fp.get("kmax", 12), dk=fp.get("dk", 1),
             window=fp.get("window", "hanning"), kweight=kweight)
        line, = ax.plot(t.r, t.chir_mag + i * offset, label=chem(g.label, sub), **_style_of(i, s, colors))
        if show_re:
            ax.plot(t.r, t.chir_re + i * offset, color=line.get_color(), lw=0.6 * s["lw"], ls="--" if not fits else "-")
        f = (fits or {}).get(g.label)
        if f is not None:
            c, md, sm = f["curves"], f.get("model") or {}, f["summ"]
            tf = Group(k=c["kfit"], chi=c["chifit"])
            xftf(tf, kmin=sm["kmin"], kmax=sm["kmax"], dk=md.get("dk", fp.get("dk", 1)),
                 window=md.get("window", fp.get("window", "hanning")), kweight=kweight)
            fc = _fit_color(line.get_color(), len(fits) == 1)
            ax.plot(tf.r, tf.chir_mag + i * offset, color=fc, ls="--", lw=0.9 * s["lw"], label=chem(g.label, sub) + " fit")
            if show_re:
                ax.plot(tf.r, tf.chir_re + i * offset, color=fc, lw=0.6 * s["lw"], ls="--")
            ax.axvspan(sm["rmin"], sm["rmax"], color="0.93", lw=0, zorder=0)
    ax.set_xlim(0, rmax)
    ax.set_xlabel(RLABEL)
    ax.set_ylabel(f"|χ(R)| (Å$^{{-{kweight + 1}}}$)" + (" (offset)" if offset else ""))
    ax.legend(loc="best")
    return fig, (f"Fourier-transformed EXAFS (k$^{kweight}$-weighted, not phase-corrected"
                 + ("; thin lines: real part" if show_re else "")
                 + ("; dashed: EXAFS fit, shaded: fit window" if fits else "") + "). "
                 + "; ".join(_caption_group(g) for g in groups) + _fit_caption(groups, fits))


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
    cb.ax.tick_params(direction="out")
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
