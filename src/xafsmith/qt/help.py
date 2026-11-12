"""使用指南：独立窗口（可与主窗口并排，一边操作一边查看）。

左侧：图形界面使用指南、零基础拟合教程、拟合质量提升教程、XAFS 基础讲义；下方单独一页“关于”（版本、署名、免责声明、引用、检查更新）。
"""
from __future__ import annotations

from xafsmith import logs
from pathlib import Path

from PySide6.QtCore import QSize, Qt, QUrl
from PySide6.QtGui import QDesktopServices, QIcon, QKeySequence, QShortcut, QTextCursor, QTextDocument
from PySide6.QtWidgets import (QButtonGroup, QHBoxLayout, QLabel, QLineEdit, QListWidget, QListWidgetItem, QMainWindow,
                               QPushButton, QScrollArea, QStackedWidget, QVBoxLayout, QWidget)

from . import widgets as W
from .theme import C, FS, SP, WIDTH, icon
from .widgets import T, Banner, Card

DOCS = Path(__file__).resolve().parent.parent / "docs"
ASSETS = Path(__file__).resolve().parent.parent / "assets"


def doc_specs():
    en = W.en()
    return [("gui", T("图形界面使用指南", "GUI guide"), "doc", "GUI_guide_en.md" if en else "图形界面使用指南.md"),
            ("tutorial", T("零基础拟合教程", "Fitting for beginners"), "fit", "fitting_tutorial_en.md" if en else "零基础拟合教程.md"),
            ("quality", T("拟合质量提升教程", "Improving fit quality"), "chart", "fit_quality_guide_en.md" if en else "拟合质量提升教程.md"),
            ("basics", T("XAFS 基础讲义", "XAFS basics"), "atom", "XAFS_basics_en.md" if en else "XAFS基础讲义.md")]


def _tex(s):
    """Markdown 中的 LaTeX → matplotlib mathtext 能识别的写法"""
    import re
    s = s.replace("\\!", "").replace("\\text{", "\\mathrm{").replace("\\left", "").replace("\\right", "")
    s = s.replace("\\|", "|")
    return re.sub(r"\\(?:,|;|quad)", " ", s)


def render_math(md, size=14):
    """把 $$…$$（独立公式）与 $…$（行内公式）渲染成 PNG（matplotlib mathtext），换成图片引用；
    同一段公式只渲染一次（按内容与颜色缓存）。GitHub 上同一份 Markdown 由网页直接渲染公式。"""
    import hashlib
    import re
    import tempfile
    from matplotlib.backends.backend_agg import FigureCanvasAgg
    from matplotlib.figure import Figure
    d = Path(tempfile.gettempdir()) / "xafsmith_math"
    d.mkdir(parents=True, exist_ok=True)
    col = C["text"]
    from PySide6.QtGui import QGuiApplication
    scr = QGuiApplication.primaryScreen()
    dpr = max(1.0, scr.devicePixelRatio() if scr else 1.0)      # 高分屏按物理像素渲染，prose.retarget_images 再折算回逻辑尺寸

    def img(tex, display):
        key = hashlib.md5(f"v3|{tex}|{display}|{col}|{size}|{dpr:.2f}".encode("utf-8")).hexdigest()[:16]
        f = d / f"xs_math_{key}_x{dpr:.2f}.png"
        if not f.exists():
            try:                  # 透明背景；行内公式与正文同高，独立公式稍大
                fig = Figure()
                FigureCanvasAgg(fig)
                fig.text(0, 0, f"${_tex(tex)}$", fontsize=size * (1.3 if display else 1.0), color=col)
                fig.savefig(str(f), dpi=96 * 1.05 * dpr, transparent=True, bbox_inches="tight", pad_inches=0.02, format="png")
            except Exception:     # noqa: BLE001  无法渲染时保留原文
                logs.log.debug("qt.help.img 出错（已忽略或已提示）", exc_info=True)
                return None
        return f.name

    def disp(m):
        n = img(m.group(1).strip(), True)
        return f"\n\n![formula]({n})\n\n" if n else m.group(0)      # 空的替代文字会被 Qt 丢掉

    def inline(m):
        n = img(m.group(1), False)
        return f"![formula]({n})" if n else m.group(0)
    md = re.sub(r"\$\$(.+?)\$\$", disp, md, flags=re.S)
    md = re.sub(r"(?<![\\$])\$([^$\n]+?)\$", inline, md)
    return md, d


