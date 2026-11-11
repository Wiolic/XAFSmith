"""normalize —— 扫描合并、边前/边后拟合、归一化、E0。

E0 定义（全项目统一）：默认 'deriv' = 平滑后一阶导数最大值（插值到 0.05 eV 网格）。
边前/边后范围以相对 E0 的 eV 给出，所有样品用同一套参数（DEFAULT_NORM）。

用法：
  python -m xafsmith.normalize <文件> [--pre1 -150 --pre2 -30 --norm1 150 --norm2 -1]
"""
import argparse
import copy

import numpy as np
from larch import Group
from scipy.ndimage import gaussian_filter1d

DEFAULT_NORM = dict(pre1=-150.0, pre2=-30.0, norm1=100.0, norm2=None, nnorm=2, nvict=0,
                    e0_method="deriv", e0=None, smooth_ev=1.0)


def find_e0(energy, mu, e_guess=None, window=40.0, smooth_ev=1.0, step=0.05):
    """一阶导数最大值。先插值到细网格，再高斯平滑（σ=smooth_ev eV）。
    e_guess 给出时只在 ±window eV 内搜索。返回 (e0, egrid, dmu)。"""
    energy = np.asarray(energy, float)
    mu = np.asarray(mu, float)
    if e_guess is None:
        d = np.gradient(mu, energy)
        e_guess = energy[np.argmax(gaussian_filter1d(d, 2))]
    lo, hi = e_guess - window, e_guess + window
    sel = (energy >= lo - 10) & (energy <= hi + 10)
    eg = np.arange(max(lo, energy[sel][0]), min(hi, energy[sel][-1]), step)
    mg = np.interp(eg, energy[sel], mu[sel])
    if smooth_ev and smooth_ev > 0:
        mg = gaussian_filter1d(mg, smooth_ev / step)
    dmu = np.gradient(mg, eg)
    i = int(np.argmax(dmu))
    # 抛物线细化
    if 0 < i < len(eg) - 1:
        y0, y1, y2 = dmu[i - 1], dmu[i], dmu[i + 1]
        den = y0 - 2 * y1 + y2
        off = 0.5 * (y0 - y2) / den if den != 0 else 0.0
        e0 = eg[i] + off * step
    else:
        e0 = eg[i]
    return float(e0), eg, dmu


def normalize(g, **kws):
    """对 Group 做边前/边后归一化。参数见 DEFAULT_NORM。结果写回 g：
    e0, edge_step, norm, flat, pre_edge, post_edge, dmude, norm_params"""
    from larch.xafs import pre_edge  # larch.xafs 导入约 2 秒：用到时才导入，加快启动
    p = dict(DEFAULT_NORM)
    p.update({k: v for k, v in kws.items() if v is not None or k in ("norm2", "e0")})
    e = g.energy
    if p.get("e0") is None:
        e_guess = getattr(g, "e_table", None)
        if e_guess is None and getattr(g, "e_nominal", None):
            e_guess = g.e_nominal + getattr(g, "e_shift", 0.0)
        e0, _, _ = find_e0(e, g.mu, e_guess=e_guess, smooth_ev=p["smooth_ev"])
    else:
        e0 = float(p["e0"])
    norm2 = p["norm2"]
    if norm2 is None or norm2 <= 0:
        # 负值或 None：距离数据末端的 eV（默认末端 - 10 eV）
        norm2 = (e[-1] - e0) - (abs(norm2) if norm2 else 10.0)
    pre_edge(g, e0=e0, pre1=p["pre1"], pre2=p["pre2"], norm1=p["norm1"], norm2=norm2,
             nnorm=p["nnorm"], nvict=p["nvict"], make_flat=True)
    g.e0 = e0
    g.dmude = np.gradient(g.mu, e)
    p.update(e0=e0, norm2=norm2)
    g.norm_params = p
    return g


