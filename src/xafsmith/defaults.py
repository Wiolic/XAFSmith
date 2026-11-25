"""defaults —— 默认值与常量的单一来源（无 Qt、无 larch 导入，只放常量）。

normalize / autobk / ft 的 DEFAULT_* 与 schema / pipeline / qt 里的同名常量都指向这里。
"""

# 处理参数默认值（normalize.DEFAULT_NORM / autobk.DEFAULT_BKG / ft.DEFAULT_FT 即这三个对象）
# 注意 norm2：这里是 None；写进新建 xafsmith.json 的是 -10（CONFIG_EDGE_DEFAULTS）。
# normalize.normalize 里 None、0、-10 都得 e_end−e0−10（等价），但 io.py 导出 Athena 工程时 None 得 e_end−e0
# （偏移 0），与 -10 不等价；两处各自保持原行为，不合并。
NORM = dict(pre1=-150.0, pre2=-30.0, norm1=100.0, norm2=None, nnorm=2, nvict=0,
            e0_method="deriv", e0=None, smooth_ev=1.0)
BKG = dict(rbkg=1.0, kweight=2, kmin=0.0, kmax=None, dk=0.1, win="hanning",
           nclamp=3, clamp_lo=0, clamp_hi=1)
FT = dict(kmin=3.0, kmax=12.0, dk=1.0, window="hanning", kweight=2, rmax_out=10.0)

# pipeline.default_edge_config 写入新建 xafsmith.json 的 norm/bkg/ft（用户文件里的值；norm2=-10 而不是 None）
CONFIG_EDGE_DEFAULTS = dict(
    norm=dict(pre1=-150, pre2=-30, norm1=100, norm2=-10, nnorm=2, smooth_ev=1.0),
    bkg=dict(rbkg=1.0, kweight=2),
    ft=dict(kmin=3.0, kmax=12.0, dk=1.0, window="hanning", kweight=2))

# data/meta.csv 的列（schema 1.1：format、group 为可选列；seq 为可选列）
META_COLS = ["file", "sample", "edge_key", "mode", "role", "use", "time", "npts", "emax", "note",
             "batch", "ref_file", "format", "group", "seq"]

# 两个后缀集合用途不同、内容不同，不合并：
# DATA_SUFFIX：pipeline 给样品命名时，这些后缀取 stem，其余保留完整文件名
DATA_SUFFIX = {".xdi", ".xmu", ".dat", ".txt", ".csv", ".chi", ".prj"}
# RAW_LIST_SUFFIX：GUI 列出原始数据文件夹时，直接认作数据文件的后缀（含 .nor，不含 .csv .chi）
RAW_LIST_SUFFIX = (".dat", ".xmu", ".nor", ".txt", ".prj", ".xdi")
