"""把“图片导出”中的图写成 Origin 工程（.opju）。

做法同 PeakForge：先写数据（CSV，每条曲线一对 X/Y 列）与说明（spec.json），再用 originpro 生成 .opju；
本机没有 originpro（或没装 Origin）时，只写出数据与 build_origin.py，在 Origin 的脚本窗口运行
    run -pyf "<导出目录>/build_origin.py"
即可得到同样的工程。曲线、颜色、线型、坐标轴范围与标题都取自当前预览的图；字号、线宽、图层尺寸按参照工程统一设置
（见 origin_builder.py 开头）。
"""
from __future__ import annotations

import json
import re
import shutil
from pathlib import Path

import numpy as np
import pandas as pd

STYLE = dict(layer_w=25.0, layer_h=19.0, left=4.8, top=1.25, font="Arial", fsize=32, axis_w=2, tick_len=6,
             lw_main=3.5, lw_other=3.0)

_SUB = str.maketrans("₀₁₂₃₄₅₆₇₈₉₊₋", "0123456789+-")
_SUP = str.maketrans("⁰¹²³⁴⁵⁶⁷⁸⁹⁺⁻", "0123456789+-")


def originpro_available() -> bool:
    try:
        import originpro  # noqa: F401
        return True
    except Exception:       # noqa: BLE001
        return False


def _uni(s):
    """非 ASCII 字符写成 Origin 的 \\x(hhhh)（避免经 COM 传递时的编码问题）"""
    return "".join(c if ord(c) < 128 else f"\\x({ord(c):04X})" for c in s)


def origin_text(s: str) -> str:
    """matplotlib 文本 → Origin 富文本：$^{..}$ → \\+(..)，$_{..}$ → \\-(..)，Unicode 上下标同样处理"""
    s = str(s)

    def math(m):
        t = m.group(1)
        t = re.sub(r"\^\{([^}]*)\}", lambda x: "\\+(" + x.group(1) + ")", t)
        t = re.sub(r"_\{([^}]*)\}", lambda x: "\\-(" + x.group(1) + ")", t)
        t = re.sub(r"\^(\w)", lambda x: "\\+(" + x.group(1) + ")", t)
        t = re.sub(r"_(\w)", lambda x: "\\-(" + x.group(1) + ")", t)
        return t.replace("\\mathrm", "").replace("{", "").replace("}", "")
    s = re.sub(r"\$([^$]*)\$", math, s)
    s = re.sub(r"[₀-₉₊₋]+", lambda m: "\\-(" + m.group(0).translate(_SUB) + ")", s)
    s = re.sub(r"[⁰-⁹⁺⁻¹²³]+", lambda m: "\\+(" + m.group(0).translate(_SUP) + ")", s)
    return _uni(s)


def _hex(c):
    from matplotlib.colors import to_hex
    return to_hex(c).upper()


def _inc(ax, which):
    t = ax.get_xticks() if which == "x" else ax.get_yticks()
    t = np.asarray(t, float)
    if len(t) >= 2:
        return float(np.round(np.median(np.diff(t)), 10))
    return None


