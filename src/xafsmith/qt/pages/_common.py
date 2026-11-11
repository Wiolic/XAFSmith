"""页面之间共享的常量与小函数（process 与 fitting 都用）。"""
from __future__ import annotations

from ..widgets import T

NOPHASE = "R (Å) — 未相移校正"


def rlabel():
    return T(NOPHASE, "R (Å) — not phase-corrected")
