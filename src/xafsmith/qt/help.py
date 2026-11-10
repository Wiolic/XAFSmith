"""使用指南：独立窗口（可与主窗口并排，一边操作一边查看）。

左侧：图形界面使用指南、零基础拟合教程、拟合质量提升教程、XAFS 基础讲义；下方单独一页“关于”（版本、署名、免责声明、引用、检查更新）。
"""
from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import (QButtonGroup, QHBoxLayout, QLabel, QMainWindow, QPushButton, QScrollArea, QStackedWidget,
                               QTextBrowser, QVBoxLayout, QWidget)

from . import widgets as W
from .theme import C, icon
from .widgets import T, Banner, Card

DOCS = Path(__file__).resolve().parent.parent / "docs"
ASSETS = Path(__file__).resolve().parent.parent / "assets"


def doc_specs():
    en = W.en()
    return [("gui", T("图形界面使用指南", "GUI guide"), "doc", "GUI_guide_en.md" if en else "图形界面使用指南.md"),
            ("tutorial", T("零基础拟合教程", "Beginner fitting tutorial"), "fit", "fitting_tutorial_en.md" if en else "零基础拟合教程.md"),
            ("quality", T("拟合质量提升教程", "Improving fit quality"), "chart", "fit_quality_guide_en.md" if en else "拟合质量提升教程.md"),
            ("basics", T("XAFS 基础讲义", "XAFS basics"), "atom", "XAFS_basics_en.md" if en else "XAFS基础讲义.md")]


