"""qc —— 数据质量检查，输出 qc_report.csv。

检查项：
  * 能量网格：点数、范围、单调性、步长
  * I0：最小计数、突降（束流掉落/填充）
  * 毛刺：μ 相对 5 点滑动中值的残差，超过 6×MAD 的点
  * 边跳：透射模式下 ln(I0/I1) 的跳变 = Δμt（与电离室增益无关，可信）；
          总 μt 因 I0/I1 增益/气体未知无法从数据得到，需样品设计计算（mut_planner）
  * 荧光：If/I0 的跳变（任意单位）；若同时有 I1，则 ln(I0/I1) 跳变给出样品（+电解池）Δμt，
          Δμt 较大说明自吸收风险高
  * 噪声：χ(k) 在 R=15–25 Å 的平均幅度估计 ε_k（larch estimate_noise）
  * 谐波：单条谱无法评估，标为“不可评估”

用法：
  python -m xafsmith.qc <文件> [<文件> ...] --out output/qc/qc_report.csv
"""
from xafsmith import logs
import argparse

import numpy as np
import pandas as pd
from scipy.ndimage import median_filter, maximum_filter1d

from .normalize import normalize


def glitches(energy, mu, e0=None, nsig=8.0):
    """毛刺：点相对左右邻点均值的偏离，超过 nsig×(边后区域稳健噪声 σ)。mu 用归一化谱。"""
    r = mu[1:-1] - 0.5 * (mu[:-2] + mu[2:])
    e = energy[1:-1]
    sel = e > (e0 + 30) if e0 else np.ones_like(e, bool)
    sig = np.median(np.abs(r[sel] - np.median(r[sel]))) * 1.4826 + 1e-12
    bad = np.where(sel & (np.abs(r) > nsig * sig))[0]
    return [float(e[i]) for i in bad]


def deglitch(g, ranges):
    """删去能量（已校准）落在 ranges=[[lo, hi], ...] 内的数据点（只改处理副本）。
    返回删去的点数；记录在 g.deglitched。"""
    keep = np.ones(len(g.energy), bool)
    for lo, hi in ranges:
        keep &= ~((g.energy >= lo) & (g.energy <= hi))
    n = len(g.energy)
    for a in ("energy", "energy_raw", "mu", "i0", "i1", "ifl"):
        v = getattr(g, a, None)
        if isinstance(v, np.ndarray) and len(v) == n:
            setattr(g, a, v[keep])
    g.deglitched = [list(r) for r in ranges]
    return int((~keep).sum())


def i0_drops(i0, frac=0.8):
    if i0 is None:
        return []
    ref = median_filter(i0, size=7, mode="nearest")
    return list(np.where(i0 < frac * ref)[0])


def _step(energy, y, element=None, edge=None, e_nominal=None):
    from larch import Group
    t = Group(energy=energy, mu=y, element=element, edge=edge, e_nominal=e_nominal)
    try:
        normalize(t)
        return float(t.edge_step), float(t.e0)
    except Exception:
        logs.log.warning("qc._step 出错（已忽略或已提示）", exc_info=True)
        return np.nan, np.nan


def check(g, kmin=2.0):
    from larch.xafs import estimate_noise
    from .autobk import autobk
    e = g.energy
    de = np.diff(e)
    row = dict(label=g.label, file=g.filename, element=g.element, edge=g.edge, mode=g.mode,
               time=g.timestamp, npts=len(e), emin=e[0], emax=e[-1],
               monotonic=bool(np.all(de > 0)), step_min=float(de.min()), step_max=float(de.max()))
    if getattr(g, "i0", None) is not None:
        row["i0_min"] = float(np.min(g.i0))
        drops = i0_drops(g.i0)
        row["i0_drops"] = len(drops)
    if not hasattr(g, "norm"):
        normalize(g)
    row["e0"] = g.e0
    row["edge_step_mu"] = float(g.edge_step)
    if g.mode == "trans":
        row["delta_mut"] = float(g.edge_step)
        row["total_mut"] = "未知(增益未知)"
    elif g.mode == "fluo" and getattr(g, "i1", None) is not None:
        st, _ = _step(e, np.log(np.abs(g.i0) / np.abs(g.i1)), g.element, g.edge, g.e0)
        row["delta_mut_from_I1"] = st
        row["self_abs_risk"] = ("高(Δμt≥0.1)" if st >= 0.1 else
                                "低-中(Δμt<0.1，仍需看总 μt)" if np.isfinite(st) and st > 0.005
                                else "无法评估(I1 无可见边跳)")
    gl = glitches(e, g.flat, g.e0)
    row["n_glitches"] = len(gl)
    row["glitch_E"] = ";".join(f"{x:.1f}" for x in gl[:10])
    try:
        autobk(g)
        kmax = float(g.k[-1])
        estimate_noise(g.k, g.chi, group=g, kmin=kmin, kmax=kmax)
        row["kmax_data"] = kmax
        row["epsilon_k"] = float(g.epsilon_k)
        row["epsilon_r"] = float(g.epsilon_r)
        # 信噪比：k^2χ 包络与噪声之比 <3 的位置
        kw = 2
        amp = np.abs(g.chi * g.k ** kw)
        dkk = g.k[1] - g.k[0]
        env = maximum_filter1d(amp, size=max(3, int(2.0 / dkk)), mode="nearest")  # 2 Å⁻¹ 窗口包络
        noise = g.epsilon_k * g.k ** kw
        ok = np.where((g.k > 3) & (env > 3 * noise))[0]
        row["k_snr3"] = float(g.k[ok[-1]]) if len(ok) else np.nan   # 包络最后一次高于 3×噪声的 k
    except Exception as ex:
        logs.log.warning("qc.check 出错（已忽略或已提示）", exc_info=True)
        row["autobk_error"] = str(ex)
    row["harmonics"] = "不可评估"
    return row


def run(groups, out=None):
    rows = [check(g) for g in groups]
    df = pd.DataFrame(rows)
    if out:
        df.to_csv(out, index=False, encoding="utf-8-sig")
    return df


def main():
    from .io import read_any
    ap = argparse.ArgumentParser()
    ap.add_argument("files", nargs="+")
    ap.add_argument("--out", default="results/qc_report.csv")
    a = ap.parse_args()
    df = run([read_any(f) for f in a.files], a.out)
    print(df.to_string())


if __name__ == "__main__":
    main()
