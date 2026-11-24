"""quickfit_report —— 快速拟合的“汇报包”：一个文件夹，含图、参数表、判定全文、方法段落与单页 HTML 报告。

界面的“导出汇报包”与命令行 `xafsmith quickfit … --report` 共用 `write(res, out_dir)`。
只读拟合结果，不写 models/ 与拟合记录（未保存的拟合也能导出）；图只用 Figure + Agg（可在后台线程里运行）。
Quick-fit report package: one folder with figures, the parameter table, the full verdict text, methods paragraphs and
a one-page HTML report. Shared by the GUI button and `xafsmith quickfit … --report`.
"""

from __future__ import annotations

import html
import re
import tempfile
from datetime import datetime
from pathlib import Path

import pandas as pd

from . import logs, quickfit as qf
from . import report as _report  # noqa: F401  导入即设好中文字体与 Agg 用法

FILES = ("参数表.csv", "判定.txt", "方法.md", "报告.html")     # 固定文件名（图的文件名随样品）
DPI = 300
_SAFE = re.compile(r"[^\w\-.]+")


def _safe(s):
    return _SAFE.sub("_", str(s)).strip("_") or "x"


def default_dir(res, now=None, root=None):
    """output/reports/<模型名>_<YYYYMMDD-HHMM>/；同一分钟已存在则加 -2、-3…（不覆盖）"""
    from . import paths
    now = now or datetime.now()
    base = Path(root or paths.REPORTS) / f"{_safe(res.model['name'])}_{now:%Y%m%d-%H%M}"
    d, i = base, 2
    while d.exists():
        d = base.with_name(f"{base.name}-{i}")
        i += 1
    return d


def _results(res):
    """(样品结果列表, 整批判定或 None)"""
    return (res.samples, res.verdict) if hasattr(res, "samples") else ([res], None)


def count_issues(res):
    """全部需注意（fail）条目数：整批 + 各样品"""
    rs, batch = _results(res)
    return (len(batch.failed) if batch is not None else 0) + sum(len(r.verdict.failed) for r in rs)


def _ex(v, e, f):
    if v is None:
        return "–"
    return f"{v:{f}}" if e is None else f"{v:{f}} ± {e:{f}}"


def table_rows(res, lang="zh"):
    """参数表（与快速拟合页的结果表同列，含 1σ 误差；N、R、σ² 等写成“值 ± 误差”）"""
    zh = lang == "zh"
    rs, _ = _results(res)
    rows = []
    for r in rs:
        row = {("样品" if zh else "Sample"): r.sample, "N": _ex(r.n, r.n_err, ".2f"), "R (Å)": _ex(r.r, r.r_err, ".4f"),
               "σ² (Å²)": _ex(r.sigma2, r.sigma2_err, ".5f")}
        if r.phase2:
            p2 = r.phase2
            row.update({"N₂": _ex(p2["n"], p2["n_err"], ".2f"), "R₂ (Å)": _ex(p2["r"], p2["r_err"], ".4f"),
                        "σ²₂ (Å²)": _ex(p2["sigma2"], p2["sigma2_err"], ".5f"),
                        ("相 2 比例" if zh else "Phase-2 fraction"): f"{p2['frac']:.2f}"})
        row.update({"ΔE0 (eV)": _ex(r.e0, r.e0_err, ".2f"),
                    "S0²": _ex(r.s02, r.s02_err, ".3f") + (("（固定）" if zh else " (fixed)") if r.mode == "sample" else ""),
                    ("R 因子" if zh else "R-factor"): f"{r.rfactor:.4f}", ("判定" if zh else "Verdict"): r.verdict.summary(lang)})
        rows.append(row)
    return pd.DataFrame(rows)


# ---------------------------------------------------------------- 图
def _curves(res, i):
    """第 i 个样品的 (曲线, 单数据集摘要)"""
    from . import fit_exafs as fx
    fit = res.fit
    summ = fit["summ"]
    if summ.get("multi"):
        ds = summ["datasets"][i]["id"]
        return fit["curves"][ds], fx.dataset_view(summ, ds)
    return fit["curves"], summ


