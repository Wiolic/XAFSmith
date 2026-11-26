"""演示项目：导出 .prj、期刊出图、LCF、报告导出、后台任务（原 demo_suite 后段）。"""
import shutil
from pathlib import Path

from PySide6.QtWidgets import QPushButton

from checks import order_check
from helpers import W, click, need, say, step, wait


def test_export_prj(app, w, ctx, proj):
    """归一化：导出 .prj"""
    need(ctx, "loaded")
    P = w.pages
    PROJ = proj
    w.go("norm")
    W.find(P["norm"], "prj_name").setText("_test_export.prj")
    n = len(W.ERRORS)
    click(P["norm"], "导出 .prj")
    step("导出 .prj", n)
    prj = PROJ / "output" / "gui" / "athena" / "_test_export.prj"
    good = prj.exists()
    if good:
        from larch.io import read_athena
        good = len(read_athena(str(prj), do_preedge=False, do_bkg=False, do_fft=False).groups) >= 1
        prj.unlink()
    say(good, ".prj 可被 larch 读回")


def test_pubfig(app, w, ctx, proj):
    """期刊出图"""
    need(ctx, "loaded")
    P = w.pages
    PROJ = proj
    w.go("pubfig")
    P["pubfig"].state.update(kind="xanes", name="_test_fig", sel=["feo_rt1", "Fe_foil"])
    P["pubfig"].refresh()
    order_check(P["pubfig"])
    n = len(W.ERRORS)
    click(P["pubfig"], "保存到 output/figs/journal/")
    step("期刊出图", n)
    made = list((PROJ / "output" / "figs" / "journal").glob("_test_fig.*"))
    say({p.suffix for p in made} >= {".tiff", ".png", ".svg", ".txt"}, f"出图文件：{sorted(p.suffix for p in made)}")
    for p in made:
        p.unlink()


def test_lcf(app, w, ctx, proj):
    """LCF：Fe3C 用 Fe 箔与 FeO 拟合（只检查流程能出结果，不对比例作结论）"""
    need(ctx, "loaded")
    S, P = w.S, w.pages
    w.go("lcf")
    P["lcf"].state.update(smp="fe3c_rt", stds=["Fe_foil", "feo_rt1"])
    P["lcf"].refresh()
    n = len(W.ERRORS)
    click(P["lcf"], "LCF")
    wait(app)
    step("LCF", n)
    say(S.extra.get("lcf") is not None, "LCF 结果")


def test_summary_report(app, w, ctx, proj):
    """报告导出"""
    need(ctx, "loaded")
    S, P = w.S, w.pages
    PROJ = proj
    w.go("summary")
    n = len(W.ERRORS)
    click(P["summary"], "生成报告")
    wait(app)
    step("报告导出", n)
    sd = S.extra.get("summary_dir")
    d = Path(sd).resolve() if sd else None
    good = d is not None and (d / "汇总.xlsx").exists() and (d / "汇总报告.html").exists()
    say(good, f"汇总文件：{d.name if d else '—'}")
    reports = (PROJ / "output" / "reports").resolve()
    if good and d.parent == reports and d.name.startswith("汇总_"):
        shutil.rmtree(d)


def test_background_tasks(app, w, ctx, proj):
    """后台任务：批量处理立即取消；质量检查运行中页面重建（旧按钮被删除）后仍正常收尾"""
    need(ctx, "loaded")
    P = w.pages
    w.go("batch")
    n = len(W.ERRORS)
    click(P["batch"], "③ 处理全部样品")
    say(bool(W._ACTIVE) and w.cancel_btn.isVisible(), "批量处理：状态栏出现取消按钮")
    W._RUNNING[-1][3].cancel()
    wait(app)
    say(len(W.ERRORS) == n and not W._ACTIVE and not W._RUNNING and not w.bar.isVisible()
        and not w.cancel_btn.isVisible(), "批量处理取消：无错误、线程已回收、状态栏收起")
    n = len(W.ERRORS)
    click(P["batch"], "① 质量检查")
    old_btn = next(x for x in P["batch"].findChildren(QPushButton) if "① 质量检查" in x.text() or x.text() == "质量检查中…")
    P["batch"].refresh()                        # 任务运行中重建页面：旧按钮的 C++ 对象被删除
    from PySide6.QtCore import QCoreApplication, QEvent
    QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)    # processEvents 不处理 deleteLater
    import shiboken6
    say(not shiboken6.isValid(old_btn), "旧按钮已被删除（测试前提）")
    wait(app)
    b = next((x for x in P["batch"].findChildren(QPushButton) if x.text() == "① 质量检查"), None)
    say(len(W.ERRORS) == n and not W._ACTIVE and not W._RUNNING and not w.bar.isVisible()
        and b is not None and b.isEnabled(), "任务期间页面重建：正常收尾、状态栏收起")
