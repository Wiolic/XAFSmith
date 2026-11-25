"""v1.4.1 审查修复：多位点内置结构的位点数、meta.csv 重扫保留 ref_file = None、元素修改器拒绝离谱的吸收边。"""
import types

import numpy as np
import pandas as pd
import pytest

from xafsmith import feff_wrap, paths, pipeline as pl


def test_n_absorber_sites():
    assert feff_wrap.n_absorber_sites("Cu", "Cu") == 1
    assert feff_wrap.n_absorber_sites("Fe3O4", "Fe") == 2          # 四面体 + 八面体


def test_rescan_keeps_ref_file_None(tmp_path):
    old = paths.ROOT
    paths.set_root(tmp_path)
    try:
        (tmp_path / "data" / "raw").mkdir(parents=True)
        row = dict.fromkeys(pl.META_COLS, "")
        row.update(file="data/raw/x.dat", sample="x", ref_file="None", use="1")
        pd.DataFrame([row]).to_csv(paths.META, index=False, encoding="utf-8-sig")
        pl.scan_raw()
        m = pd.read_csv(paths.META, dtype=str, encoding="utf-8-sig", keep_default_na=False)
        assert m.loc[m.file == "data/raw/x.dat", "ref_file"].iloc[0] == "None"
    finally:
        paths.set_root(old)


def test_guess_for_rejects_edge_outside_spectrum():
    from xafsmith.qt.pages.process.load import guess_for
    g = types.SimpleNamespace(energy=np.linspace(11000, 12000, 50))        # Ir L3 附近
    assert guess_for(g, "Ir") == ("Ir", "L3")
    with pytest.raises(ValueError):
        guess_for(g, "Fe")                                                  # Fe K 在 7.1 keV，不在谱范围内


def test_fit_rect_leaves_room_for_title_bar():
    """客户区不能贴着屏幕顶端（否则标题栏在屏幕外：看不到最小化 / 还原 / 关闭、拖不动窗口）"""
    pytest.importorskip("PySide6")
    import os
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication
    QApplication.instance() or QApplication([])
    from xafsmith.qt.app import _avail, _fit_rect, _frame_margins
    a = _avail()
    top, side = _frame_margins()
    for rect in [(a.left(), a.top(), a.width(), a.height()),            # 存下的是最大化时的整屏
                 (a.left() - 50, a.top() - 40, 800, 600),               # 位置在屏幕上方之外
                 (a.right() + 100, a.bottom() + 100, 900, 700)]:        # 在已拔掉的显示器上
        x, y, w, h = _fit_rect(*rect)
        assert y - top >= a.top() and x - side >= a.left()
        assert y + h + side <= a.bottom() + 1 and x + w + side <= a.right() + 1
