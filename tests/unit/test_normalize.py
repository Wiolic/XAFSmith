"""normalize 单元测试。参考值来源见各测试 docstring。"""
from pathlib import Path

import numpy as np
import pytest
from larch import Group

from xafsmith.normalize import find_e0, merge_scans, normalize

E0 = 8979.3

DEMO_RAW = Path(__file__).resolve().parents[1] / "data" / "demo_project" / "data" / "raw" / "public"


def _edge(grid):
    e = np.arange(8800.0, 9300.0, grid)
    mu = 0.3 - 1e-5 * (e - 8800) + np.arctan((e - E0) / 1.5) / np.pi + 0.5
    return e, mu


def test_find_e0_fine_grid():
    """合成真值：arctan 边，E0=8979.3，0.5 eV 网格。"""
    e, mu = _edge(0.5)
    v = find_e0(e, mu)[0]
    print("find_e0 0.5eV err", v - E0)
    assert abs(v - E0) < 0.01


def test_find_e0_coarse_grid():
    """合成真值：2 eV 网格，记录粗网格的已知偏差。"""
    e, mu = _edge(2.0)
    v = find_e0(e, mu)[0]
    print("find_e0 2eV err", v - E0)
    assert abs(v - E0) < 0.25


def test_find_e0_guess_offset():
    """合成真值：e_guess 偏 15 eV 仍找到同一 E0。"""
    e, mu = _edge(0.5)
    a = find_e0(e, mu)[0]
    b = find_e0(e, mu, e_guess=E0 + 15)[0]
    print("find_e0 guess+15 diff", b - a)
    assert abs(b - a) < 0.01


def test_normalize_matches_larch(cu):
    """直接调用 larch.xafs.pre_edge，参数取自 g.norm_params。"""
    from larch.xafs import pre_edge
    normalize(cu)
    p = cu.norm_params
    ref = Group(energy=cu.energy.copy(), mu=cu.mu.copy())
    pre_edge(ref, e0=p["e0"], pre1=p["pre1"], pre2=p["pre2"], norm1=p["norm1"], norm2=p["norm2"],
             nnorm=p["nnorm"], nvict=p["nvict"], make_flat=True)
    np.testing.assert_allclose(cu.norm, ref.norm, rtol=0, atol=1e-12)
    np.testing.assert_allclose(cu.flat, ref.flat, rtol=0, atol=1e-12)
    np.testing.assert_allclose(cu.edge_step, ref.edge_step, rtol=0, atol=1e-12)


def test_normalize_flat_mean(cu):
    """物理不变量：flat 在 E0+150 eV 之后的均值 = 1。"""
    normalize(cu)
    m = cu.flat[cu.energy > cu.e0 + 150].mean()
    print("Cu flat mean beyond E0+150:", m)
    assert abs(m - 1) < 0.02


def test_normalize_scale_invariance(cu):
    """物理不变量：μ → 3.7μ + 0.5，norm 不变、edge_step 变 3.7 倍。"""
    from xafsmith.readers import read_scan
    normalize(cu)
    g2 = read_scan(DEMO_RAW / "cu_metal_rt.xdi")
    g2.mu = 3.7 * g2.mu + 0.5
    normalize(g2, e0=cu.e0)
    d = np.max(np.abs(g2.norm - cu.norm))
    r = g2.edge_step / cu.edge_step
    print("scale invariance max|dnorm|", d, "step ratio-3.7", r - 3.7)
    np.testing.assert_allclose(g2.norm, cu.norm, rtol=0, atol=1e-9)
    np.testing.assert_allclose(g2.edge_step, 3.7 * cu.edge_step, rtol=1e-9)


@pytest.mark.parametrize("n2,expect", [(None, 10.0), (-30.0, 30.0)])
def test_norm2_default_and_negative(cu, n2, expect):
    """norm2=None / 负值 = 末端 − E0 − 10 / 末端 − E0 − |norm2|（来自 normalize 文档）。"""
    normalize(cu, norm2=n2)
    want = (cu.energy[-1] - cu.e0) - expect
    assert cu.norm_params["norm2"] == pytest.approx(want, abs=1e-9)


def _copies(cu, n=5):
    rng = np.random.default_rng(1)
    gs = []
    for i in range(n):
        g = Group(energy=cu.energy.copy(), mu=cu.mu + rng.normal(0, 0.002, len(cu.mu)),
                  label=f"s{i}", mode=cu.mode, element=cu.element, edge=cu.edge,
                  e_nominal=cu.e_nominal, timestamp=cu.timestamp)
        gs.append(g)
    return gs


def test_merge_scans_rejects_outlier(cu):
    """合成：5 份 Cu 箔 + σ=0.002 噪声，第 5 份加 0.05·sin(E/20)。"""
    gs = _copies(cu)
    gs[4].mu = gs[4].mu + 0.05 * np.sin(gs[4].energy / 20)
    for g in gs:
        normalize(g)
    m, rep = merge_scans(gs)
    print("merge rms:", [(r["label"], round(r["rms_vs_median"], 4), r["used"]) for r in rep])
    used = {r["label"]: r["used"] for r in rep}
    assert used["s4"] is False and m.nscans == 4


def test_merge_scans_manual_reject(cu):
    gs = _copies(cu)
    for g in gs:
        normalize(g)
    m, rep = merge_scans(gs, reject=["s0"])
    assert {r["label"]: r["used"] for r in rep}["s0"] is False
    assert m.nscans == 4


def test_merge_scans_short_scan(cu):
    gs = _copies(cu)
    n = int(len(cu.energy) * 0.8)
    gs[2].energy, gs[2].mu = gs[2].energy[:n], gs[2].mu[:n]
    for g in gs:
        normalize(g)
    m, rep = merge_scans(gs)
    r2 = [r for r in rep if r["label"] == "s2"][0]
    assert r2["used"] is False and "能量范围不完整" in r2["reason"]
    assert m.nscans == 4


def test_merge_scans_single(cu):
    gs = _copies(cu, 1)
    normalize(gs[0])
    m, rep = merge_scans(gs)
    assert m.nscans == 1 and len(rep) == 1
