"""联合快速拟合：公共窗口、联合模型结构、两层判定、趋势表合并、CLI、schema。演示项目（Cu；同一条谱登记成多个样品名）。"""
import copy
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pandas as pd
import pytest

from xafsmith import fit_exafs as fx, paths, quickfit as qf, schema, trend as tr

TESTS = Path(__file__).resolve().parents[1]
DEMO = TESTS / "data" / "demo_project"
FEFF_CU = TESTS / "data" / "benchmark" / "feffcu01.dat"
FEFF = "output/feff/Cu_CuK"
SAMPLES = ["cu_a", "cu_b", "cu_c"]


def noisy_copy(src, dst, seed):
    """复制 xdi，给 itrans 列乘以很小的确定性噪声（读入时 μ 由 i0、itrans 算出）：larch 以数据内容给数据集编号，两条完全相同的谱会让路径参数互相覆盖，
    真实样品不会出现完全相同的谱。"""
    import numpy as np
    rng = np.random.default_rng(seed)
    out = []
    for line in src.read_text(encoding="utf-8").splitlines():
        if line.startswith("#") or not line.strip():
            out.append(line)
            continue
        e, i0, it, mu = line.split()
        out.append(f"{e}  {i0}  {float(it) * (1 + rng.normal(0, 3e-4)):.6f}  {mu}")
    dst.write_text("\n".join(out) + "\n", encoding="utf-8")


def make_project(root):
    shutil.copytree(DEMO, root)
    f = root / FEFF
    f.mkdir(parents=True)
    shutil.copyfile(FEFF_CU, f / "feff0001.dat")
    mf = root / "data" / "meta.csv"
    meta = pd.read_csv(mf, dtype=str, encoding="utf-8-sig").fillna("")
    src = meta[meta["sample"] == "cu_metal_rt"].iloc[0]
    rows = []
    for i, s in enumerate(SAMPLES):
        r = src.copy()
        r["sample"], r["role"], r["file"] = s, "standard", f"data/raw/public/{s}.xdi"
        r["time"] = f"2001-06-26T2{i}:27:31"
        noisy_copy(root / src["file"], root / r["file"], seed=i + 1)
        rows.append(r)
    meta = pd.concat([meta, pd.DataFrame(rows)], ignore_index=True)
    meta["seq"] = ""
    for i, s in enumerate(SAMPLES):
        meta.loc[meta["sample"] == s, "seq"] = str(10 * (i + 1))
    meta.to_csv(mf, index=False, encoding="utf-8-sig")


@pytest.fixture(scope="module")
def proj(tmp_path_factory):
    d = tmp_path_factory.mktemp("qfj") / "demo_project"
    make_project(d)
    old = paths.ROOT
    paths.set_root(d)
    yield d
    paths.set_root(old)


@pytest.fixture(scope="module")
def joint(proj):
    m = qf.build_joint_model(["cu_a", "cu_b"], FEFF, 3.0, s02=0.9)
    return m, qf.run(m)


# ---------------------------------------------------------------- 公共 k 窗
def W(kmin, kmax, dk=1.0, window="hanning"):
    return dict(kmin=kmin, kmax=kmax, dk=dk, window=window)


def test_common_k_window_is_the_intersection():
    w = qf.common_k_window({"a": W(3, 12), "b": W(3.5, 11, 2, "kaiser"), "c": W(2.5, 13)})
    assert (w["kmin"], w["kmax"]) == (3.5, 11) and (w["dk"], w["window"]) == (1.0, "hanning")      # dk / 窗取第一个


def test_common_k_window_too_short_raises_bilingual():
    with pytest.raises(qf.QuickFitError) as e:
        qf.common_k_window({"a": W(3, 12), "b": W(8, 14)})
    assert "不足 6" in str(e.value) and "below 6" in str(e.value) and "b: 8–14" in str(e.value)
    assert qf.common_k_window({"a": W(3, 9), "b": W(3, 12)})["kmax"] == 9               # 恰好 6 Å⁻¹ 可以


