"""错误框：三段（发生了什么 / 你可以怎么做 / 联系），英文堆栈只在“详细信息”里。

文字由 xafsmith.errors.explain 给出；后台任务的默认报错与未捕获异常的错误框共用本对话框。
Error dialog in three parts (what happened / what you can do / contact); the English stack is only under “Details”.
"""

from __future__ import annotations

from PySide6.QtWidgets import QApplication, QDialog, QDialogButtonBox, QFileDialog, QLabel, QPlainTextEdit, QVBoxLayout

from xafsmith import errors, logs
from . import widgets as W
from .widgets import T


class ErrorDialog(QDialog):
    def __init__(self, parent, exc, detail=None):
        super().__init__(parent)
        lang = W.LANG["v"]
        self.what, self.todo = errors.explain(exc, lang)
        self.detail = str(detail if detail is not None else exc)
        self.setWindowTitle(T("出错了", "Something went wrong"))
        lay = QVBoxLayout(self)
        lay.setSpacing(8)
        lay.addWidget(self._head(T("发生了什么", "What happened")))
        lay.addWidget(self._body(self.what))
        lay.addWidget(self._head(T("你可以怎么做", "What you can do")))
        lay.addWidget(self._body(self.todo))
        lay.addWidget(self._head(T("联系", "Contact")))
        self.contact = QLabel(T(f'解决不了？到 <a href="{errors.ISSUES_URL}">GitHub Issues</a> 反馈，并附上诊断包（不含原始数据与谱）。',
                                f'Still stuck? Report it on <a href="{errors.ISSUES_URL}">GitHub Issues</a> and attach the diagnostics bundle '
                                "(it contains no raw data or spectra)."))
        self.contact.setOpenExternalLinks(True)
        self.contact.setWordWrap(True)
        lay.addWidget(self.contact)
        self.status = QLabel("")
        self.status.setWordWrap(True)
        lay.addWidget(self.status)
        self.details = QPlainTextEdit(self.detail)
        self.details.setReadOnly(True)
        self.details.setMinimumHeight(160)
        lay.addWidget(W.collapsible(T("详细信息", "Details"), self.details, expanded=False))
        bb = QDialogButtonBox()
        self.b_diag = bb.addButton(T("导出诊断包…", "Export diagnostics…"), QDialogButtonBox.ButtonRole.ActionRole)
        self.b_copy = bb.addButton(T("复制详细信息", "Copy details"), QDialogButtonBox.ButtonRole.ActionRole)
        close = bb.addButton(T("关闭", "Close"), QDialogButtonBox.ButtonRole.AcceptRole)
        self.b_diag.clicked.connect(self.export_diagnostics)
        self.b_copy.clicked.connect(lambda: QApplication.clipboard().setText(self.detail))
        close.clicked.connect(self.accept)
        lay.addWidget(bb)
        self.resize(560, 320)

    @staticmethod
    def _head(t):
        lb = QLabel(f"<b>{t}</b>")
        return lb

    @staticmethod
    def _body(t):
        lb = QLabel(t)
        lb.setWordWrap(True)
        lb.setTextInteractionFlags(lb.textInteractionFlags() | W.Qt.TextInteractionFlag.TextSelectableByMouse)
        return lb

    def export_diagnostics(self, dest=None):
        """调用已有的 logs.diagnostics_zip；dest 缺省时弹出“另存为”"""
        from datetime import datetime
        from pathlib import Path
        if not dest:
            dest, _ = QFileDialog.getSaveFileName(self, T("保存诊断包", "Save diagnostics"),
                                                  str(Path.home() / f"xafsmith_diag_{datetime.now():%Y%m%d_%H%M%S}.zip"), "ZIP (*.zip)")
        if not dest:
            return None
        try:
            logs.diagnostics_zip(dest)
        except Exception as ex:      # noqa: BLE001
            logs.log.warning("导出诊断包失败", exc_info=True)
            self.status.setText(T(f"导出失败：{ex}", f"Export failed: {ex}"))
            return None
        self.status.setText(T(f"诊断包已保存：{dest}", f"Diagnostics saved: {dest}"))
        return dest


def show_error(parent, exc, detail=None):
    """弹出错误框（模态）；exc 是异常对象或后台任务带回的文字"""
    dlg = ErrorDialog(parent, exc, detail)
    dlg.exec()
    return dlg
