"""文档配图脚本（README / QUICKSTART 用），由 shot_gui.py 加载：
    python tools/shot_gui.py docs/images/zh --lang zh --workdir D:/xafsmith_shots --script tools/shot_docs.py
    python tools/shot_gui.py docs/images/en --lang en --workdir D:/xafsmith_shots --script tools/shot_docs.py
--workdir 用一个不含用户名的目录，因为 AI 助手页会显示项目路径；xafsmith 命令路径在下面改成安装版的样子。
只用标样（Ir 箔、IrO2、KTaO3、Ta2O5、Ta 箔），从用户的完整项目复制出最小副本（见 make_project）：
    --project <完整项目目录>
联合拟合与趋势图用同一种标样的不同批次谱（样品用途，S0² 取标样拟合值）。
截图需要的操作都在这里用代码完成；要改某张图，改对应函数即可。"""
import shutil
from pathlib import Path

from PySide6.QtWidgets import QPushButton


# 只用标样（Ir 箔、IrO2；KTaO3、Ta2O5 与 Ta 箔）：项目里没有的样品一律不复制，未发表样品的名字不会出现在截图里
KEEP = ["Ir foil", "IrO2", "Ir_foil_1W1B", "IrO2_Batch1", "Ir_foil_2132",
        "Ta_foil", "KTaO3_20261105_Ta", "Ta2O5_20261105_Ta",
        "Ta_foil_Ta_Time_resolved", "KTaO3_Ta_Time_resolved", "Ta2O5_Ta_Time_resolved",
        "Ta_foil_IrTa_series", "KTaO3_IrTa_series", "Ta2O5_IrTa_series"]
FEFF = ["IrO2_IrL3", "Ir_IrL3", "KTaO3_TaL3", "Ta_TaL3"]


