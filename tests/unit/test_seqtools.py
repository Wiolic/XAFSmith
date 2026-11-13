"""C2：联合拟合序列工具——σ² 各数据集独立（命名、初值、幂等）、路径勾选同步；合成数据上“共用 → 同值，独立 → 各自接近真值”。"""
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from xafsmith import seqtools as st

TESTS = Path(__file__).resolve().parents[1]
FEFF = str(TESTS / "data" / "benchmark" / "feffcu01.dat")


def _tab(sig, use=True, rows=1):
    return pd.DataFrame([dict(use=use, label=f"p{j}", N="", s02="s02", e0="e0", deltar="dr1", sigma2=sig, third="",
                              dir="d", file=f"feff000{j + 1}.dat") for j in range(rows)])


def _par(*names):
    return pd.DataFrame([dict(name=n, value=0.004, vary=True, min=0.0, max=0.05, expr="") for n in names],
                        columns=st.PARAM_COLS)


def test_param_names():
    assert st.param_names("ss1*1.5") == ["ss1"]
    assert st.param_names("sigma2_debye(tempK, thD) + ss0") == ["thD", "ss0"]
    assert st.param_names("0.003") == [] and st.param_names("1e-3") == []
    assert st.param_names("sqrt(ss1)+ss2*pi") == ["ss1", "ss2"]
    assert st.param_names(None) == [] and st.param_names("") == []


def test_independent_renames_shared_sigma2_with_whole_word_and_expression():
    t = {"IrTa_100": _tab("ss1*1.5"), "IrTa 200": _tab("ss1*1.5")}
    p = _par("ss1")
    p.loc[0, ["value", "vary", "min", "max", "expr"]] = [0.0123, False, 0.001, 0.04, "x"]
    nt, np_, ch = st.sigma2_independent(t, p)
    assert nt["IrTa_100"].at[0, "sigma2"] == "ss1_IrTa_100*1.5"
    assert nt["IrTa 200"].at[0, "sigma2"] == "ss1_IrTa_200*1.5"          # id 中的空格 → _
    assert ch == [("IrTa_100", "ss1", "ss1_IrTa_100"), ("IrTa 200", "ss1", "ss1_IrTa_200")]
    new = np_[np_.name.str.startswith("ss1_")]
    assert len(new) == 2
    for _, r in new.iterrows():                                            # 新参数复制 value/vary/min/max/expr
        assert (r.value, r.vary, r["min"], r["max"], r.expr) == (0.0123, False, 0.001, 0.04, "x")
    assert t["IrTa_100"].at[0, "sigma2"] == "ss1*1.5"                      # 输入不被修改
    assert len(p) == 1


def test_independent_only_shared_names_and_only_used_rows():
    t = {"A": pd.concat([_tab("ss1"), _tab("ssA_only").assign(file="f2")], ignore_index=True),
         "B": pd.concat([_tab("ss1"), _tab("ss9", use=False).assign(file="f2")], ignore_index=True)}
    nt, _, ch = st.sigma2_independent(t, _par("ss1", "ssA_only", "ss9"))
    assert [c[1] for c in ch] == ["ss1", "ss1"]                           # 只出现在一个数据集的名字不改
    assert nt["A"].at[1, "sigma2"] == "ssA_only" and nt["B"].at[1, "sigma2"] == "ss9"


def test_independent_idempotent_and_collisions():
    t = {"A": _tab("ss1"), "B": _tab("ss1")}
    nt, np_, ch = st.sigma2_independent(t, _par("ss1"))
    nt2, np2, ch2 = st.sigma2_independent(nt, np_)
    assert ch2 == [] and nt2["A"].at[0, "sigma2"] == "ss1_A" and len(np2) == len(np_)
    # 撞名：参数表里已有 ss1_A → 加 _2
    _, np3, ch3 = st.sigma2_independent(t, _par("ss1", "ss1_A"))
    assert ("A", "ss1", "ss1_A_2") in ch3 and ("B", "ss1", "ss1_B") in ch3
    # 已带本数据集后缀的不再加
    t4 = {"A": _tab("ss1_A"), "B": _tab("ss1_A")}
    _, _, ch4 = st.sigma2_independent(t4, _par("ss1_A"))
    assert ch4 == [("B", "ss1_A", "ss1_A_B")]


