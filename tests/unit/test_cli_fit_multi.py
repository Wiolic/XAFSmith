"""B1 T9：多数据集模型走命令行与界面入口。

演示项目复制到 tmp_path，写一个 2 数据集模型（同一 cu_metal_rt，路径用 feffcu01.dat 绝对路径）：
  xafsmith fit 退出码 0、每个数据集一张图、CSV 有 dataset 列且两个数据集各一行；
  xafsmith robust 给出“暂不支持”且退出码非 0；
  界面 state.run_model 抛出双语提示（界面在 B2 提供）。
CLI 在子进程里运行（项目目录须在导入 xafsmith.paths 之前设定）。
"""
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
FEFF = TESTS / "data" / "benchmark" / "feffcu01.dat"


def _path(sig):
    return {"file": str(FEFF), "label": "Cu-Cu", "s02": "amp", "e0": "del_e0", "deltar": "del_r", "sigma2": sig}


MODEL = {"name": "cu_twin", "kmin": 3, "kmax": 17, "dk": 4, "window": "kaiser", "kweight": 2,
         "rmin": 1.4, "rmax": 3.0, "fitspace": "r",
         "params": {"amp": 1.0, "del_e0": 0.0, "del_r": 0.0, "ssA": 0.005, "ssB": 0.005},
         "datasets": [{"id": "A", "sample": "cu_metal_rt", "paths": [_path("ssA")]},
                      {"id": "B", "sample": "cu_metal_rt", "kmax": 14, "paths": [_path("ssB")]}]}


@pytest.fixture(scope="module")
def proj(tmp_path_factory):
    d = tmp_path_factory.mktemp("demo") / "demo_project"
    shutil.copytree(DEMO, d)
    (d / "models").mkdir(exist_ok=True)
    (d / "models" / "cu_twin.json").write_text(json.dumps(MODEL, ensure_ascii=False), encoding="utf-8")
    return d


def _cli(proj, *args):
    env = dict(os.environ, PYTHONIOENCODING="utf-8", XAFSMITH_NO_RECENT="1")
    return subprocess.run([sys.executable, "-m", "xafsmith.cli", "--project", str(proj), *args],
                          capture_output=True, text=True, encoding="utf-8", env=env, timeout=300)


def test_fit_multi_cli(proj):
    r = _cli(proj, "fit", "cu_twin")
    assert r.returncode == 0, r.stderr[-2000:]
    assert "联合拟合 2 个数据集" in r.stdout
    for i in ("A", "B"):
        assert (proj / "output" / "figs" / f"cu_twin_{i}_fit.png").is_file()
    df = pd.read_csv(proj / "output" / "fits" / "exafs_fits.csv", encoding="utf-8-sig")
    rows = df[df["model"] == "cu_twin"]
    assert "dataset" in df.columns
    assert sorted(rows["dataset"]) == ["A", "B"]
    assert set(rows[rows["dataset"] == "B"]["k_range"]) == {"3-14"}


def test_robust_refuses_multi(proj):
    r = _cli(proj, "robust", "cu_twin")
    assert r.returncode != 0
    assert "暂不支持" in r.stderr + r.stdout


def test_gui_run_model_runs_multi(proj):
    """B2：GUI 的 run_model 能直接运行多数据集模型（组按项目配置建，与命令行一致）"""
    from xafsmith import paths
    from xafsmith.qt import state
    old = paths.ROOT
    paths.set_root(proj)
    try:
        m = state.load_model("cu_twin.json", sample="cu_metal_rt")     # 不替换样品、不报缺 sample
        assert "datasets" in m and "sample" not in m
        fit = state.run_model(None, m)
        assert fit["multi"] and fit["summ"]["n_datasets"] == 2 and len(fit["curves"]) == 2
        assert state.fit_ds_ids(fit) == [d["id"] for d in fit["summ"]["datasets"]]
        sub = state.fit_dataset(fit, state.fit_ds_ids(fit)[1])
        assert sub["summ"]["dataset"] == state.fit_ds_ids(fit)[1] and sub["summ"]["n_idp"] == fit["summ"]["datasets"][1]["n_idp"]
    finally:
        paths.set_root(old)


