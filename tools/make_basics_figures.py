"""生成《XAFS 基础讲义》的插图与公式图片（中文 / 英文两套）。

用法：python tools/make_basics_figures.py <演示项目目录>
演示项目需含 Ir foil 与 IrO2 的已处理数据，以及内置 IrO2 与 Ir 的 FEFF 计算（output/feff/IrO2_IrL3/site0、
output/feff/Ir_IrL3/site0）。输出到 src/xafsmith/docs/images/basics/。
图中的谱都是实测数据（Ir foil、IrO2，Ir L3 边）或 xraydb / FEFF 的计算值；示意图会在图中注明“示意”。
"""
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
from matplotlib.patches import Circle, FancyArrowPatch, FancyBboxPatch  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "src" / "xafsmith" / "docs" / "images" / "basics"
BLUE, ORANGE, GREEN, PURPLE, GREY, RED = "#266EC4", "#D0812A", "#3E8E5E", "#8E5BB5", "#6B6A64", "#B3372B"

L = {"zh": {}, "en": {}}


def t(zh, en):
    return en if LANG == "en" else zh


def style():
    rc = plt.rcParams
    rc.update(matplotlib.rcParamsDefault)
    rc["font.family"] = ["Microsoft YaHei", "Segoe UI", "Arial", "DejaVu Sans"]
    rc["font.size"] = 10
    rc["axes.unicode_minus"] = False
    rc["axes.spines.top"] = False
    rc["axes.spines.right"] = False
    rc["axes.linewidth"] = 0.8
    rc["lines.linewidth"] = 1.6
    rc["legend.frameon"] = False
    rc["mathtext.fontset"] = "stix"


def save(fig, name):
    d = OUT / LANG
    d.mkdir(parents=True, exist_ok=True)
    fig.savefig(d / f"{name}.png", dpi=150, bbox_inches="tight", facecolor="white")
    plt.close(fig)


def eq(name, tex, size=17):
    """公式图片（与语言无关）"""
    d = OUT / "eq"
    d.mkdir(parents=True, exist_ok=True)
    fig = plt.figure(figsize=(0.1, 0.1))
    fig.text(0, 0, f"${tex}$", fontsize=size)
    fig.savefig(d / f"{name}.png", dpi=150, bbox_inches="tight", pad_inches=0.08, facecolor="white")
    plt.close(fig)


# ----------------------------------------------------------------------------- 公式
def equations():
    style()
    eq("photon_energy", r"E = h\nu = \frac{hc}{\lambda},\qquad E\,[\mathrm{eV}] \approx \frac{12398.4}{\lambda\,[\mathrm{\AA}]}")
    eq("beer_lambert", r"I_1 = I_0\, e^{-\mu t}\qquad\Longrightarrow\qquad \mu t = \ln\frac{I_0}{I_1}")
    eq("mu_mixture", r"\mu = \rho \sum_i w_i \left(\frac{\mu}{\rho}\right)_i")
    eq("bragg", r"\lambda = 2d\,\sin\theta")
    eq("fluo", r"\mu(E) \propto \frac{I_f}{I_0}")
    eq("k_def", r"k = \sqrt{\frac{2m_e\,(E-E_0)}{\hbar^2}} \approx \sqrt{0.2625\,(E-E_0)\,[\mathrm{eV}]}\ \ \mathrm{\AA}^{-1}")
    eq("chi_def", r"\chi(E) = \frac{\mu(E) - \mu_0(E)}{\Delta\mu_0(E_0)}")
    eq("exafs_eq", r"\chi(k) = S_0^2 \sum_j \frac{N_j\, f_j(k)}{k\,R_j^2}\; e^{-2k^2\sigma_j^2}\; e^{-2R_j/\lambda(k)}\;"
                   r"\sin\!\left[2kR_j + \delta_j(k)\right]")
    eq("phase", r"\Delta\phi = 2kR + \delta(k)")
    eq("ft", r"\chi(R) = \frac{1}{\sqrt{2\pi}} \int_{k_{min}}^{k_{max}} w(k)\, k^n \chi(k)\, e^{2ikR}\, dk")
    eq("resolution", r"\Delta R \approx \frac{\pi}{2\,\Delta k}")
    eq("nidp", r"N_{idp} \approx \frac{2\,\Delta k\,\Delta R}{\pi}")
    eq("rfactor", r"\mathcal{R} = \frac{\sum_i \left[\chi_{data}(R_i) - \chi_{fit}(R_i)\right]^2}{\sum_i \chi_{data}(R_i)^2}")
    eq("debye_waller", r"e^{-2k^2\sigma^2},\qquad \sigma^2 = \sigma^2_{static} + \sigma^2_{thermal}")
    eq("lcf", r"\mu_{sample}(E) \approx \sum_i w_i\, \mu_i(E),\qquad \sum_i w_i = 1")
    eq("wavelet", r"W(k,R) = \int \chi(k')\,k'^n\,\psi^*\!\left(\frac{k'-k}{s}\right) dk',\qquad s=\frac{\eta}{2R}")


