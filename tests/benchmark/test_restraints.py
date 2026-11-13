"""B3 restraint 软约束：驱动与 larch 逐位一致、权重极限、高斯合并、误差校准、逐数据集统计、警告。

设计与容差见路线图“B3 设计”第 5 节（执行时不得改容差）。
运行：python -m pytest tests/benchmark/test_restraints.py -q
"""
import numpy as np
import pytest

import test_cu_feffit as cu
from test_cu_feffit import MODEL
from test_multi_dataset import SYN_MODEL, TRUTH, _pair, _single_A, _synth

from xafsmith import fit_exafs as fx

chi_tutorial = cu.chi_tutorial          # fixture 复用


def _cu_parts(g, sig2=0.0):
    from larch.fitting import guess, param_group
    from larch.xafs import feffit_dataset, feffit_transform, feffpath
    pars = param_group(amp=guess(1.0), del_e0=guess(0.0), sig2=guess(sig2), del_r=guess(0.0))
    p = feffpath(str(cu.FEFF), label="Cu-Cu", s02="amp", e0="del_e0", sigma2="sig2", deltar="del_r")
    tr = feffit_transform(kmin=3, kmax=17, dk=4, window="kaiser", kweight=2, rmin=1.4, rmax=3.0, fitspace="r")
    return pars, feffit_dataset(data=g, pathlist=[p], transform=tr)


# ------------------------------------------------------------------ R0
def test_restrained_empty_bitwise(chi_tutorial):
    from larch.xafs import feffit, feffit_report
    from xafsmith._feffit_restrained import feffit_restrained
    pa, da = _cu_parts(chi_tutorial)
    ref = feffit(pa, [da])
    pb, db = _cu_parts(chi_tutorial)
    new = feffit_restrained(pb, [db], [], 1.0)
    for k in ("amp", "del_e0", "sig2", "del_r"):
        assert ref.params[k].value == new.params[k].value, k
        assert ref.params[k].stderr == new.params[k].stderr, k
    for k in ("chi_square", "chi2_reduced", "rfactor", "n_independent"):
        assert getattr(ref, k) == getattr(new, k), k
    assert np.array_equal(ref.covar, new.covar)
    assert feffit_report(ref) == feffit_report(new)


# ------------------------------------------------------------------ 共用
def _cu_model(*restraints, **extra):
    m = dict(MODEL, **extra)
    m["restraints"] = [dict(r) for r in restraints]
    return m


@pytest.fixture(scope="module")
def unres(chi_tutorial):
    return fx.run_fit(chi_tutorial, MODEL, root=None)


# ------------------------------------------------------------------ R1
def test_no_restraints_unchanged(chi_tutorial, unres):
    r0, _, s0 = unres
    r1, _, s1 = fx.run_fit(chi_tutorial, dict(MODEL, restraints=[]), root=None)
    assert s0 == s1
    for k in ("restraints", "restraint_chi2", "restraint_c0", "chi2_data"):
        assert k not in s1
    assert not hasattr(r1, "restraints")
    for k in r0.params:
        assert r0.params[k].value == r1.params[k].value, k
        assert r0.params[k].stderr == r1.params[k].stderr, k
    for k in ("rfactor", "chi_square", "chi2_reduced", "n_independent"):
        assert getattr(r0, k) == getattr(r1, k), k
    assert np.array_equal(r0.covar, r1.covar)
    assert fx.report_text(r0) == fx.report_text(r1)


# ------------------------------------------------------------------ R2
def _close(r_a, r_b, rtol=1e-8):
    for k in r_a.params:
        a, b = r_a.params[k], r_b.params[k]
        assert b.value == pytest.approx(a.value, rel=rtol, abs=0), k
        if a.stderr is not None:
            assert b.stderr == pytest.approx(a.stderr, rel=rtol, abs=0), k
    for k in ("chi_square", "chi2_reduced", "rfactor"):
        assert getattr(r_b, k) == pytest.approx(getattr(r_a, k), rel=rtol, abs=0), k


def test_weight_to_zero(chi_tutorial, unres):
    r0 = unres[0]
    r, _, s = fx.run_fit(chi_tutorial, _cu_model(dict(expr="amp", value=0.80, sigma=1e9)), root=None)
    _close(r0, r)
    ga, gb = _pair(0)
    groups = {"A": ga, "B": gb}
    m0, _, _ = fx.fit_multi(groups, SYN_MODEL, root=None)
    m1, _, _ = fx.fit_multi(groups, dict(SYN_MODEL, restraints=[dict(expr="ssA - ssB", value=0, sigma=1e9)]),
                            root=None)
    _close(m0, m1)


# ------------------------------------------------------------------ R3
def _gauss(au, su, p0, sp):
    pv = (au / su ** 2 + p0 / sp ** 2) / (1 / su ** 2 + 1 / sp ** 2)
    ps = (1 / su ** 2 + 1 / sp ** 2) ** -0.5
    return pv, ps


def _check_bookkeeping(res):
    assert res.chi_square == pytest.approx(res.chi2_data + res.restraint_chi2, rel=1e-12, abs=0)
    for r in res.restraints:
        assert r["chi2"] == pytest.approx(res.restraint_c0 * r["pull"] ** 2, rel=1e-12, abs=0)
    assert res.restraint_chi2 == pytest.approx(sum(r["chi2"] for r in res.restraints), rel=1e-12, abs=0)
    num, den, _ = fx._dataset_stats(res)
    assert res.rfactor == pytest.approx(sum(num) / sum(den), rel=1e-12, abs=0)


