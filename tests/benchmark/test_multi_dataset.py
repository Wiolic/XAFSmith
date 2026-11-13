"""B1 多数据集同时拟合：向后兼容（逐位）与联合拟合的统计性质。

设计与容差见路线图“B1 设计”第 5 节（执行时不得改容差）。
  T1 旧格式新 run_fit 与 v1.1 冻结副本（_legacy_fit_v11.py）逐位一致；
  T2 fit_multi 处理单数据集与 run_fit 一致；
  T3 同一 χ 两次：参数不变，误差比 = √((N₁−v)/(2N₁−v))（不是 1/√2，v ≪ N₁ 时才趋于它）；
  T4 合成谱误差校准（20 个噪声种子）；
  T5 逐数据集统计与 larch 合计值一致；
  T6 失配警告。
运行：python -m pytest tests/benchmark/test_multi_dataset.py -q
"""
import numpy as np
import pytest

import _legacy_fit_v11 as legacy
import test_cu_feffit as cu
from test_cu_feffit import FEFF, MODEL

from xafsmith import fit_exafs as fx

chi_tutorial = cu.chi_tutorial          # fixture 复用（与 Cu 基准同一 χ(k)）


def _same_fit(r1, s1, r2, s2):
    assert s1 == s2
    assert list(r1.params) == list(r2.params)
    for k in r1.params:
        a, b = r1.params[k], r2.params[k]
        assert a.value == b.value, k
        assert a.stderr == b.stderr, k
    for k in ("rfactor", "chi_square", "chi2_reduced", "n_independent"):
        assert getattr(r1, k) == getattr(r2, k), k
    assert np.array_equal(r1.covar, r2.covar)


# ------------------------------------------------------------------ T1
def test_legacy_bitwise(chi_tutorial):
    r_new, _, s_new = fx.run_fit(chi_tutorial, MODEL, root=None)
    r_old, _, s_old = legacy.run_fit(chi_tutorial, MODEL, root=None)
    _same_fit(r_new, s_new, r_old, s_old)
    assert fx.report_text(r_new) == fx.report_text(r_old)


# ------------------------------------------------------------------ 共用
TRUTH = dict(amp=0.92, del_e0=4.4, del_r=-0.006, ssA=0.0087, ssB=0.0127)
RANGE = {k: MODEL[k] for k in ("kmin", "kmax", "dk", "window", "kweight", "rmin", "rmax", "fitspace")}


def _path(sig):
    return {"file": str(FEFF), "label": "Cu-Cu", "s02": "amp", "e0": "del_e0", "deltar": "del_r", "sigma2": sig}


def _multi(datasets, params=None):
    return dict(name="Cu_joint", **RANGE,
                params=params or {"amp": 1.0, "del_e0": 0.0, "del_r": 0.0, "ssA": 0.005, "ssB": 0.005},
                datasets=datasets)


def _synth(sig2, seed_rng):
    from larch import Group
    from larch.xafs import feffpath, ff2chi
    k = np.arange(0, 18 + 1e-9, 0.05)
    p = feffpath(str(FEFF), s02=TRUTH["amp"], e0=TRUTH["del_e0"], deltar=TRUTH["del_r"], sigma2=sig2)
    g = Group()
    ff2chi([p], k=k, group=g)
    chi = np.interp(k, g.k, g.chi) + seed_rng.normal(0, 0.01, k.size)
    return Group(k=k, chi=chi)


def _pair(seed):
    rng = np.random.default_rng(seed)
    return _synth(TRUTH["ssA"], rng), _synth(TRUTH["ssB"], rng)


SYN_MODEL = _multi([dict(id="A", sample="synA", kmax=17, paths=[_path("ssA")]),
                    dict(id="B", sample="synB", kmax=14, paths=[_path("ssB")])])


def _single_A():
    return dict(name="A_only", sample="synA", **{**RANGE, "kmax": 17},
                params={"amp": 1.0, "del_e0": 0.0, "del_r": 0.0, "ssA": 0.005}, paths=[_path("ssA")])


