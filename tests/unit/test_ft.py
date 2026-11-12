"""ft 单元测试。"""
import numpy as np
from larch import Group

from xafsmith.autobk import autobk
from xafsmith.ft import DEFAULT_FT, forward


def _synth(scale=1.0):
    k = np.arange(0, 16.0001, 0.05)
    return Group(k=k, chi=scale * np.sin(2 * k * 2.5) * np.exp(-2 * 0.005 * k ** 2))


def test_matches_larch():
    """直接调用 larch.xafs.xftf，同参数。"""
    from larch.xafs import xftf
    g, ref = _synth(), _synth()
    forward(g, kmin=3, kmax=12, dk=1, window="hanning", kweight=2)
    xftf(ref, kmin=3, kmax=12, dk=1, window="hanning", kweight=2, rmax_out=10.0)
    for a in ("chir_mag", "chir_re", "chir_im", "r"):
        print("ft", a, "max diff", np.max(np.abs(getattr(g, a) - getattr(ref, a))))
        np.testing.assert_allclose(getattr(g, a), getattr(ref, a), rtol=0, atol=1e-12)


def test_peak_position_kweight():
    """合成真值：sin(2k·2.5) → 峰在 2.5 Å（无相移）；kweight 0→2 不变。"""
    pos = []
    for kw in (0, 1, 2):
        g = _synth()
        forward(g, kmin=3, kmax=14, kweight=kw)
        pos.append(float(g.r[np.argmax(g.chir_mag)]))
    print("ft peak positions kw0,1,2:", pos)
    assert all(abs(p - 2.5) < 0.05 for p in pos)


def test_linear():
    """线性：χ×2 → |χ(R)|×2。"""
    a, b = _synth(1.0), _synth(2.0)
    forward(a)
    forward(b)
    np.testing.assert_allclose(b.chir_mag, 2 * a.chir_mag, rtol=1e-12)


def test_ft_params_recorded():
    g = _synth()
    forward(g, kmin=2)
    assert set(g.ft_params) == set(DEFAULT_FT) and g.ft_params["kmin"] == 2


def test_cu_first_peak(cu):
    """回归（非物理真值）：Cu 箔默认 autobk，kmin 3 kmax 14，第一峰 2.24 Å。"""
    autobk(cu)
    forward(cu, kmin=3, kmax=14)
    pk = float(cu.r[np.argmax(cu.chir_mag)])
    print("Cu FT first peak R:", pk)
    assert abs(pk - 2.24) < 0.05
