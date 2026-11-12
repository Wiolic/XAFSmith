"""Fe K 边位置与价态标定基准。

数据与合成方法见 _fe_synth.py。价态标定只用 FeO（Fe2+）/ Fe2O3（Fe3+）——两者同一线站同一次课程
（APS 20BM 2001），能量标尺可比；Fe3C 与 fe.060 来自别的线站，绝对能量不可与它们比较，故不参与标定。
斜率回归值是“本机首跑值”，不是文献值，仅用于防回归；斜率 > 0 才是物理要求。

E0_deriv（一阶导数最大值）不适合混合物：混合谱的导数是双峰，最大值会跳到其中一个峰，
不随比例连续变化。报告价态时应首选 E_half。
"""
import numpy as np
import pytest

from _fe_synth import load_standards, mix
from xafsmith.xanes import edge_features, predict_valence, valence_calibration

XS = [0.0, 0.25, 0.5, 0.75, 1.0]


@pytest.fixture(scope="module")
def std():
    return load_standards()


@pytest.fixture(scope="module")
def cals(std):
    out = {}
    for key in ("E_half", "E0_deriv"):
        pos = [edge_features(std[n])[key] for n in ("FeO", "Fe2O3")]
        out[key] = valence_calibration(pos, [2, 3])
    return out


def test_calibration_slopes(cals):
    h, d = cals["E_half"]["a"], cals["E0_deriv"]["a"]
    print(f"slopes: E_half {h:.3f}  E0_deriv {d:.3f} eV/valence")
    assert h > 0 and d > 0
    assert abs(h - 3.82) < 0.1
    assert abs(d - 3.09) < 0.1


def test_mixture_valence_ehalf(std, cals):
    dev = []
    for x in XS:
        g = mix({"FeO": 1 - x, "Fe2O3": x}, 0.0, 0, std)
        v, _ = predict_valence(cals["E_half"], edge_features(g)["E_half"])
        dev.append(v - (2 + x))
    print("E_half valence deviations:", np.round(dev, 4))
    assert max(abs(d) for d in dev) < 0.06


def test_mixture_valence_e0deriv_unsuitable(std, cals):
    g = mix({"FeO": 0.5, "Fe2O3": 0.5}, 0.0, 0, std)
    v, _ = predict_valence(cals["E0_deriv"], edge_features(g)["E0_deriv"])
    dev = v - 2.5
    print(f"E0_deriv valence deviation at x=0.5: {dev:.3f}")
    assert abs(dev) > 0.3


def test_noise_robustness(std):
    eh, ed = [], []
    for s in range(20):
        f = edge_features(mix({"FeO": 0.5, "Fe2O3": 0.5}, 0.005, s, std))
        eh.append(f["E_half"])
        ed.append(f["E0_deriv"])
    print(f"noise: std(E_half)={np.std(eh):.4f}  std(E0_deriv)={np.std(ed):.4f}")
    assert np.std(eh) < 0.06
    assert np.std(ed) < 0.2