# ------------------------------------------------------------------ T2
def test_fit_multi_single_equals_run_fit(chi_tutorial):
    r0, _, s0 = fx.run_fit(chi_tutorial, MODEL, root=None)
    one = {k: v for k, v in MODEL.items() if k not in ("sample", "paths")}
    one["datasets"] = [dict(sample="cu_metal_rt", paths=MODEL["paths"])]
    for m in (MODEL, one):
        r, ds, s = fx.fit_multi({"cu_metal_rt": chi_tutorial}, m, root=None)
        for k in r0.params:
            assert r.params[k].value == r0.params[k].value, k
            assert r.params[k].stderr == r0.params[k].stderr, k
        for k in ("rfactor", "chi_square", "chi2_reduced", "n_independent"):
            assert getattr(r, k) == getattr(r0, k), k
        assert s["params"] == s0["params"] and s["nvarys"] == s0["nvarys"]
        d = s["datasets"][0]
        assert d["rfactor"] == pytest.approx(r0.rfactor, rel=1e-12, abs=0)
        assert d["chi2_share"] == pytest.approx(1.0, abs=1e-12)
        assert [{k: v for k, v in p.items() if k != "dataset"} for p in s["paths"]] == s0["paths"]


# ------------------------------------------------------------------ T3
def test_twin(chi_tutorial):
    r1, _, s1 = fx.run_fit(chi_tutorial, MODEL, root=None)
    twin = {k: v for k, v in MODEL.items() if k not in ("sample", "paths")}
    twin["datasets"] = [dict(id="A", sample="cu_metal_rt", paths=MODEL["paths"]),
                        dict(id="B", sample="cu_metal_rt", paths=MODEL["paths"])]
    r2, _, s2 = fx.fit_multi({"A": chi_tutorial, "B": chi_tutorial}, twin, root=None)
    n1, v = r1.n_independent, r1.nvarys
    expect = np.sqrt((n1 - v) / (2 * n1 - v))
    print(f"\nT3: N1={n1:.6f} v={v} 期望比 {expect:.6f}")
    for k in ("amp", "del_e0", "sig2", "del_r"):
        a, b = r1.params[k], r2.params[k]
        dz, ratio = abs(a.value - b.value) / a.stderr, b.stderr / a.stderr
        print(f"  {k}: 单 {a.value:.6g}±{a.stderr:.4g}  双 {b.value:.6g}±{b.stderr:.4g}  |Δ|/σ={dz:.2e}  σ比={ratio:.6f}")
        assert dz < 1e-6, k
        assert ratio == pytest.approx(expect, rel=1e-6), k
    print(f"  n_idp {s2['n_idp']:.6f}  R {s1['rfactor']:.8g} vs {s2['rfactor']:.8g}  "
          f"share {[d['chi2_share'] for d in s2['datasets']]}  警告 {s2['warnings']}")
    assert s2["n_idp"] == pytest.approx(2 * n1, rel=1e-12)
    assert s2["rfactor"] == pytest.approx(s1["rfactor"], rel=1e-9)
    for d in s2["datasets"]:
        assert d["chi2_share"] == pytest.approx(0.5, abs=1e-9)
    assert any("重复使用" in w for w in s2["warnings"])
    assert not any("失配" in w for w in s2["warnings"])


# ------------------------------------------------------------------ T4
def test_error_calibration():
    z = {k: [] for k in ("amp", "ssA", "ssB")}
    ratio = []
    for seed in range(20):
        ga, gb = _pair(seed)
        r, _, _ = fx.fit_multi({"A": ga, "B": gb}, SYN_MODEL, root=None)
        for k in z:
            z[k].append((r.params[k].value - TRUTH[k]) / r.params[k].stderr)
        ra, _, _ = fx.run_fit(ga, _single_A(), root=None)
        ratio.append(r.params["amp"].stderr / ra.params["amp"].stderr)
    rms = {k: float(np.sqrt(np.mean(np.square(v)))) for k, v in z.items()}
    zmax = max(abs(x) for v in z.values() for x in v)
    med = float(np.median(ratio))
    print(f"\nT4: z RMS {rms}  max|z| {zmax:.3f}  σ_amp 联合/只拟合A 中位数 {med:.4f}")
    for k, v in rms.items():
        assert 0.6 <= v <= 1.5, (k, v)
    assert zmax < 4
    assert med < 0.9


