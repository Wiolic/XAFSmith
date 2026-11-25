"""Origin 导出：每次导出的文件夹名不重复（不覆盖）、originpro 模式下文件夹里只有 .opju。
originpro 用假模块代替（不启动 Origin）。"""
import sys
from unittest.mock import MagicMock

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402

from xafsmith import origin_export as oe  # noqa: E402


def _fig(ylabel="Normalized μ(E)"):
    fig, ax = plt.subplots()
    e = np.linspace(-20, 60, 50)
    ax.plot(e, np.tanh(e / 5) + 1, label="A")
    ax.set_xlabel("E − 11215 (eV)")
    ax.set_ylabel(ylabel)
    return fig


def test_stem_differs_by_kind_and_samples():
    a = oe.export_stem("fig", "xanes", ["IrO2", "Ir foil"])
    b = oe.export_stem("fig", "chir", ["IrO2", "Ir foil"])
    c = oe.export_stem("fig", "xanes", ["IrTa-50"])
    assert len({a, b, c}) == 3
    assert a.startswith("fig_XANES_")
    assert oe.export_stem("fig", "xanes", list("ABCDE")).endswith("+2")


def test_unique_dir_never_reuses(tmp_path):
    d1 = oe.unique_dir(tmp_path, "x")
    d1.mkdir()
    d2 = oe.unique_dir(tmp_path, "x")
    d2.mkdir()
    assert d1.name == "x" and d2.name == "x_2" and oe.unique_dir(tmp_path, "x").name == "x_3"


def test_originpro_mode_leaves_only_opju(tmp_path, monkeypatch):
    fake = MagicMock()
    monkeypatch.setitem(sys.modules, "originpro", fake)
    built = {}

    def build(spec, op):
        built.update(spec)
        open(spec["out"], "w").close()                   # 假装 Origin 存了工程

    from xafsmith import origin_builder
    monkeypatch.setattr(origin_builder, "build", build)
    fig = _fig()
    try:
        od = tmp_path / "out"
        r = oe.export(fig, od, "fig_XANES_A", kind="xanes", use_originpro=True)
    finally:
        plt.close(fig)
    assert r["mode"] == "originpro"
    assert [p.name for p in od.iterdir()] == ["fig_XANES_A.opju"]
    assert not any(str(od) in g["csv"] for g in built["graphs"])   # CSV 写在临时文件夹
