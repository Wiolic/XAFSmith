"""ft —— k 空间加窗、傅里叶变换与反变换（larch xftf/xftr）。

所有 R 空间图须标注“未相移校正”。

用法：
  python -m xafsmith.ft <文件> --kmin 3 --kmax 12 --kweight 2 --dk 1 --window hanning
"""
import argparse


DEFAULT_FT = dict(kmin=3.0, kmax=12.0, dk=1.0, window="hanning", kweight=2, rmax_out=10.0)
DEFAULT_BFT = dict(rmin=1.0, rmax=3.0, dr=0.0, window="hanning")


def forward(g, **kws):
    p = dict(DEFAULT_FT)
    p.update({k: v for k, v in kws.items() if v is not None})
    from larch.xafs import xftf  # larch.xafs 导入约 2 秒：用到时才导入，加快启动
    xftf(g, kmin=p["kmin"], kmax=p["kmax"], dk=p["dk"], window=p["window"],
         kweight=p["kweight"], rmax_out=p["rmax_out"])
    g.ft_params = p
    return g


def backward(g, **kws):
    p = dict(DEFAULT_BFT)
    p.update({k: v for k, v in kws.items() if v is not None})
    from larch.xafs import xftr
    xftr(g, rmin=p["rmin"], rmax=p["rmax"], dr=p["dr"], window=p["window"])
    g.bft_params = p
    return g


def main():
    from .io import read_any
    from .normalize import normalize
    from .autobk import autobk
    ap = argparse.ArgumentParser()
    ap.add_argument("files", nargs="+")
    for k in ("kmin", "kmax", "dk", "kweight"):
        ap.add_argument(f"--{k}", type=float, default=DEFAULT_FT[k])
    ap.add_argument("--window", default="hanning")
    a = ap.parse_args()
    for f in a.files:
        g = read_any(f)
        normalize(g)
        autobk(g)
        forward(g, kmin=a.kmin, kmax=a.kmax, dk=a.dk, kweight=a.kweight, window=a.window)
        i = g.chir_mag.argmax()
        print(f"{g.label}: |χ(R)| 最大峰 R={g.r[i]:.2f} Å（未相移校正）")


if __name__ == "__main__":
    main()
