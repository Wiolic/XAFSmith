"""图形界面自动测试（PySide6，无窗口运行）：逐页构建、载入、去毛刺、FEFF6L/8L、拟合、诊断、已保存模型、
稳健性、.prj 导出、边前峰、图片导出（配色、Origin 说明）、LCF、报告导出、方法导出、制样指导、吸收边查询，最后用英文界面再逐页构建一遍。

运行：
  python tests/test_qt.py                       # 默认：公开数据的演示项目 tests/data/demo_project（CI 用这个）
  python tests/test_qt.py --project <项目目录>   # 本机 IrTaOx 项目：额外跑 IrTaOx 专用检查（Ir/Ta 样品、已保存模型、FEFF）
项目里含 IrO2、Ir foil、IrCoOx_OCP 三个样品时走 IrTaOx 专用检查，否则走演示项目的通用检查。
测试不改用户保存的界面语言；测试生成的临时文件按名字删除，只删自己创建的。
"""
import argparse
import json
import re as _re
import os
import shutil
import sys
import time
from pathlib import Path

ap = argparse.ArgumentParser()
DEMO = Path(__file__).resolve().parent / "data" / "demo_project"
ap.add_argument("--project", default=str(DEMO), help="项目目录；默认是公开数据的演示项目（不读 XAFSMITH_PROJECT，避免误测真实项目）")
ap.add_argument("--quick", action="store_true", help="跳过 FEFF8L 与稳健性检查（较慢）")
# 被 pytest 收集/导入时不解析 sys.argv（用默认参数）；脚本方式运行才读命令行
ARGS = ap.parse_args() if __name__ == "__main__" else ap.parse_args([])
os.environ["XAFSMITH_PROJECT"] = str(Path(ARGS.project).resolve())
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ["XAFSMITH_NO_RECENT"] = "1"          # 不写入用户的“最近的项目”

from PySide6.QtWidgets import QLabel, QPushButton   # noqa: E402

from xafsmith.qt import widgets as W                                 # noqa: E402
from xafsmith.qt.app import make_window                              # noqa: E402

PROJ = Path(os.environ["XAFSMITH_PROJECT"])
OK = [True]


def _project_samples():
    import pandas as pd
    return set(pd.read_csv(PROJ / "data" / "meta.csv", dtype=str, encoding="utf-8-sig").fillna("")["sample"])


IRTAOX = {"IrO2", "Ir foil", "IrCoOx_OCP"} <= _project_samples()


_NONE_RC = [sys.getrefcount(None)]


def _none_rc():
    """Python < 3.12：None 的引用计数变化。某个 C 扩展多减 None 的引用时，累积到 0 才崩（none_dealloc），
    崩溃位置与出错步骤无关；逐步打印下降量才能定位。3.12 起 None 不计引用（PEP 683），不打印。"""
    if sys.version_info >= (3, 12):
        return ""
    r = sys.getrefcount(None)
    d, _NONE_RC[0] = r - _NONE_RC[0], r
    return f"  [None 引用 {r}，{d:+d}]" if d < -200 else ""


def say(good, what):
    print(f"[{'ok' if good else 'FAIL'}] {what}{_none_rc()}", flush=True)
    OK[0] &= bool(good)
    return good


def pump(app, t=0.05):
    end = time.time() + t
    while time.time() < end:
        app.processEvents()


def wait(app, timeout=900):
    """等后台任务结束"""
    t0 = time.time()
    pump(app)
    while W._RUNNING and time.time() - t0 < timeout:
        app.processEvents()
        time.sleep(0.02)
    pump(app, 0.2)


def go_fit(w):
    """进入“EXAFS 拟合”并切到精细拟合（进入页默认是快速拟合）"""
    w.go("fit")
    w.pages["fit"].show_detailed()


def errors_since(n):
    return W.ERRORS[n:]


def step(what, n0):
    e = errors_since(n0)
    return say(not e, what + (f": {e[0][:400]}" if e else ""))


def click(page, text):
    for b in page.findChildren(QPushButton):
        if b.text().replace("&&", "&").strip() == text and b.isEnabled():
            b.click()
            return True
    raise AssertionError(f"找不到按钮：{text}")


def texts(page):
    return " ".join(l.text() for l in page.findChildren(QLabel))


def no_console_check(sample):
    """桌面快捷方式用 pythonw 启动：没有控制台（sys.stdout 为 None）时处理也必须正常"""
    from xafsmith.qt import app as qapp
    from xafsmith import pipeline as pl
    out, err = sys.stdout, sys.stderr
    sys.stdout = sys.stderr = None
    try:
        qapp._no_console_output()
        pl.build_sample(sample)
        ok = True
        msg = ""
    except Exception as ex:      # noqa: BLE001
        ok, msg = False, f": {ex}"
    finally:
        log = sys.stdout
        sys.stdout, sys.stderr = out, err
        if log not in (out, None):
            log.close()
    say(ok, "无控制台（pythonw）时载入样品" + msg)


def copy_register_check(app, w):
    """在临时文件夹新建项目，复制原始文件后应自动登记"""
    import tempfile
    from PySide6.QtWidgets import QFileDialog
    from xafsmith.cli import create_project
    import pandas as pd
    meta = pd.read_csv(PROJ / "data" / "meta.csv", dtype=str, encoding="utf-8-sig").fillna("")
    src = [str(PROJ / f) for f in meta.file if (PROJ / f).is_file()][:2]
    with tempfile.TemporaryDirectory() as td:
        create_project(td)
        w.open_project(td)
        w.go("data")
        old = QFileDialog.getOpenFileNames
        QFileDialog.getOpenFileNames = staticmethod(lambda *a, **k: (src, ""))
        n = len(W.ERRORS)
        try:
            click(w.pages["data"], "选择文件，复制到批次并登记…")
        finally:
            QFileDialog.getOpenFileNames = old
        import pandas as pd
        meta = pd.read_csv(Path(td) / "data" / "meta.csv", dtype=str)
        step("新项目：复制文件并登记", n)
        say(len(list((Path(td) / "data" / "raw").rglob("*"))) >= len(src) and len(meta) == len(src),
            f"复制 {len(src)} 个文件，登记 {len(meta)} 行")
        w.open_project(str(PROJ))


def container_checks(app, w, S, P, k1, fdir):
    """F2-1：EXAFS 拟合页是容器（快速拟合 | 精细拟合）：进入默认快速拟合、切换后状态保留；
    路径表新列顺序；旧顺序的路径表载入后重排，且拟合所用的模型 JSON 与重排前逐字相同。"""
    import json
    from xafsmith.qt.pages.fitting.fit_page import PATH_COLS
    box = P["fit"]
    pg = box.detailed_page
    w.go("fit")
    say(box.mode == "quick" and box.stack.currentWidget() is box.quick_page, "进入“EXAFS 拟合”：默认快速拟合")
    say("只拟合第一壳层" in texts(box.quick_page), "快速拟合页有说明文字")
    box.show_detailed()
    say(box.stack.currentWidget() is pg and box.mode == "detailed" and box.seg.value() == "detailed", "show_detailed 切到精细拟合")
    st = pg.state
    st.update(multi=False, data=k1)
    st["fdirs_" + k1] = [str(PROJ / fdir)]
    st["_f21_marker"] = 123
    st.pop("partab", None)
    for k in [k for k in st if k.startswith("pathtab_")]:
        st.pop(k)
    pg.refresh()
    pump(app)
    box.show_quick()
    say(box.stack.currentWidget() is box.quick_page, "show_quick 切回快速拟合")
    box.show_detailed()
    say(st.get("_f21_marker") == 123 and st.get("data") == k1, "来回切换后精细拟合状态保留")
    w.go("data")
    w.go("fit")
    say(box.mode == "quick", "离开再进入：又是快速拟合")
    box.show_detailed()

    def path_tab():
        return next((t for t in pg.findChildren(W.Table) if {"use", "sigma2", "note"} <= set(t.m.df.columns)), None)
    pt = path_tab()
    say(pt is not None and list(pt.m.df.columns) == PATH_COLS, "路径表列顺序：use,label,N,deltar,sigma2,e0,s02,third,note,reff,degen,nleg,amp_ratio,dir,file")
    if pt is None:
        return
    key = next(k for k in st if k.startswith("pathtab_"))
    new_df = st[key].copy()
    n0, n = len(S.fits), len(W.ERRORS)
    click(pg, "拟合")
    wait(app)
    step("新顺序路径表拟合", n)
    m_new = S.fits[-1]["model"] if len(S.fits) == n0 + 1 else None
    old_cols = ["file", "dir", "amp_ratio", "nleg", "degen", "reff", "note", "third", "deltar", "sigma2", "e0", "s02", "N", "label", "use"]
    st[key] = new_df[old_cols].copy()
    pg.refresh()
    pump(app)
    pt = path_tab()
    say(pt is not None and list(pt.m.df.columns) == PATH_COLS and pt.m.df.astype(str).equals(new_df.astype(str)),
        "旧顺序路径表载入后按新顺序重排，内容不变")
    click(pg, "拟合")
    wait(app)
    m_old = S.fits[-1]["model"] if len(S.fits) == n0 + 2 else None
    say(m_new is not None and m_old is not None and json.dumps(m_new, sort_keys=True, default=str) == json.dumps(m_old, sort_keys=True, default=str),
        "重排前后模型 JSON 逐字相同")
    S.fits[:] = S.fits[:n0]
    st.pop("_f21_marker", None)
    pg.refresh()


def pubfig_overlay_check(app, w, fit, keys, what):
    """F2-6 ②：快速拟合后图片导出的 χ(k) / |χ(R)| 可选，勾“叠加拟合曲线”后图中每个所选谱多一条拟合线"""
    from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
    S, pg = w.S, w.pages["pubfig"]
    idx = next(i for i, f in enumerate(S.fits) if f is fit)
    w.go("pubfig")
    for kind in ("chik", "chir"):
        pg.state.update(kind=kind, sel=list(keys), usefit=False, fits=[idx])
        pg.refresh()
        pump(app)
        seg = pg.findChildren(W.Segmented)[0]
        n0 = sum(len(c.figure.axes[0].lines) for c in pg.findChildren(FigureCanvasQTAgg))
        pg.state.update(usefit=True)
        pg.refresh()
        pump(app)
        n1 = sum(len(c.figure.axes[0].lines) for c in pg.findChildren(FigureCanvasQTAgg))
        say(seg.isEnabled() and pg.state.get("kind") == kind and n0 > 0 and n1 - n0 == len(keys),
            f"F2-6 ② {what}：图片导出 {kind} 可选，叠加拟合曲线后多 {n1 - n0} 条线（应为 {len(keys)}）")


def trend_order_check(app, w, q, jr, td):
    """F2-6 ③：趋势图样品顺序可调（快速拟合页内、图片导出 › 趋势图），顺序存在拟合记录上、两处一致；
    保存的趋势 CSV 行序一致、原有列的值不变；恢复默认后回到原顺序。"""
    from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
    from xafsmith import trend as tr
    S, pg, fit = w.S, w.pages["pubfig"], jr.fit
    meta, proc = tr.load_project_tables()
    base = tr.trend_table(fit["summ"], fit["model"], meta, proc)
    dflt = tr.default_order(base)
    name = dict(zip(base["dataset"], base["sample"]))

    def quick_ticks():
        pl_ = [p for p in q.findChildren(W.Plot)][0]          # 页内趋势图是第一张
        return [t.get_text() for t in pl_.ax.get_xticklabels()]

    def pub_ticks():
        c = pg.findChildren(FigureCanvasQTAgg)[0]
        return [t.get_text() for t in c.figure.axes[-1].get_xticklabels()]
    say("trend_order" not in fit, "F2-6 ③ 未调顺序时记录里没有 trend_order")
    q._trend_order.reverse()                                   # 快速拟合页内调顺序
    pump(app)
    want = [name[d] for d in dflt[::-1]]
    say(fit.get("trend_order") == dflt[::-1] and quick_ticks() == want, f"F2-6 ③ 快速拟合页内：顺序存在拟合记录上，横轴按 {want}")
    idx = next(i for i, f in enumerate(S.fits) if f is fit)
    w.go("pubfig")
    pg.state.update(kind="trend", tr_fit=idx)
    pg.refresh()
    pump(app)
    say(pub_ticks() == want, f"F2-6 ③ 图片导出 › 趋势图：与页内同一顺序 {pub_ticks()}")
    from PySide6.QtWidgets import QPushButton as _B

    def press(text):
        next(b for b in pg.findChildren(_B) if b.text() == text).click()
        pump(app)
    press("恢复默认顺序")                                         # 图片导出里恢复默认 → 记录里的顺序清除
    say("trend_order" not in fit, "F2-6 ③ 图片导出里“恢复默认顺序”：记录里的顺序清除")
    w.go("fit")
    w.pages["fit"].show_quick()
    pump(app)
    say("trend_order" not in fit and quick_ticks() != want, "F2-6 ③ 回到快速拟合：页内趋势图同步回到缺省顺序")
    w.go("pubfig")
    pg.refresh()
    pump(app)
    pg.findChildren(W.OrderList)[0].reverse()                  # 在图片导出里调顺序 → 快速拟合页同步
    pump(app)
    say(fit.get("trend_order") == dflt[::-1] and pub_ticks() == want, "F2-6 ③ 图片导出里调顺序：记录与图一致")
    w.go("fit")
    w.pages["fit"].show_quick()
    pump(app)
    say(quick_ticks() == want, "F2-6 ③ 回到快速拟合：页内趋势图随之变化")
    q._b_save.click()                                          # 保存：趋势 CSV 行序 = 当前顺序，原有列值不变
    pump(app)
    import pandas as pd
    f_csv = td / "output" / "fits" / "QF_joint_test_trend.csv"
    csv = pd.read_csv(f_csv, encoding="utf-8-sig")
    keep = pd.read_csv(f_csv, encoding="utf-8-sig", usecols=tr.COLUMNS).sort_values(["dataset", "path"]).reset_index(drop=True)
    say(list(csv["dataset"].drop_duplicates()) == fit["trend_order"] and list(csv.columns) == tr.COLUMNS + ["order"]
        and list(csv["order"].drop_duplicates()) == [1, 2], "F2-6 ③ 保存的趋势 CSV：行序 = 当前顺序，末尾加 order 列")
    cmp_ = base.sort_values(["dataset", "path"]).reset_index(drop=True)[tr.COLUMNS]
    say((keep["seq"] == cmp_["seq"]).all() and ((keep["R"] - cmp_["R"]).abs() < 1e-9).all(), "F2-6 ③ CSV 的 seq、R 等原有列数值不变")
    q._trend_order.set_value(dflt, emit=True)                  # 页内顺序控件设回缺省（等价于未调）后，用“恢复默认顺序”清掉记录
    fit.pop("trend_order", None)


