"""E4：处理参数页不改写配置里已有的取值（norm2=0、larch 支持的任意窗、FT kweight 列表）。离屏 Qt。"""
import pytest

pytest.importorskip("PySide6")
from PySide6.QtWidgets import QApplication

from xafsmith.qt import widgets as W
from xafsmith.qt.pages import project as pp


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


def test_norm2_shown():
    assert pp.norm2_shown(None) == -10
    assert pp.norm2_shown(0) == 0            # 旧写法 `or -10` 把 0 改成 −10
    assert pp.norm2_shown(-25.0) == -25.0
    assert pp.norm2_shown(800.0) == 800.0


def test_windows_are_larch_full_set():
    from larch.xafs.xafsutils import FT_WINDOWS_SHORT
    assert sorted(w[:3] for w in pp.FT_WINDOW_NAMES) == sorted(FT_WINDOWS_SHORT)


@pytest.mark.parametrize("base,cur,want", [
    ([1, 2, 3], 2, [1, 2, 3]),
    ([1, 2, 3], [1, 2, 3], [1, 2, 3, [1, 2, 3]]),
    (pp.FT_WINDOW_NAMES, "parzen", pp.FT_WINDOW_NAMES),
    (pp.FT_WINDOW_NAMES, "Kaiser-Bessel", pp.FT_WINDOW_NAMES + ["Kaiser-Bessel"]),
    ([1, 2, 3], None, [1, 2, 3]),
])
def test_options_keeping(base, cur, want):
    assert pp.options_keeping(base, cur) == want


@pytest.mark.parametrize("base,cur", [
    ([1, 2, 3], [1, 2, 3]), ([1, 2, 3], [2, 3]), ([1, 2, 3], 3),
    (pp.FT_WINDOW_NAMES, "welch"), (pp.FT_WINDOW_NAMES, "gaussian"), (pp.FT_WINDOW_NAMES, "Kaiser-Bessel"),
])
def test_combo_round_trip(app, base, cur):
    """未改动时 value() 原样返回配置里的值（旧代码：窗被改成 hanning、列表 kweight 崩溃）。"""
    cb = W.combo(pp.options_keeping(base, cur), cur)
    assert cb.value() == cur


def test_norm2_widget_round_trip(app):
    w = W.num(pp.norm2_shown(0), step=10)
    assert w.value() == 0
