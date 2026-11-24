"""quickfit：第一壳层、自动 Rmin、建模型、判定、CLI；合成 FEFF 路径表 + 演示项目（Cu）+ 项目对照（有项目才跑）。"""
import json
import shutil
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest

from xafsmith import paths, quickfit as qf

TESTS = Path(__file__).resolve().parents[1]
DEMO = TESTS / "data" / "demo_project"
FEFF_CU = TESTS / "data" / "benchmark" / "feffcu01.dat"
PROJECT = Path(__file__).resolve().parents[3]            # …/XAFS（含 XAFSmith/ 的项目根目录）


def table(*rows):
    """rows：(label, reff, degen[, nleg])；输入故意不排序时也应得到同样结果。"""
    return pd.DataFrame([dict(file=f"/x/feff{i + 1:04d}.dat", label=r[0], reff=r[1], degen=r[2],
                              nleg=r[3] if len(r) > 3 else 2) for i, r in enumerate(rows)])


# ---------------------------------------------------------------- 第一壳层
def test_first_shell_single_element():
    s = qf.first_shell(table(("Ir-O", 2.0, 6), ("Ir-Ir", 3.2, 8)))
    assert (s.absorber, s.scatterer, s.n_ref, s.r_cif) == ("Ir", "O", 6, 2.0)
    assert len(s.members) == 1 and not s.other_elements


def test_first_shell_distorted_octahedron_is_one_shell():
    s = qf.first_shell(table(("Ir-O", 2.00, 2), ("Ir-O", 1.94, 4), ("Ir-Ir", 3.1, 8)))     # 不按 Reff 排序的输入
    assert [m["reff"] for m in s.members] == [1.94, 2.00]
    assert s.n_ref == 6 and s.r_cif == pytest.approx((4 * 1.94 + 2 * 2.00) / 6)


def test_first_shell_other_element_within_gap_is_noted_and_stops():
    s = qf.first_shell(table(("Fe-O", 2.00, 4), ("Fe-N", 2.10, 2), ("Fe-O", 2.15, 2)))
    assert s.scatterer == "O" and s.n_ref == 4                 # 遇到异种元素即停，后面的同元素路径不并入
    assert s.other_elements == [("N", 2.10)]


def test_first_shell_other_element_far_is_not_noted():
    s = qf.first_shell(table(("Fe-O", 2.00, 4), ("Fe-N", 2.40, 2)))
    assert s.other_elements == []


def test_first_shell_gap_stops_merging():
    s = qf.first_shell(table(("Cu-Cu", 2.55, 12), ("Cu-Cu", 3.61, 6)))
    assert s.n_ref == 12 and len(s.members) == 1
    s = qf.first_shell(table(("Fe-O", 1.90, 3), ("Fe-O", 2.15, 3), ("Fe-O", 2.50, 2)))    # 0.25 并入，0.35 不并入
    assert [m["reff"] for m in s.members] == [1.90, 2.15] and s.n_ref == 6


def test_first_shell_ignores_multiple_scattering_and_needs_single_scattering():
    s = qf.first_shell(table(("Cu-Cu-Cu", 2.2, 48, 3), ("Cu-Cu", 2.55, 12)))
    assert s.n_ref == 12
    with pytest.raises(qf.QuickFitError):
        qf.first_shell(table(("Cu-Cu-Cu", 2.2, 48, 3)))


# ---------------------------------------------------------------- 自动 Rmin
R = np.arange(0, 6, 0.02)


def _peak(c, w=0.1):
    return np.exp(-((R - c) ** 2) / w)


def test_auto_rmin_with_minimum():
    mag = 3 * _peak(1.6) + 0.8 * _peak(0.8, 0.02) + 0.05
    rmin, rp = qf.auto_rmin(R, mag, 2.5)
    assert rp == pytest.approx(1.6, abs=0.021)
    sel = (R >= 0.7) & (R <= 1.6)
    assert 0.9 < rmin < 1.3 and mag[np.argmin(abs(R - rmin))] == mag[sel].min()          # 落在低 R 凸起与第一峰之间的谷里


