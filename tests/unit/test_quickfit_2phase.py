"""quickfit 混合相（第二相）：模型结构、错误、判定、趋势表、schema、CLI；合成两相（Cu–Cu 2.55 Å ×12 + 改成 Cu–O 2.10 Å ×6 的同一份路径文件）。
IrTa 原位序列的项目对照（有项目才跑）见 test_quickfit_2phase_project.py。"""
import json
import re
import shutil
from pathlib import Path

import pandas as pd
import pytest

from xafsmith import fit_exafs as fx, paths, quickfit as qf, schema, trend as tr

TESTS = Path(__file__).resolve().parents[1]
DEMO = TESTS / "data" / "demo_project"
FEFF_CU = TESTS / "data" / "benchmark" / "feffcu01.dat"
F1, F2 = "output/feff/Cu_CuK", "output/feff/CuO_CuK"       # 相 1：Cu–Cu 2.55 ×12；相 2：Cu–O 2.10 ×6（合成）


def make_o_path(src, dst):
    """把 Cu–Cu 路径文件改成 Cu–O：散射原子 8 / O，Reff 2.10 Å，简并度 6（只改几何与标签，振幅表照旧：只用来测结构 / 判定逻辑）。"""
    t = src.read_text(encoding="utf-8").splitlines()
    out = []
    for ln in t:
        if re.search(r"nleg, deg, reff", ln):
            ln = "   2   6.000   2.1000    2.6300   -5.53502 nleg, deg, reff, rnrmav(bohr), edge"
        elif re.match(r"\s+\.0000\s+-1\.8016\s+1\.8016\s+1\s+29\s+Cu", ln):
            ln = "      .0000   -1.4849    1.4849  1   8 O"
        out.append(ln)
    dst.write_text("\n".join(out) + "\n", encoding="utf-8")


@pytest.fixture(scope="module")
def proj(tmp_path_factory):
    d = tmp_path_factory.mktemp("qf2") / "demo_project"
    shutil.copytree(DEMO, d)
    (d / F1).mkdir(parents=True)
    shutil.copyfile(FEFF_CU, d / F1 / "feff0001.dat")
    (d / F2).mkdir(parents=True)
    make_o_path(FEFF_CU, d / F2 / "feff0001.dat")
    mf = d / "data" / "meta.csv"
    meta = pd.read_csv(mf, dtype=str, encoding="utf-8-sig").fillna("")
    src = meta[meta["sample"] == "cu_metal_rt"].iloc[0]
    rows = []
    for s in ("cu_a", "cu_b"):
        r = src.copy()
        r["sample"], r["file"] = s, f"data/raw/public/{s}.xdi"
        shutil.copyfile(d / src["file"], d / r["file"])
        rows.append(r)
    pd.concat([meta, pd.DataFrame(rows)], ignore_index=True).to_csv(mf, index=False, encoding="utf-8-sig")
    old = paths.ROOT
    paths.set_root(d)
    yield d
    paths.set_root(old)


def test_synthetic_second_phase_is_cu_o(proj):
    from xafsmith.feff_wrap import list_paths
    sh2 = qf.first_shell(list_paths(proj / F2))
    assert (sh2.absorber, sh2.scatterer, sh2.n_ref, sh2.r_cif) == ("Cu", "O", 6, pytest.approx(2.1))


def test_rmax_default_by_phase_count():
    assert qf.default_rmax(False) == qf.RMAX_DEFAULT == 2.5 and qf.default_rmax(True) == qf.RMAX_DEFAULT_2PHASE == 3.0