# ----------------------------------------------------------------------------- 示意图
def fig_absorption_coeff():
    import xraydb
    e = np.linspace(5000, 30000, 4000)
    mu = xraydb.mu_elam("Ir", e)
    fig, ax = plt.subplots(figsize=(6.4, 3.3))
    ax.loglog(e / 1000, mu, color=BLUE)
    for name, ed in xraydb.xray_edges("Ir").items():
        if name in ("L1", "L2", "L3", "K") and 5000 < ed.energy < 30000:
            ax.axvline(ed.energy / 1000, color=GREY, lw=0.7, ls=":")
            ax.text(ed.energy / 1000, mu.max() * 0.8, f" Ir {name}\n {ed.energy:.0f} eV", fontsize=8, color=GREY, va="top")
    ax.set_xlabel(t("X 射线能量 (keV)", "X-ray energy (keV)"))
    ax.set_ylabel(t("质量吸收系数 μ/ρ (cm²/g)", "mass absorption μ/ρ (cm²/g)"))
    ax.set_title(t("Ir 的吸收随能量下降，在吸收边处突然升高（xraydb 数据）",
                   "Ir absorption falls with energy and jumps at each edge (xraydb)"), fontsize=10)
    save(fig, "01_mu_vs_energy")


def fig_levels():
    fig, ax = plt.subplots(figsize=(6.4, 3.6))
    ax.set_xlim(0, 10)
    ax.set_ylim(-0.3, 10)
    ax.axis("off")
    levels = [("K (1s)", 0.8), ("L1 (2s)", 5.2), ("L2 (2p₁/₂)", 5.9), ("L3 (2p₃/₂)", 6.4), ("M …", 8.3)]
    for name, y in levels:
        ax.plot([1, 4.2], [y, y], color=GREY, lw=2)
        ax.text(4.4, y, name, va="center", fontsize=9)
    ax.plot([1, 4.2], [9.6, 9.6], color=GREY, lw=1, ls="--")
    ax.text(4.4, 9.6, t("连续态（电离）", "continuum (ionized)"), va="center", fontsize=9)
    ax.add_patch(Circle((2.6, 6.4), 0.16, color=BLUE))
    ax.add_patch(FancyArrowPatch((2.6, 6.6), (2.6, 9.4), arrowstyle="-|>", mutation_scale=14, color=BLUE, lw=1.6))
    ax.text(2.8, 7.25, t("光电子", "photoelectron"), color=BLUE, fontsize=9)
    ax.add_patch(FancyArrowPatch((0.2, 3.0), (2.4, 6.2), arrowstyle="-|>", mutation_scale=14, color=ORANGE, lw=1.6,
                                 connectionstyle="arc3,rad=-0.2"))
    ax.text(0.1, 2.3, "X 射线 hν" if LANG == "zh" else "X-ray hν", color=ORANGE, fontsize=9)
    ax.text(6.3, 7.4, t("hν ≥ 结合能 E₀ 时，\n内层电子被打出：\n吸收突然增加 = 吸收边",
                        "When hν ≥ binding energy E₀,\na core electron is ejected:\nabsorption jumps = the edge"),
            fontsize=9.5, va="top")
    ax.text(6.3, 3.6, t("Ir：K 边 76 111 eV\n      L3 边 11 215 eV\nCu：K 边 8 979 eV\nTa：L3 边 9 881 eV",
                        "Ir: K edge 76 111 eV\n     L3 edge 11 215 eV\nCu: K edge 8 979 eV\nTa: L3 edge 9 881 eV"),
            fontsize=9, va="top", color=GREY)
    ax.set_title(t("内层能级与吸收边（示意，间距不按比例）", "Core levels and absorption edges (schematic, not to scale)"), fontsize=10)
    save(fig, "02_levels")


