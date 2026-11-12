"""Fe K 边 LCF 基准：合成混合物还原比例。

数据与合成方法见 _fe_synth.py。FeO 与 Fe2O3 同一线站同一次课程（APS 20BM 2001），能量标尺可比；
Fe3C（13-BM-D）来自别的线站，绝对能量不可与前两者比较，只在 LCF 里当“形状”端点
（合成与拟合都在同一能量轴上，与线站无关）。
参考值 = 合成时给定的权重（合成真值）；"本机首跑值"只用于防回归，不是文献值。
"""
import numpy as np
import pytest

from _fe_synth import load_standards, mix
from xafsmith.fit_lcf import fit_all_combinations, lcf, single_standard_compare

RNG = dict(xmin=-20, xmax=30, space="norm", sum_to_one=True, bounds=True)
SEEDS = range(20)
SIGMA = 0.005


@pytest.fixture(scope="module")
def std():
    return load_standards()


@pytest.fixture(scope="module")
def binary(std):
    """二元 FeO 0.3 / Fe2O3 0.7，20 个 seed 的拟合结果。"""
    out = []
    for s in SEEDS:
        g = mix({"FeO": 0.3, "Fe2O3": 0.7}, SIGMA, s, std)
        out.append(lcf(g, [std["FeO"], std["Fe2O3"]], **RNG))
    return out


def test_binary_recovery(binary):
    d = np.array([r["weights"]["FeO"] - 0.3 for r in binary])
    rms = float(np.sqrt(np.mean(d ** 2)))
    print(f"binary: max|dw|={np.max(np.abs(d)):.4f}  RMS={rms:.4f}")
    assert np.all(np.abs(d) < 0.02)
    assert rms < 0.01


def test_ternary_recovery(std):
    truth = {"FeO": 0.5, "Fe2O3": 0.2, "Fe3C": 0.3}
    stds = [std["FeO"], std["Fe2O3"], std["Fe3C"]]
    d = []
    for s in SEEDS:
        r = lcf(mix(truth, SIGMA, s, std), stds, **RNG)
        d.append([r["weights"][k] - v for k, v in truth.items()])
    d = np.array(d)
    rms = np.sqrt(np.mean(d ** 2, axis=0))
    print(f"ternary: max|dw|={np.max(np.abs(d)):.4f}  RMS per comp={np.round(rms, 4)}")
    assert np.all(np.abs(d) < 0.05)
    assert np.all(rms < 0.02)


def test_error_estimate_reasonable(binary):
    """Δw 的标准差 / lcf 报告 stderr 的平均值（stderr 未乘 √χ²ν 时偏小，作为已知现象记录）。"""
    d = np.array([r["weights"]["FeO"] - 0.3 for r in binary])
    err = np.mean([r["weights_err"]["FeO"] for r in binary])
    ratio = float(np.std(d) / err)
    print(f"error: std(dw)={np.std(d):.5f}  mean stderr={err:.5f}  ratio={ratio:.3f}")
    assert 0.5 < ratio < 3


def test_combination_ranking(std):
    stds = [std["FeO"], std["Fe2O3"], std["Fe3C"]]
    g = mix({"FeO": 0.5, "Fe2O3": 0.2, "Fe3C": 0.3}, SIGMA, 0, std)
    df = fit_all_combinations(g, stds, nmax=3, xmin=-20, xmax=30)
    best2 = df[df.n == 2].rfactor.min()
    r3 = df.rfactor.iloc[0]
    print(f"combinations: top n={df.n.iloc[0]}  R3={r3:.3e}  best binary R={best2:.3e}  ratio={best2 / r3:.2f}")
    assert df.n.iloc[0] == 3
    assert best2 >= 2 * r3


def test_single_standard_comparison(std):
    g = mix({"FeO": 0.3, "Fe2O3": 0.7}, SIGMA, 0, std)
    stds = [std["FeO"], std["Fe2O3"]]
    sc = single_standard_compare(g, stds, xmin=-20, xmax=30)
    r2 = lcf(g, stds, **RNG)["rfactor"]
    print(f"single: best single R={sc.rfactor.iloc[0]:.3e}  binary R={r2:.3e}  ratio={sc.rfactor.iloc[0] / r2:.1f}")
    assert sc.rfactor.iloc[0] > 10 * r2
