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


# ------------------------------------------------------------------ 其余保存都写 params.json
def test_save_robustness_and_compare_write_params(proj):
    import pandas as pd
    from xafsmith import services
    fit = services.run_model(services.load_model("cu_one"))
    tab, ver = pd.DataFrame({"a": [1.0]}), pd.DataFrame({"b": [2.0]})
    files = services.save_robustness(fit, tab, ver, "GUI robustness")
    assert [f.name for f in files] == ["cu_one_robustness.csv", "cu_one_robustness_summary.csv",
                                       "cu_one_robustness.params.json"]
    p = json.loads(files[2].read_text(encoding="utf-8"))
    assert p["tool"] == "GUI robustness" and p["params"]["name"] == "cu_one"
    out = services.save_compare(pd.DataFrame({"model": ["a", "b"]}), ["a", "b"], "xafsmith compare")
    assert out == proj / "output" / "fits" / "model_compare.csv" and out.is_file()
    p = json.loads(out.with_suffix(".params.json").read_text(encoding="utf-8"))
    assert p["tool"] == "xafsmith compare" and p["params"] == {"models": ["a", "b"]}
    out2 = services.save_compare(pd.DataFrame({"model": ["a"]}), ["a"], "t", proj / "x" / "cmp.csv")
    assert out2.is_file() and out2.with_suffix(".params.json").is_file()


def _fake_lcf_result():
    import numpy as np
    x = np.linspace(-20, 30, 51)
    return dict(sample="s 1", space="norm", xmin=-20, xmax=30, rfactor=0.001, chi2_reduced=1.5, sum_weights=1.0, de=0.0,
                weights={"A": 0.4, "B": 0.6}, weights_err={"A": 0.01, "B": 0.01},
                curves=dict(x=x, y=x * 0.01, fit=x * 0.01, comps={"A": x * 0.02, "B": x * 0.005}))


def test_save_lcf_writes_row_figure_params(proj):
    import pandas as pd
    from xafsmith import services
    r = _fake_lcf_result()
    files = services.save_lcf(r, sample="s 1", standards=["A", "B"], kwargs=dict(xmin=-20, xmax=30, space="norm"),
                              note="n1", tool="xafsmith lcf")
    out = proj / "output"
    assert files == [out / "lcf" / "lcf_results.csv", out / "figs" / "lcf_s_1.png", out / "lcf" / "lcf_s_1.params.json"]
    assert all(f.is_file() for f in files)
    p = json.loads(files[2].read_text(encoding="utf-8"))
    assert p["tool"] == "xafsmith lcf"
    q = p["params"]
    assert q["sample"] == "s 1" and q["standards"] == ["A", "B"] and q["note"] == "n1"
    assert q["xmin"] == -20 and q["space"] == "norm" and q["sum_to_one"] is True and q["kweight"] == 2   # 缺省值也记录
    services.save_lcf(r, sample="s 1", standards=["A", "B"], kwargs={}, note="n2", tool="GUI LCF", figure=False)
    df = pd.read_csv(files[0], encoding="utf-8-sig")
    assert list(df["note"].dropna())[-2:] == ["n1", "n2"]


def test_save_xanes_merges_by_sample(proj):
    import pandas as pd
    from xafsmith import paths, services
    paths.XANES_CSV.unlink(missing_ok=True)
    paths.XANES_CSV.with_suffix(".params.json").unlink(missing_ok=True)

    def tab(rows):
        return pd.DataFrame([dict(sample=s, E0_deriv=v) for s, v in rows])
    services.save_xanes(tab([("A", 1.0), ("B", 2.0)]), wl_window=30.0, tool="xafsmith xanes")
    services.save_xanes(tab([("B", 2.5), ("C", 3.0)]), wl_window=20.0, tool="GUI XANES")
    df = pd.read_csv(paths.XANES_CSV, encoding="utf-8-sig")
    assert list(df["sample"]) == ["A", "B", "C"] and list(df["E0_deriv"]) == [1.0, 2.5, 3.0]
    p = json.loads(paths.XANES_CSV.with_suffix(".params.json").read_text(encoding="utf-8"))
    assert p["tool"] == "GUI XANES"
    s = p["params"]["samples"]
    assert list(s) == ["A", "B", "C"]
    assert [s[k]["wl_window"] for k in "ABC"] == [30.0, 20.0, 20.0]
    assert [s[k]["tool"] for k in "ABC"] == ["xafsmith xanes", "GUI XANES", "GUI XANES"]
    assert all(s[k]["time"] for k in "ABC")
    paths.XANES_CSV.with_suffix(".params.json").write_text("{not json", encoding="utf-8")      # 损坏的旧文件：从空开始
    services.save_xanes(tab([("D", 4.0)]), wl_window=10.0, tool="GUI XANES")
    s = json.loads(paths.XANES_CSV.with_suffix(".params.json").read_text(encoding="utf-8"))["params"]["samples"]
    assert list(s) == ["D"]


