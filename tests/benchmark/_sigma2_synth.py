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


def variant_feff(dirpath):
    """6.9：由 feffcu01.dat 派生一条几何不同的路径文件（散射原子换成 O、距离 3.603 Å、简并度 6），写进 dirpath。
    振幅/相位仍是 Cu 第一壳层的（合成检验只需几何与质量不同）。返回路径字符串。"""
    src = Path(FEFF).read_text()
    old_hdr, new_hdr = "   2  12.000   2.5478", "   2   6.000   3.6030"
    old_atom = "      .0000   -1.8016    1.8016  1  29 Cu    "
    new_atom = "      .0000     .0000    3.6030  1   8 O     "
    assert old_hdr in src and old_atom in src
    out = Path(dirpath) / "feffv_O_3p603.dat"
    out.write_text(src.replace(old_hdr, new_hdr).replace(old_atom, new_atom))
    return str(out)


def synth_two_path_groups(kind, files, temps=TEMPS, seed=4, noise=NOISE, theta=None, ss0=SS0_TRUE):
    """两条路径共用 θ：χ = Σ 路径(σ² = 模型(T, θ, 该路径) + ss0)。{id: Group}。"""
    from larch import Group
    from larch.xafs import feffpath, path2chi
    from larch.xafs.sigma2_models import sigma2_debye, sigma2_eins
    fn = sigma2_debye if kind == "debye" else sigma2_eins
    th = THETA_TRUE[kind] if theta is None else theta
    p0 = [feffpath(f) for f in files]
    rng = np.random.default_rng(seed)
    groups = {}
    for T in temps:
        chi = 0
        for f, p in zip(files, p0):
            q = feffpath(f, s02=S02_TRUE, sigma2=float(fn(T, th, p)) + ss0, e0=E0_TRUE, deltar=DR_TRUE)
            path2chi(q)
            chi = chi + q.chi
        groups[f"T{T}"] = Group(k=q.k, chi=chi + rng.normal(0, noise, len(q.k)), label=f"T{T}")
    return groups


def two_path_model(kind, files, temps=TEMPS, theta0=300.0):
    params = {"amp": {"value": 0.8}, "e0": 0.0, "dr": 0.0, "thD": {"value": theta0, "min": 50, "max": 2000}, "ss0": 0.0}
    paths = [dict(file=f, label=f"p{i + 1}", s02="amp", e0="e0", deltar="dr", sigma2=sigma2_model(kind))
             for i, f in enumerate(files)]
    rng = dict(RANGE, rmax=4.0)
    return dict(name=f"sig2_2path_{kind}", **rng, params=params,
                datasets=[dict(id=f"T{T}", sample=f"T{T}", temperature=T, paths=[dict(p) for p in paths]) for T in temps])
