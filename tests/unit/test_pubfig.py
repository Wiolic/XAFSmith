"""出图：化学式下标、刻度位置、图内布局（预览不裁切）"""
import matplotlib

matplotlib.use("Agg")

import numpy as np  # noqa: E402

from xafsmith import pubfig as pf  # noqa: E402


def test_chem_subscripts_formula_words_only():
    assert pf.chem("IrO2") == "IrO$_{2}$"
    assert pf.chem("IrO2 Batch 1") == "IrO$_{2}$ Batch 1"
    assert pf.chem("Ta2O5_1_3V") == "Ta$_{2}$O$_{5}$_1_3V"
    assert pf.chem("Ir foil 1W1B") == "Ir foil 1W1B"
    assert pf.chem("IrTa-100") == "IrTa-100"
    assert pf.chem("IrCoOx_OCP") == "IrCoOx_OCP"
    assert pf.chem("IrO2", on=False) == "IrO2"


def test_ticks_left_bottom_and_labels_inside_figure():
    class G:
        label = "IrO2"
        k = np.linspace(0, 14, 281)
        chi = np.sin(2 * k) * np.exp(-0.05 * k)
    fig, _ = pf.chik([G()], kweight=2)
    ax = fig.axes[0]
    assert ax.xaxis.get_ticks_position() == "bottom" and ax.yaxis.get_ticks_position() == "left"
    fig.canvas.draw()
    r = fig.canvas.get_renderer()
    for a in (ax.xaxis.label, ax.yaxis.label):
        bb = a.get_window_extent(r)
        assert bb.x0 >= -1 and bb.y0 >= -1 and bb.x1 <= fig.bbox.width + 1 and bb.y1 <= fig.bbox.height + 1
