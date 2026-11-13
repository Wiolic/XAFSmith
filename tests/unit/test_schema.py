import json
import shutil
from pathlib import Path

import pytest

from xafsmith import paths, schema

DEMO = Path(__file__).resolve().parents[1] / "data" / "demo_project"


@pytest.fixture
def proj(tmp_path):
    dst = tmp_path / "p"
    shutil.copytree(DEMO, dst, ignore=shutil.ignore_patterns("output"))
    old = paths.ROOT
    paths.set_root(dst)
    yield dst
    paths.set_root(old)


def msgs(rep):
    return [f"{a} {b} {c}" for a, b, c in rep.items]


def test_demo_has_no_errors(proj):
    assert schema.validate(structures=False).n_err == 0


def test_bad_config_json_reports_line(proj):
    (proj / "xafsmith.json").write_text('{\n  "edges": {,\n}', encoding="utf-8")
    rep = schema.validate(structures=False)
    assert any("第 2 行" in m for m in msgs(rep))


def test_meta_duplicate_and_empty_cell(proj):
    f = proj / "data" / "meta.csv"
    lines = f.read_text(encoding="utf-8-sig").splitlines()
    lines.append(lines[1])                                  # 重复登记
    f.write_text("\n".join(lines) + "\n", encoding="utf-8-sig")
    rep = schema.validate(structures=False)
    assert any("重复登记" in m for m in msgs(rep))


def test_model_json_errors(proj):
    (proj / "models").mkdir(exist_ok=True)
    (proj / "models" / "bad.json").write_text("{\n 'a': 1}", encoding="utf-8")
    (proj / "models" / "rng.json").write_text(json.dumps(
        dict(name="x", sample="s", kmin=10, kmax=3, rmin=1, rmax=3, kweight=2, params={}, paths=[{}])), encoding="utf-8")
    ms = msgs(schema.validate(structures=False))
    assert any("bad.json" in m and "第 2 行" in m for m in ms)
    assert any("kmin 应小于 kmax" in m for m in ms)
    assert any("paths[0]" in m for m in ms)


def _model(**kw):
    m = dict(name="x", sample="s", kmin=3, kmax=12, rmin=1, rmax=3, kweight=[1, 2, 3], window="hanning",
             params={"s02": 0.8}, paths=[{"file": "output/feff/x/feff0001.dat"}])
    m.update(kw)
    return m


def test_model_kweight_list_and_window(proj):
    (proj / "models").mkdir(exist_ok=True)
    (proj / "models" / "ok.json").write_text(json.dumps(_model()), encoding="utf-8-sig")       # BOM 也能读
    (proj / "models" / "win.json").write_text(json.dumps(_model(window="hamming2")), encoding="utf-8")
    ms = msgs(schema.validate(structures=False))
    assert not any("ok.json" in m and m.startswith("错误") for m in ms)
    assert any("win.json" in m and "窗函数" in m for m in ms)


def test_nidp_rules():
    assert schema.count_varied({"a": 1.0, "b": "a*2", "c": {"value": 1, "vary": False},
                                "d": {"value": 1}, "e": {"expr": "a"}}) == 2
    assert abs(schema.n_idp(3, 12, 1, 3) - 2 * 9 * 2 / 3.141592653589793) < 1e-9


def test_model_underdetermined_is_error(proj):
    (proj / "models").mkdir(exist_ok=True)
    many = {f"p{i}": 0.1 for i in range(6)}                 # N_idp = 2·2·0.5/π ≈ 0.64
    (proj / "models" / "u.json").write_text(json.dumps(_model(kmin=3, kmax=5, rmin=1, rmax=1.5, params=many)),
                                            encoding="utf-8")
    rep = schema.validate(structures=False)
    assert any(lv == "错误" and "u.json" in at and "欠定" in m for lv, at, m in rep.items)


def test_config_ranges(proj):
    cfg = json.loads((proj / "xafsmith.json").read_text(encoding="utf-8-sig"))
    ek = next(iter(cfg["edges"]))
    cfg["edges"][ek]["norm"]["pre1"], cfg["edges"][ek]["norm"]["pre2"] = -30, -150
    cfg["edges"][ek]["ft"]["kweight"] = [1, 2, 3]           # 列表合法
    cfg["edges"][ek]["bkg"]["rbkg"] = 0
    (proj / "xafsmith.json").write_text(json.dumps(cfg), encoding="utf-8")
    rep = schema.validate(structures=False)
    errs = [f"{at} {m}" for lv, at, m in rep.items if lv == "错误"]
    assert any("pre1 应小于 pre2" in e for e in errs)
    assert any("rbkg" in e for e in errs)
    assert not any("kweight" in e for e in errs)


