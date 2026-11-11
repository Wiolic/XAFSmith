"""XAFSmith 桌面程序（PySide6）。

启动：xafsmith gui [--project <项目目录>]，或双击桌面图标。
布局：左侧栏（品牌与署名、打开项目、按使用流程分组的导航、当前项目与语言），右侧页面；
页面底部始终显示免责声明（点击查看全文与引用方式）。
"""
from __future__ import annotations

from xafsmith import logs
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
        ("spectra", SpectraTabs), ("norm", pr.NormPage),
        ("chi", pr.ChiPage), ("wavelet", pr.WaveletPage),
        None,
        ("feff", ft.FeffPage), ("fit", ft.FitPage), ("history", ft.HistoryPage), ("lcf", ft.LCFPage),
        ("xanes", ft.XanesPage),
        None,
        ("summary", op.SummaryPage), ("pubfig", op.PubFigPage), ("methods", op.MethodsPage),
        None,
        ("planner", op.PlannerPage), ("elements", op.ElementsPage), ("agent", op.AgentPage), ("help", op.HelpPage),
    ]


# “载入与检查”一页三个标签：载入谱、质量检查、能量校准（各自仍可用 go("load") 等直接打开）
TABBED = {"spectra": ("load", "qc", "calib")}
PARENT = {k: g for g, ks in TABBED.items() for k in ks}
HIDDEN = {"home"}              # 不在导航中显示：由“打开 / 新建项目”按钮进入
NO_PROJECT = ("home", "planner", "elements", "help")     # 未打开项目时也能用的页面