def figure_spec(fig, out_dir, name, kind="", png=False):
    """从 matplotlib 图取曲线与坐标轴，写 CSV，返回 builder 用的说明（每个坐标轴一张 Origin 图）"""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    graphs = []
    axes = [a for a in fig.axes if a.get_label() != "<colorbar>"]
    for ai, ax in enumerate(axes):
        lines = [ln for ln in ax.get_lines() if len(np.atleast_1d(ln.get_xdata())) > 2]
        if not lines:
            continue
        book = re.sub(r"[^\w]+", "_", f"{name}_{ai + 1}" if len(axes) > 1 else name)[:28]
        cols, data, spec_lines = [], {}, []
        # XANES：预览图横轴是 E − E0，Origin 工程里一律用能量 E（eV）
        shift = 0.0
        m = re.match(r"^E\s*[−-]\s*([\d.]+)\s*\(eV\)", ax.get_xlabel())
        if kind in ("xanes", "deriv") and m:
            shift = float(m.group(1))
            xlab = "Energy (eV)"
        else:
            xlab = origin_text(ax.get_xlabel())
        for i, ln in enumerate(lines):
            x = np.asarray(ln.get_xdata(), float) + shift
            y = np.asarray(ln.get_ydata(), float)
            lab = ln.get_label()
            legend = "" if lab.startswith("_") else origin_text(lab)
            cx, cy = f"X{i + 1}", f"Y{i + 1}"
            data[cx], data[cy] = pd.Series(x), pd.Series(y)
            cols += [dict(name=cx, long=xlab), dict(name=cy, long=legend or f"line {i + 1}")]
            ls = ln.get_linestyle()
            dash = {"--": 1, ":": 2, "-.": 3}.get(ls, 0)
            main = ls in ("-", "solid") and ln.get_linewidth() >= 0.9 * max(l_.get_linewidth() for l_ in lines)
            spec_lines.append(dict(x=2 * i, y=2 * i + 1, color=_hex(ln.get_color()), dash=dash, legend=legend,
                                   width=STYLE["lw_main"] if main else STYLE["lw_other"]))
        df = pd.DataFrame(data)
        csv = out_dir / f"{book}.csv"
        df.to_csv(csv, index=False, encoding="utf-8")
        hide_y = kind in ("xanes", "deriv") and "offset" in ax.get_ylabel()
        xlim = [float(v) + shift for v in ax.get_xlim()]
        xinc = _inc(ax, "x")
        if shift and xinc:          # 能量轴范围取整到刻度间隔的整数倍
            step = xinc / 2
            xlim = [float(np.floor(xlim[0] / step) * step), float(np.ceil(xlim[1] / step) * step)]
        graphs.append(dict(book=book, csv=str(csv.resolve()), columns=cols, lines=spec_lines,
                           xlabel=xlab, ylabel=origin_text(ax.get_ylabel().replace(" (offset)", "")),
                           xlim=xlim, ylim=[float(v) for v in ax.get_ylim()],
                           xinc=xinc, yinc=_inc(ax, "y"), hide_y=hide_y,
                           legend_pos="tl" if kind in ("xanes", "deriv") else "tr",
                           png=str((out_dir / f"{book}_origin.png").resolve()) if png else None))
    return dict(out=str((out_dir / f"{name}.opju").resolve()), style=STYLE, graphs=graphs)


def write_script(spec, out_dir):
    out_dir = Path(out_dir)
    (out_dir / "spec.json").write_text(json.dumps(spec, ensure_ascii=False, indent=1), encoding="utf-8")
    dst = out_dir / "build_origin.py"
    shutil.copy(Path(__file__).with_name("origin_builder.py"), dst)
    (out_dir / "README_Origin.txt").write_text(
        "在 Origin 中打开脚本窗口（窗口 → 脚本窗口 / Window > Script Window），输入并回车：\n"
        f'    run -pyf "{dst.resolve()}"\n'
        f"生成的工程：{spec['out']}\n\n"
        "Open Origin, then in the Script Window run:\n"
        f'    run -pyf "{dst.resolve()}"\n'
        f"The project is saved to: {spec['out']}\n", encoding="utf-8")
    return dst


def export(fig, out_dir, name, kind="", use_originpro=None, png=False):
    """返回 dict(mode="originpro"|"script", opju, script, folder)"""
    spec = figure_spec(fig, out_dir, name, kind, png)
    if not spec["graphs"]:
        raise ValueError("图中没有可导出的曲线")
    script = write_script(spec, out_dir)
    if use_originpro is None:
        use_originpro = originpro_available()
    if use_originpro:
        import originpro as op
        from . import origin_builder
        try:
            origin_builder.build(spec, op)
        finally:
            try:
                op.exit()
            except Exception:   # noqa: BLE001
                pass
        return dict(mode="originpro", opju=spec["out"], script=str(script), folder=str(Path(out_dir).resolve()))
    return dict(mode="script", opju=None, script=str(script), folder=str(Path(out_dir).resolve()))
