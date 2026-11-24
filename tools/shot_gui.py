"""主窗口截图（offscreen），供人眼检查与文档配图。

用法：
  python tools/shot_gui.py <输出目录> [选项]
    --project DIR     项目目录（默认 tests/data/demo_project；总是先复制到临时目录，不改原项目）
    --lang zh|en      界面语言（默认 zh）
    --size 1440x900   窗口大小（默认 1440x900）
    --scale 1         QT_SCALE_FACTOR（高分屏效果；默认 1）
    --pages a,b       只截这些页面（nav 键，如 norm,fit,pubfig；默认全部页面，文件名 gui_x<缩放>_<键>.png）
    --script FILE.py  先加载样品、操作页面再截图：FILE.py 里定义 run(ctx)，见下
    --offscreen       用 offscreen 平台（需要 QT_QPA_FONTDIR 提供中文字体，字形与真实界面不同）
    --workdir DIR     项目副本放在 DIR/shot_gui_run/demo_project（默认系统临时目录；截图里会显示项目路径时，用一个不含用户名的目录）
    --max-width N     输出 PNG 最大宽度（像素，默认 1600，超出按比例缩小）
默认用原生窗口平台（真实字体渲染；窗口移到屏幕外 x=-4000 再 grab，不打扰桌面）；--offscreen 才用 offscreen（CI / 无桌面，字体与真实界面不同）。

脚本接口：run(ctx)；可选 make_project(src, dst)（自己复制项目，例如只复制需要的样品）。ctx 提供
  ctx.app, ctx.w          QApplication 与主窗口
  ctx.proj                项目临时副本（Path）；ctx.lang、ctx.out
  ctx.pump(sec)           处理事件；ctx.wait()  等后台任务结束
  ctx.load(*samples)      把样品载入会话（等同“载入谱”）
  ctx.go(key)             切到页面
  ctx.resize(w, h)        改窗口大小（页面较长时加高）
  ctx.tab(page, 文字)      把页面里标题含该文字的标签页切到前面（QTabWidget）
  ctx.scroll_to(widget, margin=120)  把页面滚到该控件（上方留 margin 像素）
  ctx.shot(name, widget=None)  保存截图（默认整个窗口）→ <out>/<name>.png
文档配图的完整脚本是 tools/shot_docs.py：
  python tools/shot_docs.py docs/images/zh zh ；python tools/shot_docs.py docs/images/en en
"""
import argparse
import os
import shutil
import tempfile
import time
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]


def rm_tree(p):
    """删目录（原始数据副本带只读属性，先去掉只读再删）"""
    import stat

    def fix(func, path, _exc):
        os.chmod(path, stat.S_IWRITE)
        func(path)
    shutil.rmtree(p, onerror=fix) if Path(p).exists() else None


