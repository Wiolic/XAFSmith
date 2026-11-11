import json
import shutil
from pathlib import Path

import pytest

from xafsmith import paths, schema

DEMO = Path(__file__).resolve().parents[1] / "data" / "demo_project"


@pytest.fixture
def proj(tmp_path):
    dst = tmp_path / "p"
    shutil.copytree(DEMO, dst, ignore=shutil.ignore_patterns("output"))
    old = paths.ROOT
    paths.set_root(dst)
    yield dst
    paths.set_root(old)


def msgs(rep):
    return [f"{a} {b} {c}" for a, b, c in rep.items]


def test_demo_has_no_errors(proj):
    assert schema.validate(structures=False).n_err == 0


def test_bad_config_json_reports_line(proj):
    (proj / "xafsmith.json").write_text('{\n  "edges": {,\n}', encoding="utf-8")
    rep = schema.validate(structures=False)
    assert any("第 2 行" in m for m in msgs(rep))


def test_meta_duplicate_and_empty_cell(proj):
    f = proj / "data" / "meta.csv"
    lines = f.read_text(encoding="utf-8-sig").splitlines()
    lines.append(lines[1])                                  # 重复登记
    f.write_text("\n".join(lines) + "\n", encoding="utf-8-sig")
    rep = schema.validate(structures=False)
    assert any("重复登记" in m for m in msgs(rep))


def test_model_json_errors(proj):
    (proj / "models").mkdir(exist_ok=True)
    (proj / "models" / "bad.json").write_text("{\n 'a': 1}", encoding="utf-8")
    (proj / "models" / "rng.json").write_text(json.dumps(
        dict(name="x", sample="s", kmin=10, kmax=3, rmin=1, rmax=3, kweight=2, params={}, paths=[{}])), encoding="utf-8")
    ms = msgs(schema.validate(structures=False))
    assert any("bad.json" in m and "第 2 行" in m for m in ms)
    assert any("kmin 应小于 kmax" in m for m in ms)
    assert any("paths[0]" in m for m in ms)


def _model(**kw):
    m = dict(name="x", sample="s", kmin=3, kmax=12, rmin=1, rmax=3, kweight=[1, 2, 3], window="hanning",
             params={"s02": 0.8}, paths=[{"file": "output/feff/x/feff0001.dat"}])
    m.update(kw)
    return m


def test_model_kweight_list_and_window(proj):
    (proj / "models").mkdir(exist_ok=True)
    (proj / "models" / "ok.json").write_text(json.dumps(_model()), encoding="utf-8-sig")       # BOM 也能读
    (proj / "models" / "win.json").write_text(json.dumps(_model(window="hamming2")), encoding="utf-8")
    ms = msgs(schema.validate(structures=False))
    assert not any("ok.json" in m and m.startswith("错误") for m in ms)
    assert any("win.json" in m and "窗函数" in m for m in ms)


def test_nidp_rules():
    assert schema.count_varied({"a": 1.0, "b": "a*2", "c": {"value": 1, "vary": False},
                                "d": {"value": 1}, "e": {"expr": "a"}}) == 2
    assert abs(schema.n_idp(3, 12, 1, 3) - 2 * 9 * 2 / 3.141592653589793) < 1e-9


def test_model_underdetermined_is_error(proj):
    (proj / "models").mkdir(exist_ok=True)
    many = {f"p{i}": 0.1 for i in range(6)}                 # N_idp = 2·2·0.5/π ≈ 0.64
    (proj / "models" / "u.json").write_text(json.dumps(_model(kmin=3, kmax=5, rmin=1, rmax=1.5, params=many)),
                                            encoding="utf-8")
    rep = schema.validate(structures=False)
    assert any(lv == "错误" and "u.json" in at and "欠定" in m for lv, at, m in rep.items)


def test_config_ranges(proj):
    cfg = json.loads((proj / "xafsmith.json").read_text(encoding="utf-8-sig"))
    ek = next(iter(cfg["edges"]))
    cfg["edges"][ek]["norm"]["pre1"], cfg["edges"][ek]["norm"]["pre2"] = -30, -150
    cfg["edges"][ek]["ft"]["kweight"] = [1, 2, 3]           # 列表合法
    cfg["edges"][ek]["bkg"]["rbkg"] = 0
    (proj / "xafsmith.json").write_text(json.dumps(cfg), encoding="utf-8")
    rep = schema.validate(structures=False)
    errs = [f"{at} {m}" for lv, at, m in rep.items if lv == "错误"]
    assert any("pre1 应小于 pre2" in e for e in errs)
    assert any("rbkg" in e for e in errs)
    assert not any("kweight" in e for e in errs)


def test_k_limit_ignores_short_scans_and_uses_sample_elements():
    import pandas as pd
    cfg = {"edges": {"Ir_L3": {"element": "Ir", "edge": "L3", "elements_in_sample": ["Ir", "Ta"],
                               "ft": {"kmax": 12.0}}},
           "overrides": {"B": {"elements_in_sample": ["Ir", "O"]}}}
    rows = [("A", "12016.8"), ("A", "11231.0"),             # 第二条是短扫描（不参与合并）
            ("B", "12016.8")]
    meta = pd.DataFrame([dict(file=f"f{i}", sample=s, edge_key="Ir_L3", use="1", emax=e)
                         for i, (s, e) in enumerate(rows)])
    kl = schema.k_limits(cfg, meta)
    assert kl[("A", "Ir_L3")][2] == "Ta" and 10.5 < kl[("A", "Ir_L3")][0] < 11.1  # Ta L1 ≈ 11.07 Å⁻¹ − 0.3
    assert kl[("B", "Ir_L3")][2] is None and kl[("B", "Ir_L3")][0] > 12            # B 不含 Ta：只受数据末端限制


def test_time_gap_accepts_all_meta_time_formats():
    from xafsmith.calib import time_gap_hours
    assert abs(time_gap_hours("2026/5/1 9:00:00", "2026/5/1 10:30:00") - 1.5) < 1e-9          # BSRF
    assert abs(time_gap_hours("2001-06-26T21:00:00", "2001-06-26T22:30:00") - 1.5) < 1e-9     # XDI
    assert abs(time_gap_hours("Tue Jun 26 21:00:00 2001", "Tue Jun 26 22:30:00 2001") - 1.5) < 1e-9   # .xmu
    assert time_gap_hours("乱写", "2026/5/1 9:00:00") is None