# ---------------------------------------------------------------- 联合模型结构
def test_joint_model_structure(proj, joint):
    m, _ = joint
    json.dumps(m)
    assert "sample" not in m and "paths" not in m and fx.is_multi(m)
    assert [(d["id"], d["sample"]) for d in m["datasets"]] == [("cu_a", "cu_a"), ("cu_b", "cu_b")]
    P = m["params"]
    assert P["s02"] == dict(value=0.9, vary=False) and P["e0"] == dict(value=0.0, vary=True, min=-15.0, max=15.0)
    for i in ("cu_a", "cu_b"):
        assert P[f"n1_{i}"] == dict(value=12.0, vary=True, min=0.0, max=24.0)
        assert P[f"dr1_{i}"] == dict(value=0.0, vary=True, min=-0.5, max=0.5)
        assert P[f"ss1_{i}"] == dict(value=0.003, vary=True, min=0.0, max=0.05)
    assert set(P) == {"s02", "e0", "n1_cu_a", "dr1_cu_a", "ss1_cu_a", "n1_cu_b", "dr1_cu_b", "ss1_cu_b"}       # 只有一个 e0
    for d in m["datasets"]:
        p = d["paths"][0]
        assert p["e0"] == "e0" and p["s02"] == "s02" and p["deltar"] == f"dr1_{d['id']}" and p["sigma2"] == f"ss1_{d['id']}"
        assert p["N"] == f"n1_{d['id']}*12.0/12.0" and p["file"] == f"{FEFF}/feff0001.dat"
    assert m["s02_source"] == dict(manual=True, value=0.9) and m["kweight"] == [1, 2, 3] and m["rmax"] == 3.0
    q = m["quickfit"]
    assert q["mode"] == "joint" and q["shell"]["n_ref"] == 12 and q["shell"]["scatterer"] == "Cu"
    assert q["shell"]["members"][0]["file"] == f"{FEFF}/feff0001.dat" and set(q["windows"]) == {"cu_a", "cu_b"}


def test_joint_common_rmin_is_the_largest_automatic_rmin(proj):
    cfg = json.loads((proj / "xafsmith.json").read_text(encoding="utf-8-sig"))
    ids = SAMPLES
    single = [qf.build_model(s, FEFF, 3.0, "standard")["rmin"] for s in ids]          # 同一条谱，窗口相同 → 自动 Rmin 相同
    m = qf.build_joint_model(ids, FEFF, 3.0, s02=0.9)
    assert m["rmin"] == max(single) and len(m["datasets"]) == 3
    assert (m["kmin"], m["kmax"]) == (cfg["edges"]["Cu_K"]["ft"]["kmin"], cfg["edges"]["Cu_K"]["ft"]["kmax"])
    assert qf.build_joint_model(ids[:2], FEFF, 3.0, s02=0.9, rmin=1.3)["rmin"] == 1.3          # 用户给的覆盖


def test_joint_rmin_uses_the_largest_of_different_samples(proj, monkeypatch):
    seen = iter([1.1, 1.4, 0.9])
    monkeypatch.setattr(qf, "auto_rmin", lambda *a: (next(seen), 1.6))
    assert qf.build_joint_model(SAMPLES, FEFF, 3.0, s02=0.9)["rmin"] == 1.4


def test_joint_input_errors(proj):
    with pytest.raises(qf.QuickFitError, match="至少 2 个"):
        qf.build_joint_model(["cu_a"], FEFF, 3.0, s02=0.9)                           # 1 个样品不走联合
    with pytest.raises(qf.QuickFitError, match="S0²"):
        qf.build_joint_model(["cu_a", "cu_b"], FEFF, 3.0)
    with pytest.raises(qf.QuickFitError, match="没有可用的样品"):
        qf.build_joint_model(["cu_a", "nope"], FEFF, 3.0, s02=0.9)
    with pytest.raises(qf.QuickFitError, match="k 窗"):
        qf.build_joint_model(["cu_a", "cu_b"], FEFF, 3.0, s02=0.9, rmin=1.0, krange=dict(kmin=3, kmax=8))
    with pytest.raises(qf.QuickFitError, match="吸收"):
        qf.build_joint_model(["cu_a", "fe2o3_rt1"], FEFF, 3.0, s02=0.9)               # 吸收边与 FEFF 不符
    with pytest.raises(qf.QuickFitError, match="太窄"):
        qf.build_joint_model(["cu_a", "cu_b"], FEFF, 3.0, s02=0.9, rmin=2.9)


