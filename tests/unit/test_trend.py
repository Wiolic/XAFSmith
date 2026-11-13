"""C2：趋势表（trend.py）——序列变量三种来源与不混用、N_err 四种情况、共享标记、与真实联合拟合摘要一致。"""
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from xafsmith import trend as tr

TESTS = Path(__file__).resolve().parents[1]
CU = TESTS / "data" / "demo_project" / "data" / "raw" / "public" / "cu_metal_rt.xdi"
FEFF = str(TESTS / "data" / "benchmark" / "feffcu01.dat")


def P(value, vary=True, stderr=None, expr=None):
    return dict(value=value, vary=vary, stderr=stderr, expr=expr)


# ------------------------------------------------------------------ 序列变量
DS = [dict(id="a", sample="s1"), dict(id="b", sample="s2"), dict(id="c", sample="s3")]


def _meta(**cols):
    n = len(cols["sample"])
    base = dict(file=[f"f{i}" for i in range(n)])
    base.update(cols)
    return pd.DataFrame(base, dtype=str)


def test_seq_column_used():
    m = _meta(sample=["s1", "s2", "s3"], seq=["50", "100", "300"], time=["2026/1/1 00:00:00"] * 3)
    r = tr.seq_values(DS, m)
    assert r["source"] == "seq" and r["values"] == [50.0, 100.0, 300.0]


def test_seq_missing_one_falls_to_time_not_mixed():
    m = _meta(sample=["s1", "s2", "s3"], seq=["50", "", "300"],
              time=["2026/1/1 02:00:00", "2026/1/1 00:00:00", "2026/1/1 05:30:00"])
    r = tr.seq_values(DS, m)
    assert r["source"] == "time"
    assert r["values"] == pytest.approx([2.0, 0.0, 5.5])
    assert any("b" in n and "seq" in n for n in r["notes"])          # 说明哪个数据集缺 seq


def test_seq_inconsistent_scans_count_as_missing():
    m = _meta(sample=["s1", "s1", "s2", "s3"], seq=["50", "60", "100", "300"],
              time=["2026/1/1 00:00:00", "2026/1/1 01:00:00", "2026/1/1 02:00:00", "2026/1/1 04:00:00"])
    r = tr.seq_values(DS, m)
    assert r["source"] == "time"
    assert any("a" in n and "不一致" in n for n in r["notes"])
    # time：样品取最早一次扫描
    assert r["values"] == pytest.approx([0.0, 2.0, 4.0])


def test_seq_blank_rows_ignored_when_others_agree():
    m = _meta(sample=["s1", "s1", "s2", "s3"], seq=["50", "", "100", "300"])
    assert tr.seq_values(DS, m)["values"] == [50.0, 100.0, 300.0]


def test_order_fallback_and_no_meta():
    r = tr.seq_values(DS, None)
    assert r["source"] == "order" and r["values"] == [1.0, 2.0, 3.0] and r["labels"] == ["a", "b", "c"]
    m = _meta(sample=["s1", "s2", "s3"], time=["2026/1/1 00:00:00", "", "2026/1/2 00:00:00"])
    r = tr.seq_values(DS, m)
    assert r["source"] == "order"
    assert any("没有 seq 列" in n for n in r["notes"]) and any("缺 time" in n for n in r["notes"])


def test_seq_non_numeric_is_missing():
    m = _meta(sample=["s1", "s2", "s3"], seq=["50", "abc", "300"])
    r = tr.seq_values(DS, m)
    assert r["source"] == "order"


# ------------------------------------------------------------------ N_err
ROW = dict(path="p", amp_err=0.06)


def test_n_err_fixed_cases():
    for spec in ({}, {"N": None}, {"N": ""}, {"N": "6"}, {"N": 6}, {"N": 4.5}):
        assert tr.n_err(spec, ROW, {"s02": P(0.9, False)}) == (None, False)


