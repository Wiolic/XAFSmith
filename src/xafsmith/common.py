"""公共工具：参数记录、k/E 换算、边能量查表。项目路径见 paths.py。"""
import json
import datetime
from pathlib import Path

import numpy as np


ETOK = 0.2624682843  # 2m/hbar^2, 单位 eV^-1 Å^-2 (k = sqrt(ETOK*(E-E0)))


def e2k(de):
    """E - E0 (eV) -> k (Å^-1)"""
    de = np.asarray(de, dtype=float)
    return np.sqrt(np.clip(de, 0, None) * ETOK)


def k2e(k):
    """k (Å^-1) -> E - E0 (eV)"""
    return np.asarray(k, dtype=float) ** 2 / ETOK


def n_idp(kmin, kmax, rmin, rmax):
    """独立点数 N_idp = 2ΔkΔR/π"""
    return 2.0 * (kmax - kmin) * (rmax - rmin) / np.pi


def r_resolution(kmin, kmax):
    """ΔR = π/(2Δk)"""
    return np.pi / (2.0 * (kmax - kmin))


def edge_energy(element, edge):
    """表值边能量（xraydb，Elam 表）。"""
    import xraydb
    return float(xraydb.xray_edge(element, edge).energy)


def guess_edge(element, energy):
    """由元素和名义能量猜测吸收边（K/L1/L2/L3/M...）。"""
    import xraydb
    best, dmin = None, 1e9
    for name, e in xraydb.xray_edges(element).items():
        d = abs(e.energy - energy)
        if d < dmin:
            best, dmin = name, d
    return best


def write_params(path, params, tool=None):
    """把运行参数写入 *.params.json（第 2 节规则）。"""
    path = Path(path)
    if path.suffix != ".json":
        path = path.with_name(path.stem + ".params.json")
    out = {"tool": tool, "time": datetime.datetime.now().isoformat(timespec="seconds"),
           "params": params}
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(out, ensure_ascii=False, indent=2, default=_json_default),
                    encoding="utf-8")
    return path


def _json_default(o):
    if isinstance(o, (np.floating, np.integer)):
        return o.item()
    if isinstance(o, np.ndarray):
        return o.tolist()
    if isinstance(o, Path):
        return str(o)
    return str(o)


def ensure_dir(p):
    p = Path(p)
    p.mkdir(parents=True, exist_ok=True)
    return p