def plot_chir(c, summ, title, lang="zh"):
    from matplotlib.figure import Figure
    zh = lang == "zh"
    fig = Figure(figsize=(6.4, 4.2))
    ax = fig.add_subplot(1, 1, 1)
    ax.plot(c["r"], c["chir_mag"], "k", lw=1.3, label="数据" if zh else "data")
    ax.plot(c["rfit"], c["chir_mag_fit"], "r--", lw=1.3, label="拟合" if zh else "fit")
    ax.axvspan(summ["rmin"], summ["rmax"], color="0.9", label="拟合窗口" if zh else "fit window")
    ax.set_xlim(0, max(4.0, summ["rmax"] + 1.5))
    ax.set_xlabel("R (Å) — " + ("未相移校正" if zh else "not phase-corrected"))
    kw = summ["kweight"][-1] if isinstance(summ["kweight"], (list, tuple)) else summ["kweight"]
    ax.set_ylabel(f"|χ(R)|  (k$^{{{kw}}}$)")
    ax.set_title(title, fontsize=10)
    ax.legend(fontsize=8)
    fig.tight_layout()
    return fig


def plot_chik(c, summ, title, lang="zh"):
    from matplotlib.figure import Figure
    zh = lang == "zh"
    fig = Figure(figsize=(6.4, 4.2))
    ax = fig.add_subplot(1, 1, 1)
    ax.plot(c["k"], c["chi"] * c["k"] ** 2, "k", lw=1.3, label="数据" if zh else "data")
    ax.plot(c["kfit"], c["chifit"] * c["kfit"] ** 2, "r--", lw=1.3, label="拟合" if zh else "fit")
    ax.set_xlabel("k (Å$^{-1}$)")
    ax.set_ylabel("k$^{2}$χ(k)")
    ax.set_title(title, fontsize=10)
    ax.legend(fontsize=8)
    fig.tight_layout()
    return fig


_TREND = {"N": ("N", "N_err", "N"), "R": ("R", "R_err", "R (Å)"), "sigma2": ("sigma2", "sigma2_err", "σ² (Å²)")}


def plot_trend(table, key, order=None, lang="zh"):
    """联合拟合的趋势图（一个参数一张；每条路径一条线，1σ 误差棒；横轴与趋势表 / 图片导出同规则）"""
    from matplotlib.figure import Figure
    from . import trend as tr
    tab = tr.ordered(table, order) if order else table
    vcol, ecol, ylab = _TREND[key]
    xc, ticks = tr.axis_of(tab)
    fig = Figure(figsize=(6.4, 4.0))
    ax = fig.add_subplot(1, 1, 1)
    for p in dict.fromkeys(tab["path"]):
        d = tab[tab["path"] == p].sort_values(xc)
        if not d[vcol].notna().any():
            continue
        err = d[ecol].to_numpy(float) if d[ecol].notna().any() else None
        ax.errorbar(d[xc], d[vcol], yerr=err, marker="o", ms=5, lw=1.3, capsize=3, label=p)
    ax.set_ylabel(ylab)
    ax.ticklabel_format(axis="y", useOffset=False)
    ax.set_xlabel(tr.SEQ_LABELS["custom"] if tab.attrs.get("custom_order") else tr.SEQ_LABELS.get(tab.attrs.get("seq_source", "order"), "Sequence"))
    if ticks is not None:
        ax.set_xticks(ticks[0])
        ax.set_xticklabels(ticks[1], rotation=30 if len(ticks[0]) > 3 else 0)
    ax.legend(fontsize=8)
    fig.tight_layout()
    return fig


# ---------------------------------------------------------------- 文本
def verdict_text(res, lang="zh"):
    rs, batch = _results(res)
    if batch is not None:
        return qf.format_joint_text(res, lang)
    return qf.format_text(res, lang)


