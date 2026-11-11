"""阶段 2 代码审查发现的问题的回归测试（.prj 参比组、同一样品多吸收边、BOM、旧样品名、列文本提示、inspect 模板）。"""
import shutil
from pathlib import Path

import pandas as pd
import pytest

from xafsmith import paths, pipeline as pl, schema

DEMO = Path(__file__).resolve().parents[1] / "data" / "demo_project"


@pytest.fixture
def proj(tmp_path):
    dst = tmp_path / "p"
    shutil.copytree(DEMO, dst, ignore=shutil.ignore_patterns("output"))
    old = paths.ROOT
    paths.set_root(dst)
    yield dst
    paths.set_root(old)


def _meta_rows(proj):
    return pd.read_csv(proj / "data" / "meta.csv", dtype=str, encoding="utf-8-sig").fillna("")


def test_ref_row_picks_reference_group_of_prj(proj):
    m = _meta_rows(proj)
    prj = m[m.file.str.endswith(".prj")]
    assert len(prj) > 1, "演示项目的 .prj 应含多组"
    f = prj.file.iloc[0]
    m.loc[m.file == f, "role"] = "standard"
    target = prj.index[-1]                                   # 把最后一组设为参比
    m.loc[target, "role"] = "reference"
    m.to_csv(proj / "data" / "meta.csv", index=False, encoding="utf-8-sig")
    assert pl.ref_row(f)["group"] == m.loc[target, "group"]


def test_two_reference_groups_in_one_file_is_error(proj):
    m = _meta_rows(proj)
    f = m[m.file.str.endswith(".prj")].file.iloc[0]
    m.loc[m.file == f, "role"] = "reference"
    m.to_csv(proj / "data" / "meta.csv", index=False, encoding="utf-8-sig")
    with pytest.raises(ValueError):
        pl.ref_row(f)
    rep = schema.validate(structures=False)
    assert any(lv == "错误" and "role=reference 的组" in msg for lv, _at, msg in rep.items)


def test_k_limits_keyed_by_sample_and_edge():
    cfg = {"edges": {"Ir_L3": {"element": "Ir", "edge": "L3", "elements_in_sample": ["Ir"], "ft": {"kmax": 12}},
                     "Ta_L3": {"element": "Ta", "edge": "L3", "elements_in_sample": ["Ta"], "ft": {"kmax": 12}}}}
    meta = pd.DataFrame([dict(file="a", sample="S", edge_key="Ir_L3", use="1", emax="12000"),
                         dict(file="b", sample="S", edge_key="Ta_L3", use="1", emax="10300")])
    kl = schema.k_limits(cfg, meta)
    assert set(kl) == {("S", "Ir_L3"), ("S", "Ta_L3")}
    assert kl[("S", "Ir_L3")][0] > kl[("S", "Ta_L3")][0]
    rep = schema.Report()
    schema.check_krange(rep, cfg, meta, kl)
    assert all("Ir_L3" not in at for _lv, at, _m in rep.items)     # Ir 数据到 12000 eV，kmax=12 不越界
    assert any("Ta_L3" in at for _lv, at, _m in rep.items)         # Ta 数据只到 k≈10.6


def test_bom_json_accepted_by_pipeline(proj):
    cfgp = proj / "xafsmith.json"
    cfgp.write_text(cfgp.read_text(encoding="utf-8-sig"), encoding="utf-8-sig")       # 记事本保存会加 BOM
    assert "edges" in pl.load_config()


def test_legacy_sample_name_with_suffix_is_kept(proj, tmp_path):
    raw = proj / "data" / "raw" / "b2"
    raw.mkdir(parents=True)
    src = proj / "data" / "raw" / "public" / "cu_metal_rt.xdi"            # 公开数据（可被自动识别的 XDI）
    for nm in ("Cufoil.xdi", "Cufoil_2.xdi"):
        shutil.copy(src, raw / nm)
    # 旧版本登记过 Cufoil.xdi，样品名带扩展名
    m = _meta_rows(proj)
    old = dict.fromkeys(m.columns, "")
    old.update(file="data/raw/b2/Cufoil.xdi", sample="Cufoil.xdi", edge_key="Cu_K", mode="trans", role="reference",
               use="1", batch="b2", ref_file="data/raw/b2/Cufoil.xdi", format="xdi")
    pd.concat([m, pd.DataFrame([old])]).to_csv(proj / "data" / "meta.csv", index=False, encoding="utf-8-sig")
    pl.scan_raw()
    m2 = _meta_rows(proj)
    new = m2[m2.file == "data/raw/b2/Cufoil_2.xdi"]
    assert len(new) == 1, "Cufoil_2.xdi 应被自动登记"
    assert new["sample"].iloc[0] == "Cufoil.xdi"               # 并入旧样品名，而不是另起 “Cufoil”


def test_unrecognised_column_text_is_reported(proj):
    raw = proj / "data" / "raw" / "b3"
    raw.mkdir(parents=True)
    rows = "\n".join(f"{8900 + i} {1e5} {5e4}" for i in range(40))
    (raw / "weird.dat").write_text("# a b c\n" + rows + "\n", encoding="utf-8")       # 列名无法识别
    pl.scan_raw()
    assert any("weird.dat" in f and "列映射向导" in why for f, why in pl.scan_raw.skipped)