def fig_beamline():
    fig, ax = plt.subplots(figsize=(7.2, 2.5))
    ax.set_xlim(0, 14)
    ax.set_ylim(0, 4)
    ax.axis("off")

    def box(x, w, label, col):
        ax.add_patch(FancyBboxPatch((x, 1.4), w, 1.2, boxstyle="round,pad=0.05,rounding_size=0.15", fc=col, ec="none", alpha=0.18))
        ax.text(x + w / 2, 2.0, label, ha="center", va="center", fontsize=8.5)
    ax.add_patch(Circle((1.0, 2.0), 0.9, fill=False, ec=GREY, lw=1.5))
    ax.text(1.0, 2.0, t("储存环\n电子", "storage\nring"), ha="center", va="center", fontsize=8)
    box(2.6, 2.0, t("单色器\nSi(111) 双晶", "monochromator\nSi(111) DCM"), BLUE)
    box(5.4, 1.4, t("I0 电离室", "I0 chamber"), GREEN)
    box(7.5, 1.2, t("样品", "sample"), ORANGE)
    box(9.4, 1.4, t("I1 电离室", "I1 chamber"), GREEN)
    box(11.5, 1.4, t("参比箔 + I2", "ref. foil + I2"), PURPLE)
    ax.plot([1.9, 13.2], [2.0, 2.0], color=RED, lw=0.8, zorder=0)
    ax.add_patch(FancyBboxPatch((7.6, 3.05), 1.0, 0.6, boxstyle="round,pad=0.05", fc=GREEN, ec="none", alpha=0.18))
    ax.text(8.1, 3.35, "If", ha="center", va="center", fontsize=8.5)
    ax.add_patch(FancyArrowPatch((8.1, 2.65), (8.1, 3.0), arrowstyle="-|>", mutation_scale=10, color=GREY))
    ax.text(7.0, 0.5, t("透射：μt = ln(I0/I1)      荧光：μ ∝ If/I0      参比：每次测量同时校准能量",
                        "transmission: μt = ln(I0/I1)    fluorescence: μ ∝ If/I0    reference: calibrates energy in every scan"),
            ha="center", fontsize=8.5, color=GREY)
    ax.set_title(t("XAFS 线站（示意）", "An XAFS beamline (schematic)"), fontsize=10)
    save(fig, "03_beamline")


def fig_waves():
    fig, axs = plt.subplots(1, 2, figsize=(7.2, 3.3))
    for ax, (dr, title) in zip(axs, ((0.0, t("回到吸收原子时同相：吸收增强", "back in phase at the absorber: more absorption")),
                                      (0.5, t("反相：吸收减弱", "out of phase: less absorption")))):
        ax.set_xlim(-1, 9)
        ax.set_ylim(-3.2, 3.2)
        ax.set_aspect("equal")
        ax.axis("off")
        for r in np.arange(0.6, 8.5, 1.0):
            ax.add_patch(Circle((0, 0), r, fill=False, ec=BLUE, lw=0.8, alpha=0.55))
        sx = 6.0 + dr
        for r in np.arange(0.6, 3.2, 1.0):
            ax.add_patch(Circle((sx, 0), r, fill=False, ec=ORANGE, lw=0.8, alpha=0.75, ls="--"))
        ax.add_patch(Circle((0, 0), 0.32, color=BLUE, zorder=3))
        ax.add_patch(Circle((sx, 0), 0.32, color=ORANGE, zorder=3))
        ax.text(0, -0.75, t("吸收原子", "absorber"), ha="center", fontsize=8.5)
        ax.text(sx, -0.75, t("散射原子", "scatterer"), ha="center", fontsize=8.5)
        ax.annotate("", (sx - 0.35, 1.6), (0.35, 1.6), arrowprops=dict(arrowstyle="<->", color=GREY, lw=0.9))
        ax.text(sx / 2, 1.8, "R", ha="center", fontsize=10, color=GREY)
        ax.set_title(title, fontsize=9)
    fig.suptitle(t("出射光电子波（蓝实线）被近邻原子散射回来（橙虚线），两者在吸收原子处干涉（示意）",
                   "Outgoing photoelectron wave (blue) is backscattered by a neighbour (orange dashed) and interferes at the absorber (schematic)"),
                 fontsize=9.5, y=1.02)
    save(fig, "06_waves")


