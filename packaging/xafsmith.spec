# -*- mode: python ; coding: utf-8 -*-
# PyInstaller 配置：onedir，两个可执行文件共用一套依赖
#   XAFSmith.exe      窗口版（无控制台，双击开图形界面）
#   xafsmith-cli.exe  控制台版（命令行 / AI 助手）
# 构建：python -m PyInstaller packaging/xafsmith.spec --noconfirm   （在 XAFSmith/ 目录下）
import os
ROOT = os.path.dirname(SPECPATH)          # XAFSmith/
from PyInstaller.utils.hooks import collect_all, collect_data_files, collect_submodules

datas, binaries, hiddenimports = [], [], []
for pkg in ("larch", "xraydb", "xafsmith"):
    d, b, h = collect_all(pkg)
    datas += d; binaries += b; hiddenimports += h
# 构建环境是 pip install -e：dist-info 里的 direct_url.json 标记“开发安装”并含构建机本地路径，不能带进安装包
datas = [x for x in datas if os.path.basename(x[0]) != "direct_url.json"]
# pymatgen 只用到 Element 与 SpacegroupAnalyzer；其数据文件（元素表等）必须带上
datas += collect_data_files("pymatgen")
hiddenimports += collect_submodules("pymatgen.core") + collect_submodules("pymatgen.symmetry") \
    + ["pymatgen.io.cif", "pymatgen.io.feff"]
hiddenimports += ["matplotlib.backends.backend_qtagg", "matplotlib.backends.backend_agg", "PySide6.QtSvg"]

import sys

# 没用到的 Qt 模块与大包，去掉以缩小体积（先保守，见 CHANGELOG 里的体积记录）
excludes = [
    "tkinter", "PySide6.QtWebEngineCore", "PySide6.QtWebEngineWidgets", "PySide6.QtWebEngineQuick", "PySide6.QtPdf",
    "PySide6.QtPdfWidgets", "PySide6.QtQuick", "PySide6.QtQml", "PySide6.Qt3DCore", "PySide6.QtMultimedia",
    "PySide6.QtCharts", "PySide6.QtDataVisualization", "PySide6.QtBluetooth", "PySide6.QtNetworkAuth",
    "IPython", "notebook", "jupyter", "pytest", "wx", "wxmplot",
    # 体积瘦身（2026-11 阶段 5）：据 packaging/used_modules.py 的实测，这些包在测试流程中从未被导入，
    # 或只是 larch / pandas 里 try-import 的可选依赖（缺了自动回退：mkl_fft→scipy.fftpack，sklearn→无 PCA，pyarrow→pandas 默认）。
    # 注意 silx / fabio / h5py / hdf5plugin 不能排除：larch.io 启动时直接 import。
    "mkl", "mkl_fft", "pyarrow", "sklearn", "skimage", "plotly", "pyFAI", "botocore", "boto3", "mypy",
    "mp_api", "emmet",
]

def analysis(entry):
    return Analysis([entry], pathex=[os.path.join(ROOT, "src")], binaries=binaries, datas=datas, hiddenimports=hiddenimports,
                    excludes=excludes, noarchive=False)

a_gui = analysis(os.path.join(ROOT, "packaging", "xafsmith_gui_entry.py"))
a_cli = analysis(os.path.join(ROOT, "packaging", "xafsmith_cli_entry.py"))
pyz_gui = PYZ(a_gui.pure)
pyz_cli = PYZ(a_cli.pure)

exe_gui = EXE(pyz_gui, a_gui.scripts, [], exclude_binaries=True, name="XAFSmith", console=False,
              icon=os.path.join(ROOT, "src", "xafsmith", "assets", "xafsmith.ico"), contents_directory="_internal")
exe_cli = EXE(pyz_cli, a_cli.scripts, [], exclude_binaries=True, name="xafsmith-cli", console=True,
              icon=os.path.join(ROOT, "src", "xafsmith", "assets", "xafsmith.ico"), contents_directory="_internal")

# Qt 翻译文件只留中文与英文（其余约 6 MB 用不到）；opengl32sw.dll 先保留（无显卡驱动时可能需要，待另一台电脑验收后再定）
def _keep(item):
    dest = item[0].replace("\\", "/")
    if "PySide6/translations/" in dest:
        n = dest.rsplit("/", 1)[-1]
        return any(k in n for k in ("_zh_CN", "_en"))
    return True
for _a in (a_gui, a_cli):
    _a.datas = [d for d in _a.datas if _keep(d)]
    _a.binaries = [b for b in _a.binaries if not b[0].lower().startswith(("mkl", "libiomp5md"))]

coll = COLLECT(exe_gui, a_gui.binaries, a_gui.datas,
               exe_cli, a_cli.binaries, a_cli.datas,
               name="XAFSmith")

# macOS：把窗口版包成 XAFSmith.app（未在 macOS 上验证；图标需要 .icns，暂不设置）
if sys.platform == "darwin":
    app = BUNDLE(coll, name="XAFSmith.app", icon=None, bundle_identifier="io.github.wiolic.xafsmith",
                 info_plist={"CFBundleShortVersionString": "0", "NSHighResolutionCapable": True})
