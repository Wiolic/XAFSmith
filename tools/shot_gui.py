"""主窗口各页截图（offscreen）：用法 python tools/shot_gui.py <输出目录> [缩放，默认 1] [项目目录]
默认复制 tests/data/demo_project 到临时目录（不改原项目），逐页保存 PNG，供人眼检查。
缩放通过 QT_SCALE_FACTOR 设置；中文字体需要 QT_QPA_FONTDIR。"""
import os
import shutil
import sys
import tempfile
from pathlib import Path

out = Path(sys.argv[1]).resolve()
scale = sys.argv[2] if len(sys.argv) > 2 else "1"
src = Path(sys.argv[3]).resolve() if len(sys.argv) > 3 else Path(__file__).resolve().parents[1] / "tests" / "data" / "demo_project"
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_QPA_FONTDIR", "C:/Windows/Fonts")
os.environ["QT_SCALE_FACTOR"] = scale
os.environ["XAFSMITH_NO_RECENT"] = "1"
out.mkdir(parents=True, exist_ok=True)

tmp = Path(tempfile.mkdtemp(prefix="shot_gui_")) / "proj"
shutil.copytree(src, tmp)

from PySide6.QtCore import QEventLoop, QTimer  # noqa: E402

from xafsmith.qt.app import make_window  # noqa: E402


def pump(ms=500):
    loop = QEventLoop()
    QTimer.singleShot(ms, loop.quit)
    loop.exec()


app, w = make_window(str(tmp), lang="zh")
w.resize(1440, 900)
w.show()
pump(800)
for key in list(w.nav):
    try:
        w.go(key)
        pump(700)
        w.grab().save(str(out / f"gui_x{scale}_{key}.png"))
    except Exception as e:      # 单页失败不影响其余页
        print("FAIL", key, e)
w.close()
shutil.rmtree(tmp.parent, ignore_errors=True)
print("ok", out)
