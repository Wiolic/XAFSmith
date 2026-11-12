"""Fe K 边合成混合物（test_fe_lcf / test_fe_valence 与 tests/unit/test_fit_lcf 共用）。

数据：FeO（feo_rt1.xdi，Fe²⁺）、Fe2O3（fe2o3_rt1.xmu，Fe³⁺）同一线站同一次课程（APS 20BM 2001），能量标尺可比；
Fe3C（13-BM-D）与 fe.060（NSLS）来自别的线站，绝对能量不可与前两者比较——价态标定只用 FeO / Fe2O3，
Fe3C 只在 LCF 里当“形状”端点（LCF 在同一合成里自洽，与线站无关）。

合成方法：
  1. 三个标样用默认参数 normalize（不做能量校准，合成只在各自能量轴上进行）；
  2. 公共网格 = FeO 的能量点中落在 Fe3C 能量范围内的部分；
  3. μ_mix = Σ wᵢ·interp(flatᵢ) + 高斯白噪声 σ，再用同一套默认参数重新 normalize（走真实流程）。
"""
from pathlib import Path

import numpy as np
from larch import Group

PUBLIC = Path(__file__).resolve().parents[1] / "data" / "demo_project" / "data" / "raw" / "public"
FILES = {"FeO": "feo_rt1.xdi", "Fe2O3": "fe2o3_rt1.xmu", "Fe3C": "fe3c_rt.xdi"}


def load_standards():
    from xafsmith.normalize import normalize
    from xafsmith.readers import read_scan
    out = {}
    for n, f in FILES.items():
        g = read_scan(PUBLIC / f)
        g.label = n                      # LCF 权重按 label 取键
        out[n] = normalize(g)
    return out


def mix(weights, sigma=0.0, seed=0, std=None, label="mix"):
    """weights: {标样名: 权重}；返回重新归一化的合成 Group。"""
    from xafsmith.normalize import normalize
    std = std or load_standards()
    feo, fe3c = std["FeO"], std["Fe3C"]
    sel = (feo.energy >= fe3c.energy[0]) & (feo.energy <= fe3c.energy[-1])
    e = feo.energy[sel]
    mu = sum(w * np.interp(e, std[n].energy, std[n].flat) for n, w in weights.items())
    if sigma:
        mu = mu + np.random.default_rng(seed).normal(0.0, sigma, len(e))
    g = Group(energy=e.copy(), mu=mu, label=label, element="Fe", edge="K", mode="trans")
    return normalize(g)
