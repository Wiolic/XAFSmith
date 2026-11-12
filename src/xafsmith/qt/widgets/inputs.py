"""输入控件：数值框、文本框、下拉、复选、分段按钮、多选框。"""

from __future__ import annotations

from PySide6.QtCore import QTimer, Qt, Signal
from PySide6.QtWidgets import (QCheckBox, QComboBox, QDoubleSpinBox, QFrame, QHBoxLayout, QLineEdit, QListWidget, QListWidgetItem, QPushButton, QSizePolicy, QSpinBox, QVBoxLayout, QWidget)
from ..theme import C, WIDTH

from .core import T, en
from .basic import hbox, link


class _NoWheel:
    """未获得焦点时忽略滚轮：滚动页面时不会误改参数（点进输入框后滚轮才起作用）"""

    def wheelEvent(self, e):
        if self.hasFocus():
            super().wheelEvent(e)
        else:
            e.ignore()


class _Spin(_NoWheel, QDoubleSpinBox):
    pass


class _ISpin(_NoWheel, QSpinBox):
    pass


class _Combo(_NoWheel, QComboBox):
    pass


def debounced(owner, fn, ms=250):
    """返回一个“最后一次调用 ms 毫秒后才执行 fn”的函数（参数即时重画用，连续微调只算一次）。
    返回的函数带 .flush()：立即执行挂起的那次（测试与“应用”按钮用）。owner 销毁后挂起的调用自动作废。"""
    t = QTimer(owner)
    t.setSingleShot(True)
    t.setInterval(ms)
    t.timeout.connect(fn)

    def call(*_a):
        t.start()

    def flush():
        try:
            if t.isActive():
                t.stop()
                fn()
        except RuntimeError:          # 页面已重建，旧控件已删除
            pass
    call.flush = flush
    reg = getattr(owner, "_debounced", None)       # Page 在切页前统一 flush，防止 250 ms 内离开页面丢掉修改
    if reg is not None:
        reg.append(call)
    return call


def link_range(lo, hi, gap=0.1):
    """范围联动：保证 lo < hi（至少相差 gap）。改 lo 超过 hi 时把 hi 顶上去，改 hi 低于 lo 时把 lo 压下来；
    被推的一端到了自己的上下限就把正在改的这一端退回。"""
    def fix_hi(_v=None):
        if hi.value() < lo.value() + gap - 1e-9:
            want = lo.value() + gap
            if want <= hi.maximum() + 1e-9:
                hi.setValue(want)
            else:
                lo.setValue(hi.value() - gap)

    def fix_lo(_v=None):
        if lo.value() > hi.value() - gap + 1e-9:
            want = hi.value() - gap
            if want >= lo.minimum() - 1e-9:
                lo.setValue(want)
            else:
                hi.setValue(lo.value() + gap)
    lo.valueChanged.connect(fix_hi)
    hi.valueChanged.connect(fix_lo)


def set_invalid(widget, bad, tip=""):
    """输入非法：红框（动态属性 invalid，样式见 theme.qss）+ 悬停说明"""
    widget.setProperty("invalid", bool(bad))
    widget.setToolTip(tip if bad else "")
    widget.style().unpolish(widget)
    widget.style().polish(widget)


def num(value=0.0, lo=-1e9, hi=1e9, step=0.1, decimals=2, width=None):
    s = _Spin()
    s.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
    s.setRange(lo, hi)
    s.setDecimals(decimals)
    s.setSingleStep(step)
    s.setValue(float(value))
    s.setKeyboardTracking(False)
    if width:
        s.setFixedWidth(width)
    return s