# ----------------------------------------------------------------------------- 实测数据图
def load_demo(demo):
    from xafsmith import paths
    paths.set_root(demo)
    from xafsmith import pipeline as pl
    foil, _ = pl.build_sample("Ir foil")
    oxide, _ = pl.build_sample("IrO2")
    return foil, oxide


def fig_spectrum(foil, oxide):
    g = oxide
    fig, ax = plt.subplots(figsize=(6.8, 3.6))
    ax.plot(g.energy, g.flat, color=BLUE)
    e0 = g.e0
    ax.axvspan(g.energy[0], e0 - 15, color=GREY, alpha=0.06)
    ax.axvspan(e0 - 15, e0 + 50, color=ORANGE, alpha=0.10)
    ax.axvspan(e0 + 50, g.energy[-1], color=GREEN, alpha=0.07)
    ax.text(e0 - 120, 0.25, t("边前", "pre-edge"), color=GREY, fontsize=9)
    ax.text(e0 + 5, 0.15, "XANES", color=ORANGE, fontsize=10, fontweight="bold")
    ax.text(e0 + 300, 1.30, "EXAFS", color=GREEN, fontsize=10, fontweight="bold")
    iwl = np.argmax(g.flat[(g.energy > e0) & (g.energy < e0 + 20)]) + np.searchsorted(g.energy, e0)
    ax.annotate(t("白线", "white line"), (g.energy[iwl], g.flat[iwl]), (e0 + 80, 1.95),
                arrowprops=dict(arrowstyle="->", color=GREY), fontsize=9)
    ax.annotate(t("吸收边 E₀", "edge E₀"), (e0, 0.5), (e0 - 230, 0.85), arrowprops=dict(arrowstyle="->", color=GREY), fontsize=9)
    ax.set_xlabel(t("X 射线能量 E (eV)", "X-ray energy E (eV)"))
    ax.set_ylabel(t("归一化吸收 μ(E)", "normalized μ(E)"))
    ax.set_title(t("实测：IrO₂，Ir L3 边，透射", "Measured: IrO₂, Ir L3 edge, transmission"), fontsize=10)
    save(fig, "04_spectrum_regions")


def fig_xanes(foil, oxide):
    fig, ax = plt.subplots(figsize=(6.4, 3.5))
    for g, lab, col in ((foil, t("Ir 金属箔（0 价）", "Ir foil (Ir⁰)"), GREY), (oxide, t("IrO₂（+4 价）", "IrO₂ (Ir⁴⁺)"), BLUE)):
        ax.plot(g.energy - foil.e0, g.flat, color=col, label=lab)
    ax.set_xlim(-25, 45)
    ax.axhline(1, color=GREY, lw=0.6, ls=":")
    ax.set_xlabel(t("E − E₀(Ir 箔) (eV)", "E − E₀(Ir foil) (eV)"))
    ax.set_ylabel(t("归一化 μ(E)", "normalized μ(E)"))
    ax.legend(loc="lower right")
    ax.set_title(t("实测：氧化后吸收边右移、白线增强（5d 空穴增多）", "Measured: oxidation shifts the edge up and strengthens the white line (more 5d holes)"),
                 fontsize=10)
    save(fig, "05_xanes_valence")