def mixed_phase_checks(app, w, td):
    """F2-7：快速拟合选第二相（混合相）：Rmax 缺省、标样禁用、联合拟合、结果表多列、页内趋势图两条线、去图片导出、在精细拟合中继续。"""
    import numpy as np
    from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
    S, P = w.S, w.pages
    box = P["fit"]
    q, det = box.quick_page, box.detailed_page
    box.show_quick()
    w.go("fit")
    box.show_quick()
    c2 = next(d for d in q._feff2._vals if d is not None and d.name == "CuO_CuK")
    q._mode.set("standard", emit=True)
    say(not q._feff2.isEnabled(), "F2-7 标样用途：第二相下拉禁用")
    q._mode.set("sample", emit=True)
    say(q._feff2.isEnabled() and q._feff2.value() is None, "F2-7 样品用途：第二相下拉可用，缺省“（无）”")
    q._rmax.setValue(2.8)                                          # 用户改过 Rmax：选第二相不再改它
    q._feff2.setCurrentIndex(q._feff2._vals.index(c2))
    say(abs(q._rmax.value() - 2.8) < 1e-9, "F2-7 用户改过的 Rmax 不被第二相覆盖")
    q.state.pop("rmax_set", None)
    q._feff2.setCurrentIndex(0)
    q._feff2.setCurrentIndex(q._feff2._vals.index(c2))
    say(abs(q._rmax.value() - 3.0) < 1e-9 and "相 2" in q._shell_lb.text() and "Cu–O" in q._shell_lb.text(),
        "F2-7 选第二相：Rmax 缺省 3.0，第一壳层说明显示两相")
    q._feff2.setCurrentIndex(0)
    say(abs(q._rmax.value() - 2.5) < 1e-9, "F2-7 取消第二相：Rmax 缺省回到 2.5")
    q._feff2.setCurrentIndex(q._feff2._vals.index(c2))
    q._feff.setCurrentIndex(q._feff._vals.index(c2))
    say(not q._run.isEnabled() and "相同" in q._why.text(), "F2-7 两相同一文件夹：不能开始，写明原因")
    q._feff.setCurrentIndex(q._feff._vals.index(next(d for d in q._feff._vals if d.name == "Cu_CuK")))
    # 联合（两条同一份数据的谱：给第二条一个确定性的小扰动，避免 larch 把两个数据集当成同一个）
    g2 = S.groups["cu_rt01"]
    g2.chi = np.asarray(g2.chi) * (1 + 1e-3 * np.sin(np.arange(len(g2.chi))))
    q._smp.set_value(["cu_metal_rt", "cu_rt01"], emit=True)
    q._name.setText("QF_mixed_test")
    n0, n = len(S.fits), len(W.ERRORS)
    q._run.click()
    wait(app)
    step("快速拟合 · 混合相联合", n)
    jr = q._res["res"] if q._res else None
    say(jr is not None and jr.shell2 is not None and len(S.fits) == n0 + 1 and all(r.phase2 for r in jr.samples),
        "F2-7 混合相联合：拟合进会话历史，每个样品有相 2 结果")
    cols = list(q._tab.m.df.columns) if jr else []
    say({"N₂", "R₂ (Å)", "σ²₂ (Å²)"} <= set(cols) and "相 2 比例" in cols, "F2-7 结果表多出 N₂、R₂、σ²₂、相 2 比例：" + ", ".join(cols))
    q._trend_sel.setCurrentIndex(0)
    pump(app)
    tp = q.findChildren(W.Plot)[0]
    say(len(tp.ax.get_legend_handles_labels()[1]) == 2, "F2-7 页内趋势图两条线：" + ", ".join(tp.ax.get_legend_handles_labels()[1]))
    q._b_fig.click()
    pump(app)
    pg = P["pubfig"]
    cv = pg.findChildren(FigureCanvasQTAgg)
    say(w.S.extra.get("page") == "pubfig" and pg.state.get("kind") == "trend" and S.fits[pg.state.get("tr_fit")] is jr.fit
        and cv and len(cv[0].figure.axes[0].get_legend_handles_labels()[1]) == 2, "F2-7 去图片导出：趋势图有两条路径")
    w.go("fit")
    q._b_det.click()
    wait(app)
    st = det.state
    say(box.mode == "detailed" and st.get("multi") is True and len(st.get("fdirs_multi", [])) == 2, "F2-7 在精细拟合中继续：联合、两个 FEFF 文件夹")
    n0, n = len(S.fits), len(W.ERRORS)
    click(det, "拟合")
    wait(app)
    step("精细拟合 · 重跑混合相联合模型", n)
    f4 = S.fits[-1] if len(S.fits) == n0 + 1 else None
    diff = max((abs(f4["summ"]["params"][k]["value"] - v["value"]) for k, v in jr.fit["summ"]["params"].items()), default=9) if f4 else 9
    say(f4 is not None and diff < 1e-6, f"F2-7 精细拟合重跑混合相模型：参数相同（最大差 {diff:.1e}）")


def guess_checks(app, w):
    """G4：读入时猜的元素 / 吸收边要让用户确认（fe.060 的文件头里没有元素与边）"""
    from xafsmith.readers import read_scan
    S, P = w.S, w.pages
    g = read_scan(PROJ / "data" / "raw" / "public" / "fe.060")
    S.groups["guess_fe"] = g
    S.emit("groups")
    w.go("load")
    pump(app)
    pg = P["load"]
    t = texts(pg)
    cells = " ".join(str(x) for tb in pg.findChildren(W.Table) for x in tb.m.df.to_numpy().ravel())
    say("（猜测）" in cells and "按能量猜的" in t and any(b.text() == "确认无误" for b in pg.findChildren(QPushButton)),
        "G4 载入页：猜测的元素 / 边标“（猜测）”，有提示条与编辑器")
    ms = next(m for m in pg.findChildren(W.MultiSelect) if m.opts == ["guess_fe"])
    ed = next(e for e in pg.findChildren(W.QLineEdit) if e.placeholderText().startswith(("元素符号", "element symbol")))
    ed.setText("Cu")
    pump(app)
    say("guess_fe → Cu K" in texts(pg), "G4 输入元素后显示将得到的边")
    click(pg, "应用")
    pump(app)
    cells = " ".join(str(x) for tb in pg.findChildren(W.Table) for x in tb.m.df.to_numpy().ravel())
    say((g.element, g.edge) == ("Cu", "K") and not g.meta_guessed and "（猜测）" not in cells and "按能量猜的" not in texts(pg), "G4 应用：元素 / 边改变，猜测标记去掉")
    g.meta_guessed = ["element", "edge"]
    S.emit("groups")
    w.go("load")
    pump(app)
    click(pg, "确认无误")
    pump(app)
    say(not g.meta_guessed and (g.element, g.edge) == ("Cu", "K"), "G4 确认无误：去掉标记，值不变")
    S.groups.pop("guess_fe", None)
    S.emit("groups")
    del ms


