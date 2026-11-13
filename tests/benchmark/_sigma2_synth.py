"""B6 合成多温度数据（Cu 第一壳层 FEFF 路径，tests/data/benchmark/feffcu01.dat）：σ² = 模型(T, θ_true) + 静态项 + 噪声（固定种子）。"""
from pathlib import Path

import numpy as np

FEFF = str(Path(__file__).resolve().parents[1] / "data" / "benchmark" / "feffcu01.dat")
TEMPS = (10, 100, 200, 300)
THETA_TRUE = {"debye": 250.0, "einstein": 220.0}
SS0_TRUE = 0.001
NOISE = 2e-4
S02_TRUE, E0_TRUE, DR_TRUE = 0.9, 2.0, 0.01
RANGE = dict(kmin=3, kmax=14, dk=1, window="hanning", kweight=2, rmin=1.8, rmax=3.0, fitspace="r")


def synth_groups(kind, temps=TEMPS, seed=1, noise=NOISE, theta=None, ss0=SS0_TRUE):
    """{id: Group}，id = f"T{T}"。"""
    from larch import Group
    from larch.xafs import feffpath, path2chi
    from larch.xafs.sigma2_models import sigma2_debye, sigma2_eins
    fn = sigma2_debye if kind == "debye" else sigma2_eins
    th = THETA_TRUE[kind] if theta is None else theta
    p0 = feffpath(FEFF)
    rng = np.random.default_rng(seed)
    groups = {}
    for T in temps:
        q = feffpath(FEFF, s02=S02_TRUE, sigma2=float(fn(T, th, p0)) + ss0, e0=E0_TRUE, deltar=DR_TRUE)
        path2chi(q)
        groups[f"T{T}"] = Group(k=q.k, chi=q.chi + rng.normal(0, noise, len(q.k)), label=f"T{T}")
    return groups


def sigma2_model(kind, th="thD", static="ss0"):
    return f"sigma2_{'debye' if kind == 'debye' else 'eins'}(tempK, {th})" + (f" + {static}" if static else "")


def joint_model(kind, temps=TEMPS, static=True, theta0=300.0):
    """多数据集联合模型：tempK 写进路径，每个数据集只改 temperature。"""
    params = {"amp": {"value": 0.8}, "e0": 0.0, "dr": 0.0, "thD": {"value": theta0, "min": 50, "max": 2000}}
    if static:
        params["ss0"] = 0.0
    path = dict(file=FEFF, label="Cu", s02="amp", e0="e0", deltar="dr",
                sigma2=sigma2_model(kind, static="ss0" if static else None))
    return dict(name=f"sig2_{kind}", **RANGE, params=params,
                datasets=[dict(id=f"T{T}", sample=f"T{T}", temperature=T, paths=[dict(path)]) for T in temps])