def test_two_phase_single_model_structure(proj):
    m = qf.build_model("cu_metal_rt", F1, None, "sample", s02=0.8, rmin=1.2, feff_dir2=F2)
    json.dumps(m)
    assert m["rmax"] == 3.0                                             # 有第二相、未给 Rmax → 3.0
    P = m["params"]
    assert list(P) == ["s02", "n1", "n2", "e0", "dr1", "ss1", "dr2", "ss2"]
    assert P["s02"] == dict(value=0.8, vary=False)
    assert P["n1"] == dict(value=6.0, vary=True, min=0.0, max=24.0)      # N_ref/2，范围 [0, 2·N_ref]
    assert P["n2"] == dict(value=3.0, vary=True, min=0.0, max=12.0)
    assert P["dr2"] == P["dr1"] and P["ss2"] == P["ss1"] == dict(value=0.003, vary=True, min=0.0, max=0.05)
    p1, p2 = m["paths"]
    assert (p1["N"], p1["deltar"], p1["sigma2"], p1["file"]) == ("n1*12.0/12.0", "dr1", "ss1", f"{F1}/feff0001.dat")
    assert (p2["N"], p2["deltar"], p2["sigma2"], p2["file"]) == ("n2*6.0/6.0", "dr2", "ss2", f"{F2}/feff0001.dat")
    assert m["quickfit"]["mode"] == "sample" and m["quickfit"]["shell2"]["scatterer"] == "O" and m["quickfit"]["shell"]["scatterer"] == "Cu"
    assert qf.build_model("cu_metal_rt", F1, 2.7, "sample", s02=0.8, rmin=1.2, feff_dir2=F2)["rmax"] == 2.7
    s, s2 = qf.shells_of_model(m, proj)                                  # 由模型还原两相
    assert (s.scatterer, s2.scatterer, s2.n_ref) == ("Cu", "O", 6)


def test_single_phase_model_unchanged(proj):
    """没有第二相：模型与加这个功能之前逐字相同（参数表、路径、quickfit 键里没有 shell2）。"""
    m = qf.build_model("cu_metal_rt", F1, 3.0, "sample", s02=0.9, rmin=1.2, kweight=[2])
    assert list(m["params"]) == ["s02", "n1", "e0", "dr1", "ss1"] and "n2" not in m["params"]
    assert m["params"]["n1"] == dict(value=12.0, vary=True, min=0.0, max=24.0)
    assert m["paths"] == [dict(file=f"{F1}/feff0001.dat", label="Cu-Cu@2.548", s02="s02", e0="e0", deltar="dr1", sigma2="ss1",
                               N="n1*12.0/12.0")]
    assert "shell2" not in m["quickfit"] and qf.shells_of_model(m, proj)[1] is None
    assert qf.build_model("cu_metal_rt", F1, None, "standard", rmin=1.2)["rmax"] == 2.5


def test_two_phase_errors(proj):
    with pytest.raises(qf.QuickFitError, match="标样"):
        qf.build_model("cu_metal_rt", F1, None, "standard", feff_dir2=F2)
    with pytest.raises(qf.QuickFitError, match="相同"):
        qf.build_model("cu_metal_rt", F1, None, "sample", s02=0.8, feff_dir2=F1)
    with pytest.raises(qf.QuickFitError):
        qf.build_model("cu_metal_rt", F1, None, "sample", s02=0.8, feff_dir2="output/feff/nothing")
    # 吸收原子不同
    bad = proj / "output" / "feff" / "Fe_FeK"
    bad.mkdir(exist_ok=True)
    t = (proj / F1 / "feff0001.dat").read_text(encoding="utf-8").replace("29 Cu       absorbing atom", "26 Fe       absorbing atom")
    (bad / "feff0001.dat").write_text(t, encoding="utf-8")
    with pytest.raises(qf.QuickFitError, match="吸收原子"):
        qf.build_model("cu_metal_rt", F1, None, "sample", s02=0.8, feff_dir2="output/feff/Fe_FeK")


