"""B6 σ² 的 Debye / Einstein 模型：摘要与 CSV 字段（④）、合成多温度联合拟合（⑤）。

  ④ 用了 σ² 模型或写了 temperature → 摘要路径行 / 数据集行 / CSV 多字段；都不用 → 一个键都不多；
     Einstein 用在 nleg > 2 的路径上给警告。
  ⑤ 合成多温度基准（Cu 路径，T = 10/100/200/300 K，σ² = 模型(θ_true) + 0.001，固定种子噪声）：
     联合拟合 θ、ss0 与真值之差 < 3×stderr（Debye、Einstein 各一组）；
     单一温度重参数化一致性（σ² 自由 vs σ²=模型(T, θ)）：χ² 相对差 < 1e-6，θ 相对差 < 1e-4。
运行：python -m pytest tests/benchmark/test_sigma2_models.py -q
"""
import pytest
from _sigma2_synth import FEFF, SS0_TRUE, THETA_TRUE, joint_model, synth_groups

from xafsmith import fit_exafs as fx


@pytest.fixture(scope="module", params=["debye", "einstein"])
def joint(request):
    kind = request.param
    groups = synth_groups(kind)
    model = joint_model(kind)
    res, ds, summ = fx.fit_multi(groups, model, root=".")
    return kind, model, res, summ


# ------------------------------------------------------------------ ④ 摘要与 CSV 字段
def test_summary_fields_multi(joint):
    kind, model, res, summ = joint
    for p in summ["paths"]:
        assert p["sigma2_model"] == kind and p["theta_param"] == "thD"
    assert [p["temperature"] for p in summ["paths"]] == [10.0, 100.0, 200.0, 300.0]
    assert [d["temperature"] for d in summ["datasets"]] == [10.0, 100.0, 200.0, 300.0]


def test_csv_columns(joint, tmp_path):
    kind, model, res, summ = joint
    df = fx.write_result_row(summ, tmp_path / "f.csv")
    assert list(df["temperature"]) == [10.0, 100.0, 200.0, 300.0]
    assert set(df["sigma2_model"]) == {kind}


def test_plain_model_gets_no_new_keys():
    """不用温度、不用 σ² 模型 → 摘要、CSV 一个键 / 一列都不多（与 B6 之前相同）。"""
    groups = synth_groups("debye", temps=(100, 200))
    m = joint_model("debye", temps=(100, 200))
    for d in m["datasets"]:
        d.pop("temperature")
        d["paths"][0]["sigma2"] = "ss0"
    m["params"].pop("thD")
    res, ds, summ = fx.fit_multi(groups, m, root=".")
    assert all(not ({"temperature", "sigma2_model", "theta_param"} & set(p)) for p in summ["paths"])
    assert all("temperature" not in d for d in summ["datasets"])
    import pandas as pd
    import tempfile
    from pathlib import Path
    with tempfile.TemporaryDirectory() as td:
        df = fx.write_result_row(summ, Path(td) / "f.csv")
        assert isinstance(df, pd.DataFrame) and not ({"temperature", "sigma2_model"} & set(df.columns))


def test_summary_single_dataset_old_format():
    groups = synth_groups("debye", temps=(100,))
    m = joint_model("debye", temps=(100,), static=False)
    d = m.pop("datasets")[0]
    m.update(sample="T100", temperature=100, paths=d["paths"])
    res, ds, summ = fx.run_fit(groups["T100"], m, root=".")
    (p,) = summ["paths"]
    assert (p["temperature"], p["sigma2_model"], p["theta_param"]) == (100.0, "debye", "thD")
    m2 = dict(m, temperature=None)                        # 只有 temperature 没有模型也加字段
    m2["paths"] = [dict(d["paths"][0], sigma2="0.003")]
    m2["temperature"] = 100
    m2["params"] = {"amp": 0.9, "e0": 0.0, "dr": 0.0}
    _, _, s2 = fx.run_fit(groups["T100"], m2, root=".")
    assert s2["paths"][0]["temperature"] == 100.0 and s2["paths"][0]["sigma2_model"] is None