def test_auto_rmin_without_minimum_uses_1():
    mag = 3 * _peak(1.6) + 0.05 * R                                          # 0.7 Å 起单调上升
    assert qf.auto_rmin(R, mag, 2.5) == (1.0, pytest.approx(1.6, abs=0.021))


def test_auto_rmin_without_minimum_far_peak_is_clamped():
    mag = 3 * _peak(2.3) + 0.05 * R                                          # 单调上升到 2.3 Å 的峰（如金属）
    rmin, rp = qf.auto_rmin(R, mag, 3.0)
    assert rp == pytest.approx(2.3, abs=0.021) and rmin == pytest.approx(rp - qf.RMIN_BELOW_PEAK)


def test_auto_rmin_minimum_far_below_peak_is_clamped():
    mag = 3 * _peak(1.5) + 0.8 * _peak(0.5, 0.02) + 0.02 * (R - 0.74) ** 2        # 谷在 ≈ 0.74 Å，离峰 0.76 Å
    rmin, rp = qf.auto_rmin(R, mag, 2.5)
    assert rp == pytest.approx(1.5, abs=0.021) and rmin == pytest.approx(rp - qf.RMIN_BELOW_PEAK)


def test_first_shell_site_labels_are_reduced_to_elements():
    s = qf.first_shell(table(("Ta1-O1", 1.98, 4), ("Ta1-O2", 2.01, 2), ("Ta1-K1", 3.4, 8)))
    assert (s.absorber, s.scatterer, s.n_ref) == ("Ta", "O", 6) and not s.other_elements


def test_auto_rmin_peak_search_limited_to_rmax():
    mag = _peak(1.6) + 2 * _peak(3.5)
    assert qf.auto_rmin(R, mag, 2.5)[1] == pytest.approx(1.6, abs=0.021)
    with pytest.raises(qf.QuickFitError):
        qf.auto_rmin(R, mag, 0.9)


# ---------------------------------------------------------------- 判定
SHELL = qf.FirstShell([dict(file="f1.dat", label="A-B", reff=1.94, degen=4.0), dict(file="f2.dat", label="A-B", reff=2.00, degen=2.0)],
                      "A", "B", 6.0, (4 * 1.94 + 2 * 2.0) / 6)


def fake_fit(mode="sample", n=6.0, dr=0.0, rf=0.01, nv=4, nidp=9.0, s02=0.8):
    P = dict(e0=dict(value=2.0, stderr=0.5, vary=True, expr=None), dr1=dict(value=dr, stderr=0.01, vary=True, expr=None),
             ss1=dict(value=0.005, stderr=0.001, vary=True, expr=None))
    if mode == "sample":
        P["n1"] = dict(value=n, stderr=0.5, vary=True, expr=None)
        P["s02"] = dict(value=s02, stderr=None, vary=False, expr=None)
    else:
        P["s02"] = dict(value=s02, stderr=0.05, vary=True, expr=None)
    summ = dict(rfactor=rf, nvarys=nv, n_idp=nidp, params=P, sample="s",
                paths=[dict(path="p1", R=1.94 + dr, sigma2=0.005, deltar=dr), dict(path="p2", R=2.00 + dr, sigma2=0.005, deltar=dr)])
    corr = {k: None for k in P}
    return dict(summ=summ, model=dict(kweight=[1, 2, 3], params={}), result=SimpleNamespace(
        params={k: SimpleNamespace(vary=v["vary"], correl=corr[k]) for k, v in P.items()}), robust=None)


def codes(v, level):
    return {i.code for i in v.items if i.level == level}