def test_joint_window_intersection_from_overrides(proj, tmp_path):
    d = tmp_path / "ov"
    shutil.copytree(proj, d)
    cfg = json.loads((d / "xafsmith.json").read_text(encoding="utf-8-sig"))
    cfg["overrides"] = {"cu_b": {"ft": dict(kmin=3.5, kmax=11.0, dk=2, window="kaiser")}}
    (d / "xafsmith.json").write_text(json.dumps(cfg), encoding="utf-8")
    old = paths.ROOT
    paths.set_root(d)
    try:
        m = qf.build_joint_model(["cu_a", "cu_b"], FEFF, 3.0, s02=0.9, rmin=1.2)
        assert (m["kmin"], m["kmax"], m["dk"], m["window"]) == (3.5, 11.0, 1.0, "hanning")
        assert m["quickfit"]["windows"]["cu_b"] == dict(kmin=3.5, kmax=11.0, dk=2, window="kaiser")
        cfg["overrides"] = {"cu_b": {"ft": dict(kmin=9.0, kmax=13.0)}}              # 交集 9–12 = 3 Å⁻¹
        (d / "xafsmith.json").write_text(json.dumps(cfg), encoding="utf-8")
        with pytest.raises(qf.QuickFitError, match="不足 6"):
            qf.build_joint_model(["cu_a", "cu_b"], FEFF, 3.0, s02=0.9, rmin=1.2)
    finally:
        paths.set_root(old)


def test_single_models_carry_the_quickfit_key(proj):
    s = qf.build_model("cu_a", FEFF, 3.0, "standard", rmin=1.0)
    assert s["quickfit"]["mode"] == "standard" and "windows" not in s["quickfit"] and s["quickfit"]["shell"]["r_cif"] == pytest.approx(2.5478, abs=1e-3)
    assert qf.build_model("cu_a", FEFF, 3.0, "sample", s02=0.9, rmin=1.0)["quickfit"]["mode"] == "sample"
    assert qf.shell_of_model(s).n_ref == 12 and not isinstance(qf.run(s), qf.JointResult)        # 单样品仍走单样品


# ---------------------------------------------------------------- 联合拟合运行
def test_joint_run_shapes(joint):
    m, r = joint
    assert isinstance(r, qf.JointResult) and [x.sample for x in r.samples] == ["cu_a", "cu_b"]
    f = r.fit                                                                       # 与 services.run_model 同形
    assert {"model", "summ", "result", "curves", "report", "time", "multi"} <= set(f) and f["multi"] is True
    assert set(f["curves"]) == {"cu_a", "cu_b"} and f["summ"]["multi"] and f["summ"]["n_datasets"] == 2
    assert r.e0 == f["summ"]["params"]["e0"]["value"] and r.nvarys == 7 and r.s02 == 0.9
    assert r.window["rmin"] == m["rmin"] and r.window["kweight"] == [1, 2, 3]
    for x in r.samples:
        assert x.mode == "sample" and x.s02_err is None and x.n_err is not None and x.verdict is r.verdict.samples[x.sample]
        assert x.e0 == r.e0 and x.nvarys == 7 and 0 < x.sigma2 < 0.03 and abs(x.r - r.shell.r_cif) < 0.15
    assert fx.dataset_view(f["summ"], "cu_a")["rfactor"] == r.samples[0].rfactor


def test_joint_of_near_identical_samples_matches_single_fits(proj, joint):
    """几乎相同的两条谱：联合拟合里每个样品的 N、R、σ² 应与同窗口的单样品拟合接近（共享 ΔE0 的影响很小）。"""
    m, r = joint
    for x in r.samples:
        s = qf.build_model(x.sample, FEFF, 3.0, "sample", s02=0.9, rmin=m["rmin"])
        assert (s["kmin"], s["kmax"], s["rmin"]) == (m["kmin"], m["kmax"], m["rmin"])
        one = qf.run(s)
        assert x.n == pytest.approx(one.n, rel=0.03) and x.r == pytest.approx(one.r, abs=2e-3)
        assert x.sigma2 == pytest.approx(one.sigma2, abs=5e-4) and r.e0 == pytest.approx(one.e0, abs=0.5)


