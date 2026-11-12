"""列映射向导：预览文件的列 → 指定能量 / I0 / It / If / μ 列 → 试读 → 保存为项目的格式模板（xafsmith.json "formats"）。

后台逻辑在 readers/wizard.py（可单独测试）；这里只有界面。保存后的模板名会出现在“载入谱 → 格式”下拉框，
也可以写进 meta.csv 的 format 列。
"""
from __future__ import annotations

from pathlib import Path

from .theme import SP
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QDialog, QHeaderView, QTableWidget, QTableWidgetItem, QVBoxLayout

from xafsmith import logs
from xafsmith.readers import wizard as wz
from xafsmith.readers.base import ReadError
from . import widgets as W
from .widgets import T, Banner

ROLE_TITLES = {
    "energy": ("能量列（必选）", "Energy column (required)"),
    "i0": ("I0 列", "I0 column"),
    "it": ("It（透射信号）列", "It (transmitted) column"),
    "if": ("If（荧光信号）列", "If (fluorescence) column"),
    "mu": ("μ 列（可选）", "μ column (optional)"),
}


class ColumnWizard(QDialog):
    """用法：ColumnWizard(parent, 文件路径).exec()；保存成功后 .saved 为模板名，否则为 None。"""

    def __init__(self, parent, path):
        super().__init__(parent)
        self.path, self.saved, self.tpl = Path(path), None, None
        self.setWindowTitle(T("列映射向导", "Column mapping wizard"))
        self.resize(820, 700)
        v = QVBoxLayout(self)
        v.setContentsMargins(SP['xl'], SP['lg'], SP['xl'], SP['lg'])
        v.setSpacing(10)
        h = W.label(T("列映射向导", "Column mapping wizard"), "h1")
        v.addWidget(h)
        try:
            self.info = wz.inspect_file(self.path)
        except ReadError as ex:
            v.addWidget(Banner("err", ex.en if W.en() else ex.zh))
            v.addWidget(W.hbox(None, W.button(T("关闭", "Close"), slot=self.reject)))
            self.info = None
            return
        info = self.info
        names = info["names"]
        self.cols = [f"{i}: {n}" for i, n in enumerate(names)] if names else [f"{i}" for i in range(info["ncols"])]
        v.addWidget(W.label(T(f"文件：{self.path.name} · {info['ncols']} 列 · {info['ntotal']} 行数据（以下是前几行）",
                              f"File: {self.path.name} · {info['ncols']} columns · {info['ntotal']} data rows (first rows below)"),
                            "muted"))
        if not names:
            v.addWidget(Banner("warn", T("文件没有可识别的列名行，只能按列号（从 0 开始）指定。",
                                         "No column-name line was found; columns can only be chosen by number (from 0).")))
        tb = QTableWidget(len(info["rows"]), info["ncols"])
        tb.setHorizontalHeaderLabels(self.cols)
        tb.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        for r, row in enumerate(info["rows"]):
            for c, val in enumerate(row):
                it = QTableWidgetItem(f"{val:.6g}")
                it.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                tb.setItem(r, c, it)
        tb.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        tb.setMaximumHeight(230)
        v.addWidget(tb)

        none = T("— 无 —", "— none —")
        opts = [None] + list(range(info["ncols"]))
        fmt = lambda i: none if i is None else self.cols[i]       # noqa: E731
        auto = info["auto"]
        self.cb = {}
        items = []
        for role in ("energy", "i0", "it", "mu"):
            guess = (auto.get(role) or [None])[0]
            self.cb[role] = W.combo(opts, guess, fmt=fmt)
            items.append((T(*ROLE_TITLES[role]), self.cb[role]))
        self.if_txt = W.text(",".join(str(i) for i in auto.get("if", [])), T("如 3 或 3,4（多通道求和）", "e.g. 3 or 3,4 (channels are summed)"))
        items.insert(3, (T("If（荧光信号）列号，可多个", "If (fluorescence) column no., several allowed"), self.if_txt))
        self.mode = W.combo(["auto", "trans", "fluo"], "auto",
                            fmt=lambda m: {"auto": T("自动（按已指定的列）", "Auto (from mapped columns)"),
                                           "trans": T("透射 μ = ln(I0/It)", "Transmission μ = ln(I0/It)"),
                                           "fluo": T("荧光 μ = If/I0", "Fluorescence μ = If/I0")}[m])
        items.append((T("模式", "Mode"), self.mode))
        v.addWidget(W.fields(*items, cols=3))
        for w_ in info["auto_warnings"]:
            v.addWidget(W.label("• " + (w_.split(" / ")[-1] if W.en() else w_.split(" / ")[0]), "faint"))
        v.addWidget(W.label(T("列名会按名称保存（换文件、列顺序变了也能用）；重名或没有列名的列按列号保存。"
                              "μ 一律由通道计算；只有通道不全才使用 μ 列。",
                              "Columns are saved by name (still valid if the order changes); duplicated or unnamed columns are saved by number. "
                              "μ is always computed from the channels; the μ column is only used if channels are missing."), "faint"))
        self.result = W.label("")
        v.addWidget(self.result)
        self.name = W.text("", T("模板名，如 BL14W1_fluo", "Template name, e.g. BL14W1_fluo"))
        v.addWidget(W.hbox(W.button(T("试读", "Test read"), slot=self.test),
                           self.name, W.button(T("保存为模板", "Save as template"), primary=True, slot=self.save),
                           None, W.button(T("关闭", "Close"), slot=self.reject), stretch_last=False))

    # --------------------------------------------------------------------------
    def _assignment(self):
        a = {r: self.cb[r].value() for r in ("energy", "i0", "it", "mu")}
        txt = self.if_txt.text().replace("，", ",").replace(" ", "")
        if txt:
            try:
                a["if"] = [int(x) for x in txt.split(",") if x != ""]
            except ValueError:
                raise ReadError("If 列号应是整数，多个用逗号隔开", "If column numbers must be integers separated by commas")
        return a

    def _template(self):
        m = self.mode.value()
        return wz.build_template(self.info["names"], self._assignment(), None if m == "auto" else m)

    def _show(self, kind, zh, en):
        self.result.setText(("✓ " if kind == "ok" else "✗ ") + T(zh, en))
        self.result.setObjectName("" if kind == "ok" else "err")
        self.result.style().unpolish(self.result)
        self.result.style().polish(self.result)

    def test(self):
        try:
            self.tpl = self._template()
            s = wz.try_read(self.path, self.tpl)
        except ReadError as ex:
            self._show("err", ex.zh, ex.en)
            return False
        except Exception as ex:           # noqa: BLE001
            logs.log.warning("colwizard.test 出错", exc_info=True)
            self._show("err", f"试读失败：{ex}", f"Test read failed: {ex}")
            return False
        w = ("；" + "；".join(s["warnings"])) if s["warnings"] else ""
        self._show("ok", f"{s['npts']} 点 · {s['e_min']:.1f}–{s['e_max']:.1f} eV · 模式 {s['mode']} · 吸收边 {s['element']} {s['edge']}"
                         f" · μ 范围 {s['mu_min']:.3g}–{s['mu_max']:.3g}（请核对）{w}",
                   f"{s['npts']} points · {s['e_min']:.1f}–{s['e_max']:.1f} eV · mode {s['mode']} · edge {s['element']} {s['edge']}"
                   f" · μ range {s['mu_min']:.3g}–{s['mu_max']:.3g} (please check){w}")
        return True

    def save(self):
        if not self.test():
            return
        from . import state
        try:
            cfg = wz.add_template(state.load_cfg(), self.name.text(), self.tpl)
            state.save_cfg(cfg)
        except ReadError as ex:
            self._show("err", ex.zh, ex.en)
            return
        except Exception as ex:           # noqa: BLE001
            logs.log.warning("colwizard.save 出错", exc_info=True)
            self._show("err", f"保存失败：{ex}", f"Save failed: {ex}")
            return
        self.saved = self.name.text().strip()
        self.accept()
