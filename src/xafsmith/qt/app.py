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

from PySide6.QtCore import QRect, QSize, Qt, QTimer, Signal
from PySide6.QtGui import QIcon, QPixmap
from PySide6.QtWidgets import (QApplication, QButtonGroup, QFrame, QHBoxLayout, QLabel, QMainWindow,
                               QProgressBar, QPushButton, QStackedWidget, QVBoxLayout, QWidget)

from xafsmith import paths
from . import theme, widgets as W
from .theme import C, SP, WIDTH, icon
from .state import State, is_project, remember
from .widgets import T

ASSETS = Path(__file__).resolve().parent.parent / "assets"
QUIET_DIALOGS = W.QUIET   # 自动测试时不弹窗
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
# 页面的前置数据：缺少时导航按钮变灰并在悬停说明缺哪一步（不禁用，仍可点进去看说明与跳转按钮）
NEEDS = {"norm": ("groups",), "chi": ("groups",), "wavelet": ("groups",), "lcf": ("groups",), "xanes": ("groups",),
         "fit": ("groups", "feff"), "pubfig": ("groups",)}
NEED_TEXT = {"groups": ("先在“载入与检查”里载入谱", "Load spectra first (Load & check)"),
             "feff": ("先在“FEFF 路径”里生成散射路径", "Generate scattering paths first (FEFF paths)")}
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


def _avail():
    """主屏的可用区域（扣除任务栏）"""
    scr = QApplication.primaryScreen()
    return scr.availableGeometry() if scr else QRect(0, 0, 1920, 1040)


def _fit_rect(x, y, w, h):
    """把窗口矩形限制在屏幕可用区域内（防止保存的位置落在已拔掉的显示器上、窗口比屏幕大）"""
    a = _avail()
    w, h = min(int(w), a.width()), min(int(h), a.height())
    x = max(a.left(), min(int(x), a.right() - w + 1))
    y = max(a.top(), min(int(y), a.bottom() - h + 1))
    return x, y, w, h


