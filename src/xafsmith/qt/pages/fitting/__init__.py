"""拟合：FEFF 路径、EXAFS 拟合、拟合历史、LCF、XANES。

拆分为子模块；这里再导出全部名字，旧的 `from .pages import fitting as ft; ft.FitPage` 用法不变。"""

from __future__ import annotations

from .guides import (  # noqa: F401
    FIT_GUIDE_EN,
    FIT_GUIDE_ZH,
    show_fit_guide,
)
from .quality import (  # noqa: F401
    quality_checks,
)
from .feff import (  # noqa: F401
    FeffPage,
)
from .fit_view import (  # noqa: F401
    FitView,
)
from .fit_page import (  # noqa: F401
    FitPage,
)
from .history import (  # noqa: F401
    HistoryPage,
)
from .lcf import (  # noqa: F401
    LCFPage,
)
from .xanes import (  # noqa: F401
    XanesPage,
)
