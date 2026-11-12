"""外观：颜色、字体、样式表、线条图标、matplotlib 样式。

设计参考 Claude 桌面版：暖米色底、白色卡片、细边框大圆角、衬线标题；强调色取图标边框的蓝色 #266EC4，
内容区底部一行居中的小字提示。只有一套浅色主题（强制浅色，不跟随系统深色）。
"""
from __future__ import annotations

from PySide6.QtCore import QByteArray, QRectF, Qt
from PySide6.QtGui import QIcon, QPainter, QPixmap
from PySide6.QtSvg import QSvgRenderer

LIGHT = dict(
    bg="#FAF9F5", side="#F3F1EA", card="#FFFFFF", raised="#FFFFFF",
    border="#E6E3D9", border2="#D9D5C8", hover="#ECE9DF", select="#E6E2D6",
    text="#1F1E1D", text2="#5E5D59", text3="#8A8880",
    accent="#266EC4", accent_h="#1F5DA8", accent_soft="#E3ECF7", accent_text="#1F5DA8",
    ok="#2F7D4F", ok_soft="#E3F1E8", warn="#A86A12", warn_soft="#FAF0DC", err="#B3372B", err_soft="#F8E3E0",
    magenta="#B5487A", gold="#A98512",
    info_soft="#EEF0F5", code="#F3F1EA", plot_bg="#FFFFFF", grid="#EEECE4",
)
C = LIGHT   # 只有一套浅色主题

# 设计令牌：字号 5 级（pt）、间距（px）、固定宽度（px）。样式表与页面都从这里取值，不再散落魔法数字。
FS = dict(xs=8.5, sm=9.5, base=10, lg=12, xl=18)
SP = dict(xs=4, sm=8, md=12, lg=16, xl=24)
WIDTH = dict(sidebar=250, help_sidebar=230, toc=220, popup_min=260, nav_min=190)

SANS = '"Segoe UI", "Microsoft YaHei UI", "PingFang SC", "Noto Sans SC", sans-serif'
SERIF = '"Cambria", "Microsoft YaHei UI", serif'   # Cambria：等高数字（Georgia 的 0 像 o，不适合数据）
MONO = '"Cascadia Mono", Consolas, "Microsoft YaHei UI", monospace'

# 数据曲线配色（色盲友好）
SERIES = ["#266EC4", "#D0812A", "#3E8E5E", "#8E5BB5", "#B5487A", "#2A9DA6", "#A98512", "#6B6A64"]   # 与白底对比度均 ≥3:1（tools 里可复算）


def force_light(app):
    """锁定浅色：Fusion 会跟随 Windows 深色设置，消息框、文件对话框等用的是调色板，所以显式设一套浅色 QPalette。"""
    from PySide6.QtGui import QColor, QPalette
    try:
        app.styleHints().setColorScheme(Qt.ColorScheme.Light)
    except Exception:
        pass
    c = C
    p = QPalette()
    R = QPalette.ColorRole
    for role, key in ((R.Window, "bg"), (R.WindowText, "text"), (R.Base, "card"), (R.AlternateBase, "bg"),
                      (R.Text, "text"), (R.Button, "card"), (R.ButtonText, "text"), (R.ToolTipBase, "text"),
                      (R.ToolTipText, "bg"), (R.Highlight, "accent"), (R.Link, "accent_text"),
                      (R.PlaceholderText, "text3"), (R.BrightText, "err")):
        p.setColor(role, QColor(c[key]))
    p.setColor(R.HighlightedText, QColor("#FFFFFF"))
    for role in (R.WindowText, R.Text, R.ButtonText):
        p.setColor(QPalette.ColorGroup.Disabled, role, QColor(c["text3"]))
    app.setPalette(p)