def quickfit_checks(app, w):
    """F2-3b：快速拟合界面端到端（在项目的临时副本里做，保存的文件不污染演示项目）：
    标样 → 保存 → 样品模式选取标样值 → 拟合 → 结果表与判定 → 在精细拟合中继续（数值与快速拟合相同）；
    ≥ 2 个样品联合 → 趋势图、保存、去图片导出、在精细拟合中继续。"""
    import tempfile
    import pandas as pd
    from xafsmith import s02_source as s2
    from xafsmith.qt.pages.fitting.quick_fit import S02Dialog
    td = Path(tempfile.mkdtemp()) / "qfproj"
    shutil.copytree(PROJ, td)
    fd = td / "output" / "feff" / "Cu_CuK"          # 演示项目没有 FEFF 目录：用基准测试的 Cu 路径文件建一个（只在临时副本里）
    fd.mkdir(parents=True, exist_ok=True)
    shutil.copy(PROJ.parent / "benchmark" / "feffcu01.dat", fd / "feff0001.dat")
    fdir = fd
    fo = td / "output" / "feff" / "CuO_CuK"          # F2-7：合成的第二相（同一份路径文件改成 Cu–O 2.10 Å ×6，只用来走通流程）
    fo.mkdir(parents=True, exist_ok=True)
    txt = (fd / "feff0001.dat").read_text(encoding="utf-8").splitlines()
    txt = ["   2   6.000   2.1000    2.6300   -5.53502 nleg, deg, reff, rnrmav(bohr), edge" if "nleg, deg, reff" in ln else
           ("      .0000   -1.4849    1.4849  1   8 O" if _re.match(r"\s+\.0000\s+-1\.8016\s+1\.8016\s+1\s+29\s+Cu", ln) else ln) for ln in txt]
    (fo / "feff0001.dat").write_text("\n".join(txt) + "\n", encoding="utf-8")
    meta_f = td / "data" / "meta.csv"
    m = pd.read_csv(meta_f, dtype=str, encoding="utf-8-sig")
    m.loc[m["sample"] == "cu_rt01", "use"] = "1"         # 第二个 Cu_K 样品（与 cu_metal_rt 同一条谱，仅用于走通联合流程）
    m.to_csv(meta_f, index=False, encoding="utf-8-sig")
    try:
        w.open_project(str(td))
        pump(app, 0.3)
        S, P = w.S, w.pages
        box = P["fit"]
        q, det = box.quick_page, box.detailed_page
        from xafsmith import pipeline as pl
        w.go("fit")
        say("已载入并算出 χ(k)" in texts(q), "F2-6 ① 会话里没有载入样品：提示去载入（不列 meta.csv 的样品）")
        S.groups["cu_metal_rt"] = pl.build_sample("cu_metal_rt")[0]
        S.emit("groups")
        w.go("fit")
        say(q._smp.opts == ["cu_metal_rt"], f"F2-6 ① 快速拟合样品列表 = 会话已载入样品（只有 cu_metal_rt，meta.csv 里还有 cu_rt01）：{q._smp.opts}")
        S.groups["cu_rt01"] = pl.build_sample("cu_rt01")[0]
        S.emit("groups")
        w.go("fit")
        say(q._smp.opts == list(S.groups) and "cu_rt01" in q._smp.opts, "F2-6 ① 载入第二个样品后列表刷新")
        say(box.mode == "quick", "快速拟合：进入页默认快速拟合")
        feff = next(d for d in q._feff._vals if d.name == Path(fdir).name)
        q._feff.setCurrentIndex(q._feff._vals.index(feff))
        say("Cu–Cu" in q._shell_lb.text() and "×12" in q._shell_lb.text(), "① 选 FEFF 后显示第一壳层：" + q._shell_lb.text()[:60])
        say(not q._run.isEnabled() and "样品" in q._why.text(), "未选样品：不能开始，写明原因（" + q._why.text() + "）")
        q._smp.set_value(["cu_metal_rt"], emit=True)
        say(not q._run.isEnabled() and "S0²" in q._why.text(), "样品用途缺 S0²：不能开始，写明原因（" + q._why.text() + "）")
        q._smp.set_value(["cu_metal_rt", "cu_rt01"], emit=True)
        q._mode.set("standard", emit=True)
        say(not q._run.isEnabled() and "一个样品" in q._why.text(), "标样用途选了多个样品：不能开始，提示只能选一个")
        q._smp.set_value(["cu_metal_rt"], emit=True)
        say(q._run.isEnabled() and not q._s02_row.isVisibleTo(q), "标样用途：可开始，隐藏 S0² 框")
        # 标样
        n0, n = len(S.fits), len(W.ERRORS)
        q._rmax.setValue(3.0)
        q._run.click()
        wait(app)
        step("快速拟合 · 标样", n)
        r = q._res["res"] if q._res else None
        say(r is not None and r.mode == "standard" and len(S.fits) == n0 + 1 and r.fit is S.fits[-1] and q._tab.m.df.shape[0] == 1,
            "标样拟合：结果表 1 行，拟合进会话历史")
        say(r is not None and ("✅" in q._tab.m.df.iloc[0, -1] or "⚠" in q._tab.m.df.iloc[0, -1]) and "选取标样值" in texts(q)
            and len(q.findChildren(W.Plot)) == 1, "结果：判定 ✅ / ⚠、选取标样值提示、R 空间图")
        q._b_save.click()
        pump(app)
        base = r.model["name"]
        say((td / "models" / f"{base}.json").exists() and (td / "output" / "fits" / "exafs_fits.csv").exists()
            and (td / "output" / "fits" / f"{base}.params.json").exists() and (td / "output" / "fits" / f"{base}.fit_report.txt").exists(),
            f"保存：models/{base}.json、拟合记录、参数文件")
        # 样品：选取标样值
        q._mode.set("sample", emit=True)
        say(not q._run.isEnabled() and q._s02_row.isVisibleTo(q), "样品用途：S0² 框出现，空则不能拟合")
        cands = s2.list_candidates("Cu_K", S.fits, session_edges=q._session_edges())
        say(bool(cands) and cands[0].model == base and S02Dialog(q, cands).chosen().model == base, "选取标样值：候选含刚才的标样拟合")
        q._pick_candidate(cands[0])
        say(q._run.isEnabled() and q.state["s02_src"]["model"] == base and f"{cands[0].value:.4f}" == q._s02.text(), "选中后填入 S0² 并记来源")
        q._s02.setText("0.9")
        q._s02.textEdited.emit("0.9")
        say(q.state.get("s02_src") is None and "手动" in q._s02_lb.text(), "手改数值：来源变为手动")
        q._pick_candidate(cands[0])
        n0, n = len(S.fits), len(W.ERRORS)
        q._run.click()
        wait(app)
        step("快速拟合 · 样品", n)
        r = q._res["res"]
        say(len(S.fits) == n0 + 1 and r.mode == "sample" and r.model["s02_source"]["model"] == base and 0 < r.n < 20,
            f"样品拟合：N = {r.n:.2f}，s02_source 记录来源")
        say(len(q.findChildren(W.Plot)) == 1 and not q._b_fig.isEnabled() and q._b_det.isEnabled(), "单样品：只有 R 空间图，“去图片导出”不可用")
        # G3：导出汇报包（未保存的拟合也能导出；文件齐全、HTML 引用的图都在）
        n0, n = len(W.ERRORS), len(W.ERRORS)
        q._b_rep.click()
        wait(app)
        rep_dirs = sorted((td / "output" / "reports").glob(f"{r.model['name']}_*"))
        names_ = {f.name for f in rep_dirs[-1].iterdir()} if rep_dirs else set()
        say(bool(rep_dirs) and {"参数表.csv", "判定.txt", "方法.md", "报告.html", "cu_metal_rt_chiR.png", "cu_metal_rt_chik.png"} <= names_
            and "汇报包" in texts(q) and len(W.ERRORS) == n0, f"G3 导出汇报包：{sorted(names_)}")
        imgs_ = _re.findall(r"<img src='([^']+)'", (rep_dirs[-1] / "报告.html").read_text(encoding="utf-8")) if rep_dirs else []
        say(bool(imgs_) and all((rep_dirs[-1] / i_).is_file() for i_ in imgs_), "G3 报告.html 引用的图都存在")
        pubfig_overlay_check(app, w, r.fit, ["cu_metal_rt"], "快速拟合（单样品）")
        # G1：判定里未通过的条目后面跟操作按钮（构造 fail 条目，不改拟合结果）
        from xafsmith.quickfit import VerdictItem
        rm_now, rc_now = q._ctx()
        box_ = q._items_box([VerdictItem("fail", "rmax_leak", "x", "x"), VerdictItem("fail", "r_cif", "x", "x"),
                             VerdictItem("fail", "e0", "x", "x"), VerdictItem("fail", "n_ratio", "x", "x"),
                             VerdictItem("fail", "noise", "x", "x"), VerdictItem("note", "manual_s02", "x", "x")])
        btn = [b.text() for b in box_.findChildren(W.QPushButton)] if hasattr(W, "QPushButton") else               [b.text() for b in box_.findChildren(__import__("PySide6.QtWidgets", fromlist=["QPushButton"]).QPushButton)]
        want_rm = f"{round(rm_now - 0.2, 2):g}"
        say(any(want_rm in t and "Rmax" in t for t in btn) == (round(rm_now - 0.2, 2) >= rc_now)
            and sum("结构" in t for t in btn) + sum("structure" in t for t in btn) == 2
            and len(btn) == (6 if round(rm_now - 0.2, 2) >= rc_now else 5),
            f"G1 判定按钮：{btn}")
        q._rmax.setValue(3.0)
        # G2：用内置结构计算 FEFF（对话框 exec 换成直接接受；选第一行 = Cu）
        import xafsmith.qt.pages.fitting.quick_fit as qk
        el_, ed_, nm_, have_ = q._builtin_target()
        say((el_, ed_, nm_) == ("Cu", "K", ["Cu"]), f"G2 对话框内容：吸收元素 / 边 / 内置结构 = {el_} {ed_} {nm_}")
        orig_exec, qk.BuiltinDialog.exec = qk.BuiltinDialog.exec, lambda self: 1
        try:
            q._change_structure()                      # G1 的“换结构…”：滚动、聚焦并打开 G2 对话框（这里直接确定）
            wait(app)
            built = td / "output" / "feff" / "Cu_CuK" / "site0"
            say((built / "feff0001.dat").exists() and q.state.get("feff") == str(built) and q._feff.value() == built,
                "G1/G2 换结构 → 用内置结构计算：算出 Cu_CuK/site0 并选中")
            stamp = (built / "feff0001.dat").stat().st_mtime_ns
            q._builtin_btn.click()
            wait(app)
            say((built / "feff0001.dat").stat().st_mtime_ns == stamp, "G2 再次选同一结构：沿用已有，不重算")
        finally:
            qk.BuiltinDialog.exec = orig_exec
        shutil.rmtree(built, ignore_errors=True)
        q.state["feff"] = str(fdir)
        q.refresh()
        say(q._feff.value() == feff, "G2 清理后回到原 FEFF 文件夹")
        real_dirs, qk.feff_dirs = qk.feff_dirs, lambda: []
        try:
            q.refresh()
            say("还没有 FEFF" in texts(q) and q._builtin_btn.isEnabled() and "已载入并算出" not in texts(q),
                "G2 有 χ(k) 但没有 FEFF：不拦，提示直接用内置结构计算")
        finally:
            qk.feff_dirs = real_dirs
        q.refresh()
        say(q._feff.value() == feff, "G2 FEFF 回来后页面恢复")
        w.go("fit")
        # 在精细拟合中继续
        fit = r.fit
        q._b_det.click()
        wait(app)
        say(box.mode == "detailed" and det.state.get("data") == "cu_metal_rt" and det.state.get("range", {}).get("rmax") == 3.0,
            "在精细拟合中继续：切到精细拟合，范围来自模型")
        n0, n = len(S.fits), len(W.ERRORS)
        click(det, "拟合")
        wait(app)
        step("精细拟合 · 重跑快速拟合的模型", n)
        f2 = S.fits[-1] if len(S.fits) == n0 + 1 else None
        diff = max((abs(f2["summ"]["params"][k]["value"] - v["value"]) for k, v in fit["summ"]["params"].items()), default=9) if f2 else 9
        say(f2 is not None and diff < 1e-6 and abs(f2["summ"]["rfactor"] - fit["summ"]["rfactor"]) < 1e-6,
            f"精细拟合重跑：参数与 R 因子相同（最大差 {diff:.1e}）")
        # 联合
        box.show_quick()
        q._smp.set_value(["cu_metal_rt", "cu_rt01"], emit=True)
        q._name.setText("QF_joint_test")
        n0, n = len(S.fits), len(W.ERRORS)
        q._run.click()
        wait(app)
        step("快速拟合 · 联合", n)
        jr = q._res["res"] if q._res else None
        say(jr is not None and q._res["kind"] == "joint" and len(jr.samples) == 2 and q._tab.m.df.shape[0] == 2 and len(S.fits) == n0 + 1,
            "联合：结果表每样品一行，拟合进会话历史")
        say(len(q.findChildren(W.Plot)) == 2 and q._b_fig.isEnabled() and ("整批" in texts(q)), "联合：趋势图 + R 空间图，整批判定，“去图片导出”可用")
        q._trend_sel.setCurrentIndex(1)
        pump(app)
        say(q.state.get("qf_panel") == "R", "趋势图下拉切到 R")
        q._tab.selectRow(1)
        pump(app)
        say(q._res["row"] == 1, "点结果表第 2 行：显示该样品的图与判定")
        trend_order_check(app, w, q, jr, td)
        q._b_save.click()
        pump(app)
        say((td / "models" / "QF_joint_test.json").exists() and (td / "output" / "fits" / "QF_joint_test_trend.csv").exists(),
            "联合保存：模型 + 趋势 CSV")
        q._b_fig.click()
        pump(app)
        say(w.S.extra.get("page") == "pubfig" and P["pubfig"].state.get("kind") == "trend"
            and S.fits[P["pubfig"].state.get("tr_fit")] is jr.fit, "去图片导出：趋势图并选中这次拟合")
        pubfig_overlay_check(app, w, jr.fit, ["cu_metal_rt", "cu_rt01"], "快速拟合（联合）")
        w.go("fit")
        q._b_det.click()
        wait(app)
        say(box.mode == "detailed" and det.state.get("multi") is True and det.state.get("datas") == ["cu_metal_rt", "cu_rt01"],
            "联合：在精细拟合中继续（联合拟合模式、两个数据集）")
        n0, n = len(S.fits), len(W.ERRORS)
        click(det, "拟合")
        wait(app)
        step("精细拟合 · 重跑联合模型", n)
        f3 = S.fits[-1] if len(S.fits) == n0 + 1 else None
        diff = max((abs(f3["summ"]["params"][k]["value"] - v["value"]) for k, v in jr.fit["summ"]["params"].items()), default=9) if f3 else 9
        say(f3 is not None and diff < 1e-6, f"精细拟合重跑联合模型：参数相同（最大差 {diff:.1e}）")
        mixed_phase_checks(app, w, td)
    finally:
        w.open_project(str(PROJ))
        pump(app, 0.3)
        shutil.rmtree(td.parent, ignore_errors=True)


def restraint_checks(app, w, S, P, k1, fdir):
    """B3：拟合页软约束表。空表 → 模型无 restraints 键；添加一行 → 拟合 → 结果区有软约束表；草稿保存再读回表内容相同。"""
    import numpy as np
    import pandas as pd
    from xafsmith.qt import session
    pg = P["fit"].detailed_page
    go_fit(w)
    st = pg.state
    st.update(multi=False, data=k1)
    st["fdirs_" + k1] = [str(PROJ / fdir)]
    st.pop("restraints", None)
    pg.refresh()
    pump(app)
    n0, n = len(S.fits), len(W.ERRORS)
    click(pg, "拟合")
    wait(app)
    step("软约束 · 空表拟合", n)
    f0 = S.fits[-1] if len(S.fits) == n0 + 1 else None
    say(f0 is not None and "restraints" not in f0["model"] and "restraints" not in f0["summ"],
        "空软约束表：模型无 restraints 键、摘要无软约束键")
    cols = ["name", "expr", "value", "sigma", "note"]
    click(pg, "添加一行")
    pump(app)
    tab = next((t for t in pg.findChildren(W.Table) if list(t.m.df.columns) == cols), None)
    say(tab is not None and len(tab.m.df) == 1, "添加一行：软约束表出现 1 行")
    if tab is None:
        return
    for j, v in enumerate(["s02prior", "s02", "0.80", "0.01", "test note"]):
        tab.m.setData(tab.m.index(0, j), v)
    n = len(W.ERRORS)
    click(pg, "拟合")
    wait(app)
    step("软约束 · 带约束拟合", n)
    f1 = S.fits[-1] if len(S.fits) == n0 + 2 else None
    rs = (f1 or {}).get("summ", {}).get("restraints") or []
    say(f1 is not None and f1["model"].get("restraints") == [dict(expr="s02", value=0.8, sigma=0.01, name="s02prior",
                                                                    note="test note")]
        and len(rs) == 1 and np.isfinite(rs[0]["pull"]) and "软约束" in texts(pg),
        "带软约束拟合：模型记录软约束，结果区有软约束表" + ("" if not rs else f"（pull {rs[0]['pull']:+.2f}σ）"))
    # 草稿：软约束表能存能恢复
    dr = session.save_draft("_b3test", S, P)
    try:
        snap = session.load_draft(dr)
        before = st["restraints"].copy()
        st.pop("restraints")
        session.apply_pages(snap, dict(P), only=("fit",))
        got = st.get("restraints")
        say(isinstance(got, pd.DataFrame) and got.astype(object).fillna("").astype(str).to_numpy().tolist()
            == before.astype(object).fillna("").astype(str).to_numpy().tolist(), "草稿：软约束表保存并恢复")
        # 非法 sigma：toast 警告、不拟合
        tab.m.setData(tab.m.index(0, 3), "0")
        n1 = len(S.fits)
        click(pg, "拟合")
        pump(app, 0.3)
        say(len(S.fits) == n1, "sigma ≤ 0：不拟合")
    finally:
        Path(dr).unlink(missing_ok=True)
        st.pop("restraints", None)
        S.fits[:] = S.fits[:n0]
        pg.refresh()