def test_k_limit_ignores_short_scans_and_uses_sample_elements():
    import pandas as pd
    cfg = {"edges": {"Ir_L3": {"element": "Ir", "edge": "L3", "elements_in_sample": ["Ir", "Ta"],
                               "ft": {"kmax": 12.0}}},
           "overrides": {"B": {"elements_in_sample": ["Ir", "O"]}}}
    rows = [("A", "12016.8"), ("A", "11231.0"),             # 第二条是短扫描（不参与合并）
            ("B", "12016.8")]
    meta = pd.DataFrame([dict(file=f"f{i}", sample=s, edge_key="Ir_L3", use="1", emax=e)
                         for i, (s, e) in enumerate(rows)])
    kl = schema.k_limits(cfg, meta)
    assert kl[("A", "Ir_L3")][2] == "Ta" and 10.5 < kl[("A", "Ir_L3")][0] < 11.1  # Ta L1 ≈ 11.07 Å⁻¹ − 0.3
    assert kl[("B", "Ir_L3")][2] is None and kl[("B", "Ir_L3")][0] > 12            # B 不含 Ta：只受数据末端限制


def test_time_gap_accepts_all_meta_time_formats():
    from xafsmith.calib import time_gap_hours
    assert abs(time_gap_hours("2026/5/1 9:00:00", "2026/5/1 10:30:00") - 1.5) < 1e-9          # BSRF
    assert abs(time_gap_hours("2001-06-26T21:00:00", "2001-06-26T22:30:00") - 1.5) < 1e-9     # XDI
    assert abs(time_gap_hours("Tue Jun 26 21:00:00 2001", "Tue Jun 26 22:30:00 2001") - 1.5) < 1e-9   # .xmu
    assert time_gap_hours("乱写", "2026/5/1 9:00:00") is None


# ------------------------------------------------------------------ B1 T8：多数据集模型
FEFF = Path(__file__).resolve().parents[1] / "data" / "benchmark" / "feffcu01.dat"


def _multi(**kw):
    p = lambda s: [{"file": str(FEFF), "s02": "amp", "e0": "e0", "deltar": "dr", "sigma2": s}]  # noqa: E731
    m = dict(name="mm", kmin=3, kmax=14, rmin=1.4, rmax=3.0, kweight=2, window="kaiser", dk=4,
             params={"amp": 1.0, "e0": 0.0, "dr": 0.0, "ssA": 0.005, "ssB": 0.005},
             datasets=[dict(id="A", sample="cu_metal_rt", paths=p("ssA")),
                       dict(id="B", sample="cu_rt01", kmax=13, paths=p("ssB"))])
    m.update(kw)
    return m


def _mm(proj, model):
    (proj / "models").mkdir(exist_ok=True)
    (proj / "models" / "mm.json").write_text(json.dumps(model, ensure_ascii=False), encoding="utf-8")
    return [(lv, at, m) for lv, at, m in schema.validate(structures=False).items if "mm.json" in at]


def test_multi_valid_model_clean(proj):
    assert _mm(proj, _multi()) == []


def _ds(m, i, **kw):
    m["datasets"][i].update(kw)
    return m


@pytest.mark.parametrize("model,where,text", [
    (_multi(datasets=[]), "datasets", "非空数组"),
    (_multi(datasets=[1]), "datasets[0]", "应是对象"),
    ({k: v for k, v in _multi().items() if k != "params"}, "mm.json", "缺少字段 params"),
    (_multi(sample="cu_metal_rt"), "mm.json sample", "不得有顶层 sample"),
    (_multi(paths=[]), "mm.json paths", "不得有顶层 paths"),
    ({**_multi(), "datasets": [{"id": "A", "paths": [{"file": str(FEFF)}]}]}, "datasets[0](A)", "缺少字段 sample"),
    ({**_multi(), "datasets": [{"id": "A", "sample": "cu_metal_rt"}]}, "datasets[0](A)", "缺少字段 paths"),
    ({k: v for k, v in _multi().items() if k != "rmax"}, "datasets[0](A)", "缺少 rmax"),
    (_ds(_multi(), 1, kmin=15), "datasets[1](B) kmin/kmax", "kmin 应小于 kmax"),
    (_ds(_multi(), 1, rmin=-1), "datasets[1](B) rmin", "不能为负"),
    (_ds(_multi(), 1, kmax="x"), "datasets[1](B) kmax", "应为数字"),
    (_ds(_multi(), 1, kweight="k2"), "datasets[1](B) kweight", "数字或数字列表"),
    (_ds(_multi(), 1, window="hamming2"), "datasets[1](B) window", "窗函数"),
    (_ds(_multi(), 1, paths=[{}]), "datasets[1](B) paths[0]", "file"),
    (_ds(_multi(), 1, id="A"), "datasets[1](A) id", "重复"),
    (_ds(_multi(), 1, id=""), "datasets[1]() id", "不能为空"),
    (_ds(_multi(), 1, epsilon_k=0), "datasets[1](B) epsilon_k", "正数"),
    (_multi(params={f"p{i}": 0.1 for i in range(25)}), "mm.json params", "Σ N_idp"),
])
def test_multi_errors(proj, model, where, text):
    items = _mm(proj, model)
    assert any(lv == "错误" and at.endswith(where) and text in m for lv, at, m in items), items


