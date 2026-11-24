"""G3：快速拟合汇报包（quickfit_report.write 与 CLI --report）。演示项目（Cu），真实拟合。"""
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pandas as pd
import pytest

from xafsmith import paths, quickfit as qf, quickfit_report as qr

TESTS = Path(__file__).resolve().parents[1]
DEMO = TESTS / "data" / "demo_project"
FEFF_CU = TESTS / "data" / "benchmark" / "feffcu01.dat"
FEFF = "output/feff/Cu_CuK"
MUST = {"参数表.csv", "判定.txt", "方法.md", "报告.html"}


@pytest.fixture(scope="module")
def proj(tmp_path_factory):
    d = tmp_path_factory.mktemp("qfrep") / "demo_project"
    shutil.copytree(DEMO, d)
    f = d / FEFF
    f.mkdir(parents=True)
    shutil.copyfile(FEFF_CU, f / "feff0001.dat")
    m = pd.read_csv(d / "data" / "meta.csv", dtype=str, encoding="utf-8-sig")
    m.loc[m["sample"] == "cu_rt01", "use"] = "1"
    m.to_csv(d / "data" / "meta.csv", index=False, encoding="utf-8-sig")
    old = paths.ROOT
    paths.set_root(d)
    yield d
    paths.set_root(old)


def _check_folder(d, imgs):
    names = {p.name for p in d.iterdir()}
    assert MUST <= names, names
    for im in imgs:
        assert im in names and (d / im).stat().st_size > 1000
    page = (d / "报告.html").read_text(encoding="utf-8")
    srcs = re.findall(r"<img src='([^']+)'", page)
    assert srcs and all((d / s).is_file() for s in srcs)
    return page


def test_single_report(proj):
    model = qf.build_model("cu_metal_rt", str(proj / FEFF), 3.0, "standard")
    res = qf.run(model)
    d = qr.default_dir(res, root=proj / "output" / "reports")
    assert d.parent.name == "reports" and d.name.startswith("QF_cu_metal_rt_")
    page = qr.write(res, d)
    html = _check_folder(d, ["cu_metal_rt_chiR.png", "cu_metal_rt_chik.png"])
    assert page == d / "报告.html" and "XAFSmith" in html and "判定" in html and "参数表" in html and "方法段落" in html
    n = qr.count_issues(res)
    assert ("需注意，不建议直接用于结论" in html) == (n > 0)
    df = pd.read_csv(d / "参数表.csv", encoding="utf-8-sig")
    assert len(df) == 1 and df.iloc[0]["样品"] == "cu_metal_rt" and "±" in df.iloc[0]["R (Å)"] and "σ² (Å²)" in df.columns
    assert (d / "判定.txt").read_text(encoding="utf-8").startswith("== cu_metal_rt")
    meth = (d / "方法.md").read_text(encoding="utf-8")
    assert "## 中文" in meth and "## English" in meth
    assert not (proj / "models" / f"{res.model['name']}.json").exists()          # 不强制先保存，也不顺手保存


def test_default_dir_never_overwrites(proj, tmp_path):
    model = qf.build_model("cu_metal_rt", str(proj / FEFF), 3.0, "standard")
    res = qf.run(model)
    d = qr.default_dir(res, root=tmp_path)
    d.mkdir()
    assert qr.default_dir(res, root=tmp_path).name == d.name + "-2"


def test_failed_verdict_banner(proj):
    model = qf.build_model("cu_metal_rt", str(proj / FEFF), 3.0, "sample", s02=0.5, s02_source=dict(manual=True, value=0.5))
    res = qf.run(model)
    n = qr.count_issues(res)
    page = qr.write(res, proj / "output" / "reports" / "banner_test")
    html = page.read_text(encoding="utf-8")
    assert ("class='warn'" in html and f"本次拟合有 {n} 项需注意" in html) if n else "class='ok'" in html
    # 需注意条目排在通过条目之前
    if n:
        assert html.index('<span class="f">') < html.index('<span class="p">') if '<span class="p">' in html else True


def test_english_report(proj):
    model = qf.build_model("cu_metal_rt", str(proj / FEFF), 3.0, "standard")
    res = qf.run(model)
    page = qr.write(res, proj / "output" / "reports" / "en_test", lang="en")
    html = page.read_text(encoding="utf-8")
    assert "Quick-fit report" in html and "Parameters" in html
    assert (page.parent / "判定.txt").read_text(encoding="utf-8").startswith("== cu_metal_rt (standard)")


def test_joint_report(proj):
    model = qf.build_joint_model(["cu_metal_rt", "cu_rt01"], str(proj / FEFF), 3.0, s02=0.9, s02_source=dict(manual=True, value=0.9),
                                 name="QF_joint_rep")
    res = qf.run(model)
    d = proj / "output" / "reports" / "joint_test"
    qr.write(res, d)
    html = _check_folder(d, ["cu_metal_rt_chiR.png", "cu_rt01_chik.png", "trend_N.png", "trend_R.png", "trend_sigma2.png"])
    assert "整批" in html
    df = pd.read_csv(d / "参数表.csv", encoding="utf-8-sig")
    assert list(df["样品"]) == ["cu_metal_rt", "cu_rt01"]
    assert (d / "判定.txt").read_text(encoding="utf-8").startswith("== 联合快速拟合")


def test_cli_report(proj):
    env = dict(os.environ, PYTHONIOENCODING="utf-8", XAFSMITH_NO_RECENT="1")
    r = subprocess.run([sys.executable, "-m", "xafsmith.cli", "--project", str(proj), "quickfit", "cu_metal_rt", "--feff", FEFF,
                        "--rmax", "3.0", "--standard", "--name", "QF_cli_rep", "--report"],
                       capture_output=True, text=True, encoding="utf-8", env=env, timeout=300)
    assert r.returncode == 0, r.stderr[-2000:]
    dirs = sorted((proj / "output" / "reports").glob("QF_cli_rep_*"))
    assert len(dirs) == 1 and "汇报包" in r.stdout
    _check_folder(dirs[0], ["cu_metal_rt_chiR.png", "cu_metal_rt_chik.png"])
    assert not (proj / "models" / "QF_cli_rep.json").exists()            # --report 不等于 --save