def sigma2_checks(app, w, S, P, k1, fdir):
    """B6：拟合页温度字段与 σ² 温度模型。温度空 → 模型无 temperature 键；写温度 + σ² 写成 sigma2_debye(tempK, thD1)
    → 模型记录 temperature、摘要路径行有 temperature / sigma2_model / theta_param、thD1 默认带 min 50 / max 2000；非法温度不拟合。"""
    pg = P["fit"].detailed_page
    go_fit(w)
    st = pg.state
    st.update(multi=False, data=k1)
    st["fdirs_" + k1] = [str(PROJ / fdir)]
    for k in [k for k in st if k.startswith("temp_")]:
        st.pop(k)
    st.pop("use_tmodel", None)
    pg.refresh()
    pump(app)
    snap = {k: v.copy() for k, v in st.items() if type(v).__name__ == "DataFrame"}   # 路径表、参数表：结束时恢复
    n0 = len(S.fits)
    try:
        def tcheck():
            return next((c for c in pg.findChildren(W.QCheckBox) if "σ² 温度模型" in c.text() or "temperature model" in c.text()), None)
        tc = tcheck()
        say(tc is not None and not tc.isChecked(), "拟合页有“使用 σ² 温度模型”勾选框，缺省不勾")
        if tc is None:
            return
        row_hidden = all(not e.isVisibleTo(pg) for e in pg.findChildren(W.QLineEdit) if e.placeholderText() in ("不写", "not set"))
        btn_hidden = all(not b.isVisibleTo(pg) for b in pg.findChildren(W.QPushButton) if "σ² 模型" in b.text() or "σ² model" in b.text())
        say(row_hidden and btn_hidden, "不勾：温度框与“σ² 模型…”按钮不显示")
        tc.setChecked(True)
        pump(app, 0.1)
        say(any(e.isVisibleTo(pg) for e in pg.findChildren(W.QLineEdit) if e.placeholderText() in ("不写", "not set")),
            "勾选后显示温度框")
        tc.setChecked(False)
        pump(app, 0.1)
        def temp_edit():
            return next((e for e in pg.findChildren(W.QLineEdit) if e.placeholderText() in ("不写", "not set")), None)

        def path_tab():
            return next((t for t in pg.findChildren(W.Table) if {"use", "sigma2"} <= set(t.m.df.columns)), None)
        te, pt = temp_edit(), path_tab()
        say(te is not None and pt is not None, "拟合页有温度输入框")
        if te is None or pt is None:
            return
        n = len(W.ERRORS)
        click(pg, "拟合")
        wait(app)
        step("σ² 模型 · 无温度拟合", n)
        say(len(S.fits) == n0 + 1 and "temperature" not in S.fits[-1]["model"]
            and "sigma2_model" not in S.fits[-1]["summ"]["paths"][0], "温度为空：模型无 temperature 键、摘要路径行无 σ² 模型字段")
        ci = list(pt.m.df.columns).index("sigma2")
        pt.m.setData(pt.m.index(0, ci), "sigma2_debye(tempK, thD1)")
        pump(app, 0.2)
        tc = tcheck()
        if tc.isChecked():                     # 页面刷新过：路径已用温度模型 → 勾选框自动勾上
            say(True, "路径 σ² 用了温度模型：勾选框自动勾上")
        else:                                  # 没刷新：手写了模型表达式但没勾 → 不拟合
            n1 = len(S.fits)
            click(pg, "拟合")
            pump(app, 0.3)
            say(len(S.fits) == n1, "路径用了温度模型但没勾选：不拟合（提示勾选）")
            tc.setChecked(True)
            pump(app, 0.1)
        te = temp_edit()
        te.setText("abc")
        n1 = len(S.fits)
        click(pg, "拟合")
        pump(app, 0.3)
        say(len(S.fits) == n1, "非法温度：不拟合")
        te.setText("150")
        pump(app, 0.1)
        pt2 = next((t for t in pg.findChildren(W.Table) if "vary" in t.m.df.columns), None)
        row = pt2.m.df[pt2.m.df.name == "thD1"] if pt2 is not None else []
        say(len(row) == 1 and float(row.iloc[0]["value"]) == 300.0 and float(row.iloc[0]["min"]) == 50.0
            and float(row.iloc[0]["max"]) == 2000.0, "sigma2_debye(tempK, thD1)：参数表自动出现 thD1（300 K，范围 50–2000）、tempK 不是参数")
        say(len(pt2.m.df[pt2.m.df.name.isin(["tempK", "sigma2_debye"])]) == 0, "tempK 与函数名不进参数表")
        n = len(W.ERRORS)
        click(pg, "拟合")
        wait(app)
        step("σ² 模型 · 温度 150 K 拟合", n)
        f = S.fits[-1] if len(S.fits) == n1 + 1 else None
        pr = f["summ"]["paths"][0] if f else {}
        say(f is not None and f["model"].get("temperature") == 150.0 and pr.get("temperature") == 150.0
            and pr.get("sigma2_model") == "debye" and pr.get("theta_param") == "thD1",
            "写了温度：模型记录 temperature=150，摘要路径行 temperature / sigma2_model / theta_param")
        # 取消勾选 = 停用：路径 σ² 改回 ss<壳层号>，刷新后不再自动勾上，拟合不带温度
        tcheck().setChecked(False)
        pump(app, 0.3)
        pg.refresh()
        pump(app, 0.2)
        sv = list(path_tab().m.df["sigma2"])
        say(not tcheck().isChecked() and not any(_re.search(r"sigma2_debye|sigma2_eins|tempK", str(v)) for v in sv)
            and str(sv[0]).startswith("ss"), f"取消勾选：σ² 改回普通参数（{sv[0]}），刷新后仍不勾")
        pnames = set(next(t for t in pg.findChildren(W.Table) if "vary" in t.m.df.columns).m.df.name)
        say("thD1" not in pnames and str(sv[0]) in pnames, f"取消勾选：参数表去掉 θ、出现 {sv[0]}")
        n2 = len(S.fits)
        n = len(W.ERRORS)
        click(pg, "拟合")
        wait(app)
        step("σ² 模型 · 取消勾选后拟合", n)
        say(len(S.fits) == n2 + 1 and "temperature" not in S.fits[-1]["model"], "取消勾选后：能拟合，模型无 temperature")
    finally:
        for k in [k for k in st if k.startswith("temp_")]:
            st.pop(k)
        S.fits[:] = S.fits[:n0]
        st.update(snap)
        st.pop("use_tmodel", None)
        pg.refresh()


def msbind_checks(app, w, S, P, k1, fdir):
    """B5：路径表有 note 列；“多重散射绑定…”按钮（单数据集）→ 对话框：取消不改任何东西、应用只改勾选行的
    deltar / sigma2 / note；note 随模型保存、拟合照常（演示项目只有一条 nleg=2 的 Cu 路径文件：建议用 suggest 的替身，几何计算在单元测试里）。"""
    from xafsmith import msbind
    from xafsmith.qt.pages.fitting import msbind_dialog as md
    pg = P["fit"].detailed_page
    go_fit(w)
    st = pg.state
    st.update(multi=False, data=k1)
    st["fdirs_" + k1] = [str(PROJ / fdir)]
    st.pop("partab", None)
    for k in [k for k in st if k.startswith("pathtab_")]:
        st.pop(k)
    pg.refresh()
    pump(app)

    def path_tab():
        return next((t for t in pg.findChildren(W.Table) if {"use", "sigma2", "note"} <= set(t.m.df.columns)), None)
    pt = path_tab()
    say(pt is not None and "note" in pt.m.df.columns, "路径表有 note 列")
    b = next((b for b in pg.findChildren(W.QPushButton) if "多重散射绑定" in b.text() or "Multiple-scattering binding" in b.text()), None)
    say(b is not None, "路径卡有“多重散射绑定…”按钮")
    if b is None or pt is None:
        return
    fake = [dict(index=0, label="Cu-Cu", deltar="2*dr1", sigma2="0.5*ss1", basis_deltar="x", basis_sigma2="y", exact=False,
                 exact_sigma2=False, problem="", sigma2_problem="", note="msbind: test note")]
    orig_s, orig_x = msbind.suggest, md.MsBindDialog.exec
    msbind.suggest = lambda rows, root=None: fake
    decision = {}

    def fake_exec(self):
        decision["spec"] = self.spec()
        decision["rows"] = len(self.df)
        return decision["go"]
    md.MsBindDialog.exec = fake_exec
    try:
        before = path_tab().df()
        decision["go"] = 0
        b.click()
        pump(app, 0.3)
        say(path_tab().df().equals(before), "取消：路径表逐格不变")
        decision["go"] = 1
        b.click()
        pump(app, 0.5)
        row = path_tab().df().iloc[0]
        say(decision["rows"] == 1 and row["deltar"] == "2*dr1" and row["sigma2"] == "0.5*ss1" and row["note"] == "msbind: test note"
            and row["N"] == before.iloc[0]["N"] and row["s02"] == before.iloc[0]["s02"] and row["e0"] == before.iloc[0]["e0"],
            "应用：只改 deltar / sigma2 / note，N / s02 / e0 不变")
        n0, n = len(S.fits), len(W.ERRORS)
        click(pg, "拟合")
        wait(app)
        step("多重散射绑定 · 拟合", n)
        md_ = S.fits[-1]["model"] if len(S.fits) == n0 + 1 else {}
        p0 = (md_.get("paths") or [{}])[0]
        say(p0.get("note") == "msbind: test note" and p0.get("deltar") == "2*dr1", "note 写进拟合记录的模型，拟合照常运行")
    finally:
        msbind.suggest, md.MsBindDialog.exec = orig_s, orig_x
        for k in [k for k in st if k.startswith("pathtab_")]:
            st.pop(k)


def sigma2_dialog_checks(app, w, S, P, k1, k2, fdir):
    """B6 ⑧：“σ² 模型…”对话框。单数据集：写表达式 + 建 θ / 静态项参数（缺省 50–2000 K、静态项无下限）；
    联合拟合：应用到所有数据集的同一壳层，各数据集温度进模型，联合拟合能跑。k2 是 k1 的副本（演示项目只有一条 Cu 谱）。"""
    import copy
    import numpy as np
    from xafsmith import pipeline as pl
    from xafsmith.qt.pages.fitting import sigma2_dialog as sd
    pg = P["fit"].detailed_page
    go_fit(w)
    st = pg.state
    id1, id2 = (pl.safe(Path(k).name) for k in (k1, k2))
    S.groups[k2] = copy.deepcopy(S.groups[k1])
    n0 = len(S.fits)
    orig = sd.Sigma2Dialog.exec
    plan = {}

    def fake_exec(self):                                   # 不弹窗：按 plan 填写后直接确定
        for key, v in plan.items():
            getattr(self, key).setValue(v) if key in ("th0", "thmin", "thmax") else None
        self.kind.setCurrentIndex(sd.KINDS.index(plan.get("kind", "debye")))
        self.static.setChecked(plan.get("static", False))
        self.apply_all.setChecked(plan.get("apply_all", True))
        plan["spec"] = self.spec()
        plan["note"] = self.note.text()
        return 1
    sd.Sigma2Dialog.exec = fake_exec

    def tabs_():
        return [t for t in pg.findChildren(W.Table) if {"use", "sigma2"} <= set(t.m.df.columns)]

    def edit(label_btn="σ² 模型"):
        b = next((b for b in pg.findChildren(W.QPushButton) if label_btn in b.text()), None)
        say(b is not None, "路径卡有“σ² 模型…”按钮")
        if b is not None:
            b.click()
            pump(app, 0.3)

    def param_tab():
        return next((t for t in pg.findChildren(W.Table) if "vary" in t.m.df.columns), None)
    try:
        for k in [k for k in st if k.startswith("temp_")]:
            st.pop(k)
        st.update(multi=False, data=k1)
        st["fdirs_" + k1] = [str(PROJ / fdir)]
        st.pop("partab", None)
        st["use_tmodel"] = True                                # 勾选“使用 σ² 温度模型”才有温度框与按钮
        pg.refresh()
        pump(app)
        te = next(e for e in pg.findChildren(W.QLineEdit) if e.placeholderText() in ("不写", "not set"))
        te.setText("100")
        plan.clear()
        plan.update(kind="debye", static=True, apply_all=False)
        edit()
        sg = plan["spec"]
        say(sg["expr"] == "sigma2_debye(tempK, thD1) + ss0_1" and set(sg["params"]) == {"thD1", "ss0_1"},
            f"对话框结果：{sg['expr']}")
        pt = tabs_()[0]
        say(pt.m.df.iloc[0]["sigma2"] == "sigma2_debye(tempK, thD1) + ss0_1", "路径表 sigma2 单元格已改写")
        par = param_tab().m.df.set_index("name")
        say(par.loc["thD1", "min"] == 50 and par.loc["thD1", "max"] == 2000 and par.loc["thD1", "value"] == sg["params"]["thD1"]["value"]
            and par.loc["ss0_1", "value"] == 0 and np.isnan(par.loc["ss0_1", "min"]) and np.isnan(par.loc["ss0_1", "max"])
            and "tempK" not in par.index, "参数表：thD1（对话框初值，50–2000）、ss0_1（0，无下限）")
        # 自由：改回 ss1，已有参数保留
        plan.clear()
        plan.update(kind="free", apply_all=False)
        edit()
        say(tabs_()[0].m.df.iloc[0]["sigma2"] == "ss1", "改回自由：sigma2 = ss1")
        # 当前 σ² 是数字且有温度 → θ 初值由 theta_from_sigma2 反算
        t0 = tabs_()[0]
        t0.m.setData(t0.m.index(0, list(t0.m.df.columns).index("sigma2")), "0.0045")
        pump(app, 0.2)
        plan.clear()
        plan.update(kind="einstein", static=False, apply_all=False)
        edit()
        from xafsmith import paths as xp
        from xafsmith.sigma2 import theta_from_sigma2
        row = tabs_()[0].m.df.iloc[0]
        ref = theta_from_sigma2(xp.resolve(row["file"]), "einstein", 100.0, 0.0045)
        thE = param_tab().m.df.set_index("name").loc["thE1"]
        say(ref is not None and abs(float(thE["value"]) - ref) < 0.006 and tabs_()[0].m.df.iloc[0]["sigma2"] == "sigma2_eins(tempK, thE1)",
            f"Einstein：θ 初值由 σ²=0.0045 @100 K 反算 = {ref}（表中 {thE['value']}，{tabs_()[0].m.df.iloc[0]['sigma2']}）")
        # 联合拟合：应用到所有数据集的同一壳层
        st.pop("partab", None)
        for k in [k for k in st if k.startswith("pathtab_")]:
            st.pop(k)
        st.update(multi=True, datas=[k1, k2], fdirs_multi=[str(PROJ / fdir)])
        st["mname_multi"] = "b6test_joint"
        st["temp_" + id1], st["temp_" + id2] = "10", "300"
        pg.refresh()
        pump(app)
        plan.clear()
        plan.update(kind="debye", static=False, apply_all=True)
        edit()
        say([t.m.df.iloc[0]["sigma2"] for t in tabs_()] == ["sigma2_debye(tempK, thD1)"] * 2, "联合：两个数据集同一壳层的 sigma2 都改了")
        n = len(W.ERRORS)
        click(pg, "拟合")
        wait(app)
        step("σ² 模型 · 联合拟合", n)
        f = S.fits[-1] if len(S.fits) == n0 + 1 else None
        sm = (f or {}).get("summ", {})
        say(f is not None and [d["temperature"] for d in sm.get("datasets", [])] == [10.0, 300.0]
            and {p["sigma2_model"] for p in sm["paths"]} == {"debye"} and {p["theta_param"] for p in sm["paths"]} == {"thD1"}
            and [d["temperature"] for d in f["model"]["datasets"]] == [10.0, 300.0],
            "联合拟合：模型与摘要记录各数据集温度、σ² 模型、θ 参数")
        if f:
            from PySide6.QtWidgets import QTabBar
            tabs_txt = [t.tabText(i) for t in pg.findChildren(QTabBar) for i in range(t.count())]
            say("σ²(T)" in tabs_txt and "拟合结果（依赖 Debye / Einstein 模型）" in texts(pg), f"结果区有 σ²(T) 图（标签页：{tabs_txt}）")
            from xafsmith import fit_exafs as fx
            res, _, s2 = fx.fit_multi({id1: S.groups[k1], id2: S.groups[k2]}, f["model"])
            same = all(s2["params"][k]["value"] == v["value"] for k, v in sm["params"].items())
            say(same, "GUI 联合拟合与同一模型重跑（同一 groups）参数相差 0")
    finally:
        sd.Sigma2Dialog.exec = orig
        for k in [k for k in st if k.startswith(("temp_", "pathtab_"))]:
            st.pop(k)
        st.update(multi=False)
        st.pop("partab", None)
        S.groups.pop(k2, None)
        S.fits[:] = S.fits[:n0]
        pg.refresh()


