"""页面骨架与容器：卡片、页面基类、提示条、指标、标签页、折叠块。"""

from __future__ import annotations

from xafsmith import logs
import traceback
from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (QFrame, QHBoxLayout, QLabel, QMessageBox, QScrollArea, QTabWidget, QToolButton,
                               QVBoxLayout, QWidget)
from ..theme import C, SP, icon

from .core import ERRORS, QUIET, T
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
        self._keys = None          # 上次建好时的 (data_key, par_key)
        self.redraw = None         # build() 里可设为本页的 update 函数：只有处理参数变了时调用它而不重建
        self._debounced = []       # W.debounced 登记的函数；切页前 flush
        self._notice = None        # (kind, title, lines)：页顶提示条，重建后仍显示

    def title(self):
        return T(self.title_zh, self.title_en)

    def header(self, subtitle=None, actions=()):
        h = QHBoxLayout()
        t = QLabel(self.title())
        t.setObjectName("h1")
        if type(self).__name__ == "HomePage":
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

    def notice(self, kind, title, lines=(), key=None):
        """页顶提示条（带 ×）：持续性错误 / 汇总多条错误。lines 超过 5 条折叠。
        原地更新、不重建页面（可在 build()/update() 里直接调用）；下次 notice 或点 × 前一直显示，重建后仍在。"""
        self._notice = (kind, title, list(lines), key)
        self._fill_notice()

    def clear_notice(self, key=None):
        """清除提示条；给 key 时只清除同 key 的那条（避免清掉别处发出的提示）"""
        if self._notice and (key is None or self._notice[3] == key):
            self._notice = None
            self._fill_notice()

    def _fill_notice(self):
        slot = getattr(self, "_slot", None)
        if slot is None:
            return
        _clear_layout(slot.layout())
        if self._notice:
            slot.layout().addWidget(self._notice_banner())

    def _notice_banner(self):
        kind, title, lines, _k = self._notice
        shown = lines[:5]
        txt = title + (chr(10) + chr(10).join(shown) if shown else "")
        if len(lines) > 5:
            txt += chr(10) + T(f"…另 {len(lines) - 5} 条（详见日志）", f"… and {len(lines) - 5} more (see the log)")
        b = Banner(kind, txt)
        x = QToolButton()
        x.setText("×")
        x.setAutoRaise(True)
        x.setCursor(Qt.CursorShape.PointingHandCursor)
        x.setToolTip(T("关闭", "Dismiss"))
        x.clicked.connect(lambda *_: self.clear_notice())
        b.layout().addWidget(x, 0, Qt.AlignmentFlag.AlignTop)
        return b

    # ---- 未保存的修改（页面可覆盖）
    def dirty(self):
        """返回“有哪些未保存修改”的一句话；没有则 None"""
        return None

    def save_changes(self):
        return True

    def confirm_leave(self):
        """有未保存修改时询问：保存 / 放弃 / 取消。返回 True = 可以离开（已保存或放弃）"""
        d = self.dirty()
        if not d or QUIET["v"]:
            return True
        box = QMessageBox(self.window())
        box.setIcon(QMessageBox.Icon.Question)
        box.setWindowTitle(T("有未保存的修改", "Unsaved changes"))
        box.setText(T(f"{d}，要保存吗？", f"{d}. Save them?"))
        b_save = box.addButton(T("保存", "Save"), QMessageBox.ButtonRole.AcceptRole)
        b_disc = box.addButton(T("放弃", "Discard"), QMessageBox.ButtonRole.DestructiveRole)
        box.addButton(T("取消", "Cancel"), QMessageBox.ButtonRole.RejectRole)
        box.exec()
        c = box.clickedButton()
        if c is b_save:
            return bool(self.save_changes())
        if c is b_disc:
            self.discard_changes()
            return True
        return False

    def discard_changes(self):
        self.refresh()

    # ---- 版本判断
    def stale_extra(self):
        """页面可覆盖：返回额外参与“是否需要重建”比较的值"""
        return ()

    def _cur_keys(self):
        return (self.S.data_key(), self.stale_extra()), self.S.par_key()

    def ack(self):
        """页面自己改了数据并已更新自己的显示后调用：回来时不再重建"""
        self._keys = self._cur_keys()

    def flush(self):
        """立即执行挂起的防抖重画（切页、保存前调用）"""
        for c in list(self._debounced):
            c.flush()

    def refresh(self):
        y = self.verticalScrollBar().value()
        self._debounced = []
        self.clear()
        self._slot = QWidget()
        QVBoxLayout(self._slot).setContentsMargins(0, 0, 0, 0)
        self.body.addWidget(self._slot)
        self._fill_notice()
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
        self._keys = self._cur_keys()
        QTimer.singleShot(0, lambda: self.verticalScrollBar().setValue(y))

    def build(self):
        pass

    def on_show(self):
        """切到本页：数据变了才重建；只有处理参数变了就只重画；都没变什么也不做"""
        if not self._built or self._keys is None:
            self.refresh()
            return
        data, par = self._cur_keys()
        if data != self._keys[0]:
            self.refresh()
        elif par != self._keys[1]:
            if self.redraw is not None:
                from .tasks import wait_cursor
                wait_cursor(self.redraw)
                self._keys = (data, par)
            else:
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
        lay.setContentsMargins(SP['md'], SP['sm'], SP['md'], SP['sm'])
        lay.setSpacing(10)
        col = {"info": C["text2"], "ok": C["ok"], "warn": C["warn"], "err": C["err"]}[kind]
        ic = QLabel()
        ic.setPixmap(icon(self.ICON[kind], col, 16, 1.9).pixmap(16, 16))
        ic.setFixedWidth(18)
        ic.setAlignment(Qt.AlignmentFlag.AlignTop)
        lay.addWidget(ic)
        lay.addWidget(label(text_, rich=rich), 1)


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
    lb.setProperty("kind", kind)
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

    def heightForWidth(self, width):
        # 页里有自动换行的文字时，布局按 heightForWidth 取高度；QTabWidget 默认取所有页的最大值，这里也只看当前页
        w = self.currentWidget()
        if w is None:
            return super().heightForWidth(width)
        h = w.heightForWidth(width) if w.hasHeightForWidth() else -1
        h = max(h, w.minimumSizeHint().height()) if h >= 0 else w.sizeHint().height()
        return h + self.tabBar().sizeHint().height() + 8


def tabs(*pages, state=None, key="tab"):
    """pages: [(标题, 控件), ...]；高度随当前页变化。给 state（页面的 self.state）时记住当前标签，重建后恢复"""
    t = _FitTabs()
    t.setDocumentMode(True)
    for title, w in pages:
        t.addTab(w, title.replace("&", "&&"))
    if state is not None:
        i = state.get(key, 0)
        if isinstance(i, int) and 0 <= i < t.count():
            t.setCurrentIndex(i)
        t.currentChanged.connect(lambda i_: state.__setitem__(key, i_))
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
    b.setObjectName("collapse")
    b.setCursor(Qt.CursorShape.PointingHandCursor)

    def upd(on):
        b.setArrowType(Qt.ArrowType.DownArrow if on else Qt.ArrowType.RightArrow)
        content.setVisible(on)
    b.toggled.connect(upd)
    lay.addWidget(b)
    lay.addWidget(content)
    upd(expanded)
    return w
