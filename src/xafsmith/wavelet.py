"""wavelet —— χ(k) 小波变换，用于区分轻/重散射体与重叠壳层。

  * Morlet：W(k,R) = ∫ χ(k')k'^w · ψ*((k'-k)/s) dk'，  ψ(x)=exp(iηx)exp(-x²/2σ²)，
    s = η/(2R)（Funke 等 2005 的定义）。η、σ 可调。
  * Cauchy：调用 larch.xafs.cauchy_wavelet（Muñoz 等 2003）。
R 轴未相移校正。

用法：
  python -m xafsmith.wavelet <文件> --kweight 2 --eta 10 --sigma 1
"""
import argparse

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


def main():
    from .io import read_any
    from .normalize import normalize
    from .autobk import autobk
    ap = argparse.ArgumentParser()
    ap.add_argument("file")
    ap.add_argument("--kweight", type=float, default=2)
    ap.add_argument("--eta", type=float, default=10)
    ap.add_argument("--sigma", type=float, default=1)
    ap.add_argument("--out", default=None)
    a = ap.parse_args()
    g = read_any(a.file)
    normalize(g)
    autobk(g)
    k, r, W = morlet(g.k, g.chi, kweight=a.kweight, eta=a.eta, sigma=a.sigma)
    i, j = np.unravel_index(W.argmax(), W.shape)
    print(f"{g.label}: |W| 最大值在 k={k[j]:.2f} Å⁻¹, R={r[i]:.2f} Å（未相移校正）")
    if a.out:
        import matplotlib.pyplot as plt
        plt.contourf(k, r, W, 40, cmap="jet")
        plt.xlabel("k (Å$^{-1}$)"); plt.ylabel("R (Å, 未相移校正)")
        plt.savefig(a.out, dpi=150)


if __name__ == "__main__":
    main()