class _RoundPopups:
    """让下拉框与菜单的弹出窗口背景透明，样式表里的圆角才不会在外面露出方角（Windows）。"""
    _inst = None

    @classmethod
    def install(cls, app):
        from PySide6.QtCore import QEvent, QObject
        from PySide6.QtWidgets import QMenu

        class F(QObject):
            def eventFilter(self, o, e):
                if e.type() == QEvent.Type.Polish and (isinstance(o, QMenu) or o.metaObject().className() == "QComboBoxPrivateContainer"):
                    if not o.testAttribute(Qt.WidgetAttribute.WA_TranslucentBackground):
                        o.setWindowFlags(o.windowFlags() | Qt.WindowType.FramelessWindowHint | Qt.WindowType.NoDropShadowWindowHint)
                        o.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
                return False
        cls._inst = F(app)
        app.installEventFilter(cls._inst)


def round_popups(app):
    _RoundPopups.install(app)


def qss() -> str:
    c = C
    return f"""
* {{ font-family: {SANS}; font-size: {FS['base']}pt; color: {c['text']}; }}
QMainWindow, QWidget#root, QWidget#main {{ background: {c['bg']}; }}
QWidget#sidebar {{ background: {c['side']}; border-right: 1px solid {c['border']}; }}
QScrollArea, QScrollArea > QWidget > QWidget#page {{ background: {c['bg']}; border: none; }}
QWidget#page {{ background: {c['bg']}; }}

QLabel#brand {{ font-family: {SERIF}; font-size: {FS['xl']}pt; color: {c['text']}; }}
QLabel#credit {{ color: {c['text3']}; font-size: {FS['xs']}pt; }}
QLabel#creditName {{ color: {c['accent_text']}; font-size: {FS['xs']}pt; font-weight: 600; }}
QLabel#h1 {{ font-family: {SERIF}; font-size: {FS['xl']}pt; color: {c['text']}; }}
QLabel#h2 {{ font-size: {FS['lg']}pt; font-weight: 600; color: {c['text']}; }}
QLabel#h3 {{ font-size: {FS['base']}pt; font-weight: 600; color: {c['text']}; }}
QLabel#muted {{ color: {c['text2']}; }}
QLabel#faint {{ color: {c['text3']}; font-size: {FS['sm']}pt; }}
QLabel#footnote {{ color: {c['text2']}; font-size: {FS['sm']}pt; }}
QLabel#metricValue {{ font-family: {SERIF}; font-size: {FS['xl']}pt; color: {c['text']}; }}
QLabel#metricLabel {{ color: {c['text3']}; font-size: {FS['xs']}pt; }}
QLabel#pill {{ border-radius: 10px; padding: 2px 10px; font-size: {FS['xs']}pt; font-weight: 600; }}
QLabel#navGap {{ background: transparent; }}

QFrame#card {{ background: {c['card']}; border: 1px solid {c['border']}; border-radius: 14px; }}
QFrame#flat {{ background: transparent; border: none; }}
QFrame#hline {{ background: {c['border']}; max-height: 1px; min-height: 1px; border: none; }}
QFrame#banner_info {{ background: {c['info_soft']}; border-radius: 10px; }}
QFrame#banner_ok {{ background: {c['ok_soft']}; border-radius: 10px; }}
QFrame#banner_warn {{ background: {c['warn_soft']}; border-radius: 10px; }}
QFrame#banner_err {{ background: {c['err_soft']}; border-radius: 10px; }}
QFrame#projectCard {{ background: {c['card']}; border: 1px solid {c['border']}; border-radius: 12px; }}

/* 侧栏导航 */
QPushButton#nav {{ text-align: left; border: none; border-radius: 9px; padding: 5px 10px; background: transparent;
    color: {c['text2']}; font-size: {FS['base']}pt; }}
QPushButton#nav[hint="true"] {{ color: {c['text3']}; }}
QListWidget#toc {{ background: {c['side']}; border: none; border-left: 1px solid {c['border']}; padding: 8px 4px; outline: 0; }}
QListWidget#toc::item {{ padding: 5px 8px; border-radius: 6px; color: {c['text2']}; font-size: {FS['sm']}pt; }}
QListWidget#toc::item:hover {{ background: {c['hover']}; }}
QListWidget#toc::item:selected {{ background: {c['select']}; color: {c['text']}; }}
QPushButton#nav:hover {{ background: {c['hover']}; color: {c['text']}; }}
QPushButton#nav:checked {{ background: {c['select']}; color: {c['text']}; font-weight: 600; }}
QPushButton#newProject {{ text-align: left; border: 1px solid {c['border2']}; border-radius: 10px; padding: 8px 12px;
    background: {c['card']}; color: {c['text']}; font-weight: 600; }}
QPushButton#newProject:hover {{ background: {c['raised']}; border-color: {c['text3']}; }}
QPushButton#seg {{ border: 1px solid {c['border2']}; background: transparent; padding: 3px 12px; color: {c['text2']};
    font-size: {FS['sm']}pt; border-radius: 0; }}
QPushButton#seg[pos="first"], QPushButton#seg[pos="only"] {{ border-top-left-radius: 9px; border-bottom-left-radius: 9px; }}
QPushButton#seg[pos="last"], QPushButton#seg[pos="only"] {{ border-top-right-radius: 9px; border-bottom-right-radius: 9px; }}
QPushButton#seg[pos="mid"], QPushButton#seg[pos="last"] {{ margin-left: -1px; }}
QPushButton#seg:checked {{ background: {c['text']}; color: {c['bg']}; border-color: {c['text']}; }}

/* 按钮 */
QPushButton {{ background: {c['card']}; border: 1px solid {c['border2']}; border-radius: 9px; padding: 6px 14px;
    color: {c['text']}; }}
QPushButton:hover {{ background: {c['hover']}; }}
QPushButton:pressed {{ background: {c['select']}; }}
QPushButton:disabled {{ color: {c['text3']}; border-color: {c['border']}; background: transparent; }}
QPushButton#primary {{ background: {c['accent']}; color: #FFFFFF; border: 1px solid {c['accent']}; font-weight: 600;
    padding: 7px 18px; }}
QPushButton#primary:hover {{ background: {c['accent_h']}; border-color: {c['accent_h']}; }}
QPushButton#primary:disabled {{ background: {c['border']}; border-color: {c['border']}; color: {c['text3']}; }}
QPushButton#link {{ border: none; background: transparent; color: {c['accent_text']}; padding: 2px 4px; }}
QPushButton#link:hover {{ text-decoration: underline; }}
QToolButton {{ border: 1px solid transparent; border-radius: 8px; padding: 4px; background: transparent; }}
QToolButton:hover {{ background: {c['hover']}; }}
QToolButton:checked {{ background: {c['select']}; }}
QPushButton#combo {{ border: 1px solid {c['border2']}; border-radius: 9px; padding: 6px 10px; background: {c['card']};
    text-align: left; font-weight: normal; }}
QPushButton#combo:hover {{ border-color: {c['text3']}; background: {c['card']}; }}
QToolButton::menu-indicator {{ image: none; width: 0; }}

/* 输入 */
QLineEdit, QComboBox, QDoubleSpinBox, QSpinBox, QPlainTextEdit#input {{ background: {c['card']};
    border: 1px solid {c['border2']}; border-radius: 9px; padding: 5px 9px; min-height: 20px;
    selection-background-color: {c['accent_soft']}; selection-color: {c['text']}; }}
QLineEdit:hover, QComboBox:hover, QDoubleSpinBox:hover, QSpinBox:hover {{ border-color: {c['text3']}; }}
QLineEdit:focus, QComboBox:focus, QDoubleSpinBox:focus, QSpinBox:focus, QPlainTextEdit#input:focus {{
    border-color: {c['accent']}; }}
QAbstractSpinBox::up-button, QAbstractSpinBox::down-button {{ subcontrol-origin: border; width: 18px;
    border: none; background: transparent; }}
QAbstractSpinBox::up-button {{ subcontrol-position: top right; }}
QAbstractSpinBox::down-button {{ subcontrol-position: bottom right; }}
QAbstractSpinBox::up-arrow {{ image: url(xs:chevup); width: 8px; height: 8px; }}
QAbstractSpinBox::down-arrow {{ image: url(xs:chev); width: 8px; height: 8px; }}
QAbstractSpinBox::up-button:hover, QAbstractSpinBox::down-button:hover {{ background: {c['hover']}; }}
QAbstractSpinBox QLineEdit {{ border: none; padding: 0 0 0 2px; margin: 0; background: transparent; min-height: 0; }}
QLineEdit[invalid="true"], QDoubleSpinBox[invalid="true"] {{ border: 1px solid {c['err']}; }}
QLineEdit:disabled, QComboBox:disabled, QDoubleSpinBox:disabled, QSpinBox:disabled, QPlainTextEdit#input:disabled {{ color: {c['text3']}; background: {c['bg']}; }}
QComboBox::drop-down {{ border: none; width: 22px; }}
QComboBox::down-arrow {{ image: url(xs:chev); width: 10px; height: 10px; }}
QComboBoxPrivateContainer {{ background: transparent; border: none; }}
QComboBox QAbstractItemView {{ background: {c['raised']}; border: 1px solid {c['border']}; border-radius: 10px;
    padding: 4px; outline: 0; selection-background-color: {c['hover']}; selection-color: {c['text']}; }}
QCheckBox {{ spacing: 7px; }}
QCheckBox::indicator {{ width: 16px; height: 16px; border-radius: 5px; border: 1px solid {c['border2']};
    background: {c['card']}; }}
QCheckBox::indicator:hover {{ border-color: {c['text3']}; }}
QCheckBox::indicator:checked {{ background: {c['accent']}; border-color: {c['accent']}; image: url(xs:tick); }}
QListWidget::indicator, QTableView::indicator {{ width: 16px; height: 16px; border-radius: 5px;
    border: 1px solid {c['border2']}; background: {c['card']}; }}
QListWidget::indicator:hover, QTableView::indicator:hover {{ border-color: {c['accent']}; }}
QListWidget::indicator:checked, QTableView::indicator:checked {{ background: {c['accent']}; border-color: {c['accent']};
    image: url(xs:tick); }}
QRadioButton {{ spacing: 7px; }}

/* 菜单与提示 */
QMenu {{ background: {c['raised']}; border: 1px solid {c['border']}; border-radius: 12px; padding: 6px; }}
QMenu::item {{ padding: 6px 26px 6px 10px; border-radius: 7px; }}
QMenu::item:selected {{ background: {c['hover']}; }}
QMenu::indicator {{ width: 14px; height: 14px; left: 6px; }}
QMenu::separator {{ height: 1px; background: {c['border']}; margin: 5px 6px; }}
QToolTip {{ background: {c['text']}; color: {c['bg']}; border: none; border-radius: 7px; padding: 6px 9px; }}

/* 表格 */
QTableView {{ background: {c['card']}; border: 1px solid {c['border']}; border-radius: 10px;
    gridline-color: {c['border']}; selection-background-color: {c['accent_soft']}; selection-color: {c['text']};
    alternate-background-color: {c['bg']}; }}
QTableView::item {{ padding: 3px 8px; }}
QHeaderView {{ background: transparent; border: none; border-top-left-radius: 9px; border-top-right-radius: 9px; }}
QHeaderView::section {{ background: {c['card']}; color: {c['text3']}; border: none;
    border-bottom: 1px solid {c['border']}; padding: 6px 8px; font-size: {FS['sm']}pt; font-weight: 600; }}
QHeaderView::section:first {{ border-top-left-radius: 9px; }}
QHeaderView::section:last {{ border-top-right-radius: 9px; }}
QHeaderView::section:only-one {{ border-top-left-radius: 9px; border-top-right-radius: 9px; }}
QTableCornerButton::section {{ background: {c['card']}; border: none; }}
QListWidget {{ background: {c['card']}; border: 1px solid {c['border']}; border-radius: 10px; padding: 4px; outline: 0; }}
QListWidget::item {{ padding: 4px 6px; border-radius: 6px; }}
QListWidget::item:hover {{ background: {c['hover']}; }}
QListWidget::item:selected {{ background: {c['select']}; color: {c['text']}; }}

QPlainTextEdit#code, QTextBrowser#code {{ background: {c['code']}; border: 1px solid {c['border']}; border-radius: 10px;
    font-family: {MONO}; font-size: {FS['sm']}pt; padding: 8px; }}
QTextBrowser#doc {{ background: transparent; border: none; font-size: {FS['base']}pt; }}
QTextBrowser#prose {{ background: {c['card']}; border: 1px solid {c['border']}; border-radius: 12px; padding: 10px 14px;
    font-family: {SERIF}; font-size: {FS['lg']}pt; }}

/* 分页 */
QTabWidget::pane {{ border: none; }}
QTabBar {{ qproperty-drawBase: 0; }}
QTabBar::tab {{ background: transparent; border: none; padding: 6px 14px; margin-right: 4px; color: {c['text2']};
    border-radius: 8px; }}
QTabBar::tab:hover {{ background: {c['hover']}; color: {c['text']}; }}
QTabBar::tab:selected {{ background: {c['select']}; color: {c['text']}; font-weight: 600; }}

QProgressBar {{ background: {c['border']}; border: none; border-radius: 3px; max-height: 6px; }}
QProgressBar::chunk {{ background: {c['accent']}; border-radius: 3px; }}
QScrollBar:vertical {{ width: 10px; background: transparent; margin: 2px; }}
QScrollBar:horizontal {{ height: 10px; background: transparent; margin: 2px; }}
QScrollBar::handle {{ background: {c['border2']}; border-radius: 4px; min-height: 28px; min-width: 28px; }}
QScrollBar::handle:hover {{ background: {c['text3']}; }}
QScrollBar::add-line, QScrollBar::sub-line, QScrollBar::add-page, QScrollBar::sub-page {{ height: 0; width: 0;
    background: none; }}
QSplitter::handle {{ background: transparent; }}
QDialog {{ background: {c['bg']}; }}

/* 主窗口部件（原内联样式） */
QProgressBar#topBar {{ background: {c['card']}; border: 1px solid {c['border']}; border-radius: 8px; min-height: 16px; max-height: 16px; min-width: {WIDTH['nav_min']}px; max-width: {WIDTH['nav_min']}px; text-align: center; color: {c['text']}; font-size: {FS['xs']}pt; }}
QProgressBar#topBar::chunk {{ background: {c['accent_soft']}; border-radius: 7px; }}
QScrollArea#navScroll {{ background: {c['side']}; border: none; }}
QWidget#navInner {{ border: none; }}
QLabel#pill[kind="ok"] {{ background: {c['ok_soft']}; color: {c['ok']}; }}
QLabel#pill[kind="warn"] {{ background: {c['warn_soft']}; color: {c['warn']}; }}
QLabel#pill[kind="err"] {{ background: {c['err_soft']}; color: {c['err']}; }}
QLabel#pill[kind="info"] {{ background: {c['info_soft']}; color: {c['text2']}; }}
QToolButton#collapse {{ font-weight: 600; color: {c['text']}; padding: 4px 2px; border: none; }}
QToolButton#collapse:hover {{ color: {c['accent']}; background: transparent; }}
QListWidget#plain {{ border: none; background: transparent; }}
QPushButton#ptEl {{ padding: 0; border-radius: 6px; font-size: {FS['sm']}pt; font-weight: 600; border: 1px solid {c['border']};
    background: {c['card']}; color: {c['text']}; }}
QPushButton#ptEl:hover {{ border-color: {c['accent']}; }}
QPushButton#ptEl:checked {{ border-color: {c['accent']}; background: {c['accent']}; color: #FFFFFF; }}
QLabel#toast {{ background: {c['text']}; color: {c['bg']}; border-radius: 10px; padding: 9px 16px;
    border-left: 4px solid {c['text2']}; }}
QLabel#toast[kind="ok"] {{ border-left-color: {c['ok']}; }}
QLabel#toast[kind="warn"] {{ border-left-color: {c['warn']}; }}
QLabel#toast[kind="err"] {{ border-left-color: {c['err']}; }}
QPushButton#flowBtn {{ background: {c['accent_soft']}; color: {c['accent_text']}; font-weight: 600;
    border: 1px solid {c['accent']}; border-radius: 13px; padding: 4px 14px; min-height: 18px; }}
QPushButton#flowBtn:hover {{ background: {c['accent']}; color: #FFFFFF; }}
QPushButton#flowBtn:disabled {{ background: transparent; color: {c['text3']}; border-color: {c['border']}; }}
QFrame#flowPopup {{ background: {c['card']}; border: 1px solid {c['border2']}; border-radius: 14px; }}
QLabel#flowNum {{ border-radius: 11px; font-weight: 600; font-size: {FS['sm']}pt; color: {c['text3']}; background: {c['hover']}; }}
QLabel#flowNum[state="done"] {{ color: {c['ok']}; background: {c['ok_soft']}; }}
QLabel#flowNum[state="next"] {{ color: {c['accent_text']}; background: {c['accent_soft']}; }}
QPushButton#flowStep {{ text-align: left; border-radius: 8px; background: transparent; border: none; }}
QPushButton#flowStep[state="next"] {{ border: 1.5px solid {c['accent']}; }}
QPushButton#flowStep:hover {{ background: {c['hover']}; }}
"""


