"""“σ² 模型…”对话框（B6）：把路径的 σ² 写成 Debye / Einstein 温度模型，并建好所缺的 θ、静态项参数。

只改路径表的 sigma2 单元格与参数表；计算在 xafsmith.sigma2 与 larch（sigma2_debye / sigma2_eins），这里不做数值。
缺省值（设计 6.4）：θ 参数名 thD<壳层号> / thE<壳层号>，θ 范围 50–2000 K，初值 = 有温度且当前 σ² 是数字时由
theta_from_sigma2 反算，否则 300 K；静态项参数 ss0_<壳层号>，初值 0，不设下限。
"""
from __future__ import annotations

import re

from PySide6.QtWidgets import QDialog, QDialogButtonBox, QVBoxLayout

from ... import widgets as W
from ...widgets import T

KINDS = ["free", "debye", "einstein"]
THETA_DEFAULT = (300.0, 50.0, 2000.0)          # 初值（无法反算时）、min、max（K）


def kind_label(k):
    return {"free": T("自由（每个温度一个 σ²）", "Free (one σ² per temperature)"),
            "debye": T("Debye（相关 Debye 模型）", "Debye (correlated Debye)"),
            "einstein": T("Einstein", "Einstein")}[k]


def shell_number(row, fallback=1):
    """从路径行的 deltar / sigma2 里的 dr<N> / ss<N> 取壳层号；取不到用 fallback。"""
    for col in ("sigma2", "deltar"):
        m = re.search(r"(?:ss0_|ss|dr|thD|thE)(\d+)", str(row.get(col, "")))
        if m:
            return int(m.group(1))
    return fallback


def theta_name(kind, shell):
    return f"th{'D' if kind == 'debye' else 'E'}{shell}"


def static_name(shell):
    return f"ss0_{shell}"


def sigma2_expression(kind, theta, static=None):
    """kind=free → None；否则 'sigma2_debye(tempK, thD1) + ss0_1'。"""
    if kind == "free":
        return None
    fn = "sigma2_debye" if kind == "debye" else "sigma2_eins"
    return f"{fn}(tempK, {theta})" + (f" + {static}" if static else "")


def current_sigma2_value(expr, partab):
    """路径 sigma2 单元格里当前的数值：数字字面量，或参数表里的一个参数名；否则 None。"""
    s = str(expr).strip()
    try:
        return float(s)
    except ValueError:
        pass
    if partab is not None and len(partab) and s in set(partab.name):
        try:
            return float(partab[partab.name == s].iloc[0]["value"])
        except (TypeError, ValueError):
            return None
    return None


def initial_theta(kind, file, temperature, sigma2_now):
    """初值：有温度且当前 σ² 是正数 → theta_from_sigma2；反算失败 / 条件不满足 → 300 K。"""
    if kind == "free" or not temperature or not sigma2_now or sigma2_now <= 0:
        return THETA_DEFAULT[0]
    try:
        from xafsmith import paths
        from xafsmith.sigma2 import theta_from_sigma2
        f = paths.resolve(file)
        th = theta_from_sigma2(f, kind, float(temperature), float(sigma2_now))
    except Exception:                      # 文件读不了等：用缺省值，不打断
        from xafsmith import logs
        logs.log.debug("σ² 模型对话框：反算 θ 失败", exc_info=True)
        th = None
    return THETA_DEFAULT[0] if th is None else th