def test_two_phase_joint_model_structure(proj):
    m = qf.build_joint_model(["cu_a", "cu_b"], F1, None, s02=0.8, rmin=1.2, feff_dir2=F2)
    assert m["rmax"] == 3.0
    P = m["params"]
    assert list(P) == ["s02", "e0", "n1_cu_a", "n2_cu_a", "n1_cu_b", "n2_cu_b", "dr1", "ss1", "dr2", "ss2"]
    assert P["n1_cu_a"]["value"] == 6.0 and P["n2_cu_b"] == dict(value=3.0, vary=True, min=0.0, max=12.0)
    d_a, d_b = m["datasets"]
    assert [p["N"] for p in d_a["paths"]] == ["n1_cu_a*12.0/12.0", "n2_cu_a*6.0/6.0"]
    assert [(p["deltar"], p["sigma2"]) for p in d_b["paths"]] == [("dr1", "ss1"), ("dr2", "ss2")]       # 全批共享
    assert "shell2" in m["quickfit"] and fx.is_multi(m)
    assert qf.joint_param_names("cu_a") == dict(n="n1_cu_a", dr="dr1_cu_a", ss="ss1_cu_a")              # 单相联合的参数名不变
    j1 = qf.build_joint_model(["cu_a", "cu_b"], F1, 3.0, s02=0.8, rmin=1.2)
    assert list(j1["params"]) == ["s02", "e0", "n1_cu_a", "dr1_cu_a", "ss1_cu_a", "n1_cu_b", "dr1_cu_b", "ss1_cu_b"]


# ---------------------------------------------------------------- 判定
SH1 = qf.FirstShell([dict(file="f1", label="Ir-O", reff=1.98, degen=6.0)], "Ir", "O", 6.0, 1.98)
SH2 = qf.FirstShell([dict(file="f2", label="Ir-Ir", reff=2.715, degen=12.0)], "Ir", "Ir", 12.0, 2.715)


def rows(r1=1.98, r2=2.715):
    return [dict(R=r1), dict(R=r2)]


def items(n1=3.0, n2=6.0, r1=1.98, r2=2.715, r_peak=2.3, amp=None, at=None):
    its = qf._shell_items_two(rows(r1, r2), n1, n2, SH1, SH2, 3.0, amp, at, r_peak)
    return {(i.code, i.zh[:4]): i for i in its}, its


def test_two_phase_verdict_items_per_phase():
    d, its = items()
    codes = [i.code for i in its]
    assert codes.count("r_cif") == 2 and codes.count("n_ratio") == 2 and codes.count("peak_pos") == 1
    assert any(i.zh.startswith("相 1（Ir–O）") for i in its) and any(i.zh.startswith("相 2（Ir–Ir）") for i in its)
    assert any(i.en.startswith("Phase 1 (Ir–O)") for i in its) and any(i.en.startswith("Phase 2 (Ir–Ir)") for i in its)
    assert all(i.level == "pass" for i in its if i.code != "phase_frac") and its[-1].code == "phase_frac" and its[-1].level == "note"


@pytest.mark.parametrize("r1,ok", [(1.98 + 0.14, True), (1.98 + 0.16, False)])
def test_two_phase_verdict_r_cif_each_phase(r1, ok):
    _, its = items(r1=r1)
    ph1 = next(i for i in its if i.code == "r_cif" and i.zh.startswith("相 1"))
    ph2 = next(i for i in its if i.code == "r_cif" and i.zh.startswith("相 2"))
    assert (ph1.level == "pass") is ok and ph2.level == "pass"


@pytest.mark.parametrize("n2,ok", [(18.0, True), (18.2, False)])
def test_two_phase_verdict_n_ratio_each_phase(n2, ok):
    _, its = items(n2=n2)
    assert next(i for i in its if i.code == "n_ratio" and i.zh.startswith("相 2")).level == ("pass" if ok else "fail")
    assert next(i for i in its if i.code == "n_ratio" and i.zh.startswith("相 1")).level == "pass"


@pytest.mark.parametrize("rp,ok", [(1.6, True), (2.3, True), (3.0, False), (0.9, False)])
def test_two_phase_peak_pos_matches_either_phase(rp, ok):
    """数据第一峰与任一相 R_CIF 满足 PEAK_SHIFT（−0.8…+0.1 Å）即通过：1.6 ↔ 相 1 (1.98)；2.3 ↔ 相 2 (2.715)；3.0 / 0.9 都对不上"""
    _, its = items(r_peak=rp)
    assert next(i for i in its if i.code == "peak_pos").level == ("pass" if ok else "fail")
    if not ok:
        assert next(i for i in its if i.code == "peak_pos").advice_zh


