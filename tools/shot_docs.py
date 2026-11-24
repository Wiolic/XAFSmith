"""文档配图脚本（README / QUICKSTART 用），由 shot_gui.py 加载：
    python tools/shot_gui.py docs/images/zh --lang zh --workdir D:/xafsmith_shots --script tools/shot_docs.py
    python tools/shot_gui.py docs/images/en --lang en --workdir D:/xafsmith_shots --script tools/shot_docs.py
--workdir 用一个不含用户名的目录，因为 AI 助手页会显示项目路径；xafsmith 命令路径在下面改成安装版的样子。
只用公开数据（tests/data/demo_project 的 Fe 箔与 Fe 氧化物、Cu 箔）。演示项目没有 FEFF 计算：本脚本在临时副本里用 FEFF6L 现算
bcc Fe 的路径；Cu 用基准测试里的 feffcu01.dat。
注意：联合拟合与趋势图用 Fe 箔与 Fe3C（FEFF 只有 bcc Fe 的第一壳层），seq 是为演示临时加的，只用来演示界面，
不代表任何结构结论；两条同一谱的 Cu 数据做联合会退化，所以没用。
截图需要的操作都在这里用代码完成；要改某张图，改对应函数即可。"""
import shutil
from pathlib import Path

from PySide6.QtWidgets import QApplication, QPushButton  # noqa: F401


def make_feff(proj: Path):
    """演示项目没有 FEFF 计算：Cu 用基准测试的 feffcu01.dat（FEFF 6.10，Cu fcc 第一壳层），Fe 箔 / FeO 用 FEFF6L 现算"""
    from pymatgen.core import Lattice, Structure
    from xafsmith import feff_wrap
    d = proj / "output" / "feff" / "Cu_CuK"
    d.mkdir(parents=True, exist_ok=True)
    shutil.copy(Path(__file__).resolve().parents[1] / "tests" / "data" / "benchmark" / "feffcu01.dat", d / "feff0001.dat")
    fe = Structure.from_spacegroup("Im-3m", Lattice.cubic(2.8665), ["Fe"], [[0, 0, 0]])
    feff_wrap.build(fe, "Fe", "K", proj / "output" / "feff" / "Fe_FeK", rmax=3.2)


def click(page, text):
    for b in page.findChildren(QPushButton):
        if b.text().replace("&&", "&").strip() == text and b.isEnabled():
            b.click()
            return True
    raise RuntimeError(f"找不到按钮：{text}")