def multi_fit_checks(app, w, S, P, k1, k2, fdir, rng=None, alias=False):
    """B2：拟合页多数据集联合拟合（k1、k2：两条已载入的谱；fdir：FEFF 目录，相对项目根）。
    alias=True：k2 是 k1 的副本（演示项目只有一条 Cu 谱），不做命令行重跑对照。
    项目里测试产生的文件按名字删除；exafs_fits.csv 先备份、测完原样写回。"""
    import numpy as np
    import pandas as pd
    from PySide6.QtWidgets import QComboBox, QTabBar
    from xafsmith import pipeline as pl
    from xafsmith.qt import session
    from xafsmith.qt.pages.fitting.fit_view import FitView
    from xafsmith.qt.state import safe
    from xafsmith.paths import FITS_CSV
    csv0 = FITS_CSV.read_bytes() if FITS_CSV.exists() else None
    made = []
    pg = P["fit"].detailed_page
    go_fit(w)
    if alias:
        import copy
        S.groups[k2] = copy.deepcopy(S.groups[k1])
    id1, id2 = (pl.safe(Path(k).name) for k in (k1, k2))
    st = pg.state
    st["range"] = dict(rng or st.get("range") or {})
    st.update(multi=False, data=k1, fdirs_multi=[str(PROJ / fdir)], datas=[k1, k2])
    st["fdirs_" + k1] = [str(PROJ / fdir)]
    pg.refresh()
    pump(app)

    def run(label):
        n = len(W.ERRORS)
        n0 = len(S.fits)
        click(pg, "拟合")
        wait(app)
        step(label, n)
        return S.fits[-1] if len(S.fits) == n0 + 1 else None
    # 数据 / FEFF 目录多选：勾选时不重建页面（否则列表关掉），关闭列表后提交一次
    ms = W.MultiSelect(["a", "b", "c"], ["a"])
    got = []
    ms.committed.connect(got.append)
    ms.click()
    pump(app, 0.2)
    pop = [c for c in ms.children() if isinstance(c, W.QFrame)][-1]
    lw = pop.findChild(W.QListWidget)
    for i in (1, 2):
        lw.item(i).setCheckState(W.Qt.CheckState.Checked)
    say(pop.isVisible() and got == [], "多选：勾选时列表保持打开、不提交")
    pop.hide()
    pump(app, 0.2)
    say(got == [["a", "b", "c"]], f"多选：关闭列表后提交一次 {got}")
    try:
        # 单数据集（对照）
        single = run("多数据集 · 先做单数据集拟合（对照）")
        # 多数据集模式只选 1 个数据集：逐位等于单数据集
        st.update(multi=True, datas=[k1])
        pg.refresh()
        m1 = run("多数据集模式选 1 个数据集")
        sp = single["summ"]["params"] if single else {}
        mp = m1["summ"]["params"] if m1 else {}
        eq = bool(sp) and set(sp) == set(mp) and all(mp[k]["value"] == v["value"] and mp[k]["stderr"] == v["stderr"]
                                                     for k, v in sp.items())
        say(eq and m1["summ"]["rfactor"] == single["summ"]["rfactor"]
            and m1["summ"]["chi2_reduced"] == single["summ"]["chi2_reduced"],
            "1 个数据集：多数据集模式与单数据集模式的参数、误差、R 因子、χ²_ν 逐位相等")
        print("   参数表（单 | 多）:", {k: (v["value"], v["stderr"]) for k, v in sp.items()}, "|",
              {k: (v["value"], v["stderr"]) for k, v in mp.items()})
        # 两个数据集联合
        st.update(multi=True, datas=[k1, k2])
        st["mname_multi"] = "b2test_joint"
        pg.refresh()
        tabs = [t.tabText(i) for t in pg.findChildren(QTabBar) for i in range(t.count())]
        say(id1 in tabs and id2 in tabs, f"路径卡按数据集分标签页：{tabs}")
        say("Σ N_idp" in texts(pg), "拟合范围显示 Σ N_idp")
        # C2：路径勾选同步（只同步 use，不动表达式；关着时不同步）
        from PySide6.QtCore import Qt as _Qt
        from PySide6.QtWidgets import QCheckBox as _QCB
        ptabs_ = [t_ for t_ in pg.findChildren(W.Table) if {"use", "label", "dir", "sigma2"} <= set(t_.m.df.columns)]
        sync_cb = [c_ for c_ in pg.findChildren(_QCB) if c_.text() == "勾选同步到所有数据集"]
        say(len(ptabs_) == 2 and len(sync_cb) == 1, "联合拟合：两个数据集路径表与“勾选同步”开关")
        if len(ptabs_) == 2 and sync_cb:
            ta, tb = ptabs_
            ids_ = [id1, id2]
            ci = list(ta.m.df.columns).index("use")
            r0 = 0                       # 演示项目只有一条 FEFF 路径（两个数据集都已勾选）
            sig_b = list(tb.m.df["sigma2"])

            def setuse(tab, r_, v_):
                tab.m.setData(tab.m.index(r_, ci), _Qt.CheckState.Checked if v_ else _Qt.CheckState.Unchecked,
                              _Qt.ItemDataRole.CheckStateRole)
            say(bool(ta.m.df.at[r0, "use"]) and bool(tb.m.df.at[r0, "use"]), "同步测试前提：两个数据集的路径都已勾选")
            setuse(ta, r0, False)
            say(bool(tb.m.df.at[r0, "use"]), "勾选同步关：另一个数据集不跟着变")
            setuse(ta, r0, True)
            sync_cb[0].setChecked(True)
            setuse(ta, r0, False)
            say(not tb.m.df.at[r0, "use"] and list(tb.m.df["sigma2"]) == sig_b, "勾选同步开：取消勾选同步到另一个数据集，表达式不变")
            setuse(tb, r0, True)
            say(bool(ta.m.df.at[r0, "use"]), "勾选同步开：反方向勾选同样同步")
            sync_cb[0].setChecked(False)
            # C2：σ² 各数据集独立（共用的 ss1 → ss1_<id>；初值复制；再点一次无改动；恢复后不影响后面的联合拟合）
            ci_s = list(ta.m.df.columns).index("sigma2")
            s0 = (ta.m.df.at[0, "sigma2"], tb.m.df.at[0, "sigma2"])
            say(s0[0] == s0[1] and s0[0] != "", f"σ² 独立前：两个数据集共用 {s0[0]}")
            click(pg, "σ² 各数据集独立")
            pump(app, 0.3)
            sa_, sb_ = ta.m.df.at[0, "sigma2"], tb.m.df.at[0, "sigma2"]
            say({sa_, sb_} == {f"{s0[0]}_{ids_[0]}", f"{s0[0]}_{ids_[1]}"}, f"σ² 独立后：{sa_}、{sb_}")
            ptab_ = [t_ for t_ in pg.findChildren(W.Table) if {"name", "value", "vary", "min", "max", "expr"} <= set(t_.m.df.columns)]
            nm_ = set(ptab_[0].m.df["name"]) if ptab_ else set()
            say({sa_, sb_} <= nm_ and s0[0] not in nm_, "参数表：新参数出现，原共用参数不再被用到而消失")
            click(pg, "σ² 各数据集独立")
            pump(app, 0.3)
            say((ta.m.df.at[0, "sigma2"], tb.m.df.at[0, "sigma2"]) == (sa_, sb_), "σ² 独立：幂等（再点一次无改动）")
            for t_ in (ta, tb):                       # 恢复共用，后面的联合拟合步骤照旧
                t_.m.setData(t_.m.index(0, ci_s), s0[0])
            pump(app, 0.3)
        f2 = run("2 个数据集联合拟合")
        s2 = f2["summ"] if f2 else {}
        say(f2 is not None and s2.get("n_datasets") == 2 and f2.get("multi") and set(f2["curves"]) == {id1, id2},
            f"联合拟合：n_datasets={s2.get('n_datasets')}")
        if f2:
            print(f"   联合 R={s2['rfactor']:.5f} χ²_ν={s2['chi2_reduced']:.3f} ΣN_idp={s2['n_idp']:.2f} 变量数={s2['nvarys']}；"
                  + "；".join(f"{d['id']}: R={d['rfactor']:.5f} N_idp={d['n_idp']:.2f} χ²占比={d['chi2_share']:.2f}"
                             for d in s2["datasets"]))
            t = texts(pg)
            say("联合 R 因子" in t and "Σ N_idp" in t and "多数据集模型暂不支持稳健性检查" in t, "右栏：联合指标与稳健性提示")
            # C2：趋势标签页（表、图、保存按钮；横轴来源 order / seq / time 由 meta 决定）
            from PySide6.QtWidgets import QTabWidget as _QTW
            fv0 = pg.findChildren(FitView)[-1]
            tt = [t_ for t_ in fv0.findChildren(_QTW) if any(t_.tabText(i) == "趋势" for i in range(t_.count()))]
            say(bool(tt) and "保存趋势表" in [b.text().strip() for b in fv0.findChildren(QPushButton)],
                "结果页：多数据集拟合有“趋势”标签页与“保存趋势表”按钮")
            # 切换数据集：图、路径、诊断重画
            fv = pg.findChildren(FitView)[-1]
            cb = [c for c in fv.findChildren(QComboBox) if c.count() == 2 and c.itemText(1) == id2][0]
            n = len(W.ERRORS)
            cb.setCurrentIndex(1)
            pump(app, 0.5)
            step("切换数据集重画", n)
            fv = pg.findChildren(FitView)[-1]
            say(fv.ds == id2 and fv.fit["summ"]["dataset"] == id2 and f"{s2['datasets'][1]['rfactor']:.4f}" in texts(pg),
                f"当前数据集 {fv.ds}")
            cb = [c for c in fv.findChildren(QComboBox) if c.count() == 2 and c.itemText(1) == id2][0]
            cb.setCurrentIndex(0)
            pump(app, 0.5)
            # 稳健性页只有一条提示：标签页高度只跟当前页（曾取各页最大值并把上方拟合图挤扁）
            from PySide6.QtWidgets import QTabWidget
            fv = pg.findChildren(FitView)[-1]
            ft = [t for t in fv.findChildren(QTabWidget) if any("稳健" in t.tabText(i) for i in range(t.count()))][0]
            hh = {}
            for i in range(ft.count()):
                if ft.tabText(i) in ("参数", "稳健性"):
                    ft.setCurrentIndex(i)
                    pump(app, 0.3)
                    hh[ft.tabText(i)] = ft.heightForWidth(ft.width())
            ft.setCurrentIndex(0)
            say(hh.get("稳健性", 1e9) < hh.get("参数", 0), f"多数据集稳健性页只占自身高度（低于参数页）：{hh}")
            # 历史页
            n = len(W.ERRORS)
            w.go("history")
            pump(app, 0.3)
            step("拟合历史显示多数据集拟合", n)
            # B4：比较卡片（会话里至少有 2 个拟合时出表）
            hp = w.pages["history"]
            if len(S.fits) >= 2:
                n = len(W.ERRORS)
                click(hp, "比较")                       # 第一个“比较”是 F 检验卡片；第二个在模型比较卡片
                bs = [b for b in hp.findChildren(QPushButton) if b.text().strip() == "比较" and b.isEnabled()]
                bs[-1].click()
                pump(app, 0.3)
                step("模型比较卡片出表", n)
                tab = next((t for t in hp.findChildren(W.Table) if "vs" in list(t.m.df.columns)), None)
                say(tab is not None and len(tab.m.df) == len(S.fits) and "嵌套模型" in texts(hp),
                    "模型比较表行数等于所选拟合数，并显示嵌套提示")
            go_fit(w)
            # 保存
            n = len(W.ERRORS)
            click(pg, "保存结果")
            step("保存多数据集拟合", n)
            base = safe(s2["model"])
            fig1, fig2 = (PROJ / "output" / "figs" / f"{base}_{i}_fit.png" for i in (id1, id2))
            mj = PROJ / "models" / f"{base}.json"
            made += [fig1, fig2, mj, PROJ / "output" / "fits" / f"{base}.fit_report.txt",
                     PROJ / "output" / "fits" / f"{base}_trend.csv", PROJ / "output" / "fits" / f"{base}_trend.params.json"]
            say((PROJ / "output" / "fits" / f"{base}_trend.csv").exists()
                and (PROJ / "output" / "fits" / f"{base}_trend.params.json").exists(),
                "保存结果顺带写 _trend.csv 与 .params.json")
            dfc = pd.read_csv(FITS_CSV)
            last = dfc[dfc["model"] == s2["model"]]
            say(fig1.exists() and fig2.exists() and mj.exists() and set(last["dataset"]) == {id1, id2},
                f"保存：{fig1.name}、{fig2.name}、CSV dataset 列 {sorted(set(last['dataset']))}")
            md = json.loads(mj.read_text(encoding="utf-8"))
            say("datasets" in md and "sample" not in md and "paths" not in md and [d["id"] for d in md["datasets"]] == [id1, id2],
                "模型 json 写入 datasets（顶层无 sample / paths）")
            w.go("pubfig")                       # C2：图片导出页的趋势图（用刚做的联合拟合）
            trend_pubfig_check(app, w, S, P)
            go_fit(w)
            # 已保存模型：多数据集，样品框禁用，直接运行
            st["mf"] = mj.name
            st["saved_open"] = True
            pg.refresh()
            say(not W.find(pg, "saved_smp").isEnabled() and "样品由模型内 datasets 决定" in texts(pg),
                "已保存的多数据集模型：样品框禁用并提示")
            n0, n = len(S.fits), len(W.ERRORS)
            click(pg, "运行")
            wait(app)
            step("运行已保存的多数据集模型", n)
            say(len(S.fits) == n0 + 1 and S.fits[-1]["summ"].get("n_datasets") == 2, "已保存多数据集模型能运行")
            # 与命令行重跑对照
            if not alias:
                from xafsmith import cli
                sc = cli._run_model(base)[4]
                gp = f2["summ"]["params"]
                dif = max(abs(sc["params"][k]["value"] - v["value"]) / max(abs(v["value"]), 1e-12) for k, v in gp.items())
                say(dif < 1e-10, f"GUI 联合拟合与 xafsmith fit 重跑：参数最大相对差 {dif:.2e}")
        # 覆盖范围：第 2 个数据集用不同的 kmax
        kmo = float(st["range"]["kmax"]) - 1.5
        st["over_" + id2] = {"kmax": f"{kmo:g}"}
        pg.refresh()
        f3 = run("第 2 个数据集覆盖 kmax")
        say(f3 is not None and f2 is not None and f3["summ"]["datasets"][1]["kmax"] == kmo
            and f3["summ"]["datasets"][0]["kmax"] == st["range"]["kmax"] and f3["summ"]["n_idp"] < f2["summ"]["n_idp"],
            "覆盖范围：" + ("无结果" if f3 is None else f"kmax {[d['kmax'] for d in f3['summ']['datasets']]}，Σ N_idp {f3['summ']['n_idp']:.2f}"))
        # 草稿：多数据集设置能存能恢复
        dr = session.save_draft("_b2test", S, P)
        made.append(dr)
        snap = session.load_draft(dr)
        before = {k: st[k] for k in ("multi", "datas", "over_" + id2, "fdirs_multi")}
        pt_key = [k for k in st if k.startswith("pathtab_") and id2 + "|" in k][0]
        pt_before = st[pt_key].copy()
        for k in list(before) + [pt_key]:
            st.pop(k)
        session.apply_pages(snap, dict(P), only=("fit",))
        same = all(st.get(k) == v for k, v in before.items()) and isinstance(st.get(pt_key), pd.DataFrame) \
            and np.array_equal(st[pt_key].astype(object).fillna("").astype(str).to_numpy(),
                       pt_before.astype(object).fillna("").astype(str).to_numpy())
        say(same, "草稿：multi、datas、范围覆盖、各数据集路径表保存并恢复")
    finally:
        st.update(multi=False)
        st.pop("over_" + id2, None)
        for k in [k for k in st if k.startswith("pathtab_") and id2 + "|" in k]:
            st.pop(k)
        for f in made:
            Path(f).unlink(missing_ok=True)
        if csv0 is None:
            FITS_CSV.unlink(missing_ok=True)
        else:
            FITS_CSV.write_bytes(csv0)
        if alias:
            S.groups.pop(k2, None)
        S.fits[:] = [f for f in S.fits if f["summ"].get("model") != "b2test_joint"]
        pg.refresh()


