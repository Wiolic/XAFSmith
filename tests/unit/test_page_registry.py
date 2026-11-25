"""页面注册：导航表由页面类属性推导，必须与 32f8eb7 时 qt/app.py 里的字面值完全相等。"""
import pytest

pytest.importorskip("PySide6")

from xafsmith.qt import app  # noqa: E402

# 以下字面值抄自 32f8eb7 的 src/xafsmith/qt/app.py
OLD_TABBED = {"spectra": ("load", "qc", "calib")}
OLD_PARENT = {k: g for g, ks in OLD_TABBED.items() for k in ks}
OLD_HIDDEN = {"home"}
OLD_NEEDS = {"norm": ("groups",), "chi": ("groups",), "wavelet": ("groups",), "lcf": ("groups",), "xanes": ("groups",),
             "fit": ("groups", "feff"), "pubfig": ("groups",)}
OLD_NO_PROJECT = ("home", "planner", "elements", "help")
OLD_SPEC_KEYS = [
    "home", "data", "batch",
    None,
    "spectra", "norm",
    "chi", "wavelet",
    None,
    "feff", "fit", "history", "lcf",
    "xanes",
    None,
    "summary", "pubfig", "methods",
    None,
    "planner", "elements", "agent", "help",
]


def test_tables_equal_old_literals():
    assert app.TABBED == OLD_TABBED
    assert app.PARENT == OLD_PARENT
    assert app.HIDDEN == OLD_HIDDEN
    assert app.NEEDS == OLD_NEEDS
    assert app.NO_PROJECT == OLD_NO_PROJECT
    assert tuple(app.NEEDS["fit"]) == ("groups", "feff")


def test_page_specs_keys_and_shape():
    specs = app.page_specs()
    assert [None if s is None else s[0] for s in specs] == OLD_SPEC_KEYS
    for s in specs:
        if s is not None:
            assert s[0] == s[1].key


def test_sub_pages_keys_and_titles():
    assert [c.key for c in app.SpectraTabs.sub_pages] == ["load", "qc", "calib"]
    for cls in [s[1] for s in app.page_specs() if s] + list(app.SpectraTabs.sub_pages):
        assert cls.title_zh and cls.title_en and cls.key
