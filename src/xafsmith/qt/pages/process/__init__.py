"""数据处理：载入谱、质量检查与去毛刺、能量校准、归一化、χ(k) 与 FT、小波变换。

按标签拆分为子模块；这里再导出全部名字，旧的 `from .pages import process as pr; pr.NormPage` 用法不变。"""

from __future__ import annotations

from ._shared import (  # noqa: F401
    need_groups,
    norm_fields,
)
from .load import (  # noqa: F401
    LoadPage,
)
from .qc import (  # noqa: F401
    QCPage,
)
from .calib import (  # noqa: F401
    CalibPage,
)
from .norm import (  # noqa: F401
    NormPage,
)
from .chi import (  # noqa: F401
    ChiPage,
)
from .wavelet import (  # noqa: F401
    WT_HELP_EN,
    WT_HELP_ZH,
    WaveletPage,
    show_wavelet_guide,
)

from .._common import NOPHASE, rlabel  # noqa: F401