# 24×24 线条图标（本软件自绘）
_ICONS = {
    "home": '<path d="M4 11.5 12 5l8 6.5"/><path d="M6 10v9h4.5v-5h3v5H18v-9"/>',
    "plus": '<path d="M12 5v14M5 12h14"/>',
    "folder": '<path d="M3.5 7a1.5 1.5 0 0 1 1.5-1.5h4l2 2h8a1.5 1.5 0 0 1 1.5 1.5v8.5A1.5 1.5 0 0 1 19 19H5a1.5 1.5 0 0 1-1.5-1.5z"/>',
    "table": '<rect x="4" y="5" width="16" height="14" rx="2"/><path d="M4 10h16M10 10v9"/>',
    "bolt": '<path d="M13 3 5 13.5h6L10 21l8-10.5h-6z"/>',
    "upload": '<path d="M12 15V4"/><path d="M7.5 8.5 12 4l4.5 4.5"/><path d="M5 15v3.5A1.5 1.5 0 0 0 6.5 20h11a1.5 1.5 0 0 0 1.5-1.5V15"/>',
    "shield": '<path d="M12 3.5 5 6v5.5c0 4.2 3 7.5 7 9 4-1.5 7-4.8 7-9V6z"/><path d="m9 12 2 2 4-4"/>',
    "target": '<circle cx="12" cy="12" r="7.5"/><circle cx="12" cy="12" r="3"/><path d="M12 2.5v3M12 18.5v3M2.5 12h3M18.5 12h3"/>',
    "edge": '<path d="M3 18h5.5c2 0 2.4-12 4.5-12s2 5 4 5h4"/>',
    "wave": '<path d="M3 12c1.5-5 3-5 4.5 0s3 5 4.5 0 3-5 4.5 0 3 5 4.5 0"/>',
    "grid": '<rect x="4" y="4" width="7" height="7" rx="1.5"/><rect x="13" y="4" width="7" height="7" rx="1.5"/>'
            '<rect x="4" y="13" width="7" height="7" rx="1.5"/><rect x="13" y="13" width="7" height="7" rx="1.5"/>',
    "atom": '<circle cx="12" cy="12" r="1.6"/><ellipse cx="12" cy="12" rx="9" ry="3.6"/>'
            '<ellipse cx="12" cy="12" rx="9" ry="3.6" transform="rotate(60 12 12)"/>'
            '<ellipse cx="12" cy="12" rx="9" ry="3.6" transform="rotate(120 12 12)"/>',
    "fit": '<path d="M3 17c3 0 4-9 7-9s3 6 5 6 3-4 6-4"/><circle cx="6" cy="14" r=".9"/><circle cx="10" cy="8.4" r=".9"/>'
           '<circle cx="14" cy="13" r=".9"/><circle cx="18.5" cy="10.5" r=".9"/>',
    "history": '<path d="M4 12a8 8 0 1 0 2.4-5.7"/><path d="M4 5v3.5h3.5"/><path d="M12 8v4.5l3 2"/>',
    "layers": '<path d="M12 4 3.5 8.5 12 13l8.5-4.5z"/><path d="m3.5 12.5 8.5 4.5 8.5-4.5"/>',
    "peak": '<path d="M3 19h18"/><path d="M5 19c2 0 3-3 4-7s1.5-7 3-7 2 3 3 7 2 7 4 7"/>',
    "doc": '<path d="M14 3.5H7.5A1.5 1.5 0 0 0 6 5v14a1.5 1.5 0 0 0 1.5 1.5h9A1.5 1.5 0 0 0 18 19V7.5z"/>'
           '<path d="M14 3.5v4h4M9 12h6M9 15.5h6"/>',
    "chart": '<path d="M4 4v16h16"/><path d="m7.5 14 3.5-4 3 2.5 4.5-6"/>',
    "quote": '<path d="M5 6h14M5 10h14M5 14h9M5 18h6"/>',
    "flask": '<path d="M9.5 3.5h5M10.5 3.5v5.5L5 18.5a1.5 1.5 0 0 0 1.3 2h11.4a1.5 1.5 0 0 0 1.3-2L13.5 9V3.5"/><path d="M7.5 15h9"/>',
    "spark": '<path d="M12 3v4M12 17v4M3 12h4M17 12h4M5.6 5.6l2.8 2.8M15.6 15.6l2.8 2.8M5.6 18.4l2.8-2.8M15.6 8.4l2.8-2.8"/>',
    "help": '<circle cx="12" cy="12" r="8.5"/><path d="M9.6 9.5a2.5 2.5 0 0 1 4.8.9c0 1.7-2.4 2.1-2.4 3.6"/><circle cx="12" cy="17" r=".6"/>',
    "copy": '<rect x="8.5" y="8.5" width="11" height="11" rx="2"/><path d="M15.5 8.5V6a1.5 1.5 0 0 0-1.5-1.5H6A1.5 1.5 0 0 0 4.5 6v8A1.5 1.5 0 0 0 6 15.5h2.5"/>',
    "download": '<path d="M12 4v11"/><path d="M7.5 10.5 12 15l4.5-4.5"/><path d="M5 19.5h14"/>',
    "external": '<path d="M13.5 4.5h6v6"/><path d="M19.5 4.5 11 13"/><path d="M17.5 14v4a1.5 1.5 0 0 1-1.5 1.5H6A1.5 1.5 0 0 1 4.5 18V8A1.5 1.5 0 0 1 6 6.5h4"/>',
    "chev": '<path d="m7 10 5 5 5-5"/>',
    "chevup": '<path d="m7 14 5-5 5 5"/>',
    "check": '<path d="m5 12.5 4.5 4.5L19 7.5"/>',
    "info": '<circle cx="12" cy="12" r="8.5"/><path d="M12 11v5.5"/><circle cx="12" cy="7.8" r=".6"/>',
    "alert": '<path d="M12 4 2.8 19.5h18.4z"/><path d="M12 10v4.5"/><circle cx="12" cy="17" r=".6"/>',
    "x": '<path d="M6.5 6.5l11 11M17.5 6.5l-11 11"/>',
    "zoomreset": '<path d="M4 9V4h5M20 9V4h-5M4 15v5h5M20 15v5h-5"/>',
    "pan": '<path d="M12 3v18M3 12h18"/><path d="m9 6 3-3 3 3M9 18l3 3 3-3M6 9l-3 3 3 3M18 9l3 3-3 3"/>',
    "zoom": '<circle cx="11" cy="11" r="6.5"/><path d="m20 20-4.4-4.4"/>',
    "save": '<path d="M5.5 4h10L19.5 8v10.5A1.5 1.5 0 0 1 18 20H6a1.5 1.5 0 0 1-1.5-1.5v-13A1.5 1.5 0 0 1 5.5 4z"/><path d="M8 4v4.5h7V4M8 20v-6h8v6"/>',
    "play": '<path d="M8 5.5v13l10.5-6.5z"/>',
    "refresh": '<path d="M19.5 12A7.5 7.5 0 1 1 17 6.4"/><path d="M19.5 4v4h-4"/>',
    "globe": '<circle cx="12" cy="12" r="8.5"/><path d="M3.5 12h17M12 3.5c2.5 2.6 3.5 5.4 3.5 8.5s-1 5.9-3.5 8.5c-2.5-2.6-3.5-5.4-3.5-8.5s1-5.9 3.5-8.5"/>',
}


