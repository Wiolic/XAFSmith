"""E18：si_text.py（Supporting Information 的 EXAFS 拟合方法文本与参数表）的单元测试。
项目 = conftest 的 fitted_proj（演示项目 + 一个已保存的 Cu 拟合 cu_one）。数值期望为快照（E18 时代码的输出）或来自项目记录。"""

import pandas as pd
import pytest

from xafsmith import __version__, paths, si_text as si


def test_fit_keys_and_load_fits(fitted_proj):
    d = si.load_fits()
    assert len(d) == 1 and d.iloc[0]["model"] == "cu_one"
    assert si.fit_keys() == ["cu_metal_rt|cu_one"]
    assert si.fit_keys(d) == ["cu_metal_rt|cu_one"]


def test_load_fits_keeps_only_last_saved_block(fitted_proj):
    d = pd.read_csv(paths.FITS_CSV, encoding="utf-8-sig")
    old = d.copy()
    old["rfactor"] = 0.5                                    # 同一（样品, 模型）更早保存的一组
    other = d.copy()
    other["model"] = "other_model"                          # 中间插入另一个模型的记录，把两组隔开
    pd.concat([old, other, d], ignore_index=True).to_csv(paths.FITS_CSV, index=False, encoding="utf-8-sig")
    out = si.load_fits()
    mine = out[out["model"] == "cu_one"]
    assert len(mine) == 1 and float(mine.iloc[0]["rfactor"]) != 0.5 and len(out) == 2


def test_no_fits_file(tmp_path):
    old = paths.ROOT
    paths.set_root(tmp_path)
    try:
        assert si.load_fits().empty and si.fit_keys() == []
        r = si.build()
    finally:
        paths.set_root(old)
    assert r["zh"] == "" and r["en"] == "" and r["table"].empty


def test_table_columns_and_snapshot(fitted_proj):
    t = si.table()
    assert list(t.columns) == ["Sample", "Model", "Path", "N", "R (Å)", "σ² (Å²)", "ΔE0 (eV)", "R-factor", "χ²ν", "N_idp / N_var"]
    assert len(t) == 1
    r = t.iloc[0]
    assert (r["Sample"], r["Model"], r["Path"], r["N"]) == ("cu_metal_rt", "cu_one", "Cu–Cu", "12.0")      # 快照
    assert r["R (Å)"].startswith("2.54") and r["R (Å)"].endswith(")")       # 2.542(3)：带不确定度的写法
    assert r["N_idp / N_var"] == "15.3 / 4" and r["R-factor"] == "0.0027"
    assert si.table(["no|such"]).empty


@pytest.mark.parametrize("lang", ["zh", "en"])
def test_build_text_has_values_and_software(fitted_proj, lang):
    r = si.build()
    txt = r[lang]
    assert "Larch" in txt and "XAFSmith" in txt and __version__ in txt and "FEFF6" in txt
    assert "15.3" in txt and "3–17" in txt and "S[n]" in txt
    assert "None" not in txt and "nan" not in txt
    assert len(r["table"]) == 1
    assert ("Cu K-edge" if lang == "en" else "Cu K 边") in txt


def test_build_empty_keys(fitted_proj):
    r = si.build(["no|such"])
    assert r["zh"] == "" and r["en"] == "" and r["table"].empty


def test_fmt():
    assert si._fmt(None) == "—" and si._fmt(float("nan")) == "—"
    assert si._fmt(2.0) == "2.000" and si._fmt(2.0, 0.0) == "2.000"
    assert si._fmt(1.23456, 0.0012) == "1.235(1)"
    assert si._fmt(1.0, 0.5) == "1.000 ± 0.500"
    assert si._fmt(4.37, 0.3, 1) == "4.4(3)"


def test_eval_and_prop_err():
    assert si._eval("2*a + sqrt(4)", {"a": 3}) == pytest.approx(8.0)
    assert si._eval("a +", {"a": 1}) is None and si._eval("__import__('os')", {}) is None
    params = {"a": (2.0, 0.1), "b": (3.0, 0.2), "c": (1.0, None)}
    assert si._prop_err("2*a", params) == pytest.approx(0.2)
    assert si._prop_err("a + b", params) == pytest.approx((0.1 ** 2 + 0.2 ** 2) ** 0.5)
    assert si._prop_err("c*5", params) is None                # c 没有误差
    assert si._prop_err("zzz", params) is None


