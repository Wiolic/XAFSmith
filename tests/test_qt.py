"""图形界面自动测试（PySide6，无窗口运行）：逐页构建、载入、去毛刺、FEFF6L/8L、拟合、诊断、已保存模型、
稳健性、.prj 导出、边前峰、图片导出（配色、Origin 说明）、LCF、报告导出、方法导出、制样指导、吸收边查询，最后用英文界面再逐页构建一遍。

运行：python tests/test_qt.py --project <项目目录>
本测试使用 IrTaOx 项目的样品名（Ir foil、IrO2、IrCoOx_OCP … 与 Ta 批次）；其他项目请改样品名。
测试不改用户保存的界面语言；测试生成的临时文件会删除。
"""
import argparse
import json
import os
import shutil
import sys
import time
from pathlib import Path

ap = argparse.ArgumentParser()
ap.add_argument("--project", default=os.environ.get("XAFSMITH_PROJECT", "."))
ap.add_argument("--quick", action="store_true", help="跳过 FEFF8L 与稳健性检查（较慢）")
ARGS = ap.parse_args()
os.environ["XAFSMITH_PROJECT"] = str(Path(ARGS.project).resolve())
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ["XAFSMITH_NO_RECENT"] = "1"          # 不写入用户的“最近的项目”

from PySide6.QtWidgets import QApplication, QLabel, QPushButton   # noqa: E402

from xafsmith.qt import widgets as W                                 # noqa: E402
from xafsmith.qt.app import make_window                              # noqa: E402

PROJ = Path(os.environ["XAFSMITH_PROJECT"])
OK = [True]


def say(good, what):
    print(f"[{'ok' if good else 'FAIL'}] {what}")
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


def no_console_check():
    """桌面快捷方式用 pythonw 启动：没有控制台（sys.stdout 为 None）时处理也必须正常"""
    from xafsmith.qt import app as qapp
    from xafsmith import pipeline as pl
    out, err = sys.stdout, sys.stderr
    sys.stdout = sys.stderr = None
    try:
        qapp._no_console_output()
        pl.build_sample("IrO2")
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
    src = sorted((PROJ / "data" / "raw" / "Ir").glob("Ir*"))
    src = [str(p) for p in src if p.is_file()][:2]
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


def main():
    W.QUIET["v"] = True
    app, w = make_window(str(PROJ), lang="zh", dark=False)
    w.resize(1440, 920)
    w.show()
    S = w.S
    P = w.pages
    n = len(W.ERRORS)
    w.go("home")
    step("启动", n)
    no_console_check()
    copy_register_check(app, w)
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
    w.go("fit")
    pg = P["fit"]
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
    w.go("fit")
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
    w.flow_btn.close_pop()

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
        and keys[:4] == ["gui", "tutorial", "quality", "basics"] and keys[-1] == "about"
        and "Claude Opus 5.5" in about_txt and "Athena / Artemis" in about_txt,
        f"使用指南独立窗口：{keys}，主窗口仍在 {cur}")
    hw.close()

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
    return 0 if OK[0] else 1


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(main())