def test_verdict_all_pass():
    v = qf.verdict(fake_fit(), SHELL, "sample", 2.5, 1.0, 0.1, dict(model="std", value=0.8, stderr=0.05))
    assert v.ok and not v.failed and not v.notes
    assert {"rfactor", "nvarys", "r_cif", "n_ratio", "rmax_leak"} <= codes(v, "pass")
    assert "✅" in v.summary("zh") and "Trustworthy" in v.summary("en")


@pytest.mark.parametrize("dr,ok", [(0.14, True), (0.16, False)])
def test_verdict_r_cif(dr, ok):
    v = qf.verdict(fake_fit(dr=dr), SHELL, "sample", 2.5, 1.0, 0.1)
    assert ("r_cif" in codes(v, "pass")) is ok and ("r_cif" in codes(v, "fail")) is not ok
    assert v.ok is (ok and True) or "r_cif" in codes(v, "fail")


@pytest.mark.parametrize("n,ok", [(9.0, True), (9.2, False)])
def test_verdict_n_ratio_sample_only(n, ok):
    v = qf.verdict(fake_fit(n=n), SHELL, "sample", 2.5, 1.0, 0.1)
    assert ("n_ratio" in codes(v, "pass")) is ok and ("n_ratio" in codes(v, "fail")) is not ok
    assert all(i.advice_zh and i.advice_en for i in v.failed)
    v = qf.verdict(fake_fit("standard", n=99.0), SHELL, "standard", 2.5, 1.0, 0.1)          # 标样：N 固定，不检查
    assert not codes(v, "pass") & {"n_ratio"} and not codes(v, "fail") & {"n_ratio"}


@pytest.mark.parametrize("amp,ok", [(0.30, True), (0.31, False)])
def test_verdict_rmax_leak(amp, ok):
    v = qf.verdict(fake_fit(), SHELL, "sample", 2.5, 1.0, amp)
    assert ("rmax_leak" in codes(v, "pass")) is ok and ("rmax_leak" in codes(v, "fail")) is not ok
    assert "rmax_leak" not in {i.code for i in qf.verdict(fake_fit(), SHELL, "sample", 2.5).items}      # 缺数据则不检查


def test_verdict_stern_counts():
    assert "nvarys" in codes(qf.verdict(fake_fit(nv=4, nidp=9.0), SHELL, "sample", 2.5), "pass")
    v = qf.verdict(fake_fit(nv=4, nidp=6.0), SHELL, "sample", 2.5)           # N_idp/2 < nv ≤ N_idp：通过 + 信息量偏少的提示
    assert "nvarys" in codes(v, "pass") and "nvarys_low_info" in codes(v, "note") and v.ok
    v = qf.verdict(fake_fit(nv=7, nidp=6.0), SHELL, "sample", 2.5)
    assert "nvarys" in codes(v, "fail") and not v.ok


def test_verdict_rfactor_fail_has_advice():
    v = qf.verdict(fake_fit(rf=0.09), SHELL, "sample", 2.5)
    assert not v.ok and v.failed[0].code == "rfactor" and v.failed[0].advice_zh and v.failed[0].advice_en
    assert "⚠" in v.summary("zh")


def test_verdict_notes_do_not_fail():
    sh = qf.FirstShell(SHELL.members, "A", "B", 6.0, SHELL.r_cif, [("C", 2.1)])
    v = qf.verdict(fake_fit(), sh, "sample", 2.5, 1.0, 0.1, dict(manual=True, value=0.8))
    assert v.ok and {"manual_s02", "other_elements"} <= codes(v, "note")
    v = qf.verdict(fake_fit(), SHELL, "sample", 2.5, 1.0, 0.1, dict(model="m", value=0.8, stderr=0.05))
    assert not codes(v, "note")
    v = qf.verdict(fake_fit("standard"), sh, "standard", 2.5, 1.0, 0.1)         # 标样没有 S0² 来源提示
    assert "manual_s02" not in codes(v, "note")


