"""report —— 作图（自动图注：样品、边、模式、扫描次数、处理参数）与结果表汇总。

汇报用图：16:9，2666×1500（figsize 13.33×7.5 in, dpi 200）。
R 空间图一律标注“未相移校正”。

用法：
  python -m xafsmith.report results/exafs_fits.csv     # 打印汇总
"""
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

plt.rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei", "DejaVu Sans"]
plt.rcParams["axes.unicode_minus"] = False

FIGSIZE = (13.333, 7.5)
DPI = 200
NOPHASE = "未相移校正 (no phase correction)"


def caption(g):
    """由 group 的处理参数生成图注"""
    s = [f"{g.label} | {g.element} {g.edge} | {g.mode} | scans={getattr(g, 'nscans', 1)}"]
    if hasattr(g, "e0"):
        s.append(f"E0={g.e0:.2f} eV (导数最大值, ΔE_cal={getattr(g, 'e_shift', 0):+.2f})")
    bp = getattr(g, "bkg_params", None)
    if bp:
        s.append(f"rbkg={bp['rbkg']}, kw_bkg={bp['kweight']}")
    fp = getattr(g, "ft_params", None)
    if fp:
        s.append(f"k={fp['kmin']}–{fp['kmax']} 1/Å, {fp['window']} dk={fp['dk']}, kw={fp['kweight']}")
    return " | ".join(s)


def _fig(nc=1):
    fig, axs = plt.subplots(1, nc, figsize=FIGSIZE)
    return fig, np.atleast_1d(axs)


def plot_norm(groups, xlim=(-30, 80), out=None, title=""):
    fig, (ax1, ax2) = _fig(2)
    for g in groups:
        ax1.plot(g.energy - (groups[0].e0 if len(groups) > 1 else 0) + (0 if len(groups) > 1 else 0),
                 g.flat, label=g.label)
        ax2.plot(g.energy, g.dmude / g.edge_step, label=g.label)
    e0 = groups[0].e0
    ax1.set_xlabel(f"E − {e0:.1f} (eV)" if len(groups) > 1 else "E (eV)")
    if len(groups) > 1:
        ax1.set_xlim(*xlim)
    ax1.set_ylabel("归一化 μ(E) (flattened)")
    ax2.set_xlim(e0 + xlim[0], e0 + xlim[1] / 2)
    ax2.set_xlabel("E (eV)"); ax2.set_ylabel("dμ/dE (归一化)")
    ax1.legend(fontsize=8)
    fig.suptitle(title)
    fig.text(0.01, 0.005, "\n".join(caption(g) for g in groups[:4]), fontsize=7, va="bottom")
    return _save(fig, out)


def plot_k_r(groups, kweight=2, rmax=6, out=None, title="", fitwin=None):
    fig, (ax1, ax2) = _fig(2)
    for g in groups:
        ax1.plot(g.k, g.chi * g.k ** kweight, label=g.label)
        ax2.plot(g.r, g.chir_mag, label=g.label)
    g0 = groups[0]
    if hasattr(g0, "kwin"):
        sc = np.max(np.abs(g0.chi * g0.k ** kweight)) * 1.05
        ax1.plot(g0.k, g0.kwin * sc, "k--", lw=0.8, label="窗函数")
    ax1.set_xlabel("k (Å$^{-1}$)"); ax1.set_ylabel(f"k$^{kweight}$χ(k)")
    ax2.set_xlim(0, rmax); ax2.set_xlabel("R (Å) — " + NOPHASE)
    ax2.set_ylabel(f"|χ(R)| (Å$^{{-{kweight + 1}}}$)")
    if fitwin:
        ax2.axvspan(*fitwin, color="0.9")
    ax1.legend(fontsize=8)
    fig.suptitle(title)
    fig.text(0.01, 0.005, "\n".join(caption(g) for g in groups[:4]), fontsize=7, va="bottom")
    return _save(fig, out)