def _slug(text):
    """标题 → GitHub 风格锚点名（小写、去标点、空格变连字符），讲义目录里的 #锚点 链接据此跳转"""
    import re
    return re.sub(r"[^\w\- ]", "", text.strip().lower()).replace(" ", "-")


class DocPane(QWidget):
    """文档阅读面板：顶部后退/前进 + 查找条（Ctrl+F），右侧标题目录；文内 #锚点 链接由本面板按标题跳转"""

    def __init__(self, tb):
        super().__init__()
        self.tb = tb
        self.heads = []                 # [(层级, 标题, 块位置, slug)]
        self._back, self._fwd = [], []
        tb.setOpenLinks(False)
        tb.setOpenExternalLinks(False)
        tb.anchorClicked.connect(self._link)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)
        bar = QWidget()
        bar.setObjectName("topBar")
        bl = QHBoxLayout(bar)
        bl.setContentsMargins(SP['md'], SP['sm'], SP['md'], SP['sm'])
        bl.setSpacing(6)
        self.bb = QPushButton("‹")
        self.fb = QPushButton("›")
        for b, tip, slot in ((self.bb, T("后退", "Back"), self.back), (self.fb, T("前进", "Forward"), self.forward)):
            b.setToolTip(tip)
            b.setFixedWidth(34)
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            b.clicked.connect(slot)
            bl.addWidget(b)
        bl.addStretch(1)
        self.find_edit = QLineEdit()
        self.find_edit.setPlaceholderText(T("查找（Ctrl+F）", "Find (Ctrl+F)"))
        self.find_edit.setClearButtonEnabled(True)
        self.find_edit.setMinimumWidth(240)
        self.find_edit.setToolTip(T("Enter 下一个，Shift+Enter 上一个", "Enter = next, Shift+Enter = previous"))
        self.find_edit.returnPressed.connect(lambda: self.find(False))
        self.find_edit.textChanged.connect(lambda _t: self.find(False, keep=True))
        bl.addWidget(self.find_edit)
        self.find_note = QLabel("")
        self.find_note.setObjectName("faint")
        bl.addWidget(self.find_note)
        lay.addWidget(bar)
        row = QHBoxLayout()
        row.setSpacing(0)
        row.addWidget(tb, 1)
        self.toc = QListWidget()
        self.toc.setFixedWidth(WIDTH['toc'])
        self.toc.setObjectName("toc")
        self.toc.setWordWrap(True)
        self.toc.itemClicked.connect(lambda it: self.goto(it.data(Qt.ItemDataRole.UserRole), push=True))
        row.addWidget(self.toc)
        lay.addLayout(row, 1)
        QShortcut(QKeySequence.StandardKey.Find, self, activated=self._focus_find)
        QShortcut(QKeySequence("Shift+Return"), self.find_edit, activated=lambda: self.find(True))
        self._build_toc()
        tb.verticalScrollBar().valueChanged.connect(self._sync_toc)
        self._nav_state()

    def _build_toc(self):
        doc = self.tb.document()
        blk = doc.begin()
        while blk.isValid():
            lvl = blk.blockFormat().headingLevel()
            if lvl and blk.text().strip():
                self.heads.append((lvl, blk.text().strip(), blk.position(), _slug(blk.text())))
            blk = blk.next()
        for i, (lvl, text, _pos, _sl) in enumerate(self.heads):
            if lvl > 3:
                continue
            it = QListWidgetItem(("    " * max(0, lvl - 2)) + text)
            it.setData(Qt.ItemDataRole.UserRole, i)
            self.toc.addItem(it)
        self._toc_vis()

    def _toc_vis(self):
        self.toc.setVisible(self.toc.count() > 2 and self.width() >= 760)     # 窗口窄时隐藏目录，把宽度留给正文

    def resizeEvent(self, e):
        super().resizeEvent(e)
        self._toc_vis()

    def _top_of(self, i):
        doc = self.tb.document()
        blk = doc.findBlock(self.heads[i][2])
        return int(doc.documentLayout().blockBoundingRect(blk).top())

    def goto(self, i, push=False):
        if i is None or not (0 <= i < len(self.heads)):
            return
        sb = self.tb.verticalScrollBar()
        if push:
            self._back.append(sb.value())
            self._fwd.clear()
        sb.setValue(max(0, self._top_of(i) - 6))
        self._nav_state()

    def _link(self, url: QUrl):
        frag = url.fragment()
        if frag and not url.scheme() and not url.path():
            for i, h in enumerate(self.heads):
                if h[3] == _slug(frag) or h[3] == frag.lower():
                    self.goto(i, push=True)
                    return
            return
        if url.scheme() in ("http", "https"):
            QDesktopServices.openUrl(url)

    def _step(self, src, dst):
        if not src:
            return
        sb = self.tb.verticalScrollBar()
        dst.append(sb.value())
        sb.setValue(src.pop())
        self._nav_state()

    def back(self):
        self._step(self._back, self._fwd)

    def forward(self):
        self._step(self._fwd, self._back)

    def _nav_state(self):
        self.bb.setEnabled(bool(self._back))
        self.fb.setEnabled(bool(self._fwd))

    def _sync_toc(self, v):
        cur = None
        for i, h in enumerate(self.heads):
            if h[0] <= 3 and self._top_of(i) <= v + 40:
                cur = i
        for r in range(self.toc.count()):
            it = self.toc.item(r)
            if it.data(Qt.ItemDataRole.UserRole) == cur:
                self.toc.blockSignals(True)
                self.toc.setCurrentItem(it)
                self.toc.blockSignals(False)
                break

    def _focus_find(self):
        self.find_edit.setFocus()
        self.find_edit.selectAll()

    def find(self, backward, keep=False):
        text = self.find_edit.text()
        tb = self.tb
        if not text:
            self.find_note.setText("")
            c = tb.textCursor()
            c.clearSelection()
            tb.setTextCursor(c)
            return
        flags = QTextDocument.FindFlag.FindBackward if backward else QTextDocument.FindFlag(0)
        if keep:                                    # 边输入边查：从当前选区开头重新找
            c = tb.textCursor()
            c.setPosition(min(c.anchor(), c.position()))
            tb.setTextCursor(c)
        if not tb.find(text, flags):
            c = tb.textCursor()                     # 到头了：从另一端继续
            c.movePosition(QTextCursor.MoveOperation.End if backward else QTextCursor.MoveOperation.Start)
            tb.setTextCursor(c)
            if not tb.find(text, flags):
                self.find_note.setText(T("无匹配", "No match"))
                return
        self.find_note.setText("")


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
        side.setStyleSheet(f"QPushButton#nav{{font-size:{FS['lg']}pt;padding-top:7px;padding-bottom:7px;}}")
        side.setFixedWidth(WIDTH['help_sidebar'])
        v = QVBoxLayout(side)
        v.setContentsMargins(SP['md'], SP['lg'], SP['md'], SP['lg'])
        v.setSpacing(2)
        t = QLabel(T("使用指南", "Help"))
        t.setObjectName("brand")
        v.addWidget(t)
        v.addSpacing(12)
        self.stack = QStackedWidget()
        self.btn = {}
        grp = QButtonGroup(self)
        self._lazy = {}
        for key, title, ic, fn in doc_specs():
            page = QWidget()                      # 文档第一次点开时才渲染（公式、图片较慢）
            QVBoxLayout(page).setContentsMargins(0, 0, 0, 0)
            self._lazy[key] = (page, fn)
            self._add(v, grp, key, title, ic, page)
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
        self._toaster = W.Toaster(self, WIDTH['help_sidebar'])
        self.show_tab("gui")

    def closeEvent(self, e):
        if self.main is not None:
            self.main._save_geometry("help", self)
        super().closeEvent(e)

    def toast(self, text, kind="ok"):
        """帮助窗口里触发的提示（如导出诊断包）显示在本窗口，不再丢失"""
        self._toaster.show(text, kind)

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
            if key in self._lazy:
                pg, fn = self._lazy.pop(key)
                pg.layout().addWidget(self._doc(fn))
            b.setChecked(True)
            self.stack.setCurrentWidget(page)

    def _doc(self, fn):
        p = DOCS / fn
        md = p.read_text(encoding="utf-8") if p.exists() else fn
        md, mdir = render_math(md)
        # 讲义中的图片（images/…）与公式；不要改 objectName（全局样式表里 #doc 的字号会覆盖这里的 14 pt）
        tb = W.prose_browser(markdown=md, size=14, search_paths=[DOCS, mdir])
        return DocPane(tb)

    def _export_diag(self):
        from datetime import datetime
        from PySide6.QtWidgets import QFileDialog, QMessageBox
        from xafsmith import logs
        f, _ = QFileDialog.getSaveFileName(self, T("保存诊断包", "Save diagnostics"),
                                           str(Path.home() / f"xafsmith_diag_{datetime.now():%Y%m%d_%H%M%S}.zip"), "ZIP (*.zip)")
        if not f:
            return
        try:
            logs.diagnostics_zip(f)
            QMessageBox.information(self, "XAFSmith", T("已保存：", "Saved: ") + f)
        except Exception as ex:
            logs.log.exception("导出诊断包失败")
            QMessageBox.warning(self, "XAFSmith", str(ex))

    def _about(self):
        from xafsmith import __version__, about, logs, update as xup
        sa = QScrollArea()
        sa.setWidgetResizable(True)
        inner = QWidget()
        inner.setObjectName("page")
        lay = QVBoxLayout(inner)
        lay.setContentsMargins(SP['xl'], SP['xl'], SP['xl'], SP['xl'])
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
        lc = Card(T("许可", "License"))
        lc.add(W.label(about.LICENSE_EN if W.en() else about.LICENSE_CN))
        lc.add(W.label(f"<a href='{about.REPO}/blob/main/LICENSE'>LICENSE</a> · <a href='{about.REPO}/blob/main/NOTICE'>NOTICE</a>",
                       "muted", rich=True))
        lay.addWidget(lc)
        dg = Card(T("诊断", "Diagnostics"))
        dg.add(W.label(T("出错时导出诊断包（日志 + 版本环境 + 项目配置 + 登记表，不含原始数据与谱图数值）发给开发者。日志位置：",
                         "On errors, export a diagnostics bundle (log + environment + project config + meta.csv; no raw data or spectra) "
                         "for the developer. Log file: ") + str(logs.LOG_FILE), "muted"))
        dg.add(W.button(T("导出诊断包", "Export diagnostics"), slot=self._export_diag))
        lay.addWidget(dg)
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
                elif xup.is_frozen():
                    res.layout().addWidget(W.label(T(f"请到 <a href='{xup.RELEASES_PAGE}'>GitHub Releases</a> 下载新的安装程序并运行（覆盖旧版，项目文件不受影响）。",
                                                     f"Download the new installer from <a href='{xup.RELEASES_PAGE}'>GitHub Releases</a> and run it "
                                                     "(it replaces the old version; project files are untouched)."), rich=True))
                else:
                    b = W.button(T("更新到最新版", "Update now"), primary=True)
                    b.clicked.connect(lambda: W.run_task(self, xup.upgrade, lambda r: res.layout().addWidget(
                        Banner("ok", T("更新完成：请关闭 XAFSmith 并重新打开。", "Updated: close and reopen XAFSmith.")) if r[0]
                        else W.code_block(r[1][-2000:])), T("正在下载并安装（约 1–5 分钟）…", "Downloading and installing (1–5 min)…"), b,
                        key="update_install"))
                    res.layout().addWidget(W.hbox(b, None))
            else:
                res.layout().addWidget(Banner("info", T(f"已是最新版本 {u['current']}", f"Up to date ({u['current']})")))
        btn = W.button(T("现在检查", "Check now"), icon_name="refresh")
        btn.clicked.connect(lambda: W.run_task(self, xup.check, show, T("检查中…", "Checking…"), btn, key="update_check"))
        up.add(W.hbox(auto, None, btn))
        up.add(res)
        lay.addWidget(up)
        if getattr(self.main, "_update", None):
            show(self.main._update)
        lay.addStretch(1)
        sa.setWidget(inner)
        return sa
