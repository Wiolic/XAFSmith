"""B1 T7：fit_exafs.normalize_model / dataset_of / model_path_files（纯函数，不跑拟合）。"""
import copy

import pytest

from xafsmith import fit_exafs as fx

P = [{"file": "output/feff/x/feff0001.dat", "label": "a"}]
OLD = dict(name="m", sample="s1", kmin=3, kmax=12, rmin=1, rmax=2, params={"s02": 0.8}, paths=P)


def test_old_format_one_dataset_with_v11_defaults():
    nm = fx.normalize_model(OLD)
    assert nm["multi"] is False and nm["name"] == "m" and nm["params"] == {"s02": 0.8}
    (d,) = nm["datasets"]
    assert d["id"] == "s1" and d["sample"] == "s1"
    assert (d["dk"], d["window"], d["fitspace"], d["kweight"]) == (1, "hanning", "r", 2)   # v1.1 run_fit 默认
    assert d["epsilon_k"] is None and d["paths"] == P


def test_old_format_ignores_epsilon_k_and_requires_ranges():
    assert fx.normalize_model({**OLD, "epsilon_k": 0.1})["datasets"][0]["epsilon_k"] is None
    bad = {k: v for k, v in OLD.items() if k != "rmax"}
    with pytest.raises(ValueError, match="rmax"):
        fx.normalize_model(bad)


def test_inheritance_dataset_over_top_over_builtin():
    m = dict(name="j", kmin=3, kmax=17, rmin=1.4, rmax=3.0, kweight=2, window="kaiser", params={},
             datasets=[dict(id="A", sample="s1", paths=P),
                       dict(sample="s2", kmax=14, dk=4, fitspace="k", epsilon_k=0.002, paths=P)])
    a, b = fx.normalize_model(m)["datasets"]
    assert (a["kmax"], a["window"], a["dk"], a["fitspace"], a["epsilon_k"]) == (17, "kaiser", 1, "r", None)
    assert (b["id"], b["kmax"], b["dk"], b["fitspace"], b["epsilon_k"]) == ("s2", 14, 4, "k", 0.002)


def test_input_not_modified():
    m = dict(name="j", kmin=3, kmax=17, rmin=1, rmax=3, kweight=2, params={"a": 1},
             datasets=[dict(sample="s1", paths=P)])
    before = copy.deepcopy(m)
    nm = fx.normalize_model(m)
    nm["datasets"][0]["paths"].append({"file": "z"})
    nm["params"]["b"] = 2
    assert m == before
    o = copy.deepcopy(OLD)
    fx.normalize_model(o)["datasets"][0]["paths"].clear()
    assert o == OLD


@pytest.mark.parametrize("ds,where", [
    (dict(paths=P), "datasets[0].sample"),
    (dict(sample="s1"), "datasets[0].paths"),
    (dict(sample="s1", paths=[]), "datasets[0].paths"),
])
def test_missing_dataset_field(ds, where):
    m = dict(name="j", kmin=3, kmax=17, rmin=1, rmax=3, kweight=2, params={}, datasets=[ds])
    with pytest.raises(ValueError, match=where.replace("[", r"\[").replace("]", r"\]")):
        fx.normalize_model(m)


def test_missing_range_after_merge_and_other_errors():
    m = dict(name="j", kmin=3, kmax=17, rmin=1, kweight=2, params={},
             datasets=[dict(sample="s1", paths=P), dict(sample="s2", paths=P, rmax=3)])
    with pytest.raises(ValueError, match=r"datasets\[0\]\.rmax"):
        fx.normalize_model(m)
    with pytest.raises(ValueError, match="非空"):
        fx.normalize_model(dict(m, datasets=[]))
    with pytest.raises(ValueError, match="重复"):
        fx.normalize_model(dict(m, rmax=3, datasets=[dict(sample="s1", paths=P), dict(sample="s1", paths=P)]))
    with pytest.raises(ValueError, match="顶层 sample"):
        fx.normalize_model(dict(m, rmax=3, sample="s1", datasets=[dict(sample="s1", paths=P)]))


def test_dataset_of_and_path_files():
    m = dict(name="j", kmin=3, kmax=17, rmin=1, rmax=3, kweight=2, params={},
             datasets=[dict(id="A", sample="s1", paths=P),
                       dict(id="B", sample="s2", paths=[{"file": "f2.dat"}, {"file": "f3.dat"}])])
    assert fx.dataset_of(m, "B")["sample"] == "s2"
    assert fx.dataset_of(m, "s1")["id"] == "A"
    with pytest.raises(KeyError):
        fx.dataset_of(m, "C")
    assert fx.dataset_of(OLD, "whatever")["sample"] == "s1"
    assert fx.model_path_files(m) == [P[0]["file"], "f2.dat", "f3.dat"]
    assert fx.model_path_files(OLD) == [P[0]["file"]]
    assert fx.is_multi(m) and not fx.is_multi(OLD)


# ------------------------------------------------------------------ B3 restraints
def test_restraints_normalized_old_and_multi():
    rs = [dict(expr="s02", value="0.8", sigma=0.05), dict(name="x", expr="a-b", value=0, sigma=1, note="n")]
    nm = fx.normalize_model({**OLD, "restraints": rs})
    assert nm["restraints"] == [dict(name="r1", expr="s02", value=0.8, sigma=0.05, note=""),
                                dict(name="x", expr="a-b", value=0.0, sigma=1.0, note="n")]
    assert isinstance(nm["restraints"][0]["value"], float)
    m = dict(name="j", kmin=3, kmax=17, rmin=1, rmax=3, kweight=2, params={}, restraints=rs,
             datasets=[dict(sample="s1", paths=P)])
    assert fx.normalize_model(m)["restraints"] == nm["restraints"]
    assert fx.normalize_model(OLD)["restraints"] == []
    assert fx.normalize_model({**OLD, "restraints": []})["restraints"] == []


def test_restraints_input_not_modified():
    rs = [dict(expr="s02", value=0.8, sigma=0.05)]
    m = {**OLD, "restraints": rs}
    before = copy.deepcopy(m)
    fx.normalize_model(m)["restraints"][0]["expr"] = "zzz"
    assert m == before


@pytest.mark.parametrize("rs,where", [
    ("x", "restraints"),
    (["x"], r"restraints\[0\]"),
    ([dict(value=1, sigma=1)], r"restraints\[0\]\.expr"),
    ([dict(expr="a", sigma=1)], r"restraints\[0\]\.value"),
    ([dict(expr="a", value=1)], r"restraints\[0\]\.sigma"),
    ([dict(expr=" ", value=1, sigma=1)], r"restraints\[0\]\.expr"),
    ([dict(expr="a", value="x", sigma=1)], r"restraints\[0\]\.value"),
    ([dict(expr="a", value=float("nan"), sigma=1)], r"restraints\[0\]\.value"),
    ([dict(expr="a", value=1, sigma=0)], r"restraints\[0\]\.sigma"),
    ([dict(expr="a", value=1, sigma=-1)], r"restraints\[0\]\.sigma"),
    ([dict(expr="a", value=1, sigma=1, name="")], r"restraints\[0\]\.name"),
    ([dict(expr="a", value=1, sigma=1), dict(expr="a", value=1, sigma=1, name="r1")], r"restraints\[1\]\.name"),
])
def test_restraints_errors(rs, where):
    with pytest.raises(ValueError, match=where):
        fx.normalize_model({**OLD, "restraints": rs})
