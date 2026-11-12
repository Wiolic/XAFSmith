"""calib 单元测试。"""
from pathlib import Path

import numpy as np
import pytest
import xraydb

from xafsmith.calib import TIME_FORMATS, _parse_time, apply_shift, calibrate_reference, time_gap_hours
from xafsmith.readers import read_scan

DEMO_RAW = Path(__file__).resolve().parents[1] / "data" / "demo_project" / "data" / "raw" / "public"


def test_shift_invariance(cu):
    """物理不变量：能量整体 +3.0 eV → delta_e 变化 −3.0。"""
    d0 = calibrate_reference(cu)["delta_e"]
    cu.energy = cu.energy + 3.0
    d1 = calibrate_reference(cu)["delta_e"]
    print("calib delta_e change after +3 eV:", d1 - d0)
    assert abs((d1 - d0) + 3.0) < 0.01


def test_e_table(cu):
    """默认 e_table = xraydb.xray_edge('Cu','K').energy；给定则为“用户给定”。"""
    r = calibrate_reference(cu)
    assert r["e_table"] == pytest.approx(xraydb.xray_edge("Cu", "K").energy, abs=1e-12)
    assert "xraydb" in r["table_source"]
    r2 = calibrate_reference(cu, e_table=8979.0)
    assert r2["table_source"] == "用户给定" and r2["e_table"] == 8979.0


def test_regression_e0_meas(cu):
    """回归（本机首跑值）：Cu 箔 8980.49，Fe 箔 fe.060 7113.80。"""
    c = calibrate_reference(cu)["e0_meas"]
    fe = calibrate_reference(read_scan(DEMO_RAW / "fe.060"))["e0_meas"]
    print("Cu e0_meas:", c, " Fe fe.060 e0_meas:", fe)
    assert abs(c - 8980.49) < 0.05
    assert abs(fe - 7113.80) < 0.05


def test_apply_shift_not_cumulative(cu):
    raw = cu.energy.copy()
    apply_shift([cu], 1.0)
    apply_shift([cu], 2.0)
    np.testing.assert_allclose(cu.energy, raw + 2.0, rtol=0, atol=1e-12)
    np.testing.assert_array_equal(cu.energy_raw, raw)


@pytest.mark.parametrize("s", ["2001/06/26 22:27:31", "2001-06-26T22:27:31", "2001-06-26 22:27:31",
                               "Tue Jun 26 22:27:31 2001"])
def test_parse_time_formats(s):
    assert len(TIME_FORMATS) == 4
    t = _parse_time(s)
    assert (t.year, t.month, t.day, t.hour) == (2001, 6, 26, 22)


def test_time_gap_unparseable():
    assert time_gap_hours("garbage", "2001-06-26T22:27:31") is None
    assert time_gap_hours("2001-06-26T22:00:00", "2001-06-26T23:30:00") == pytest.approx(1.5)