def test_joint_with_given_groups(proj):
    import copy as cp
    from xafsmith import pipeline as pl
    gs = {i: cp.deepcopy(pl.build_sample(i)[0]) for i in ("cu_a", "cu_b")}
    m = qf.build_joint_model(["cu_a", "cu_b"], FEFF, 3.0, s02=0.9, rmin=1.2, groups=gs)
    r = qf.run(m, gs)
    assert 0 < r.samples[0].n < 24 and r.samples[0].n == pytest.approx(r.samples[1].n, rel=0.1)


def test_format_joint_text(joint):
    _, r = joint
    t = qf.format_joint_text(r)
    assert "公共窗口" in t and "整批判定" in t and "-- cu_a" in t and "-- cu_b" in t
    assert "Common window" in qf.format_joint_text(r, "en") and "Batch verdict" in qf.format_joint_text(r, "en")


# ---------------------------------------------------------------- 两层判定
SH = qf.FirstShell([dict(file="f.dat", label="A-B", reff=2.0, degen=6.0)], "A", "B", 6.0, 2.0)


def fake_joint(ids=("s1", "s2"), nv=7, nidp=20.0, rf=0.01, dr=None, n=None, ss=None, nerr=None, rfs=None, e0=2.0, e0_err=0.5):
    dr, n, ss, nerr, rfs = dr or {}, n or {}, ss or {}, nerr or {}, rfs or {}
    P = dict(s02=dict(value=0.9, stderr=None, vary=False, expr=None),
             e0=dict(value=e0, stderr=e0_err, vary=True, expr=None))
    paths_, dsets = [], []
    for i in ids:
        nm = qf.joint_param_names(i)
        P[nm["n"]] = dict(value=n.get(i, 6.0), stderr=nerr.get(i, 0.5), vary=True, expr=None)
        P[nm["dr"]] = dict(value=dr.get(i, 0.0), stderr=0.01, vary=True, expr=None)
        P[nm["ss"]] = dict(value=ss.get(i, 0.005), stderr=0.001, vary=True, expr=None)
        paths_.append(dict(path="p", R=2.0 + dr.get(i, 0.0), sigma2=ss.get(i, 0.005), deltar=dr.get(i, 0.0), dataset=i))
        dsets.append(dict(id=i, sample=i, rfactor=rfs.get(i, 0.01), n_idp=nidp / len(ids)))
    summ = dict(multi=True, rfactor=rf, nvarys=nv, n_idp=nidp, params=P, paths=paths_, datasets=dsets, sample="+".join(ids))
    corr = {k: None for k in P}
    rg = dict(e0=(-15.0, 15.0), dr=(-0.5, 0.5), ss=(0.0, 0.05), n=(0.0, 24.0))
    bounds = {k: dict(min=rg[k.split("_")[0].rstrip("1")][0], max=rg[k.split("_")[0].rstrip("1")][1]) for k in P if k != "s02"}
    return dict(summ=summ, model=dict(kweight=[1, 2, 3], params=bounds), result=SimpleNamespace(
        params={k: SimpleNamespace(vary=v["vary"], correl=corr[k]) for k, v in P.items()}), robust=None, multi=True)


PEAKS = {"s1": (1.0, 0.1), "s2": (1.0, 0.1)}


def jv(fit, peaks=PEAKS, **kw):
    return qf.verdict_joint(fit, SH, 2.5, peaks, **kw)


def test_joint_verdict_all_pass():
    v = jv(fake_joint(), s02_source=dict(model="m", value=0.9, stderr=0.04))
    assert v.ok and not v.failed and not v.failed_samples and not v.notes and "整批可信" in v.summary("zh")
    assert {i.code for i in v.items} >= {"rfactor", "nvarys", "e0"} and set(v.samples) == {"s1", "s2"}
    assert {i.code for i in v.samples["s1"].items} >= {"rfactor", "r_cif", "n_ratio", "rmax_leak", "sigma2_ok", "dr"}


