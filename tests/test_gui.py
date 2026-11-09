"""GUI 自动测试（Streamlit AppTest）：逐页渲染、载入、FEFF、拟合、LCF，检查无异常。

运行：python tests/test_gui.py --project <项目目录>
本测试使用 IrTaOx 项目的样品名（Ir foil、IrO2、IrCoOx_OCP …与 Ta 批次）；其他项目请改样品名。
"""
import argparse
import json
import os
import sys
from pathlib import Path

ap = argparse.ArgumentParser()
ap.add_argument("--project", default=os.environ.get("XAFSMITH_PROJECT", "."))
os.environ["XAFSMITH_PROJECT"] = str(Path(ap.parse_args().project).resolve())   # 必须在导入 xafsmith 之前

import xafsmith                                     # noqa: E402
from streamlit.testing.v1 import AppTest            # noqa: E402

from xafsmith.feff_wrap import feff_info as xfeff_info   # noqa: E402
from xafsmith import update as _xup                      # noqa: E402

_load = _xup.load_settings
_xup.load_settings = lambda: {**_load(), "lang": "zh"}   # 测试固定用中文界面，不改用户保存的语言设置

APP = str(Path(xafsmith.__file__).resolve().parent / "gui.py")
PROJ = Path(os.environ["XAFSMITH_PROJECT"])


def check(at, where):
    errs = [e.value for e in at.exception] + [e.value for e in at.error]
    print(f"[{'FAIL' if errs else 'ok'}] {where}" + (f": {errs}" if errs else ""))
    return not errs


