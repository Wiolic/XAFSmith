"""autobk —— 背景扣除（larch autobk），得到 χ(k)。

参数（样品间保持一致）：rbkg、kweight、kmin、kmax、clamp_lo/hi。
"""


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