class MainWindow(QMainWindow):
    update_found = Signal(dict)

    def __init__(self, S: State):
        super().__init__()
        self.S = S
        self.setWindowTitle("XAFSmith")
        if (ASSETS / "xafsmith.ico").exists():
            self.setWindowIcon(QIcon(str(ASSETS / "xafsmith.ico")))
        self.setMinimumSize(1060, 680)
        self._saved_geo = None
        avail = _avail()
        self.resize(min(1440, avail.width() - 20), min(920, avail.height() - 40))      # 1366×768 的屏幕也放得下
        self.pages = {}
        self.nav = {}
        self._update = {}
        self._session_ready = False        # 恢复流程（含后台重新载入谱）结束前不保存，否则不完整的状态会覆盖上次的快照
        self._session_timer = QTimer(self)  # 切页等频繁事件只在空闲 2 秒后保存一次，不在每次点击时写文件
        self._session_timer.setSingleShot(True)
        self._session_timer.setInterval(2000)
        self._session_timer.timeout.connect(self.save_session)
        self._build()
        self._shortcuts()
        self.S.changed.connect(self._state_changed)
        self.update_found.connect(self._show_update)

    def _shortcuts(self):
        """F1 帮助、Ctrl+O 打开项目、Ctrl+1…9 按侧栏顺序切页、Esc 关闭流程弹窗"""
        from PySide6.QtGui import QKeySequence, QShortcut

        def sc(seq, fn):
            QShortcut(QKeySequence(seq), self, activated=fn, context=Qt.ShortcutContext.WindowShortcut)
        sc("F1", lambda: self.open_help())
        sc("Ctrl+O", lambda: (self.go("home"), self.pages["home"].focus_open()))
        sc("Esc", lambda: self.flow_btn.close_pop())
        for i in range(1, 10):
            sc(f"Ctrl+{i}", lambda i=i: self._go_nth(i))

    def _go_nth(self, i):
        keys = [k for k, b in self.nav.items() if b.isEnabled() and k not in ("home", "help")]
        if 1 <= i <= len(keys):
            self.go(keys[i - 1])

    def restore_geometry(self):
        """启动时恢复上次的窗口位置与大小（限制在当前屏幕内）"""
        from xafsmith import update as xup
        g = xup.load_settings().get("win", {}).get("main")
        if g and len(g) == 4:
            self.setGeometry(*_fit_rect(*g))

    def _save_geometry(self, which, widget):
        if W.QUIET["v"]:
            return
        try:
            from xafsmith import update as xup
            r = widget.geometry()
            win = dict(xup.load_settings().get("win", {}))
            win[which] = [r.x(), r.y(), r.width(), r.height()]
            xup.save_settings(win=win)
        except Exception:
            logs.log.debug("qt.app._save_geometry 出错（已忽略）", exc_info=True)

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
        # 右上角：流程与本项目（与导航分开，始终在同一位置）
        top = QHBoxLayout()
        top.setContentsMargins(0, SP['sm'], SP['xl'], 0)
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
        self._toaster = W.Toaster(self, WIDTH['sidebar'])
        self.go("home" if not is_project() else self.S.extra.get("page", "data"))

    def _sidebar(self):
        side = QWidget()
        side.setObjectName("sidebar")
        side.setFixedWidth(WIDTH['sidebar'])
        v = QVBoxLayout(side)
        v.setContentsMargins(SP['md'], SP['lg'], SP['md'], SP['lg'])
        v.setSpacing(2)
        # 品牌 + 署名（始终可见）
        brand = QHBoxLayout()
        brand.setSpacing(10)
        logo = QLabel()
        pm = QPixmap(str(ASSETS / "xafsmith.png"))
        dpr = self.devicePixelRatioF()
        lp = pm.scaled(round(38 * dpr), round(38 * dpr), Qt.AspectRatioMode.KeepAspectRatio,
                       Qt.TransformationMode.SmoothTransformation)
        lp.setDevicePixelRatio(dpr)
        logo.setPixmap(lp)
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
        navw.setObjectName("navInner")
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
            b.setIcon(icon(cls.icon_name, C["text2"], 17, on=C["accent_text"], disabled=C["border2"]))
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
        sa.setObjectName("navScroll")
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
        pl_.setContentsMargins(SP['md'], SP['sm'], SP['md'], SP['sm'])
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
        self._lang_seg = lang
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
        lay.setContentsMargins(SP['xl'], SP['sm'], SP['xl'], SP['sm'])
        self.busy_lbl = QLabel("")
        self.busy_lbl.setObjectName("faint")
        lay.addWidget(self.busy_lbl, 1)
        self.bar = QProgressBar()                 # 状态栏进度条：确定进度时带百分比文字，否则为不确定动画
        self.bar.setRange(0, 0)
        self.bar.setTextVisible(True)
        self.bar.setFormat("%p%")
        self.bar.setObjectName("topBar")
        self.bar.hide()
        lay.addWidget(self.bar)
        self._elapsed_timer = QTimer(self)        # 每秒刷新“已用时间”
        self._elapsed_timer.setInterval(1000)
        self._elapsed_timer.timeout.connect(lambda: W.refresh_status(self.busy))
        self._elapsed_timer.start()
        self._cancel_cb = None
        self.cancel_btn = W.button(T("取消", "Cancel"), tip=T("在当前步骤结束后停止（一次拟合 / 一次 FEFF 运行不能中途停止）",
                                                              "Stops after the current step (a single fit / FEFF run cannot be interrupted)"))
        self.cancel_btn.clicked.connect(lambda: self._cancel_cb() if self._cancel_cb else None)
        self.cancel_btn.hide()
        lay.addWidget(self.cancel_btn)
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
        if key != self.S.extra.get("page") and not self._confirm_leave():
            cur = PARENT.get(self.S.extra.get("page", "home"), self.S.extra.get("page", "home"))
            if cur in self.nav:                # 导航按钮已被点选：恢复为当前页
                self.nav[cur].setChecked(True)
            return
        self.S.extra["page"] = key
        self._nav_hints()
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
        self.save_session_later()

    def _confirm_leave(self):
        """当前页有未保存修改时询问（保存 / 放弃 / 取消）；返回 False = 取消"""
        pg = self.pages.get(self.S.extra.get("page", "home"))
        if hasattr(pg, "flush"):
            pg.flush()
        return pg.confirm_leave() if hasattr(pg, "confirm_leave") else True

    def _block_for_tasks(self, what):
        """后台任务运行中不能切换项目 / 语言（任务线程用全局路径，中途换根目录会写进新项目）。
        返回 True = 不要继续。选“取消这些任务”只发取消信号，用户待任务停下后再操作。"""
        n = W.running_count()
        if not n:
            return False
        from PySide6.QtWidgets import QMessageBox
        box = QMessageBox(self)
        box.setIcon(QMessageBox.Icon.Warning)
        box.setWindowTitle(T("有任务在运行", "Tasks are running"))
        box.setText(T(f"有 {n} 个任务在运行，结束后才能{what[0]}。", f"{n} task(s) are running; wait for them to finish before {what[1]}."))
        b_cancel = box.addButton(T("取消这些任务", "Cancel the tasks"), QMessageBox.ButtonRole.DestructiveRole)
        box.addButton(T("继续等待", "Keep waiting"), QMessageBox.ButtonRole.RejectRole)
        if not QUIET_DIALOGS["v"]:
            box.exec()
            if box.clickedButton() is b_cancel:
                W.cancel_all_tasks()
        return True

    def _state_changed(self, what):
        self._nav_hints()
        if what == "project":
            self.rebuild()
        elif what == "fits":
            self.save_session_later()

    def _nav_hints(self):
        """导航按钮：缺前置数据的页面变灰并在悬停说明缺什么；条件满足即恢复"""
        if not is_project():
            return
        have = {"groups": bool(self.S.groups)}
        if any(k == "fit" for k in self.nav):
            try:
                from .state import feff_dirs
                have["feff"] = bool(feff_dirs())
            except Exception:
                logs.log.debug("qt.app._nav_hints 出错（已忽略）", exc_info=True)
                have["feff"] = True
        for key, needs in NEEDS.items():
            b = self.nav.get(key)
            if b is None:
                continue
            miss = [n for n in needs if not have.get(n, True)]
            tip = "；".join(T(*NEED_TEXT[n]) for n in miss) if miss else ""
            if bool(b.property("hint")) != bool(miss):
                b.setProperty("hint", bool(miss))
                b.style().unpolish(b)
                b.style().polish(b)
            b.setToolTip(tip)

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
            from xafsmith import update as xup
            saved = xup.load_settings().get("win", {}).get("help")
            if saved and len(saved) == 4:
                hw.setGeometry(*_fit_rect(*saved))
            else:
                g = self.geometry()
                hw.setGeometry(*_fit_rect(g.right() - 920 + 40, g.top() + 30, 920, max(700, g.height())))
        if tab is not None:
            hw.show_tab(tab)
        hw.show()
        hw.raise_()
        hw.activateWindow()

    def closeEvent(self, e):
        if not self._confirm_leave():
            e.ignore()
            return
        act = self._ask_save_on_close()
        if act is None:                        # 取消关闭
            e.ignore()
            return
        if act == "save":
            self.save_session()
        else:                                  # 不保存：删除快照，下次打开从空白开始
            self._discard_session()
        self._save_geometry("main", self)
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
        if lang != W.LANG["v"] and (self._block_for_tasks(("切换语言", "switching language")) or not self._confirm_leave()):
            seg = getattr(self, "_lang_seg", None)
            if seg is not None:
                seg.set(W.LANG["v"])
            return
        W.LANG["v"] = lang
        try:
            xup.save_settings(lang=lang)
        except Exception:
            logs.log.debug("qt.app.set_lang 出错（已忽略或已提示）", exc_info=True)
            pass
        self.rebuild()

    def open_project(self, root):
        if self._block_for_tasks(("切换项目", "switching project")) or not self._confirm_leave():
            return
        self.save_session()                    # 先保存正在用的项目
        self._session_ready = False
        paths.set_root(root)
        paths.ensure()
        remember(paths.ROOT)
        self.S.reset()
        self.S.extra["page"] = "data"
        self.rebuild()
        QTimer.singleShot(0, self.start_session)

    def clear_workspace(self):
        """清空工作区：移出所有已载入的谱、拟合与各页设置，删除上次的会话快照（数据文件与 output/ 结果不动）。
        用于同一项目里换一批样品从头处理。"""
        if self._block_for_tasks(("清空工作区", "clearing the workspace")):
            return
        n, nf = len(self.S.groups), len(self.S.fits)
        if not W.ask(self, T("清空工作区", "Clear workspace"), T(
                f"移出全部 {n} 条已载入的谱、{nf} 个本次拟合和各页设置，从头开始？\n"
                "原始数据、meta.csv、xafsmith.json 和 output/ 中已保存的结果都不会删除；拟合草稿也保留。",
                f"Remove all {n} loaded spectra, {nf} fits of this session and page settings, and start over?\n"
                "Raw data, meta.csv, xafsmith.json and saved results in output/ are kept; fit drafts are kept too.")):
            return
        from . import session
        self._session_timer.stop()
        try:
            session.session_file().unlink(missing_ok=True)
        except Exception:                      # noqa: BLE001
            logs.log.warning("删除会话快照失败（已忽略）", exc_info=True)
        self.S.reset()
        self.S.extra["page"] = "load"
        self.S.emit("groups")
        self.rebuild()
        self.go("load")
        self.toast(T("工作区已清空，可以读入新的样品", "Workspace cleared; load new samples"), "info")

    # ------------------------------------------------------------------ 会话快照（关闭时保存，打开时恢复）
    def _discard_session(self):
        from . import session
        self._session_timer.stop()
        self._session_ready = False
        if is_project() and session.enabled():
            try:
                session.session_file().unlink(missing_ok=True)
            except Exception:                  # noqa: BLE001
                logs.log.warning("删除会话快照失败（已忽略）", exc_info=True)

    def _ask_save_on_close(self):
        """关闭窗口时：询问是否保存当前进度（下次打开时恢复）。返回 "save" / "discard" / None（取消）。
        设置 close_action：ask（默认）/ save / discard；没有载入的谱和拟合、或关闭了“恢复上次状态”时不问。"""
        from . import session
        from xafsmith import update as xup
        if not is_project() or not session.enabled():
            return "save"
        act = xup.load_settings().get("close_action", "ask")
        if act in ("save", "discard"):
            return act
        if not (self.S.groups or self.S.fits) or W.QUIET["v"]:
            return "save"
        from PySide6.QtWidgets import QMessageBox, QCheckBox
        box = QMessageBox(self)
        box.setIcon(QMessageBox.Icon.Question)
        box.setWindowTitle(T("关闭 XAFSmith", "Close XAFSmith"))
        box.setText(T(f"保存当前进度吗？（{len(self.S.groups)} 条已载入的谱、各页设置、做到一半的拟合设置）",
                      f"Save the current progress? ({len(self.S.groups)} loaded spectra, page settings, half-done fit setup)"))
        box.setInformativeText(T("保存：下次打开本项目时自动恢复。\n不保存：下次从空白开始。\n"
                                 "两种情况下数据文件和 output/ 中已保存的结果都不受影响。",
                                 "Save: restored next time you open this project.\nDon't save: start blank next time.\n"
                                 "Data files and results saved in output/ are kept either way."))
        b_save = box.addButton(T("保存", "Save"), QMessageBox.ButtonRole.AcceptRole)
        b_drop = box.addButton(T("不保存", "Don't save"), QMessageBox.ButtonRole.DestructiveRole)
        box.addButton(T("取消", "Cancel"), QMessageBox.ButtonRole.RejectRole)
        box.setDefaultButton(b_save)
        cb = QCheckBox(T("记住选择，不再询问（可在“项目”页改回）", "Remember and don't ask again (change it on the Project page)"))
        box.setCheckBox(cb)
        box.exec()
        clicked = box.clickedButton()
        act = "save" if clicked is b_save else ("discard" if clicked is b_drop else None)
        if act and cb.isChecked():
            xup.save_settings(close_action=act)
        return act

    def save_session_later(self):
        if self._session_ready:
            self._session_timer.start()

    def save_session(self):
        self._session_timer.stop()
        if not self._session_ready or not is_project():
            return
        from . import session
        session.save_session(self.S, self.pages)

    def start_session(self):
        """打开项目后调用：有上次的快照就恢复，然后才允许保存。"""
        from . import session
        try:
            if is_project() and session.enabled():
                snap = session.load_session()
                if snap:
                    self.restore_session(snap, on_finished=self._session_restored)
                    return                     # 后台载入结束（done）后才允许保存
        except Exception:                      # noqa: BLE001
            logs.log.warning("恢复上次状态失败（已忽略）", exc_info=True)
        self._session_ready = True

    def _session_restored(self):
        self._session_ready = True

    def restore_session(self, snap, only=None, quiet=False, on_finished=None):
        """把快照应用到界面：处理参数、各页设置，并在后台重新载入当时的谱。
        only：只应用这些页面的设置（草稿用）；此时回到 only[0] 页，且**不改**全局处理参数。
        重新载入的谱按快照里的处理参数（归一化 / 背景 / FT）重算，使界面显示的参数与谱实际所用的一致。"""
        from . import session
        from xafsmith import pipeline as pl
        from types import SimpleNamespace
        S = self.S
        if only is None:
            session.apply_params(S, snap)
        session.apply_pages(snap, self.pages, only)
        names = [n for n in snap.get("groups", []) if n not in S.groups]
        page = snap.get("page") if only is None else (only[0] if only else None)
        root = paths.ROOT                      # 恢复期间若切换了项目，结果作废
        # 只携带参数的轻量对象，供 state.process 使用（在启动前复制，线程规则）
        par = SimpleNamespace(norm_par=dict(S.norm_par), bkg_par=dict(S.bkg_par), ft_par=dict(S.ft_par))
        session.apply_params(par, snap)

        def work():
            from .state import process
            cfg, meta, calib = pl.load_config(), pl.load_meta(), pl.load_calib()
            known = set(meta["sample"]) if len(meta) else set()
            out, lost = {}, []
            for n in names:
                if n not in known:
                    lost.append(n)
                    continue
                try:
                    g, _ = pl.build_sample(n, cfg, meta, calib)
                    out[n] = process(par, g)
                except Exception:              # noqa: BLE001
                    logs.log.warning("恢复谱 %s 失败", n, exc_info=True)
                    lost.append(n)
            return out, lost

        def done(r):
            if paths.ROOT != root:
                logs.log.info("恢复上次状态期间切换了项目，丢弃结果")
                return
            out, lost = r
            S.groups.update(out)
            if out:
                S.emit("groups")
            self.go(page if page in self.pages else self.S.extra.get("page", "data"))
            if page in self.pages:
                self.pages[page].refresh()
            if not quiet:
                msg = T(f"已恢复上次状态（{len(out)} 条谱；要换样品从头开始：“载入谱”页的“清空工作区”）",
                        f"Restored the last session ({len(out)} spectra; to start over with other samples: “Clear workspace” on the Load spectra page)")
                if lost:
                    msg += T(f"；{len(lost)} 条未能恢复（不在 meta.csv 登记表中，需重新读入）：" + ", ".join(lost[:3]),
                             f"; {len(lost)} could not be restored (not in meta.csv — load again): " + ", ".join(lost[:3]))
                self.toast(msg, "warn" if lost else "info")
            if on_finished:
                on_finished()

        def failed(msg=""):
            logs.log.warning("恢复上次状态失败：%s", msg)
            if paths.ROOT != root:
                return
            self.toast(T("恢复上次状态失败（详情见日志）", "Could not restore the last session (see the log)"), "warn")
            if on_finished:
                on_finished()                  # 出错也要放开保存，否则本次会话再也不会写快照
        if names:
            W.run_task(self, work, done, T("恢复上次状态…", "Restoring the last session…"), on_error=failed, key="restore", excl="groups")
        else:
            done(({}, []))

    def busy(self, on, text="", frac=None, cancel=None):
        """状态栏：on=忙碌；frac（0–1）有值时显示确定进度，否则为不确定动画；cancel 有值时显示“取消”按钮"""
        self.bar.setVisible(on)
        if on and frac is not None:
            self.bar.setRange(0, 1000)
            self.bar.setValue(int(max(0.0, min(1.0, frac)) * 1000))
            self.bar.setFormat(f"{frac * 100:.0f}%")
        else:
            self.bar.setRange(0, 0)
        self.busy_lbl.setText(text if on else "")
        self._cancel_cb = cancel if on else None
        self.cancel_btn.setVisible(on and cancel is not None)

    def toast(self, text, kind="ok"):
        """轻提示（成功 / 轻量信息）；持续性错误用页内 Banner（Page.notice），只有阻断性错误才用对话框"""
        self._toaster.show(text, kind)

    def show_disclaimer(self):
        self.open_help("about")

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
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.pop = None
        self._cache = (None, None)       # (data_key, 计数)：只在数据变了才重新数文件
        self.clicked.connect(self.toggle)

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
        QApplication.instance().installEventFilter(self)       # 点击弹窗外面即关闭

    def counts(self):
        """流程各步的计数；按 data_key 缓存（读表格和遍历文件夹较慢，每次弹出都做会卡）"""
        import pandas as pd
        from xafsmith import pipeline as pl
        from .state import feff_dirs
        S = self.win.S
        key = (S.data_key(), str(paths.ROOT))
        if self._cache[0] == key:
            return self._cache[1]
        try:
            nfit = len(pd.read_csv(paths.FITS_CSV, encoding="utf-8-sig")) if paths.FITS_CSV.exists() else 0
        except Exception:
            logs.log.debug("qt.app.counts 出错（已忽略或已提示）", exc_info=True)
            nfit = 0
        c = dict(meta=len(pl.load_meta()) if paths.META.exists() else 0, cal=len(S.calib),
                 proc=len(list(paths.PROC.glob("*"))) if paths.PROC.exists() else 0, feff=len(feff_dirs()), fit=nfit,
                 rep=len(list(paths.REPORTS.glob("*"))) if paths.REPORTS.exists() else 0)
        self._cache = (key, c)
        return c

    def eventFilter(self, obj, ev):
        from PySide6.QtCore import QEvent
        if self.pop is not None and ev.type() == QEvent.Type.MouseButtonPress:
            from PySide6.QtWidgets import QWidget as _W
            if isinstance(obj, _W) and obj is not self and not self.isAncestorOf(obj)                     and obj is not self.pop and not self.pop.isAncestorOf(obj):
                self.close_pop()
        return False

    def close_pop(self):
        QApplication.instance().removeEventFilter(self)
        if self.pop is not None:
            self.pop.hide()
            self.pop.deleteLater()
            self.pop = None


