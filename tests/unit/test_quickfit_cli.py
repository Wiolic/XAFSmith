"""CLI xafsmith quickfit：默认只打印，--save 才写文件；保存的模型是普通模型。演示项目（Cu）。"""
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pandas as pd
import pytest

TESTS = Path(__file__).resolve().parents[1]
DEMO = TESTS / "data" / "demo_project"
FEFF_CU = TESTS / "data" / "benchmark" / "feffcu01.dat"
FEFF = "output/feff/Cu_CuK"


@pytest.fixture(scope="module")
def proj(tmp_path_factory):
    d = tmp_path_factory.mktemp("qfcli") / "demo_project"
    shutil.copytree(DEMO, d)
    f = d / FEFF
    f.mkdir(parents=True)
    shutil.copyfile(FEFF_CU, f / "feff0001.dat")
    return d


def _cli(proj, *args):
    env = dict(os.environ, PYTHONIOENCODING="utf-8", XAFSMITH_NO_RECENT="1")
    return subprocess.run([sys.executable, "-m", "xafsmith.cli", "--project", str(proj), *args],
                          capture_output=True, text=True, encoding="utf-8", env=env, timeout=300)


def test_cli_quickfit_prints_and_does_not_save_by_default(proj):
    out = proj / "output"
    before = {p for p in out.rglob("*") if p.is_file()}
    r = _cli(proj, "quickfit", "cu_metal_rt", "--feff", FEFF, "--rmax", "3.0", "--standard")
    assert r.returncode == 0, r.stderr[-2000:]
    assert "第一壳层" in r.stdout and "判定" in r.stdout and "R-factor" in r.stdout and "未加 --save" in r.stdout
    assert {p for p in out.rglob("*") if p.is_file()} == before and not (proj / "models" / "QF_cu_metal_rt.json").exists()


def test_cli_quickfit_options_and_errors(proj):
    r = _cli(proj, "quickfit", "cu_metal_rt", "--feff", FEFF, "--rmax", "3.0", "--s02", "0.9", "--rmin", "1.3", "--kweight", "2")
    assert r.returncode == 0, r.stderr[-2000:]
    assert "R 1.30–3.00 Å" in r.stdout and "kweight [2]" in r.stdout and "没有标样依据" in r.stdout
    r = _cli(proj, "quickfit", "cu_metal_rt", "--feff", FEFF, "--s02-from", "nothing_here")
    assert r.returncode != 0 and "nothing_here" in r.stderr
    assert _cli(proj, "quickfit", "cu_metal_rt", "--feff", FEFF).returncode != 0         # 三选一必须给


def test_cli_quickfit_save_and_no_overwrite(proj):
    r = _cli(proj, "quickfit", "cu_metal_rt", "--feff", FEFF, "--rmax", "3.0", "--standard", "--save", "--name", "QF_std_cu")
    assert r.returncode == 0, r.stderr[-2000:]
    m = json.loads((proj / "models" / "QF_std_cu.json").read_text(encoding="utf-8"))
    assert m["sample"] == "cu_metal_rt" and "n1" not in m["params"]
    df = pd.read_csv(proj / "output" / "fits" / "exafs_fits.csv", encoding="utf-8-sig")
    assert "QF_std_cu" in set(df["model"])
    assert (proj / "output" / "figs" / "QF_std_cu_fit.png").is_file()
    again = _cli(proj, "quickfit", "cu_metal_rt", "--feff", FEFF, "--rmax", "3.0", "--standard", "--save", "--name", "QF_std_cu")
    assert again.returncode != 0 and "不覆盖" in again.stderr
    r = _cli(proj, "fit", "QF_std_cu", "--nosave")                       # 保存的模型就是普通模型：fit 命令能直接跑
    assert r.returncode == 0, r.stderr[-2000:]
    sample = _cli(proj, "quickfit", "cu_metal_rt", "--feff", FEFF, "--rmax", "3.0", "--s02-from", "QF_std_cu")
    assert sample.returncode == 0, sample.stderr[-2000:]                 # 同边标样 → 样品 S0² 来自它
    assert "N_idp" in sample.stdout
