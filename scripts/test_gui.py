"""GUI 自动测试（Streamlit AppTest）：逐页渲染，检查无异常。
运行：.venv\\Scripts\\python scripts\\test_gui.py
"""
import sys
from pathlib import Path

from streamlit.testing.v1 import AppTest

APP = str(Path(__file__).resolve().parent / "gui_app.py")


def check(at, where):
    errs = [e.value for e in at.exception] + [e.value for e in at.error]
    print(f"[{'FAIL' if errs else 'ok'}] {where}" + (f": {errs}" if errs else ""))
    return not errs


def main():
    ok = True
    at = AppTest.from_file(APP, default_timeout=300).run()
    ok &= check(at, "启动")
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
    pages = [r for r in at.sidebar.radio[0].options]
    for p in pages:
        at.sidebar.radio[0].set_value(p).run()
        ok &= check(at, p)
    # ⑦ FEFF：内置 IrO2
    at.sidebar.radio[0].set_value("⑦ FEFF 路径").run()
    sb = [s for s in at.selectbox if s.label == "结构"][0]
    sb.set_value("IrO2").run()
    [b for b in at.button if b.label == "运行 FEFF6L"][0].click().run()
    ok &= check(at, "FEFF 运行")
    # ⑧ 拟合：默认路径表（前两条 Ir-O）
    at.sidebar.radio[0].set_value("⑧ EXAFS 拟合 (Artemis)").run()
    sel = [s for s in at.selectbox if s.label == "数据"][0]
    sel.set_value("IrO2").run()
    nr = [n for n in at.number_input if n.label == "Rmax"][0]
    nr.set_value(2.1).run()
    fd = [m for m in at.multiselect if m.label.startswith("FEFF 目录")][0]
    fd.set_value([o for o in fd.options if "IrO2_IrL3" in str(o)][:1]).run()
    print("   FEFF 目录:", fd.value)
    [b for b in at.button if b.label == "拟合"][0].click().run()
    ok &= check(at, "EXAFS 拟合")
    fits = at.session_state["fits"]
    if fits:
        s = fits[-1]["summ"]
        print(f"   拟合: R={s['rfactor']:.4f} nvarys={s['nvarys']} params=",
              {k: round(v['value'], 4) for k, v in s['params'].items()})
    # ⑩ LCF
    at.sidebar.radio[0].set_value("⑩ LCF").run()
    [s for s in at.selectbox if s.label == "样品"][0].set_value("IrCoOx_OCP").run()
    [m for m in at.multiselect if m.label.startswith("端点标样")][0].set_value(["Ir foil", "IrO2"]).run()
    [b for b in at.button if b.label == "LCF"][0].click().run()
    ok &= check(at, "LCF")
    print("全部通过" if ok else "存在失败")
    return 0 if ok else 1


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(main())
