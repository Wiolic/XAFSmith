"""fit_lcf 单元测试（无噪声；带噪声的统计检验在 tests/benchmark/test_fe_lcf.py）。
合成方法见 tests/benchmark/_fe_synth.py。"""
import importlib.util
from pathlib import Path

import numpy as np
import pytest
from larch import Group

from xafsmith.fit_lcf import fit_all_combinations, lcf, result_row, single_standard_compare

_spec = importlib.util.spec_from_file_location(
    "_fe_synth", Path(__file__).resolve().parents[1] / "benchmark" / "_fe_synth.py")
synth = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(synth)

RNG = dict(xmin=-20, xmax=30)


@pytest.fixture(scope="module")
def std():
    return synth.load_standards()


def test_self_consistency(std):
    """合成真值：样品 = FeO 本身 → w=1，R 因子≈0。"""
    r = lcf(std["FeO"], [std["FeO"], std["Fe2O3"]], **RNG)      # 样品就是标样本身（不经合成再归一化）
    print("self: w", r["weights"], "R", r["rfactor"])
    assert abs(r["weights"]["FeO"] - 1) < 1e-3
    assert r["rfactor"] < 1e-6


def test_noiseless_binary(std):
    """合成真值：FeO 0.3 + Fe2O3 0.7，无噪声。"""
    s = synth.mix({"FeO": 0.3, "Fe2O3": 0.7}, std=std)
    r = lcf(s, [std["FeO"], std["Fe2O3"]], **RNG)
    print("binary: w", r["weights"], "sum", r["sum_weights"], "R", r["rfactor"])
    assert abs(r["weights"]["FeO"] - 0.3) < 0.005
    assert abs(r["weights"]["Fe2O3"] - 0.7) < 0.005
    assert abs(r["sum_weights"] - 1) < 1e-3


def test_no_sum_constraint_and_bounds(std):
    """合成真值：样品 = 0.8×FeO，sum_to_one=False → w=0.8；bounds=True 时权重在 [0,1]。"""
    f = std["FeO"]
    s = Group(energy=f.energy.copy(), flat=0.8 * f.flat, norm=0.8 * f.norm, e0=f.e0, label="0.8FeO")
    r = lcf(s, [f], sum_to_one=False, **RNG)
    print("0.8x: w", r["weights"])
    assert abs(r["weights"]["FeO"] - 0.8) < 0.005
    r2 = lcf(synth.mix({"FeO": 0.3, "Fe2O3": 0.7}, std=std), [std["FeO"], std["Fe2O3"]], bounds=True, **RNG)
    assert all(-1e-9 <= w <= 1 + 1e-9 for w in r2["weights"].values())


def test_eshift(std):
    """合成真值：样品 = FeO 能量平移 +1.5 eV → de=1.5；space='chik' 时 de 不变化。"""
    f = std["FeO"]
    sh = Group(energy=f.energy + 1.5, flat=f.flat.copy(), norm=f.norm.copy(), e0=f.e0 + 1.5,
               label="shifted")
    r = lcf(sh, [f], fit_eshift=True, **RNG)
    print("eshift: de", r["de"], "w", r["weights"])
    assert abs(r["de"] - 1.5) < 0.1
    assert abs(r["weights"]["FeO"] - 1) < 0.01
    k = np.arange(0, 12, 0.05)
    c = Group(k=k, chi=np.sin(2 * k * 2), label="c", e0=0.0)
    r2 = lcf(c, [c], space="chik", xmin=3, xmax=10, fit_eshift=True, sum_to_one=False)
    assert r2["de"] == 0.0


def test_all_combinations(std):
    """三标样 nmax=3 → 7 行，按 rfactor 升序，真组合排第一；single_standard_compare 每标样一行。"""
    s = synth.mix({"FeO": 0.5, "Fe2O3": 0.2, "Fe3C": 0.3}, std=std)
    stds = [std["FeO"], std["Fe2O3"], std["Fe3C"]]
    df = fit_all_combinations(s, stds, nmax=3, **RNG)
    print(df[["n", "rfactor"]].to_string())
    assert len(df) == 7
    assert list(df.rfactor) == sorted(df.rfactor)
    assert df.n.iloc[0] == 3
    sc = single_standard_compare(s, stds, **RNG)
    assert len(sc) == 3


def test_result_row(std):
    s = synth.mix({"FeO": 0.3, "Fe2O3": 0.7}, std=std)
    row = result_row(lcf(s, [std["FeO"], std["Fe2O3"]], **RNG))
    assert "w[FeO]" in row and "err[Fe2O3]" in row