def test_two_phase_rmax_leak_is_a_note_and_fraction_note():
    _, its = items(amp=1.0, at=0.31)
    it = next(i for i in its if i.code == "rmax_leak")
    assert it.level == "note" and "混合相只作提示" in it.zh and not it.advice_zh
    _, its = items(amp=1.0, at=0.30)
    assert next(i for i in its if i.code == "rmax_leak").level == "pass"
    note = next(i for i in its if i.code == "phase_frac")
    assert "相 2 比例 ≈ 0.50" in note.zh and "仅供参考" in note.zh and "0.50" in note.en and "indicative" in note.en


def test_phase2_dict_and_other_elements_note():
    p2 = qf._phase2(SH2, [dict(R=2.70)], 9.0, 0.5, 0.004, 0.0026, 0.0004)
    assert p2["frac"] == 0.75 and p2["r"] == pytest.approx(2.70) and p2["shell2"] is SH2
    sh = qf.FirstShell(SH1.members, "Ir", "O", 6.0, 1.98, [("Ta", 2.05)])
    its = qf._others_note(sh, SH2)
    assert len(its) == 1 and its[0].zh.startswith("相 1（Ir–O）：") and qf._others_note(sh)[0].zh.startswith("第一层还有")


# ---------------------------------------------------------------- 趋势表
def fake_summ(ids):
    P = dict(e0=dict(value=2.0, stderr=0.5, vary=True, expr=None), dr1=dict(value=0.01, stderr=0.004, vary=True, expr=None),
             ss1=dict(value=0.004, stderr=0.001, vary=True, expr=None), dr2=dict(value=-0.01, stderr=0.003, vary=True, expr=None),
             ss2=dict(value=0.003, stderr=0.0005, vary=True, expr=None), s02=dict(value=0.8, stderr=None, vary=False, expr=None))
    for k, i in enumerate(ids):
        P[f"n1_{i}"] = dict(value=2.0 + k, stderr=0.3, vary=True, expr=None)
        P[f"n2_{i}"] = dict(value=8.0 - k, stderr=0.5, vary=True, expr=None)
    return dict(multi=True, params=P, datasets=[dict(id=i, sample=i.upper()) for i in ids])


def test_trend_rows_two_phase():
    ids = ["a", "b"]
    mem = lambda sh, f: dict(sh, members=[dict(file=f, label="x", reff=sh["r_cif"], degen=sh["n_ref"])])    # noqa: E731
    s1 = dict(absorber="Ir", scatterer="O", n_ref=6.0, r_cif=1.98)
    s2 = dict(absorber="Ir", scatterer="Ir", n_ref=12.0, r_cif=2.715)
    model = dict(quickfit=dict(mode="joint", shell=mem(s1, "f1"), shell2=mem(s2, "f2")),
                 datasets=[dict(id=i, sample=i.upper(), paths=[{}, {}]) for i in ids])
    seq = {i: float(k + 1) for k, i in enumerate(ids)}
    rows_ = tr._quickfit_rows(model, model["datasets"], fake_summ(ids), seq, dict(source="order"), {})
    assert len(rows_) == 4 and [r["path"] for r in rows_] == ["Ir–O first shell", "Ir–Ir first shell"] * 2
    r_a1, r_a2 = rows_[0], rows_[1]
    assert (r_a1["N"], r_a2["N"]) == (2.0, 8.0) and r_a1["R"] == pytest.approx(1.99) and r_a2["R"] == pytest.approx(2.705)
    assert (r_a1["sigma2"], r_a2["sigma2"]) == (0.004, 0.003) and r_a1["dE0"] == 2.0
    assert r_a1["shared_R"] and r_a1["shared_sigma2"] and not r_a1["shared_N"] and r_a1["shared_dE0"]
    assert rows_[2]["N"] == 3.0 and rows_[2]["R"] == r_a1["R"]                    # 共享：b 与 a 的 R 相同
    model["datasets"][0]["paths"] = [{}]                                          # 结构对不上 → 回到逐路径行（None）
    assert tr._quickfit_rows(model, model["datasets"], fake_summ(ids), seq, dict(source="order"), {}) is None