def test_joint_verdict_batch_rules():
    v = jv(fake_joint(rf=0.08))
    assert not v.ok and [i.code for i in v.failed] == ["rfactor"] and not v.failed_samples          # 总 R 因子：整批
    v = jv(fake_joint(nv=25, nidp=20.0))                                                             # Stern：变量数 > Σ N_idp
    assert [i.code for i in v.failed] == ["nvarys"] and "Σ" not in v.failed[0].zh and "20.0" in v.failed[0].zh
    v = jv(fake_joint(nv=12, nidp=20.0))                                                             # > N_idp/2 只提示
    assert v.ok and "nvarys_low_info" in {i.code for i in v.notes}
    v = jv(fake_joint(e0=14.5))
    assert "e0" in {i.code for i in v.failed}
    v = jv(fake_joint(e0=3.0, e0_err=None))
    assert "err_none" in {i.code for i in v.failed}                                                  # 共享 ΔE0 的误差
    v = jv(fake_joint(e0=-15.0))
    assert "at_bound" in {i.code for i in v.failed}


def test_joint_verdict_sample_rules_name_the_sample():
    cases = [(dict(dr={"s2": 0.2}), "r_cif"), (dict(n={"s1": 10.0}), "n_ratio"), (dict(rfs={"s2": 0.09}), "rfactor"),
             (dict(ss={"s1": 0.04}), "sigma2_big"), (dict(nerr={"s2": 8.0}), "err_big"), (dict(ss={"s2": -0.001}), "sigma2_neg")]
    for kw, code in cases:
        v = jv(fake_joint(**kw))
        bad = "s2" if "s2" in str(kw) else "s1"
        other = "s1" if bad == "s2" else "s2"
        assert not v.ok and v.failed_samples == [bad] and not v.failed, (kw, v.failed_samples)
        assert code in {i.code for i in v.samples[bad].failed} and v.samples[other].ok
        assert bad in v.summary("zh") and bad in v.summary("en")
    v = jv(fake_joint(), peaks={"s1": (1.0, 0.1), "s2": (1.0, 0.5)})                                 # Rmax 处残余
    assert v.failed_samples == ["s2"] and [i.code for i in v.samples["s2"].failed] == ["rmax_leak"]
    v = jv(fake_joint(), peaks={})                                                                   # 没给峰高 → 不做窗口检查
    assert "rmax_leak" not in {i.code for i in v.samples["s1"].items}


def test_joint_verdict_notes_do_not_fail():
    sh = qf.FirstShell(SH.members, "A", "B", 6.0, 2.0, [("C", 2.1)])
    wins = {"s1": W(3, 12), "s2": W(3, 12, 2, "kaiser")}
    v = qf.verdict_joint(fake_joint(), sh, 2.5, PEAKS, dict(manual=True, value=0.9), wins)
    assert v.ok and {"manual_s02", "other_elements", "window_mismatch"} <= {i.code for i in v.notes}
    v = qf.verdict_joint(fake_joint(), SH, 2.5, PEAKS, None, {"s1": W(3, 12), "s2": W(3, 12)})
    assert "window_mismatch" not in {i.code for i in v.notes}


def test_joint_verdict_ids_with_odd_characters():
    ids = ("IrTa_1.3V", "IrTa-2")
    v = qf.verdict_joint(fake_joint(ids=ids, n={"IrTa-2": 10.0}), SH, 2.5, {i: (1.0, 0.1) for i in ids})
    assert v.failed_samples == ["IrTa-2"] and qf.joint_param_names("IrTa_1.3V")["n"] == "n1_IrTa_1_3V"