@pytest.mark.parametrize("case", ["a", "b"])
def test_gaussian_combination(chi_tutorial, unres, case):
    r0 = unres[0]
    au, su, c0 = r0.params["amp"].value, r0.params["amp"].stderr, r0.chi2_reduced
    p0, sp = (au + su, su) if case == "a" else (0.80, 0.01)
    r, _, s = fx.run_fit(chi_tutorial, _cu_model(dict(expr="amp", value=p0, sigma=sp)), root=None)
    a_star, s_star = _gauss(au, su, p0, sp)
    s_star *= np.sqrt(r.chi2_reduced / c0)
    amp, err = r.params["amp"].value, r.params["amp"].stderr
    print(f"\nR3({case}): amp {amp:.5f} 预测 {a_star:.5f}  误差 {err:.5f} 预测 {s_star:.5f} 比 {err / s_star:.4f}"
          f"  su {su:.5f} c0 {c0:.4f}")
    assert abs(amp - a_star) < (0.1 * su if case == "a" else 0.3 * sp)
    assert 0.95 <= err / s_star <= 1.05
    assert r.restraint_c0 == c0
    _check_bookkeeping(r)
    assert s["restraint_chi2"] == r.restraint_chi2 and s["restraint_c0"] == c0
    if case == "a":                                        # R6：(a) 不应出软约束警告
        assert not any("软约束" in w for w in s["warnings"])


# ------------------------------------------------------------------ R4
def test_error_calibration():
    import time
    t0 = time.time()
    zr, zss, ratio = [], [], []
    for seed in range(40):
        rng = np.random.default_rng(seed)
        g = _synth(TRUTH["ssA"], rng)
        p0 = 0.92 + rng.normal(0, 0.10)
        ru, _, _ = fx.run_fit(g, _single_A(), root=None)
        m = dict(_single_A(), restraints=[dict(expr="amp", value=p0, sigma=0.10)])
        r, _, _ = fx.run_fit(g, m, root=None)
        au, su, c0 = ru.params["amp"].value, ru.params["amp"].stderr, ru.chi2_reduced
        _, ps = _gauss(au, su, p0, 0.10)
        ps *= np.sqrt(r.chi2_reduced / c0)
        zr.append((r.params["amp"].value - TRUTH["amp"]) / r.params["amp"].stderr)
        zss.append((r.params["ssA"].value - TRUTH["ssA"]) / r.params["ssA"].stderr)
        ratio.append(r.params["amp"].stderr / ps)
    rms = lambda a: float(np.sqrt(np.mean(np.square(a))))   # noqa: E731
    print(f"\nR4: amp z RMS {rms(zr):.4f}  max|z| {max(abs(np.array(zr))):.4f}  ssA z RMS {rms(zss):.4f}"
          f"  误差/高斯预测 中位数 {np.median(ratio):.4f}  用时 {time.time() - t0:.1f}s")
    assert 0.6 <= rms(zr) <= 1.4
    assert max(abs(np.array(zr))) < 4
    assert 0.6 <= rms(zss) <= 1.4
    assert 0.95 <= float(np.median(ratio)) <= 1.10


# ------------------------------------------------------------------ R5
def test_per_dataset_stats_with_restraint():
    ga, gb = _pair(0)
    groups = {"A": ga, "B": gb}
    nm0 = fx.normalize_model(SYN_MODEL)
    res0, _ = fx._fit_core([ga, gb], nm0, root=None)
    nm = fx.normalize_model(dict(SYN_MODEL, restraints=[dict(expr="ssA - ssB", value=-0.004, sigma=0.001)]))
    res, dsets = fx._fit_core([ga, gb], nm, root=None)
    before = {i: {k: np.array(v, copy=True) for k, v in c.items()} for i, c in fx.model_curves_all(dsets, nm).items()}
    s = fx.summarize_multi(res, nm, groups)
    after = fx.model_curves_all(dsets, nm)
    rows = s["datasets"]
    num, den, _ = fx._dataset_stats(res)
    print(f"\nR5: Σchi2_i {sum(r['chi2'] for r in rows)} + restraint {s['restraint_chi2']} = {s['chi2']}"
          f"  shares {[r['chi2_share'] for r in rows]} + {s['restraint_share']}")
    assert sum(r["chi2"] for r in rows) + s["restraint_chi2"] == pytest.approx(s["chi2"], rel=1e-12, abs=0)
    assert sum(r["chi2_share"] for r in rows) + s["restraint_share"] == pytest.approx(1.0, abs=1e-12)
    assert sum(num) / sum(den) == pytest.approx(s["rfactor"], rel=1e-12, abs=0)
    for r, a, b in zip(rows, num, den):
        assert r["rfactor"] == pytest.approx(a / b, rel=1e-12, abs=0)
    assert sum(r["n_idp"] for r in rows) == s["n_idp"] == float(res0.n_independent)
    for i in before:
        for k in before[i]:
            assert np.array_equal(before[i][k], np.asarray(after[i][k])), (i, k)


# ------------------------------------------------------------------ R6
def test_pull_warning(chi_tutorial):
    r, _, s = fx.run_fit(chi_tutorial, _cu_model(dict(expr="amp", value=0.70, sigma=0.02)), root=None)
    w = [x for x in s["warnings"] if "软约束" in x]
    print(f"\nR6: pull {s['restraints'][0]['pull']:+.3f}  警告 {w}")
    assert w and "r1" in w[0] and abs(s["restraints"][0]["pull"]) > 2
    assert "Restraints" in fx.report_text(r)
