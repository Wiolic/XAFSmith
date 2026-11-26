"""E17：io.read_direct（GUI“直接读入文件”的逐文件读入）：自动识别、指定格式、按列号、.prj、元素覆盖；
并与 E17 前页面里的旧调用方式（read_scan(columns=…, fmt="columns")）逐位对照。"""
from pathlib import Path

import numpy as np
import pytest

from xafsmith import io as xio, paths

DEMO = Path(__file__).resolve().parents[1] / "data" / "demo_project"
PUB = DEMO / "data" / "raw" / "public"


@pytest.fixture(autouse=True)
def _root(monkeypatch):
    monkeypatch.setattr(paths, "ROOT", DEMO)


def _same(a, b):
    assert np.array_equal(a.energy, b.energy) and np.array_equal(a.mu, b.mu)
    for k in ("mode", "element", "edge", "format", "read_warnings", "label"):
        assert getattr(a, k, None) == getattr(b, k, None), k


def test_auto_detect_label_and_warnings():
    ((lab, g),) = xio.read_direct(PUB / "cu_metal_rt.xdi", fmt="auto", mode="auto")
    assert lab == "data/raw/public/cu_metal_rt.xdi" and g.label == lab
    assert g.format == "xdi" and g.element == "Cu" and g.edge == "K" and g.mode == "trans"
    assert isinstance(g.read_warnings, list)
    ref = xio.read_scan(PUB / "cu_metal_rt.xdi")
    ref.label = lab
    _same(g, ref)


def test_specified_format_and_mode():
    ((_, g),) = xio.read_direct(PUB / "cu_rt01.xmu", fmt="athena_xmu", mode="trans")
    assert g.format == "athena_xmu" and g.mode == "trans"
    with pytest.raises(xio.ReadError):
        xio.read_direct(PUB / "cu_metal_rt.xdi", fmt="no_such_format")


@pytest.mark.parametrize("f", ["cu_metal_rt.xdi", "cu_rt01.xmu", "fe.060", "fe2o3_rt1.xmu", "feo_rt1.xdi"])
@pytest.mark.parametrize("idx", [dict(energy=0, i0=1, it=2, **{"if": -1}, mu=-1), dict(energy=0, i0=-1, it=-1, **{"if": -1}, mu=1)])
def test_columns_by_index_equals_old_call(f, idx):
    ((_, g),) = xio.read_direct(PUB / f, fmt="columns_by_index", columns=idx)
    old = {k: v for k, v in idx.items() if v >= 0}                     # E17 前：按列号走 columns= 参数
    g0 = xio.read_scan(PUB / f, fmt="columns", columns=old, templates={})
    g0.label = g.label
    assert g.format == "columns"
    _same(g, g0)


def test_columns_by_index_errors_like_old_call():
    idx = dict(energy=0, i0=1, it=2, **{"if": -1}, mu=3)                # 只有 3 列：列号越界
    with pytest.raises(xio.ReadError) as new:
        xio.read_direct(PUB / "cu_rt01.xmu", fmt="columns_by_index", columns=idx)
    with pytest.raises(xio.ReadError) as old:
        xio.read_scan(PUB / "cu_rt01.xmu", fmt="columns", columns={k: v for k, v in idx.items() if v >= 0}, templates={})
    assert str(new.value) == str(old.value)


def test_saved_template_and_index_template_do_not_clash():
    tpl = {"mine": {"base": "columns", "energy": 0, "mu": 1}}
    ((_, a),) = xio.read_direct(PUB / "cu_rt01.xmu", fmt="mine", templates=tpl)
    ((_, b),) = xio.read_direct(PUB / "cu_rt01.xmu", fmt="columns_by_index", columns=dict(energy=0, mu=1), templates=tpl)
    _same(a, b)
    assert tpl == {"mine": {"base": "columns", "energy": 0, "mu": 1}}   # 传入的模板字典不被改动


def test_prj_returns_all_groups():
    got = xio.read_direct(PUB / "fe_athena.prj", fmt="auto", element="Zn")         # .prj：元素覆盖不生效
    ref = xio.read_prj(PUB / "fe_athena.prj")
    assert len(got) == len(ref) > 1
    assert [lab for lab, _ in got] == [f"fe_athena:{n}" for n in ref]
    assert all(g.element != "Zn" for _, g in got)
    assert len(xio.read_direct(PUB / "fe_athena.prj", fmt="prj")) == len(ref)


def test_element_override_guesses_edge_from_energy():
    ((_, g),) = xio.read_direct(PUB / "cu_metal_rt.xdi", element="  Fe ")
    from xafsmith.common import guess_edge
    assert g.element == "Fe" and g.edge == guess_edge("Fe", float(np.median(g.energy)))
    ((_, g2),) = xio.read_direct(PUB / "cu_metal_rt.xdi", element="   ")      # 空白 = 不覆盖
    assert g2.element == "Cu"