def shrink(path: Path, max_width: int):
    """宽度超过 max_width 时按比例缩小，并用 Pillow 压缩 PNG（没有 Pillow 就保持原样）"""
    try:
        from PIL import Image
    except ImportError:
        return
    im = Image.open(path)
    if im.width > max_width:
        im = im.resize((max_width, round(im.height * max_width / im.width)), Image.LANCZOS)
    im.save(path, optimize=True)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("out")
    ap.add_argument("--project", default=str(ROOT / "tests" / "data" / "demo_project"))
    ap.add_argument("--lang", default="zh", choices=["zh", "en"])
    ap.add_argument("--size", default="1440x900")
    ap.add_argument("--scale", default="1")
    ap.add_argument("--pages", default="")
    ap.add_argument("--script", default="")
    ap.add_argument("--workdir", default="")
    ap.add_argument("--offscreen", action="store_true")
    ap.add_argument("--max-width", type=int, default=1600)
    a = ap.parse_args(argv)

    out = Path(a.out).resolve()
    if a.offscreen:          # 无桌面环境 / CI：offscreen 平台用 FreeType 读 QT_QPA_FONTDIR，字体回退与字形渲染与真实界面不同，只做检查用，不用于文档配图
        os.environ["QT_QPA_PLATFORM"] = "offscreen"
        os.environ.setdefault("QT_QPA_FONTDIR", "C:/Windows/Fonts")
    else:                    # 默认走原生平台（Windows 上是 DirectWrite），字体与真实界面一致
        os.environ.pop("QT_QPA_PLATFORM", None)
        os.environ.pop("QT_QPA_FONTDIR", None)
    os.environ["QT_SCALE_FACTOR"] = a.scale
    os.environ["XAFSMITH_NO_RECENT"] = "1"
    out.mkdir(parents=True, exist_ok=True)
    if a.workdir:
        base = Path(a.workdir).resolve() / "shot_gui_run"      # 只删这个子目录，不碰 DIR 里的其他东西
        rm_tree(base)
        base.mkdir(parents=True)
    else:
        base = Path(tempfile.mkdtemp(prefix="shot_gui_"))
    tmp = base / "demo_project"
    mod = None
    if a.script:                 # 脚本可以定义 make_project(src, dst) 自己复制项目（例如只复制需要的样品）；没有就整个复制
        import importlib.util
        spec = importlib.util.spec_from_file_location("shot_script", a.script)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
    if mod is not None and hasattr(mod, "make_project"):
        mod.make_project(Path(a.project).resolve(), tmp)
    else:
        shutil.copytree(Path(a.project).resolve(), tmp)
    wd, ht = (int(v) for v in a.size.lower().split("x"))

    from PySide6.QtCore import QEventLoop, QTimer   # noqa: E402

    from xafsmith.qt import widgets as W            # noqa: E402
    from xafsmith.qt.app import make_window         # noqa: E402

    def pump(sec=0.5):
        loop = QEventLoop()
        QTimer.singleShot(int(sec * 1000), loop.quit)
        loop.exec()

    app, w = make_window(str(tmp), lang=a.lang)
    w.resize(wd, ht)
    if not a.offscreen:
        w.move(-4000, 0)             # 原生平台要真正 show()：放到屏幕可见区域外
    w.show()
    pump(0.8)

    def wait(timeout=900):
        t0 = time.time()
        pump(0.05)
        while W._RUNNING and time.time() - t0 < timeout:
            app.processEvents()
            time.sleep(0.02)
        pump(0.4)

    def cjk_residue(name):
        """英文界面截图里仍有中文的控件文字（标签、按钮、标签页、下拉框、表格单元、图中文字）：打印出来，作为界面 bug 报告"""
        import re
        from PySide6.QtWidgets import QAbstractButton, QComboBox, QLabel, QTabBar, QTableView
        cjk = re.compile(r"[一-鿿　-〿＀-￯]")
        found = []
        for wd_ in w.findChildren(QLabel) + w.findChildren(QAbstractButton):
            if wd_.isVisible() and cjk.search(wd_.text() or "") and wd_.text() != "中文":      # “中文”是语言切换按钮，本来就该是中文
                found.append(f"{type(wd_).__name__}: {wd_.text()[:70]}")
        for tb in w.findChildren(QTabBar):
            for i in range(tb.count()):
                if cjk.search(tb.tabText(i)):
                    found.append(f"Tab: {tb.tabText(i)}")
        for cb in w.findChildren(QComboBox):
            if cb.isVisible() and cjk.search(cb.currentText() or ""):
                found.append(f"Combo: {cb.currentText()[:70]}")
        for tv in w.findChildren(QTableView):
            m_ = tv.model()
            if tv.isVisible() and m_ is not None:
                for r_ in range(min(m_.rowCount(), 40)):
                    for c_ in range(min(m_.columnCount(), 20)):
                        t_ = str(m_.index(r_, c_).data() or "")
                        if cjk.search(t_):
                            found.append(f"Cell[{r_},{c_}]: {t_[:70]}")
        for pl_ in w.findChildren(W.Plot):
            if pl_.isVisible():
                for t_ in pl_.ax.figure.findobj(lambda o: hasattr(o, "get_text")):
                    if cjk.search(t_.get_text() or ""):
                        found.append(f"PlotText: {t_.get_text()[:70]}")
        for f_ in dict.fromkeys(found):
            print(f"CJK-RESIDUE [{name}] {f_}".encode("ascii", "backslashreplace").decode())

    def shot(name, widget=None):
        if a.lang == "en":
            cjk_residue(name)
        p = out / f"{name}.png"
        t = getattr(w, "_toaster", None)      # 轻提示（“已保存…”）不要留在图里
        if t is not None:
            t.q.clear()
            t.timer.stop()
            t.label.hide()
            pump(0.1)
        (widget or w).grab().save(str(p))
        shrink(p, a.max_width)
        print("saved", p)
        return p

    def go(key):
        w.go(key)
        pump(0.7)

    def resize(wd_, ht_):
        w.resize(wd_, ht_)
        pump(0.5)

    def tab(page, text):
        from PySide6.QtWidgets import QTabWidget
        for tw in page.findChildren(QTabWidget):
            for i in range(tw.count()):
                if text in tw.tabText(i):
                    tw.setCurrentIndex(i)
                    pump(0.6)
                    return True
        raise RuntimeError(f"找不到标签页：{text}")

    def scroll_to(widget, margin=120):
        from PySide6.QtWidgets import QScrollArea
        sa = widget.parentWidget()
        while sa is not None and not isinstance(sa, QScrollArea):
            sa = sa.parentWidget()
        if sa is not None:
            y = widget.mapTo(sa.widget(), widget.rect().topLeft()).y()
            sa.verticalScrollBar().setValue(max(0, y - margin))
            pump(0.5)

    def load(*samples):
        from xafsmith import pipeline as pl
        for s in samples:
            w.S.groups[s] = pl.build_sample(s)[0]
        w.S.emit("groups")
        pump(0.3)

    try:
        if mod is not None:
            mod.run(SimpleNamespace(app=app, w=w, proj=tmp, lang=a.lang, out=out, pump=pump, wait=wait,
                                    load=load, go=go, shot=shot, W=W, resize=resize, tab=tab, scroll_to=scroll_to))
        else:
            keys = [k for k in a.pages.split(",") if k] or list(w.nav)
            for key in keys:
                try:
                    go(key)
                    shot(f"gui_x{a.scale}_{key}")
                except Exception as e:      # 单页失败不影响其余页
                    print("FAIL", key, e)
    finally:
        w.close()
        rm_tree(base)
    print("ok", out)


if __name__ == "__main__":
    main()