def test_save_qc_and_calib_write_params(proj):
    import pandas as pd
    from xafsmith import paths, services
    out = services.save_qc(pd.DataFrame({"label": ["a"], "e0": [1.0]}), norm_params={"Cu_K": {"pre1": -150}}, tool="GUI QC")
    assert out == paths.QC_CSV and out.is_file()
    p = json.loads(paths.QC_CSV.with_suffix(".params.json").read_text(encoding="utf-8"))
    assert p["tool"] == "GUI QC" and p["params"] == {"norm": {"Cu_K": {"pre1": -150}}}
    calib = {"ref.dat": {"delta_e": 1.5, "edge_key": "Cu_K", "reference_file": "ref.dat"}}
    out = services.save_calib(calib, tool="GUI calibration", params={"reference": "ref.dat"})
    assert out == paths.CALIB_JSON and json.loads(out.read_text(encoding="utf-8")) == calib
    p = json.loads(paths.CALIB_JSON.with_suffix(".params.json").read_text(encoding="utf-8"))
    assert p["tool"] == "GUI calibration" and p["params"] == {"reference": "ref.dat"}
    assert paths.CALIB_JSON.with_suffix(".params.json").name == "calib.params.json"
    from xafsmith import pipeline as pl
    assert pl.load_calib() == calib                                    # params.json 不影响读校准记录


def test_pipeline_run_qc_and_calib_write_params(proj):
    """pipeline.run_qc / run_calib 经 services 落盘（tool 为 pipeline.*）"""
    from xafsmith import paths, pipeline as pl
    pl.run_calib(pl.load_config(), pl.load_meta())
    p = json.loads(paths.CALIB_JSON.with_suffix(".params.json").read_text(encoding="utf-8"))
    assert p["tool"] == "pipeline.run_calib" and p["params"]["references"]
    pl.run_qc()
    q = json.loads(paths.QC_CSV.with_suffix(".params.json").read_text(encoding="utf-8"))
    assert q["tool"] == "pipeline.run_qc" and q["params"]["norm"]


def test_load_model_bare_name_prefers_models_dir(tmp_path, monkeypatch):
    """只给名字时取 models/ 里的文件，不取项目根同名 json（如 xafsmith.json）"""
    import json as _json
    from xafsmith import paths, services
    (tmp_path / "models").mkdir()
    (tmp_path / "xafsmith.json").write_text(_json.dumps({"edges": {}}), encoding="utf-8")
    (tmp_path / "models" / "xafsmith.json").write_text(_json.dumps({"sample": "s1", "paths": []}), encoding="utf-8")
    monkeypatch.setattr(paths, "ROOT", tmp_path)
    monkeypatch.setattr(paths, "MODELS", tmp_path / "models")
    m = services.load_model("xafsmith.json")
    assert m["sample"] == "s1" and m["name"] == "xafsmith"


def test_save_xanes_numeric_sample_names(proj):
    """样品名是数字（如 50）：旧 CSV 读回时仍按字符串比较，重算替换而不是重复追加。"""
    import pandas as pd
    from xafsmith import paths, services
    paths.XANES_CSV.unlink(missing_ok=True)
    t = pd.DataFrame([dict(sample="50", E0_deriv=1.0), dict(sample="100", E0_deriv=2.0)])
    services.save_xanes(t, wl_window=30.0, tool="xafsmith xanes")
    services.save_xanes(pd.DataFrame([dict(sample="50", E0_deriv=1.5)]), wl_window=30.0, tool="xafsmith xanes")
    df = pd.read_csv(paths.XANES_CSV, encoding="utf-8-sig", dtype={"sample": str})
    assert list(df["sample"]) == ["100", "50"] and list(df["E0_deriv"]) == [2.0, 1.5]