# ------------------------------------------------------------------ T5
def test_per_dataset_stats():
    ga, gb = _pair(0)
    groups = {"A": ga, "B": gb}
    nm = fx.normalize_model(SYN_MODEL)
    res, dsets = fx._fit_core([ga, gb], nm, root=None)
    before = {i: {k: np.array(v, copy=True) for k, v in c.items()} for i, c in fx.model_curves_all(dsets, nm).items()}
    s = fx.summarize_multi(res, nm, groups)
    after = fx.model_curves_all(dsets, nm)
    assert "restraint_share" not in s               # B3: no extra key without restraints
    rows = s["datasets"]
    num, den, _ = fx._dataset_stats(res)
    print(f"\nT5: n_idp {[r['n_idp'] for r in rows]} 合计 {s['n_idp']}  chi2_i {[r['chi2'] for r in rows]} 合计 {s['chi2']}"
          f"  R_i {[r['rfactor'] for r in rows]}  R {s['rfactor']}  Σnum/Σden {sum(num) / sum(den)}")
    for r in rows:
        assert r["n_idp"] == pytest.approx(1 + 2 * (r["kmax"] - r["kmin"]) * (r["rmax"] - r["rmin"]) / np.pi, abs=1e-9)
    assert sum(r["n_idp"] for r in rows) == pytest.approx(s["n_idp"], rel=1e-12)
    assert sum(r["chi2"] for r in rows) == pytest.approx(s["chi2"], rel=1e-12)
    assert sum(num) / sum(den) == pytest.approx(s["rfactor"], rel=1e-12)
    for i in before:
        for k in before[i]:
            assert np.array_equal(before[i][k], np.asarray(after[i][k])), (i, k)


# ------------------------------------------------------------------ T6
def test_misfit_warning(chi_tutorial):
    """实测 Cu（A）+ 合成 ssB 谱（B）。A 的系统失配（实测谱对单壳层模型的偏差远大于合成谱的白噪声）使 χ² 主要来自 A；
    误差按合计 χ²_ν 统一缩放，于是 B 的误差也被放大（20 个种子下 ssB 的 z RMS 仅约 0.33）——
    这是“统一缩放”的已知后果，不是 bug；警告就是为提示这一点。"""
    _, gb = _pair(0)
    m = _multi([dict(id="A", sample="cu_metal_rt", kmax=17, paths=[_path("ssA")]),
                dict(id="B", sample="synB", kmax=14, paths=[_path("ssB")])])
    r, _, s = fx.fit_multi({"A": chi_tutorial, "B": gb}, m, root=None)
    sh = {d["id"]: d["chi2_share"] for d in s["datasets"]}
    p = r.params["ssB"]
    print(f"\nT6: chi2_share {sh}  ssB {p.value:.5f}±{p.stderr:.5f}（真值 {TRUTH['ssB']}）  警告 {s['warnings']}")
    mis = [w for w in s["warnings"] if "失配" in w]
    assert mis and mis[0].startswith("数据集 A ")
    assert sh["A"] > 0.85
    assert abs(p.value - TRUTH["ssB"]) < 2 * p.stderr


def test_no_false_misfit_with_kweight_list():
    """Opus 核对时加：两个都在噪声水平的合成谱，B 用 k 权重 [1,2,3]（拟合点数 ×3，N_idp 不变）。
    失配警告若按 χ²/N_idp 判断，10 个种子中比值中位数约 3.3、最大约 10（误报）；按每点残差平方均值判断最大约 2.7。"""
    m = _multi([dict(id="A", sample="synA", kmax=17, paths=[_path("ssA")]),
                dict(id="B", sample="synB", kmax=14, kweight=[1, 2, 3], paths=[_path("ssB")])])
    ratios = []
    for seed in range(10):
        ga, gb = _pair(seed)
        _, _, s = fx.fit_multi({"A": ga, "B": gb}, m, root=None)
        rp = [d["resid2_per_point"] for d in s["datasets"]]
        ratios.append(max(rp) / min(rp))
        assert not any("失配" in w for w in s["warnings"]), (seed, s["warnings"])
    print(f"\n每点残差平方均值比：中位数 {np.median(ratios):.2f}  最大 {max(ratios):.2f}")