def make_project(src: Path, dst: Path):
    """从完整项目 src 复制出只含标样的最小项目到 dst：meta.csv 只留 KEEP 行，原始数据只复制这些行用到的文件，
    处理参数里只留这些样品的例外，FEFF 只复制 FEFF 列表里的目录；其他（模型、笔记、拟合记录、已有输出）都不复制。"""
    import json
    import pandas as pd
    dst.mkdir(parents=True)
    m = pd.read_csv(src / "data" / "meta.csv", dtype=str, encoding="utf-8-sig")
    m = m[m["sample"].isin(KEEP)].copy()
    # 趋势图横轴：两个 IrO2 按测量时间先后记 seq = 1（2026-05）、2（2026-11）。没有 seq 时趋势图会显示一条“缺 seq”的提示，
    # 英文界面里这条提示是中文（trend.py 的 bug），所以截图里给 seq，避免英文图里出现中文。
    m["seq"] = m["sample"].map({"IrO2": "1", "IrO2_Batch1": "2"}).fillna("")
    (dst / "data").mkdir()
    m.to_csv(dst / "data" / "meta.csv", index=False, encoding="utf-8-sig")
    for col in ("file", "ref_file"):
        for rel in m[col].dropna().unique():
            sp, dp = src / rel, dst / rel
            if dp.exists():          # file 与 ref_file 可能是同一个（原始数据只读，不能覆盖）
                continue
            dp.parent.mkdir(parents=True, exist_ok=True)
            if sp.is_dir():
                shutil.copytree(sp, dp, dirs_exist_ok=True)
            elif sp.exists():
                shutil.copy2(sp, dp)
    cfg = json.loads((src / "xafsmith.json").read_text(encoding="utf-8"))
    cfg["edges"] = {k: v for k, v in cfg["edges"].items() if k in ("Ir_L3", "Ta_L3")}
    for k in ("overrides", "overrides_reason", "deglitch", "deglitch_reason"):
        if isinstance(cfg.get(k), dict):
            cfg[k] = {s_: v for s_, v in cfg[k].items() if s_ in KEEP}
    (dst / "xafsmith.json").write_text(json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8")
    for d in FEFF:
        shutil.copytree(src / "output" / "feff" / d, dst / "output" / "feff" / d)


def click(page, text):
    for b in page.findChildren(QPushButton):
        if b.text().replace("&&", "&").strip() == text and b.isEnabled():
            b.click()
            return True
    raise RuntimeError(f"找不到按钮：{text}")


NORM = ["Ir_foil_1W1B", "IrO2_Batch1", "IrO2", "Ir foil"]
STD = "IrO2_Batch1"                  # 快速拟合：标样用途
JOINT = ["IrO2_Batch1", "IrO2"]      # 联合拟合：同一种标样的两个批次（样品用途）
FEFF_NAME = "IrO2_IrL3"


def run(ctx):
    w, W = ctx.w, ctx.W
    P, S = w.pages, w.S
    from xafsmith import agent
    agent.command = lambda: "C:/Program Files/XAFSmith/xafsmith-cli.exe"      # AI 助手页显示的命令路径：用安装版的典型路径，不露本机路径
    w.open_project(str(ctx.proj))
    ctx.pump(0.5)
    ctx.load(*NORM)

    # —— 归一化：多谱叠加
    ctx.resize(1440, 1100)
    P["norm"].state.update(sel=NORM, cur=NORM[0], flat=True, rel=True, tab=1)
    ctx.go("norm")
    P["norm"].refresh()
    ctx.pump(0.8)
    for pl_ in P["norm"].findChildren(W.Plot):
        if pl_.isVisible():
            pl_.ax.set_xlim(-30, 150)           # 叠加图只看边附近
            pl_.draw()
    ctx.pump(0.3)
    ctx.shot("normalization")

    # —— χ(k) 与 FT
    P["chi"].state.update(sel=NORM[:2], re=False)
    ctx.go("chi")
    P["chi"].refresh()
    ctx.pump(0.8)
    ctx.shot("chi_ft")

    # —— 小波
    P["wavelet"].state.update(k=NORM[0], k2=NORM[1])
    ctx.go("wavelet")
    P["wavelet"].refresh()
    ctx.pump(0.8)
    ctx.shot("wavelet")

    # —— 吸收边查询
    P["elements"].state["el"] = "Ir"
    ctx.go("elements")
    P["elements"].refresh()
    ctx.pump(0.6)
    ctx.shot("edge_lookup")

    # —— AI 助手
    ctx.go("agent")
    ctx.shot("ai_assistant")

    # —— 快速拟合：单样品（标样用途，S0² 为拟合量）→ 联合（样品用途，S0² 取标样值）
    from xafsmith import s02_source as s2
    box = P["fit"]
    q = box.quick_page
    ctx.go("fit")
    box.show_quick()
    ctx.resize(1440, 1000)
    q._feff.setCurrentIndex(next(i for i, d in enumerate(q._feff._vals) if FEFF_NAME in str(d)))
    q._smp.set_value([STD], emit=True)
    q._mode.set("standard", emit=True)
    q._run.click()
    ctx.wait()
    ctx.scroll_to(q._tab, 160)
    ctx.shot("quick_fit_single")
    q._b_save.click()
    ctx.pump(0.5)

    q._mode.set("sample", emit=True)
    q._smp.set_value(JOINT, emit=True)
    cands = s2.list_candidates("Ir_L3", S.fits, session_edges=q._session_edges())
    q._pick_candidate(cands[0])
    q._name.setText("QF_IrO2_joint")
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
    pg.state.update(kind="chir", sel=JOINT, usefit=True, fits=[idx])
    pg.refresh()
    ctx.pump(1.0)
    ctx.shot("journal_figure")

    # —— 在精细拟合中继续：重跑 → 结果与质量检查
    ctx.resize(1440, 1100)
    ctx.go("fit")
    q._b_det.click()
    ctx.wait()
    det = box.detailed_page
    click(det, "Fit" if ctx.lang == "en" else "拟合")
    ctx.wait()
    ctx.shot("fit_detailed")
    ctx.tab(det, "Quality" if ctx.lang == "en" else "质量检查")
    ctx.shot("fit_quality")

    # —— Origin 工程：本机有 Origin（originpro）才做；用 Origin 自己渲染三张图拼成一张。没有就保留 docs/images 里的旧图
    make_origin_figure(ctx, pg, idx)

    # —— 方法导出
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
    keys = JOINT
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
