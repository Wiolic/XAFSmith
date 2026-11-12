"""与系统交互：提示条 toast、打开文件夹、另存为。"""

from __future__ import annotations

from collections import deque

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QLabel

from .core import ERRORS, T


class Toaster:
    """窗口底部的轻提示：正在显示时新消息排队（最多 4 条，与队尾相同的丢弃）；err 显示更久。
    主窗口与帮助窗口共用；owner 是 QMainWindow，left 是左侧栏宽度（居中时扣除）。"""

    def __init__(self, owner, left=0):
        self.owner, self.left = owner, left
        self.label = QLabel(owner)
        self.label.hide()
        self.q = deque(maxlen=4)
        self.timer = QTimer(owner)
        self.timer.setSingleShot(True)
        self.timer.timeout.connect(self._next)

    def show(self, text, kind="ok"):
        if self.timer.isActive():
            if not self.q or self.q[-1] != (text, kind):
                self.q.append((text, kind))
            return
        self._show(text, kind)

    def _next(self):
        if self.q:
            self._show(*self.q.popleft())
        else:
            self.label.hide()

    def _show(self, text, kind):
        t = self.label
        t.setText(text)
        t.setWordWrap(True)
        t.setObjectName("toast")
        t.setProperty("kind", kind)
        t.style().unpolish(t)
        t.style().polish(t)
        t.setMaximumWidth(620)
        t.adjustSize()
        o = self.owner
        t.move((o.width() + self.left - t.width()) // 2, o.height() - t.height() - 110)
        t.raise_()
        t.show()
        self.timer.start(5000 if kind == "err" else 3200)


def toast(parent, text_, kind="ok"):
    if kind == "err":
        ERRORS.append(text_)
    w = parent.window()
    if hasattr(w, "toast"):
        w.toast(text_, kind)


def open_folder(p):
    import os
    import subprocess
    import sys
    from pathlib import Path
    p = Path(p)
    p.mkdir(parents=True, exist_ok=True)
    try:
        os.startfile(str(p))
    except AttributeError:
        subprocess.Popen(["open" if sys.platform == "darwin" else "xdg-open", str(p)])


def save_file_dialog(parent, default_name, data: bytes, filt="*.*"):
    """另存为（对应网页版的“下载”）"""
    from PySide6.QtWidgets import QFileDialog
    from pathlib import Path
    fn, _ = QFileDialog.getSaveFileName(parent, T("保存", "Save"), str(Path.home() / "Desktop" / default_name), filt)
    if fn:
        Path(fn).write_bytes(data)
        toast(parent, T(f"已保存 {fn}", f"Saved {fn}"))
    return fn
