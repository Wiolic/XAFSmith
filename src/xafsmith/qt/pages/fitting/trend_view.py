"""C2：联合拟合结果的“趋势”标签页——N / R / σ² / ΔE0 / 边位置随序列变量（meta.csv 的 seq、测量时间或数据集顺序）的变化。
画图只用趋势表（xafsmith.trend.trend_table），不重算任何拟合量。"""

from __future__ import annotations

from xafsmith import logs
from xafsmith import trend as tr
from ... import widgets as W
from ...state import safe
from ...theme import C
from ...widgets import T, Banner

PANEL_KEYS = ("N", "R", "sigma2", "dE0", "E0")
DEFAULT_PANELS = ("N", "R", "sigma2", "E0")
_COLS = {"N": ("N", "N_err"), "R": ("R", "R_err"), "sigma2": ("sigma2", "sigma2_err"),
         "dE0": ("dE0", "dE0_err"), "E0": ("E0_edge", None)}
_SHARED = {"N": "shared_N", "R": "shared_R", "sigma2": "shared_sigma2", "dE0": "shared_dE0"}


def panel_name(k):
    return {"N": "N", "R": "R (Å)", "sigma2": "σ² (Å²)", "dE0": "ΔE0 (eV)",
            "E0": T("边位置 E0 (eV)", "Edge position E0 (eV)")}[k]


def trend_colors():
    return [C["accent"], C["err"], C["ok"], C["magenta"], C["gold"], C["text2"]]


def draw_trend(axes, table, panels, paths, xlabel=None, colors=None):
    """在 axes（与 panels 等长）上画趋势：点 + 连线 + 1σ 误差棒；N 固定的路径不画误差棒。"""
    cols = colors or trend_colors()
    src = table.attrs.get("seq_source", "order")
    for ax, pk in zip(axes, panels):
        vcol, ecol = _COLS[pk]
        if pk == "E0":
            d = table.drop_duplicates("dataset").sort_values("seq")
            if d[vcol].notna().any():
                ax.errorbar(d["seq"], d[vcol], color=C["text"], marker="o", ms=5, lw=1.3)
        else:
            for i, p in enumerate(paths):
                d = table[table["path"] == p].sort_values("seq")
                if not d[vcol].notna().any():
                    continue
                err = d[ecol].to_numpy(float) if d[ecol].notna().any() else None
                ax.errorbar(d["seq"], d[vcol], yerr=err, color=cols[i % len(cols)], marker="o", ms=5, lw=1.3,
                            capsize=3, elinewidth=1.0, label=p)
            if len(paths) > 1 and ax is axes[0]:
                ax.legend(fontsize=8)
        ax.set_ylabel(panel_name(pk))
        ax.ticklabel_format(axis="y", useOffset=False)
    last = axes[-1]
    last.set_xlabel(xlabel or tr.SEQ_LABELS[src])
    if src == "order":
        d = table.drop_duplicates("dataset").sort_values("seq")
        last.set_xticks(list(d["seq"]))
        last.set_xticklabels(list(d["sample"]), rotation=30 if len(d) > 3 else 0)


def notes_for(table, panels, paths):
    """提示文字（中英）：序列降级原因、N 固定 / 复合表达式、共享参数。"""
    out = list(table.attrs.get("seq_notes", []))
    if "N" in panels:
        fixed = [p for p in paths if table[table["path"] == p]["N_err"].isna().all()]
        if fixed:
            out.append(T(f"N 固定或无误差：{'、'.join(fixed)}（图上不画误差棒）",
                         f"N is fixed or has no error: {', '.join(fixed)} (no error bars)"))
        comp = [p for p in table.attrs.get("n_composite", []) if p in paths]
        if comp:
            out.append(T(f"N 为复合表达式，未给误差：{'、'.join(comp)}",
                         f"N is a composite expression, no error given: {', '.join(comp)}"))
    shared = [f"{k}/{p}" for k in ("N", "R", "sigma2", "dE0") if k in panels
              for p in paths if table[table["path"] == p][_SHARED[k]].any()]
    if shared:
        out.append(T(f"在数据集之间共享（一个拟合值，水平线不代表“没有变化”）：{'、'.join(shared)}",
                     f"Shared between datasets (one fitted value; a flat line does not mean “no change”): {', '.join(shared)}"))
    return out


