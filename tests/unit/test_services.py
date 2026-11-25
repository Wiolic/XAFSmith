"""E9：单一业务层 services.py —— CLI 与 GUI 两条路径落盘一致，每种保存都有 params.json。

演示项目复制到 tmp_path（不碰演示项目自身的 output/），进程内用 paths.set_root 切换项目。
"""
import json
import shutil
from pathlib import Path

import pytest

TESTS = Path(__file__).resolve().parents[1]
DEMO = TESTS / "data" / "demo_project"
FEFF = TESTS / "data" / "benchmark" / "feffcu01.dat"

CU1 = {"name": "cu_one", "sample": "cu_metal_rt", "kmin": 3, "kmax": 17, "dk": 4, "window": "kaiser",
       "kweight": 2, "rmin": 1.4, "rmax": 3.0, "fitspace": "r",
       "params": {"amp": 1.0, "del_e0": 0.0, "sig2": 0.0, "del_r": 0.0},
       "paths": [{"file": str(FEFF), "label": "Cu-Cu", "s02": "amp", "e0": "del_e0",
                  "sigma2": "sig2", "deltar": "del_r"}]}


def _path(sig):
    return {"file": str(FEFF), "label": "Cu-Cu", "s02": "amp", "e0": "del_e0", "deltar": "del_r", "sigma2": sig}


TWIN = {"name": "cu_twin", "kmin": 3, "kmax": 17, "dk": 4, "window": "kaiser", "kweight": 2,
        "rmin": 1.4, "rmax": 3.0, "fitspace": "r",
        "params": {"amp": 1.0, "del_e0": 0.0, "del_r": 0.0, "ssA": 0.005, "ssB": 0.005},
        "datasets": [{"id": "A", "sample": "cu_metal_rt", "paths": [_path("ssA")]},
                     {"id": "B", "sample": "cu_metal_rt", "kmax": 14, "paths": [_path("ssB")]}]}


def make_project(root: Path) -> Path:
    d = root / "demo_project"
    shutil.copytree(DEMO, d)
    (d / "models").mkdir(exist_ok=True)
    (d / "models" / "cu_one.json").write_text(json.dumps(CU1, ensure_ascii=False), encoding="utf-8")
    (d / "models" / "cu_twin.json").write_text(json.dumps(TWIN, ensure_ascii=False), encoding="utf-8")
    return d


@pytest.fixture()
def proj(tmp_path):
    from xafsmith import paths
    d = make_project(tmp_path)
    old = paths.ROOT
    paths.set_root(d)
    try:
        yield d
    finally:
        paths.set_root(old)


# ------------------------------------------------------------------ 小函数
def test_fit_base_candidates():
    from xafsmith import services
    assert services.fit_base_candidates("a  b") == ["a_b", "a__b"]
    assert services.fit_base_candidates("ab-1.2_x") == ["ab-1.2_x"]
    assert services.safe("a  b") == "a_b"


def test_load_model_name_and_file(proj):
    from xafsmith import services
    m = services.load_model("cu_one")
    assert m["name"] == "cu_one" and m["sample"] == "cu_metal_rt"
    assert services.load_model("cu_one.json") == m                     # GUI 传文件名
    m2 = services.load_model("cu_one.json", sample="other")            # 换样品：名字里没有旧样品名 → 加 @
    assert m2["sample"] == "other" and m2["name"] == "cu_one@other"
    mt = services.load_model("cu_twin.json", sample="whatever")       # 多数据集：不替换
    assert "datasets" in mt and "sample" not in mt


def test_run_model_single_and_multi(proj):
    from xafsmith import services
    fit = services.run_model(services.load_model("cu_one"))
    assert set(fit) == {"model", "summ", "result", "curves", "report", "time"}
    assert "multi" not in fit and fit["summ"]["model"] == "cu_one"
    fm = services.run_model(services.load_model("cu_twin"))
    assert fm["multi"] and set(fm["curves"]) == {"A", "B"} and fm["summ"]["n_datasets"] == 2


