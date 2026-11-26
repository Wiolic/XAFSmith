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


# ---- E17：页面里的小波计算搬进 wavelet.compute / maxima；下面照抄 E17 前页面里的旧实现作逐位对照
def _old_compute(k, chi, kmax, kind, kw, rmax, eta, sig):
    m = k <= kmax
    if kind == "Morlet":
        kk, rr, Wt = wavelet.morlet(k[m], chi[m], kweight=kw, rmax=rmax, eta=eta, sigma=sig)
    else:
        kk, rr, Wt = wavelet.cauchy(Group(k=k[m], chi=chi[m]), kweight=kw, rmax_out=rmax)
        mm = (rr <= rmax) & (rr > 0)
        rr, Wt = rr[mm], Wt[mm]
    return np.asarray(kk), np.asarray(rr), np.asarray(Wt)


def _old_maxima(kk, rr, Wt, wins):
    rows = []
    for lo, hi in wins:
        sel = (rr >= lo) & (rr <= hi)
        if not sel.any():
            continue
        sub = Wt[sel]
        i, j = np.unravel_index(np.argmax(sub), sub.shape)
        rows.append((f"{lo:g}–{hi:g}", round(float(kk[j]), 2), round(float(rr[sel][i]), 2), float(sub[i, j])))
    return rows


@pytest.fixture
def cu_chi(cu):
    from xafsmith.autobk import autobk
    from xafsmith.normalize import normalize
    normalize(cu)
    autobk(cu)
    return np.array(cu.k, copy=True), np.array(cu.chi, copy=True)


@pytest.mark.parametrize("kind", ["Morlet", "Cauchy"])
@pytest.mark.parametrize("kw", [1, 3])
def test_compute_equals_old_page_code(cu_chi, kind, kw):
    k, chi = cu_chi
    new = wavelet.compute(k, chi, kind=kind, kweight=kw, rmax=5.0, eta=10.0, sigma=1.0, kmax=12.0)
    old = _old_compute(k, chi, 12.0, kind, kw, 5.0, 10.0, 1.0)
    for a, b in zip(new, old):
        assert a.shape == b.shape and np.array_equal(a, b)
    assert new[0].max() <= 12.0 + 0.05
    if kind == "Cauchy":
        assert new[1].min() > 0 and new[1].max() <= 5.0


def test_maxima_equals_old_page_code(cu_chi):
    k, chi = cu_chi
    kk, rr, Wt = wavelet.compute(k, chi, kind="Morlet", kweight=2, rmax=5.0, eta=10.0, sigma=1.0, kmax=12.0)
    wins = [(1.0, 2.0), (2.0, 3.6), (9.0, 9.5)]          # 最后一个区间在 rmax 之外：跳过
    rows = wavelet.maxima(kk, rr, Wt, wins)
    assert len(rows) == 2 and set(rows[0]) == {"window_lo", "window_hi", "k_max", "r_max", "w_max"}
    mapped = [(f"{m['window_lo']:g}–{m['window_hi']:g}", round(m["k_max"], 2), round(m["r_max"], 2), m["w_max"]) for m in rows]
    assert mapped == _old_maxima(kk, rr, Wt, wins)
    assert wavelet.maxima(kk, rr, Wt, []) == []


def test_maxima_sine_window_position():
    kk, rr, Wt = wavelet.compute(K, CHI, kind="Morlet", kweight=2, rmax=3.5, eta=10.0, sigma=1.0, kmax=99.0)
    (row,) = wavelet.maxima(kk, rr, Wt, [(1.0, 3.0)])
    assert abs(row["r_max"] - R0) <= 0.15 and row["w_max"] == Wt.max()