class FlowPopup(QFrame):
    """流程进度（每步可点击跳转）+ 本项目（已载入、拟合、参比）+ 常用文件夹"""

    def __init__(self, win, btn):
        super().__init__(win)
        from PySide6.QtGui import QColor
        from PySide6.QtWidgets import QGraphicsDropShadowEffect
        self.win, self.btn = win, btn
        self.setObjectName("flowPopup")
        self.setFixedWidth(400)
        sh = QGraphicsDropShadowEffect(self)
        sh.setBlurRadius(28)
        sh.setOffset(0, 6)
        sh.setColor(QColor(0, 0, 0, 60))
        self.setGraphicsEffect(sh)
        v = QVBoxLayout(self)
        v.setContentsMargins(SP['lg'], SP['md'], SP['lg'], SP['md'])
        v.setSpacing(4)
        S = win.S
        cn = btn.counts()
        nmeta, ncal, nproc, nfeff, nfit, nrep = cn["meta"], cn["cal"], cn["proc"], cn["feff"], cn["fit"], cn["rep"]
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
            row = QHBoxLayout(b)
            row.setContentsMargins(8, 4, 8, 4)
            row.setSpacing(10)
            num = QLabel("✓" if done else str(i + 1))
            num.setFixedSize(22, 22)
            num.setAlignment(Qt.AlignmentFlag.AlignCenter)
            state = "done" if done else ("next" if i == nxt else "todo")
            num.setObjectName("flowNum")
            num.setProperty("state", state)
            b.setProperty("state", state)
            tx = QLabel(f"<b>{name}</b>&nbsp;&nbsp;<span style='color:{C['text3']}'>{sub}</span>")
            tx.setTextFormat(Qt.TextFormat.RichText)
            for x in (num, tx):
                x.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
            row.addWidget(num)
            row.addWidget(tx, 1)
            b.setMinimumHeight(38)
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
                            (T("保存处理参数", "Save parameters"), "save", save_session),
                            (T("清空工作区", "Clear workspace"), "refresh",
                             lambda: (self.btn.close_pop(), self.win.clear_workspace()))):
            g.addWidget(W.button(txt, icon_name=ic, slot=fn))
        v.addSpacing(4)
        v.addLayout(g)


def make_window(project=None, lang=None):
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
    app.aboutToQuit.connect(W.shutdown_tasks)       # 退出前等后台线程结束（否则 Qt 会 abort）
    app.setApplicationName("XAFSmith")
    app.setStyle("Fusion")
    theme.force_light(app)
    theme.install_resources()
    theme.round_popups(app)
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


def run(project=None, splash=None):
    _no_console_output()
    from xafsmith import logs
    logs.install_excepthook(_error_dialog)
    app, w = make_window(project)
    w.restore_geometry()
    w.show()
    if splash is not None:
        splash.finish(w)
    QTimer.singleShot(400, w.start_background)
    QTimer.singleShot(0, w.start_session)
    return app.exec()


if __name__ == "__main__":
    sys.exit(run(sys.argv[1] if len(sys.argv) > 1 else None))