def test_independent_param_missing_from_table_is_still_renamed():
    nt, np_, ch = st.sigma2_independent({"A": _tab("ss1"), "B": _tab("ss1")}, _par())
    assert len(ch) == 2 and len(np_) == 0 and nt["B"].at[0, "sigma2"] == "ss1_B"


def test_sync_use():
    a = _tab("ss1", rows=3)
    b = _tab("ss1", rows=2).assign(use=[True, False])
    c = pd.DataFrame(columns=a.columns)                                     # 没有这些行
    t = {"A": a, "B": b, "C": c}
    assert st.sync_targets(t, "A", ("d", "feff0001.dat"), True) == []       # B 已是 True
    assert st.sync_targets(t, "A", ("d", "feff0002.dat"), True) == [("B", 1)]
    assert st.sync_targets(t, "A", ("d", "feff0003.dat"), False) == []      # B 没有这一行 → 跳过
    assert st.sync_use(t, "A", ("d", "feff0002.dat"), True) == [("B", 1)]
    assert bool(t["B"].at[1, "use"]) is True
    assert b.at[0, "N"] == "" and t["B"].at[1, "sigma2"] == "ss1"           # 只动 use，不动表达式


# ------------------------------------------------------------------ 合成数据：共用 vs 独立
@pytest.fixture(scope="module")
def synth():
    from larch import Group
    from larch.xafs import feffpath, path2chi
    k = np.arange(0, 17.0, 0.05)
    out = {}
    for sid, ss in (("A", 0.004), ("B", 0.008)):
        p = feffpath(FEFF, s02=0.9, e0=0.0, deltar=0.0, sigma2=ss)
        path2chi(p, k=k)
        out[sid] = Group(k=k, chi=np.array(p.chi))
    return out


def _model(sig_a, sig_b, params):
    def path(ss):
        return dict(file=FEFF, label="Cu", s02="amp", e0="de", deltar="dr", sigma2=ss)
    return {"name": "synth", "kmin": 3, "kmax": 14, "dk": 2, "window": "hanning", "kweight": 2, "rmin": 1.2, "rmax": 3.0,
            "fitspace": "r", "params": params,
            "datasets": [dict(id="A", sample="A", paths=[path(sig_a)]), dict(id="B", sample="B", paths=[path(sig_b)])]}


def test_shared_gives_one_value_and_independent_recovers_each(synth):
    from xafsmith import fit_exafs as fx
    base = {"amp": {"value": 0.9, "vary": False}, "de": 0.0, "dr": 0.0, "ss1": 0.005}
    _, _, s_shared = fx.fit_multi(synth, _model("ss1", "ss1", base))
    v = s_shared["params"]["ss1"]["value"]
    assert 0.004 < v < 0.008                                               # 共用：一个居中的值
    rows = {r["dataset"]: r["sigma2"] for r in s_shared["paths"]}
    assert rows["A"] == rows["B"]
    nt, np_, ch = st.sigma2_independent({"A": _tab("ss1"), "B": _tab("ss1")}, _par("ss1"))
    sa, sb = nt["A"].at[0, "sigma2"], nt["B"].at[0, "sigma2"]
    assert (sa, sb) == ("ss1_A", "ss1_B")
    params = dict(base)
    del params["ss1"]
    for n in (sa, sb):
        params[n] = 0.005
    _, _, s_ind = fx.fit_multi(synth, _model(sa, sb, params))
    rows = {r["dataset"]: r["sigma2"] for r in s_ind["paths"]}
    assert rows["A"] == pytest.approx(0.004, abs=2e-5) and rows["B"] == pytest.approx(0.008, abs=2e-5)
    assert abs(rows["A"] - rows["B"]) > 0.003
