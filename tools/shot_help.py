"""帮助窗口截图（offscreen）：用法 python tools/shot_help.py <输出目录> [缩放，默认 1]
会在 <输出目录> 下为每个语言、4 处位置各存一张 PNG，供人眼检查讲义图片与公式。
缩放通过 QT_SCALE_FACTOR 设置；中文字体需要 QT_QPA_FONTDIR（脚本自动设为 C:/Windows/Fonts）。"""
import os
import sys
from pathlib import Path

out = Path(sys.argv[1]).resolve()
scale = sys.argv[2] if len(sys.argv) > 2 else "1"
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_QPA_FONTDIR", "C:/Windows/Fonts")
os.environ["QT_SCALE_FACTOR"] = scale
out.mkdir(parents=True, exist_ok=True)

from PySide6.QtWidgets import QApplication  # noqa: E402

from xafsmith.qt import theme, widgets as W  # noqa: E402
from xafsmith.qt.help import HelpWindow  # noqa: E402

app = QApplication([])
app.setStyleSheet(theme.qss())


def pump(ms=400):
    from PySide6.QtCore import QEventLoop, QTimer
    loop = QEventLoop()
    QTimer.singleShot(ms, loop.quit)
    loop.exec()


for lang in ("zh", "en"):
    W.LANG["v"] = lang
    win = HelpWindow(None)
    win.resize(1000, 800)
    win.show()
    win.show_tab("basics")
    pump(700)
    tb = win.btn["basics"][1].layout().itemAt(0).widget().tb
    sb = tb.verticalScrollBar()
    for i, frac in enumerate((0.0, 0.25, 0.55, 0.85)):
        sb.setValue(int(sb.maximum() * frac))
        pump(150)
        win.grab().save(str(out / f"help_{lang}_x{scale}_{i}.png"))
    win.resize(700, 800)                     # 拖窄窗口：图片应随宽度重算
    pump(700)
    sb.setValue(int(sb.maximum() * 0.25))
    pump(150)
    win.grab().save(str(out / f"help_{lang}_x{scale}_narrow.png"))
    win.close()
print("ok", out)
