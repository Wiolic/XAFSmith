"""图形界面自动测试（PySide6，无窗口运行）：逐页构建、载入、去毛刺、FEFF6L/8L、拟合、诊断、已保存模型、
稳健性、.prj 导出、边前峰、期刊出图、LCF、汇总、方法段落、SI，最后用英文界面再逐页构建一遍。

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
        b.text() for b in pg.findChildren(W.QToolButton)), "拟合质量检查与注意事项")

    # 小波：极大值表与导出
    w.go("wavelet")
    P["wavelet"].state.update(k="IrO2", kind="Morlet", kw=2)
    P["wavelet"].refresh()
    n = len(W.ERRORS)
    click(P["wavelet"], "导出数据与图")
    step("小波导出", n)
    wd = PROJ / "output" / "gui" / "wavelet"
    made = [wd / f"IrO2_morlet_k2{s}" for s in (".csv", "_maxima.csv", ".png", ".svg", ".txt", ".params.json")]
    import numpy as np
    mat = np.genfromtxt(made[0], delimiter=",", comments="#") if made[0].exists() else None
    say(all(p.exists() for p in made[:4]) and mat is not None and mat.shape[0] > 10 and mat.shape[1] > 10,
        f"小波导出文件：矩阵 {None if mat is None else mat.shape}")
    for p in made:
        if p.exists():
            p.unlink()

    # SI 方法
    w.go("si")
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

    # LCF
    w.go("lcf")
    P["lcf"].state.update(smp="IrCoOx_OCP", stds=["Ir foil", "IrO2"])
    P["lcf"].refresh()
    n = len(W.ERRORS)
    click(P["lcf"], "LCF")
    step("LCF", n)
    say(S.extra.get("lcf") is not None, "LCF 结果")

    # 汇总 + 方法段落
    w.go("summary")
    n = len(W.ERRORS)
    click(P["summary"], "生成汇总")
    wait(app)
    step("汇总报告", n)
    sd = S.extra.get("summary_dir")
    d = Path(sd).resolve() if sd else None
    good = d is not None and (d / "汇总.xlsx").exists() and (d / "汇总报告.html").exists()
    say(good, f"汇总文件：{d.name if d else '—'}")
    reports = (PROJ / "output" / "reports").resolve()
    # 只删除本次测试刚生成的汇总文件夹（必须位于 output/reports 之下）
    if good and d.parent == reports and d.name.startswith("汇总_"):
        shutil.rmtree(d)
    n = len(W.ERRORS)
    click(P["summary"], "生成方法段落")
    step("方法段落", n)
    m = S.extra.get("methods") or {}
    say("AUTOBK" in m.get("en", "") and "XAFSmith" in m.get("zh", ""),
        f"方法段落：中文 {len(m.get('zh', ''))} 字，英文 {len(m.get('en', '').split())} 词")

    # 署名与免责声明始终可见
    lbls = " ".join(l.text() for l in w.findChildren(QLabel))
    say("Claude Opus 5.5" in lbls and "Athena / Artemis" in lbls, "侧栏署名与底部免责声明")

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