def plot_fit(curves, summ, kweight=2, rmax=6, out=None, title=""):
    fig = plt.figure(figsize=FIGSIZE)
    ax1 = fig.add_subplot(1, 2, 1)
    ax2 = fig.add_subplot(1, 2, 2)
    c = curves
    ax1.plot(c["k"], c["chi"] * c["k"] ** kweight, "k", label="数据")
    ax1.plot(c["kfit"], c["chifit"] * c["kfit"] ** kweight, "r--", label="拟合")
    ax1.plot(c["k"], c["kwin"] * np.max(np.abs(c["chi"] * c["k"] ** kweight)), "g:", lw=0.8)
    ax1.set_xlabel("k (Å$^{-1}$)"); ax1.set_ylabel(f"k$^{kweight}$χ(k)"); ax1.legend()
    ax2.plot(c["r"], c["chir_mag"], "k", label="|χ(R)| 数据")
    ax2.plot(c["rfit"], c["chir_mag_fit"], "r--", label="|χ(R)| 拟合")
    ax2.plot(c["r"], c["chir_re"], "b", lw=0.8, label="Re χ(R) 数据")
    ax2.plot(c["rfit"], c["chir_re_fit"], "m--", lw=0.8, label="Re χ(R) 拟合")
    ax2.axvspan(summ["rmin"], summ["rmax"], color="0.9", label="拟合窗口")
    ax2.set_xlim(0, rmax); ax2.set_xlabel("R (Å) — " + NOPHASE); ax2.legend(fontsize=8)
    txt = (f"{summ['sample']} | 模型 {summ['model']} | R因子={summ['rfactor']:.4f} | "
           f"χ²_ν={summ['chi2_reduced']:.1f} | N_idp={summ['n_idp']:.1f} | "
           f"变量={summ['nvarys']} | k={summ['kmin']}–{summ['kmax']}, R={summ['rmin']}–{summ['rmax']}, "
           f"kw={summ['kweight']}")
    fig.suptitle(title or summ["sample"])
    fig.text(0.01, 0.005, txt, fontsize=8)
    return _save(fig, out)


def plot_lcf(r, out=None):
    fig, (ax,) = _fig(1)
    c = r["curves"]
    ax.plot(c["x"], c["y"], "k", label="样品")
    ax.plot(c["x"], c["fit"], "r--", label="LCF")
    for k, v in c["comps"].items():
        ax.plot(c["x"], v, lw=0.8, label=f"{k} ({r['weights'][k]:.2f}±{r['weights_err'][k]:.2f})")
    ax.plot(c["x"], c["y"] - c["fit"], "0.5", lw=0.8, label="残差")
    ax.set_xlabel("E − E0 (eV)" if r["space"] != "chik" else "k (Å$^{-1}$)")
    ax.legend()
    fig.text(0.01, 0.005, f"{r['sample']} | {r['space']} {r['xmin']}..{r['xmax']} | "
                          f"R因子={r['rfactor']:.5f} | Σw={r['sum_weights']:.3f}", fontsize=8)
    return _save(fig, out)


def plot_wavelet(k, r, W, out=None, title="", rmax=6):
    fig, (ax,) = _fig(1)
    m = ax.contourf(k, r, W, 40, cmap="jet")
    fig.colorbar(m, ax=ax)
    ax.set_ylim(r[0], rmax)
    ax.set_xlabel("k (Å$^{-1}$)"); ax.set_ylabel("R (Å) — " + NOPHASE)
    ax.set_title(title)
    return _save(fig, out)


def _save(fig, out):
    fig.tight_layout(rect=(0, 0.05, 1, 0.97))
    if out:
        fig.savefig(out, dpi=DPI)
        plt.close(fig)
    return fig


def summary_table(csv):
    df = pd.read_csv(csv)
    return df


if __name__ == "__main__":
    print(summary_table(sys.argv[1]).to_string())
