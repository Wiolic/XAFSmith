"""G4：读入时按能量猜的元素 / 吸收边要让用户确认（纯函数部分）。fe.060 的 XDAC 头里没有元素与边。"""
from pathlib import Path

import pytest

from xafsmith.qt.pages.process.load import apply_guess, confirm_guess, guess_for, guessed_groups
from xafsmith.readers import read_scan

PUB = Path(__file__).resolve().parents[1] / "data" / "demo_project" / "data" / "raw" / "public"


@pytest.fixture
def fe():
    return read_scan(PUB / "fe.060")


def test_guessed_groups_finds_only_guessed(fe):
    cu = read_scan(PUB / "cu_metal_rt.xdi")
    assert set(guessed_groups({"fe": fe, "cu": cu})) == {"fe"}


def test_apply_changes_element_edge_and_clears_flags(fe):
    assert (fe.element, fe.edge) == ("Fe", "K")
    el, ed = apply_guess(fe, "Cu")                       # 手改元素 → 边按中位能量重新猜
    assert fe.element == el == "Cu" and fe.edge == ed == "K"
    assert "element" not in fe.meta_guessed and "edge" not in fe.meta_guessed
    assert not guessed_groups({"fe": fe})


def test_confirm_keeps_values_and_other_flags(fe):
    fe.meta_guessed = ["element", "edge", "mode"]
    confirm_guess(fe)
    assert fe.meta_guessed == ["mode"] and (fe.element, fe.edge) == ("Fe", "K")


def test_guess_for_matches_common_guess_edge_and_rejects_bad_symbol(fe):
    assert guess_for(fe, "Fe") == ("Fe", "K")
    with pytest.raises(ValueError):
        guess_for(fe, "")
    with pytest.raises(ValueError):
        guess_for(fe, "Zz")
