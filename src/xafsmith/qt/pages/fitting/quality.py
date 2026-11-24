"""拟合质量检查（界面文字；逻辑在 xafsmith.fitcheck，不含控件）。"""

from __future__ import annotations

from xafsmith.fitcheck import fit_checks
from ...widgets import T


def quality_checks(fit, dg=None):
    """[(True/False/None, 文字)]：True 通过，False 需注意，None 仅提示"""
    return [(c.ok, T(c.zh, c.en)) for c in fit_checks(fit, dg)]