def test_n_err_single_param_name():
    params = {"s02": P(0.9, False), "N1": P(5.0, True, 0.3)}
    assert tr.n_err({"N": "N1"}, ROW, params) == (0.3, False)
    # 参数未估计出误差（固定或失败）→ 空，不算复合
    assert tr.n_err({"N": "N1"}, ROW, {"N1": P(5.0, False)}) == (None, False)
    # s02 参考值也在变，N 本身就是该参数：仍取该参数的 stderr
    assert tr.n_err({"N": "s02", "s02": "s02"}, ROW, {"s02": P(0.9, True, 0.05)}) == (0.05, False)


def test_n_err_expression_with_fixed_s02_ref():
    params = {"s02": P(0.8, False), "N1": P(5.0, True, 0.3)}
    e, comp = tr.n_err({"N": "N1*2"}, dict(amp_err=0.48), params)
    assert comp is False and e == pytest.approx(0.48 / 0.8)
    # 路径的 s02 字段是别的固定参数：以它为参考
    params["amp"] = P(0.5, False)
    e, comp = tr.n_err({"N": "N1*2", "s02": "amp"}, dict(amp_err=0.2), params)
    assert e == pytest.approx(0.4)
    # 没有任何 S0² 参数：参考 = 1.0（固定）
    assert tr.n_err({"N": "N1*2"}, dict(amp_err=0.2), {"N1": P(5.0, True, 0.1)})[0] == pytest.approx(0.2)


def test_n_err_expression_with_varying_s02_ref_is_blank():
    params = {"s02": P(0.8, True, 0.05), "N1": P(5.0, True, 0.3)}
    assert tr.n_err({"N": "N1*2"}, ROW, params) == (None, True)
    # s02 参数是表达式（依赖变量）也不算固定
    params = {"s02": P(0.8, False, 0.05, "a*b"), "N1": P(5.0, True, 0.3)}
    assert tr.n_err({"N": "N1*2"}, ROW, params) == (None, True)
    # 振幅误差没有 → 空，但仍提示复合
    assert tr.n_err({"N": "N1*2"}, dict(amp_err=None), {"s02": P(0.8, False)}) == (None, True)


# ------------------------------------------------------------------ 真实联合拟合
def _model(n_a="N1", n_b="N1", ss_a="ssA", ss_b="ssB", temp_a=None, temp_b=None):
    def path(n, ss):
        d = dict(file=FEFF, label="Cu-Cu", s02="amp", e0="del_e0", deltar="del_r", sigma2=ss)
        if n is not None:
            d["N"] = n
        return d
    da = dict(id="A", sample="cu_metal_rt", paths=[path(n_a, ss_a)])
    db = dict(id="B", sample="cu_metal_rt", kmax=14, paths=[path(n_b, ss_b)])
    return {"name": "cu_twin", "kmin": 3, "kmax": 17, "dk": 4, "window": "kaiser", "kweight": 2,
            "rmin": 1.4, "rmax": 3.0, "fitspace": "r",
            "params": {"amp": {"value": 1.0, "vary": False}, "del_e0": 0.0, "del_r": 0.0,
                       "N1": {"value": 12.0, "vary": True}, "ssA": 0.005, "ssB": 0.005},
            "datasets": [da, db]}


@pytest.fixture(scope="module")
def fitted():
    from larch import Group
    from larch.xafs import autobk
    from xafsmith import fit_exafs as fx
    from xafsmith.readers import read_scan
    g0 = read_scan(CU)
    g = Group(energy=g0.energy, mu=g0.mu)
    autobk(g.energy, g.mu, group=g, rbkg=1.0, kw=2)
    m = _model()
    _, _, summ = fx.fit_multi({"A": g, "B": g}, m)
    return m, summ


