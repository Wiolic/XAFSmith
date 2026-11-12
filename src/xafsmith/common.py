"""公共工具：参数记录、k/E 换算、边能量查表。项目路径见 paths.py。"""
import json
import datetime
from pathlib import Path

import numpy as np


def _etok():
    # 2m_e/ħ²，单位 eV⁻¹ Å⁻²；与 larch.xafs.xafsutils.ETOK 同一公式、同一 CODATA（scipy.constants），
    # 使这里换算的 k 与 larch autobk 的 k 网格完全一致。文档里的 0.2625 只是近似写法。
    from scipy import constants as c
    return 1.0 / (1.e20 * c.hbar ** 2 / (2 * c.m_e * c.e))


ETOK = _etok()  # ≈ 0.262468424 (k = sqrt(ETOK*(E-E0)))


def e2k(de):
    """E - E0 (eV) -> k (Å^-1)"""
    de = np.asarray(de, dtype=float)
    return np.sqrt(np.clip(de, 0, None) * ETOK)


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


def append_csv(df, csv):
    """把 df 追加到 csv。列不同时按列名合并后整体重写（mode='a' 会沿用旧表头，导致新列错位）。"""
    import pandas as pd
    csv = Path(csv)
    csv.parent.mkdir(parents=True, exist_ok=True)
    if csv.exists():
        old = pd.read_csv(csv, encoding="utf-8-sig", dtype=str, keep_default_na=False)
        if list(old.columns) != list(df.columns):
            pd.concat([old, df.astype(str)], ignore_index=True).to_csv(
                csv, index=False, encoding="utf-8-sig")
            return
    df.to_csv(csv, mode="a", header=not csv.exists(), index=False, encoding="utf-8-sig")
