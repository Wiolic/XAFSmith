"""wavelet —— χ(k) 小波变换，用于区分轻/重散射体与重叠壳层。

  * Morlet：W(k,R) = ∫ χ(k')k'^w · ψ*((k'-k)/s) dk'，  ψ(x)=exp(iηx)exp(-x²/2σ²)，
    s = η/(2R)（Funke 等 2005 的定义）。η、σ 可调。
  * Cauchy：调用 larch.xafs.cauchy_wavelet（Muñoz 等 2003）。
R 轴未相移校正。
"""

import numpy as np


def morlet(k, chi, kweight=2, rmin=0.5, rmax=6.0, nr=221, eta=10.0, sigma=1.0, kgrid=0.05):
    """返回 (k, r, |W|)。k 网格均匀化到 kgrid。"""
    k = np.asarray(k, float)
    kk = np.arange(k[0], k[-1] + kgrid / 2, kgrid)
    f = np.interp(kk, k, chi) * kk ** kweight
    rs = np.linspace(rmin, rmax, nr)
    W = np.zeros((nr, len(kk)))
    dk = kk[:, None] - kk[None, :]   # k - k'
    for i, r in enumerate(rs):
        s = eta / (2.0 * r)
        x = -dk / s                   # (k' - k)/s
        psi = np.exp(1j * eta * x) * np.exp(-x ** 2 / (2 * sigma ** 2))
        W[i] = np.abs((psi.conj() * f[None, :]).sum(axis=1) * kgrid / np.sqrt(s))
    return kk, rs, W


def cauchy(g, kweight=2, rmax_out=6.0, nfft=2048):
    from larch.xafs import cauchy_wavelet
    cauchy_wavelet(g.k, g.chi, group=g, kweight=kweight, rmax_out=rmax_out, nfft=nfft)
    return g.k, g.wcauchy_r, np.abs(g.wcauchy_mag)