def test_resolve_groups_fallback(proj):
    """谱没有登记时取会话里的同名谱（fallback）；没有则照旧 KeyError"""
    from xafsmith import services
    g = services.resolve_groups(services.load_model("cu_one"))
    m = dict(CU1, sample="not_registered")
    with pytest.raises(KeyError):
        services.resolve_groups(m)
    assert services.resolve_groups(m, fallback={"not_registered": g}) is g
    mt = dict(TWIN, datasets=[dict(TWIN["datasets"][0], sample="nope")])
    got = services.resolve_groups(mt, fallback={"nope": g})
    assert got == {"A": g}


# ------------------------------------------------------------------ CLI 与 GUI 两条路径落盘一致
def _snap(proj: Path) -> dict:
    out = proj / "output"
    return {p.relative_to(out).as_posix(): p.read_bytes() for p in out.rglob("*") if p.is_file()} if out.exists() else {}


def _clear(proj: Path, names):
    for n in names:
        (proj / "output" / n).unlink()


def _norm_params(raw: bytes):
    d = json.loads(raw.decode("utf-8"))
    assert d["tool"] and d["time"]
    d.pop("tool"), d.pop("time")
    return d


def _compare_paths(proj, model_name, multi):
    """A：cli.main(["fit", …])；B：services.run_model + save_fit(tool="GUI fit", write_model=False)；产物应相同。"""
    from xafsmith import cli, services
    (proj / "output" / "fits" / "exafs_fits.csv").unlink(missing_ok=True)      # 临时副本：让结果表也是“新写出”的文件
    before = _snap(proj)
    cli.main(["--project", str(proj), "fit", model_name])
    after = _snap(proj)
    a_new = {k: v for k, v in after.items() if k not in before}
    assert a_new, "CLI 没有写出任何文件"
    assert not [k for k in before if after[k] != before[k]], "CLI 改动了已有文件"
    _clear(proj, a_new)
    fit = services.run_model(services.load_model(model_name))
    res = services.save_fit(fit, "GUI fit", write_model=False)
    b_new = {k: v for k, v in _snap(proj).items() if k not in before}
    assert set(b_new) == set(a_new)
    for k in a_new:
        if k.endswith(".params.json"):
            assert _norm_params(a_new[k]) == _norm_params(b_new[k]), k
        else:
            assert a_new[k] == b_new[k], f"{k} 两条路径不逐字节相同"
    got = {f.relative_to(proj / "output").as_posix() for f in res.files}
    assert got == set(b_new)                                          # SaveResult 列出的文件 = 实际写出的文件
    assert "fits/%s.params.json" % model_name in b_new
    assert not (proj / "models" / f"{model_name}_zz.json").exists()
    return res, a_new


def test_cli_and_gui_fit_identical_single(proj):
    res, files = _compare_paths(proj, "cu_one", multi=False)
    assert sorted(files) == ["figs/cu_one_fit.png", "fits/cu_one.fit_report.txt", "fits/cu_one.params.json",
                             "fits/exafs_fits.csv"]
    assert res.trend is None
    p = json.loads(files["fits/cu_one.params.json"])
    assert p["tool"] == "xafsmith fit" and p["params"]["name"] == "cu_one"


def test_cli_and_gui_fit_identical_multi(proj):
    res, files = _compare_paths(proj, "cu_twin", multi=True)
    assert {"figs/cu_twin_A_fit.png", "figs/cu_twin_B_fit.png", "fits/cu_twin_trend.csv",
            "fits/cu_twin_trend.params.json", "fits/cu_twin.params.json"} <= set(files)
    assert res.trend is not None and res.trend.name == "cu_twin_trend.csv"


def test_save_fit_writes_model_and_tool(proj):
    from xafsmith import services
    fit = services.run_model(services.load_model("cu_one"))
    res = services.save_fit(fit, "GUI quickfit")
    mf = proj / "models" / "cu_one.json"
    assert mf in res.files and json.loads(mf.read_text(encoding="utf-8"))["name"] == "cu_one"
    assert json.loads((proj / "output" / "fits" / "cu_one.params.json").read_text(encoding="utf-8"))["tool"] == "GUI quickfit"
