"""出图：化学式下标、刻度位置、图内布局（预览不裁切）"""
import matplotlib

matplotlib.use("Agg")

import numpy as np  # noqa: E402
import pytest  # noqa: E402

from xafsmith import pubfig as pf  # noqa: E402


def test_chem_subscripts_formula_words_only():
    assert pf.chem("IrO2") == "IrO$_{2}$"
    assert pf.chem("IrO2 Batch 1") == "IrO$_{2}$ Batch 1"
    assert pf.chem("Ta2O5_1_3V") == "Ta$_{2}$O$_{5}$_1_3V"
    assert pf.chem("Ir foil 1W1B") == "Ir foil 1W1B"
    assert pf.chem("IrTa-100") == "IrTa-100"
    assert pf.chem("IrCoOx_OCP") == "IrCoOx_OCP"
    assert pf.chem("IrO2", on=False) == "IrO2"


def test_ticks_left_bottom_and_labels_inside_figure():
    class G:
        label, element, edge, mode = "IrO2", "Ir", "L3", "trans"
        k = np.linspace(0, 14, 281)
        chi = np.sin(2 * k) * np.exp(-0.05 * k)
    fig, _ = pf.chik([G()], kweight=2)
    ax = fig.axes[0]
    assert ax.xaxis.get_ticks_position() == "bottom" and ax.yaxis.get_ticks_position() == "left"
    fig.canvas.draw()
    r = fig.canvas.get_renderer()
    for a in (ax.xaxis.label, ax.yaxis.label):
        bb = a.get_window_extent(r)
        assert bb.x0 >= -1 and bb.y0 >= -1 and bb.x1 <= fig.bbox.width + 1 and bb.y1 <= fig.bbox.height + 1


# ------------------------------------------------------------------ C2：趋势图
def _trend_table(source="seq", n_err=True):
    import numpy as np
    import pandas as pd
    from xafsmith import trend as tr
    rows = []
    for i, ds in enumerate(("A", "B", "C")):
        for p, (n0, r0) in {"Ir-O": (6.0, 1.98), "Ir-Ir": (4.0, 3.10)}.items():
            rows.append(dict(dataset=ds, sample=f"s{i}", seq=[50.0, 100.0, 300.0][i] if source == "seq" else i + 1.0,
                             seq_source=source, path=p, N=n0 - 0.5 * i, N_err=0.3 if n_err and p == "Ir-O" else np.nan,
                             R=r0 + 0.01 * i, R_err=0.005, sigma2=0.003 + 0.001 * i, sigma2_err=0.0004,
                             dE0=1.0, dE0_err=0.5, E0_edge=11215.0 + i, shared_N=False, shared_R=False,
                             shared_sigma2=(p == "Ir-Ir"), shared_dE0=True))
    df = pd.DataFrame(rows, columns=tr.COLUMNS)
    df.attrs.update(seq_source=source, seq_notes=[], n_composite=[], seq_labels=["A", "B", "C"])
    return df


def test_trend_figure_layout_and_errorbar_style():
    from matplotlib.container import ErrorbarContainer
    from xafsmith import pubfig
    fig, cap = pubfig.trend(_trend_table(), "单栏 85 mm", model="m", edge="Ir L3")
    try:
        axs = [a for a in fig.axes if a.get_visible()]
        assert len(axs) == 4                                    # N、R、σ²、E0（缺省面板）
        assert fig.get_size_inches()[1] == pytest.approx(2.6 * 0.6 * 4)       # 每个面板高 = 0.6×该尺寸 h
        s = pubfig.SIZES["单栏 85 mm"]
        cont = [c for c in axs[0].containers if isinstance(c, ErrorbarContainer)]
        assert len(cont) == 2
        data, caps, bars = cont[0]
        assert data.get_markersize() == pytest.approx(0.5 * s["font"])
        assert data.get_linewidth() == pytest.approx(s["lw"])
        assert all(c.get_markeredgewidth() == pytest.approx(0.7 * s["lw"]) for c in caps)
        assert all(c.get_markersize() == pytest.approx(2 * 0.3 * s["font"]) for c in caps)     # capsize = 0.3·font（pt，单侧）
        assert bars[0].get_linewidths()[0] == pytest.approx(0.7 * s["lw"])
        # 固定 N（Ir-Ir 无 N_err）：没有误差棒线段
        assert cont[1][2] == () or len(cont[1][2]) == 0 or not len(cont[1][2][0].get_segments())
        assert axs[0].get_xlabel() == "" and axs[-1].get_xlabel() == "Sequence"
        assert "1σ" in cap and "N is fixed" in cap and "Ir-Ir" in cap and "model-dependent" in cap
        assert "shared between datasets" in cap and "sigma2 of Ir-Ir" in cap
        assert "E$_0$" in cap and "m" in cap and "Ir L3" in cap
    finally:
        import matplotlib.pyplot as plt
        plt.close(fig)


def test_trend_slide_grid_order_axis_and_custom_label():
    import matplotlib.pyplot as plt
    from xafsmith import pubfig
    t = _trend_table("order")
    fig, cap = pubfig.trend(t, "汇报 16:9", panels=("N", "R", "sigma2", "dE0", "E0"), paths=["Ir-O"], xlabel="Reduced time")
    try:
        assert tuple(fig.get_size_inches()) == pytest.approx((13.333, 7.5))
        assert len(fig.axes) == 6 and sum(a.get_visible() for a in fig.axes) == 5     # 2 列 3 行，空一格
        labels = [x.get_text() for x in fig.axes[4].get_xticklabels()]
        assert labels == ["s0", "s1", "s2"]                        # order：刻度标样品名
        assert "Reduced time" in cap and "dataset order" in cap
    finally:
        plt.close(fig)


def test_trend_no_data_for_e0_panel_and_save(tmp_path):
    from xafsmith import pubfig
    t = _trend_table()
    t["E0_edge"] = float("nan")
    fig, cap = pubfig.trend(t, "单栏 85 mm", panels=("R", "E0"))
    pubfig.save(fig, cap, tmp_path / "t", formats=("png",), dpi=100)
    assert (tmp_path / "t.png").is_file() and (tmp_path / "t.txt").read_text(encoding="utf-8") == cap
    with pytest.raises(ValueError):
        pubfig.trend(t, panels=("nope",))
