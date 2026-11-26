"""services 里的模型字典拼装纯函数（E17）：与 E17 前 fit_page.go() 的内联逻辑（下面照抄的 _old_*）逐字节对照。"""
import json

import numpy as np
import pandas as pd
import pytest

from xafsmith import services
from xafsmith.defaults import FIT_PARAM_DEFAULTS


# ---- E17 前的旧逻辑（照抄自 fit_page._model_cards 的 rebuild_params / go）
def _old_default(n):
    defaults = {"s02": (0.85, True, 0.3, 1.5), "e0": (0.0, True, -15, 15)}
    v, vary, lo, hi = defaults.get(n, (300.0, True, 50.0, 2000.0) if n.startswith(("thD", "thE")) else
                                   (0.0, True, None, None) if n.startswith("ss0_") else
                                   (0.003, True, 0.0, 0.05) if n.startswith("ss") else
                                   (0.0, True, -0.5, 0.5) if n.startswith("dr") else (1.0, True, None, None))
    return dict(name=n, value=v, vary=vary, min=lo, max=hi, expr="")


def _old_params(t):
    params = {}
    for _, r in t.iterrows():
        if isinstance(r.expr, str) and r.expr.strip():
            params[r["name"]] = {"expr": r.expr}
        else:
            params[r["name"]] = {"value": float(r.value), "vary": bool(r.vary),
                                 "min": None if pd.isna(r["min"]) else float(r["min"]),
                                 "max": None if pd.isna(r["max"]) else float(r["max"])}
    return params


def _old_mk_paths(used):
    mpaths = []
    for _, r in used.iterrows():
        d = dict(file=r.file, label=r.label, s02=r.s02, e0=r.e0, deltar=r.deltar, sigma2=r.sigma2)
        if str(r.N).strip():
            d["N"] = str(r.N)
        if isinstance(r.third, str) and r.third.strip():
            d["third"] = r.third
        if isinstance(r.note, str) and r.note.strip():
            d["note"] = r.note.strip()
        mpaths.append(d)
    return mpaths


def _old_model(st, name, params, norm, bkg, restraints, multi, keys, ids, over, tvals, used_by, data_k):
    rng = dict(kmin=st["kmin"], kmax=st["kmax"], dk=st["dk"], window=st["win"], kweight=st["kws"] or [2],
               rmin=st["rmin"], rmax=st["rmax"], fitspace=st["space"])
    extra = dict(restraints=restraints) if restraints else {}
    if multi:
        dsl = []
        for k in keys:
            d = dict(id=ids[k], sample=k)
            d.update(over[k])
            if k in tvals:
                d["temperature"] = tvals[k]
            d["paths"] = _old_mk_paths(used_by[k])
            dsl.append(d)
        return dict(name=name, params=params, **rng, datasets=dsl, norm=dict(norm), bkg=dict(bkg), **extra)
    model = dict(name=name, sample=data_k, **rng, params=params, paths=_old_mk_paths(used_by[data_k]),
                 norm=dict(norm), bkg=dict(bkg), **extra)
    if data_k in tvals:
        model["temperature"] = tvals[data_k]
    return model


ST = dict(kmin=3.0, kmax=12.0, dk=1.0, win="hanning", kws=[1, 2, 3], rmin=1.0, rmax=3.0, space="r")
NORM = dict(pre1=-150, pre2=-30)
BKG = dict(rbkg=1.0, kweight=2)


def _ptab(rows):
    cols = ["use", "label", "N", "s02", "e0", "deltar", "sigma2", "third", "note", "file"]
    return pd.DataFrame(rows, columns=cols)


def _used():
    return _ptab([
        [True, "O@2.0", "6", "s02", "e0", "dr1", "ss1", "", "  note a ", "f1.dat"],
        [True, "Ir@3.1", "", "s02", "e0", "dr2", "ss2*1.5", "c3_a", "", "f2.dat"],
        [True, "O@3.5", "  ", "s02", "e0", "dr1", "ss1", None, None, "f3.dat"]])