@pytest.mark.parametrize("model,where,text", [
    (_multi(params={f"p{i}": 0.1 for i in range(12)}), "mm.json params", "全部数据集合计"),
    (_ds(_multi(), 1, sample="cu_metal_rt", id="B"), "mm.json datasets", "重复使用"),
    (_ds(_multi(), 1, fitspace="k"), "mm.json datasets", "fitspace 不同"),
    (_ds(_multi(), 1, sample="nope"), "datasets[1](B)", "不在 meta.csv"),
    (_ds(_multi(), 1, paths=[{"file": "output/feff/none/feff0001.dat"}]), "datasets[1](B)", "FEFF 路径文件不存在"),
    (_ds(_multi(), 0, kmax=30), "datasets[0](A) kmax", "超过可用上限"),
])
def test_multi_warnings(proj, model, where, text):
    items = _mm(proj, model)
    assert any(lv == "警告" and at.endswith(where) and text in m for lv, at, m in items), items
    assert not any(lv == "错误" for lv, _, _ in items), items


# ------------------------------------------------------------------ B3 R7：restraints
def _rs(*items, **kw):
    return _multi(restraints=list(items), **kw)


OKR = dict(expr="ssA - ssB", value=-0.004, sigma=0.001)


def test_restraints_valid_clean(proj):
    assert _mm(proj, _rs(OKR, dict(name="s02", expr="amp", value=0.8, sigma=0.05, note="x"))) == []
    assert _mm(proj, _multi(restraints=[])) == []


@pytest.mark.parametrize("rs,where,text", [
    ("x", "restraints", "应是数组"),
    ([1], "restraints[0]", "应是对象"),
    ([dict(value=1, sigma=1)], "restraints[0]", "缺少字段 expr"),
    ([dict(expr="amp", sigma=1)], "restraints[0]", "缺少字段 value"),
    ([dict(expr="amp", value=1)], "restraints[0]", "缺少字段 sigma"),
    ([dict(expr="", value=1, sigma=1)], "restraints[0] expr", "非空"),
    ([dict(expr="amp +", value=1, sigma=1)], "restraints[0] expr", "无法解析"),
    ([dict(expr="amp", value="a", sigma=1)], "restraints[0] value", "有限数字"),
    ([dict(expr="amp", value=1, sigma=0)], "restraints[0] sigma", "大于 0"),
    ([dict(expr="amp", value=1, sigma=-2)], "restraints[0] sigma", "大于 0"),
    ([dict(expr="amp", value=1, sigma=1, name="")], "restraints[0] name", "不能为空"),
    ([dict(expr="amp", value=1, sigma=1), dict(expr="e0", value=0, sigma=1, name="r1")], "restraints[1] name", "重复"),
    ([dict(expr="amp + zzz", value=1, sigma=1)], "restraints[0] expr", "zzz"),
    ([dict(expr="3.0", value=1, sigma=1)], "restraints[0] expr", "没有引用任何模型参数"),
])
def test_restraints_errors(proj, rs, where, text):
    items = _mm(proj, _multi(restraints=rs))
    assert any(lv == "错误" and at.endswith(where) and text in m for lv, at, m in items), items


def test_restraints_warnings(proj):
    m = _multi(restraints=[dict(expr="e0", value=0, sigma=1)])
    m["params"]["e0"] = dict(value=0.0, vary=False)
    items = _mm(proj, m)
    assert any(lv == "警告" and "固定参数" in x for lv, _, x in items) and not any(lv == "错误" for lv, _, _ in items)
    m = _multi(restraints=[dict(expr="unused", value=0, sigma=1)])
    m["params"]["unused"] = 0.1
    items = _mm(proj, m)
    assert any(lv == "警告" and "不在任何路径中" in x for lv, _, x in items) and not any(lv == "错误" for lv, _, _ in items)


def test_restraints_old_format(proj):
    m = _model(restraints=[dict(expr="nope", value=1, sigma=1)])
    (proj / "models").mkdir(exist_ok=True)
    (proj / "models" / "old.json").write_text(json.dumps(m), encoding="utf-8")
    items = [(lv, at, x) for lv, at, x in schema.validate(structures=False).items if "old.json" in at]
    assert any(lv == "错误" and "restraints[0] expr" in at and "nope" in x for lv, at, x in items), items