def test_spec():
    m = {"params": {"a": 1.5, "b": {"value": 2.0, "vary": False}, "c": {"value": 1.0}, "d": "a*2", "e": {"expr": "a+1"}}}
    assert si._spec(m, "a") == ("free", 1.5, None)
    assert si._spec(m, "b") == ("fixed", 2.0, None)
    assert si._spec(m, "c") == ("free", 1.0, None)
    assert si._spec(m, "d") == ("expr", None, "a*2") and si._spec(m, "e") == ("expr", None, "a+1")
    assert si._spec(m, "zz") is None and si._spec(None, "a") is None


def test_kw_and_path_text():
    assert "k²-weighted" in si._kw_txt(2, True) and "was fitted" in si._kw_txt(2, True)
    assert "simultaneously" in si._kw_txt([1, 3], True) and "同时拟合" in si._kw_txt([1, 3], False)
    model = {"params": {"amp": {"value": 0.9, "vary": False}, "ss": {"value": 0.003, "vary": True}}}
    mp = {"label": "Cu-Cu", "N": "12", "deltar": "dr", "sigma2": "ss"}
    en = si._path_txt(mp, model, True)
    assert en.startswith("Cu–Cu (") and "N fixed at 12" in en and "σ² = ss" in en
    assert "N 固定为 12" in si._path_txt(mp, model, False)
    assert "crystallographic" in si._path_txt({"label": "A"}, model, True)


def test_model_json_lookup(fitted_proj):
    assert si._model_json("cu_one")["name"] == "cu_one"
    assert si._model_json("cu_one@something")["name"] == "cu_one"          # “模型@样品”兼容
    assert si._model_json("nope") is None


def test_table_markdown_and_tsv():
    t = pd.DataFrame([
        {"Sample": "s1", "Model": "m", "Path": "Cu–Cu", "N": "12.0", "R-factor": "0.0027", "χ²ν": "9.7", "N_idp / N_var": "15.3 / 4"},
        {"Sample": "s1", "Model": "m", "Path": "Cu–O", "N": "2.0", "R-factor": "0.0027", "χ²ν": "9.7", "N_idp / N_var": "15.3 / 4"},
        {"Sample": "s2", "Model": "m", "Path": "Cu–Cu", "N": "11.0", "R-factor": "0.0030", "χ²ν": "5.0", "N_idp / N_var": "15.3 / 4"},
    ])
    md = si.table_markdown(t).split("\n")
    assert md[0] == "| Sample | Path | N | R-factor | χ²ν | N_idp / N_var |" and md[1] == "|---|---|---|---|---|---|"
    assert md[2].startswith("| s1 | Cu–Cu |") and md[3].startswith("|  | Cu–O |") and md[3].endswith("|  |  |  |")   # 同一样品后续行不重复整体指标
    assert md[4].startswith("| s2 |")
    tsv = si.table_tsv(t).split("\n")
    assert tsv[0] == "Sample\tPath\tN\tR-factor\tχ²ν\tN_idp / N_var" and tsv[2].split("\t")[1] == "Cu–O" and len(tsv) == 4
    empty = pd.DataFrame()
    assert si.table_markdown(empty) == "" and si.table_tsv(empty) == ""


def test_save_writes_markdown_and_csv(fitted_proj, tmp_path):
    p, r = si.save(out_dir=tmp_path / "si")
    txt = p.read_text(encoding="utf-8")
    assert p.name == "SI_EXAFS拟合方法.md" and "# EXAFS fitting (Supporting Information)" in txt and "# EXAFS 拟合（补充材料）" in txt
    assert r["en"] in txt and r["zh"] in txt
    t = pd.read_csv(tmp_path / "si" / "SI_EXAFS拟合参数表.csv", encoding="utf-8-sig")
    assert list(t.columns) == list(r["table"].columns) and len(t) == 1