# ------------------------------------------------------------------ B3 R8：软约束走命令行
CU1 = {"name": "cu_one", "sample": "cu_metal_rt", "kmin": 3, "kmax": 17, "dk": 4, "window": "kaiser",
       "kweight": 2, "rmin": 1.4, "rmax": 3.0, "fitspace": "r",
       "params": {"amp": 1.0, "del_e0": 0.0, "sig2": 0.0, "del_r": 0.0},
       "paths": [{"file": str(FEFF), "label": "Cu-Cu", "s02": "amp", "e0": "del_e0",
                  "sigma2": "sig2", "deltar": "del_r"}]}


def test_fit_restraint_cli_and_ftest(proj):
    (proj / "models" / "cu_one.json").write_text(json.dumps(CU1), encoding="utf-8")
    (proj / "models" / "cu_one_r.json").write_text(json.dumps(
        dict(CU1, name="cu_one_r", restraints=[dict(expr="amp", value=0.9, sigma=0.05)])), encoding="utf-8")
    r = _cli(proj, "fit", "cu_one_r")
    assert r.returncode == 0, r.stderr[-2000:]
    assert "Restraints" in r.stdout
    df = pd.read_csv(proj / "output" / "fits" / "exafs_fits.csv", encoding="utf-8-sig")
    rows = df[df["model"] == "cu_one_r"]
    assert len(rows) == 1 and "restraint_chi2" in df.columns and rows["restraint_chi2"].iloc[0] > 0
    assert "r1" in json.loads(rows["restraints"].iloc[0])
    f = _cli(proj, "ftest", "cu_one", "cu_one_r")
    assert f.returncode == 0, f.stderr[-2000:]
    assert "软约束不同" in f.stdout
    m = _cli(proj, "methods")
    assert m.returncode == 0, m.stderr[-1500:]
    assert "软约束" in m.stdout and "amp = 0.9 ± 0.05" in m.stdout and "Soft restraints" in m.stdout
    for lang, word in (("zh", "软约束"), ("en", "Soft restraints")):
        si = _cli(proj, "si", "--lang", lang)
        assert si.returncode == 0, si.stderr[-1500:]
        assert word in si.stdout and "amp = 0.9 ± 0.05" in si.stdout and "σ" in si.stdout


# ------------------------------------------------------------------ C2：xafsmith trend
def test_trend_cli_prints_and_saves(proj):
    r = _cli(proj, "trend", "cu_twin", "--seq-label", "Reduced time")
    assert r.returncode == 0, r.stderr[-2000:]
    assert "来源 time" in r.stdout                           # 演示项目的 meta.csv 没有 seq 列，有 time → 以小时为序列变量
    assert "N_err" in r.stdout and "shared_sigma2" in r.stdout
    assert "Reduced time" in r.stdout                        # 图注里的横轴标题
    t = pd.read_csv(proj / "output" / "fits" / "cu_twin_trend.csv", encoding="utf-8-sig")
    assert list(t["dataset"]) == ["A", "B"] and "dE0_err" in t.columns
    assert (proj / "output" / "fits" / "cu_twin_trend.params.json").is_file()
    assert (proj / "output" / "figs" / "cu_twin_trend.png").stat().st_size > 5000


def test_trend_cli_nosave_and_errors(proj):
    for f in ("cu_twin_trend.csv", "cu_twin_trend.params.json"):
        (proj / "output" / "fits" / f).unlink(missing_ok=True)
    r = _cli(proj, "trend", "cu_twin", "--nosave", "--panels", "R,sigma2")
    assert r.returncode == 0, r.stderr[-2000:]
    assert not (proj / "output" / "fits" / "cu_twin_trend.csv").exists()
    bad = _cli(proj, "trend", "cu_twin", "--panels", "R,nope")
    assert bad.returncode != 0 and "--panels" in bad.stderr + bad.stdout
    (proj / "models" / "cu_one_t.json").write_text(json.dumps(dict(CU1, name="cu_one_t")), encoding="utf-8")
    one = _cli(proj, "trend", "cu_one_t")
    assert one.returncode != 0 and "联合拟合" in one.stderr + one.stdout
