"""E18：methods_text.py（论文“方法”段落生成）的单元测试。
项目 = 演示项目处理过一遍 + 保存了一个 Cu 拟合（conftest 的 fitted_proj）。数值期望来自项目自己的配置 / 记录，
或是快照（E18 时代码的输出）；中英文段落都必须含参数值与软件名，且不出现 "None" / "nan"。"""
import json

import pytest

from xafsmith import __version__, methods_text as mt, paths


def _bad(txt):
    return [w for w in ("None", "nan", "NaN") if w in txt]


def test_small_helpers():
    assert mt._fmt_list(["a", "b", "a", ""]) == "a、b"
    assert mt._fmt_list([1, 2], "; ") == "1; 2"
    assert mt._dash("3-17") == "3–17"
    assert mt._rng([3.0, 17.0]) == "3–17" and mt._rng([2.04, 2.0401]) == "2" and mt._rng([]) == ""
    assert mt._rng([float("nan")]) == ""
    assert mt._mode_txt(["trans", "fluo"], "zh") == "透射、荧光"
    assert mt._mode_txt(["trans", "fluo"], "en") == "transmission and fluorescence"
    assert mt._mode_txt(["weird"], "en") == "weird"


def test_collect_facts(fitted_proj):
    f = mt.collect()
    assert [e["key"] for e in f["edges"]] == ["Cu_K", "Fe_K", "Ni_K", "Pt_L3"]          # 快照：演示项目的四个吸收边
    cu = f["edges"][0]
    assert (cu["element"], cu["edge"], cu["modes"]) == ("Cu", "K", ["trans"]) and cu["scans"] == "1"
    assert cu["e_table"] == pytest.approx(8979.0, abs=1.0)
    assert list(f["fits"]["model"]) == ["cu_one"] and f["fits"].iloc[0]["feff"] == "feff6"
    assert f["fits"].iloc[0]["nvarys"] == 4 and f["fits"].iloc[0]["R"] == "1.4-3.0"
    assert set(f["versions"]) == {"larch", "xraydb", "lmfit", "xafsmith"} and f["versions"]["xafsmith"] == __version__


def test_collect_sample_filter(fitted_proj):
    f = mt.collect(samples=["Fe_foil"])
    assert [e["key"] for e in f["edges"]] == ["Fe_K"] and f["fits"].empty
    f2 = mt.collect(samples=["cu_metal_rt"])
    assert [e["key"] for e in f2["edges"]] == ["Cu_K"] and len(f2["fits"]) == 1


def test_build_both_languages_have_values_and_software(fitted_proj):
    r = mt.build()
    f = r["facts"]
    cu = f["edges"][0]
    for lang in ("zh", "en"):
        txt = r[lang]
        assert "XAFSmith" in txt and __version__ in txt and "AUTOBK" in txt and "FEFF6" in txt
        assert "Larch" in txt and f["versions"]["larch"] in txt
        assert f"{cu['e_table']}" in txt                      # 表值
        assert "N_idp" in txt and "15.3" in txt               # 独立点数（快照）
        assert "Rbkg = 1.0" in txt and "dk = 1.0" in txt      # 默认处理参数
        assert not _bad(txt), _bad(txt)
    assert "Cu K 边" in r["zh"] and "Cu K-edge" in r["en"]
    assert "3–17" in r["zh"] and "3–17" in r["en"]            # 拟合 k 范围
    assert "【光源】" in r["zh"] and "[facility]" in r["en"]    # 未填仪器信息：方括号占位


def test_build_instrument_from_config(fitted_proj):
    cfg = json.loads(paths.CONFIG.read_text(encoding="utf-8-sig"))
    cfg["instrument"] = {"facility": "TESTLIGHT", "beamline": "BL-9", "monochromator": "Si(111)", "detection": "ion chambers"}
    paths.CONFIG.write_text(json.dumps(cfg, ensure_ascii=False), encoding="utf-8")
    r = mt.build()
    for lang in ("zh", "en"):
        assert all(w in r[lang] for w in ("TESTLIGHT", "BL-9", "Si(111)", "ion chambers"))
    assert "【光源】" not in r["zh"] and "[facility]" not in r["en"]


def test_build_without_fits_has_no_fit_paragraph(fitted_proj):
    r = mt.build(fits_csv=fitted_proj / "does_not_exist.csv")
    assert "EXAFS 拟合" not in r["zh"] and "N_idp" not in r["en"]
    assert "XAFSmith" in r["zh"] and not _bad(r["zh"] + r["en"])


def test_build_empty_project(tmp_path):
    old = paths.ROOT
    paths.set_root(tmp_path)
    try:
        r = mt.build()
    finally:
        paths.set_root(old)
    assert r["zh"] == "（项目中还没有登记的数据）" and r["en"].startswith("(No registered data")


def test_restraint_items_and_feff_code(fitted_proj):
    cu = json.loads((paths.MODELS / "cu_one.json").read_text(encoding="utf-8"))
    m = dict(cu, name="cu_r", restraints=[{"expr": "amp", "value": 0.9, "sigma": 0.05}])
    (paths.MODELS / "cu_r.json").write_text(json.dumps(m), encoding="utf-8")
    assert mt._restraint_items(["cu_r", "cu_r", "cu_one", "missing"]) == [("amp", 0.9, 0.05)]
    assert mt._restraint_items(["cu_one"]) == []
    assert mt._feff_code("cu_one") == "feff6" and mt._feff_code("no_such_model") == "feff6"


def test_save_writes_markdown_with_both_languages(fitted_proj, tmp_path):
    p, r = mt.save(out_dir=tmp_path / "out")
    assert p.name == "方法段落.md" and p.parent == tmp_path / "out"
    txt = p.read_text(encoding="utf-8")
    assert "## 中文" in txt and "## English" in txt and r["zh"] in txt and r["en"] in txt
    assert "Newville" in txt
