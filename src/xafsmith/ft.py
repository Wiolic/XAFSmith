"""ft —— k 空间加窗与傅里叶变换（larch xftf）。

所有 R 空间图须标注“未相移校正”。
"""


DEFAULT_FT = dict(kmin=3.0, kmax=12.0, dk=1.0, window="hanning", kweight=2, rmax_out=10.0)


def forward(g, **kws):
    p = dict(DEFAULT_FT)
    p.update({k: v for k, v in kws.items() if v is not None})
    from larch.xafs import xftf  # larch.xafs 导入约 2 秒：用到时才导入，加快启动
    xftf(g, kmin=p["kmin"], kmax=p["kmax"], dk=p["dk"], window=p["window"],
         kweight=p["kweight"], rmax_out=p["rmax_out"])
    g.ft_params = p
    return g