def _ptable():
    return pd.DataFrame(dict(
        name=["s02", "e0", "ss1", "dr1", "ss2", "c"], value=[0.85, 1.234567891, 0.003, 0.0, 0.0, 1.0],
        vary=[True, True, False, True, True, True], min=[0.3, np.nan, 0.0, -0.5, np.nan, np.nan],
        max=[1.5, 15, np.nan, 0.5, np.nan, np.nan], expr=["", "", "", "", "ss1*2", ""]))


@pytest.mark.parametrize("name", ["s02", "e0", "thD", "thE1", "ss0_x", "ss0", "ss1", "ssA", "dr1", "dr", "foo", "N_x", "e0x"])
def test_default_param_row_equals_old(name):
    assert services.default_param_row(name) == _old_default(name)
    assert FIT_PARAM_DEFAULTS["exact"]["s02"] == (0.85, True, 0.3, 1.5)


def test_params_from_table_expr_nan_and_bytes():
    t = _ptable()
    p = services.params_from_table(t)
    assert p == _old_params(t)
    assert p["ss2"] == {"expr": "ss1*2"}
    assert p["e0"]["min"] is None and p["ss1"]["max"] is None and p["s02"]["max"] == 1.5
    assert json.dumps(p) == json.dumps(_old_params(t))


def test_paths_from_table_conditions():
    u = _used()
    p = services.paths_from_table(u)
    assert p == _old_mk_paths(u)
    assert "N" in p[0] and "N" not in p[1] and "N" not in p[2]          # N 空 / 全空白不写
    assert p[0]["note"] == "note a" and "note" not in p[1]              # note strip；空不写
    assert p[1]["third"] == "c3_a" and "third" not in p[2]              # None 不写
    assert services.paths_from_table(u.iloc[0:0]) == []                 # N 空表


@pytest.mark.parametrize("temp", [None, 300.0])
@pytest.mark.parametrize("restr", [None, [], [{"expr": "ss1-ss2", "lo": 0}]])
@pytest.mark.parametrize("kws", [[1, 2, 3], []])
def test_build_single_bytes_equal(temp, restr, kws):
    st = dict(ST, kws=kws)
    used = _used()
    prm = services.params_from_table(_ptable())
    tv = {"A.dat": temp} if temp is not None else {}
    old = _old_model(st, "m1", prm, NORM, BKG, restr, False, ["A.dat"], {"A.dat": "A"}, {}, tv, {"A.dat": used}, "A.dat")
    new = services.build_fit_model(name="m1", rng=st, params=prm, norm=NORM, bkg=BKG, restraints=restr,
                                   sample="A.dat", paths=services.paths_from_table(used), temperature=temp)
    assert json.dumps(new) == json.dumps(old)
    assert ("restraints" in new) == bool(restr) and ("temperature" in new) == (temp is not None)
    if not kws:
        assert new["kweight"] == [2]
    assert list(new)[-1] == ("temperature" if temp is not None else ("restraints" if restr else "bkg"))


@pytest.mark.parametrize("restr", [None, [{"expr": "a-b"}]])
def test_build_multi_bytes_equal(restr):
    keys = ["A.dat", "B.dat"]
    ids = {"A.dat": "A", "B.dat": "B"}
    over = {"A.dat": {}, "B.dat": {"kmin": 2.5, "rmax": 3.5}}
    tvals = {"B.dat": 77.0}
    used = _used()
    prm = services.params_from_table(_ptable())
    old = _old_model(ST, "j", prm, NORM, BKG, restr, True, keys, ids, over, tvals, {k: used for k in keys}, None)
    new = services.build_fit_model(
        name="j", rng=ST, params=prm, norm=NORM, bkg=BKG, restraints=restr,
        datasets=[dict(id=ids[k], sample=k, over=over[k], temperature=tvals.get(k), paths=services.paths_from_table(used))
                  for k in keys])
    assert json.dumps(new) == json.dumps(old)
    assert list(new)[:2] == ["name", "params"] and "temperature" not in new["datasets"][0]
    assert list(new["datasets"][1])[:5] == ["id", "sample", "kmin", "rmax", "temperature"]
