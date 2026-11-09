"""xafsmith —— 通用 XAFS 数据处理与拟合工具包（基于 xraylarch）。

模块：
    io          读入束线文件 / Athena .prj / 通用列文本
    qc          数据质量检查
    calib       参比箔能量校准
    normalize   扫描合并、边前/边后归一化、E0
    autobk      背景扣除得到 chi(k)
    ft          傅里叶变换与反变换
    wavelet     小波变换（Cauchy / Morlet）
    structures  内置标准结构（pymatgen Structure）
    feff_wrap   结构 → feff.inp → 运行 feff6l → 路径
    fit_exafs   EXAFS 路径拟合（larch feffit 封装）
    fit_lcf     线性组合拟合
    mut_planner 样品设计（μt、边跳、干扰边）
    report      作图与结果表
    paths       项目目录标准（xafsmith.json、data/、structures/、models/、output/ …）
    schema      数据标准检查（xafsmith validate）
    pipeline    配置驱动的批处理（meta.csv + xafsmith.json）
    cli         命令行 xafsmith
    gui         图形界面（xafsmith gui）
"""
__version__ = "0.1.0"
