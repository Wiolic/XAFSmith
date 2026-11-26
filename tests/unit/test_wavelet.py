"""E18：wavelet.py（Morlet 与 Cauchy 小波）的单元测试。纯正弦 χ(k) = sin(2kR0)：|W| 的极大值应落在 R0 附近。"""
import numpy as np
import pytest
from larch import Group

from xafsmith import wavelet

R0 = 2.0
K = np.arange(2.0, 14.0 + 1e-9, 0.05)
CHI = np.sin(2 * K * R0)


def test_morlet_shapes_and_nonnegative():
    kk, rs, W = wavelet.morlet(K, CHI, kweight=2, rmin=1.0, rmax=3.5, nr=101)
    assert rs.shape == (101,) and rs[0] == pytest.approx(1.0) and rs[-1] == pytest.approx(3.5)
    assert kk[0] == pytest.approx(K[0]) and np.all(np.diff(kk) > 0) and abs(kk[1] - kk[0] - 0.05) < 1e-9
    assert W.shape == (len(rs), len(kk))
    assert np.isfinite(W).all() and (W >= 0).all()


def test_morlet_maximum_at_sine_frequency():
    kk, rs, W = wavelet.morlet(K, CHI, kweight=2, rmin=1.0, rmax=3.5, nr=101)
    i, j = np.unravel_index(W.argmax(), W.shape)
    assert abs(rs[i] - R0) <= 0.15
    assert kk[0] < kk[j] < kk[-1]


@pytest.mark.parametrize("r0", [1.5, 2.5])
def test_morlet_maximum_follows_r0(r0):
    kk, rs, W = wavelet.morlet(K, np.sin(2 * K * r0), kweight=2, rmin=1.0, rmax=3.5, nr=101)
    assert abs(rs[np.unravel_index(W.argmax(), W.shape)[0]] - r0) <= 0.15


def test_morlet_kweight_scales_amplitude():
    _, _, w1 = wavelet.morlet(K, CHI, kweight=1, rmin=1.0, rmax=3.5, nr=51)
    _, _, w2 = wavelet.morlet(K, CHI, kweight=2, rmin=1.0, rmax=3.5, nr=51)
    assert w2.max() > w1.max()          # k > 1 的区间里 k² 权重 > k 权重


def test_cauchy_shapes_and_peak():
    g = Group(k=K, chi=CHI)
    k, r, mag = wavelet.cauchy(g, kweight=2, rmax_out=6.0, nfft=2048)
    assert mag.shape == (len(r), len(k)) and len(k) == len(K)
    assert np.isfinite(mag).all() and (mag >= 0).all()
    assert r.max() <= 6.0 + 1e-9
    i, _ = np.unravel_index(mag.argmax(), mag.shape)
    assert abs(r[i] - R0) <= 0.15       # 快照（E18 时代码的输出：R = 2.0 Å）
