"""G5：meta.csv ref_file = none（没有参比，有意不校准）。演示项目 Cu。"""
import shutil
from pathlib import Path

import pandas as pd
import pytest

from xafsmith import methods_text, paths, pipeline as pl, quickfit as qf, schema

TESTS = Path(__file__).resolve().parents[1]
DEMO = TESTS / "data" / "demo_project"
FEFF = "output/feff/Cu_CuK"


def _set_meta(d, **cols):
    f = d / "data" / "meta.csv"
    m = pd.read_csv(f, dtype=str, encoding="utf-8-sig").fillna("")
    m.loc[m["sample"] == "cu_rt01", "use"] = "1"
    for k, v in cols.items():
        m.loc[m["sample"] == "cu_rt01", k] = v
    m.to_csv(f, index=False, encoding="utf-8-sig")


@pytest.fixture
def proj(tmp_path):
    d = tmp_path / "p"
    shutil.copytree(DEMO, d)
    (d / FEFF).mkdir(parents=True)
    shutil.copyfile(TESTS / "data" / "benchmark" / "feffcu01.dat", d / FEFF / "feff0001.dat")
    old = paths.ROOT
    paths.set_root(d)
    yield d
    paths.set_root(old)


def test_none_runs_and_is_marked_uncalibrated(proj):
    _set_meta(proj, ref_file="None")                            # 大小写不敏感
    g, _ = pl.build_sample("cu_rt01")
    assert g.uncalibrated is True and g.calib_ref == "" and g.e_shift == 0.0
    ref, _ = pl.build_sample("cu_metal_rt")                      # 有参比的谱不受影响
    assert not ref.uncalibrated and ref.calib_ref.endswith("cu_metal_rt.xdi")
    from xafsmith.qt.state import calib_status
    assert calib_status(None, g, False)[0] == "✘ 未按参比校准"


def test_run_calib_skips_none(proj):
    _set_meta(proj, ref_file="none")
    res = pl.run_calib(pl.load_config(), pl.load_meta(), out=proj / "calib_test.json")
    assert all(k != "none" for k in res) and any("cu_metal_rt" in k for k in res)


def test_empty_ref_still_errors_with_new_text(proj):
    _set_meta(proj, ref_file="", batch="zzz")
    with pytest.raises(ValueError) as ei:
        pl.build_sample("cu_rt01")
    m = str(ei.value)
    assert "没有参比" in m and "ref_file 填 none" in m and "no reference" in m and "none" in m.split(" / ")[1]


def test_mixed_scans_rejected(proj):
    f = proj / "data" / "meta.csv"
    m = pd.read_csv(f, dtype=str, encoding="utf-8-sig").fillna("")
    row = m[m["sample"] == "cu_rt01"].iloc[0].copy()
    row["use"], row["ref_file"], row["file"] = "1", "none", "data/raw/public/cu_metal_rt.xdi"
    m = pd.concat([m, row.to_frame().T], ignore_index=True)       # 同一样品两条扫描：一条有参比、一条 none
    m.loc[m["sample"] == "cu_rt01", "use"] = "1"
    m.loc[(m["sample"] == "cu_rt01").to_numpy().nonzero()[0][0], "ref_file"] = "data/raw/public/cu_metal_rt.xdi"
    with pytest.raises(ValueError, match="none"):
        pl.build_sample("cu_rt01", meta=m)


def test_validate_accepts_none_and_rejects_empty(proj):
    _set_meta(proj, ref_file="none")
    assert schema.validate(structures=False).n_err == 0
    _set_meta(proj, ref_file="", batch="zzz")
    rep = schema.validate(structures=False)
    assert rep.n_err >= 1 and any("没有参比" in c for _a, _b, c in rep.items)


def test_quickfit_note_not_fail(proj):
    _set_meta(proj, ref_file="none")
    res = qf.run(qf.build_model("cu_rt01", str(proj / FEFF), 3.0, "standard"))
    codes = {i.code: i for i in res.verdict.items}
    assert codes["uncalibrated"].level == "note" and "未按参比校准" in codes["uncalibrated"].zh
    assert "R and N are not affected" in codes["uncalibrated"].en
    cal = qf.run(qf.build_model("cu_metal_rt", str(proj / FEFF), 3.0, "standard"))
    assert "uncalibrated" not in {i.code for i in cal.verdict.items}
    assert res.verdict.ok == (not res.verdict.failed)              # note 不影响可信与否


def test_quickfit_joint_note(proj):
    _set_meta(proj, ref_file="none")
    m = qf.build_joint_model(["cu_metal_rt", "cu_rt01"], str(proj / FEFF), 3.0, s02=0.9, s02_source=dict(manual=True, value=0.9))
    res = qf.run(m)
    it = [i for i in res.verdict.items if i.code == "uncalibrated"]
    assert len(it) == 1 and it[0].level == "note" and "cu_rt01" in it[0].zh and "cu_metal_rt" not in it[0].zh


def test_methods_text_says_no_calibration(proj):
    _set_meta(proj, ref_file="none")
    r = methods_text.build(["cu_rt01"])
    assert "未做能量校准（无参比）" in r["zh"] and "【ΔE】" not in r["zh"]
    assert "no energy calibration was made" in r["en"] and "[ΔE]" not in r["en"]
    r2 = methods_text.build(["cu_metal_rt"])                        # 有参比：原样
    assert "未做能量校准" not in r2["zh"] and "校准" in r2["zh"]
