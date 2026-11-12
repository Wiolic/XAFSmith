"""文字展示：代码块、复制按钮、富文本浏览器、独立信息窗口、确认对话框。"""

from __future__ import annotations

import re

from PySide6.QtCore import QEvent, QObject, Qt, QTimer
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import QLabel, QMessageBox, QPlainTextEdit, QTextBrowser, QVBoxLayout, QWidget
from ..theme import C, SP

from .core import T
from .basic import button, hbox


def copy_to_clipboard(text_):
    QGuiApplication.clipboard().setText(text_)


def copy_button(get_text, label_=None):
    b = button(label_ or T("复制", "Copy"), icon_name="copy")

    def go():
        copy_to_clipboard(get_text() if callable(get_text) else get_text)
        old = b.text()
        b.setText(T("已复制 ✓", "Copied ✓"))
        QTimer.singleShot(1400, lambda: b.setText(old))
    b.clicked.connect(go)
    return b


def code_block(text_, copy=False, height=None, wrap=False):
    e = QPlainTextEdit(text_)
    e.setObjectName("code")
    e.setReadOnly(True)
    e.setLineWrapMode(QPlainTextEdit.LineWrapMode.WidgetWidth if wrap else QPlainTextEdit.LineWrapMode.NoWrap)
    lines = text_.count("\n") + 1
    lh = e.fontMetrics().lineSpacing()                      # 行高随字体与缩放
    e.setFixedHeight(height or min(22 * lh, max(2 * lh + 6, lines * lh + 28)))
    if not copy:
        return e
    w = QWidget()
    lay = QVBoxLayout(w)
    lay.setContentsMargins(0, 0, 0, 0)
    lay.setSpacing(6)
    lay.addWidget(e)
    lay.addWidget(hbox(None, copy_button(text_)))
    return w


_CARD = re.compile(r"^xscard_(\d+)_(\d+)_(.*)$")
_MATH_DPR = re.compile(r"_x(\d+(?:\.\d+)?)\.png$")
_PAD, _RADIUS = 8, 8


def _image_frags(doc):
    """文档中所有图片片段：[(位置, 长度, QTextImageFormat)]"""
    out = []
    blk = doc.begin()
    while blk.isValid():
        it = blk.begin()
        while not it.atEnd():
            frag = it.fragment()
            it += 1
            if frag.isValid() and frag.charFormat().isImageFormat():
                out.append((frag.position(), frag.length(), frag.charFormat().toImageFormat()))
        blk = blk.next()
    return out


def _has_image(blk):
    it = blk.begin()
    while not it.atEnd():
        frag = it.fragment()
        it += 1
        if frag.isValid() and frag.charFormat().isImageFormat():
            return True
    return False


def _load_image(tb, name):
    """按资源名取原图（QImage）；找不到返回 None"""
    from PySide6.QtCore import QUrl
    from PySide6.QtGui import QImage, QPixmap, QTextDocument
    cache = tb.__dict__.setdefault("_xs_src", {})
    if name in cache:
        return cache[name]
    kind = QTextDocument.ResourceType.ImageResource.value
    res = tb.document().resource(kind, QUrl(name))
    if res is None or (isinstance(res, (bytes, bytearray)) and not res):
        res = tb.loadResource(kind, QUrl(name))
    if isinstance(res, QPixmap):
        res = res.toImage()
    elif not isinstance(res, QImage) and res is not None:
        try:
            res = QImage.fromData(bytes(res))
        except (TypeError, ValueError):
            res = None
    img = res if isinstance(res, QImage) and res.width() > 0 else None
    cache[name] = img
    return img


def _card(img, inner_w, dpr):
    """原图 → 平滑缩放 + 白底圆角卡片（1 px 边框、留白）；返回 (QImage, 逻辑宽, 逻辑高)"""
    from PySide6.QtCore import QRectF, Qt as _Qt
    from PySide6.QtGui import QColor, QImage, QPainter, QPainterPath, QPen
    sw = max(1, round(inner_w * dpr))
    sc = img.scaledToWidth(sw, _Qt.TransformationMode.SmoothTransformation)
    pad = round(_PAD * dpr)
    out = QImage(sc.width() + 2 * pad, sc.height() + 2 * pad, QImage.Format.Format_ARGB32_Premultiplied)
    out.fill(0)
    p = QPainter(out)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
    r = QRectF(0.5, 0.5, out.width() - 1, out.height() - 1)
    path = QPainterPath()
    path.addRoundedRect(r, _RADIUS * dpr, _RADIUS * dpr)
    p.fillPath(path, QColor("#FFFFFF"))
    p.drawImage(pad, pad, sc)
    p.setPen(QPen(QColor(C["border"]), max(1.0, dpr)))
    p.drawPath(path)
    p.end()
    out.setDevicePixelRatio(dpr)
    return out, out.width() / dpr, out.height() / dpr


