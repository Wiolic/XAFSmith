"""paths.Project：set_root 后的大写模块变量与 current() 的属性一致；名字集合与旧实现相同。"""
import os

import pytest

from xafsmith import paths

OLD_NAMES = [
    "ROOT", "CONFIG", "PROJECT_MD", "DATA", "RAW", "META", "STRUCT", "MODELS", "NOTES", "SCRIPTS", "OUT",
    "QC", "CALIB", "PROC", "FEFF", "FITS", "LCF", "XANES", "FIGS", "PUBFIGS", "REPORTS", "GUI",
    "CALIB_JSON", "QC_CSV", "FITS_CSV", "LCF_CSV", "XANES_CSV", "INPUT_DIRS", "OUTPUT_DIRS",
]


@pytest.fixture
def restore_root():
    old = paths.ROOT
    env = os.environ.get("XAFSMITH_PROJECT")
    yield
    paths.set_root(old)
    if env is None:
        os.environ.pop("XAFSMITH_PROJECT", None)
    else:
        os.environ["XAFSMITH_PROJECT"] = env


def test_module_vars_keys():
    assert len(OLD_NAMES) == 29
    assert set(paths.Project.from_root(".").module_vars()) == set(OLD_NAMES)


def test_set_root_matches_current(tmp_path, restore_root):
    for name in ("a", "b"):
        root = tmp_path / name
        root.mkdir()
        ret = paths.set_root(root)
        p = paths.current()
        assert ret == root.resolve() == p.root
        assert os.environ["XAFSMITH_PROJECT"] == str(root.resolve())
        for n in OLD_NAMES:
            assert getattr(paths, n) == getattr(p, n.lower()), n
        assert paths.PUBFIGS == root.resolve() / "output" / "figs" / "journal"
        assert paths.INPUT_DIRS == (p.raw, p.struct, p.models, p.notes)
