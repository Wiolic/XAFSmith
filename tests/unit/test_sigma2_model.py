"""B6 ②：temperature 字段的规范化与取值顺序、tempK 词边界替换。"""
from pathlib import Path

import pytest

from xafsmith import fit_exafs as fx

CU = str(Path(__file__).resolve().parents[1] / "data" / "benchmark" / "feffcu01.dat")
PATH = dict(file=CU, label="Cu", s02="s02", e0="e0", deltar="dr", sigma2="sigma2_debye(tempK, thD) + ss0")
OLD = dict(name="m", sample="s1", kmin=3, kmax=12, rmin=1, rmax=2, params={"s02": 0.8}, paths=[PATH])
PLAIN = dict(PATH, sigma2="ss0")


def _multi(**top):
    return dict(name="j", kmin=3, kmax=12, rmin=1, rmax=2, kweight=2, params={}, **top,
                datasets=[dict(id="A", sample="a", temperature=10, paths=[PATH]),
                          dict(id="B", sample="b", paths=[PATH]),
                          dict(id="C", sample="c", temperature=300.5, paths=[PATH])])


def test_temperature_none_by_default():
    assert fx.normalize_model({**OLD, "paths": [PLAIN]})["datasets"][0]["temperature"] is None


def test_temperature_old_format():
    assert fx.normalize_model({**OLD, "temperature": 77})["datasets"][0]["temperature"] == 77.0


def test_temperature_dataset_over_top():
    a, b, c = fx.normalize_model(_multi(temperature=100))["datasets"]
    assert (a["temperature"], b["temperature"], c["temperature"]) == (10.0, 100.0, 300.5)
    m = _multi()
    m["datasets"][1]["paths"] = [PLAIN]
    assert fx.normalize_model(m)["datasets"][1]["temperature"] is None


@pytest.mark.parametrize("bad", [0, -5, "300", float("nan"), float("inf"), True, [300]])
def test_temperature_invalid(bad):
    with pytest.raises(ValueError, match="temperature"):
        fx.normalize_model({**OLD, "temperature": bad})
    m = _multi()
    m["datasets"][0]["temperature"] = bad
    with pytest.raises(ValueError, match=r"datasets\[0\]\.temperature"):
        fx.normalize_model(m)


def _sigma2_exprs(nm):
    out = []
    for d in nm["datasets"]:
        for p in fx.build_paths(d, root=".").values():
            out.append(str(p.sigma2))
    return out


def test_tempk_substituted_per_dataset():
    nm = fx.normalize_model(_multi(temperature=100))
    got = _sigma2_exprs(nm)
    # 6.9：build_paths 先替换 tempK，再按路径几何展开 σ² 模型调用
    from larch.xafs import feffpath
    from xafsmith.sigma2 import expand_for_path
    fd = feffpath(str(Path(nm["datasets"][0]["paths"][0]["file"])))._feffdat
    assert got == [expand_for_path(f"sigma2_debye({t}, thD) + ss0", fd) for t in ("10.0", "100.0", "300.5")]


def test_tempk_word_boundary_and_other_fields():
    assert fx._subst_tempk("tempK2 + tempK + mytempK + tempK_x + tempK*2", 100, "x") == \
        "tempK2 + 100.0 + mytempK + tempK_x + 100.0*2"
    p = dict(PATH, sigma2="ss0", third="tempK*1e-5", N="tempK2")
    nm = fx.normalize_model({**OLD, "temperature": 50, "paths": [p]})
    (path,) = fx.build_paths(nm["datasets"][0], root=".").values()
    assert str(path.third) == "50.0*1e-5"


def test_tempk_without_temperature_raises():
    with pytest.raises(ValueError, match=r"paths\[0\]\.sigma2.*tempK"):
        fx.normalize_model(OLD)
    nm = fx.normalize_model({**OLD, "temperature": 5})          # build_paths 自身也防御
    nm["datasets"][0]["temperature"] = None
    with pytest.raises(ValueError, match=r"paths\[0\]\.sigma2.*tempK"):
        fx.build_paths(nm["datasets"][0], root=".")


@pytest.mark.parametrize("sigma2,text", [
    ("sigma2_debye(300)", "2 个位置参数"),
    ("ss0 + sigma2_eins(300, thD, 1)", "2 个位置参数"),
])
def test_normalize_raises_on_sigma2_errors(sigma2, text):
    with pytest.raises(ValueError, match=text):
        fx.normalize_model({**OLD, "paths": [dict(PATH, sigma2=sigma2)], "temperature": 1})


def test_normalize_raises_on_reserved_and_misplaced():
    with pytest.raises(ValueError, match="tempK"):
        fx.normalize_model({**OLD, "temperature": 1, "params": {"tempK": 1.0}})
    with pytest.raises(ValueError, match="deltar"):
        fx.normalize_model({**OLD, "temperature": 1, "paths": [dict(PATH, deltar="sigma2_debye(1, thD)")]})


def test_build_paths_does_not_mutate_model():
    nm = fx.normalize_model({**OLD, "temperature": 50})
    fx.build_paths(nm["datasets"][0], root=".")
    assert nm["datasets"][0]["paths"][0]["sigma2"] == "sigma2_debye(tempK, thD) + ss0"
