"""XAFSmith 桌面程序（PySide6）。

启动：xafsmith gui [--project <项目目录>]，或双击桌面图标。
布局：左侧栏（品牌与署名、打开项目、按使用流程分组的导航、当前项目与语言），右侧页面；
页面底部始终显示免责声明（点击查看全文与引用方式）。
"""
from __future__ import annotations

import os
import sys
import threading
from pathlib import Path

from PySide6.QtCore import QSize, Qt, QTimer, Signal
from PySide6.QtGui import QIcon, QPixmap
from PySide6.QtWidgets import (QApplication, QButtonGroup, QDialog, QFrame, QHBoxLayout, QLabel, QMainWindow,
                               QProgressBar, QPushButton, QStackedWidget, QTextBrowser, QVBoxLayout, QWidget)

from xafsmith import paths
from . import theme, widgets as W
from .theme import C, icon
from .state import State, is_project, remember
from .widgets import T

ASSETS = Path(__file__).resolve().parent.parent / "assets"
CREDIT_NAMES = ("Eggy", "Claude Opus 5.5")


def page_specs():
    """(键, 类) 按使用流程分组；None 表示组间空隙"""
    from .pages import project as pj, process as pr, fitting as ft, output as op
    return [
        ("home", pj.HomePage), ("data", pj.DataPage), ("batch", pj.BatchPage),
        None,
        ("load", pr.LoadPage), ("qc", pr.QCPage), ("calib", pr.CalibPage), ("norm", pr.NormPage),
        ("chi", pr.ChiPage), ("wavelet", pr.WaveletPage),
        None,
        ("feff", ft.FeffPage), ("fit", ft.FitPage), ("history", ft.HistoryPage), ("lcf", ft.LCFPage),
        ("xanes", ft.XanesPage),
        None,
        ("summary", op.SummaryPage), ("pubfig", op.PubFigPage), ("si", op.SIPage),
        None,
        ("planner", op.PlannerPage), ("agent", op.AgentPage), ("help", op.HelpPage),
    ]


