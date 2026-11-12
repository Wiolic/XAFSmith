"""xanes 单元测试。参考值均为合成真值。"""
import math

import numpy as np
import pytest
from larch import Group
from scipy.special import erf

from xafsmith.xanes import edge_features, predict_valence, preedge_fit, valence_calibration

E0 = 7120.0


def _g(flat, e):
    return Group(energy=e, flat=flat, norm=flat, e0=E0, label="syn", element="Fe", edge="K")


def test_edge_features():
    """合成真值：arctan 台阶（中心 E0）+ 高斯白线（E0+8，高 0.5，σ 2）。
    WL_height 的真值是该解析函数的最大值（scipy 有界极小化，与 edge_features 无关）：台阶在 E0+8 处
    已是 0.941，所以真值 ≈ 1.4412 而不是设计稿原写的 1.5（漏算台阶，由 Opus 更正，容差 0.02 不变）。"""
    from scipy.optimize import minimize_scalar

    def flat(x):
        return 0.5 + np.arctan((x - E0) / 1.5) / np.pi + 0.5 * np.exp(-0.5 * ((x - E0 - 8) / 2) ** 2)

    e = np.arange(E0 - 60, E0 + 120, 0.25)
    step = 0.5 + np.arctan((e - E0) / 1.5) / np.pi
    g = _g(flat(e), e)
    f = edge_features(g)
    pk = minimize_scalar(lambda x: -flat(x), bounds=(E0, E0 + 30), method="bounded", options={"xatol": 1e-8})
    print("edge_features:", {k: f[k] for k in ("WL_E", "WL_height", "WL_area", "E_half")},
          "analytic peak:", pk.x - E0, -pk.fun)
    assert abs(f["WL_E"] - (E0 + 8)) < 0.3
    assert abs(f["WL_height"] - (-pk.fun)) < 0.02
    w = (e >= E0) & (e <= E0 + 30)
    assert f["WL_area"] == pytest.approx(getattr(np, "trapezoid", getattr(np, "trapz", None))(np.clip(g.flat[w] - 1, 0, None), e[w]), rel=1e-6)
    gp = _g(step, e)
    ehalf = edge_features(gp)["E_half"]
    print("pure arctan E_half - E0:", ehalf - E0)
    assert abs(ehalf - E0) < 0.05


def test_valence_calibration_exact():
    c = valence_calibration([7120, 7123.5, 7127], [2, 3, 4])
    print("cal:", c["a"], c["b"], c["r2"], c["a_err"])
    assert c["a"] == pytest.approx(3.5, abs=1e-9) and c["b"] == pytest.approx(7113, abs=1e-9)
    assert c["r2"] == pytest.approx(1, abs=1e-9)
    assert c["a_err"] < 1e-6


def test_valence_calibration_edge_cases():
    c = valence_calibration([7120, 7123.5], [2, 3])
    assert math.isnan(c["a_err"])
    with pytest.raises(ValueError):
        valence_calibration([7120, 7121], [2, 2])


def test_predict_valence_error_vs_montecarlo():
    """蒙特卡洛：按 cov 抽 (a,b) 1e4 次（seed 0），与 predict_valence 误差比较。"""
    cal = valence_calibration([7120.3, 7123.2, 7127.4, 7130.1], [2, 3, 4, 5])
    pos = 7125.0
    v, err = predict_valence(cal, pos)
    rng = np.random.default_rng(0)
    ab = rng.multivariate_normal([cal["a"], cal["b"]], np.asarray(cal["cov"]), 10000)
    sd = np.std((pos - ab[:, 1]) / ab[:, 0])
    print("predict_valence err", err, "MC sd", sd, "rel diff", abs(err - sd) / sd)
    assert abs(err - sd) / sd < 0.10


def test_preedge_fit():
    """合成真值：常数 0.02 + erf 台阶（E0+3，σ 2）+ 高斯（E0−8，σ 1.2，面积 0.08）。"""
    e = np.arange(E0 - 60, E0 + 60, 0.2)
    y = 0.02 + 0.5 * (1 + erf((e - E0 - 3) / (2 * math.sqrt(2)))) \
        + 0.08 / (1.2 * math.sqrt(2 * math.pi)) * np.exp(-0.5 * ((e - E0 + 8) / 1.2) ** 2)
    r = preedge_fit(_g(y, e), emin=-20, emax=0)
    p = r["peaks"][0]
    print("preedge: center", p["center"] - E0, "area", p["area"], "warnings", r["warnings"])
    assert abs(p["center"] - (E0 - 8)) < 0.2
    assert abs(p["area"] - 0.08) / 0.08 < 0.15
    assert r["warnings"] == []
    r2 = preedge_fit(_g(y, e), emin=-20, emax=0, npeaks=2)
    areas = sorted(q["area"] for q in r2["peaks"])
    print("preedge npeaks=2 areas", areas, r2["warnings"])
    assert areas[0] < 0.01 or any("面积≈0" in w for w in r2["warnings"])
    with pytest.raises(ValueError):
        preedge_fit(Group(energy=e, mu=y, e0=E0), emin=-20, emax=0)