def irtaox_suite(app, w, S, P):
    """本机 IrTaOx 项目专用检查（样品名与已保存模型写死）。"""
    # 载入谱：按样品
    w.go("load")
    n = len(W.ERRORS)
    P["load"].state["samples"] = ["Ir foil", "IrO2", "IrCoOx_OCP", "IrCoOx_OCP_r"]
    P["load"].refresh()
    click(P["load"], "载入")
    wait(app)
    step("载入样品", n)
    print("   已载入:", list(S.groups))
    g = S.groups.get("IrO2")
    say(g is not None and "Ir foil" in S.groups and g.calib_ref == "data/raw/Ir/Ir foil",
        f"按样品载入：参比随样品载入，IrO2.calib_ref={getattr(g, 'calib_ref', None)}")

    # 载入谱：直接读文件（默认同批次参比）
    for f, ref in [("data/raw/20261105_Ta/Ta2O5", "data/raw/20261105_Ta/Ta_foil"),
                   ("data/raw/Ta/Ta2O5", "data/raw/Ta/Ta powder")]:
        n = len(W.ERRORS)
        W.find(P["load"], "imp_files").set_value([f], emit=True)
        r = W.find(P["load"], "imp_ref").value()
        say(r == ref, f"默认参比：{r}")
        click(P["load"], "读入")
        pump(app)
        step(f"读入 {f}", n)
        G = S.groups
        de_ref = S.calib[ref]["delta_e"]
        say(f in G and ref in G and abs(G[f].e_shift - de_ref) < 1e-9 and G[f].calib_ref == ref,
            f"{f} ΔE={G[f].e_shift:+.3f}（参比 {ref} {de_ref:+.3f}）")

    # 逐页
    for key in list(P):
        n = len(W.ERRORS)
        t = time.time()
        w.go(key)
        pump(app)
        step(f"页面 {key}（{time.time() - t:.1f} s）", n)

    # 去毛刺：IrO2 已有区间原样保存
    w.go("qc")
    cfg_path = PROJ / "xafsmith.json"
    before = json.loads(cfg_path.read_text(encoding="utf-8"))
    P["qc"].state["dg"] = ["IrO2"]
    P["qc"].refresh()
    n = len(W.ERRORS)
    click(P["qc"], "保存并重新载入")
    pump(app)
    step("去毛刺 保存", n)
    after = json.loads(cfg_path.read_text(encoding="utf-8"))
    say(after.get("deglitch") == before.get("deglitch") and after.get("deglitch_reason") == before.get("deglitch_reason")
        and getattr(S.groups["IrO2"], "deglitched", None) == before["deglitch"]["IrO2"], "去毛刺区间读回、写入不变")

    # 质量检查（后台任务，作用于副本）
    S.qc = None
    P["qc"].refresh()
    n = len(W.ERRORS)
    click(P["qc"], "运行检查")
    wait(app)
    step("质量检查", n)
    say(S.qc is not None and len(S.qc) > 0 and "error" not in S.qc, f"质量检查结果：{0 if S.qc is None else len(S.qc)} 条谱")

    # FEFF：内置 IrO2，FEFF6L
    w.go("feff")
    fp = P["feff"]
    fp.state.update(src="builtin", bname="IrO2", code="feff6", abs_IrO2="Ir", edge_IrO2="L3")
    fp.refresh()
    n = len(W.ERRORS)
    click(fp, "运行 FEFF")
    wait(app)
    step("FEFF6L 运行", n)
    if not ARGS.quick:
        fp.state["code"] = "feff8"
        fp.refresh()
        W.find(fp, "feff_rmax").setValue(3.6)
        W.find(fp, "feff_scf").setValue(3.5)
        out8 = W.find(fp, "feff_out").text()
        say("IrO2_IrL3_feff8" in out8, f"FEFF8L 吸收原子与边：{out8}")
        n = len(W.ERRORS)
        click(fp, "运行 FEFF")
        wait(app)
        step("FEFF8L 运行", n)
        from xafsmith.feff_wrap import feff_info
        d8 = PROJ / out8
        say("_feff8" in out8 and (d8 / "feff0001.dat").exists() and feff_info(d8)["code"] == "feff8",
            f"FEFF8L 输出 {out8}：费米能 {feff_info(d8).get('fermi_ev') if d8.exists() else None}")
        fp.state["code"] = "feff6"

    # 拟合：IrO2 第一壳层
    go_fit(w)
    pg = P["fit"].detailed_page
    from xafsmith.qt.state import feff_dirs
    d = [x for x in feff_dirs() if "IrO2_IrL3" in str(x) and "_feff8" not in str(x)][0]
    pg.state["data"] = "IrO2"
    pg.state["fdirs_IrO2"] = [str(d)]
    pg.state.setdefault("range", {})
    pg.refresh()
    pg.state["range"]["rmax"] = 2.1
    pg.refresh()
    n0 = len(S.fits)
    n = len(W.ERRORS)
    click(pg, "拟合")
    wait(app)
    step("EXAFS 拟合", n)
    say(len(S.fits) == n0 + 1 and S.fits[-1]["model"].get("sample") == "IrO2", "界面建的模型记录了样品名")
    t = texts(pg)
    say("残差 / 噪声" in t and "窗口内残差 RMS" in t, "拟合诊断显示残差/噪声")
    if S.fits:
        s = S.fits[-1]["summ"]
        print(f"   拟合: R={s['rfactor']:.4f} nvarys={s['nvarys']}", {k: round(v["value"], 4) for k, v in s["params"].items()})

    say("拟合质量检查" in t and "R 因子" in t and "注意事项与“拟合得好”的标准" in " ".join(
        b.text() for b in pg.findChildren(QPushButton)), "拟合质量检查与注意事项按钮")
    # 采纳拟合值：写回参数表；参数表可输入任意位小数
    n = len(W.ERRORS)
    click(pg, "采纳拟合值到参数")
    pt = pg._ptab["tab"]
    fitted = S.fits[-1]["summ"]["params"]
    good = all(abs(pt.m.df.loc[pt.m.df.name == k, "value"].iloc[0] - v["value"]) < 1e-12
               for k, v in fitted.items() if v["vary"] and not v["expr"] and k in set(pt.m.df.name))
    idx = pt.m.index(int((pt.m.df.name == "ss1").to_numpy().nonzero()[0][0]), list(pt.m.df.columns).index("value"))
    pt.m.setData(idx, "0.00412345")
    step("采纳拟合值", n)
    say(good and abs(pt.m.df.loc[pt.m.df.name == "ss1", "value"].iloc[0] - 0.00412345) < 1e-12
        and isinstance(pt.m.data(idx, W.Qt.ItemDataRole.EditRole), str),
        "采纳拟合值写回参数表；value 可输入 8 位小数")
    from xafsmith.qt.pages.fitting import show_fit_guide
    from xafsmith.qt.pages.process import show_wavelet_guide
    show_fit_guide(pg)
    show_wavelet_guide(pg)
    pump(app)
    say({"fit_guide", "wt_guide"} <= set(W._INFO), "注意事项、小波说明：独立窗口")
    gd = W._INFO.get("fit_guide")
    gt = [gd.tabs.tabText(i) for i in range(gd.tabs.count())] if gd is not None and gd.tabs is not None else []
    say(gt == ["拟合前", "拟合得好的标准", "多数据集联合拟合", "σ² 温度模型"], f"注意事项窗口四个标签页：{gt}")
    show_fit_guide(pg, 2)
    say(gd is not None and gd.tabs.currentIndex() == 2, "注意事项：可直接打开“多数据集联合拟合”页")
    show_fit_guide(pg, 3)
    say(gd.tabs.currentIndex() == 3 and "tempK" in W.QTextBrowser.toPlainText(gd.tabs.widget(3)), "注意事项：可直接打开“σ² 温度模型”页")
    for d_ in list(W._INFO.values()):
        d_.close()

    # 小波：极大值表与导出
    w.go("wavelet")
    P["wavelet"].state.update(k="IrO2", k2="Ir foil", kind="Morlet", kw=2)
    P["wavelet"].refresh()
    say(len(P["wavelet"].findChildren(W.Plot)[0].axes) == 2, "小波：两条谱左右对比")
    n = len(W.ERRORS)
    click(P["wavelet"], "导出数据与图")
    step("小波导出", n)
    wd = PROJ / "output" / "gui" / "wavelet"
    made = [wd / f"IrO2_morlet_k2{s}" for s in (".csv", "_maxima.csv", ".png", ".svg", ".txt", ".params.json")]
    import numpy as np
    mat = np.genfromtxt(made[0], delimiter=",", comments="#") if made[0].exists() else None
    say(all(p.exists() for p in made[:4]) and mat is not None and mat.shape[0] > 10 and mat.shape[1] > 10,
        f"小波导出文件：矩阵 {None if mat is None else mat.shape}")
    made2 = [wd / f"Ir_foil_morlet_k2{s}" for s in (".csv", "_maxima.csv", ".png", ".svg", ".txt", ".params.json")]
    say(made2[0].exists(), "小波导出：对比谱也导出")
    for p in made + made2:
        if p.exists():
            p.unlink()

    # 方法导出（SI 拟合表）
    w.go("methods")
    from xafsmith import si_text as si
    r = si.build([k for k in si.fit_keys() if k.startswith("IrO2|")][-1:])
    say("IrO2" in r["en"] and "FEFF" in r["en"] and len(r["table"]) >= 1 and "Table S" in r["en"],
        f"SI 方法文本：{len(r['en'])} 字符，表 {len(r['table'])} 行")

    # 已保存模型
    go_fit(w)
    pg.state["mf"] = "IrO2_1shell_ArtemisCompare.json"
    pg.refresh()
    n0, n = len(S.fits), len(W.ERRORS)
    click(pg, "运行")
    wait(app)
    step("运行已保存模型", n)
    s = S.fits[-1]["summ"]
    say(len(S.fits) == n0 + 1 and abs(s["params"]["s02"]["value"] - 0.816) < 0.01,
        f"已保存模型 IrO2：S0²={s['params']['s02']['value']:.3f}（期望 ≈0.816）")
    pg.state["mf"] = "TR1_TaO.json"
    pg.refresh()
    W.find(pg, "saved_smp").set_value(["IrTa-50", "IrTa-100"])
    n1, n = len(S.fits), len(W.ERRORS)
    click(pg, "运行")
    wait(app)
    step("已保存模型用于多个样品", n)
    say([f["summ"]["sample"] for f in S.fits[n1:]] == ["IrTa-50", "IrTa-100"], f"多样品运行：{[f['summ']['sample'] for f in S.fits[n1:]]}")
    from xafsmith.qt.state import feff_dirs
    d_ir = [x for x in feff_dirs() if "IrO2_IrL3" in str(x) and "_feff8" not in str(x)][0]
    multi_fit_checks(app, w, S, P, "IrO2", "IrCoOx_OCP", str(d_ir.relative_to(PROJ)), rng=dict(pg.state["range"]))
    if not ARGS.quick:
        pg.state["mf"] = "IrO2_1shell_ArtemisCompare.json"
        pg.refresh()
        click(pg, "运行")
        wait(app)
        n = len(W.ERRORS)
        click(pg, "运行稳健性检查")
        wait(app)
        step("稳健性检查", n)
        rb = S.fits[-1].get("robust")
        say(rb is not None and len(rb[0]) >= 7 and set(rb[1]["参数"]) == {"s02", "e0", "dr1", "ss1"},
            f"稳健性：{0 if rb is None else len(rb[0])} 个条件")
        # 取消：再跑一次稳健性检查，立即取消 → 不应写入结果、不算错误、按钮恢复、状态栏收起
        S.fits[-1].pop("robust", None)
        n = len(W.ERRORS)
        click(pg, "运行稳健性检查")
        say(bool(W._RUNNING) and bool(W._ACTIVE), "稳健性检查已在后台运行")
        W._RUNNING[-1][3].cancel()
        wait(app)
        say(S.fits[-1].get("robust") is None and len(W.ERRORS) == n and not W._ACTIVE and not w.bar.isVisible()
            and not w.cancel_btn.isVisible(),
            "稳健性检查取消：未写入结果、无错误、状态栏已收起")

    # 归一化：导出 .prj
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

    # XANES：边前峰
    w.go("xanes")
    P["xanes"].state["pk"] = "IrO2"
    P["xanes"].refresh()
    n = len(W.ERRORS)
    click(P["xanes"], "拟合边前峰")
    step("边前峰拟合", n)

    # 期刊出图
    w.go("pubfig")
    P["pubfig"].state.update(kind="xanes", name="_test_fig", sel=["IrO2", "Ir foil"])
    P["pubfig"].refresh()
    order_check(P["pubfig"])
    n = len(W.ERRORS)
    click(P["pubfig"], "保存到 output/figs/journal/")
    step("期刊出图", n)
    made = list((PROJ / "output" / "figs" / "journal").glob("_test_fig.*"))
    say({p.suffix for p in made} >= {".tiff", ".png", ".svg", ".txt"}, f"出图文件：{sorted(p.suffix for p in made)}")
    for p in made:
        p.unlink()
    # 配色方案与 Origin 说明（不启动 Origin）
    from xafsmith import pubfig as pf, origin_export as oe
    cols = pf.series_colors(["IrO2", "Ir foil"], "glacier", ["Ir foil"])
    say(len(pf.PALETTES) >= 20 and cols[0] == ("#1E5FBF", False) and cols[1][1], f"配色方案 {len(pf.PALETTES)} 种；标样画灰色")
    import tempfile
    with tempfile.TemporaryDirectory() as td:
        import matplotlib.pyplot as plt
        from xafsmith.qt.state import plain_rc
        with plain_rc():
            fig, _ = pf.xanes([S.groups["IrO2"], S.groups["Ir foil"]], offset=0.5, colors=cols)
        spec = oe.figure_spec(fig, td, "t", kind="xanes")
        g0 = spec["graphs"][0]
        say(g0["xlabel"] == "Energy (eV)" and g0["xlim"][0] > 10000 and g0["hide_y"] and g0["lines"][0]["legend"] == "IrO\\-(2)"
            and Path(g0["csv"]).exists(), f"Origin 说明：横轴 E、图例 {g0['lines'][0]['legend']}")
        plt.close(fig)

    # LCF
    w.go("lcf")
    P["lcf"].state.update(smp="IrCoOx_OCP", stds=["Ir foil", "IrO2"])
    P["lcf"].refresh()
    n = len(W.ERRORS)
    click(P["lcf"], "LCF")
    wait(app)
    step("LCF", n)
    say(S.extra.get("lcf") is not None, "LCF 结果")

    # 报告导出 + 方法导出
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
    # 只删除本次测试刚生成的汇总文件夹（必须位于 output/reports 之下）
    if good and d.parent == reports and d.name.startswith("汇总_"):
        shutil.rmtree(d)
    n = len(W.ERRORS)
    w.go("methods")
    click(P["methods"], "生成方法段落")
    step("方法段落", n)
    m = S.extra.get("methods") or {}
    say("AUTOBK" in m.get("en", "") and "XAFSmith" in m.get("zh", ""),
        f"方法段落：中文 {len(m.get('zh', ''))} 字，英文 {len(m.get('en', '').split())} 词")