class MainWindow(QMainWindow):
    update_found = Signal(dict)

    def __init__(self, S: State):
        super().__init__()
        self.S = S
        self.setWindowTitle("XAFSmith")
        if (ASSETS / "xafsmith.ico").exists():
            self.setWindowIcon(QIcon(str(ASSETS / "xafsmith.ico")))
        self.resize(1440, 920)
        self.setMinimumSize(1060, 680)
        self.pages = {}
        self.nav = {}
        self._update = {}
        self._build()
        self.S.changed.connect(self._state_changed)
        self.update_found.connect(self._show_update)

    # ------------------------------------------------------------------ 布局
    def _build(self):
        root = QWidget()
        root.setObjectName("root")
        h = QHBoxLayout(root)
        h.setContentsMargins(0, 0, 0, 0)
        h.setSpacing(0)
        h.addWidget(self._sidebar())
        main = QWidget()
        main.setObjectName("main")
        v = QVBoxLayout(main)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(0)
        self.bar = QProgressBar()
        self.bar.setRange(0, 0)
        self.bar.setTextVisible(False)
        self.bar.setFixedHeight(3)
        self.bar.setStyleSheet(f"QProgressBar{{background:transparent;border:none;max-height:3px;}}"
                               f"QProgressBar::chunk{{background:{C['accent']};}}")
        self.bar.hide()
        v.addWidget(self.bar)
        self.stack = QStackedWidget()
        v.addWidget(self.stack, 1)
        v.addWidget(self._footer())
        h.addWidget(main, 1)
        self.setCentralWidget(root)
        for spec in page_specs():
            if spec is None:
                continue
            key, cls = spec
            p = cls(self)
            self.pages[key] = p
            self.stack.addWidget(p)
        self._toast = QLabel(self)
        self._toast.hide()
        self.go("home" if not is_project() else self.S.extra.get("page", "home"))

    def _sidebar(self):
        side = QWidget()
        side.setObjectName("sidebar")
        side.setFixedWidth(250)
        v = QVBoxLayout(side)
        v.setContentsMargins(14, 16, 14, 14)
        v.setSpacing(2)
        # 品牌 + 署名（始终可见）
        brand = QHBoxLayout()
        brand.setSpacing(10)
        logo = QLabel()
        pm = QPixmap(str(ASSETS / "xafsmith.png"))
        logo.setPixmap(pm.scaled(38, 38, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
        brand.addWidget(logo)
        bt = QVBoxLayout()
        bt.setSpacing(0)
        name = QLabel("XAFSmith")
        name.setObjectName("brand")
        bt.addWidget(name)
        cr = QLabel(f'<span style="color:{C["text3"]}">Developed by</span><br/>'
                    f'<b style="color:{C["accent_text"]}">{CREDIT_NAMES[0]}</b>'
                    f'<span style="color:{C["text3"]}"> &amp; </span>'
                    f'<b style="color:{C["accent_text"]}">{CREDIT_NAMES[1]}</b>')
        cr.setObjectName("credit")
        cr.setToolTip("Developed by Eggy & Claude Opus 5.5 (Anthropic)")
        cr.setWordWrap(False)
        bt.addWidget(cr)
        brand.addLayout(bt, 1)
        head = QWidget()                      # 品牌与署名：固定高度，任何窗口尺寸下都完整显示
        head.setLayout(brand)
        head.setFixedHeight(max(56, head.sizeHint().height()))
        v.addWidget(head)
        v.addSpacing(16)
        # 打开 / 新建项目（类似“新对话”按钮）
        np_ = QPushButton(T("  打开 / 新建项目", "  Open / new project"))
        np_.setObjectName("newProject")
        np_.setIcon(icon("plus", C["text"], 16, 2))
        np_.setCursor(Qt.CursorShape.PointingHandCursor)
        np_.clicked.connect(lambda: (self.go("home"), self.pages["home"].focus_open()))
        v.addWidget(np_)
        v.addSpacing(12)
        # 导航（可滚动：窗口较矮时不挤压品牌区与底部）
        from PySide6.QtWidgets import QScrollArea
        navw = QWidget()
        navw.setObjectName("sidebar")
        navw.setStyleSheet("QWidget#sidebar{border:none;}")
        nv = QVBoxLayout(navw)
        nv.setContentsMargins(0, 0, 0, 0)
        nv.setSpacing(2)
        grp = QButtonGroup(self)
        grp.setExclusive(True)
        on = is_project()
        for spec in page_specs():
            if spec is None:
                nv.addSpacing(10)
                continue
            key, cls = spec
            b = QPushButton("  " + T(cls.title_zh, cls.title_en).replace("&", "&&"))
            b.setObjectName("nav")
            b.setCheckable(True)
            b.setIcon(icon(cls.icon_name, C["text2"], 17))
            b.setIconSize(QSize(17, 17))
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            b.clicked.connect(lambda _=False, k=key: self.go(k))
            b.setEnabled(on or key in ("home", "planner", "help"))
            grp.addButton(b)
            self.nav[key] = b
            nv.addWidget(b)
        nv.addStretch(1)
        sa = QScrollArea()
        sa.setWidgetResizable(True)
        sa.setFrameShape(QFrame.Shape.NoFrame)
        sa.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        sa.setStyleSheet(f"QScrollArea{{background:{C['side']};border:none;}}")
        sa.setWidget(navw)
        v.addWidget(sa, 1)
        v.addSpacing(6)
        # 底部：更新提示、项目、语言
        self.upd_btn = QPushButton()
        self.upd_btn.setObjectName("link")
        self.upd_btn.hide()
        self.upd_btn.clicked.connect(lambda: self.go("help"))
        v.addWidget(self.upd_btn)
        pc = QFrame()
        pc.setObjectName("projectCard")
        pl_ = QHBoxLayout(pc)
        pl_.setContentsMargins(10, 8, 10, 8)
        pl_.setSpacing(8)
        fi = QLabel()
        fi.setPixmap(icon("folder", C["text2"], 16).pixmap(16, 16))
        pl_.addWidget(fi)
        self.proj_lbl = QLabel()
        self.proj_lbl.setObjectName("muted")
        pl_.addWidget(self.proj_lbl, 1)
        v.addWidget(pc)
        self._update_project_label()
        v.addSpacing(8)
        lang = W.Segmented(["zh", "en"], W.LANG["v"], fmt=lambda x: "中文" if x == "zh" else "English")
        lang.changed.connect(self.set_lang)
        lh = QHBoxLayout()
        gl = QLabel()
        gl.setPixmap(icon("globe", C["text3"], 15).pixmap(15, 15))
        lh.addWidget(gl)
        lh.addWidget(lang, 1)
        v.addLayout(lh)
        return side

    def _footer(self):
        f = QWidget()
        lay = QHBoxLayout(f)
        lay.setContentsMargins(24, 6, 24, 10)
        self.busy_lbl = QLabel("")
        self.busy_lbl.setObjectName("faint")
        lay.addWidget(self.busy_lbl, 1)
        ic = QLabel()
        ic.setPixmap(icon("shield", C["text2"], 15).pixmap(15, 15))
        lay.addWidget(ic)
        d = QLabel(T("XAFSmith 不对结果负责，可能出错：关键结果请与 Athena / Artemis 对照。",
                     "XAFSmith comes with no warranty and can make mistakes — cross-check key results with Athena / Artemis.")
                   + f'  <a href="#" style="color:{C["accent_text"]};text-decoration:none">'
                   + T("免责声明与引用", "Disclaimer & citation") + "</a>")
        d.setObjectName("footnote")
        d.setTextFormat(Qt.TextFormat.RichText)
        d.linkActivated.connect(lambda *_: self.show_disclaimer())
        lay.addWidget(d)
        lay.addStretch(1)
        return f

    # ------------------------------------------------------------------ 行为
    def go(self, key):
        if key not in self.pages:
            key = "home"
        if not is_project() and key not in ("home", "planner", "help"):
            key = "home"
        self.S.extra["page"] = key
        if key in self.nav:
            self.nav[key].setChecked(True)
        p = self.pages[key]
        self.stack.setCurrentWidget(p)
        p.on_show()

    def refresh_current(self):
        self.stack.currentWidget().refresh()

    def _state_changed(self, what):
        if what == "project":
            self.rebuild()

    def _update_project_label(self):
        if is_project():
            self.proj_lbl.setText(paths.ROOT.name)
            self.proj_lbl.setToolTip(str(paths.ROOT))
        else:
            self.proj_lbl.setText(T("未打开项目", "No project"))

    def rebuild(self):
        """语言或项目改变后重建整个界面（会话数据保留在 State 中）"""
        geo = self.geometry()
        old = self.centralWidget()
        self.pages.clear()
        self.nav.clear()
        self._build()
        old.deleteLater()
        self.setGeometry(geo)
        if self._update:
            self._show_update(self._update)

    def set_lang(self, lang):
        from xafsmith import update as xup
        W.LANG["v"] = lang
        try:
            xup.save_settings(lang=lang)
        except Exception:
            pass
        self.rebuild()

    def open_project(self, root):
        paths.set_root(root)
        paths.ensure()
        remember(paths.ROOT)
        self.S.reset()
        self.S.extra["page"] = "home"
        self.rebuild()

    def busy(self, on, text=""):
        self.bar.setVisible(on)
        self.busy_lbl.setText(text if on else "")

    def toast(self, text, kind="ok"):
        t = self._toast
        col = {"ok": C["ok"], "warn": C["warn"], "err": C["err"], "info": C["text2"]}.get(kind, C["text2"])
        t.setText(text)
        t.setWordWrap(True)
        t.setStyleSheet(f"background:{C['text']};color:{C['bg']};border-radius:10px;padding:9px 16px;"
                        f"border-left:4px solid {col};")
        t.setMaximumWidth(620)
        t.adjustSize()
        t.move((self.width() + 250 - t.width()) // 2, self.height() - t.height() - 56)
        t.raise_()
        t.show()
        QTimer.singleShot(3200, t.hide)

    def show_disclaimer(self):
        from xafsmith import about, __version__
        dlg = QDialog(self)
        dlg.setWindowTitle(T("免责声明与引用", "Disclaimer & citation"))
        dlg.resize(680, 520)
        v = QVBoxLayout(dlg)
        v.setContentsMargins(24, 22, 24, 18)
        h = QLabel(T("免责声明与引用", "Disclaimer & citation"))
        h.setObjectName("h1")
        v.addWidget(h)
        v.addWidget(W.label(f"XAFSmith {__version__} · Developed by Eggy & Claude Opus 5.5 (Anthropic) · {about.REPO}",
                            "muted"))
        tb = QTextBrowser()
        tb.setObjectName("prose")
        tb.setOpenExternalLinks(True)
        body = [about.DISCLAIMER_EN if W.en() else about.DISCLAIMER_CN, "",
                about.CITE_EN if W.en() else about.CITE_CN, ""] + about.UPSTREAM
        tb.setPlainText("\n".join(body))
        v.addWidget(tb, 1)
        v.addWidget(W.hbox(None, W.copy_button(about.CITATION_TEXT + "\n\n" + "\n".join(about.UPSTREAM),
                                                T("复制引用", "Copy citation")),
                           W.button(T("关闭", "Close"), primary=True, slot=dlg.accept)))
        dlg.exec()

    def _show_update(self, u):
        self._update = u
        if u.get("newer"):
            self.upd_btn.setText(T(f"↑ 有新版本 {u['latest']}", f"↑ Update {u['latest']} available"))
            self.upd_btn.show()

    def start_background(self):
        """后台：检查更新（遵守设置，不阻塞界面），预先导入 larch / lmfit"""
        def work():
            from xafsmith import update as xup
            try:
                if xup.load_settings().get("check_updates", True):
                    u = xup.check(timeout=3.0)
                    if u:
                        self.update_found.emit(u)
            except Exception:
                pass
            try:
                import larch.xafs  # noqa: F401
                import larch.fitting  # noqa: F401
                import lmfit  # noqa: F401
            except Exception:
                pass
        threading.Thread(target=work, daemon=True).start()


def make_window(project=None, lang=None, dark=None):
    """创建程序与主窗口（不进入事件循环；测试也用它）"""
    import matplotlib
    matplotlib.use("QtAgg")
    if sys.platform == "win32":
        try:
            import ctypes
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("XAFSmith.App")
        except Exception:
            pass
    if project:
        paths.set_root(project)
    elif os.environ.get("XAFSMITH_PROJECT"):
        paths.set_root(os.environ["XAFSMITH_PROJECT"])
    app = QApplication.instance() or QApplication(sys.argv)
    app.setApplicationName("XAFSmith")
    app.setStyle("Fusion")
    if dark is None:
        dark = False
        try:
            dark = app.styleHints().colorScheme() == Qt.ColorScheme.Dark
        except Exception:
            pass
    theme.use_dark(dark)
    theme.install_resources()
    app.setStyleSheet(theme.qss())
    theme.mpl_style()
    from xafsmith import update as xup
    W.LANG["v"] = lang or xup.load_settings().get("lang", "zh")
    if (ASSETS / "xafsmith.ico").exists():
        app.setWindowIcon(QIcon(str(ASSETS / "xafsmith.ico")))
    if is_project():
        paths.ensure()
        remember(paths.ROOT)
    S = State()
    w = MainWindow(S)
    return app, w


def run(project=None):
    app, w = make_window(project)
    w.show()
    QTimer.singleShot(400, w.start_background)
    return app.exec()


if __name__ == "__main__":
    sys.exit(run(sys.argv[1] if len(sys.argv) > 1 else None))