def run(ctx):
    w, W = ctx.w, ctx.W
    P, S = w.pages, w.S
    from xafsmith import agent
    agent.command = lambda: "C:\\Program Files\\XAFSmith\\xafsmith-cli.exe"      # AI 助手页显示的命令路径：用安装版的典型路径，不露本机路径
    make_feff(ctx.proj)
    import pandas as pd      # 临时副本的 meta.csv 加 seq 列（Fe 箔 1、Fe3C 2），趋势图横轴才有意义；只改副本
    mf = ctx.proj / "data" / "meta.csv"
    m = pd.read_csv(mf, dtype=str, encoding="utf-8-sig")
    m["seq"] = m["sample"].map({"Fe_foil": "1", "fe3c_rt": "2"}).fillna("")
    m.to_csv(mf, index=False, encoding="utf-8-sig")
    w.open_project(str(ctx.proj))
    ctx.pump(0.5)
    samples = ["Fe_foil", "feo_rt1", "fe2o3_rt1", "fe3c_rt"]
    ctx.load(*samples)

    # —— 归一化：多谱叠加
    ctx.resize(1440, 1100)
    P["norm"].state.update(sel=samples, cur="Fe_foil", flat=True, rel=True, tab=1)
    ctx.go("norm")
    P["norm"].refresh()
    ctx.pump(0.8)
    for pl_ in P["norm"].findChildren(W.Plot):
        if pl_.isVisible():
            pl_.ax.set_xlim(-30, 150)           # 叠加图只看边附近
            pl_.ax.set_ylim(-0.05, 1.6)
            pl_.draw()
    ctx.pump(0.3)
    ctx.shot("normalization")

    # —— χ(k) 与 FT
    P["chi"].state.update(sel=["Fe_foil", "feo_rt1"], re=False)
    ctx.go("chi")
    P["chi"].refresh()
    ctx.pump(0.8)
    ctx.shot("chi_ft")

    # —— 小波
    P["wavelet"].state.update(k="Fe_foil", k2="feo_rt1")
    ctx.go("wavelet")
    P["wavelet"].refresh()
    ctx.pump(0.8)
    ctx.shot("wavelet")

    # —— 吸收边查询
    P["elements"].state["el"] = "Fe"
    ctx.go("elements")
    P["elements"].refresh()
    ctx.pump(0.6)
    ctx.shot("edge_lookup")

    # —— AI 助手、方法导出
    ctx.go("agent")
    ctx.shot("ai_assistant")


    # —— 快速拟合：先用 Cu 箔求 S0²（标样），再把两条 Cu 谱联合拟合（演示数据，见文件头注意）
    from xafsmith import s02_source as s2
    box = P["fit"]
    q = box.quick_page
    ctx.load("cu_metal_rt")
    ctx.go("fit")
    box.show_quick()
    ctx.resize(1440, 1000)
    pick = lambda name: q._feff.setCurrentIndex(next(i for i, d in enumerate(q._feff._vals) if d.name == name))  # noqa: E731
    pick("Cu_CuK")
    q._smp.set_value(["cu_metal_rt"], emit=True)
    q._mode.set("standard", emit=True)
    q._rmax.setValue(3.0)
    q._run.click()
    ctx.wait()
    ctx.scroll_to(q._tab, 160)
    ctx.shot("quick_fit_single")
    q._b_save.click()
    ctx.pump(0.5)

    # 联合：Fe 箔（标样，求 S0²）→ Fe 箔 + Fe3C 联合（演示界面；FEFF 只有 bcc Fe，不代表 Fe3C 的结构结论）
    pick("Fe_FeK")
    q._smp.set_value(["Fe_foil"], emit=True)
    q._mode.set("standard", emit=True)
    q._run.click()
    ctx.wait()
    q._mode.set("sample", emit=True)
    q._smp.set_value(["Fe_foil", "fe3c_rt"], emit=True)
    cands = s2.list_candidates("Fe_K", S.fits, session_edges=q._session_edges())
    q._pick_candidate(cands[0])
    q._rmax.setValue(2.5)
    q._name.setText("QF_Fe_joint")
    q._run.click()
    ctx.wait()
    ctx.scroll_to(q._tab, 160)
    ctx.shot("quick_fit")
    q._b_save.click()
    ctx.pump(0.5)
    jr = q._res["res"]

    # —— 图片导出：趋势图；|χ(R)| 叠加联合拟合
    q._b_fig.click()
    ctx.pump(1.0)
    ctx.resize(1440, 1700)
    ctx.shot("trend")
    pg = P["pubfig"]
    idx = next(i for i, f in enumerate(S.fits) if f is jr.fit)
    pg.state.update(kind="chir", sel=["Fe_foil", "fe3c_rt"], usefit=True, fits=[idx])
    pg.refresh()
    ctx.pump(1.0)
    ctx.shot("journal_figure")

    # —— 在精细拟合中继续：重跑 → 结果与质量检查
    ctx.resize(1440, 1100)
    ctx.go("fit")
    q._b_det.click()
    ctx.wait()
    det = box.detailed_page
    click(det, "拟合")
    ctx.wait()
    ctx.shot("fit_detailed")
    ctx.tab(det, "质量检查")
    ctx.shot("fit_quality")

    # —— Origin 工程：本机有 Origin（originpro）才做；用 Origin 自己渲染三张图拼成一张。没有就保留 docs/images 里的旧图
    make_origin_figure(ctx, pg, idx)

    # —— 方法导出（选到刚才的联合拟合，参数表里有两个样品）
    ctx.resize(1440, 1100)
    ctx.go("methods")
    ctx.shot("methods_export")

    # —— 流程弹窗（放在最后，此时各步已有内容）
    box.show_quick()
    ctx.go("fit")
    ctx.scroll_to(q._smp, 500)
    w.flow_btn.open()
    ctx.pump(0.6)
    ctx.shot("flow")
    w.flow_btn.close_pop()


def make_origin_figure(ctx, pg, idx):
    from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
    from xafsmith import origin_export as oe
    if not oe.originpro_available():
        print("没有 originpro：跳过 origin_export.png")
        return
    from PIL import Image
    keys = ["Fe_foil", "fe3c_rt"]
    pngs = []
    for kind in ("xanes", "chik", "chir"):
        pg.state.update(kind=kind, sel=keys, usefit=kind != "xanes", fits=[idx])
        pg.refresh()
        ctx.pump(1.0)
        fig = pg.findChildren(FigureCanvasQTAgg)[0].figure
        od = ctx.proj / "output" / "figs" / "origin_tmp" / kind
        r = oe.export(fig, od, f"origin_{kind}", kind=kind, png=True)
        got = sorted(Path(r["folder"]).glob("*_origin.png"))
        if not got:
            print("Origin 没有生成 PNG，跳过 origin_export.png")
            return
        pngs.append(got[0])
    ims = [Image.open(p).convert("RGB") for p in pngs]
    h = max(i.height for i in ims)
    sheet = Image.new("RGB", (sum(i.width for i in ims), h), "white")
    x = 0
    for i in ims:
        sheet.paste(i, (x, 0))
        x += i.width
    out = ctx.out / "origin_export.png"
    sheet.save(out)
    from shot_gui import shrink     # noqa: E402  （tools/ 在 sys.path 里）
    shrink(out, 1600)
    print("saved", out)
