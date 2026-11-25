"""“EXAFS 拟合”容器页：顶部 [快速拟合 | 精细拟合] 切换，下面堆叠两页。

精细拟合 = FitPage（Artemis 式路径表 + 参数表）；快速拟合 = QuickFitPage。
每次进入本页默认显示快速拟合；两页各自保留状态。"""

from __future__ import annotations

from PySide6.QtWidgets import QHBoxLayout, QStackedWidget, QVBoxLayout, QWidget

from ... import widgets as W
from ...widgets import T
from .fit_page import FitPage
from .quick_fit import QuickFitPage


class FitContainer(QWidget):
    title_zh, title_en, icon_name = "EXAFS 拟合", "EXAFS fitting", "fit"
    key = "fit"
    needs = ("groups", "feff")
    no_project = False
    hidden = False

    def __init__(self, app):
        super().__init__()
        self.app = app
        self.S = app.S
        self.quick_page = QuickFitPage(app)
        self.detailed_page = FitPage(app)
        v = QVBoxLayout(self)
        v.setContentsMargins(28, 14, 28, 0)
        v.setSpacing(6)
        bar = QHBoxLayout()
        self.seg = W.Segmented(["quick", "detailed"], "quick",
                               fmt=lambda x: T("快速拟合", "Quick fit") if x == "quick" else T("精细拟合", "Detailed fit"))
        self.seg.setToolTip(T("快速拟合：只拟合第一壳层，给出判定；精细拟合：逐条设置路径与参数（Artemis 式）",
                              "Quick fit: first shell only, with a verdict; Detailed fit: set every path and parameter (Artemis style)"))
        self.seg.changed.connect(self._switched)
        bar.addWidget(self.seg)
        bar.addStretch(1)
        v.addLayout(bar)
        self.stack = QStackedWidget()
        self.stack.addWidget(self.quick_page)
        self.stack.addWidget(self.detailed_page)
        v.addWidget(self.stack, 1)

    # ---- 切换
    @property
    def mode(self):
        return self.seg.value()

    @property
    def current_page(self):
        return self.detailed_page if self.mode == "detailed" else self.quick_page

    def show_quick(self):
        self._set("quick")

    def show_detailed(self):
        self._set("detailed")

    def _set(self, mode):
        self.seg.set(mode)
        self._switched(mode)

    def _switched(self, mode):
        cur = self.detailed_page if mode == "detailed" else self.quick_page
        other = self.quick_page if mode == "detailed" else self.detailed_page
        other.flush()
        self.stack.setCurrentWidget(cur)
        cur.on_show()

    # ---- 与主窗口 / 会话的接口（转交给当前页或精细拟合页）
    @property
    def state(self):
        """会话快照与草稿存的是精细拟合页的设置（键 "fit"）"""
        return self.detailed_page.state

    def on_show(self):
        self.show_quick()                 # 每次进入默认快速拟合

    def refresh(self):
        self.quick_page.refresh()
        self.detailed_page.refresh()

    def flush(self):
        self.quick_page.flush()
        self.detailed_page.flush()

    def dirty(self):
        return self.detailed_page.dirty()

    def save_changes(self):
        return self.detailed_page.save_changes()

    def confirm_leave(self):
        return self.detailed_page.confirm_leave()
