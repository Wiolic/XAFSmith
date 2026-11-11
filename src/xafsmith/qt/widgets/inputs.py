"""输入控件：数值框、文本框、下拉、复选、分段按钮、多选框。"""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (QCheckBox, QComboBox, QDoubleSpinBox, QFrame, QHBoxLayout, QLineEdit, QListWidget, QListWidgetItem, QPushButton, QSizePolicy, QSpinBox, QVBoxLayout, QWidget)
from ..theme import C

from .core import T, en
from .basic import hbox, link


def num(value=0.0, lo=-1e9, hi=1e9, step=0.1, decimals=2, width=None):
    s = QDoubleSpinBox()
    s.setRange(lo, hi)
    s.setDecimals(decimals)
    s.setSingleStep(step)
    s.setValue(float(value))
    s.setKeyboardTracking(False)
    if width:
        s.setFixedWidth(width)
    return s


def inum(value=0, lo=-10**6, hi=10**6):
    s = QSpinBox()
    s.setRange(lo, hi)
    s.setValue(int(value))
    s.setKeyboardTracking(False)
    return s


def text(value="", placeholder=""):
    e = QLineEdit(str(value) if value is not None else "")
    e.setPlaceholderText(placeholder)
    return e


def combo(options, current=None, fmt=None):
    """options: 取值列表；fmt: 取值 → 显示文字。用 .value() 取当前值"""
    cb = QComboBox()
    cb._vals = list(options)
    for o in cb._vals:
        cb.addItem(fmt(o) if fmt else str(o))
    if current is not None and current in cb._vals:
        cb.setCurrentIndex(cb._vals.index(current))
    cb.value = lambda: cb._vals[cb.currentIndex()] if cb._vals and cb.currentIndex() >= 0 else None
    cb.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
    cb.setMinimumContentsLength(6)
    return cb


def check(text_, value=False):
    c = QCheckBox(text_)
    c.setChecked(bool(value))
    return c


class Segmented(QWidget):
    """分段按钮（单选）"""
    changed = Signal(object)

    def __init__(self, options, current=None, fmt=None):
        super().__init__()
        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)
        self.vals = list(options)
        self.btns = []
        for i, o in enumerate(self.vals):
            b = QPushButton((fmt(o) if fmt else str(o)).replace("&", "&&"))
            b.setObjectName("seg")
            b.setCheckable(True)
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            b.setProperty("first", i == 0)
            b.clicked.connect(lambda _=False, j=i: self.set(self.vals[j], emit=True))
            # 圆角：第一个与最后一个
            r = "9px"
            if i == 0:
                b.setStyleSheet(f"border-top-left-radius:{r};border-bottom-left-radius:{r};")
            if i == len(self.vals) - 1:
                b.setStyleSheet(b.styleSheet() + f"border-top-right-radius:{r};border-bottom-right-radius:{r};")
            if i:
                b.setStyleSheet(b.styleSheet() + "margin-left:-1px;")
            lay.addWidget(b)
            self.btns.append(b)
        lay.addStretch(1)
        self.set(current if current in self.vals else self.vals[0])

    def set(self, v, emit=False):
        self._v = v
        for o, b in zip(self.vals, self.btns):
            b.setChecked(o == v)
        if emit:
            self.changed.emit(v)

    def value(self):
        return self._v


class MultiSelect(QPushButton):
    """多选：点击弹出可勾选列表（带搜索、全选、清空）"""
    changed = Signal(list)

    def __init__(self, options, selected=(), placeholder=None, fmt=None, max_sel=None):
        super().__init__()
        self.setObjectName("combo")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.opts = list(options)
        self.fmt = fmt or str
        self.max_sel = max_sel
        self.placeholder = placeholder or T("选择…", "Select…")
        self.sel = [o for o in selected if o in self.opts]
        self.clicked.connect(lambda *_: self._popup())
        self._update_text()

    def set_options(self, options, selected=None):
        self.opts = list(options)
        self.sel = [o for o in (self.sel if selected is None else selected) if o in self.opts]
        self._update_text()

    def value(self):
        return list(self.sel)

    def set_value(self, sel, emit=False):
        self.sel = [o for o in self.opts if o in set(sel)]
        self._update_text()
        if emit:
            self.changed.emit(self.value())

    def _update_text(self):
        if not self.sel:
            t = self.placeholder
        elif len(self.sel) <= 3:
            t = "、".join(self.fmt(s) for s in self.sel) if not en() else ", ".join(self.fmt(s) for s in self.sel)
        else:
            t = T(f"{self.fmt(self.sel[0])} 等 {len(self.sel)} 项", f"{self.fmt(self.sel[0])} + {len(self.sel) - 1} more")
        fm = self.fontMetrics()
        self.setText(fm.elidedText(t, Qt.TextElideMode.ElideRight, max(120, self.width() - 30)) + "  ▾")
        self.setToolTip("\n".join(self.fmt(s) for s in self.sel))

    def resizeEvent(self, e):
        super().resizeEvent(e)
        self._update_text()

    def _popup(self):
        pop = QFrame(self, Qt.WindowType.Popup)
        pop.setObjectName("card")
        pop.setStyleSheet(f"QFrame#card{{background:{C['raised']};border:1px solid {C['border']};border-radius:12px;}}")
        lay = QVBoxLayout(pop)
        lay.setContentsMargins(8, 8, 8, 8)
        lay.setSpacing(6)
        q = QLineEdit()
        q.setPlaceholderText(T("搜索", "Search"))
        lw = QListWidget()
        lw.setStyleSheet("QListWidget{border:none;background:transparent;}")
        for o in self.opts:
            it = QListWidgetItem(self.fmt(o))
            it.setData(Qt.ItemDataRole.UserRole, o)
            it.setFlags(it.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            it.setCheckState(Qt.CheckState.Checked if o in self.sel else Qt.CheckState.Unchecked)
            lw.addItem(it)

        def changed(_it=None):
            sel = [lw.item(i).data(Qt.ItemDataRole.UserRole) for i in range(lw.count())
                   if lw.item(i).checkState() == Qt.CheckState.Checked]
            if self.max_sel and len(sel) > self.max_sel and _it is not None:
                lw.blockSignals(True)
                _it.setCheckState(Qt.CheckState.Unchecked)
                lw.blockSignals(False)
                return
            self.sel = sel
            self._update_text()
            self.changed.emit(self.value())

        def click(it):
            it.setCheckState(Qt.CheckState.Unchecked if it.checkState() == Qt.CheckState.Checked else Qt.CheckState.Checked)

        lw.itemChanged.connect(changed)
        lw.itemClicked.connect(click)
        q.textChanged.connect(lambda s: [lw.item(i).setHidden(s.lower() not in lw.item(i).text().lower())
                                         for i in range(lw.count())])

        def set_all(v):
            lw.blockSignals(True)
            for i in range(lw.count()):
                if not lw.item(i).isHidden():
                    lw.item(i).setCheckState(Qt.CheckState.Checked if v else Qt.CheckState.Unchecked)
            lw.blockSignals(False)
            changed()
        bar = hbox(link(T("全选", "All"), lambda: set_all(True)), link(T("清空", "None"), lambda: set_all(False)), None)
        if len(self.opts) > 8:
            lay.addWidget(q)
        lay.addWidget(lw)
        if not self.max_sel:
            lay.addWidget(bar)
        h = min(360, 24 * len(self.opts) + 90)
        pop.resize(max(self.width(), 260), h)
        pop.move(self.mapToGlobal(self.rect().bottomLeft()))
        pop.show()
        q.setFocus()