def fig_normalize(foil, oxide):
    g = oxide
    fig, axs = plt.subplots(1, 2, figsize=(7.4, 3.2))
    a = axs[0]
    a.plot(g.energy, g.mu, color=BLUE, label="μ(E)")
    a.plot(g.energy, g.pre_edge, ls="--", color=ORANGE, lw=1.1, label=t("边前线", "pre-edge line"))
    a.plot(g.energy, g.post_edge, ls="--", color=GREEN, lw=1.1, label=t("边后线", "post-edge line"))
    a.annotate("", (g.e0, g.post_edge[np.searchsorted(g.energy, g.e0)]), (g.e0, g.pre_edge[np.searchsorted(g.energy, g.e0)]),
               arrowprops=dict(arrowstyle="<->", color=RED))
    a.text(g.e0 + 20, (g.pre_edge[np.searchsorted(g.energy, g.e0)] + g.post_edge[np.searchsorted(g.energy, g.e0)]) / 2,
           t("边跳 Δμ₀", "edge step Δμ₀"), color=RED, fontsize=9)
    a.set_xlabel("E (eV)")
    a.legend(fontsize=8)
    a.set_title(t("① 原始 μ(E)：边前 / 边后拟合直线", "① raw μ(E) with pre/post-edge lines"), fontsize=9)
    b = axs[1]
    b.plot(g.energy, g.mu, color=BLUE, lw=1.2, label="μ(E)")
    b.plot(g.energy, g.bkg, color=PURPLE, lw=1.2, label=t("平滑背景 μ₀(E)", "smooth background μ₀(E)"))
    b.set_xlim(g.e0 - 50, g.energy[-1])
    b.set_xlabel("E (eV)")
    b.legend(fontsize=8)
    b.set_title(t("② 用样条拟合“没有邻居时”的平滑背景", "② spline background = absorption without neighbours"), fontsize=9)
    save(fig, "07_normalize_background")


def fig_chik(foil, oxide):
    fig, axs = plt.subplots(2, 1, figsize=(6.8, 4.6), sharex=True)
    for a, n in zip(axs, (1, 3)):
        for g, lab, col in ((foil, "Ir foil", GREY), (oxide, "IrO₂", BLUE)):
            a.plot(g.k, g.chi * g.k ** n, color=col, label=lab, lw=1.2)
        a.set_ylabel(f"k$^{n}$χ(k)")
        a.axhline(0, color=GREY, lw=0.5)
    axs[0].legend(loc="upper right")
    axs[1].set_xlabel("k (Å⁻¹)")
    axs[0].set_title(t("实测 χ(k)：k 权重越高，高 k 段（重散射体 Ir 的贡献、也包括噪声）越突出",
                       "Measured χ(k): higher k-weight emphasizes high k (heavy Ir scatterers — and noise)"), fontsize=9.5)
    save(fig, "08_chik")


def fig_ft(foil, oxide):
    from larch import Group
    from larch.xafs import xftf
    fig, ax = plt.subplots(figsize=(6.8, 3.5))
    for g, lab, col in ((foil, "Ir foil", GREY), (oxide, "IrO₂", BLUE)):
        h = Group(k=g.k, chi=g.chi)
        xftf(h, kmin=3, kmax=14, dk=1, window="hanning", kweight=2)
        ax.plot(h.r, h.chir_mag, color=col, label=lab)
    ax.set_xlim(0, 6)
    ax.set_ylim(0, 2.9)
    ax.annotate(t("Ir–O\n真实 1.96–2.00 Å", "Ir–O\ntrue 1.96–2.00 Å"), (1.6, 1.0), (0.3, 2.0), fontsize=8.5,
                arrowprops=dict(arrowstyle="->", color=BLUE), color=BLUE)
    ax.annotate(t("Ir–Ir（金属）\n真实 2.71 Å", "Ir–Ir (metal)\ntrue 2.71 Å"), (2.45, 2.3), (3.2, 1.9), fontsize=8.5,
                arrowprops=dict(arrowstyle="->", color=GREY), color=GREY)
    ax.set_xlabel(t("R (Å) — 未相移校正", "R (Å) — not phase-corrected"))
    ax.set_ylabel(t("|χ(R)| (Å⁻³)", "|χ(R)| (Å⁻³)"))
    ax.legend(loc="upper right")
    ax.set_title(t("实测傅里叶变换：峰对应配位壳层，峰位比真实键长短约 0.3–0.5 Å",
                   "Measured FT: peaks are shells, appearing ~0.3–0.5 Å shorter than the bonds"), fontsize=9.5)
    save(fig, "09_ft")