def methods_md(res, lang="zh"):
    """方法段落（中英文，只含这次的样品与模型）；项目里读不到所需事实时返回说明而不是抛错"""
    from . import fit_exafs as fx, methods_text as mt
    rs, _ = _results(res)
    zh = lang == "zh"
    try:
        with tempfile.TemporaryDirectory() as td:
            csv = Path(td) / "fits.csv"
            fx.write_result_row(res.fit["summ"], csv)
            r = mt.build(sorted({x.sample for x in rs}), fits_csv=csv)
    except Exception as ex:      # noqa: BLE001
        logs.log.warning("quickfit_report: 方法段落生成失败（已写入说明）", exc_info=True)
        msg = f"（方法段落未能生成：{ex}）" if zh else f"(The methods paragraphs could not be generated: {ex})"
        return dict(zh=msg, en=msg)
    return dict(zh=r["zh"], en=r["en"])


_CSS = """body{font-family:'Microsoft YaHei','Segoe UI',Arial,sans-serif;max-width:980px;margin:24px auto;padding:0 16px;color:#1f2933;line-height:1.55}
h1{font-size:22px;margin-bottom:2px}h2{font-size:17px;margin-top:28px;border-bottom:1px solid #d0d7de;padding-bottom:4px}
.meta{color:#667;font-size:13px}.warn{background:#fdecea;border:2px solid #c62828;color:#8e1b1b;padding:10px 14px;border-radius:6px;font-weight:700;margin:14px 0}
.ok{background:#e8f5e9;border:1px solid #2e7d32;color:#1b5e20;padding:8px 14px;border-radius:6px;margin:14px 0}
table{border-collapse:collapse;font-size:13px}td,th{border:1px solid #c9d1d9;padding:4px 8px;text-align:left}th{background:#f3f5f7}
ul.v{list-style:none;padding-left:0}ul.v li{margin:4px 0}.f{color:#c62828;font-weight:700}.p{color:#2e7d32;font-weight:700}.n{color:#667}
.adv{color:#555;margin-left:1.6em}img{max-width:48%;height:auto;border:1px solid #e1e4e8}.figs{display:flex;flex-wrap:wrap;gap:8px}
pre,.methods{background:#f6f8fa;padding:10px 12px;border-radius:6px;white-space:pre-wrap;font-size:13px}"""


def _esc_items(items, lang):
    """条目文字里可能含 < >（如 “≤”以外的比较符）：先转义再拼标记"""
    mark = {"pass": ('p', "✓"), "fail": ('f', "✗"), "note": ('n', "ℹ")}
    order = {"fail": 0, "note": 1, "pass": 2}
    out = []
    for it in sorted(items, key=lambda i: order[i.level]):
        c, m = mark[it.level]
        t = html.escape(html.unescape(it.zh if lang == "zh" else it.en))
        adv = it.advice_zh if lang == "zh" else it.advice_en
        s = f'<li><span class="{c}">{m}</span> {t}'
        if it.level == "fail" and adv:
            s += f'<div class="adv">→ {html.escape(adv)}</div>'
        out.append(s + "</li>")
    return '<ul class="v">' + "".join(out) + "</ul>"


