"""calib —— 用参比箔（或参比标样）做能量校准。

方法：参比谱一阶导数最大值 E0_meas（normalize.find_e0），与 xraydb 表值
E0_table 比较，ΔE = E0_table − E0_meas，同一吸收边、同一批测量的所有谱加同一 ΔE。
注意：若参比未与样品同时测量（无第三电离室），ΔE 只能代表测参比时的单色器状态，
能量漂移无法逐谱校正——在 calib.json 中记录参比与样品的测量时间差。

用法：
  python -m xafstool.calib <参比文件> [--element Ir --edge L3 --etable 11215.0]
"""
import argparse
import datetime
import json
from pathlib import Path

import numpy as np

from .common import edge_energy
from .normalize import find_e0


def calibrate_reference(ref, e_table=None, smooth_ev=1.0, window=40.0):
    """返回 dict(element, edge, e_table, e0_meas, delta_e, source)"""
    if e_table is None:
        e_table = edge_energy(ref.element, ref.edge)
        src = "xraydb (Elam) 表值"
    else:
        src = "用户给定"
    guess = ref.e_nominal if getattr(ref, "e_nominal", None) else e_table
    e0, eg, dmu = find_e0(ref.energy, ref.mu, e_guess=guess, smooth_ev=smooth_ev, window=window)
    ref.calib_curve = (eg, dmu)
    return dict(reference=ref.label, element=ref.element, edge=ref.edge, e_table=e_table,
                e0_meas=e0, delta_e=e_table - e0, table_source=src,
                ref_time=getattr(ref, "timestamp", ""), smooth_ev=smooth_ev)


def apply_shift(groups, delta_e):
    """给 group 的能量加 ΔE（只改处理副本，原始文件不动）。"""
    for g in groups:
        if not hasattr(g, "energy_raw"):
            g.energy_raw = g.energy.copy()
        g.energy = g.energy_raw + delta_e
        g.e_shift = delta_e
    return groups


def _parse_time(s):
    for fmt in ("%Y/%m/%d %H:%M:%S",):
        try:
            return datetime.datetime.strptime(s.strip(), fmt)
        except Exception:
            pass
    return None


def time_gap_hours(t1, t2):
    a, b = _parse_time(t1 or ""), _parse_time(t2 or "")
    if a is None or b is None:
        return None
    return abs((a - b).total_seconds()) / 3600.0


def save_calib(results, path):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")


def main():
    from .io import read_any
    ap = argparse.ArgumentParser()
    ap.add_argument("ref")
    ap.add_argument("--etable", type=float, default=None)
    a = ap.parse_args()
    r = read_any(a.ref)
    res = calibrate_reference(r, e_table=a.etable)
    print(json.dumps(res, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