def svg(name: str, color: str | None = None, width: float = 1.6) -> str:
    col = color or C["text2"]
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="{col}" '
            f'stroke-width="{width}" stroke-linecap="round" stroke-linejoin="round">{_ICONS.get(name, "")}</svg>')


def icon(name: str, color: str | None = None, size: int = 18, width: float = 1.6,
         on: str | None = None, disabled: str | None = None) -> QIcon:
    """线条图标。on：按钮选中（checked）时的颜色；disabled：禁用时的颜色（默认 text3 的淡色，避免白色图标在浅底上消失）。"""
    ic = QIcon()
    variants = [(color, QIcon.Mode.Normal, QIcon.State.Off)]
    if on:
        variants += [(on, QIcon.Mode.Normal, QIcon.State.On), (on, QIcon.Mode.Active, QIcon.State.On)]
    if disabled:
        variants.append((disabled, QIcon.Mode.Disabled, QIcon.State.Off))
    for col, mode, state in variants:
        r = QSvgRenderer(QByteArray(svg(name, col, width).encode()))
        for scale in (1, 1.5, 2, 3):          # 各缩放档位各一张，Qt 按屏幕 devicePixelRatio 选最接近的
            s = round(size * scale)
            pm = QPixmap(s, s)
            pm.fill(Qt.GlobalColor.transparent)
            p = QPainter(pm)
            p.setRenderHint(QPainter.RenderHint.Antialiasing)
            r.render(p, QRectF(0, 0, s, s))
            p.end()
            pm.setDevicePixelRatio(scale)
            ic.addPixmap(pm, mode, state)
    return ic


