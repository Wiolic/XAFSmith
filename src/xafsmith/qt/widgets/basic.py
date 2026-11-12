"""基本元素：标签、分隔线、按钮、行列布局、表单字段。"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QGridLayout, QHBoxLayout, QLabel, QPushButton, QSizePolicy, QVBoxLayout, QWidget
from ..theme import C, icon


def label(text="", kind=None, wrap=True, rich=False):
    lb = QLabel(text)
    if kind:
        lb.setObjectName(kind)
    lb.setWordWrap(wrap)
    if rich:
        lb.setTextFormat(Qt.TextFormat.RichText)
        lb.setOpenExternalLinks(True)
    lb.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse | Qt.TextInteractionFlag.LinksAccessibleByMouse)
    return lb


def hline():
    f = QFrame()
    f.setObjectName("hline")
    return f


def button(text, primary=False, icon_name=None, slot=None, tip=None):
    b = QPushButton(text.replace("&", "&&"))      # “&” 不作快捷键标记
    if primary:
        b.setObjectName("primary")
    if icon_name:
        b.setIcon(icon(icon_name, "#FFFFFF" if primary else C["text2"], 16, disabled=C["text3"]))
    if slot:
        b.clicked.connect(lambda *_: slot())
    if tip:
        b.setToolTip(tip)
    b.setCursor(Qt.CursorShape.PointingHandCursor)
    return b


def link(text, slot):
    b = QPushButton(text)
    b.setObjectName("link")
    b.setCursor(Qt.CursorShape.PointingHandCursor)
    b.clicked.connect(lambda *_: slot())
    return b


def hbox(*ws, spacing=10, stretch_last=False, margins=(0, 0, 0, 0)):
    w = QWidget()
    lay = QHBoxLayout(w)
    lay.setContentsMargins(*margins)
    lay.setSpacing(spacing)
    for x in ws:
        if x is None:
            lay.addStretch(1)
        elif isinstance(x, int):
            lay.addSpacing(x)
        elif isinstance(x, QLabel) and x.wordWrap():
            # 会换行的说明文字：占据剩余宽度（否则被挤成很窄的一列，逐字换行）
            x.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
            lay.addWidget(x, 20)
        else:
            lay.addWidget(x)
    if stretch_last:
        lay.addStretch(1)
    return w


def vbox(*ws, spacing=8):
    w = QWidget()
    lay = QVBoxLayout(w)
    lay.setContentsMargins(0, 0, 0, 0)
    lay.setSpacing(spacing)
    for x in ws:
        if x is None:
            lay.addStretch(1)
        else:
            lay.addWidget(x)
    return w


def field(title, widget, tip=None):
    """标签在上、输入在下的表单字段"""
    w = QWidget()
    lay = QVBoxLayout(w)
    lay.setContentsMargins(0, 0, 0, 0)
    lay.setSpacing(4)
    lb = QLabel(title)
    lb.setObjectName("faint")
    if tip:
        lb.setToolTip(tip)
        widget.setToolTip(tip)
    lay.addWidget(lb)
    lay.addWidget(widget)
    w.input = widget
    return w


def fields(*items, cols=None):
    """一行多个字段：items = [(标题, 控件[, 提示]), ...]；cols 为每行列数（自动换行）"""
    w = QWidget()
    g = QGridLayout(w)
    g.setContentsMargins(0, 0, 0, 0)
    g.setHorizontalSpacing(12)
    g.setVerticalSpacing(10)
    n = cols or len(items)
    for i, it in enumerate(items):
        g.addWidget(field(*it), i // n, i % n)
    for c in range(n):
        g.setColumnStretch(c, 1)
    return w