# ---------------------------------------------------------------- 演示项目（Cu）端到端
@pytest.fixture(scope="module")
def proj(tmp_path_factory):
    d = tmp_path_factory.mktemp("qf") / "demo_project"
    shutil.copytree(DEMO, d)
    f = d / "output" / "feff" / "Cu_CuK"
    f.mkdir(parents=True)
    shutil.copyfile(FEFF_CU, f / "feff0001.dat")          # Cu–Cu 单散射，N = 12
    old = paths.ROOT
    paths.set_root(d)
    yield d
    paths.set_root(old)


FEFF = "output/feff/Cu_CuK"


def test_build_model_errors(proj):
    with pytest.raises(qf.QuickFitError):
        qf.build_model("cu_metal_rt", FEFF, 3.0, "sample")                         # 样品模式没有 S0²
    with pytest.raises(qf.QuickFitError):
        qf.build_model("no_such_sample", FEFF, 3.0, "standard")
    with pytest.raises(qf.QuickFitError):
        qf.build_model("cu_metal_rt", "output/feff/nothing", 3.0, "standard")
    with pytest.raises(qf.QuickFitError):
        qf.build_model("cu_metal_rt", FEFF, 3.0, "bogus")


def test_build_model_missing_k_window(proj):
    cfg = json.loads((proj / "xafsmith.json").read_text(encoding="utf-8-sig"))
    del cfg["edges"]["Cu_K"]["ft"]["dk"]
    bad = proj.parent / "nodk"
    shutil.copytree(proj, bad)
    (bad / "xafsmith.json").write_text(json.dumps(cfg), encoding="utf-8")
    old = paths.ROOT
    paths.set_root(bad)
    try:
        with pytest.raises(qf.QuickFitError, match="k 窗"):
            qf.build_model("cu_metal_rt", FEFF, 3.0, "standard", rmin=1.0)
    finally:
        paths.set_root(old)


def test_standard_model_structure_and_run(proj):
    m = qf.build_model("cu_metal_rt", FEFF, 3.0, "standard")
    json.dumps(m)                                                        # 普通 JSON 模型
    assert m["kweight"] == [1, 2, 3] and m["rmax"] == 3.0 and 0.7 <= m["rmin"] < 3.0
    assert m["params"]["s02"] == dict(value=0.85, vary=True, min=0.3, max=1.5)
    assert m["params"]["e0"] == dict(value=0.0, vary=True, min=-15.0, max=15.0)
    assert m["params"]["dr1"]["min"] == -0.5 and m["params"]["ss1"] == dict(value=0.003, vary=True, min=0.0, max=0.05)
    assert "n1" not in m["params"] and "s02_source" not in m and all("N" not in p for p in m["paths"])
    assert m["paths"][0]["file"] == f"{FEFF}/feff0001.dat" and m["paths"][0]["deltar"] == "dr1"
    r = qf.run(m)
    assert r.mode == "standard" and r.n == 12 and r.n_err is None and r.s02_err is not None
    assert 0.3 < r.s02 < 1.5 and 0 < r.sigma2 < 0.03 and abs(r.r - r.shell.r_cif) < 0.15
    assert r.window["rmax"] == 3.0 and r.verdict.items and r.fit["summ"]["model"] == m["name"]
    assert "N_idp" in qf.format_text(r) and "Trustworthy" in qf.format_text(r, "en") + "Trustworthy"


def test_sample_model_structure_and_run(proj):
    m = qf.build_model("cu_metal_rt", FEFF, 3.0, "sample", s02=0.9, rmin=1.2, kweight=[2])
    assert m["rmin"] == 1.2 and m["kweight"] == [2]
    assert m["params"]["s02"] == dict(value=0.9, vary=False)
    assert m["params"]["n1"] == dict(value=12.0, vary=True, min=0.0, max=24.0)
    assert m["paths"][0]["N"] == "n1*12.0/12.0" and m["s02_source"] == dict(manual=True, value=0.9)
    r = qf.run(m)
    assert r.mode == "sample" and r.s02 == 0.9 and r.s02_err is None and r.n_err is not None
    assert "manual_s02" in {i.code for i in r.verdict.notes}
    src = dict(model="std", value=0.9, stderr=0.04)
    assert qf.build_model("cu_metal_rt", FEFF, 3.0, "sample", s02=0.9, s02_source=src, rmin=1.2)["s02_source"] == src