def trend_pubfig_check(app, w, S, P):
    """C2：图片导出页的“趋势图”（需要会话里有 ≥ 2 个数据集的联合拟合）：预览、保存、Origin 脚本模式的误差列。"""
    from xafsmith import origin_export as oe
    joint = [f for f in S.fits if f["summ"].get("multi") and len(f["summ"].get("datasets", [])) >= 2]
    say(bool(joint), "趋势图前提：会话里有联合拟合")
    if not joint:
        return
    pg = P["pubfig"]
    old = {k: pg.state.get(k) for k in ("kind", "name", "fmts", "tr_fit")}
    pg.state.update(kind="trend", name="_test_trend", fmts=["png", "svg"])
    pg.state.pop("tr_fit", None)
    n = len(W.ERRORS)
    pg.refresh()
    pump(app, 0.5)
    step("趋势图页构建与预览", n)
    t = texts(pg)
    say("Trend of fitted structural parameters" in t and "1σ" in t, "趋势图：预览图注含误差棒说明")
    n = len(W.ERRORS)
    click(pg, "保存到 output/figs/journal/")
    step("趋势图保存", n)
    made = list((PROJ / "output" / "figs" / "journal").glob("_test_trend.*"))
    say({p.suffix for p in made} >= {".png", ".svg", ".txt"}, f"趋势图文件：{sorted(p.suffix for p in made)}")
    for p_ in made:
        p_.unlink()
    import tempfile
    from xafsmith import pubfig as pf, trend as tr
    meta, proc = tr.load_project_tables()
    tab = tr.trend_table(joint[-1]["summ"], joint[-1]["model"], meta, proc)
    with tempfile.TemporaryDirectory() as td:
        fig, _ = pf.trend(tab, "单栏 85 mm")
        r = oe.export(fig, td, "_t", kind="trend", use_originpro=False)
        import json as _j
        sp = _j.loads((Path(td) / "spec.json").read_text(encoding="utf-8"))
        import matplotlib.pyplot as plt
        plt.close(fig)
        say(r["mode"] == "script" and any(ln.get("symbol") for g_ in sp["graphs"] for ln in g_["lines"]),
            "趋势图：Origin 脚本模式写出符号线")
    pg.state.update({k: v for k, v in old.items() if v is not None})
    if old["kind"] is None:
        pg.state.pop("kind", None)
    pg.refresh()


def demo_suite(app, w, S, P):
    """公开数据演示项目的通用检查：载入、直接读入、逐页、已保存模型、LCF、出图、.prj、报告。"""

    # 载入谱：按样品（参比随样品一起载入）
    w.go("load")
    n = len(W.ERRORS)
    P["load"].state["samples"] = ["cu_metal_rt", "Fe_foil", "feo_rt1", "fe3c_rt"]
    P["load"].refresh()
    click(P["load"], "载入")
    wait(app)
    step("载入样品", n)
    G = S.groups
    say({"cu_metal_rt", "Fe_foil", "feo_rt1", "fe3c_rt"} <= set(G), f"已载入：{list(G)}")
    say(G["feo_rt1"].calib_ref == "data/raw/public/fe.060" and G["feo_rt1"].format == "xdi",
        f"feo_rt1：参比 {G['feo_rt1'].calib_ref}，格式 {G['feo_rt1'].format}")

    # 载入谱：直接读文件（自动识别格式，默认同批次参比）
    f, ref = "data/raw/public/ni_metal_rt.xdi", "data/raw/public/ni_metal_rt.xdi"
    n = len(W.ERRORS)
    W.find(P["load"], "imp_files").set_value([f], emit=True)
    r = W.find(P["load"], "imp_ref").value()
    say(r == ref, f"默认参比：{r}")
    click(P["load"], "读入")
    pump(app)
    step(f"读入 {f}", n)
    G = S.groups
    say(f in G and G[f].format == "xdi" and G[f].element == "Ni" and abs(G[f].e_shift - S.calib[ref]["delta_e"]) < 1e-9,
        f"{f}：{G[f].element} {G[f].edge}，ΔE={G[f].e_shift:+.3f}")

    # 逐页
    for key in list(P):
        n = len(W.ERRORS)
        t = time.time()
        w.go(key)
        pump(app)
        step(f"页面 {key}（{time.time() - t:.1f} s）", n)

    # 已保存模型：Cu 箔第一壳层（FEFF 路径文件见 tests/data/benchmark），结果与基准测试同一范围
    model = {"name": "test_cu_demo", "sample": "cu_metal_rt", "kmin": 3, "kmax": 17, "dk": 4, "window": "kaiser",
             "kweight": 2, "rmin": 1.4, "rmax": 3.0, "fitspace": "r",
             "params": {"amp": {"value": 1.0, "vary": True}, "del_e0": {"value": 0.0, "vary": True},
                        "sig2": {"value": 0.0, "vary": True}, "del_r": 0.0},
             "paths": [{"file": "../benchmark/feffcu01.dat", "label": "Cu-Cu", "s02": "amp", "e0": "del_e0",
                        "sigma2": "sig2", "deltar": "del_r"}]}
    mf = PROJ / "models" / "test_cu_demo.json"
    mf.parent.mkdir(exist_ok=True)
    mf.write_text(json.dumps(model, ensure_ascii=False, indent=2), encoding="utf-8")
    try:
        go_fit(w)
        pg = P["fit"].detailed_page
        pg.state["mf"] = mf.name
        pg.refresh()
        n0, n = len(S.fits), len(W.ERRORS)
        click(pg, "运行")
        wait(app)
        step("运行已保存模型（Cu 箔）", n)
        s = S.fits[-1]["summ"] if len(S.fits) == n0 + 1 else None
        say(s is not None and 0.88 < s["params"]["amp"]["value"] < 0.96 and abs(s["params"]["del_e0"]["value"]) < 10
            and s["rfactor"] < 0.02,
            "Cu 箔拟合：" + ("无结果" if s is None else f"S0²={s['params']['amp']['value']:.3f}，R={s['rfactor']:.4f}"))
        say("残差 / 噪声" in texts(pg), "拟合诊断显示残差/噪声")
    finally:
        mf.unlink(missing_ok=True)
        (PROJ / "output" / "fits" / "test_cu_demo.params.json").unlink(missing_ok=True)

    # B2：多数据集联合拟合（演示项目没有 FEFF 目录：用基准测试的 Cu 路径文件临时建一个；第 2 个数据集是 Cu 谱的副本）
    fd = PROJ / "output" / "feff" / "_b2test_Cu_CuK"
    fd.mkdir(parents=True, exist_ok=True)
    shutil.copy(PROJ.parent / "benchmark" / "feffcu01.dat", fd / "feff0001.dat")
    try:
        multi_fit_checks(app, w, S, P, "cu_metal_rt", "cu_b2copy", "output/feff/_b2test_Cu_CuK",
                         rng=dict(kmin=3, kmax=17, dk=4, win="kaiser", kws=[2], rmin=1.4, rmax=3.0, space="r"), alias=True)
        container_checks(app, w, S, P, "cu_metal_rt", "output/feff/_b2test_Cu_CuK")
        restraint_checks(app, w, S, P, "cu_metal_rt", "output/feff/_b2test_Cu_CuK")
        sigma2_checks(app, w, S, P, "cu_metal_rt", "output/feff/_b2test_Cu_CuK")
        sigma2_dialog_checks(app, w, S, P, "cu_metal_rt", "cu_b6copy", "output/feff/_b2test_Cu_CuK")
        msbind_checks(app, w, S, P, "cu_metal_rt", "output/feff/_b2test_Cu_CuK")
    finally:
        (fd / "feff0001.dat").unlink(missing_ok=True)
        fd.rmdir()

    # 归一化：导出 .prj
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

    # 期刊出图
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

    # LCF：Fe3C 用 Fe 箔与 FeO 拟合（只检查流程能出结果，不对比例作结论）
    w.go("lcf")
    P["lcf"].state.update(smp="fe3c_rt", stds=["Fe_foil", "feo_rt1"])
    P["lcf"].refresh()
    n = len(W.ERRORS)
    click(P["lcf"], "LCF")
    wait(app)
    step("LCF", n)
    say(S.extra.get("lcf") is not None, "LCF 结果")

    # 报告导出
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

    # 后台任务：批量处理立即取消；质量检查运行中页面重建（旧按钮被删除）后仍正常收尾
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


def u1_checks(app, w):
    """U1：切页不丢输入、任务登记与按钮禁用、toast 队列、未保存修改"""
    import threading
    from PySide6.QtWidgets import QTabWidget
    S, P = w.S, w.pages
    # 1. 切页后输入仍在，且数据没变时不重建
    if any(has for has in (len(S.groups),)):
        g = next(k for k, g in S.groups.items() if hasattr(g, "chi"))
        P["chi"].state["sel"] = [g]
        w.go("chi")
        pump(app)
        cnt = []
        orig = P["chi"].build
        P["chi"].build = lambda: (cnt.append(1), orig())[1]
        tb = [t for t in P["chi"].findChildren(QTabWidget) if t.count() == 4][0]
        tb.setCurrentIndex(2)
        w.go("norm")
        pump(app)
        w.go("chi")
        pump(app)
        tb2 = [t for t in P["chi"].findChildren(QTabWidget) if t.count() == 4][0]
        say(tb2.currentIndex() == 2 and not cnt, f"切页后内页标签仍在、数据未变时不重建（重建 {len(cnt)} 次）")
        S.emit("groups")                     # 数据版本变了 → 回来时重建，标签仍恢复
        w.go("norm")
        w.go("chi")
        pump(app)
        tb3 = [t for t in P["chi"].findChildren(QTabWidget) if t.count() == 4][0]
        say(len(cnt) == 1 and tb3.currentIndex() == 2, "数据变了才重建，内页标签仍恢复")
        P["chi"].build = orig
        del P["chi"].build
    # 2. 任务登记：运行中重复启动被拒，重建出的新按钮同样禁用
    ev = threading.Event()
    b1 = QPushButton("run")
    W.bind_task(b1, "u1test", "u1grp")
    done = []
    h = W.run_task(w, lambda: ev.wait(10), lambda r: done.append(r), "busy", b1, key="u1test", excl="u1grp")
    pump(app)
    b2 = QPushButton("run2")
    W.bind_task(b2, "u1other", "u1grp")
    h2 = W.run_task(w, lambda: 1, lambda r: None, key="u1other", excl="u1grp")
    say(h is not None and h2 is None and not b1.isEnabled() and not b2.isEnabled()
        and W.task_running("u1test") and W.task_running(excl="u1grp") and W.running_count() >= 1,
        "任务运行中：同 key / 同互斥组不能再启动，新按钮已禁用")
    ev.set()
    wait(app, 30)
    say(done and b1.isEnabled() and b1.text() == "run" and b2.isEnabled() and not W.task_running("u1test"),
        "任务结束后按钮恢复")
    # 3. toast 队列
    tz = w._toaster
    tz.q.clear()
    tz.timer.stop()
    tz.label.hide()
    w.toast("a")
    w.toast("b")
    w.toast("b")
    w.toast("c", "err")
    say(len(tz.q) == 2 and tz.label.text() == "a", f"toast 排队：显示 a，队列 {[t for t, _ in tz.q]}")
    tz.timer.stop()
    tz._next()
    say(tz.label.text() == "b", "toast 依次显示")
    tz.q.clear()
    tz.timer.stop()
    tz.label.hide()
    # 4. 未保存修改与提示条
    pg = P["data"]
    pg._meta_dirty = True
    say(bool(pg.dirty()), "数据登记：表格被编辑后 dirty() 有提示")
    pg.discard_changes()
    say(not pg.dirty(), "放弃修改后 dirty() 清零")
    pg.notice("err", "测试", [f"e{i}" for i in range(8)])
    pump(app)
    say(any("另 3 条" in l.text() for l in pg.findChildren(QLabel)), "页顶提示条：超过 5 条折叠")
    pg.clear_notice()
    say(pg._notice is None, "提示条可关闭")