# ---------------------------------------------------------------- 趋势表合并
def test_trend_merges_first_shell_for_quickfit_models(proj, joint):
    m, r = joint
    meta = pd.read_csv(proj / "data" / "meta.csv", dtype=str, encoding="utf-8-sig").fillna("")
    t = r.trend(meta, pd.DataFrame(dict(sample=["cu_a", "cu_b"], E0=[8979.0, 8980.0])))
    P = r.fit["summ"]["params"]
    assert list(t.columns) == tr.COLUMNS and len(t) == 2 and list(t["dataset"]) == ["cu_a", "cu_b"]
    assert set(t["path"]) == {"Cu–Cu first shell"} and set(t["seq_source"]) == {"seq"} and list(t["seq"]) == [10.0, 20.0]
    for (_, row), i in zip(t.iterrows(), ("cu_a", "cu_b")):
        nm = qf.joint_param_names(i)
        assert row["N"] == P[nm["n"]]["value"] and row["N_err"] == P[nm["n"]]["stderr"] > 0
        assert row["R"] == r.shell.r_cif + P[nm["dr"]]["value"] and row["R_err"] == P[nm["dr"]]["stderr"]
        assert row["sigma2"] == P[nm["ss"]]["value"] and row["sigma2_err"] == P[nm["ss"]]["stderr"]
        assert row["dE0"] == P["e0"]["value"] and row["dE0_err"] == P["e0"]["stderr"]
    assert list(t["E0_edge"]) == [8979.0, 8980.0] and list(t["shared_dE0"]) == [True, True]
    assert not t[["shared_N", "shared_R", "shared_sigma2"]].any().any() and t.attrs["n_composite"] == []
    # 趋势 CSV 能写
    csv = tr.save_trend(t, "qfj_test", m["name"], "test")
    assert pd.read_csv(csv, encoding="utf-8-sig").shape[0] == 2


def test_trend_without_quickfit_key_is_the_generic_table(proj, joint):
    m, r = joint
    plain = {k: v for k, v in m.items() if k != "quickfit"}
    t = tr.trend_table(r.fit["summ"], plain)
    summ = r.fit["summ"]
    assert len(t) == len(summ["paths"]) and list(t["path"]) == [p["path"] for p in summ["paths"]]        # 逐路径一行，标签仍是 FEFF 路径名
    for (_, row), pr in zip(t.iterrows(), summ["paths"]):
        assert (row["N"], row["R"], row["sigma2"], row["R_err"], row["sigma2_err"], row["dE0"]) == \
               (pr["N"], pr["R"], pr["sigma2"], pr["R_err"], pr["sigma2_err"], pr["e0"])
    assert t["N_err"].notna().all()                                       # N 是复合表达式 n1*12/12，参考 S0² 固定 → amp_err/S0²


def test_trend_falls_back_when_the_quickfit_model_was_edited(proj, joint):
    m, r = joint
    edited = copy.deepcopy(m)
    edited["datasets"][0]["paths"].append(dict(edited["datasets"][0]["paths"][0], label="extra"))          # 路径数与第一壳层不符
    t = tr.trend_table(r.fit["summ"], edited)
    assert set(t["path"]) != {"Cu–Cu first shell"}
    broken = copy.deepcopy(m)
    broken["quickfit"] = dict(mode="joint", shell="oops")
    assert set(tr.trend_table(r.fit["summ"], broken)["path"]) != {"Cu–Cu first shell"}


# ---------------------------------------------------------------- schema
def _validate_model(proj, model):
    paths.MODELS.mkdir(exist_ok=True)
    (paths.MODELS / "qfj.json").write_text(json.dumps(model), encoding="utf-8")
    try:
        return [f"{a} {b} {c}" for a, b, c in schema.validate(structures=False).items if "qfj.json" in b]
    finally:
        (paths.MODELS / "qfj.json").unlink()


def test_schema_accepts_quickfit_models_and_checks_types(proj, joint):
    m, _ = joint
    assert _validate_model(proj, m) == []
    assert _validate_model(proj, qf.build_model("cu_a", FEFF, 3.0, "standard", rmin=1.0)) == []
    for mutate, text in [(lambda q: q.update(mode="duo"), "quickfit.mode"),
                         (lambda q: q.update(shell=[1]), "quickfit.shell"),
                         (lambda q: q["shell"].update(n_ref="six"), "n_ref"),
                         (lambda q: q["shell"].update(members=[]), "members"),
                         (lambda q: q["shell"]["members"][0].update(reff="x"), "reff"),
                         (lambda q: q.update(windows={"a": {"kmin": 3}}), "windows")]:
        bad = copy.deepcopy(m)
        mutate(bad["quickfit"])
        assert any(text in x and x.startswith("错误") for x in _validate_model(proj, bad)), text
    bad = copy.deepcopy(m)
    bad["quickfit"] = "x"
    assert any("quickfit" in x for x in _validate_model(proj, bad))