class SpectraTabs(QWidget):
    """载入谱 / 质量检查 / 能量校准 合并为一页（标签切换），各标签仍是独立的页面对象"""
    title_zh, title_en, icon_name = "载入与检查", "Load & check", "upload"

    def __init__(self, app):
        super().__init__()
        from PySide6.QtWidgets import QTabWidget
        from .pages import process as pr
        self.app = app
        self.subs = {"load": pr.LoadPage(app), "qc": pr.QCPage(app), "calib": pr.CalibPage(app)}
        v = QVBoxLayout(self)
        v.setContentsMargins(0, 6, 0, 0)
        v.setSpacing(0)
        self.tabs = QTabWidget()
        self.tabs.setObjectName("pageTabs")
        self.tabs.setDocumentMode(True)
        self.tabs.setStyleSheet("QTabWidget#pageTabs::tab-bar{left:36px;}")
        for k, pg in self.subs.items():
            self.tabs.addTab(pg, "  " + T(pg.title_zh, pg.title_en) + "  ")
        self.tabs.currentChanged.connect(self._changed)
        v.addWidget(self.tabs)
        self._quiet = False

    def show_sub(self, key):
        self._quiet = True
        self.tabs.setCurrentWidget(self.subs[key])
        self._quiet = False

    def _changed(self, i):
        if self._quiet:
            return
        pg = self.tabs.widget(i)
        key = next(k for k, v in self.subs.items() if v is pg)
        self.app.S.extra["page"] = key
        pg.on_show()

    def refresh(self):
        self.tabs.currentWidget().refresh()

    def on_show(self):
        self.tabs.currentWidget().on_show()


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
        # 右上角：流程与本项目（与导航分开，始终在同一位置）
        top = QHBoxLayout()
        top.setContentsMargins(0, 8, 22, 0)
        top.addStretch(1)
        self.flow_btn = FlowButton(self)
        self.flow_btn.setEnabled(is_project())
        top.addWidget(self.flow_btn)
        v.addLayout(top)
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
            if key in TABBED:                  # 标签页也登记为页面（go("qc") 等）
                self.pages.update(p.subs)
        self._toast = QLabel(self)
        self._toast.hide()
        self.go("home" if not is_project() else self.S.extra.get("page", "data"))

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
            if key in HIDDEN:
                continue
            b = QPushButton("  " + T(cls.title_zh, cls.title_en).replace("&", "&&"))
            b.setObjectName("nav")
            b.setCheckable(True)
            b.setIcon(icon(cls.icon_name, C["text2"], 17))
            b.setIconSize(QSize(17, 17))
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            b.clicked.connect(lambda _=False, k=key: self.go(k))
            b.setEnabled(on or key in NO_PROJECT)
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
        self.upd_btn.clicked.connect(lambda: self.open_help("about"))
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
        if key == "help":                     # 使用指南在独立窗口中打开，主窗口停在当前页
            self.open_help()
            cur = PARENT.get(self.S.extra.get("page", "home"), self.S.extra.get("page", "home"))
            if cur in self.nav:
                self.nav[cur].setChecked(True)
            return
        if key not in self.pages:
            key = "home"
        if not is_project() and key not in NO_PROJECT:
            key = "home"
        self.S.extra["page"] = key
        nk = PARENT.get(key, key)
        if nk in self.nav:
            self.nav[nk].setChecked(True)
        p = self.pages[key]
        if key in PARENT:                      # 合并页中的一个标签
            box = self.pages[PARENT[key]]
            self.stack.setCurrentWidget(box)
            box.show_sub(key)
        elif key in TABBED:
            self.stack.setCurrentWidget(p)
        else:
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

    def open_help(self, tab=None):
        """使用指南：独立窗口，便于一边操作一边查看"""
        from .help import HelpWindow
        hw = getattr(self, "_help", None)
        if hw is None or hw.lang != W.LANG["v"]:
            if hw is not None:
                hw.close()
            hw = HelpWindow(self)
            self._help = hw
            g = self.geometry()
            hw.resize(920, max(700, g.height()))
            hw.move(g.right() - 920 + 40, g.top() + 30)
        if tab is not None:
            hw.show_tab(tab)
        hw.show()
        hw.raise_()
        hw.activateWindow()

    def closeEvent(self, e):
        hw = getattr(self, "_help", None)
        if hw is not None:
            hw.close()
        super().closeEvent(e)

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
            logs.log.debug("qt.app.set_lang 出错（已忽略或已提示）", exc_info=True)
            pass
        self.rebuild()

    def open_project(self, root):
        paths.set_root(root)
        paths.ensure()
        remember(paths.ROOT)
        self.S.reset()
        self.S.extra["page"] = "data"
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
        t.move((self.width() + 250 - t.width()) // 2, self.height() - t.height() - 110)
        t.raise_()
        t.show()
        QTimer.singleShot(3200, t.hide)

    def show_disclaimer(self):
        self.open_help("about")

    def _disclaimer_dialog(self):
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
                logs.log.debug("qt.app.work 出错（已忽略或已提示）", exc_info=True)
                pass
            try:
                import larch.xafs  # noqa: F401
                import larch.fitting  # noqa: F401
                import lmfit  # noqa: F401
            except Exception:
                logs.log.debug("qt.app.work 出错（已忽略或已提示）", exc_info=True)
                pass
        threading.Thread(target=work, daemon=True).start()


class FlowButton(QPushButton):
    """侧栏固定按钮“流程与本项目”：鼠标悬停弹出小窗口（流程进度、本项目、常用文件夹），点击可打开 / 关闭"""

    def __init__(self, win):
        super().__init__(T(" 流程与本项目", " Workflow && project"))
        self.win = win
        self.setObjectName("flowBtn")
        self.setIcon(icon("layers", C["accent_text"], 16))
        self.setIconSize(QSize(16, 16))
        self.setStyleSheet(f"QPushButton#flowBtn{{background:{C['accent_soft']};color:{C['accent_text']};font-weight:600;"
                           f"border:1px solid {C['accent']};border-radius:13px;padding:4px 14px;min-height:18px;}}"
                           f"QPushButton#flowBtn:hover{{background:{C['accent']};color:#FFFFFF;}}"
                           f"QPushButton#flowBtn:disabled{{background:transparent;color:{C['text3']};border-color:{C['border']};}}")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.pop = None
        self._timer = QTimer(self)
        self._timer.setInterval(300)
        self._timer.timeout.connect(self._check)
        self.clicked.connect(self.toggle)

    def enterEvent(self, e):
        if self.isEnabled():
            self.open()
        super().enterEvent(e)

    def toggle(self):
        if self.pop is not None and self.pop.isVisible():
            self.close_pop()
        else:
            self.open()

    def open(self):
        if self.pop is not None and self.pop.isVisible():
            return
        self.close_pop()
        self.pop = FlowPopup(self.win, self)
        p = self.mapTo(self.win, self.rect().bottomRight())     # 在按钮正下方，右对齐
        self.pop.adjustSize()
        self.pop.move(max(8, p.x() - self.pop.width()), p.y() + 6)
        self.pop.show()
        self.pop.raise_()
        self._timer.start()

    def close_pop(self):
        self._timer.stop()
        if self.pop is not None:
            self.pop.hide()
            self.pop.deleteLater()
            self.pop = None

    def _check(self):
        from PySide6.QtGui import QCursor
        if self.pop is None:
            return
        pos = QCursor.pos()
        inside = (self.pop.rect().adjusted(-24, -12, 12, 12).contains(self.pop.mapFromGlobal(pos))
                  or self.rect().contains(self.mapFromGlobal(pos)))
        if not inside:
            self.close_pop()


class FlowPopup(QFrame):
    """流程进度（每步可点击跳转）+ 本项目（已载入、拟合、参比）+ 常用文件夹"""

    def __init__(self, win, btn):
        super().__init__(win)
        import pandas as pd
        from PySide6.QtGui import QColor
        from PySide6.QtWidgets import QGraphicsDropShadowEffect
        from xafsmith import pipeline as pl
        from .state import feff_dirs
        self.win, self.btn = win, btn
        self.setObjectName("flowPopup")
        self.setStyleSheet(f"QFrame#flowPopup{{background:{C['card']};border:1px solid {C['border2']};border-radius:14px;}}")
        self.setFixedWidth(400)
        sh = QGraphicsDropShadowEffect(self)
        sh.setBlurRadius(28)
        sh.setOffset(0, 6)
        sh.setColor(QColor(0, 0, 0, 60))
        self.setGraphicsEffect(sh)
        v = QVBoxLayout(self)
        v.setContentsMargins(16, 14, 16, 14)
        v.setSpacing(4)
        S = win.S
        nmeta = len(pl.load_meta()) if paths.META.exists() else 0
        ncal = len(S.calib)
        nproc = len(list(paths.PROC.glob("*"))) if paths.PROC.exists() else 0
        nfeff = len(feff_dirs())
        try:
            nfit = len(pd.read_csv(paths.FITS_CSV, encoding="utf-8-sig")) if paths.FITS_CSV.exists() else 0
        except Exception:
            logs.log.debug("qt.app.__init__ 出错（已忽略或已提示）", exc_info=True)
            nfit = 0
        nrep = len(list(paths.REPORTS.glob("*"))) if paths.REPORTS.exists() else 0
        steps = [
            ("data", T("登记数据", "Register data"), nmeta, T(f"{nmeta} 个文件", f"{nmeta} files")),
            ("batch", T("校准与处理", "Calibrate & process"), nproc, T(f"{ncal} 个参比 · {nproc} 个结果", f"{ncal} refs · {nproc} outputs")),
            ("load", T("查看与检查谱", "Inspect spectra"), len(S.groups), T(f"已载入 {len(S.groups)} 条", f"{len(S.groups)} loaded")),
            ("feff", T("FEFF 路径", "FEFF paths"), nfeff, T(f"{nfeff} 个计算", f"{nfeff} calculations")),
            ("fit", T("拟合", "Fit"), nfit, T(f"{nfit} 个已保存的拟合", f"{nfit} saved fits")),
            ("summary", T("导出", "Export"), nrep, T(f"{nrep} 个报告", f"{nrep} reports")),
        ]
        h = QLabel(T("流程", "Workflow"))
        h.setObjectName("h2")
        v.addWidget(h)
        v.addSpacing(4)
        nxt = next((i for i, s in enumerate(steps) if not s[2]), None)
        for i, (key, name, n, sub) in enumerate(steps):
            b = QPushButton()
            b.setObjectName("flowStep")
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            done = bool(n)
            col = C["ok"] if done else (C["accent_text"] if i == nxt else C["text3"])
            row = QHBoxLayout(b)
            row.setContentsMargins(8, 4, 8, 4)
            row.setSpacing(10)
            num = QLabel("✓" if done else str(i + 1))
            num.setFixedSize(22, 22)
            num.setAlignment(Qt.AlignmentFlag.AlignCenter)
            num.setStyleSheet(f"border-radius:11px;font-weight:600;font-size:9pt;color:{col};"
                              f"background:{C['ok_soft'] if done else (C['accent_soft'] if i == nxt else C['hover'])};")
            tx = QLabel(f"<b>{name}</b>&nbsp;&nbsp;<span style='color:{C['text3']}'>{sub}</span>")
            tx.setTextFormat(Qt.TextFormat.RichText)
            for x in (num, tx):
                x.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
            row.addWidget(num)
            row.addWidget(tx, 1)
            b.setMinimumHeight(38)
            b.setStyleSheet("QPushButton#flowStep{text-align:left;border-radius:8px;background:transparent;"
                            + (f"border:1.5px solid {C['accent']};}}" if i == nxt else "border:none;}")
                            + f"QPushButton#flowStep:hover{{background:{C['hover']};}}")
            b.clicked.connect(lambda _=False, k=key: (self.btn.close_pop(), self.win.go(k)))
            v.addWidget(b)
        v.addSpacing(10)
        h2 = QLabel(T("本项目", "This project"))
        h2.setObjectName("h2")
        v.addWidget(h2)
        nm = QLabel(paths.ROOT.name)
        nm.setObjectName("muted")
        nm.setToolTip(str(paths.ROOT))
        v.addWidget(nm)
        v.addWidget(W.metrics((T("已载入的谱", "Loaded"), len(S.groups)), (T("拟合", "Fits"), len(S.fits)),
                              (T("参比校准", "References"), ncal)))

        def save_session():
            from xafsmith.common import write_params
            write_params(paths.GUI / "gui_session.params.json",
                         dict(norm=S.norm_par, bkg=S.bkg_par, ft=S.ft_par, calib=S.calib, groups=list(S.groups)), "gui")
            self.win.toast(T("已保存 output/gui/gui_session.params.json", "Saved output/gui/gui_session.params.json"))
        g = QHBoxLayout()
        g.setSpacing(6)
        for txt, ic, fn in ((T("项目文件夹", "Project folder"), "folder", lambda: W.open_folder(paths.ROOT)),
                            ("output", "external", lambda: W.open_folder(paths.OUT)),
                            (T("保存处理参数", "Save parameters"), "save", save_session)):
            g.addWidget(W.button(txt, icon_name=ic, slot=fn))
        v.addSpacing(4)
        v.addLayout(g)


def make_window(project=None, lang=None, dark=None):
    """创建程序与主窗口（不进入事件循环；测试也用它）"""
    import matplotlib
    matplotlib.use("QtAgg")
    if sys.platform == "win32":
        try:
            import ctypes
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("XAFSmith.App")
        except Exception:
            logs.log.debug("qt.app.make_window 出错（已忽略或已提示）", exc_info=True)
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
            logs.log.debug("qt.app.make_window 出错（已忽略或已提示）", exc_info=True)
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


def _no_console_output():
    """pythonw（桌面快捷方式）没有控制台，sys.stdout / sys.stderr 为 None；
    larch 等库会直接调用 sys.stdout.write，必须给它们一个可写的文件，否则处理和拟合会报错。"""
    if sys.stdout is not None and sys.stderr is not None:
        return
    try:
        d = Path.home() / ".xafsmith"
        d.mkdir(parents=True, exist_ok=True)
        f = open(d / "console.log", "w", encoding="utf-8", buffering=1)
    except Exception:
        logs.log.debug("qt.app._no_console_output 出错（已忽略或已提示）", exc_info=True)
        f = open(os.devnull, "w", encoding="utf-8")
    if sys.stdout is None:
        sys.stdout = f
    if sys.stderr is None:
        sys.stderr = f


def _error_dialog(text):
    """未捕获异常：弹出可复制的错误框（日志已由 logs.install_excepthook 写入）。"""
    from PySide6.QtWidgets import QApplication, QMessageBox
    if QApplication.instance() is None:
        return
    box = QMessageBox(QMessageBox.Critical, "XAFSmith", T("出错了。详情已写入日志，可在“免责声明与引用”里导出诊断包发给开发者。",
                      "Something went wrong. Details are in the log; export a diagnostics bundle from the About dialog."))
    box.setDetailedText(text)
    box.exec()


def run(project=None):
    _no_console_output()
    from xafsmith import logs
    logs.install_excepthook(_error_dialog)
    app, w = make_window(project)
    w.show()
    QTimer.singleShot(400, w.start_background)
    return app.exec()


if __name__ == "__main__":
    sys.exit(run(sys.argv[1] if len(sys.argv) > 1 else None))
