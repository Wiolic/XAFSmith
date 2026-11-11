"""文字展示：代码块、复制按钮、富文本浏览器、独立信息窗口、确认对话框。"""

from __future__ import annotations

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import QLabel, QMessageBox, QPlainTextEdit, QTextBrowser, QVBoxLayout, QWidget
from ..theme import C

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
    e.setFixedHeight(height or min(420, max(44, 19 * lines + 22)))
    if not copy:
        return e
    w = QWidget()
    lay = QVBoxLayout(w)
    lay.setContentsMargins(0, 0, 0, 0)
    lay.setSpacing(6)
    lay.addWidget(e)
    lay.addWidget(hbox(None, copy_button(text_)))
    return w


def _block_images(tb, blk, max_w):
    """块中的图片：超过 max_w 的按比例缩小；返回是否含图片"""
    from PySide6.QtCore import QUrl
    from PySide6.QtGui import QImage, QPixmap, QTextCharFormat, QTextCursor, QTextDocument
    doc = tb.document()
    found = False
    it = blk.begin()
    while not it.atEnd():
        frag = it.fragment()
        it += 1
        if not (frag.isValid() and frag.charFormat().isImageFormat()):
            continue
        found = True
        imf = frag.charFormat().toImageFormat()
        if imf.width() > 0:
            continue
        if "xs_math_" in imf.name():           # 公式图片：与文字居中对齐
            imf.setVerticalAlignment(QTextCharFormat.VerticalAlignment.AlignMiddle)
            c = QTextCursor(doc)
            c.setPosition(frag.position())
            c.setPosition(frag.position() + frag.length(), QTextCursor.MoveMode.KeepAnchor)
            c.setCharFormat(imf)
            continue
        res = doc.resource(QTextDocument.ResourceType.ImageResource.value, QUrl(imf.name()))
        if res is None or isinstance(res, (bytes, bytearray)) and not res:
            res = tb.loadResource(QTextDocument.ResourceType.ImageResource.value, QUrl(imf.name()))
        if isinstance(res, (bytes, bytearray)) or (hasattr(res, "data") and not isinstance(res, (QImage, QPixmap))):
            img = QImage.fromData(bytes(res))
        else:
            img = res
        if not isinstance(img, (QImage, QPixmap)) or img.width() <= 0:
            continue
        w_, h_ = img.width(), img.height()
        if w_ > max_w:
            imf.setWidth(max_w)
            imf.setHeight(h_ * max_w / w_)
            c = QTextCursor(doc)
            c.setPosition(frag.position())
            c.setPosition(frag.position() + frag.length(), QTextCursor.MoveMode.KeepAnchor)
            c.setCharFormat(imf)
    return found


def prose_style(tb, size=11.0, line=160, doc_margin=30, max_img=700):
    """QTextBrowser 的阅读排版（对 Markdown 与 HTML 都有效；在设置内容之后调用）：
    正文字号 size、行距 line %、段距；标题按级别放大加粗、上方留白；只有图片的段落不加行距，过宽的图片按比例缩小。"""
    from PySide6.QtGui import QFont, QTextBlockFormat, QTextCharFormat, QTextCursor
    doc = tb.document()
    doc.setDocumentMargin(doc_margin)
    blk = doc.begin()
    prop = QTextBlockFormat.LineHeightTypes.ProportionalHeight.value
    head_pt = {1: size + 10, 2: size + 5.5, 3: size + 2.5, 4: size + 1}
    while blk.isValid():
        fmt = blk.blockFormat()
        lvl = fmt.headingLevel()
        cur = QTextCursor(blk)
        in_table = cur.currentTable() is not None
        has_img = _block_images(tb, blk, max_img)
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
    h.setContentsMargins(26, 20, 26, 0)
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
    return QMessageBox.question(parent, title, text_) == QMessageBox.StandardButton.Yes
