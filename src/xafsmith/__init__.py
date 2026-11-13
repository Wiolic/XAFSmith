"""xafsmith —— 可连接 AI 助手（agent）的同步辐射 XAFS 分析软件包（基于 xraylarch / FEFF）。

模块：
    io          读入束线文件 / Athena .prj / 通用列文本
    qc          数据质量检查
    calib       参比箔能量校准
    normalize   扫描合并、边前/边后归一化、E0
    autobk      背景扣除得到 chi(k)
    ft          k 空间加窗与傅里叶变换
    wavelet     小波变换（Cauchy / Morlet）
    structures  内置标准结构（pymatgen Structure）
    feff_wrap   结构 → feff.inp → 运行 feff6l → 路径
    fit_exafs   EXAFS 路径拟合（larch feffit 封装）
    fit_lcf     线性组合拟合
    mut_planner 样品设计（μt、边跳、干扰边）
    report      作图与结果表
    xanes       XANES 定量：边位置、白线、价态标定、边前峰拟合
    pubfig      期刊风格出图（600 dpi TIFF / SVG / PDF + 英文图注）
    methods_text 自动生成“方法”段落（中英文）
    update      检查 / 安装 GitHub 上的新版本
    paths       项目目录标准（xafsmith.json、data/、structures/、models/、output/ …）
    schema      数据标准检查（xafsmith validate）
    pipeline    配置驱动的批处理（meta.csv + xafsmith.json）
    cli         命令行 xafsmith
    qt          图形界面（PySide6 原生窗口，xafsmith gui）
"""
__version__ = "1.3.0"