def fig_params(demo):
    """用 FEFF 计算的 Ir–O 路径，改变 N、σ²、R，看 χ(k) 怎么变"""
    from larch.xafs import feffpath, path2chi
    d = Path(demo) / "output" / "feff" / "IrO2_IrL3" / "site0"
    k = np.linspace(2, 14, 600)

    def chi(N=6, ss=0.003, dr=0.0):
        p = feffpath(str(d / "feff0002.dat") if (d / "feff0002.dat").exists() else str(d / "feff0001.dat"),
                     degen=1, s02=f"0.85*{N}", sigma2=ss, deltar=dr, e0=0)
        path2chi(p, k=k)
        return p.k, p.chi
    fig, axs = plt.subplots(1, 3, figsize=(8.6, 2.9), sharey=True)
    for N, col in ((3, GREY), (6, BLUE)):
        kk, c = chi(N=N)
        axs[0].plot(kk, c * kk ** 2, color=col, label=f"N = {N}")
    axs[0].set_title(t("N 决定振幅", "N sets the amplitude"), fontsize=9.5)
    for ss, col in ((0.002, BLUE), (0.010, ORANGE)):
        kk, c = chi(ss=ss)
        axs[1].plot(kk, c * kk ** 2, color=col, label=f"σ² = {ss} Å²")
    axs[1].set_title(t("σ² 让高 k 衰减", "σ² damps high k"), fontsize=9.5)
    for dr, col in ((0.0, BLUE), (0.1, GREEN)):
        kk, c = chi(dr=dr)
        axs[2].plot(kk, c * kk ** 2, color=col, label=f"ΔR = {dr:+.1f} Å")
    axs[2].set_xlim(8, 14)
    axs[2].set_title(t("R 决定振荡频率（放大高 k）", "R sets the frequency (high k zoom)"), fontsize=9.5)
    for a in axs:
        a.set_xlabel("k (Å⁻¹)")
        a.legend(fontsize=8)
        a.axhline(0, color=GREY, lw=0.5)
    axs[0].set_ylabel("k²χ(k)")
    fig.suptitle(t("FEFF 计算的 Ir–O 单散射路径（IrO₂ 结构）：改变一个参数，其余不变",
                   "FEFF Ir–O single-scattering path (IrO₂ structure): change one parameter at a time"), fontsize=9.5, y=1.04)
    save(fig, "10_params")


