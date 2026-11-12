"""可编辑表格（DataFrame 模型）。"""

from __future__ import annotations

import numpy as np
import pandas as pd
from PySide6.QtCore import QAbstractTableModel, QModelIndex, Qt, Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QAbstractItemView, QComboBox, QHeaderView, QStyledItemDelegate, QTableView
from ..theme import C


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
                    return f"{float(v):.10g}"          # 文本编辑：小数位不受限制（默认数字框只能输两位）
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
        if (role == Qt.ItemDataRole.TextAlignmentRole and o == Qt.Orientation.Horizontal
                and pd.api.types.is_numeric_dtype(self.df.iloc[:, s]) and not pd.api.types.is_bool_dtype(self.df.iloc[:, s])):
            return int(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)     # 数值列表头右对齐
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
                 stretch=True, max_height=420, click_edit=False, fit=False):
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
        trig = (QAbstractItemView.EditTrigger.DoubleClicked | QAbstractItemView.EditTrigger.SelectedClicked
                | QAbstractItemView.EditTrigger.EditKeyPressed | QAbstractItemView.EditTrigger.AnyKeyPressed)
        if click_edit:                       # 单击即编辑（参数、路径表）
            trig |= QAbstractItemView.EditTrigger.CurrentChanged
            self.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectItems)
        self.setEditTriggers(trig)
        self.setHorizontalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        self.setVerticalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        hh = self.horizontalHeader()
        hh.setHighlightSections(False)
        hh.setDefaultAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        self.resizeColumnsToContents()
        ch = self.fontMetrics().averageCharWidth()          # 列宽上下限按字符宽度（跟随字体与缩放）
        for i in range(self.m.columnCount()):
            self.setColumnWidth(i, min(max(self.columnWidth(i) + ch, 6 * ch), 36 * ch))
        if fit:                               # 所有列按宽度均分、不出现横向滚动条（紧凑的小表）
            hh.setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
            if self.m.df.shape[1] and not pd.api.types.is_numeric_dtype(self.m.df.iloc[:, -1]):
                hh.setSectionResizeMode(self.m.df.shape[1] - 1, QHeaderView.ResizeMode.ResizeToContents)   # 文字列完整显示
            self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        elif stretch:
            hh.setStretchLastSection(True)
        fh = self.fontMetrics().height()
        row_h = fh + (10 if fit else 12)                    # 行高 = 字高 + 内边距
        self.verticalHeader().setDefaultSectionSize(row_h)
        rows = len(self.m.df)
        self.setFixedHeight(height or min(max_height, (fh + 18) + row_h * max(rows, 1) + 6))
        self.m.dataChanged.connect(lambda *_: self.edited.emit())

    def df(self):
        return self.m.df.copy()

    def hide_cols(self, *cols):
        for c in cols:
            if c in self.m.df.columns:
                self.setColumnHidden(list(self.m.df.columns).index(c), True)