def build_trend_tab(page, full):
    """返回“趋势”标签页控件；失败时返回只含提示的页。选择变化后只重建本页内容。"""
    body = W.vbox()
    _fill(page, body, full)
    return body


def _fill(page, body, full):
    lay = body.layout()
    try:
        meta, proc = tr.load_project_tables()
        table = tr.trend_table(full["summ"], full["model"], meta, proc)
    except Exception as ex:      # noqa: BLE001
        logs.log.warning("趋势表失败（已提示）", exc_info=True)
        lay.addWidget(Banner("err", T(f"无法生成趋势表：{ex}", f"Cannot build the trend table: {ex}")))
        return
    all_paths = list(dict.fromkeys(table["path"]))
    st = page.state
    has_e0 = bool(table["E0_edge"].notna().any())
    options = [k for k in PANEL_KEYS if k != "E0" or has_e0]
    panels = [p for p in st.get("trend_panels", DEFAULT_PANELS) if p in options] or [options[0]]
    paths_sel = [p for p in st.get("trend_paths", all_paths) if p in all_paths] or all_paths
    src = table.attrs["seq_source"]
    pm = W.MultiSelect(options, panels, fmt=panel_name)
    pp = W.MultiSelect(all_paths, paths_sel)
    xl = W.text(st.get("trend_xlabel", ""), tr.SEQ_LABELS[src])

    def commit(*_):
        from PySide6.QtCore import QTimer
        st["trend_panels"] = pm.value() or list(DEFAULT_PANELS)
        st["trend_paths"] = pp.value() or all_paths
        st["trend_xlabel"] = xl.text().strip()
        QTimer.singleShot(0, lambda: _refill(page, body, full))
    pm.committed.connect(commit)
    pp.committed.connect(commit)
    xl.editingFinished.connect(commit)
    lay.addWidget(W.hbox(W.label(T("面板", "Panels"), "faint"), pm, W.label(T("路径", "Paths"), "faint"), pp,
                         W.label(T("横轴标题", "X title"), "faint"), xl, spacing=8))
    for n in notes_for(table, panels, paths_sel):
        lay.addWidget(Banner("info", n))
    plot = W.Plot(max(240, 170 * len(panels)), len(panels), 1, sharex=True)
    draw_trend(list(plot.axes), table, panels, paths_sel, xl.text().strip() or None)
    plot.draw()
    lay.addWidget(plot)
    lay.addWidget(W.label(T("1σ 误差棒：协方差矩阵按 √χ²_ν 缩放（Larch）。拟合结果，依赖模型；E0 是实测边位置，不是拟合量。",
                            "1σ error bars: covariance matrix scaled by √χ²_ν (Larch). Fit results, model-dependent; "
                            "E0 is the measured edge position, not a fitted quantity."), "faint"))

    def save():
        base = safe(full["summ"]["model"])
        f = tr.save_trend(table, base, full["summ"]["model"], "GUI trend")
        W.toast(page, T(f"已保存 output/fits/{f.name}", f"Saved output/fits/{f.name}"))
    lay.addWidget(W.hbox(None, W.button(T("保存趋势表", "Save trend table"), icon_name="save", slot=save)))
    lay.addWidget(W.Table(table, max_height=320))


def _refill(page, body, full):
    try:
        W._clear_layout(body.layout())
        _fill(page, body, full)
    except RuntimeError:         # 控件已被销毁（切换了拟合）
        logs.log.debug("trend refill after widget deleted", exc_info=True)