def install_resources():
    """把下拉箭头、勾选标记写成临时文件供样式表引用（Qt 资源路径 :/xs/...）"""
    import tempfile
    from pathlib import Path
    from PySide6.QtCore import QDir
    d = Path(tempfile.gettempdir()) / "xafsmith_qt"
    d.mkdir(exist_ok=True)
    (d / "chev").write_text(svg("chev", C["text3"], 2.2), encoding="utf-8")
    (d / "chevup").write_text(svg("chevup", C["text3"], 2.2), encoding="utf-8")
    (d / "tick").write_text(svg("check", "#FFFFFF", 2.6), encoding="utf-8")
    QDir.setSearchPaths("xs", [str(d)])


def mpl_style():
    import matplotlib
    c = C
    rc = matplotlib.rcParams
    rc["font.family"] = ["Segoe UI", "Microsoft YaHei", "Arial", "DejaVu Sans"]
    rc["font.size"] = 9
    rc["axes.unicode_minus"] = False
    rc["figure.facecolor"] = c["plot_bg"]
    rc["axes.facecolor"] = c["plot_bg"]
    rc["savefig.facecolor"] = c["plot_bg"]
    rc["axes.edgecolor"] = c["border2"]
    rc["axes.labelcolor"] = c["text2"]
    rc["axes.titlecolor"] = c["text"]
    rc["axes.titlesize"] = 9.5
    rc["axes.linewidth"] = 0.8
    rc["axes.spines.top"] = False
    rc["axes.spines.right"] = False
    rc["axes.grid"] = True
    rc["grid.color"] = c["grid"]
    rc["grid.linewidth"] = 0.7
    rc["xtick.color"] = c["text3"]
    rc["ytick.color"] = c["text3"]
    rc["xtick.labelcolor"] = c["text2"]
    rc["ytick.labelcolor"] = c["text2"]
    rc["legend.frameon"] = False
    rc["legend.fontsize"] = 8.5
    rc["legend.labelcolor"] = c["text"]
    rc["lines.linewidth"] = 1.4
    from cycler import cycler
    rc["axes.prop_cycle"] = cycler(color=SERIES)
