"""全局状态（语言、错误列表、静默开关）与最基础的小函数。可变全局只在此处定义。"""

from __future__ import annotations

from PySide6.QtWidgets import QWidget


LANG = {"v": "zh"}


ERRORS = []          # 运行中出现的异常（自动测试检查它；界面上同时以提示条 / 弹窗显示）


QUIET = {"v": False}  # 测试时不弹模态对话框


def tag(w, key):
    """给控件一个稳定的名字（自动测试用）"""
    w.setProperty("xs_key", key)
    return w


def find(root, key):
    for c in root.findChildren(QWidget):
        if c.property("xs_key") == key:
            return c
    return None


def T(zh: str, en: str | None = None) -> str:
    """界面文字：中文 / English"""
    return en if (LANG["v"] == "en" and en is not None) else zh


def en() -> bool:
    return LANG["v"] == "en"
