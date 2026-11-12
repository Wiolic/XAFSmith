"""通用控件：页面骨架、卡片、表单字段、多选框、表格（可编辑）、图表、提示条、后台任务。

拆分为若干子模块；这里再导出全部名字，保证 `from xafsmith.qt import widgets as W` 的旧用法不变。"""

from __future__ import annotations

from .core import (  # noqa: F401
    ERRORS,
    LANG,
    QUIET,
    T,
    en,
    find,
    tag,
)
from .basic import (  # noqa: F401
    button,
    field,
    fields,
    hbox,
    hline,
    label,
    link,
    vbox,
)
from .prose import (  # noqa: F401
    _INFO,
    retarget_images,
    ask,
    code_block,
    copy_button,
    copy_to_clipboard,
    info_window,
    prose_browser,
    prose_style,
)
from .inputs import (  # noqa: F401
    debounced,
    link_range,
    set_invalid,
    MultiSelect,
    OrderList,
    Segmented,
    check,
    combo,
    inum,
    num,
    text,
)
from .layout import (  # noqa: F401
    Banner,
    Card,
    Metric,
    Page,
    _clear_layout,
    collapsible,
    metrics,
    pill,
    tabs,
)
from .table import (  # noqa: F401
    DFModel,
    Table,
    _ChoiceDelegate,
)
from .plot import (  # noqa: F401
    Plot,
)
from .tasks import (  # noqa: F401
    _ACTIVE,
    _RUNNING,
    _Relay,
    _Worker,
    _show_status,
    bind_task,
    cancel_all_tasks,
    refresh_status,
    run_task,
    running_count,
    task_running,
    shutdown_tasks,
    wait_cursor,
)
from .system import (  # noqa: F401
    Toaster,
    open_folder,
    save_file_dialog,
    toast,
)

from xafsmith import logs  # noqa: F401
import traceback  # noqa: F401
import numpy as np  # noqa: F401
import pandas as pd  # noqa: F401
from PySide6.QtCore import QAbstractTableModel, QModelIndex, QObject, QSize, Qt, QThread, QTimer, Signal, Slot  # noqa: F401
from PySide6.QtGui import QColor, QFont, QGuiApplication  # noqa: F401
from PySide6.QtWidgets import (QAbstractItemView, QApplication, QCheckBox, QComboBox, QDoubleSpinBox, QFrame, QGridLayout, QHBoxLayout, QHeaderView, QLabel, QLineEdit, QListWidget, QListWidgetItem, QMessageBox, QPlainTextEdit, QPushButton, QScrollArea, QSizePolicy, QSpinBox, QStyledItemDelegate, QTableView, QTabWidget, QTextBrowser, QToolButton, QVBoxLayout, QWidget)  # noqa: F401
from .. import theme  # noqa: F401
from ..theme import C, icon  # noqa: F401
from xafsmith.tasks import Cancelled, TaskHandle  # noqa: F401
