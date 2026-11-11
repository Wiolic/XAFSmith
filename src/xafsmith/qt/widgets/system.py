"""与系统交互：提示条 toast、打开文件夹、另存为。"""

from __future__ import annotations

from .core import ERRORS, T


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
