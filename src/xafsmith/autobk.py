"""autobk —— 背景扣除（larch autobk），得到 χ(k)。

参数（样品间保持一致）：rbkg、kweight、kmin、kmax、clamp_lo/hi。

用法：
  python -m xafsmith.autobk <文件> [--rbkg 1.0 --kweight 2]
"""
import argparse


DEFAULT_BKG = dict(rbkg=1.0, kweight=2, kmin=0.0, kmax=None, dk=0.1, win="hanning",
                   nclamp=3, clamp_lo=0, clamp_hi=1)


def autobk(g, **kws):
    p = dict(DEFAULT_BKG)
    p.update({k: v for k, v in kws.items() if v is not None})
    if not hasattr(g, "e0"):
        from .normalize import normalize
        normalize(g)
    npar = getattr(g, "norm_params", {})
    from larch.xafs import autobk as _autobk  # larch.xafs 导入约 2 秒：用到时才导入，加快启动
    _autobk(g, e0=g.e0, edge_step=g.edge_step, rbkg=p["rbkg"], kweight=p["kweight"],
            kmin=p["kmin"], kmax=p["kmax"], dk=p["dk"], win=p["win"], nclamp=p["nclamp"],
            clamp_lo=p["clamp_lo"], clamp_hi=p["clamp_hi"],
            pre_edge_kws=dict(pre1=npar.get("pre1"), pre2=npar.get("pre2"),
                              norm1=npar.get("norm1"), norm2=npar.get("norm2"),
                              nnorm=npar.get("nnorm", 2)))
    g.bkg_params = p
    return g


def main():
    from .io import read_any
    from .normalize import normalize
    ap = argparse.ArgumentParser()
    ap.add_argument("files", nargs="+")
    ap.add_argument("--rbkg", type=float, default=1.0)
    ap.add_argument("--kweight", type=float, default=2)
    a = ap.parse_args()
    for f in a.files:
        g = read_any(f)
        normalize(g)
        autobk(g, rbkg=a.rbkg, kweight=a.kweight)
        print(f"{g.label}: E0={g.e0:.2f}  k=0..{g.k[-1]:.2f}  n={len(g.k)}")


if __name__ == "__main__":
    main()