def inum(value=0, lo=-10**6, hi=10**6):
    s = _ISpin()
    s.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
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
    cb = _Combo()
    cb.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
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
            b.clicked.connect(lambda _=False, j=i: self.set(self.vals[j], emit=True))
            n = len(self.vals)
            b.setProperty("pos", "only" if n == 1 else "first" if i == 0 else "last" if i == n - 1 else "mid")
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

    def minimumSizeHint(self):
        sz = super().minimumSizeHint()
        sz.setWidth(min(sz.width(), 120))
        return sz

    def sizeHint(self):
        # 文字很长时（多个选中项）不按文字长度撑宽布局；显示时按实际宽度省略
        sz = super().sizeHint()
        sz.setWidth(min(sz.width(), 240))
        return sz

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
        lay = QVBoxLayout(pop)
        lay.setContentsMargins(8, 8, 8, 8)
        lay.setSpacing(6)
        q = QLineEdit()
        q.setPlaceholderText(T("搜索", "Search"))
        lw = QListWidget()
        lw.setObjectName("plain")
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
        pop.resize(max(self.width(), WIDTH['popup_min']), h)
        pop.move(self.mapToGlobal(self.rect().bottomLeft()))
        pop.show()
        q.setFocus()


class OrderList(QWidget):
    """可调整顺序的列表：拖动条目，或选中后用 ↑ / ↓ / 倒序按钮。.value() 取当前顺序，changed(list) 在顺序变化时发出。
    set_items(新列表)：保留已有条目的相对顺序，新条目追加在末尾，已不存在的移除。fmt：取值 → 显示文字。"""
    changed = Signal(list)

    def __init__(self, items=(), fmt=None):
        from PySide6.QtWidgets import QAbstractItemView, QToolButton
        from ..theme import icon
        super().__init__()
        self.fmt = fmt or str
        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(6)
        self.lw = QListWidget()
        self.lw.setDragDropMode(QAbstractItemView.DragDropMode.InternalMove)
        self.lw.setDefaultDropAction(Qt.DropAction.MoveAction)
        self.lw.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.lw.model().rowsMoved.connect(lambda *_: self._emit())
        lay.addWidget(self.lw, 1)
        col = QVBoxLayout()
        col.setSpacing(4)
        self.btns = {}
        for key, ic, tip, fn in (("up", "chevup", T("上移", "Move up"), lambda: self.move(-1)),
                                 ("down", "chev", T("下移", "Move down"), lambda: self.move(1)),
                                 ("rev", "refresh", T("整体倒序", "Reverse all"), self.reverse)):
            b = QToolButton()
            b.setIcon(icon(ic, C["text2"], 16))
            b.setToolTip(tip)
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            b.clicked.connect(fn)
            col.addWidget(b)
            self.btns[key] = b
        col.addStretch(1)
        lay.addLayout(col)
        self.set_items(list(items))

    def _fit_height(self):
        rh = self.lw.sizeHintForRow(0) if self.lw.count() else -1      # 实际行高（含样式表的内边距）
        if rh <= 0:
            rh = self.lw.fontMetrics().height() + 10
        n = max(2, min(8, self.lw.count()))
        self.lw.setFixedHeight(n * rh + 2 * self.lw.frameWidth() + 8)

    def value(self):
        return [self.lw.item(i).data(Qt.ItemDataRole.UserRole) for i in range(self.lw.count())]

    def _fill(self, vals, cur=None):
        self.lw.blockSignals(True)
        self.lw.clear()
        for v in vals:
            it = QListWidgetItem(f"{self.fmt(v)}")
            it.setData(Qt.ItemDataRole.UserRole, v)
            self.lw.addItem(it)
        if cur is not None and 0 <= cur < self.lw.count():
            self.lw.setCurrentRow(cur)
        self.lw.blockSignals(False)
        self._fit_height()

    def set_items(self, items, emit=False):
        old = self.value()
        new = [x for x in old if x in items] + [x for x in items if x not in old]
        if new != old:
            self._fill(new)
            if emit:
                self._emit()

    def set_value(self, order, emit=False):
        self._fill(list(order))
        if emit:
            self._emit()

    def move(self, d):
        r = self.lw.currentRow()
        v = self.value()
        if r < 0 or not (0 <= r + d < len(v)):
            return
        v[r], v[r + d] = v[r + d], v[r]
        self._fill(v, r + d)
        self._emit()

    def reverse(self):
        v = self.value()
        if len(v) > 1:
            r = self.lw.currentRow()
            self._fill(v[::-1], len(v) - 1 - r if r >= 0 else None)
            self._emit()

    def _emit(self):
        self.changed.emit(self.value())
