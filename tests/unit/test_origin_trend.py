"""C2：Origin 导出的误差棒图（脚本模式：spec / CSV；builder 用假的 originpro 对象检查调用）。
本机没有 Origin，工程观感与误差棒线宽、端帽宽的 Origin 设置未验证。"""
from unittest.mock import MagicMock

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
import pytest  # noqa: E402

from xafsmith import origin_export as oe  # noqa: E402
from xafsmith import pubfig  # noqa: E402
from test_pubfig import _trend_table  # noqa: E402


def _spec(tmp_path, **kw):
    fig, _ = pubfig.trend(_trend_table(), "单栏 85 mm", **kw)
    try:
        return oe.figure_spec(fig, tmp_path, "tr", kind="trend")
    finally:
        plt.close(fig)


def test_trend_spec_has_yerr_columns_and_no_cap_curves(tmp_path):
    sp = _spec(tmp_path)
    assert len(sp["graphs"]) == 4                        # N、R、σ²、E0 各一张图
    g = sp["graphs"][0]                                   # N：Ir-O 有误差棒，Ir-Ir（N 固定）没有
    assert len(g["lines"]) == 2                           # 端帽线（markers '_'）不是曲线
    assert [c["name"] for c in g["columns"]] == ["X1", "Y1", "E1", "X2", "Y2"]
    a, b = g["lines"]
    assert (a["x"], a["y"], a["yerr"], a["symbol"]) == (0, 1, 2, True)
    assert (b["x"], b["y"], b["symbol"]) == (3, 4, True) and "yerr" not in b
    df = pd.read_csv(g["csv"])
    assert list(df.columns) == ["X1", "Y1", "E1", "X2", "Y2"]
    assert df["E1"].tolist() == pytest.approx([0.3, 0.3, 0.3])      # 由竖线段还原的 yerr = 输入的 N_err
    assert df["Y1"].tolist() == pytest.approx([6.0, 5.5, 5.0])
    assert [c.get("axis") for c in g["columns"]] == [None, None, "E", None, None]
    assert sp["style"]["symbol_size"] == 14 and sp["style"]["errbar_w"] == 2 and sp["style"]["cap_w"] == 16
    assert sp["style"]["lw_main"] == 3.5
    g2 = sp["graphs"][1]                                  # R：两条线都有 σ_R
    assert [c["name"] for c in g2["columns"]] == ["X1", "Y1", "E1", "X2", "Y2", "E2"]
    assert pd.read_csv(g2["csv"])["E1"].tolist() == pytest.approx([0.005] * 3)
    g4 = sp["graphs"][3]                                  # E0：无误差棒，点 + 线
    assert [c["name"] for c in g4["columns"]] == ["X1", "Y1"] and g4["lines"][0]["symbol"] is True


def test_two_point_series_kept(tmp_path):
    t = _trend_table()
    t = t[t["dataset"].isin(["A", "B"])]
    fig, _ = pubfig.trend(t, "单栏 85 mm", panels=("R",))
    sp = oe.figure_spec(fig, tmp_path, "t2", kind="trend")
    plt.close(fig)
    assert len(sp["graphs"][0]["lines"]) == 2


def test_plain_line_figure_spec_unchanged(tmp_path):
    fig, ax = plt.subplots()
    x = np.linspace(0, 5, 30)
    ax.plot(x, x, label="a")
    ax.plot(x, x ** 2, "--", label="b")
    sp = oe.figure_spec(fig, tmp_path, "plain")
    plt.close(fig)
    g = sp["graphs"][0]
    assert [c["name"] for c in g["columns"]] == ["X1", "Y1", "X2", "Y2"]
    assert [(ln["x"], ln["y"]) for ln in g["lines"]] == [(0, 1), (2, 3)]
    assert all("symbol" not in ln and "yerr" not in ln for ln in g["lines"])


def test_builder_uses_symbol_plot_with_error_column(tmp_path):
    from xafsmith import origin_builder as ob
    sp = _spec(tmp_path)
    sp["out"] = str(tmp_path / "x.opju")
    op = MagicMock()
    ob.build(sp, op)
    calls = []
    for c in op.new_book.return_value.__getitem__.return_value.cols_axis.call_args_list:
        calls.append(c.args[0])
    assert calls[0] == "XYEXY" and calls[1] == "XYEXYE"
    lay = op.new_graph.return_value.__getitem__.return_value
    kws = [c for c in lay.add_plot.call_args_list]
    assert kws[0].kwargs == dict(coly=1, colx=0, type="y", colyerr=2)
    assert kws[1].kwargs == dict(coly=4, colx=3, type="y")