def merge_scans(groups, label="merge", ref_index=0, reject=None, tol_sigma=4.0, min_span_frac=0.9):
    """先逐条检查再平均。
    检查：每条归一化谱与中位谱的 RMS 偏差，超过 tol_sigma×(中位 RMS) 记为异常。
    reject：手动剔除的 label 列表。
    返回 (merged_group, report_list)"""
    reject = set(reject or [])
    # 能量范围明显短的扫描（中断/只测 XANES）不参与合并，否则会截断公共范围
    span = [g.energy[-1] - g.energy[0] for g in groups]
    short = {g.label for g, s in zip(groups, span) if s < min_span_frac * max(span)}
    short_report = [dict(label=g.label, rms_vs_median=np.nan, e0=float(getattr(g, "e0", np.nan)),
                         used=False, reason=f"能量范围不完整（至 {g.energy[-1]:.0f} eV），仅可用于 XANES")
                    for g in groups if g.label in short]
    groups = [g for g in groups if g.label not in short]
    if len(groups) == 1:
        g = groups[0]
        m = copy.deepcopy(g)
        m.label, m.nscans, m.merged_from = label, 1, [g.label]
        return m, [dict(label=g.label, rms_vs_median=0.0, e0=float(getattr(g, "e0", np.nan)),
                        used=True, reason="")] + short_report
    base = groups[min(ref_index, len(groups) - 1)]
    egrid = base.energy
    # 用公共能量范围
    emin = max(g.energy[0] for g in groups)
    emax = min(g.energy[-1] for g in groups)
    egrid = egrid[(egrid >= emin) & (egrid <= emax)]
    mus, norms, labels = [], [], []
    for g in groups:
        if not hasattr(g, "norm"):
            normalize(g)
        mus.append(np.interp(egrid, g.energy, g.mu))
        norms.append(np.interp(egrid, g.energy, g.norm))
        labels.append(g.label)
    norms = np.array(norms)
    med = np.median(norms, axis=0)
    rms = np.sqrt(np.mean((norms - med) ** 2, axis=1))
    med_rms = np.median(rms) if len(rms) > 2 else max(rms.min(), 1e-6)
    report, use = [], []
    for i, lab in enumerate(labels):
        bad_auto = len(groups) > 2 and rms[i] > tol_sigma * med_rms
        e0i = getattr(groups[i], "e0", np.nan)
        reason = ""
        if lab in reject:
            reason = "手动剔除"
        elif bad_auto:
            reason = f"与中位谱 RMS 偏差 {rms[i]:.4f} > {tol_sigma}×{med_rms:.4f}"
        report.append(dict(label=lab, rms_vs_median=float(rms[i]), e0=float(e0i),
                           used=reason == "", reason=reason))
        if reason == "":
            use.append(i)
    if not use:
        use = list(range(len(groups)))
    # 平均归一化 μ（重复扫描间探测器增益可能不同，平均原始 μ 会按增益加权）
    mu_avg = np.mean([norms[i] for i in use], axis=0)
    m = Group(energy=egrid, mu=mu_avg, label=label, mode=base.mode, element=base.element,
              edge=base.edge, e_nominal=base.e_nominal, e_shift=getattr(base, "e_shift", 0.0),
              filename=";".join(labels[i] for i in use), nscans=len(use),
              merged_from=[labels[i] for i in use], timestamp=base.timestamp, source="merge")
    if hasattr(base, "norm_params"):
        p = {k: v for k, v in base.norm_params.items() if k not in ("e0", "norm2")}
        normalize(m, **p)
    return m, report + short_report


def main():
    from .io import read_any
    ap = argparse.ArgumentParser()
    ap.add_argument("files", nargs="+")
    for k in ("pre1", "pre2", "norm1", "norm2"):
        ap.add_argument(f"--{k}", type=float, default=DEFAULT_NORM[k])
    ap.add_argument("--nnorm", type=int, default=2)
    a = ap.parse_args()
    for f in a.files:
        g = read_any(f)
        normalize(g, pre1=a.pre1, pre2=a.pre2, norm1=a.norm1, norm2=a.norm2, nnorm=a.nnorm)
        print(f"{g.label}: E0={g.e0:.2f} eV  edge_step={g.edge_step:.4f}")


if __name__ == "__main__":
    main()