def _html(res, lang, figs, methods, version, when):
    zh = lang == "zh"
    rs, batch = _results(res)
    n = count_issues(res)
    name = res.model["name"]
    head = (f"快速拟合汇报：{name}" if zh else f"Quick-fit report: {name}")
    parts = [f"<!doctype html><html lang='{'zh' if zh else 'en'}'><head><meta charset='utf-8'><title>{html.escape(head)}</title>"
             f"<style>{_CSS}</style></head><body><h1>{html.escape(head)}</h1>",
             f"<div class='meta'>{when:%Y-%m-%d %H:%M} · XAFSmith {html.escape(version)}"
             + (" · " + ("联合拟合" if zh else "joint fit") + f" ({len(rs)})" if batch is not None else "") + "</div>"]
    if n:
        parts.append("<div class='warn'>⚠ " + (f"本次拟合有 {n} 项需注意，不建议直接用于结论。" if zh else
                                             f"This fit has {n} issue(s) to look at; do not use it directly for conclusions.") + "</div>")
    else:
        parts.append("<div class='ok'>✅ " + ("判定：可信（没有需注意的项）。" if zh else "Verdict: trustworthy (no issues).") + "</div>")
    parts.append("<h2>" + ("判定" if zh else "Verdict") + "</h2>")
    if batch is not None:
        parts.append("<h3>" + ("整批" if zh else "Batch") + f" — {html.escape(batch.summary(lang))}</h3>" + _esc_items(batch.items, lang))
    for r in rs:
        parts.append(f"<h3>{html.escape(r.sample)} — {html.escape(r.verdict.summary(lang))}</h3>" + _esc_items(r.verdict.items, lang))
    df = table_rows(res, lang)
    parts.append("<h2>" + ("参数表" if zh else "Parameters") + "</h2>" + df.to_html(index=False, escape=True, border=0))
    w = rs[0].window
    parts.append("<p class='meta'>" + (f"窗口：k {w['kmin']:g}–{w['kmax']:g} Å⁻¹（dk {w['dk']:g}，{w['window']}），k 权重 {w['kweight']}，"
                                       f"R {w['rmin']:.2f}–{w['rmax']:.2f} Å；±为 1σ。" if zh else
                                       f"Window: k {w['kmin']:g}–{w['kmax']:g} Å⁻¹ (dk {w['dk']:g}, {w['window']}), k-weight {w['kweight']}, "
                                       f"R {w['rmin']:.2f}–{w['rmax']:.2f} Å; ± is 1σ.") + "</p>")
    parts.append("<h2>" + ("图" if zh else "Figures") + "</h2><div class='figs'>"
                 + "".join(f"<img src='{html.escape(f)}' alt='{html.escape(f)}'>" for f in figs) + "</div>")
    parts.append("<h2>" + ("方法段落" if zh else "Methods") + "</h2><div class='methods'>" + html.escape(methods["zh" if zh else "en"])
                 + "</div><div class='methods' style='margin-top:8px'>" + html.escape(methods["en" if zh else "zh"]) + "</div>")
    parts.append("<p class='meta'>" + ("以上为 XAFSmith 自动生成的草稿；引用前请核对。" if zh else
                                       "Generated automatically by XAFSmith; check before quoting.") + "</p></body></html>")
    return "".join(parts)


def write(res, out_dir, lang="zh", table=None, now=None):
    """写汇报包到 out_dir（不存在则建；已有同名文件会被覆盖）。res：QuickResult 或 JointResult；
    table：联合拟合的趋势表（缺省现算，失败则略去趋势图）。返回报告.html 的路径。"""
    from . import __version__
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    when = now or datetime.now()
    rs, batch = _results(res)
    figs = []
    for i, r in enumerate(rs):
        c, summ = _curves(res, i)
        for kind, fn in (("chiR", plot_chir), ("chik", plot_chik)):
            f = f"{_safe(r.sample)}_{kind}.png"
            fn(c, summ, r.sample, lang).savefig(out / f, dpi=DPI)
            figs.append(f)
    if batch is not None:
        if table is None:
            try:
                table = res.trend()
            except Exception:      # noqa: BLE001
                logs.log.warning("quickfit_report: 趋势表失败，趋势图略去", exc_info=True)
        if table is not None and len(table):
            for key in _TREND:
                f = f"trend_{key}.png"
                plot_trend(table, key, res.fit.get("trend_order"), lang).savefig(out / f, dpi=DPI)
                figs.append(f)
    df = table_rows(res, lang)
    df.to_csv(out / "参数表.csv", index=False, encoding="utf-8-sig")
    (out / "判定.txt").write_text(verdict_text(res, lang) + "\n", encoding="utf-8")
    m = methods_md(res, lang)
    (out / "方法.md").write_text(("# 方法段落（自动生成草稿，引用前逐句核对）\n\n## 中文\n\n" + m["zh"] + "\n\n## English\n\n" + m["en"] + "\n") if lang == "zh"
                                 else ("# Methods (auto-generated draft; check before quoting)\n\n## English\n\n" + m["en"] + "\n\n## 中文\n\n" + m["zh"] + "\n"),
                                 encoding="utf-8")
    page = out / "报告.html"
    page.write_text(_html(res, lang, figs, m, __version__, when), encoding="utf-8")
    return page
