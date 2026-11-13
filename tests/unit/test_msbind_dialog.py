"""B5：对话框表（已一致 / 无建议的行不勾）与 spec()（只含勾选且确有改动的行）。手写几何，离屏 Qt。"""
import math

import pytest

pytest.importorskip("PySide6")
from PySide6.QtWidgets import QApplication

from xafsmith import msbind as mb
from xafsmith.qt.pages.fitting import msbind_dialog as md

O1, TA1 = 1.995, 3.99


def _row(file, nleg, reff, geom, deltar, sigma2, label):
    return dict(file=file, nleg=nleg, reff=reff, label=label, use=True, deltar=deltar, sigma2=sigma2, geom=geom)


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


def _rows():
    tri = [("Ta", (0, 0, 0)), ("O", (O1, 0, 0)), ("O", (0, O1, 0))]
    col = [("Ta", (0, 0, 0)), ("Ta", (0, 0, TA1)), ("O", (0, 0, O1))]
    return [_row("d/o.dat", 2, O1, [("Ta", (0, 0, 0)), ("O", (0, 0, O1))], "dr1", "ss1", "Ta-O"),
            _row("d/ta.dat", 2, TA1, [("Ta", (0, 0, 0)), ("Ta", (0, 0, TA1))], "2*dr1", "ssT", "Ta-Ta"),
            _row("d/tri.dat", 3, 3.4, tri, "dr1", "ss1", "tri"),                 # 要改
            _row("d/col.dat", 3, TA1, col, "dr1*2", "ssT", "col"),               # 已一致（写法不同）
            _row("d/nosingle.dat", 3, 3.4, [("Ta", (0, 0, 0)), ("Ni", (5, 0, 0)), ("Ni", (0, 5, 0))], "0", "0.003", "nb")]  # 无建议


def test_table_and_spec(app):
    rows = _rows()
    sugg = mb.suggest(rows)
    df = md.build_table(rows, sugg)
    assert list(df["path"]) == ["tri", "col", "nb"]
    assert list(df["apply"]) == [True, False, False]
    dlg = md.MsBindDialog(None, rows, sugg)
    sp = dlg.spec()
    assert [s["label"] for s in sp] == ["tri"] and sp[0]["index"] == 2
    assert sp[0]["deltar"] == "1.707*dr1" and sp[0]["sigma2"] == "1.457*ss1" and sp[0]["note"].startswith("msbind:")
    dlg.tab.m.df.iat[0, 0] = False                                            # 用户取消勾选
    assert dlg.spec() == []
    dlg.tab.m.df.iat[1, 0] = True                                             # 勾选一个本无改动的行：仍不写
    assert dlg.spec() == []
    assert math.isclose(df.iloc[0]["reff"], 3.4)


def test_no_ms_rows(app):
    dlg = md.MsBindDialog(None, _rows()[:2], [])
    assert dlg.spec() == []