def retarget_images(tb, avail=None):
    """把文档里的图片换成按当前宽度预先平滑缩放好的圆角卡片（2× 原图按 1:1 物理像素显示，不放大）；公式图按渲染时的 dpr 折算尺寸。
    可重复调用（窗口大小变化后只换图片，不重排全文）。"""
    from PySide6.QtCore import QUrl
    from PySide6.QtGui import QTextCharFormat, QTextCursor, QTextDocument
    doc = tb.document()
    dpr = max(1.0, tb.devicePixelRatioF())
    if avail is None:
        avail = _avail_width(tb)
    avail = max(240, int(avail) // 8 * 8)             # 取整到 8 px，避免拖动时产生大量不同尺寸
    kind = QTextDocument.ResourceType.ImageResource.value
    todo = []
    for pos, ln, imf in _image_frags(doc):
        name = imf.name()
        m = _CARD.match(name)
        orig = m.group(3) if m else name
        if "xs_math_" in orig:                         # 公式图片：按渲染 dpr 折算为逻辑尺寸，与文字居中
            img = _load_image(tb, orig)
            if img is None:
                continue
            md = _MATH_DPR.search(orig)
            d = float(md.group(1)) if md else 1.0
            imf.setWidth(img.width() / d)
            imf.setHeight(img.height() / d)
            imf.setVerticalAlignment(QTextCharFormat.VerticalAlignment.AlignMiddle)
            todo.append((pos, ln, imf))
            continue
        img = _load_image(tb, orig)
        if img is None:
            continue
        inner = max(120, min(avail - 2 * _PAD, img.width() // 2))
        key = f"xscard_{inner}_{round(dpr * 100)}_{orig}"
        if key != name:
            card, w_, h_ = _card(img, inner, dpr) if not doc.resource(kind, QUrl(key)) else (None, None, None)
            if card is not None:
                doc.addResource(kind, QUrl(key), card)
                tb.__dict__.setdefault("_xs_size", {})[key] = (w_, h_)
            w_, h_ = tb.__dict__["_xs_size"][key]
            imf.setName(key)
            imf.setWidth(w_)
            imf.setHeight(h_)
            todo.append((pos, ln, imf))
    for pos, ln, imf in todo:
        c = QTextCursor(doc)
        c.setPosition(pos)
        c.setPosition(pos + ln, QTextCursor.MoveMode.KeepAnchor)
        c.setCharFormat(imf)
    tb.__dict__["_xs_avail"] = (avail, dpr)


def _avail_width(tb):
    w = tb.viewport().width()
    if w < 300:                                        # 还没显示出来：先按常见宽度估计，显示后由 resize 修正
        w = 640
    return w - 2 * tb.document().documentMargin()


class _ResizeWatcher(QObject):
    """窗口大小变化后等 250 ms 再重算图片宽度（只换图片）"""

    def __init__(self, tb):
        super().__init__(tb)
        self.tb = tb
        self.t = QTimer(self)
        self.t.setSingleShot(True)
        self.t.setInterval(250)
        self.t.timeout.connect(self.go)
        tb.installEventFilter(self)

    def eventFilter(self, obj, ev):
        if obj is self.tb and ev.type() == QEvent.Type.Resize:
            self.t.start()
        return False

    def go(self):
        tb = self.tb
        avail = max(240, int(_avail_width(tb)) // 8 * 8)
        dpr = max(1.0, tb.devicePixelRatioF())
        if tb.__dict__.get("_xs_avail") == (avail, dpr):
            return
        sb = tb.verticalScrollBar()
        v = sb.value()
        retarget_images(tb, avail)
        sb.setValue(v)


def prose_style(tb, size=11.0, line=160, doc_margin=30, max_img=None):
    """QTextBrowser 的阅读排版（对 Markdown 与 HTML 都有效；在设置内容之后调用）：
    正文字号 size、行距 line %、段距；标题按级别放大加粗、上方留白；只有图片的段落不加行距，图片按窗口宽度预先平滑缩放成圆角卡片。"""
    from PySide6.QtGui import QFont, QTextBlockFormat, QTextCharFormat, QTextCursor
    doc = tb.document()
    doc.setDocumentMargin(doc_margin)
    retarget_images(tb, max_img)
    blk = doc.begin()
    prop = QTextBlockFormat.LineHeightTypes.ProportionalHeight.value
    head_pt = {1: size + 10, 2: size + 5.5, 3: size + 2.5, 4: size + 1}
    while blk.isValid():
        fmt = blk.blockFormat()
        lvl = fmt.headingLevel()
        cur = QTextCursor(blk)
        in_table = cur.currentTable() is not None
        has_img = _has_image(blk)
        only_img = has_img and not blk.text().replace("\ufffc", "").strip()
        if only_img:
            fmt.setLineHeight(100, prop)
            fmt.setTopMargin(8)
            fmt.setBottomMargin(14)
        elif lvl:
            fmt.setTopMargin({1: 4, 2: 34, 3: 24}.get(lvl, 16))
            fmt.setBottomMargin({1: 14, 2: 12}.get(lvl, 8))
            fmt.setLineHeight(130, prop)
            cf = QTextCharFormat()
            cf.setFontPointSize(head_pt.get(lvl, size + 1))
            cf.setFontWeight(QFont.Weight.Bold)
            c2 = QTextCursor(blk)
            c2.select(QTextCursor.SelectionType.BlockUnderCursor)
            c2.mergeCharFormat(cf)
        elif in_table:
            fmt.setLineHeight(140, prop)
        else:
            fmt.setLineHeight(line, prop)
            lst = cur.currentList()
            fmt.setBottomMargin(7 if lst is not None else 13)
        cur.setBlockFormat(fmt)
        blk = blk.next()


def prose_browser(html=None, markdown=None, size=11.0, search_paths=None, bg=None):
    """排版良好的只读文本（说明、指南）"""
    tb = QTextBrowser()
    tb.setObjectName("reader")
    tb.setOpenExternalLinks(True)
    tb.setStyleSheet(f"QTextBrowser#reader{{background:{bg or C['bg']};border:none;font-size:{size}pt;}}")
    f = tb.document().defaultFont()
    f.setPointSizeF(size)
    tb.document().setDefaultFont(f)
    if search_paths:
        tb.setSearchPaths([str(x) for x in search_paths])
    tb.document().setDefaultStyleSheet(
        f"h1,h2,h3,h4{{color:{C['text']};}} h2{{font-size:{size + 5.5}pt;}} h3{{font-size:{size + 2.5}pt;}}"
        f"code{{background:{C['code']};}} b{{color:{C['text']};}} li{{margin-bottom:5px;}}"
        f"td,th{{padding:5px 9px;}} a{{color:{C['accent_text']};}}")
    if markdown is not None:
        tb.setMarkdown(markdown)
    elif html is not None:
        tb.setHtml(html)
    prose_style(tb, size)
    tb.__dict__['_xs_watch'] = _ResizeWatcher(tb)
    return tb


_INFO = {}


def info_window(parent, key, title, html, size=(760, 760)):
    """独立的说明窗口（不阻塞主窗口，可一边看一边操作）；同一个 key 只开一个"""
    from PySide6.QtWidgets import QDialog
    old = _INFO.get(key)
    if old is not None:
        try:
            old.show()
            old.raise_()
            old.activateWindow()
            return old
        except RuntimeError:
            pass
    top = parent.window() if parent is not None else None
    dlg = QDialog(top)
    dlg.setWindowTitle(title)
    dlg.setWindowFlag(Qt.WindowType.WindowContextHelpButtonHint, False)
    dlg.setWindowFlag(Qt.WindowType.WindowMinMaxButtonsHint, True)
    dlg.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, True)
    dlg.resize(*size)
    v = QVBoxLayout(dlg)
    v.setContentsMargins(0, 0, 0, 0)
    h = QLabel(title)
    h.setObjectName("h1")
    h.setContentsMargins(SP['xl'], SP['lg'], SP['xl'], 0)
    v.addWidget(h)
    v.addWidget(prose_browser(html=html), 1)
    _INFO[key] = dlg
    dlg.destroyed.connect(lambda *_: _INFO.pop(key, None))
    if top is not None:
        g = top.geometry()
        dlg.move(max(0, g.right() - size[0] - 20), g.top() + 60)
    dlg.show()
    return dlg


def ask(parent, title, text_):
    from .core import QUIET
    if QUIET["v"]:            # 自动测试：不弹模态对话框，视为确认
        return True
    return QMessageBox.question(parent, title, text_) == QMessageBox.StandardButton.Yes