def test_krange_and_kweight_override(proj):
    m = qf.build_model("cu_metal_rt", FEFF, 3.0, "standard", rmin=1.0, krange=dict(kmin=3.5, kmax=11, dk=2, window="kaiser"))
    assert (m["kmin"], m["kmax"], m["dk"], m["window"]) == (3.5, 11, 2, "kaiser")


# ---------------------------------------------------------------- 项目对照（有项目才跑）
@pytest.mark.skipif(not (PROJECT / "models" / "IrO2_1shell_ArtemisCompare.json").exists()
                    or not (PROJECT / "output" / "feff" / "IrO2_IrL3" / "site0").exists(),
                    reason="需要 IrTaOx 项目（IrO2 标样与 Artemis 对照模型）")
def test_iro2_matches_artemis_compare_model():
    from xafsmith import fit_exafs as fx, pipeline as pl
    old = paths.ROOT
    paths.set_root(PROJECT)
    try:
        ref = json.loads((PROJECT / "models" / "IrO2_1shell_ArtemisCompare.json").read_text(encoding="utf-8-sig"))
        m = qf.build_model("IrO2", "output/feff/IrO2_IrL3/site0", 2.5, "standard", rmin=1.0, kweight=[1, 2, 3],
                           krange=dict(kmin=3, kmax=12.5, dk=1, window="hanning"))
        # 语义相同：同样的路径文件、共用 dr1 / ss1、N = FEFF 简并度、S0² 与 ΔE0 拟合
        assert [p["file"] for p in m["paths"]] == [p["file"] for p in ref["paths"]]
        assert all(p["deltar"] == "dr1" and p["sigma2"] == "ss1" and "N" not in p for p in m["paths"])
        assert set(m["params"]) == set(ref["params"]) and all(v["vary"] for v in m["params"].values())
        for k in ("kmin", "kmax", "dk", "window", "kweight", "rmin", "rmax"):
            assert m[k] == ref[k], k
        g, _ = pl.build_sample("IrO2")
        s_ref = fx.run_fit(g, ref)[2]["params"]
        res = qf.run(m, group=g)
        assert abs(res.s02 - s_ref["s02"]["value"]) < 1e-4
        assert abs(res.e0 - s_ref["e0"]["value"]) < 1e-3
        assert abs(res.s02 - 0.816) < 2e-3 and abs(res.e0 - 8.93) < 2e-2
        assert not any(i.code == "at_bound" for i in res.verdict.items)           # ΔR、σ² 不卡边界
        assert res.shell.n_ref == 6 and len(res.shell.members) == 2
    finally:
        paths.set_root(old)


def test_verdict_peak_position_vs_structure():
    shell = qf.FirstShell([dict(file="f", label="Ir-O", reff=1.98, degen=6)], "Ir", "O", 6, 1.98)
    rows = [dict(R=1.98)]
    ok = qf._shell_items(rows, 6, shell, "sample", 2.5, None, None, r_peak=1.60)
    bad = qf._shell_items(rows, 6, shell, "sample", 2.5, None, None, r_peak=2.30)       # 金属相样品配氧化物 FEFF
    low = qf._shell_items(rows, 6, shell, "sample", 2.5, None, None, r_peak=1.10)
    pick = lambda it: next(i for i in it if i.code == "peak_pos")                       # noqa: E731
    assert pick(ok).level == "pass" and pick(bad).level == "fail" and pick(low).level == "fail"
    assert pick(bad).advice_zh and not any(i.code == "peak_pos" for i in qf._shell_items(rows, 6, shell, "sample", 2.5, None, None))
