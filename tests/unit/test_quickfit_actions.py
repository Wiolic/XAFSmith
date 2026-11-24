"""G1：快速拟合判定后的操作按钮映射（纯函数，不需要 Qt）。"""
from xafsmith.qt.pages.fitting.quick_fit import ACTIONS, item_actions, rmax_target
from xafsmith.quickfit import VerdictItem


def _fail(code, level="fail"):
    return VerdictItem(level, code, "x", "x")


def test_rmax_target_rounds_and_has_floor():
    assert rmax_target(2.5, 1.9) == 2.3
    assert rmax_target(2.3, 2.1) == 2.1          # 恰好等于 R_CIF：仍可点
    assert rmax_target(2.25, 1.0) == 2.05        # round(…, 2)
    assert rmax_target(2.2, 2.1) is None          # 低于 R_CIF：不画


def test_rmax_button_text_and_floor():
    a = item_actions(_fail("rmax_leak"), 2.5, 1.9)
    assert [x[0] for x in a] == ["rmax"] and "2.3" in a[0][1] and "2.3" in a[0][2]
    assert item_actions(_fail("rmax_leak"), 2.1, 1.9)             # 2.1 − 0.2 = 1.9 = R_CIF → 刚好可以
    assert item_actions(_fail("rmax_leak"), 2.0, 1.9) == []       # 1.8 < 1.9 → 不画
    assert item_actions(_fail("rmax_leak")) == []                 # 没有窗口信息


def test_mixed_phase_uses_shorter_rcif():
    # 调用方传 min(R_CIF)：2.0 与 2.7 取 2.0
    assert item_actions(_fail("rmax_leak"), 2.3, min(2.0, 2.7))
    assert not item_actions(_fail("rmax_leak"), 2.1, min(2.0, 2.7))


def test_mapping_per_design():
    for c in ("peak_pos", "r_cif", "dr", "rfactor"):
        assert [x[0] for x in item_actions(_fail(c))] == ["structure"]
    assert [x[0] for x in item_actions(_fail("e0"))] == ["structure", "calib"]
    assert [x[0] for x in item_actions(_fail("n_ratio"))] == ["s02"]
    for c in ("nvarys", "err_none", "err_big", "at_bound", "correl", "noise", "sigma2_neg", "sigma2_big"):
        assert [x[0] for x in item_actions(_fail(c))] == ["detailed"]


def test_only_fail_level_gets_buttons():
    for lvl in ("pass", "note"):
        assert item_actions(_fail("r_cif", lvl)) == []
    assert item_actions(_fail("unknown_code")) == []
    assert "rmax_leak" in ACTIONS