def test_trend_table_matches_summary(fitted):
    m, summ = fitted
    meta = _meta(sample=["cu_metal_rt"], seq=["7"])
    proc = pd.DataFrame(dict(sample=["cu_metal_rt", "other"], E0=[8979.0, 1.0]))
    t = tr.trend_table(summ, m, meta, proc)
    assert list(t.columns) == tr.COLUMNS and len(t) == 2
    assert list(t["dataset"]) == ["A", "B"]
    for (_, row), pr in zip(t.iterrows(), summ["paths"]):
        assert row["N"] == pr["N"] and row["R"] == pr["R"] and row["sigma2"] == pr["sigma2"]
        assert row["R_err"] == pr["R_err"] and row["sigma2_err"] == pr["sigma2_err"]
        assert row["dE0"] == pr["e0"] and row["dE0_err"] == pr["e0_err"]
        assert row["E0_edge"] == 8979.0
    assert set(t["seq_source"]) == {"seq"} and set(t["seq"]) == {7.0}
    # N 是单个参数名 → N_err = 该参数 stderr；N、ΔR、ΔE0 在两数据集里写法相同 → 共享；σ² 名字不同 → 不共享
    assert t["N_err"].iloc[0] == summ["params"]["N1"]["stderr"] and t["N_err"].iloc[0] > 0
    assert bool(t["shared_N"].all()) and bool(t["shared_R"].all()) and bool(t["shared_dE0"].all())
    assert not t["shared_sigma2"].any()


def test_trend_table_without_meta_or_processed(fitted):
    m, summ = fitted
    t = tr.trend_table(summ, m)
    assert set(t["seq_source"]) == {"order"} and list(t["seq"]) == [1.0, 2.0]
    assert t["E0_edge"].isna().all()
    assert t.attrs["seq_labels"] == ["A", "B"]


def test_trend_table_composite_n_expression(fitted):
    from larch import Group
    from larch.xafs import autobk
    from xafsmith import fit_exafs as fx
    from xafsmith.readers import read_scan
    g0 = read_scan(CU)
    g = Group(energy=g0.energy, mu=g0.mu)
    autobk(g.energy, g.mu, group=g, rbkg=1.0, kw=2)
    m = _model(n_a="N1*1", n_b="N1*1")
    _, _, summ = fx.fit_multi({"A": g, "B": g}, m)
    t = tr.trend_table(summ, m)
    # s02 参考（amp）固定 → N_err = amp_err / amp，非空；摘要里 amp_err 来自路径 s02 的 stderr
    assert t["N_err"].notna().all()
    assert t["N_err"].iloc[0] == pytest.approx(summ["paths"][0]["amp_err"] / 1.0)
    # 放开 amp：N 的参考 S0² 在变 → 留空并提示
    m2 = _model(n_a="N1*1", n_b="N1*1")
    m2["params"]["amp"] = {"value": 1.0, "vary": True}
    m2["params"]["N1"] = {"value": 12.0, "vary": False}
    _, _, summ2 = fx.fit_multi({"A": g, "B": g}, m2)
    t2 = tr.trend_table(summ2, m2)
    assert t2["N_err"].isna().all() and t2.attrs["n_composite"] == ["Cu-Cu"]


def test_trend_table_fixed_n(fitted):
    m, summ = fitted
    m3 = _model(n_a="12", n_b=None)
    # 构造摘要即可：把 N 字段换成固定数，N_err 空
    t = tr.trend_table(summ, m3)
    assert t["N_err"].isna().all()


def test_trend_table_single_dataset_raises(fitted):
    m, summ = fitted
    with pytest.raises(ValueError):
        tr.trend_table(dict(summ, multi=False), m)


def test_summary_old_keys_unchanged(fitted):
    """C2 只给多数据集路径行加了 amp_err；其余键与 v1.3 前相同。"""
    _, summ = fitted
    keys = set(summ["paths"][0])
    assert keys == {"path", "reff", "degen", "N", "amp", "R", "R_err", "sigma2", "sigma2_err", "e0", "e0_err",
                    "deltar", "dataset", "amp_err"}
    assert np.isfinite(summ["paths"][0]["N"])


# ------------------------------------------------------------------ 共享标记
def test_shared_flags_tempk_with_different_temperatures():
    nm_model = _model(ss_a="ss0+tempK*0", ss_b="ss0+tempK*0")
    nm_model["datasets"][0]["temperature"] = 10
    nm_model["datasets"][1]["temperature"] = 300
    from xafsmith.fit_exafs import normalize_model
    fl = tr._shared_flags(normalize_model(nm_model))
    assert fl["Cu-Cu"]["shared_sigma2"] is False and fl["Cu-Cu"]["shared_R"] is True
    nm_model["datasets"][1]["temperature"] = 10
    assert tr._shared_flags(normalize_model(nm_model))["Cu-Cu"]["shared_sigma2"] is True
