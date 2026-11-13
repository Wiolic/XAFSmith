"""B4：多模型比较表 compare_models / `xafsmith compare` / `xafsmith ftest` 输出不变。

演示项目复制到 tmp_path；模型都是 cu_metal_rt 上的 Cu-Cu 单壳层，只改变量数、k 范围、软约束。
"""
import json
import shutil
from pathlib import Path

import pandas as pd
import pytest

from test_cli_fit_multi import CU1, _cli

TESTS = Path(__file__).resolve().parents[1]
DEMO = TESTS / "data" / "demo_project"

SMALL = dict(CU1, name="m_small", params=dict(CU1["params"], amp={"value": 1.0, "vary": False}))   # 3 个变量
BIG = dict(CU1, name="m_big")                                                                      # 4 个变量
BIG2 = dict(CU1, name="m_big2")                                                                    # 4 个变量（与 m_big 相同）
RANGE = dict(CU1, name="m_range", kmax=14)
RESTR = dict(CU1, name="m_restr", restraints=[dict(expr="amp", value=0.9, sigma=0.05)])
ALL = [SMALL, BIG, BIG2, RANGE, RESTR]


@pytest.fixture(scope="module")
def proj(tmp_path_factory):
    d = tmp_path_factory.mktemp("cmp") / "demo_project"
    shutil.copytree(DEMO, d)
    (d / "models").mkdir(exist_ok=True)
    for m in ALL:
        (d / "models" / f"{m['name']}.json").write_text(json.dumps(m), encoding="utf-8")
    return d


@pytest.fixture(scope="module")
def entries(proj):
    from xafsmith import paths
    from xafsmith.cli import _run_model
    old = paths.ROOT
    paths.set_root(proj)
    try:
        out = {}
        for m in ALL:
            model, _g, res, _d, summ = _run_model(m["name"])
            out[m["name"]] = dict(name=m["name"], model=model, result=res, summ=summ)
        yield out
    finally:
        paths.set_root(old)


def test_sorted_by_nvarys_and_vs(entries):
    from xafsmith import fit_exafs as fx
    df = fx.compare_models([entries["m_big"], entries["m_small"]])      # 输入顺序与变量数相反
    assert list(df["model"]) == ["m_small", "m_big"]
    assert df["vs"].isna().iloc[0] and df["vs"].iloc[1] == "m_small"
    assert df[["F", "p", "b", "dof"]].iloc[0].isna().all()
    assert list(df["nvarys"]) == [3, 4] and list(df["n_restraints"]) == [0, 0]
    assert list(df["samples"]) == ["cu_metal_rt"] * 2


def test_F_p_equal_hamilton(entries):
    from xafsmith import fit_exafs as fx
    df = fx.compare_models([entries["m_small"], entries["m_big"]])
    h = fx.hamilton_test(entries["m_small"]["result"], entries["m_big"]["result"])
    r = df.iloc[1]
    assert r["F"] == h["F"] and r["p"] == h["p"] and r["b"] == h["b"] and r["dof"] == h["dof"]
    assert r["note"] == h["note"]
    s = entries["m_big"]["summ"]
    assert r["rfactor"] == s["rfactor"] and r["chi2_reduced"] == s["chi2_reduced"] and r["n_idp"] == s["n_idp"]
    assert r["chi_square"] == entries["m_big"]["result"].chi_square


def test_blockers_range_and_restraints(entries):
    from xafsmith import fit_exafs as fx
    df = fx.compare_models([entries["m_small"], entries["m_range"]])
    assert pd.isna(df["F"].iloc[1]) and pd.isna(df["p"].iloc[1])
    assert "拟合范围不同" in df["note"].iloc[1]
    df = fx.compare_models([entries["m_small"], entries["m_restr"]])
    assert pd.isna(df["F"].iloc[1]) and "软约束不同" in df["note"].iloc[1]
    assert df["n_restraints"].iloc[1] == 1


def test_same_nvarys_no_ftest(entries):
    from xafsmith import fit_exafs as fx
    df = fx.compare_models([entries["m_big"], entries["m_big2"]])
    assert pd.isna(df["F"].iloc[1]) and pd.isna(df["p"].iloc[1])
    assert "变量数相同" in df["note"].iloc[1]


def test_compare_cli_needs_two(proj):
    r = _cli(proj, "compare", "m_big")
    assert r.returncode != 0
    assert "至少需要 2 个模型" in r.stderr + r.stdout


def test_compare_cli_writes_csv(proj):
    r = _cli(proj, "compare", "m_small", "m_big")
    assert r.returncode == 0, r.stderr[-2000:]
    assert "The F-test is valid only for nested models" in r.stdout
    csv = proj / "output" / "fits" / "model_compare.csv"
    df = pd.read_csv(csv, encoding="utf-8-sig")
    assert list(df["model"]) == ["m_small", "m_big"]
    assert json.loads((proj / "output" / "fits" / "model_compare.params.json").read_text(encoding="utf-8"))


def test_ftest_output_unchanged(proj):
    """两条提示文字与 B4 之前逐字相同，其后是 hamilton_test 的 JSON"""
    r = _cli(proj, "ftest", "m_small", "m_range")
    assert r.returncode == 0, r.stderr[-2000:]
    lines = [x for x in r.stdout.splitlines() if not x.startswith("No conda env")]
    assert lines[0] == ("两个模型的数据或拟合范围不同，F 检验不适用 / the two models use different data or fit ranges: "
                        "the F-test does not apply")
    assert lines[1].startswith("{")
    r = _cli(proj, "ftest", "m_small", "m_restr")
    assert [x for x in r.stdout.splitlines() if not x.startswith("No conda env")][0] == (
        "两个模型的软约束不同，χ² 含不同的约束项，F 检验不适用 / the two models have different restraints: "
        "their χ² contain different restraint terms, the F-test does not apply")
    r = _cli(proj, "ftest", "m_small", "m_big")
    body = "\n".join(x for x in r.stdout.splitlines() if not x.startswith("No conda env"))
    assert body.startswith("{") and json.loads(body)["b"] == 1
