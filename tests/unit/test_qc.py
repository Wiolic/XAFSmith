"""E18：qc.py（数据质量检查）的单元测试。用演示项目的公开数据；数值期望为快照（E18 时代码的输出），其余为结构 / 物理性质。"""
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest

from xafsmith import qc
from xafsmith.readers import read_scan

PUBLIC = Path(__file__).resolve().parents[1] / "data" / "demo_project" / "data" / "raw" / "public"


def test_glitches_finds_the_spike_and_ignores_smooth_data():
    e = np.linspace(0, 100, 201)
    mu = np.ones(201)
    assert qc.glitches(e, mu) == []
    mu[100] += 5.0
    found = qc.glitches(e, mu)
    assert 50.0 in found                                   # 尖峰所在点
    assert all(abs(x - 50.0) <= 0.5 + 1e-9 for x in found)  # 其余只可能是它的两个邻点（二阶差分）


def test_glitches_e0_restricts_to_post_edge():
    e = np.linspace(0, 100, 201)
    mu = np.ones(201)
    mu[20] += 5.0                                          # E = 10：在 e0 + 30 之前
    assert qc.glitches(e, mu, e0=20.0) == []               # e0=20 → 只看 E > 50
    assert qc.glitches(e, mu, e0=None) != []


def test_deglitch_removes_points_and_records_ranges():
    n = 100
    e = np.linspace(8000, 9000, n)
    g = SimpleNamespace(energy=e.copy(), energy_raw=e.copy(), mu=np.arange(n, dtype=float), i0=np.ones(n), i1=None, ifl=np.ones(5))
    removed = qc.deglitch(g, [[8100.0, 8200.0], [8500.0, 8510.0]])
    keep = ~(((e >= 8100) & (e <= 8200)) | ((e >= 8500) & (e <= 8510)))
    assert removed == int((~keep).sum()) and removed > 0
    assert len(g.energy) == len(g.mu) == len(g.i0) == len(g.energy_raw) == n - removed
    assert len(g.ifl) == 5 and g.i1 is None               # 长度不同的数组不动
    assert g.deglitched == [[8100.0, 8200.0], [8500.0, 8510.0]]
    assert not ((g.energy >= 8100) & (g.energy <= 8200)).any()


def test_i0_drops():
    i0 = np.full(50, 1000.0)
    i0[20] = 100.0
    assert [int(i) for i in qc.i0_drops(i0)] == [20]
    assert qc.i0_drops(None) == []
    assert qc.i0_drops(np.full(50, 1000.0)) == []


@pytest.fixture(scope="module")
def cu_row():
    return qc.check(read_scan(PUBLIC / "cu_metal_rt.xdi"))


def test_check_cu_foil_fields(cu_row):
    r = cu_row
    assert r["element"] == "Cu" and r["edge"] == "K" and r["mode"] == "trans"
    assert r["monotonic"] is True and r["step_min"] > 0 and r["step_max"] >= r["step_min"]
    assert r["emin"] < r["e0"] < r["emax"]
    assert r["npts"] == 408                                           # 快照（E18 时代码的输出）
    assert r["e0"] == pytest.approx(8980.485, abs=0.01)               # 快照；Cu K 边表值 8979 eV 附近
    assert r["edge_step_mu"] == pytest.approx(2.769, rel=1e-3)        # 快照
    assert r["delta_mut"] == r["edge_step_mu"]                        # 透射：边跳 = Δμt
    assert r["i0_drops"] == 0 and r["i0_min"] > 0
    assert r["n_glitches"] > 0 and len(r["glitch_E"].split(";")) == min(r["n_glitches"], 10)   # glitch_E 最多列 10 个
    assert "autobk_error" not in r
    assert 0 < r["epsilon_k"] < 0.01 and 0 < r["epsilon_r"] < 0.1     # 快照量级
    assert 3 < r["k_snr3"] <= r["kmax_data"]
    assert r["harmonics"]


def test_run_returns_one_row_per_group_and_writes_csv(tmp_path):
    groups = [read_scan(PUBLIC / "cu_metal_rt.xdi"), read_scan(PUBLIC / "ni_metal_rt.xdi")]
    out = tmp_path / "qc_report.csv"
    df = qc.run(groups, out=out)
    assert list(df["element"]) == ["Cu", "Ni"] and len(df) == 2
    back = pd.read_csv(out, encoding="utf-8-sig")
    assert list(back.columns) == list(df.columns) and len(back) == 2
    assert back["npts"].tolist() == df["npts"].tolist()
    assert qc.run([]).empty