def main():
    ok = True
    at = AppTest.from_file(APP, default_timeout=300).run()
    ok &= check(at, "启动")
    # ⓪ 项目：数据标准检查
    [b for b in at.button if b.label == "运行检查"][0].click().run()
    ok &= check(at, "⓪ 项目：运行检查")
    at.sidebar.radio(key="nav_page").set_value("① 数据导入").run()
    # ① 按 meta 载入
    at.multiselect(key="meta_samples").set_value(["Ir foil", "IrO2", "IrCoOx_OCP", "IrCoOx_OCP_r"]).run()
    at.button(key="load_meta").click().run()
    ok &= check(at, "载入样品")
    print("   已载入:", list(at.session_state["groups"].keys()))
    g = at.session_state["groups"]["IrO2"]
    good = "Ir foil" in at.session_state["groups"] and g.calib_ref == "data/raw/Ir/Ir foil"
    print(f"   [{'ok' if good else 'FAIL'}] meta 载入：参比随样品载入，IrO2.calib_ref={g.calib_ref}")
    ok &= good
    # ① 文件读入：必须选参比；默认选同批次参比，参比一起读入，ΔE 来自该参比
    for f, ref in [("data/raw/20261105_Ta/Ta2O5", "data/raw/20261105_Ta/Ta_foil"),
                   ("data/raw/Ta/Ta2O5", "data/raw/Ta/Ta powder")]:
        fm = [m for m in at.multiselect if m.label.startswith("从项目中选择文件")][0]
        fm.set_value([f]).run()
        rs = at.selectbox(key="imp_ref")
        print(f"   默认参比: {rs.value}")
        ok &= rs.value == ref
        [b for b in at.button if b.label == "读入"][0].click().run()
        ok &= check(at, f"读入 {f}")
        G = at.session_state["groups"]
        de_ref = at.session_state["calib"][ref]["delta_e"]
        good = f in G and ref in G and abs(G[f].e_shift - de_ref) < 1e-9 and G[f].calib_ref == ref
        print(f"   [{'ok' if good else 'FAIL'}] {f} ΔE={G[f].e_shift:+.3f}（参比 {ref} {de_ref:+.3f}）")
        ok &= good
    pages = [r for r in at.sidebar.radio(key="nav_page").options]
    for p in pages:
        at.sidebar.radio(key="nav_page").set_value(p).run()
        ok &= check(at, p)
    # ② 去毛刺：用 IrO2 已有区间原样保存（不改变 xafsmith.json 内容），检查读写与重新载入
    at.sidebar.radio(key="nav_page").set_value("② 质量检查").run()
    cfg_path = Path(os.environ["XAFSMITH_PROJECT"]) / "xafsmith.json"
    before = json.loads(cfg_path.read_text(encoding="utf-8"))
    at.multiselect(key="dg_samples").set_value(["IrO2"]).run()
    txt = at.text_input(key="dg_ranges").value
    at.button(key="dg_save").click().run()
    ok &= check(at, "② 去毛刺 保存")
    after = json.loads(cfg_path.read_text(encoding="utf-8"))
    g = at.session_state["groups"]["IrO2"]
    good = after.get("deglitch") == before.get("deglitch") and         after.get("deglitch_reason") == before.get("deglitch_reason") and         getattr(g, "deglitched", None) == before["deglitch"]["IrO2"]
    print(f"   [{'ok' if good else 'FAIL'}] 去毛刺区间读回：{txt}")
    ok &= good
    # ⑦ FEFF：内置 IrO2
    at.sidebar.radio(key="nav_page").set_value("⑦ FEFF 路径").run()
    [r for r in at.radio if r.label == "结构来源"][0].set_value("内置结构").run()
    sb = [s for s in at.selectbox if s.label == "结构"][0]
    sb.set_value("IrO2").run()
    [b for b in at.button if b.label == "运行 FEFF6L"][0].click().run()
    ok &= check(at, "FEFF 运行")
    # ⑦ FEFF8L（小 RMAX 以缩短时间），输出目录带 _feff8
    [r for r in at.radio if r.label == "FEFF 版本"][0].set_value("FEFF8L").run()
    [n for n in at.number_input if n.label == "RMAX (Å)"][0].set_value(3.6).run()
    [n for n in at.number_input if n.label == "SCF 自洽半径 (Å)"][0].set_value(3.5).run()
    out8 = [t for t in at.text_input if t.label == "输出目录"][0].value
    at.button(key="run_feff").click().run(timeout=900)
    ok &= check(at, "FEFF8L 运行")
    d8 = PROJ / out8
    good = "_feff8" in out8 and (d8 / "feff0001.dat").exists() and xfeff_info(d8)["code"] == "feff8"
    print(f"   [{'ok' if good else 'FAIL'}] FEFF8L 输出 {out8}：feff0001.dat、SCF 费米能 {xfeff_info(d8).get('fermi_ev')}")
    ok &= good
    [r for r in at.radio if r.label == "FEFF 版本"][0].set_value("FEFF6L").run()
    # ⑧ 拟合：默认路径表（前两条 Ir-O）
    at.sidebar.radio(key="nav_page").set_value("⑧ EXAFS 拟合 (Artemis)").run()
    sel = [s for s in at.selectbox if s.label == "数据"][0]
    sel.set_value("IrO2").run()
    nr = [n for n in at.number_input if n.label == "Rmax"][0]
    nr.set_value(2.1).run()
    fd = [m for m in at.multiselect if m.label.startswith("FEFF 目录")][0]
    fd.set_value([o for o in fd.options if "IrO2_IrL3" in str(o)][:1]).run()
    print("   FEFF 目录:", fd.value)
    [b for b in at.button if b.label == "拟合"][0].click().run()
    ok &= check(at, "EXAFS 拟合")
    mets = {m.label: m.value for m in at.metric}
    good = "残差 / 噪声" in mets and "窗口内残差 RMS" in mets
    print(f"   [{'ok' if good else 'FAIL'}] 拟合诊断：残差/噪声 = {mets.get('残差 / 噪声')}")
    ok &= good
    fits = at.session_state["fits"]
    good = bool(fits) and fits[-1]["model"].get("sample") == "IrO2"
    print(f"   [{'ok' if good else 'FAIL'}] 图形界面建的模型记录了样品名（保存后可重跑）")
    ok &= good
    if fits:
        s = fits[-1]["summ"]
        print(f"   拟合: R={s['rfactor']:.4f} nvarys={s['nvarys']} params=",
              {k: round(v['value'], 4) for k, v in s['params'].items()})
    # ⑧ 运行已保存的模型
    n0 = len(at.session_state["fits"])
    at.selectbox(key="saved_model").set_value("IrO2_1shell_ArtemisCompare.json").run()
    at.button(key="run_saved").click().run()
    ok &= check(at, "运行已保存模型")
    s = at.session_state["fits"][-1]["summ"]
    good = len(at.session_state["fits"]) == n0 + 1 and abs(s["params"]["s02"]["value"] - 0.816) < 0.01
    print(f"   [{'ok' if good else 'FAIL'}] 已保存模型 IrO2：S0²={s['params']['s02']['value']:.3f}（期望 ≈0.816）")
    ok &= good
    # ⑧ 同一已保存模型用于多个样品
    n1 = len(at.session_state["fits"])
    at.selectbox(key="saved_model").set_value("TR1_TaO.json").run()
    at.multiselect(key="saved_samples_TR1_TaO.json").set_value(["IrTa-50", "IrTa-100"]).run()
    at.button(key="run_saved").click().run()
    ok &= check(at, "已保存模型用于多个样品")
    new = [f["summ"]["sample"] for f in at.session_state["fits"][n1:]]
    good = new == ["IrTa-50", "IrTa-100"]
    print(f"   [{'ok' if good else 'FAIL'}] 多样品运行：{new}")
    ok &= good
    at.selectbox(key="saved_model").set_value("IrO2_1shell_ArtemisCompare.json").run()
    at.multiselect(key="saved_samples_IrO2_1shell_ArtemisCompare.json").set_value(["IrO2"]).run()
    at.button(key="run_saved").click().run()
    # ⑧ 稳健性检查（对刚运行的已保存模型）
    at.button(key="rb_golast").click().run()
    ok &= check(at, "稳健性检查")
    rb = at.session_state["fits"][-1].get("robust")
    good = rb is not None and len(rb[0]) >= 7 and set(rb[1]["参数"]) == {"s02", "e0", "dr1", "ss1"}
    print(f"   [{'ok' if good else 'FAIL'}] 稳健性：{0 if rb is None else len(rb[0])} 个条件")
    ok &= good
    # ④ 导出 Athena .prj
    at.sidebar.radio(key="nav_page").set_value("④ 归一化 (Athena)").run()
    at.text_input(key="prj_name").set_value("_test_export.prj").run()
    at.button(key="prj_go").click().run()
    ok &= check(at, "导出 .prj")
    prj = Path(os.environ["XAFSMITH_PROJECT"]) / "output" / "gui" / "athena" / "_test_export.prj"
    good = prj.exists()
    if good:
        from larch.io import read_athena
        good = len(read_athena(str(prj), do_preedge=False, do_bkg=False, do_fft=False).groups) >= 1
        prj.unlink()
    print(f"   [{'ok' if good else 'FAIL'}] .prj 可被 larch 读回")
    ok &= good
    # ⑬ XANES 定量：边前峰拟合
    at.sidebar.radio(key="nav_page").set_value("⑬ XANES 定量").run()
    ok &= check(at, "⑬ XANES 定量")
    at.selectbox(key="pe_k").set_value("IrO2").run()
    at.button(key="pe_go").click().run()
    ok &= check(at, "边前峰拟合")
    # ⑭ 期刊出图
    at.sidebar.radio(key="nav_page").set_value("⑭ 期刊出图").run()
    at.text_input(key="pf_name").set_value("_test_fig").run()
    at.button(key="pf_save").click().run()
    ok &= check(at, "期刊出图")
    figd = Path(os.environ["XAFSMITH_PROJECT"]) / "output" / "figs" / "journal"
    made = list(figd.glob("_test_fig.*"))
    good = {p.suffix for p in made} >= {".tiff", ".png", ".svg", ".txt"}
    for p in made:
        p.unlink()
    print(f"   [{'ok' if good else 'FAIL'}] 出图文件：{sorted(p.suffix for p in made)}")
    ok &= good
    # ⑩ LCF
    at.sidebar.radio(key="nav_page").set_value("⑩ LCF").run()
    [s for s in at.selectbox if s.label == "样品"][0].set_value("IrCoOx_OCP").run()
    [m for m in at.multiselect if m.label.startswith("端点标样")][0].set_value(["Ir foil", "IrO2"]).run()
    [b for b in at.button if b.label == "LCF"][0].click().run()
    ok &= check(at, "LCF")
    # ⑫ 汇总报告
    at.sidebar.radio(key="nav_page").set_value("⑫ 汇总报告").run()
    [b for b in at.button if b.label == "生成汇总"][0].click().run()
    ok &= check(at, "汇总报告")
    d = Path(at.session_state["summary_dir"])
    good = (d / "汇总.xlsx").exists() and (d / "汇总报告.html").exists()
    print(f"   [{'ok' if good else 'FAIL'}] 汇总文件：{d.name}")
    ok &= good
    import shutil
    shutil.rmtree(d, ignore_errors=True)            # 测试生成的汇总不留在项目里
    # ⑫ 方法段落
    at.button(key="mt_go").click().run()
    ok &= check(at, "方法段落")
    m = at.session_state["methods"]
    good = "AUTOBK" in m["en"] and "XAFSmith" in m["zh"]
    print(f"   [{'ok' if good else 'FAIL'}] 方法段落：中文 {len(m['zh'])} 字，英文 {len(m['en'].split())} 词")
    ok &= good
    print("全部通过" if ok else "存在失败")
    return 0 if ok else 1


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(main())