class HelpWindow(QMainWindow):
    def __init__(self, main):
        super().__init__()
        self.main = main
        self.lang = W.LANG["v"]
        self.setWindowTitle(T("XAFSmith 使用指南", "XAFSmith help"))
        if (ASSETS / "xafsmith.ico").exists():
            self.setWindowIcon(QIcon(str(ASSETS / "xafsmith.ico")))
        self.setMinimumSize(720, 520)
        root = QWidget()
        root.setObjectName("root")
        h = QHBoxLayout(root)
        h.setContentsMargins(0, 0, 0, 0)
        h.setSpacing(0)
        side = QWidget()
        side.setObjectName("sidebar")
        side.setFixedWidth(210)
        v = QVBoxLayout(side)
        v.setContentsMargins(12, 16, 12, 14)
        v.setSpacing(2)
        t = QLabel(T("使用指南", "Help"))
        t.setObjectName("brand")
        v.addWidget(t)
        v.addSpacing(12)
        self.stack = QStackedWidget()
        self.btn = {}
        grp = QButtonGroup(self)
        for key, title, ic, fn in doc_specs():
            self._add(v, grp, key, title, ic, self._doc(fn))
        v.addStretch(1)
        self._add(v, grp, "about", T("关于与免责声明", "About & disclaimer"), "shield", self._about())
        h.addWidget(side)
        main_area = QWidget()
        main_area.setObjectName("main")
        mv = QVBoxLayout(main_area)
        mv.setContentsMargins(0, 0, 0, 0)
        mv.addWidget(self.stack)
        h.addWidget(main_area, 1)
        self.setCentralWidget(root)
        self.show_tab("gui")

    def _add(self, v, grp, key, title, ic, page):
        b = QPushButton("  " + title.replace("&", "&&"))
        b.setObjectName("nav")
        b.setCheckable(True)
        b.setIcon(icon(ic, C["text2"], 16))
        b.setIconSize(QSize(16, 16))
        b.setCursor(Qt.CursorShape.PointingHandCursor)
        b.clicked.connect(lambda _=False, k=key: self.show_tab(k))
        grp.addButton(b)
        v.addWidget(b)
        self.btn[key] = (b, page)
        self.stack.addWidget(page)

    def show_tab(self, key):
        if key in self.btn:
            b, page = self.btn[key]
            b.setChecked(True)
            self.stack.setCurrentWidget(page)

    def _doc(self, fn):
        p = DOCS / fn
        md = p.read_text(encoding="utf-8") if p.exists() else fn
        tb = W.prose_browser(markdown=md, size=11.5, search_paths=[DOCS])     # 讲义中的图片与公式（images/…）
        tb.setObjectName("doc")
        return tb

    def _about(self):
        from xafsmith import __version__, about, update as xup
        sa = QScrollArea()
        sa.setWidgetResizable(True)
        inner = QWidget()
        inner.setObjectName("page")
        lay = QVBoxLayout(inner)
        lay.setContentsMargins(28, 24, 28, 24)
        lay.setSpacing(14)
        h = QLabel(T("关于与免责声明", "About & disclaimer"))
        h.setObjectName("h1")
        lay.addWidget(h)
        ab = Card()
        ab.add(W.label(f"<b>XAFSmith {__version__}</b> · Agent-ready synchrotron XAFS (XANES / EXAFS) analysis software<br/>"
                       f"<b style='color:{C['accent_text']}'>Developed by Eggy &amp; Claude Opus 5.5</b> (Anthropic)<br/>"
                       "Built on <a href='https://xraypy.github.io/xraylarch/'>xraylarch</a> (FEFF6L, FEFF8L, feffit), xraydb, lmfit, "
                       f"pymatgen, PySide6 and matplotlib · <a href='{about.REPO}'>{about.REPO}</a>", rich=True))
        lay.addWidget(ab)
        dc = Card(T("免责声明", "Disclaimer"))
        dc.add(W.label(about.DISCLAIMER_EN if W.en() else about.DISCLAIMER_CN))
        lay.addWidget(dc)
        ci = Card(T("引用", "Citation"), actions=[W.copy_button(about.CITATION_TEXT + "\n\n" + "\n".join(about.UPSTREAM),
                                                                 T("复制引用", "Copy citation"))])
        ci.add(W.label(about.CITE_EN if W.en() else about.CITE_CN))
        for u in about.UPSTREAM:
            ci.add(W.label("• " + u, "muted"))
        lay.addWidget(ci)
        up = Card(T("检查更新", "Updates"))
        s = xup.load_settings()
        auto = W.check(T("启动时自动检查新版本（只访问 github.com，不发送任何数据）",
                         "Check for updates at start-up (contacts github.com only, sends nothing)"), s.get("check_updates", True))
        auto.toggled.connect(lambda v: xup.save_settings(check_updates=bool(v)))
        res = W.vbox()

        def show(u):
            W._clear_layout(res.layout())
            if u.get("latest") is None:
                res.layout().addWidget(Banner("warn", T("无法连接 GitHub（离线或被网络阻止）。", "Cannot reach GitHub (offline or blocked).")))
            elif u.get("newer"):
                res.layout().addWidget(Banner("ok", T(f"有新版本 {u['latest']}（当前 {u['current']}）",
                                                      f"New version {u['latest']} (current {u['current']})")))
                if u.get("editable"):
                    res.layout().addWidget(W.label(T("开发安装：请在源码目录用 git pull 更新。",
                                                     "Development install: update with git pull in the source folder."), "faint"))
                else:
                    b = W.button(T("更新到最新版", "Update now"), primary=True)
                    b.clicked.connect(lambda: W.run_task(self, xup.upgrade, lambda r: res.layout().addWidget(
                        Banner("ok", T("更新完成：请关闭 XAFSmith 并重新打开。", "Updated: close and reopen XAFSmith.")) if r[0]
                        else W.code_block(r[1][-2000:])), T("正在下载并安装（约 1–5 分钟）…", "Downloading and installing (1–5 min)…"), b))
                    res.layout().addWidget(W.hbox(b, None))
            else:
                res.layout().addWidget(Banner("info", T(f"已是最新版本 {u['current']}", f"Up to date ({u['current']})")))
        btn = W.button(T("现在检查", "Check now"), icon_name="refresh")
        btn.clicked.connect(lambda: W.run_task(self, xup.check, show, T("检查中…", "Checking…"), btn))
        up.add(W.hbox(auto, None, btn))
        up.add(res)
        lay.addWidget(up)
        if getattr(self.main, "_update", None):
            show(self.main._update)
        lay.addStretch(1)
        sa.setWidget(inner)
        return sa
