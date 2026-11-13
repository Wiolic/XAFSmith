"""由 JSON 说明生成 Origin 工程（.opju）。故意写成独立文件（只需要 originpro 与 pandas），同一份代码可以：
  * 由 XAFSmith 通过外部 Python 的 originpro 调用（本机装有 Origin 2021 及以上）；或
  * 在 Origin 内置 Python 中运行：脚本窗口输入  run -pyf "<导出目录>/build_origin.py"
    （XAFSmith 找不到 originpro 时，只写出数据与这个脚本）。

图层格式参照作者的 Origin 工程（IrCoOx_Ir_XANES.opju）：图层 25 × 19 cm、Arial 32 pt（坐标轴标题、刻度、图例）、
坐标轴 2 pt、四边框（上、右框线无刻度、无数字）、开启抗锯齿、刻度朝外、主刻度间一个次刻度、数据线 3.5 pt（其余 3 pt）、图例无边框。

spec = {"out": ".../xxx.opju", "style": {...}, "graphs": [{
    "book": "fig_xanes", "csv": ".../fig_xanes.csv",
    "columns": [{"name", "long", "units", "axis"}],  # 依次 X1, Y1, X2, Y2 …；趋势图每条曲线 X、Y、E 三列（axis="E" = y 误差）
    "lines": [{"x": 0, "y": 1, "color": "#1E5FBF", "width": 3.5, "dash": 0, "legend": "IrO\\-(2)"}],
               # 趋势图另有 "symbol": true（线 + 符号）与 "yerr": 误差列序号（0 起）
    "xlabel": "...", "ylabel": "...",                 # Origin 富文本（\\+() 上标、\\-() 下标、\\x(hhhh) 字符）
    "xlim": [lo, hi], "ylim": [lo, hi], "xinc": 10, "yinc": 0.5,
    "hide_y": false, "legend_pos": "tl" | "tr", "png": null | ".../xxx.png"}]}
"""
from __future__ import annotations

from xafsmith import logs
import json
import os
import sys


def _lt(op, lay, expr):
    lay.lt_exec(f"double __xs = {expr};")
    return float(op.lt_float("__xs"))