def fig_fit(demo, oxide):
    from xafsmith import fit_exafs as xfit
    from xafsmith.qt.state import feff_dirs  # noqa: F401  (确保包可导入)
    d = "output/feff/IrO2_IrL3/site0"
    model = dict(name="IrO2_1shell", sample="IrO2", kmin=3, kmax=14, dk=1, window="hanning", kweight=[1, 2, 3],
                 rmin=1.0, rmax=2.1, fitspace="r",
                 params={"s02": 0.85, "e0": 0.0, "dr1": 0.0, "ss1": {"value": 0.003, "min": 0.0, "max": 0.05}},
                 paths=[dict(file=f"{d}/feff0001.dat", label="Ir-O", N="2", s02="s02", e0="e0", deltar="dr1", sigma2="ss1"),
                        dict(file=f"{d}/feff0002.dat", label="Ir-O", N="4", s02="s02", e0="e0", deltar="dr1", sigma2="ss1")])
    res, dset, summ = xfit.run_fit(oxide, model, root=demo)
    c = xfit.model_curves(dset)
    from larch import Group
    from larch.xafs import xftf
    fig, axs = plt.subplots(1, 2, figsize=(8.2, 3.2))
    axs[0].plot(c["k"], c["chi"] * c["k"] ** 2, color="black", lw=1.1, label=t("数据", "data"))
    axs[0].plot(c["kfit"], c["chifit"] * c["kfit"] ** 2, color=RED, ls="--", label=t("拟合（只含第一壳层）", "fit (first shell only)"))
    axs[0].set_xlabel("k (Å⁻¹)")
    axs[0].set_ylabel("k²χ(k)")
    axs[0].legend(fontsize=8)
    gd, gf = Group(k=c["k"], chi=c["chi"]), Group(k=c["kfit"], chi=c["chifit"])
    for gg in (gd, gf):
        xftf(gg, kmin=3, kmax=14, dk=1, window="hanning", kweight=2)
    axs[1].plot(gd.r, gd.chir_mag, color="black", lw=1.1, label="|χ(R)|")
    axs[1].plot(gf.r, gf.chir_mag, color=RED, ls="--", label=t("拟合", "fit"))
    axs[1].plot(gd.r, gd.chir_re, color=BLUE, lw=0.8, label="Re χ(R)")
    axs[1].plot(gf.r, gf.chir_re, color=ORANGE, lw=0.8, ls="--", label=t("Re 拟合", "Re fit"))
    axs[1].axvspan(1.0, 2.1, color=GREY, alpha=0.1)
    axs[1].set_xlim(0, 5)
    axs[1].set_xlabel(t("R (Å) — 未相移校正", "R (Å) — not phase-corrected"))
    axs[1].legend(fontsize=7.5)
    p = summ["params"]
    fig.suptitle(t(f"IrO₂ 第一壳层拟合（灰色为拟合窗口）：S₀² = {p['s02']['value']:.2f}，ΔR = {p['dr1']['value']:+.3f} Å，"
                   f"σ² = {p['ss1']['value']:.4f} Å²，R 因子 {summ['rfactor']:.3f}",
                   f"IrO₂ first-shell fit (grey: fit window): S₀² = {p['s02']['value']:.2f}, ΔR = {p['dr1']['value']:+.3f} Å, "
                   f"σ² = {p['ss1']['value']:.4f} Å², R-factor {summ['rfactor']:.3f}"), fontsize=9, y=1.03)
    save(fig, "11_fit")
    return summ


def fig_wavelet(foil, oxide):
    from xafsmith import wavelet as xwav
    fig, axs = plt.subplots(1, 2, figsize=(8.0, 3.2), sharey=True)
    for a, (g, lab) in zip(axs, ((foil, "Ir foil"), (oxide, "IrO₂"))):
        m = g.k <= 14
        kk, rr, W = xwav.morlet(g.k[m], g.chi[m], kweight=2, rmax=4.5, eta=10, sigma=1)
        a.pcolormesh(kk, rr, W, shading="auto", cmap="jet")
        a.set_title(lab, fontsize=10)
        a.set_xlabel("k (Å⁻¹)")
    axs[0].set_ylabel(t("R (Å) — 未相移校正", "R (Å) — not phase-corrected"))
    fig.suptitle(t("小波变换（Morlet，k²，η = 10，σ = 1）：Ir–Ir 极大值在 k ≈ 11 Å⁻¹，Ir–O 在 k ≈ 5.5 Å⁻¹",
                   "Wavelet transform (Morlet, k², η = 10, σ = 1): Ir–Ir maximum at k ≈ 11 Å⁻¹, Ir–O at k ≈ 5.5 Å⁻¹"),
                 fontsize=9, y=1.03)
    save(fig, "12_wavelet")


def main():
    global LANG
    demo = Path(sys.argv[1]).resolve()
    LANG = "zh"
    equations()
    for LANG in ("zh", "en"):
        style()
        fig_absorption_coeff()
        fig_levels()
        fig_beamline()
        fig_waves()
        foil, oxide = load_demo(demo)
        fig_spectrum(foil, oxide)
        fig_xanes(foil, oxide)
        fig_normalize(foil, oxide)
        fig_chik(foil, oxide)
        fig_ft(foil, oxide)
        fig_params(demo)
        summ = fig_fit(demo, oxide)
        fig_wavelet(foil, oxide)
    print("ok", {k: round(v["value"], 4) for k, v in summ["params"].items()}, round(summ["rfactor"], 4))


LANG = "zh"
if __name__ == "__main__":
    main()
