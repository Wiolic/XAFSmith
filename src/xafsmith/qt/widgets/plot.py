"""matplotlib 图表控件。"""

from __future__ import annotations

from PySide6.QtWidgets import QHBoxLayout, QLabel, QSizePolicy, QToolButton, QVBoxLayout, QWidget
from ..theme import C, icon

from .core import T


class Plot(QWidget):
    """matplotlib 图：工具（平移 / 缩放 / 复位 / 存图）+ 鼠标坐标"""
    def __init__(self, height=380, nrows=1, ncols=1, sharex=False, height_ratios=None, width_ratios=None):
        super().__init__()
        from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg, NavigationToolbar2QT
        from matplotlib.figure import Figure
        self.fig = Figure(figsize=(8, height / 100), layout="constrained")
        self.canvas = FigureCanvasQTAgg(self.fig)
        self.canvas.setMinimumHeight(height)
        self.setMinimumHeight(height + 34)
        self.canvas.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.nav = NavigationToolbar2QT(self.canvas, self)
        self.nav.hide()
        kw = {}
        if height_ratios:
            kw["height_ratios"] = height_ratios
        if width_ratios:
            kw["width_ratios"] = width_ratios
        self.axes = self.fig.subplots(nrows, ncols, sharex=sharex, squeeze=False, gridspec_kw=kw or None).ravel()
        self.ax = self.axes[0]
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(2)
        bar = QHBoxLayout()
        bar.setSpacing(2)
        self.coord = QLabel("")
        self.coord.setObjectName("faint")
        bar.addWidget(self.coord)
        bar.addStretch(1)
        self._tools = {}
        for name, tip, fn in (("pan", T("平移", "Pan"), self.nav.pan), ("zoom", T("框选放大", "Zoom to box"), self.nav.zoom)):
            b = QToolButton()
            b.setIcon(icon(name, C["text3"], 16, on=C["accent_text"]))
            b.setToolTip(tip)
            b.setCheckable(True)
            b.clicked.connect(lambda _=False, f=fn, n=name: self._mode(f, n))
            bar.addWidget(b)
            self._tools[name] = b
        for name, tip, fn in (("zoomreset", T("复位", "Reset view"), self.nav.home),
                              ("download", T("保存图片", "Save image"), self.nav.save_figure)):
            b = QToolButton()
            b.setIcon(icon(name, C["text3"], 16))
            b.setToolTip(tip)
            b.clicked.connect(lambda _=False, f=fn: f())
            bar.addWidget(b)
        lay.addLayout(bar)
        lay.addWidget(self.canvas, 1)
        self.canvas.mpl_connect("motion_notify_event", self._move)

    def _mode(self, fn, name):
        fn()
        for n, b in self._tools.items():
            b.setChecked(n == name and b.isChecked())

    def _move(self, e):
        if e.inaxes and e.xdata is not None:
            self.coord.setText(f"x = {e.xdata:.4g}    y = {e.ydata:.4g}")
        else:
            self.coord.setText("")

    def clear(self):
        for a in self.axes:
            a.clear()

    def draw(self, legend=True):
        for a in self.axes:
            if legend and a.get_legend_handles_labels()[0]:
                n = len(a.get_legend_handles_labels()[0])
                a.legend(loc="best", fontsize=8 if n > 6 else 8.5, ncol=2 if n > 8 else 1)
        self.nav.update()          # 复位按钮回到新视图
        self.nav.push_current()
        self.canvas.draw_idle()

    def message(self, msg):
        self.clear()
        self.ax.text(0.5, 0.5, msg, ha="center", va="center", transform=self.ax.transAxes, color=C["text3"])
        self.ax.set_axis_off()
        self.canvas.draw_idle()