# ------------------------------------------------------------------ B6：σ² 温度模型
def _sg(sigma2="sigma2_debye(tempK, thD) + ss0", temps=(10, 100), **kw):
    """多数据集，每个数据集一个温度；θ 参数 thD 带 min。"""
    p = lambda s: [{"file": str(FEFF), "s02": "amp", "e0": "e0", "deltar": "dr", "sigma2": s}]  # noqa: E731
    m = dict(name="mm", kmin=3, kmax=14, rmin=1.4, rmax=3.0, kweight=2, window="kaiser", dk=4,
             params={"amp": 1.0, "e0": 0.0, "dr": 0.0, "thD": dict(value=300, min=50, max=2000), "ss0": 0.0},
             datasets=[dict(id="A", sample="cu_metal_rt", temperature=temps[0], paths=p(sigma2)),
                       dict(id="B", sample="cu_rt01", temperature=temps[1], paths=p(sigma2))])
    m.update(kw)
    return m


def _err(proj, m, where, text, level="错误"):
    items = _mm(proj, m)
    assert any(lv == level and where in at and text in x for lv, at, x in items), items
    return items


def test_sigma2_valid_clean(proj):
    assert _mm(proj, _sg()) == []


def test_sigma2_not_triggered_for_plain_models(proj):
    assert _mm(proj, _multi()) == []


def test_sigma2_error_in_params_expr(proj):
    m = _sg()
    m["params"]["bad"] = dict(expr="sigma2_debye(300, thD)")
    _err(proj, m, "params.bad", "只能写在路径的 sigma2 字段")


def test_sigma2_error_in_restraints(proj):
    _err(proj, _sg(restraints=[dict(expr="sigma2_eins(300, thD)", value=0.003, sigma=0.001)]),
         "restraints[0].expr", "只能写在路径的 sigma2 字段")


def test_sigma2_error_in_other_path_field(proj):
    m = _sg()
    m["datasets"][0]["paths"][0]["deltar"] = "sigma2_debye(10, thD)"
    _err(proj, m, "datasets[0].paths[0].deltar", "只能写在路径的 sigma2 字段")


@pytest.mark.parametrize("expr", ["sigma2_debye(tempK)", "sigma2_eins(tempK, thD, 1)",
                                  "sigma2_debye(t=tempK, theta=thD)"])
def test_sigma2_error_arg_count(proj, expr):
    _err(proj, _sg(expr), "paths[0].sigma2", "恰好 2 个位置参数")


def test_sigma2_error_tempk_without_temperature(proj):
    m = _sg()
    del m["datasets"][1]["temperature"]
    _err(proj, m, "datasets[1].paths[0].sigma2", "tempK")


@pytest.mark.parametrize("bad", [0, -3, "300", True])
def test_sigma2_error_bad_temperature(proj, bad):
    m = _sg()
    m["datasets"][0]["temperature"] = bad
    _err(proj, m, "datasets[0].temperature", "大于 0")


@pytest.mark.parametrize("name", ["tempK", "sigma2_debye", "sigma2_eins"])
def test_sigma2_error_reserved_param(proj, name):
    m = _sg()
    m["params"][name] = 1.0
    _err(proj, m, f"params.{name}", "保留名")


@pytest.mark.parametrize("th", [dict(value=300), dict(value=300, min=0), dict(value=300, min=-5), 300.0])
def test_sigma2_warn_theta_min(proj, th):
    m = _sg()
    m["params"]["thD"] = th
    items = _err(proj, m, "params.thD", "min", level="警告")
    assert not any(lv == "错误" for lv, _, _ in items)


def test_sigma2_no_warn_theta_fixed(proj):
    m = _sg()
    m["params"]["thD"] = dict(value=300, vary=False)
    assert _mm(proj, m) == []


def test_sigma2_warn_single_temperature(proj):
    items = _err(proj, _sg(temps=(100, 100)), "params.thD", "单一温度", level="警告")
    assert not any(lv == "错误" for lv, _, _ in items)


def test_sigma2_warn_single_dataset_old_format(proj):
    m = _model(temperature=300, params={"s02": 0.8, "thD": dict(value=300, min=50, max=2000)},
               paths=[{"file": str(FEFF), "sigma2": "sigma2_debye(tempK, thD)"}])
    (proj / "models").mkdir(exist_ok=True)
    (proj / "models" / "old.json").write_text(json.dumps(m), encoding="utf-8")
    items = [(lv, at, x) for lv, at, x in schema.validate(structures=False).items if "old.json" in at]
    assert any(lv == "警告" and "单一温度" in x for lv, _, x in items), items
    assert not any(lv == "错误" for lv, _, x in items), items
