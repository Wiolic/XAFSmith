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
import os
import shutil
import sys
import time
from pathlib import Path

ap = argparse.ArgumentParser()
DEMO = Path(__file__).resolve().parent / "data" / "demo_project"
ap.add_argument("--project", default=str(DEMO), help="项目目录；默认是公开数据的演示项目（不读 XAFSMITH_PROJECT，避免误测真实项目）")
ap.add_argument("--quick", action="store_true", help="跳过 FEFF8L 与稳健性检查（较慢）")
ARGS = ap.parse_args()
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


def restraint_checks(app, w, S, P, k1, fdir):
    """B3：拟合页软约束表。空表 → 模型无 restraints 键；添加一行 → 拟合 → 结果区有软约束表；草稿保存再读回表内容相同。"""
    import numpy as np
    import pandas as pd
    from xafsmith.qt import session
    pg = P["fit"]
    w.go("fit")
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
    pg = P["fit"]
    w.go("fit")
    st = pg.state
    st.update(multi=False, data=k1)
    st["fdirs_" + k1] = [str(PROJ / fdir)]
    for k in [k for k in st if k.startswith("temp_")]:
        st.pop(k)
    st.pop("use_tmodel", None)
    pg.refresh()
    pump(app)
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
        if tc.isChecked():                     # 路径已用温度模型时，刷新后勾选框会自动勾上；先取消，检查“不勾不拟合”
            tc.setChecked(False)
            pump(app, 0.1)
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
    finally:
        for k in [k for k in st if k.startswith("temp_")]:
            st.pop(k)
        S.fits[:] = S.fits[:n0]
        pg.refresh()


def sigma2_dialog_checks(app, w, S, P, k1, k2, fdir):
    """B6 ⑧：“σ² 模型…”对话框。单数据集：写表达式 + 建 θ / 静态项参数（缺省 50–2000 K、静态项无下限）；
    联合拟合：应用到所有数据集的同一壳层，各数据集温度进模型，联合拟合能跑。k2 是 k1 的副本（演示项目只有一条 Cu 谱）。"""
    import copy
    import numpy as np
    from xafsmith import pipeline as pl
    from xafsmith.qt.pages.fitting import sigma2_dialog as sd
    pg = P["fit"]
    w.go("fit")
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
        say(par.loc["thD1", "min"] == 50 and par.loc["thD1", "max"] == 2000 and par.loc["thD1", "value"] == 300
            and par.loc["ss0_1", "value"] == 0 and np.isnan(par.loc["ss0_1", "min"]) and np.isnan(par.loc["ss0_1", "max"])
            and "tempK" not in par.index, "参数表：thD1（300，50–2000）、ss0_1（0，无下限）")
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
    pg = P["fit"]
    w.go("fit")
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
            w.go("fit")
            # 保存
            n = len(W.ERRORS)
            click(pg, "保存结果")
            step("保存多数据集拟合", n)
            base = safe(s2["model"])
            fig1, fig2 = (PROJ / "output" / "figs" / f"{base}_{i}_fit.png" for i in (id1, id2))
            mj = PROJ / "models" / f"{base}.json"
            made += [fig1, fig2, mj, PROJ / "output" / "fits" / f"{base}.fit_report.txt"]
            dfc = pd.read_csv(FITS_CSV)
            last = dfc[dfc["model"] == s2["model"]]
            say(fig1.exists() and fig2.exists() and mj.exists() and set(last["dataset"]) == {id1, id2},
                f"保存：{fig1.name}、{fig2.name}、CSV dataset 列 {sorted(set(last['dataset']))}")
            md = json.loads(mj.read_text(encoding="utf-8"))
            say("datasets" in md and "sample" not in md and "paths" not in md and [d["id"] for d in md["datasets"]] == [id1, id2],
                "模型 json 写入 datasets（顶层无 sample / paths）")
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
        w.go("fit")
        pg = P["fit"]
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
        restraint_checks(app, w, S, P, "cu_metal_rt", "output/feff/_b2test_Cu_CuK")
        sigma2_checks(app, w, S, P, "cu_metal_rt", "output/feff/_b2test_Cu_CuK")
        sigma2_dialog_checks(app, w, S, P, "cu_metal_rt", "cu_b6copy", "output/feff/_b2test_Cu_CuK")
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
        and keys[:4] == ["gui", "tutorial", "quality", "basics"] and keys[-1] == "about"
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
