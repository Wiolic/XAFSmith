"""B6 ① sigma2.py：Einstein 与独立闭式、Debye 的 DLL 版与纯 Python 版、单调性、高温极限、θ 反算。"""
from pathlib import Path

import numpy as np
import pytest
from scipy import constants as C

from xafsmith import sigma2 as s2

CU = Path(__file__).resolve().parents[1] / "data" / "benchmark" / "feffcu01.dat"
TEMPS = np.array([10.0, 50.0, 100.0, 200.0, 300.0, 600.0])


def _geom():
    from larch.xafs import feffpath
    return feffpath(str(CU))._feffdat.geom


def _mu_amu():
    return 1.0 / sum(1.0 / max(0.1, g[3]) for g in _geom())


def _eins_closed(T, theta):
    mu = _mu_amu() * C.atomic_mass
    return 1e20 * C.hbar ** 2 / (2 * mu * C.k * theta) / np.tanh(theta / (2 * T))


@pytest.mark.parametrize("theta", [120.0, 250.0, 400.0])
def test_einstein_closed_form(theta):
    got = s2.sigma2_curve(CU, "einstein", theta, TEMPS)
    ref = np.array([_eins_closed(t, theta) for t in TEMPS])
    assert np.max(np.abs(got - ref) / ref) < 1e-12


@pytest.mark.parametrize("theta", [150.0, 315.0])
def test_debye_dll_vs_python(theta):
    from larch.xafs.sigma2_models import sigma2_correldebye_py
    from larch.xafs import feffpath
    fd = feffpath(str(CU))._feffdat
    g = fd.geom
    got = s2.sigma2_curve(CU, "debye", theta, TEMPS)
    ref = np.array([sigma2_correldebye_py(len(g), t, theta, fd.rnorman,
                                          [float(a[4]) for a in g], [float(a[5]) for a in g],
                                          [float(a[6]) for a in g], [float(a[3]) for a in g]) for t in TEMPS])
    assert np.max(np.abs(got - ref) / ref) < 1e-6


def test_debye_dll_vs_python_three_legs():
    """合成 3 腿路径（原子坐标直接给 larch 内部函数，DLL 与 Python 版同输入）。"""
    from larch.xafs.sigma2_models import sigma2_correldebye, sigma2_correldebye_py
    x, y, z = [0.0, 1.9, 3.8], [0.0, 0.3, 0.0], [0.0, 0.0, 0.2]
    m = [192.2, 16.0, 192.2]
    for t in (10.0, 150.0, 300.0):
        a = sigma2_correldebye(3, t, 300.0, 1.5, x, y, z, m)
        b = sigma2_correldebye_py(3, t, 300.0, 1.5, x, y, z, m)
        assert abs(a - b) / abs(b) < 1e-6


@pytest.mark.parametrize("kind", s2.KINDS)
def test_monotonic(kind):
    v = s2.sigma2_curve(CU, kind, 300.0, TEMPS)
    assert np.all(np.diff(v) > 0)                       # 随 T 增
    th = np.array([150.0, 250.0, 400.0, 600.0])
    w = np.array([s2.sigma2_curve(CU, kind, t, [300.0])[0] for t in th])
    assert np.all(np.diff(w) < 0)                       # 随 θ 减


def test_einstein_high_T_slope():
    theta = 200.0
    T = np.array([20 * theta, 40 * theta])
    v = s2.sigma2_curve(CU, "einstein", theta, T)
    slope = (v[1] - v[0]) / (T[1] - T[0])
    mu = _mu_amu() * C.atomic_mass
    omega = C.k * theta / C.hbar                        # θ_E = ħω/k_B
    ref = 1e20 * C.k / (mu * omega ** 2)
    assert abs(slope - ref) / ref < 1e-3


def test_static_added():
    a = s2.sigma2_curve(CU, "debye", 300.0, [100.0])
    b = s2.sigma2_curve(CU, "debye", 300.0, [100.0], static=0.002)
    assert abs(b[0] - a[0] - 0.002) < 1e-15


@pytest.mark.parametrize("kind", s2.KINDS)
def test_theta_roundtrip(kind):
    for theta in (80.0, 250.0, 700.0):
        v = s2.sigma2_curve(CU, kind, theta, [150.0], static=0.001)[0]
        got = s2.theta_from_sigma2(CU, kind, 150.0, v, static=0.001)
        assert abs(got - theta) / theta < 1e-8


def test_theta_none_cases():
    assert s2.theta_from_sigma2(CU, "debye", 300.0, -0.001) is None
    assert s2.theta_from_sigma2(CU, "debye", 300.0, 0.0) is None
    assert s2.theta_from_sigma2(CU, "debye", 300.0, 100.0) is None        # 大于 θ=10 K 的值
    assert s2.theta_from_sigma2(CU, "debye", 300.0, 1e-9) is None         # 小于 θ=5000 K 的值
    with pytest.raises(ValueError):
        s2.sigma2_curve(CU, "foo", 300, [1])


# ------------------------------------------------------------------ 6.9 按路径几何展开
def _variant(tmp_path):
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "benchmark"))
    from _sigma2_synth import variant_feff
    return variant_feff(tmp_path)


@pytest.mark.parametrize("kind", ["debye", "eins"])
def test_expand_for_path_bitwise_equals_larch(kind, tmp_path):
    """展开式经 larch 路径参数求值 == larch 直接调用 sigma2_<kind>(T, θ, path)，逐位相同。"""
    from larch.fitting import param_group
    from larch.xafs import feffpath
    from larch.xafs import sigma2_models as sm
    fn = sm.sigma2_debye if kind == "debye" else sm.sigma2_eins
    for f in (str(CU), _variant(tmp_path)):
        p0 = feffpath(f)
        for T in (5.0, 77.0, 300.0, 900.0):
            for th in (90.0, 250.0, 700.0):
                q = feffpath(f, label="q")
                q.sigma2 = s2.expand_for_path(f"sigma2_{kind}({T!r}, {th!r})", q._feffdat)
                assert "sigma2_debye" not in q.sigma2 and "sigma2_eins" not in q.sigma2
                q.create_path_params(params=param_group())
                assert q.path_paramvals()["sigma2"] == fn(T, th, p0), (f, T, th)


def test_expand_for_path_nested_and_noop():
    from larch.xafs import feffpath
    fd = feffpath(str(CU))._feffdat
    assert s2.expand_for_path("ss1 + 0.001", fd) == "ss1 + 0.001"
    assert s2.expand_for_path(0.003, fd) == 0.003
    out = s2.expand_for_path("sigma2_debye(300.0, th*(1 + x)) + sigma2_eins(max(t, 1), th) + ss0", fd)
    import ast
    ast.parse(out, mode="eval")
    assert "sigma2_correldebye(2, max(300.0, 1e-05), max(th * (1 + x), 1e-05)" in out
    assert "EINS_FACTOR" in out and "max(max(t, 1), 1e-05)" in out and out.endswith("+ ss0")