class Sigma2Dialog(QDialog):
    """参数：row（路径表当前行 dict）、temperature（该数据集温度，可为 None）、sigma2_now（当前 σ² 数值或 None）、
    multi（联合拟合模式：显示“应用到所有数据集的同一壳层”）。结果见 spec()。"""

    def __init__(self, parent, row, temperature=None, sigma2_now=None, multi=False, kind="debye"):
        super().__init__(parent)
        self.setWindowTitle(T("σ² 模型", "σ² model"))
        self.row, self.temperature, self.sigma2_now = row, temperature, sigma2_now
        self.shell = shell_number(row)
        v = QVBoxLayout(self)
        v.addWidget(W.label(T(f"路径 {row.get('label', '')}：把 σ² 写成温度的函数，多个温度共用一个 θ（至少 2–3 个温度才有意义）。",
                              f"Path {row.get('label', '')}: write σ² as a function of temperature with one θ shared by all "
                              "temperatures (use at least 2–3 temperatures)."), "faint"))
        self.kind = W.combo(KINDS, kind, fmt=kind_label)
        self.name = W.text("")
        self.th0 = W.num(THETA_DEFAULT[0], 1, 5000, 10, 2)
        self.thmin = W.num(THETA_DEFAULT[1], 1, 5000, 10, 1)
        self.thmax = W.num(THETA_DEFAULT[2], 1, 10000, 10, 1)
        self.static = W.check(T("加静态无序项（与温度无关）", "Add a temperature-independent static disorder term"), False)
        self.apply_all = W.check(T("应用到所有数据集的同一壳层", "Apply to the same shell of all datasets"), True)
        v.addWidget(W.fields((T("模型", "Model"), self.kind), (T("θ 参数名", "θ parameter name"), self.name), cols=2))
        v.addWidget(W.fields((T("θ 初值 (K)", "θ start (K)"), self.th0), (T("θ 下限 (K)", "θ min (K)"), self.thmin),
                             (T("θ 上限 (K)", "θ max (K)"), self.thmax), cols=3))
        v.addWidget(self.static)
        self.note = W.label("", "faint")
        v.addWidget(self.note)
        if multi:
            v.addWidget(self.apply_all)
        self.apply_all.setVisible(bool(multi))
        bb = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        bb.button(QDialogButtonBox.StandardButton.Ok).setText(T("确定", "OK"))
        bb.button(QDialogButtonBox.StandardButton.Cancel).setText(T("取消", "Cancel"))
        bb.accepted.connect(self.accept)
        bb.rejected.connect(self.reject)
        v.addWidget(bb)
        self._auto_name = ""
        self.kind.currentIndexChanged.connect(lambda *_: self._on_kind())
        self._on_kind()

    def _on_kind(self):
        k = self.kind.value()
        for w_ in (self.name, self.th0, self.thmin, self.thmax, self.static):
            w_.setEnabled(k != "free")
        if k == "free":
            self.note.setText(T(f"改回自由 σ²：单元格写成 ss{self.shell}（不再被引用的 θ 参数会从参数表中消失）。",
                                f"Back to a free σ²: the cell becomes ss{self.shell} (θ parameters no longer referenced disappear from the table)."))
            return
        if not self.name.text().strip() or self.name.text() == self._auto_name:
            self._auto_name = theta_name(k, self.shell)
            self.name.setText(self._auto_name)
        th = initial_theta(k, self.row.get("file", ""), self.temperature, self.sigma2_now)
        self.th0.setValue(th)
        if self.temperature:
            self.note.setText(T(f"温度 {self.temperature:g} K；θ 初值" + ("由当前 σ² 反算。" if th != THETA_DEFAULT[0] else "取缺省 300 K。"),
                                f"Temperature {self.temperature:g} K; θ start " + ("back-calculated from the current σ²."
                                                                                  if th != THETA_DEFAULT[0] else "defaults to 300 K.")))
        else:
            self.note.setText(T("该数据集还没有填温度：tempK 需要温度，请先在路径表上方填写“温度 (K)”，否则无法拟合。",
                                "This dataset has no temperature yet: tempK needs it, fill in “Temperature (K)” above the path "
                                "table first, otherwise the fit cannot run."))

    def spec(self):
        """→ dict(kind, expr, params={名: dict(value, vary, min, max)}, apply_all)；free：expr = ss<壳层号>，params 空。"""
        k = self.kind.value()
        if k == "free":
            return dict(kind=k, expr=f"ss{self.shell}", params={}, apply_all=self.apply_all.isChecked())
        th = self.name.text().strip() or theta_name(k, self.shell)
        st = static_name(self.shell) if self.static.isChecked() else None
        params = {th: dict(value=self.th0.value(), vary=True, min=self.thmin.value(), max=self.thmax.value())}
        if st:
            params[st] = dict(value=0.0, vary=True, min=None, max=None)
        return dict(kind=k, expr=sigma2_expression(k, th, st), params=params, apply_all=self.apply_all.isChecked())