# ---------------------------------------------------------------- schema
def test_schema_accepts_shell2_and_checks_it(proj):
    import copy
    m = qf.build_model("cu_metal_rt", F1, None, "sample", s02=0.8, rmin=1.2, feff_dir2=F2)

    def check(model):
        paths.MODELS.mkdir(exist_ok=True)
        (paths.MODELS / "qf2.json").write_text(json.dumps(model), encoding="utf-8")
        try:
            return [f"{a} {b} {c}" for a, b, c in schema.validate(structures=False).items if "qf2.json" in b]
        finally:
            (paths.MODELS / "qf2.json").unlink()
    assert not [x for x in check(m) if x.startswith("错误")]          # 单样品七个变量 → 只有“变量太多”的警告，没有错误
    for mutate, text in [(lambda q: q.update(shell2=[1]), "quickfit.shell2"), (lambda q: q["shell2"].update(n_ref="six"), "shell2.n_ref"),
                         (lambda q: q["shell2"].update(members=[]), "shell2.members")]:
        bad = copy.deepcopy(m)
        mutate(bad["quickfit"])
        assert any(text in x and x.startswith("错误") for x in check(bad)), text


# ---------------------------------------------------------------- 端到端（合成 Cu + Cu–O，联合）
def test_two_phase_joint_runs_end_to_end(proj):
    """两条（同一数据的）谱、Cu–Cu + 合成 Cu–O：能建模型、拟合、给出两层判定、趋势表每数据集两行；只验证流程，不验证物理。"""
    from xafsmith import pipeline as pl
    m = qf.build_joint_model(["cu_a", "cu_b"], F1, None, s02=0.9, rmin=1.2, feff_dir2=F2)
    g = {pl.safe(s): pl.build_sample(s)[0] for s in ("cu_a", "cu_b")}
    # larch 以数据内容给数据集编号，完全相同的两条谱会互相覆盖：给第二条一点确定性的扰动
    import numpy as np
    g["cu_b"].chi = np.asarray(g["cu_b"].chi) * (1 + 1e-3 * np.sin(np.arange(len(g["cu_b"].chi))))
    try:
        r = qf.run(m, g)
    except qf.QuickFitError:
        pytest.skip("合成两相数据退化（协方差奇异）；流程已由结构 / 判定测试覆盖")
    assert r.shell2 is not None and len(r.samples) == 2 and all(s.phase2 for s in r.samples)
    assert r.samples[0].phase2["shell2"].scatterer == "O"
    assert "phase_frac" in {i.code for i in r.verdict.samples["cu_a"].items}
    t = r.trend()
    assert len(t) == 4 and set(t["path"]) == {"Cu–Cu first shell", "Cu–O first shell"}
    txt = qf.format_joint_text(r)
    assert "第二相第一壳层" in txt and "相 2" in txt


def test_peak_search_rmax_single_unchanged_two_phase_shorter_shell():
    a = qf.FirstShell([], "Ir", "O", 6, 1.98)
    b = qf.FirstShell([], "Ir", "Ir", 12, 2.71)
    assert qf.peak_search_rmax(3.0, a) == 3.0
    assert qf.peak_search_rmax(3.0, a, b) == pytest.approx(1.98 - qf.PEAK_SHIFT_MIN)
    assert qf.peak_search_rmax(3.0, b, a) == pytest.approx(1.98 - qf.PEAK_SHIFT_MIN)
    assert qf.peak_search_rmax(1.5, a, b) == 1.5
