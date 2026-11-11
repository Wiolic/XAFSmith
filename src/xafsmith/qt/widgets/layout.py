"""页面骨架与容器：卡片、页面基类、提示条、指标、标签页、折叠块。"""

from __future__ import annotations

from xafsmith import logs
import traceback
from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QScrollArea, QTabWidget, QToolButton, QVBoxLayout, QWidget
from ..theme import C, icon

from .core import ERRORS, T
from .basic import label
from .prose import code_block


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
    fill = False          # True：内容占满页面高度（左右分栏、各自滚动），不出现整页滚动条

    def __init__(self, app):
        super().__init__()
        self.app = app
        self.S = app.S
        self.setWidgetResizable(True)
        self.setFrameShape(QFrame.Shape.NoFrame)
        self._inner = QWidget()
        self._inner.setObjectName("page")
        outer = QHBoxLayout(self._inner)
        outer.setContentsMargins(*((28, 20, 28, 12) if self.fill else (40, 30, 40, 24)))
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
            logs.log.warning("qt.widgets.refresh 出错（已忽略或已提示）", exc_info=True)
            ERRORS.append(f"{type(self).__name__}: {ex}\n{traceback.format_exc()}")
            self.add(Banner("err", f"{type(ex).__name__}: {ex}"))
            self.add(code_block(traceback.format_exc()))
        if not self.fill:
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


class _FitTabs(QTabWidget):
    """高度只跟随当前页（QTabWidget 默认取所有页的最大值，会把较短的页撑出大片空白）"""
    def _cur(self, attr):
        w = self.currentWidget()
        h = getattr(w, attr)().height() if w is not None else 0
        return h + self.tabBar().sizeHint().height() + 8

    def minimumSizeHint(self):
        sz = super().minimumSizeHint()
        sz.setHeight(self._cur("minimumSizeHint"))
        return sz

    def sizeHint(self):
        sz = super().sizeHint()
        sz.setHeight(self._cur("sizeHint"))
        return sz


def tabs(*pages):
    """pages: [(标题, 控件), ...]；高度随当前页变化"""
    t = _FitTabs()
    t.setDocumentMode(True)
    for title, w in pages:
        t.addTab(w, title.replace("&", "&&"))
    t.currentChanged.connect(lambda _i: t.updateGeometry())
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
