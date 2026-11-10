"""通用控件：页面骨架、卡片、表单字段、多选框、表格（可编辑）、图表、提示条、后台任务。"""
from __future__ import annotations

import traceback

import numpy as np
import pandas as pd
from PySide6.QtCore import (QAbstractTableModel, QModelIndex, QObject, QSize, Qt, QThread, QTimer, Signal, Slot)
from PySide6.QtGui import QColor, QFont, QGuiApplication
from PySide6.QtWidgets import (QAbstractItemView, QApplication, QCheckBox, QComboBox, QDoubleSpinBox, QFrame,
                               QGridLayout, QHBoxLayout, QHeaderView, QLabel, QLineEdit, QListWidget,
                               QListWidgetItem, QMessageBox, QPlainTextEdit, QPushButton, QScrollArea, QSizePolicy,
                               QSpinBox, QStyledItemDelegate, QTableView, QTabWidget, QTextBrowser, QToolButton,
                               QVBoxLayout, QWidget)

from . import theme
from .theme import C, icon

# ----------------------------------------------------------------------------- 语言
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


# ----------------------------------------------------------------------------- 基本元素
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
        b.setIcon(icon(icon_name, "#FFFFFF" if primary else C["text2"], 16))
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


# ----------------------------------------------------------------------------- 卡片与页面
class Card(QFrame):
    def __init__(self, title=None, actions=(), flat=False):
        super().__init__()
        self.setObjectName("flat" if flat else "card")
        self.lay = QVBoxLayout(self)
        m = 0 if flat else 18
        self.lay.setContentsMargins(m, 16 if not flat else 0, m, 18 if not flat else 0)
        self.lay.setSpacing(12)
        if title or actions:
            head = QHBoxLayout()
            head.setSpacing(8)
            if title:
                t = QLabel(title)
                t.setObjectName("h2")
                head.addWidget(t)
            head.addStretch(1)
            for a in actions:
                head.addWidget(a)
            self.lay.addLayout(head)

    def add(self, *ws):
        for w in ws:
            if isinstance(w, QWidget):
                self.lay.addWidget(w)
            else:
                self.lay.addLayout(w)
        return ws[0] if len(ws) == 1 else ws


class Page(QScrollArea):
    """一页：居中的内容列（最大宽度），衬线标题；build() 生成内容，refresh() 重建"""
    title_zh = ""
    title_en = ""
    icon_name = "doc"
    max_width = 1180

    def __init__(self, app):
        super().__init__()
        self.app = app
        self.S = app.S
        self.setWidgetResizable(True)
        self.setFrameShape(QFrame.Shape.NoFrame)
        self._inner = QWidget()
        self._inner.setObjectName("page")
        outer = QHBoxLayout(self._inner)
        outer.setContentsMargins(40, 30, 40, 24)
        self._col = QWidget()
        self._col.setMaximumWidth(self.max_width)
        outer.addStretch(1)
        outer.addWidget(self._col, 100)
        outer.addStretch(1)
        self.body = QVBoxLayout(self._col)
        self.body.setContentsMargins(0, 0, 0, 0)
        self.body.setSpacing(16)
        self.setWidget(self._inner)
        self._built = False
        self.state = {}            # 重建时保留的控件取值

    def title(self):
        return T(self.title_zh, self.title_en)

    def header(self, subtitle=None, actions=()):
        h = QHBoxLayout()
        t = QLabel(self.title())
        t.setObjectName("h1")
        if self.title_zh == "项目":
            from xafsmith import paths as _p
            t.setToolTip(str(_p.ROOT))
        h.addWidget(t)
        h.addStretch(1)
        for a in actions:
            h.addWidget(a)
        self.body.addLayout(h)
        if subtitle:
            self.body.addWidget(label(subtitle, "muted"))

    def add(self, w):
        if isinstance(w, QWidget):
            self.body.addWidget(w)
        else:
            self.body.addLayout(w)
        return w

    def clear(self):
        while self.body.count():
            it = self.body.takeAt(0)
            w_ = it.widget()
            if w_ is not None:
                w_.setParent(None)
                w_.deleteLater()
            elif it.layout():
                _clear_layout(it.layout())

    def refresh(self):
        y = self.verticalScrollBar().value()
        self.clear()
        try:
            self.build()
        except Exception as ex:          # 页面出错时显示错误，不让整个程序退出
            ERRORS.append(f"{type(self).__name__}: {ex}\n{traceback.format_exc()}")
            self.add(Banner("err", f"{type(ex).__name__}: {ex}"))
            self.add(code_block(traceback.format_exc()))
        self.body.addStretch(1)
        self._built = True
        QTimer.singleShot(0, lambda: self.verticalScrollBar().setValue(y))

    def build(self):
        pass

    def on_show(self):
        self.refresh()


