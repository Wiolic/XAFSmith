"""defaults —— 默认值与常量的单一来源（无 Qt、无 larch 导入，只放常量）。

normalize / autobk / ft 的 DEFAULT_* 与 schema / pipeline / qt 里的同名常量都指向这里。
"""
from pathlib import Path
from typing import Any

# 用户级目录（日志、最近项目、设置），在导入时求值。paths.USER_DIR 指向同一对象；
# logs / update 在 cli 解析 --project 之前就被导入，不能为此导入 paths（paths 导入时即确定项目根目录），所以定义放在这里
USER_DIR = Path.home() / ".xafsmith"

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

# 精细拟合页参数表：新参数的初值 (value, vary, min, max)，按参数名匹配（services.default_param_row）。
# 前缀判断顺序：thD/thE 先于 ss0_ 先于 ss；不与 quickfit 的 SS_INIT 等合并（语义不同）
FIT_PARAM_DEFAULTS: dict[str, Any] = dict(
    exact={"s02": (0.85, True, 0.3, 1.5), "e0": (0.0, True, -15, 15)},
    theta=(300.0, True, 50.0, 2000.0),     # thD*, thE*
    ss0=(0.0, True, None, None),           # ss0_*
    ss=(0.003, True, 0.0, 0.05),           # ss*
    dr=(0.0, True, -0.5, 0.5),             # dr*
    other=(1.0, True, None, None))
