"""快速拟合页（占位）：只拟合第一壳层并给出人话判定。完整界面在后续步骤实现。"""

from __future__ import annotations

from ... import widgets as W
from ...widgets import T, Banner, Card, Page


class QuickFitPage(Page):
    """快速拟合 / Quick fit。目前只是占位卡片。"""
    title_zh, title_en, icon_name = "快速拟合", "Quick fit", "fit"
    fill = True
    max_width = 100000

    def build(self):
        c = Card(T("快速拟合", "Quick fit"))
        c.add(W.label(T("快速拟合：只拟合第一壳层，下一版本步骤实现。",
                        "Quick fit: fits the first shell only; to be implemented in the next step."), "muted"))
        self.add(c)
        self.add(Banner("info", T("需要逐条设置路径与参数时，请切到上方的“精细拟合”。",
                                  "To set every path and parameter yourself, switch to “Detailed fit” above.")))