def test_einstein_multiple_scattering_warning():
    warn = []
    prows = [dict(), dict()]
    fx._add_sigma2_fields(prows, [("einstein", "thE"), ("debye", "thD")], [300.0, 300.0], warn,
                          [("MS3", 3), ("MS3d", 3)])
    assert len(warn) == 1 and "MS3" in warn[0] and "Debye" in warn[0]
    warn.clear()
    fx._add_sigma2_fields([dict()], [("einstein", "thE")], [300.0], warn, [("SS", 2)])
    assert warn == []


# ------------------------------------------------------------------ ⑤ 合成多温度基准
def test_joint_fit_recovers_theta_and_ss0(joint):
    kind, model, res, summ = joint
    th, ss = summ["params"]["thD"], summ["params"]["ss0"]
    assert th["stderr"] and ss["stderr"]
    assert abs(th["value"] - THETA_TRUE[kind]) < 3 * th["stderr"], (kind, th)
    assert abs(ss["value"] - SS0_TRUE) < 3 * ss["stderr"], (kind, ss)
    print(f"[B6 {kind}] thD = {th['value']:.3f} +/- {th['stderr']:.3f} (true {THETA_TRUE[kind]}), "
          f"ss0 = {ss['value']:.6f} +/- {ss['stderr']:.6f} (true {SS0_TRUE})")


@pytest.mark.parametrize("kind", ["debye", "einstein"])
def test_single_temperature_is_pure_reparametrisation(kind):
    """单一温度：σ² 自由 与 σ² = 模型(T, θ)（无静态项）拟合同一数据，χ² 相同，θ 与 θ_from_sigma2(σ²) 相同。"""
    from xafsmith.sigma2 import theta_from_sigma2
    T = 150
    groups = synth_groups(kind, temps=(T,), ss0=0.0)
    base = joint_model(kind, temps=(T,), static=False)
    ds = base.pop("datasets")[0]
    common = dict(base, sample=ds["sample"])
    free = dict(common, params={"amp": 0.9, "e0": 0.0, "dr": 0.0, "ssA": {"value": 0.004}},
                paths=[dict(ds["paths"][0], sigma2="ssA")])
    mod = dict(common, temperature=T, paths=[dict(ds["paths"][0])])
    ra, _, sa = fx.run_fit(groups[f"T{T}"], free, root=".")
    rb, _, sb = fx.run_fit(groups[f"T{T}"], mod, root=".")
    assert abs(sa["chi2"] - sb["chi2"]) / sa["chi2"] < 1e-6
    ssa = sa["paths"][0]["sigma2"]
    th_a = theta_from_sigma2(FEFF, kind, T, ssa)
    th_b = sb["params"]["thD"]["value"]
    assert abs(th_a - th_b) / th_b < 1e-4, (th_a, th_b)
    print(f"[B6 {kind} single T] chi2 rel diff = {abs(sa['chi2'] - sb['chi2']) / sa['chi2']:.2e}, "
          f"theta rel diff = {abs(th_a - th_b) / th_b:.2e}")


# ------------------------------------------------------------------ ⑨ σ²(T) 图数据
def test_sigma2_T_series(joint):
    import numpy as np
    from xafsmith.sigma2 import sigma2_curve, sigma2_T_series
    kind, model, res, summ = joint
    (sr,) = sigma2_T_series(summ, fx.normalize_model(model))
    assert sr["theta_param"] == "thD" and sr["model"] == kind
    assert sr["theta"] == summ["params"]["thD"]["value"] and sr["theta_err"] == summ["params"]["thD"]["stderr"]
    assert [p[0] for p in sr["points"]] == [10.0, 100.0, 200.0, 300.0]
    assert abs(sr["static"] - summ["params"]["ss0"]["value"]) < 1e-9          # 表达式 = 模型 + ss0：静态项就是 ss0
    assert sr["T"][0] == 1.0 and abs(sr["T"][-1] - 360.0) < 1e-9
    at_pts = sigma2_curve(FEFF, kind, sr["theta"], [p[0] for p in sr["points"]], static=sr["static"])
    assert np.allclose(at_pts, [p[1] for p in sr["points"]], rtol=1e-9)       # 曲线在各温度处 = 各数据集拟合 σ²


def test_sigma2_T_series_empty_without_model():
    from xafsmith.sigma2 import sigma2_T_series
    assert sigma2_T_series(dict(paths=[dict(sigma2=0.003)]), fx.normalize_model(joint_model("debye"))) == []