def _clear_layout(lay):
    while lay.count():
        it = lay.takeAt(0)
        w_ = it.widget()
        if w_ is not None:
            w_.setParent(None)
            w_.deleteLater()
        elif it.layout():
            _clear_layout(it.layout())


class Banner(QFrame):
    """提示条：info / ok / warn / err"""
    ICON = {"info": "info", "ok": "check", "warn": "alert", "err": "alert"}

    def __init__(self, kind, text_, rich=False):
        super().__init__()
        self.setObjectName("banner_" + kind)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(12, 9, 12, 9)
        lay.setSpacing(10)
        col = {"info": C["text2"], "ok": C["ok"], "warn": C["warn"], "err": C["err"]}[kind]
        ic = QLabel()
        ic.setPixmap(icon(self.ICON[kind], col, 16, 1.9).pixmap(16, 16))
        ic.setFixedWidth(18)
        ic.setAlignment(Qt.AlignmentFlag.AlignTop)
        lay.addWidget(ic)
        lb = label(text_, rich=rich)
        lb.setStyleSheet(f"color:{C['text']};")
        lay.addWidget(lb, 1)


class Metric(QWidget):
    def __init__(self, title, value, sub=None):
        super().__init__()
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(2)
        lay.addWidget(label(title, "metricLabel"))
        v = label(str(value), "metricValue", wrap=False)
        lay.addWidget(v)
        if sub:
            lay.addWidget(label(sub, "faint"))


def metrics(*items):
    w = QWidget()
    lay = QHBoxLayout(w)
    lay.setContentsMargins(0, 0, 0, 0)
    lay.setSpacing(28)
    for it in items:
        lay.addWidget(Metric(*it))
    lay.addStretch(1)
    return w


def pill(text_, ok=True, kind=None):
    kind = kind or ("ok" if ok else "warn")
    lb = QLabel(text_)
    lb.setObjectName("pill")
    lb.setStyleSheet(f"background:{C[kind + '_soft']};color:{C[kind]};")
    return lb


def copy_to_clipboard(text_):
    QGuiApplication.clipboard().setText(text_)


def copy_button(get_text, label_=None):
    b = button(label_ or T("复制", "Copy"), icon_name="copy")

    def go():
        copy_to_clipboard(get_text() if callable(get_text) else get_text)
        old = b.text()
        b.setText(T("已复制 ✓", "Copied ✓"))
        QTimer.singleShot(1400, lambda: b.setText(old))
    b.clicked.connect(go)
    return b


def code_block(text_, copy=False, height=None, wrap=False):
    e = QPlainTextEdit(text_)
    e.setObjectName("code")
    e.setReadOnly(True)
    e.setLineWrapMode(QPlainTextEdit.LineWrapMode.WidgetWidth if wrap else QPlainTextEdit.LineWrapMode.NoWrap)
    lines = text_.count("\n") + 1
    e.setFixedHeight(height or min(420, max(44, 19 * lines + 22)))
    if not copy:
        return e
    w = QWidget()
    lay = QVBoxLayout(w)
    lay.setContentsMargins(0, 0, 0, 0)
    lay.setSpacing(6)
    lay.addWidget(e)
    lay.addWidget(hbox(None, copy_button(text_)))
    return w


def tabs(*pages):
    """pages: [(标题, 控件), ...]"""
    t = QTabWidget()
    t.setDocumentMode(True)
    for title, w in pages:
        t.addTab(w, title.replace("&", "&&"))
    # 标签页高度取所有页面中最高的（否则页面里的图会被裁掉）
    t.setMinimumHeight(max(w.minimumSizeHint().height() for _, w in pages) + t.tabBar().sizeHint().height() + 8)
    return t


def collapsible(title, content, expanded=False):
    """可折叠区域"""
    w = QWidget()
    lay = QVBoxLayout(w)
    lay.setContentsMargins(0, 0, 0, 0)
    lay.setSpacing(8)
    b = QToolButton()
    b.setText(title)
    b.setCheckable(True)
    b.setChecked(expanded)
    b.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
    b.setStyleSheet(f"QToolButton{{font-weight:600;color:{C['text']};padding:4px 2px;border:none;}}"
                    f"QToolButton:hover{{color:{C['accent']};background:transparent;}}")
    b.setCursor(Qt.CursorShape.PointingHandCursor)

    def upd(on):
        b.setArrowType(Qt.ArrowType.DownArrow if on else Qt.ArrowType.RightArrow)
        content.setVisible(on)
    b.toggled.connect(upd)
    lay.addWidget(b)
    lay.addWidget(content)
    upd(expanded)
    return w