def order_check(page):
    """图片导出：作图顺序列表倒序后，图例顺序随之倒过来"""
    from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
    ol = page.findChildren(W.OrderList)
    if not ol:
        say(False, "图片导出：找不到作图顺序列表")
        return

    def legend():
        cs = page.findChildren(FigureCanvasQTAgg)
        leg = cs[-1].figure.axes[0].get_legend() if cs else None
        return [t.get_text() for t in leg.get_texts()] if leg else []
    before = legend()
    ol[0].reverse()
    after = legend()
    say(len(before) >= 2 and after == before[::-1] and page.state.get("order") == ol[0].value(),
        f"图片导出：倒序后图例 {before} → {after}")
    ol[0].reverse()


def u3_checks(app, w):
    """U3：范围联动、防抖、滚轮防误触、E0 校验、帮助窗口 toast"""
    from PySide6.QtCore import QPoint, QPointF, Qt
    from PySide6.QtWidgets import QApplication
    from PySide6.QtGui import QWheelEvent
    # 范围联动
    lo, hi = W.num(1, 0, 10, 0.1), W.num(5, 0, 25, 0.1)
    W.link_range(lo, hi, 0.5)
    lo.setValue(9)
    say(hi.value() >= 9.5, f"kmin 超过 kmax：kmax 被顶到 {hi.value():.1f}")
    hi.setValue(2)
    say(lo.value() <= 1.5, f"kmax 低于 kmin：kmin 被压到 {lo.value():.1f}")
    # 防抖
    cnt = []
    d = W.debounced(w, lambda: cnt.append(1), 60)
    for _ in range(5):
        d()
    say(not cnt, "防抖：连续 5 次调用，尚未执行")
    d.flush()
    say(len(cnt) == 1, "防抖：flush 只执行一次")
    for _ in range(3):
        d()
    t0 = time.time()
    while len(cnt) < 2 and time.time() - t0 < 2:
        pump(app)
    say(len(cnt) == 2, "防抖：到时只执行一次")
    # 滚轮：未获得焦点时忽略
    sp = W.num(1, 0, 10, 0.1)
    sp.show()
    ev = QWheelEvent(QPointF(5, 5), QPointF(5, 5), QPoint(0, 0), QPoint(0, 120), Qt.MouseButton.NoButton,
                     Qt.KeyboardModifier.NoModifier, Qt.ScrollPhase.NoScrollPhase, False)
    QApplication.sendEvent(sp, ev)
    say(sp.value() == 1 and not ev.isAccepted(), "数值框未获得焦点：滚轮被忽略")
    sp.close()
    # E0 非法：红框
    from xafsmith.qt.pages.process._shared import norm_fields
    nf = norm_fields(dict(W.__dict__.get("_np", {}) or w.S.norm_par))
    nf.e0.setText("abc")
    r = nf.read()
    say(r["e0"] is None and nf.e0.property("invalid") is True, "E0 输入非法：红框并按自动 E0 处理")
    nf.e0.setText("")
    nf.read()
    say(nf.e0.property("invalid") is False, "E0 清空后红框消失")
    # pre1 < pre2 联动
    nf.widgets["pre2"].setValue(-200)
    say(nf.widgets["pre1"].value() < nf.widgets["pre2"].value(), "pre1 < pre2 联动")
    # 窗口矩形限制在屏幕内；快捷键与恢复默认值
    from xafsmith.qt.app import _avail, _fit_rect
    x, y, ww, hh = _fit_rect(-5000, 99999, 99999, 99999)
    av = _avail()
    say(ww <= av.width() and hh <= av.height() and av.left() <= x and y + hh <= av.bottom() + 1, "窗口位置与大小被限制在屏幕内")
    from PySide6.QtGui import QShortcut
    seqs = {q.key().toString() for q in w.findChildren(QShortcut)}
    say({"F1", "Ctrl+O", "Esc", "Ctrl+1", "Ctrl+9"} <= seqs, "快捷键 F1 / Ctrl+O / Esc / Ctrl+1…9 已登记")
    nf.set_values(dict(e0=None, pre1=-120.0, pre2=-25.0, norm1=80.0, norm2=-5.0, nnorm=1, smooth_ev=1.0))
    r = nf.read()
    say(r["pre1"] == -120 and r["norm1"] == 80 and r["nnorm"] == 1, "恢复默认值：参数写回输入框")
    # 帮助窗口有 toast
    w.open_help("gui")
    hw = w._help
    hw.toast("help-toast")
    say(hw._toaster.label.text() == "help-toast" and hw._toaster.label.isVisible(), "帮助窗口 toast 可见")
    hw.hide()


def wizard_check(app):
    """列映射向导：用临时目录里的合成数据（非标准列名）试读，并截获保存（不写项目的 xafsmith.json）。"""
    import tempfile
    import numpy as np
    from xafsmith.qt import state as st
    from xafsmith.qt.colwizard import ColumnWizard
    d = Path(tempfile.mkdtemp(prefix="xafsmith_wizard_"))
    try:
        e = np.linspace(8919, 9179, 80)
        mu = 0.3 + 0.8 / (1 + np.exp(-(e - 8979) / 2))
        f = d / "bl_scan.dat"
        lines = ["# beamline X", "# Energy Mon Det"]
        lines += [f"{a:.4f} 100000 {1e5 * np.exp(-m):.3f}" for a, m in zip(e, mu)]
        f.write_text(chr(10).join(lines) + chr(10), encoding="utf-8")
        dlg = ColumnWizard(None, f)
        say(dlg.info is not None and dlg.cb["energy"].value() == 0, "列映射向导：打开并按列名预选能量列")
        dlg.cb["i0"].setCurrentIndex(dlg.cb["i0"]._vals.index(1))
        dlg.cb["it"].setCurrentIndex(dlg.cb["it"]._vals.index(2))
        say(dlg.test() and "模式 trans" in dlg.result.text(), "列映射向导：试读成功（透射）")
        saved = {}
        old_save, old_load = st.save_cfg, st.load_cfg
        st.save_cfg, st.load_cfg = (lambda c: saved.update(c)), (lambda: {"edges": {}})
        try:
            dlg.name.setText("bl_test")
            dlg.save()
        finally:
            st.save_cfg, st.load_cfg = old_save, old_load
        say(dlg.saved == "bl_test" and saved.get("formats", {}).get("bl_test", {}).get("i0") == "Mon", "列映射向导：保存为模板（列名）")
        dlg2 = ColumnWizard(None, f)
        dlg2.cb["energy"].setCurrentIndex(0)
        dlg2.name.setText("bsrf")
        dlg2.cb["i0"].setCurrentIndex(dlg2.cb["i0"]._vals.index(1))
        dlg2.cb["it"].setCurrentIndex(dlg2.cb["it"]._vals.index(2))
        dlg2.save()
        say(dlg2.saved is None, "列映射向导：内置格式名不能当模板名")
    finally:
        shutil.rmtree(d, ignore_errors=True)


def main():
    W.QUIET["v"] = True
    app, w = make_window(str(PROJ), lang="zh")
    w.resize(1440, 920)
    w.show()
    S = w.S
    P = w.pages
    n = len(W.ERRORS)
    w.go("home")
    step("启动", n)
    no_console_check("IrO2" if IRTAOX else "cu_metal_rt")
    copy_register_check(app, w)
    wizard_check(app)
    if not IRTAOX:
        quickfit_checks(app, w)
        guess_checks(app, w)
    S, P = w.S, w.pages

    # 数据登记：检查
    w.go("data")
    n = len(W.ERRORS)
    click(P["data"], "运行检查")
    pump(app)
    step("数据登记：运行检查", n)

    # AI 助手
    w.go("agent")
    say("xafsmith" in " ".join(e.toPlainText() for e in P["agent"].findChildren(W.QPlainTextEdit))
        and any(b.text() == "写入 / 更新 AI 说明文件" for b in P["agent"].findChildren(QPushButton)),
        "AI 助手：写入按钮与命令路径")

    (irtaox_suite if IRTAOX else demo_suite)(app, w, S, P)
    n = len(W.ERRORS)
    u1_checks(app, w)
    u3_checks(app, w)
    step("U1 检查", n)

    # 制样指导：元素来自化学式；吸收边查询：滤片
    w.go("planner")
    P["planner"].state.update(formula="IrCo0.2O2", el="Ir", ed="L3")
    P["planner"].refresh()
    say("Ir, Co, O" in texts(P["planner"]), "制样指导：体系元素由化学式读取")
    from xafsmith import mut_planner as xm
    r = xm.fluor_filter("Fe", "K")
    say(r["table"]["filter"].iloc[0] == "Mn", f"荧光滤片 Fe K → {r['table']['filter'].iloc[0]}（Z−1）")
    w.go("elements")
    P["elements"].state["el"] = "Ta"
    P["elements"].refresh()
    say("Ta" in texts(P["elements"]) and "tantalum" in texts(P["elements"]), "吸收边查询：Ta")
    # 项目页不在导航里；流程与本项目悬浮窗
    w.go("data")
    w.flow_btn.open()
    pump(app, 0.1)
    say("home" not in w.nav and w.flow_btn.pop is not None and "本项目" in texts(w.flow_btn.pop), "流程与本项目悬浮窗")
    c1 = w.flow_btn._cache
    w.flow_btn.close_pop()
    w.flow_btn.open()
    say(w.flow_btn._cache is c1, "U5：流程弹窗计数按 data_key 缓存")
    w.flow_btn.close_pop()
    # U5：导航提示（无谱时 norm 变灰，有谱后恢复）
    w._nav_hints()
    say(bool(w.S.groups) or w.nav["norm"].property("hint") is True, "U5：缺前置数据的导航按钮变灰")

    # 署名与免责声明始终可见
    lbls = " ".join(l.text() for l in w.findChildren(QLabel))
    say("Claude Opus 5.5" in lbls and "Athena / Artemis" in lbls, "侧栏署名与底部免责声明")
    # 使用指南：独立窗口，讲义在最后，“关于”单独一页
    from xafsmith.qt.help import HelpWindow
    cur = w.S.extra.get("page")
    w.go("help")
    hw = w._help
    keys = list(hw.btn)
    about_txt = " ".join(l.text() for l in hw.btn["about"][1].findChildren(QLabel))
    say(isinstance(hw, HelpWindow) and hw.isVisible() and w.S.extra.get("page") == cur
        and keys[:5] == ["gui", "tutorial", "joint", "quality", "basics"] and keys[-1] == "about"
        and "Claude Opus 5.5" in about_txt and "Athena / Artemis" in about_txt,
        f"使用指南独立窗口：{keys}，主窗口仍在 {cur}")
    # U5：帮助窗口目录、锚点跳转、查找、后退
    from xafsmith.qt.help import DocPane
    hw.show_tab("basics")
    pane = hw.btn["basics"][1].findChild(DocPane)
    pane.resize(900, 600)
    pump(app, 0.1)
    n_h = len(pane.heads)
    from PySide6.QtCore import QUrl
    before = pane.tb.verticalScrollBar().value()
    tgt = [h for h in pane.heads if h[0] == 2][-1]
    pane._link(QUrl("#" + tgt[3]))
    pump(app, 0.1)
    moved = pane.tb.verticalScrollBar().value() > before
    pane.find_edit.setText(tgt[1][:4])
    pane.find(False)
    found = pane.tb.textCursor().hasSelection()
    pane.back()
    say(n_h > 5 and pane.toc.count() > 5 and moved and found and pane.tb.verticalScrollBar().value() == before,
        f"U5：帮助目录 {pane.toc.count()} 项、#锚点跳转、查找、后退")
    hw.close()

    # 清空工作区：同一项目换一批样品从头处理
    n = len(W.ERRORS)
    ng = len(w.S.groups)
    w.clear_workspace()
    pump(app)
    step("清空工作区", n)
    say(ng > 0 and not w.S.groups and not w.S.fits and w.S.extra.get("page") == "load",
        f"清空工作区：{ng} 条谱 → {len(w.S.groups)} 条，回到“载入谱”页")

    # 关闭时询问保存（自动测试不弹窗 → 视为保存）；启动画面
    from xafsmith.cli import _splash
    sp = _splash()
    say(w._ask_save_on_close() == "save" and sp is not None, "关闭询问（测试中按保存）、启动画面")
    if sp is not None:
        sp.close()

    # 英文界面逐页（不保存语言设置）
    W.LANG["v"] = "en"
    w.rebuild()
    for key in list(w.pages):
        n = len(W.ERRORS)
        w.go(key)
        pump(app)
        step(f"English: {key}", n)
    lbls = " ".join(l.text() for l in w.findChildren(QLabel))
    say("Claude Opus 5.5" in lbls and "no warranty" in lbls, "English：署名与免责声明")
    print("全部通过" if OK[0] else "存在失败")
    W.shutdown_tasks()          # 后台线程全部结束后再退出（线程对象在运行中被销毁会 abort）
    w.close()
    app.processEvents()
    return 0 if OK[0] else 1


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(main())
