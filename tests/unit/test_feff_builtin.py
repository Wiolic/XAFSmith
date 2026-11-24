"""G2：用内置结构直接算 FEFF6L（快速拟合页的“用内置结构计算…”所用函数）。真实 FEFF6L，Cu 约几秒。"""
import pytest

from xafsmith import feff_wrap, paths


@pytest.fixture
def proj(tmp_path):
    old = paths.ROOT
    paths.set_root(tmp_path)
    yield tmp_path
    paths.set_root(old)


def test_default_edge():
    assert feff_wrap.default_edge("Cu") == "K" and feff_wrap.default_edge("Ir") == "L3"


def test_build_builtin_runs_then_reuses(proj):
    out, reused = feff_wrap.build_builtin("Cu", "Cu", "K")
    assert not reused and out == proj / "output" / "feff" / "Cu_CuK" / "site0" and (out / "feff0001.dat").exists()
    df = feff_wrap.list_paths(out)
    first = df[df["nleg"] == 2].sort_values("reff").iloc[0]
    assert first["degen"] == 12 and first["reff"] == pytest.approx(3.6149 / 2 ** 0.5, abs=2e-3)
    stamp = (out / "feff0001.dat").stat().st_mtime_ns
    out2, reused2 = feff_wrap.build_builtin("Cu", "Cu", "K")                 # 已有 → 直接选用，不重算
    assert reused2 and out2 == out and (out / "feff0001.dat").stat().st_mtime_ns == stamp
    out3, reused3 = feff_wrap.build_builtin("Cu", "Cu", "K", recompute=True)
    assert not reused3 and out3 == out and (out / "feff0001.dat").stat().st_mtime_ns != stamp


def test_wrong_absorber(proj):
    with pytest.raises(ValueError):
        feff_wrap.build_builtin("NiO", "Cu", "K")