def build(spec, op=None, show=False):
    import pandas as pd
    if op is None:
        import originpro as op
    if getattr(op, "oext", False):
        op.set_show(show)
    op.new()
    st = spec.get("style", {})
    font = st.get("font", "Arial")
    fs = st.get("fsize", 32)
    W, H = st.get("layer_w", 25.0), st.get("layer_h", 19.0)
    left, top = st.get("left", 4.8), st.get("top", 1.25)
    for g in spec["graphs"]:
        df = pd.read_csv(g["csv"])
        wb = op.new_book("w", lname=g["book"])
        wks = wb[0]
        wks.name = g["book"][:31]
        wks.from_df(df)
        for i, c in enumerate(g["columns"]):
            wks.set_label(i, c.get("long", ""), "L")
            if c.get("units"):
                wks.set_label(i, c["units"], "U")
        wks.cols_axis("".join(c.get("axis") or ("X" if c["name"].startswith("X") else "Y") for c in g["columns"]))
        gp = op.new_graph(lname=g["book"], template="line")
        gp.lt_exec("page.aa=1;")                 # 抗锯齿（曲线与文字平滑）
        lay = gp[0]
        entries = []
        for n, ln in enumerate(g["lines"]):
            if ln.get("symbol"):                 # C2 趋势图：线 + 符号，可带 y 误差列
                kw = dict(colyerr=ln["yerr"]) if ln.get("yerr") is not None else {}
                p = lay.add_plot(wks, coly=ln["y"], colx=ln["x"], type="y", **kw)
                p.symbol_size = st.get("symbol_size", 14)
                p.symbol_kind = st.get("symbol_kind", 2)         # 2 = 圆点
                p.symbol_interior = st.get("symbol_interior", 1)  # 1 = 实心
                # 误差棒线宽（st["errbar_w"]）与端帽宽（st["cap_w"]）：LabTalk / originpro 写法未能查证，这里不改格式（未验证）
            else:
                p = lay.add_plot(wks, coly=ln["y"], colx=ln["x"], type="l")
            p.color = ln["color"]
            sname = lay.obj.GetStrProp(p._format_property("name"))
            lay.lt_exec(f"set {sname} -w {int(round(ln.get('width', 3.0) * 500))}; set {sname} -d {int(ln.get('dash', 0))};")
            if ln.get("legend"):
                entries.append(f"\\l({n + 1}) {ln['legend']}")
        # 图层尺寸与位置（cm），页面贴合图层
        lay.lt_exec(f"layer.unit=3; layer.left={left}; layer.top={top}; layer.width={W}; layer.height={H};")
        (x0, x1), (y0, y1) = g["xlim"], g["ylim"]
        lay.lt_exec(f"layer.x.from={x0}; layer.x.to={x1}; layer.y.from={y0}; layer.y.to={y1};")
        if g.get("xinc"):
            lay.lt_exec(f"layer.x.inc={g['xinc']};")
        if g.get("yinc"):
            lay.lt_exec(f"layer.y.inc={g['yinc']};")
        lw_ax = st.get("axis_w", 2)
        tl = st.get("tick_len", 6)
        lay.lt_exec(
            f"layer.x.thickness={lw_ax}; layer.y.thickness={lw_ax}; layer.x2.thickness={lw_ax}; layer.y2.thickness={lw_ax};"
            f"layer.x.ticklength={tl}; layer.y.ticklength={tl}; layer.x2.ticklength={tl}; layer.y2.ticklength={tl};"
            "layer.x.minorTicks=1; layer.y.minorTicks=1;"
            "layer.x.showAxes=3; layer.y.showAxes=3; layer.x.showLabels=1; layer.y.showLabels=1;"
            "layer.x.ticks=10; layer.y.ticks=10; layer.x2.ticks=0; layer.y2.ticks=0;"
            f"layer.x.label.pt={fs}; layer.y.label.pt={fs};"
            f"layer.x.label.font=font({font}); layer.y.label.font=font({font});")
        if g.get("hide_y"):
            lay.lt_exec("layer.y.showLabels=0; layer.y.ticks=0;")
        xl = g.get("xlabel", "").replace('"', "'")
        yl = g.get("ylabel", "").replace('"', "'")
        lay.lt_exec(f'xb.text$="{xl}"; yl.text$="{yl}"; xb.fsize={fs}; yl.fsize={fs};'
                    f"xb.font=font({font}); yl.font=font({font});")
        if entries:
            leg = "%(CRLF)".join(e.replace('"', "'") for e in entries)
            lay.lt_exec(f'legend -r; legend.text$="{leg}"; legend.fsize={fs}; legend.font=font({font}); legend.showframe=0;')
            # legend.x / legend.y 是中心，legend.dx / legend.dy 是宽高（坐标轴单位）
            w_, h_ = abs(_lt(op, lay, "legend.dx")), abs(_lt(op, lay, "legend.dy"))
            mx, my = 0.035 * (x1 - x0), 0.035 * (y1 - y0)
            cx = x0 + mx + w_ / 2 if g.get("legend_pos", "tr") == "tl" else x1 - mx - w_ / 2
            lay.lt_exec(f"legend.x={cx}; legend.y={y1 - my - h_ / 2};")
        # 页面大小：图层四周留出坐标轴标题的位置（与参照工程相同：约 A4 横向宽）
        try:
            res = _lt(op, lay, "page.resx") or 600.0
            pw = (left + W + 1.6) / 2.54 * res
            ph = (top + H + 4.2) / 2.54 * res
            gp.lt_exec(f"page.width={int(pw)}; page.height={int(ph)};")
            lay.lt_exec(f"layer.unit=3; layer.left={left}; layer.top={top}; layer.width={W}; layer.height={H};")
        except Exception:      # noqa: BLE001
            logs.log.warning("origin_builder.build 出错（已忽略或已提示）", exc_info=True)
            pass
        if g.get("png"):
            try:
                gp.save_fig(g["png"], width=1600)
            except Exception:  # noqa: BLE001
                logs.log.warning("origin_builder.build 出错（已忽略或已提示）", exc_info=True)
                pass
    op.save(spec["out"])
    return spec["out"]


if __name__ == "__main__":
    # Origin 内置 Python：run -pyf "path/build_origin.py"（spec.json 在同一文件夹）
    here = os.path.dirname(os.path.abspath(__file__ if "__file__" in globals() else sys.argv[0]))
    with open(os.path.join(here, "spec.json"), encoding="utf-8") as f:
        build(json.load(f))