def ask(parent, title, text_):
    return QMessageBox.question(parent, title, text_) == QMessageBox.StandardButton.Yes


# ----------------------------------------------------------------------------- 表格
class DFModel(QAbstractTableModel):
    """pandas 表格模型。editable: 可编辑列；bools: 勾选列；choices: {列: 选项}"""
    def __init__(self, df, editable=(), bools=(), choices=None, header_fmt=None, decimals=4):
        super().__init__()
        self.df = df.reset_index(drop=True).copy()
        self.editable = set(editable)
        self.bools = set(bools)
        self.choices = choices or {}
        self.hfmt = header_fmt or (lambda c: str(c))
        self.dec = decimals

    def rowCount(self, p=QModelIndex()):
        return len(self.df)

    def columnCount(self, p=QModelIndex()):
        return self.df.shape[1]

    def _col(self, i):
        return self.df.columns[i]

    def data(self, idx, role=Qt.ItemDataRole.DisplayRole):
        if not idx.isValid():
            return None
        c = self._col(idx.column())
        v = self.df.iat[idx.row(), idx.column()]
        if c in self.bools:
            if role == Qt.ItemDataRole.CheckStateRole:
                return Qt.CheckState.Checked if bool(v) and not (isinstance(v, float) and np.isnan(v)) else Qt.CheckState.Unchecked
            return None
        if role in (Qt.ItemDataRole.DisplayRole, Qt.ItemDataRole.EditRole):
            if v is None or (isinstance(v, float) and np.isnan(v)):
                return ""
            if isinstance(v, (float, np.floating)):
                if role == Qt.ItemDataRole.EditRole:
                    return float(v)
                return f"{v:.{self.dec}g}" if abs(v) < 1e-3 or abs(v) >= 1e5 else f"{round(float(v), self.dec):g}"
            if isinstance(v, (bool, np.bool_)):
                return "✓" if v else ""
            return str(v)
        if role == Qt.ItemDataRole.ForegroundRole and c not in self.editable and self.editable:
            return QColor(C["text2"])
        if role == Qt.ItemDataRole.TextAlignmentRole and isinstance(v, (int, float, np.number)) and not isinstance(v, bool):
            return int(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        return None

    def setData(self, idx, value, role=Qt.ItemDataRole.EditRole):
        c = self._col(idx.column())
        if c in self.bools and role == Qt.ItemDataRole.CheckStateRole:
            self.df.iat[idx.row(), idx.column()] = (value == Qt.CheckState.Checked.value or value == Qt.CheckState.Checked)
        elif role == Qt.ItemDataRole.EditRole:
            old = self.df.iat[idx.row(), idx.column()]
            if isinstance(old, (float, np.floating)) or (old is None and c not in self.choices
                                                         and pd.api.types.is_float_dtype(self.df[c])):
                try:
                    value = float(value) if str(value).strip() != "" else np.nan
                except ValueError:
                    return False
            self.df.iat[idx.row(), idx.column()] = value
        else:
            return False
        self.dataChanged.emit(idx, idx)
        return True

    def flags(self, idx):
        f = Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable
        c = self._col(idx.column())
        if c in self.editable:
            f |= Qt.ItemFlag.ItemIsUserCheckable if c in self.bools else Qt.ItemFlag.ItemIsEditable
        return f

    def headerData(self, s, o, role=Qt.ItemDataRole.DisplayRole):
        if role != Qt.ItemDataRole.DisplayRole:
            return None
        if o == Qt.Orientation.Horizontal:
            return self.hfmt(self._col(s))
        return str(s + 1)


class _ChoiceDelegate(QStyledItemDelegate):
    def __init__(self, choices, parent=None):
        super().__init__(parent)
        self.choices = choices

    def createEditor(self, parent, opt, idx):
        cb = QComboBox(parent)
        cb.addItems([str(x) for x in self.choices])
        return cb

    def setEditorData(self, ed, idx):
        v = str(idx.data(Qt.ItemDataRole.EditRole) or "")
        i = ed.findText(v)
        ed.setCurrentIndex(max(i, 0))

    def setModelData(self, ed, model, idx):
        model.setData(idx, ed.currentText(), Qt.ItemDataRole.EditRole)


class Table(QTableView):
    """显示 / 编辑 DataFrame。.df() 取当前表"""
    edited = Signal()

    def __init__(self, df, editable=(), bools=(), choices=None, height=None, header_fmt=None, decimals=4,
                 stretch=True, max_height=420):
        super().__init__()
        self.m = DFModel(df, editable, bools, choices, header_fmt, decimals)
        self.setModel(self.m)
        for c, opts in (choices or {}).items():
            if c in self.m.df.columns:
                self.setItemDelegateForColumn(list(self.m.df.columns).index(c), _ChoiceDelegate(opts, self))
        self.verticalHeader().setVisible(False)
        self.setAlternatingRowColors(True)
        self.setShowGrid(False)
        self.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.setEditTriggers(QAbstractItemView.EditTrigger.DoubleClicked | QAbstractItemView.EditTrigger.SelectedClicked
                             | QAbstractItemView.EditTrigger.EditKeyPressed | QAbstractItemView.EditTrigger.AnyKeyPressed)
        self.setHorizontalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        self.setVerticalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        hh = self.horizontalHeader()
        hh.setHighlightSections(False)
        hh.setDefaultAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        self.resizeColumnsToContents()
        for i in range(self.m.columnCount()):
            self.setColumnWidth(i, min(max(self.columnWidth(i) + 12, 60), 360))
        if stretch:
            hh.setStretchLastSection(True)
        self.verticalHeader().setDefaultSectionSize(28)
        rows = len(self.m.df)
        self.setFixedHeight(height or min(max_height, 32 + 28 * max(rows, 1) + 6))
        self.m.dataChanged.connect(lambda *_: self.edited.emit())

    def df(self):
        return self.m.df.copy()

    def hide_cols(self, *cols):
        for c in cols:
            if c in self.m.df.columns:
                self.setColumnHidden(list(self.m.df.columns).index(c), True)


# ----------------------------------------------------------------------------- 图表
class Plot(QWidget):
    """matplotlib 图：工具（平移 / 缩放 / 复位 / 存图）+ 鼠标坐标"""
    def __init__(self, height=380, nrows=1, ncols=1, sharex=False, height_ratios=None, width_ratios=None):
        super().__init__()
        from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg, NavigationToolbar2QT
        from matplotlib.figure import Figure
        self.fig = Figure(figsize=(8, height / 100), layout="constrained")
        self.canvas = FigureCanvasQTAgg(self.fig)
        self.canvas.setMinimumHeight(height)
        self.setMinimumHeight(height + 34)
        self.canvas.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.nav = NavigationToolbar2QT(self.canvas, self)
        self.nav.hide()
        kw = {}
        if height_ratios:
            kw["height_ratios"] = height_ratios
        if width_ratios:
            kw["width_ratios"] = width_ratios
        self.axes = self.fig.subplots(nrows, ncols, sharex=sharex, squeeze=False, gridspec_kw=kw or None).ravel()
        self.ax = self.axes[0]
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(2)
        bar = QHBoxLayout()
        bar.setSpacing(2)
        self.coord = QLabel("")
        self.coord.setObjectName("faint")
        bar.addWidget(self.coord)
        bar.addStretch(1)
        self._tools = {}
        for name, tip, fn in (("pan", T("平移", "Pan"), self.nav.pan), ("zoom", T("框选放大", "Zoom to box"), self.nav.zoom)):
            b = QToolButton()
            b.setIcon(icon(name, C["text3"], 16))
            b.setToolTip(tip)
            b.setCheckable(True)
            b.clicked.connect(lambda _=False, f=fn, n=name: self._mode(f, n))
            bar.addWidget(b)
            self._tools[name] = b
        for name, tip, fn in (("zoomreset", T("复位", "Reset view"), self.nav.home),
                              ("download", T("保存图片", "Save image"), self.nav.save_figure)):
            b = QToolButton()
            b.setIcon(icon(name, C["text3"], 16))
            b.setToolTip(tip)
            b.clicked.connect(lambda _=False, f=fn: f())
            bar.addWidget(b)
        lay.addLayout(bar)
        lay.addWidget(self.canvas, 1)
        self.canvas.mpl_connect("motion_notify_event", self._move)

    def _mode(self, fn, name):
        fn()
        for n, b in self._tools.items():
            b.setChecked(n == name and b.isChecked())

    def _move(self, e):
        if e.inaxes and e.xdata is not None:
            self.coord.setText(f"x = {e.xdata:.4g}    y = {e.ydata:.4g}")
        else:
            self.coord.setText("")

    def clear(self):
        for a in self.axes:
            a.clear()

    def draw(self, legend=True):
        for a in self.axes:
            if legend and a.get_legend_handles_labels()[0]:
                n = len(a.get_legend_handles_labels()[0])
                a.legend(loc="best", fontsize=8 if n > 6 else 8.5, ncol=2 if n > 8 else 1)
        self.nav.update()          # 复位按钮回到新视图
        self.nav.push_current()
        self.canvas.draw_idle()

    def message(self, msg):
        self.clear()
        self.ax.text(0.5, 0.5, msg, ha="center", va="center", transform=self.ax.transAxes, color=C["text3"])
        self.ax.set_axis_off()
        self.canvas.draw_idle()


# ----------------------------------------------------------------------------- 后台任务
class _Worker(QObject):
    done = Signal(object)
    failed = Signal(str)
    progress = Signal(float, str)

    def __init__(self, fn, with_progress):
        super().__init__()
        self.fn = fn
        self.wp = with_progress

    def run(self):
        try:
            r = self.fn((lambda f, n="": self.progress.emit(float(f), str(n))) if self.wp else None) \
                if self.wp else self.fn()
            self.done.emit(r)
        except Exception as ex:          # noqa: BLE001
            self.failed.emit(f"{type(ex).__name__}: {ex}\n\n{traceback.format_exc()}")


class _Relay(QObject):
    """在界面线程中接收后台线程的信号（回调里会新建控件，必须在界面线程执行）"""
    def __init__(self, ok, bad, prog):
        super().__init__()
        self._ok, self._bad, self._prog = ok, bad, prog

    @Slot(object)
    def ok(self, r):
        self._ok(r)

    @Slot(str)
    def bad(self, m):
        self._bad(m)

    @Slot(float, str)
    def prog(self, f, n):
        self._prog(f, n)


_RUNNING = []


def run_task(parent, fn, on_done, busy_text=None, button_=None, progress=False, on_error=None):
    """在后台线程运行 fn（耗时计算不卡界面）；完成后在界面线程调用 on_done(result)。
    progress=True 时 fn 接收一个 progress(f, 文字) 回调。"""
    app = parent.window()
    status = getattr(app, "busy", None)
    th = QThread()
    wk = _Worker(fn, progress)
    wk.moveToThread(th)
    if button_ is not None:
        button_.setEnabled(False)
        button_._old = button_.text()
        button_.setText(busy_text or T("运行中…", "Running…"))
    if status:
        status(True, busy_text or T("运行中…", "Running…"))
    QApplication.setOverrideCursor(Qt.CursorShape.BusyCursor)

    def finish():
        QApplication.restoreOverrideCursor()
        if button_ is not None:
            button_.setEnabled(True)
            button_.setText(button_._old)
        if status:
            status(False)
        th.quit()

    def ok(r):
        finish()
        on_done(r)

    def bad(msg):
        finish()
        ERRORS.append(msg)
        if on_error:
            on_error(msg)
        elif not QUIET["v"]:
            dlg = QMessageBox(parent)
            dlg.setIcon(QMessageBox.Icon.Warning)
            dlg.setWindowTitle(T("出错了", "Error"))
            dlg.setText(msg.split("\n\n")[0])
            dlg.setDetailedText(msg)
            dlg.exec()
    def prog(f, n):
        if status:
            status(True, f"{busy_text or ''} {n} {f * 100:.0f}%")
    relay = _Relay(ok, bad, prog)            # 创建于界面线程 → 排队连接，回调在界面线程执行
    Q = Qt.ConnectionType.QueuedConnection
    wk.done.connect(relay.ok, Q)
    wk.failed.connect(relay.bad, Q)
    wk.progress.connect(relay.prog, Q)
    th.started.connect(wk.run)
    entry = (th, wk, relay)
    th.finished.connect(relay.deleteLater)
    th.finished.connect(lambda: _RUNNING.remove(entry) if entry in _RUNNING else None)
    _RUNNING.append(entry)
    th.start()


def wait_cursor(fn):
    """短任务：显示等待光标同步运行；出错时弹窗并返回 None"""
    QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
    try:
        return fn()
    except Exception as ex:        # noqa: BLE001
        QApplication.restoreOverrideCursor()
        ERRORS.append(f"{type(ex).__name__}: {ex}\n{traceback.format_exc()}")
        if QUIET["v"]:
            return None
        QMessageBox.warning(QApplication.activeWindow(), T("出错了", "Error"), f"{type(ex).__name__}: {ex}")
        return None
    finally:
        if QApplication.overrideCursor():
            QApplication.restoreOverrideCursor()


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