# ---------------------------------------------------------------- CLI
def _cli(proj, *args):
    env = dict(os.environ, PYTHONIOENCODING="utf-8", XAFSMITH_NO_RECENT="1")
    return subprocess.run([sys.executable, "-m", "xafsmith.cli", "--project", str(proj), *args],
                          capture_output=True, text=True, encoding="utf-8", env=env, timeout=600)


def test_cli_joint_prints_and_does_not_save(proj):
    out = proj / "output"
    before = {p for p in out.rglob("*") if p.is_file()}
    r = _cli(proj, "quickfit", "cu_a", "cu_b", "cu_c", "--feff", FEFF, "--rmax", "3.0", "--s02", "0.9")
    assert r.returncode == 0, r.stderr[-2000:]
    o = r.stdout
    assert "联合快速拟合：3 个样品" in o and "公共窗口" in o and "整批判定" in o and "趋势表" in o and "未加 --save" in o
    assert "Cu–Cu first shell" in o and o.count("-- cu_") == 3 and "没有标样依据" in o
    assert {p for p in out.rglob("*") if p.is_file()} == before


def test_cli_standard_with_several_samples_is_an_error(proj):
    r = _cli(proj, "quickfit", "cu_a", "cu_b", "--feff", FEFF, "--rmax", "3.0", "--standard")
    assert r.returncode != 0 and "标样模式只能选一个样品" in r.stderr


def test_cli_single_sample_is_not_joint(proj):
    r = _cli(proj, "quickfit", "cu_a", "--feff", FEFF, "--rmax", "3.0", "--s02", "0.9", "--rmin", "1.3")
    assert r.returncode == 0 and "联合" not in r.stdout and "== cu_a（样品）" in r.stdout


def test_cli_joint_errors(proj):
    r = _cli(proj, "quickfit", "cu_a", "cu_b", "--feff", FEFF, "--rmax", "3.0", "--s02-from", "nothing_here")
    assert r.returncode != 0 and "nothing_here" in r.stderr
    r = _cli(proj, "quickfit", "cu_a", "nope", "--feff", FEFF, "--rmax", "3.0", "--s02", "0.9")
    assert r.returncode != 0 and "nope" in r.stderr


def test_cli_joint_save_writes_model_trend_and_records(proj):
    r = _cli(proj, "quickfit", "cu_a", "cu_b", "--feff", FEFF, "--rmax", "3.0", "--s02", "0.9", "--save", "--name", "QFJ_cli")
    assert r.returncode == 0, r.stderr[-2000:]
    m = json.loads((proj / "models" / "QFJ_cli.json").read_text(encoding="utf-8"))
    assert m["quickfit"]["mode"] == "joint" and len(m["datasets"]) == 2
    t = pd.read_csv(proj / "output" / "fits" / "QFJ_cli_trend.csv", encoding="utf-8-sig")
    assert list(t.columns) == tr.COLUMNS and len(t) == 2 and set(t["path"]) == {"Cu–Cu first shell"}
    assert (proj / "output" / "fits" / "QFJ_cli_trend.params.json").is_file()
    df = pd.read_csv(proj / "output" / "fits" / "exafs_fits.csv", encoding="utf-8-sig")
    assert "QFJ_cli" in set(df["model"])
    assert (proj / "output" / "figs" / "QFJ_cli_cu_a_fit.png").is_file()
    again = _cli(proj, "quickfit", "cu_a", "cu_b", "--feff", FEFF, "--rmax", "3.0", "--s02", "0.9", "--save", "--name", "QFJ_cli")
    assert again.returncode != 0 and "已存在" in again.stderr
    r = _cli(proj, "trend", "QFJ_cli", "--nosave")
    assert r.returncode == 0 and "Cu–Cu first shell" in r.stdout, r.stderr[-1500:]
