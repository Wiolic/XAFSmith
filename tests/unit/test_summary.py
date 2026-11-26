"""E18：summary.py（Excel 工作簿 + HTML 汇总报告）的单元测试。
项目 = conftest 的 fitted_proj（演示项目处理过一遍 + 一个已保存的 Cu 拟合）。数值 / 形状期望为快照（E18 时代码的输出）或结构性质。"""
import re

import numpy as np
import pandas as pd

from xafsmith import about, paths, summary


def test_safe():
    assert summary.safe("a b/c") == "a_b_c"
    assert summary.safe("ab-1.2_x") == "ab-1.2_x"
    assert summary.safe(12) == "12"


def test_read_csv_missing_and_present(tmp_path):
    assert summary._read_csv(tmp_path / "no.csv").empty
    p = tmp_path / "a.csv"
    pd.DataFrame({"x": [1, 2]}).to_csv(p, index=False, encoding="utf-8-sig")
    assert list(summary._read_csv(p)["x"]) == [1, 2]


def test_collect_sheets(fitted_proj):
    sheets = summary.collect()
    assert list(sheets) == ["样品", "校准", "处理结果", "EXAFS拟合", "拟合概要", "处理参数"]    # 快照：处理 + 一个拟合之后的工作表
    s = sheets["样品"]
    assert len(s) == 11 and "cu_metal_rt" in set(s["sample"]) and {"吸收边", "模式", "角色", "扫描数", "使用"} <= set(s.columns)
    assert int(s.loc[s["sample"] == "cu_rt01", "使用"].iloc[0]) == 0           # meta.csv 里 use=0 的样品
    cal = sheets["校准"]
    assert len(cal) == 4 and {"参比", "E0_meas", "E_table", "ΔE"} <= set(cal.columns)
    cu = cal[cal["吸收边"] == "Cu_K"].iloc[0]
    assert abs(cu["E_table"] - 8979.0) < 1.0 and abs(cu["ΔE"]) < 5            # Cu 箔：E0 对齐到表值，ΔE 为几 eV 以内
    assert len(sheets["处理结果"]) == 7
    assert len(sheets["EXAFS拟合"]) == 1 and len(sheets["拟合概要"]) == 1
    assert len(sheets["处理参数"]) == 4 and {"吸收边", "E_table"} <= set(sheets["处理参数"].columns)


def test_collect_empty_project(tmp_path):
    old = paths.ROOT
    paths.set_root(tmp_path)
    try:
        assert summary.collect() == {}
    finally:
        paths.set_root(old)


def test_fit_overview():
    fits = pd.DataFrame([
        dict(sample="s1", model="m", path="A", rfactor=0.01, chi2_reduced=2.0, n_idp=10.0, nvarys=3, dE0=1.0, S02=0.9, N=6, R=2.0, sigma2=0.005),
        dict(sample="s1", model="m", path="B", rfactor=0.01, chi2_reduced=2.0, n_idp=10.0, nvarys=3, dE0=1.0, S02=0.9, N=3, R=2.5, sigma2=0.007),
        dict(sample="s1", model="m", path="B", rfactor=0.02, chi2_reduced=3.0, n_idp=11.0, nvarys=4, dE0=2.0, S02=0.8, N=4, R=2.6, sigma2=0.008),
        dict(sample="s2", model="m", path="A", rfactor=0.03, chi2_reduced=4.0, n_idp=12.0, nvarys=5, dE0=3.0, S02=0.7, N=5, R=2.1, sigma2=0.009),
    ])
    o = summary.fit_overview(fits)
    assert list(o["样品"]) == ["s1", "s2"] and list(o["模型"]) == ["m", "m"]
    r = o.iloc[0]
    assert (r["R因子"], r["N_idp"], r["变量数"], r["ΔE0"], r["S02"]) == (0.02, 11.0, 4, 2.0, 0.8)    # 同一路径重复时取最后一行
    assert (r["A: N"], r["A: R"], r["A: σ²"]) == (6, 2.0, 0.005) and (r["B: N"], r["B: R"]) == (4, 2.6)
    assert np.isnan(o.iloc[1]["B: N"]) and o.iloc[1]["A: N"] == 5


def test_table_html_formats_numbers_and_truncates():
    df = pd.DataFrame({"a": np.arange(400.0) / 3, "b": ["x"] * 400})
    t = summary._table(df, maxrows=300)
    assert t.count("<tr") == 301 and "0.3333" in t and "0.33333333" not in t
    assert "NaN" not in summary._table(pd.DataFrame({"a": [1.0, np.nan]}))


def test_notice_contains_disclaimer_and_citation():
    n = summary._notice()
    assert "<div class=w>" in n and "<div class=c>" in n and "<li>" in n
    assert about.DISCLAIMER_EN.split(" ")[0] in n and "XAFSmith" in n


def test_html_sections_and_figures(fitted_proj):
    sheets = {"样品": pd.DataFrame({"sample": ["a"]}), "LCF": pd.DataFrame({"x": [1.0]})}
    h = summary._html("My <proj>", sheets, ["spec.png", "cu_fit.png", "lcf_a.png"])
    assert "My &lt;proj&gt; —— XAFSmith 汇总" in h and "<h2>样品</h2>" in h and "<h2>LCF</h2>" in h
    assert "<h2>校准</h2>" not in h
    assert [m for m in re.findall(r"<h3>(.*?)</h3>", h)] == ["谱图", "拟合", "LCF"]
    assert "figs/spec.png" in h and "figs/cu_fit.png" in h and "figs/lcf_a.png" in h
    assert "<h2>图</h2>" not in summary._html("t", sheets, [])


def test_build_writes_workbook_report_and_figs(fitted_proj):
    paths.FIGS.mkdir(parents=True, exist_ok=True)
    (paths.FIGS / "demo.png").write_bytes(b"\x89PNG\r\n")
    out = summary.build(title="E18 demo")
    assert out.parent == paths.REPORTS and out.name.startswith("汇总_")
    assert sorted(p.name for p in out.iterdir()) == ["figs", "汇总.xlsx", "汇总报告.html"]
    assert (out / "figs" / "demo.png").read_bytes() == b"\x89PNG\r\n"
    xl = pd.ExcelFile(out / "汇总.xlsx")
    assert xl.sheet_names == ["说明与引用", "样品", "校准", "处理结果", "EXAFS拟合", "拟合概要", "处理参数"]
    assert len(xl.parse("样品")) == 11
    h = (out / "汇总报告.html").read_text(encoding="utf-8")
    assert "E18 demo —— XAFSmith 汇总" in h and "figs/demo.png" in h and "cu_metal_rt" in h


def test_build_without_figs(fitted_proj):
    paths.FIGS.mkdir(parents=True, exist_ok=True)
    (paths.FIGS / "demo.png").write_bytes(b"\x89PNG\r\n")
    out = summary.build(include_figs=False)
    assert not (out / "figs").exists() and "figs/demo.png" not in (out / "汇总报告.html").read_text(encoding="utf-8")


def test_build_empty_project_says_so(tmp_path):
    old = paths.ROOT
    paths.set_root(tmp_path)
    try:
        out = summary.build()
        sheets = pd.ExcelFile(out / "汇总.xlsx").sheet_names
    finally:
        paths.set_root(old)
    assert sheets == ["说明与引用", "说明"]
    assert (out / "汇总报告.html").exists() and out.parent == tmp_path / "output" / "reports"
