"""处理页面之间共享的小函数。"""

from __future__ import annotations

from ... import widgets as W
from ...widgets import T, Banner


def need_groups(page):
    if not page.S.groups:
        page.add(Banner("info", T("先在“载入谱”中载入样品。", "Load samples under “Load spectra” first.")))
        btn = W.button(T("去载入谱", "Go to Load spectra"), primary=True, slot=lambda: page.app.go("load"))
        page.add(W.hbox(btn, None))
        return False
    return True


def norm_fields(p):
    e0 = W.text("" if p.get("e0") is None else str(p["e0"]), T("空 = 导数最大值", "empty = derivative max"))
    w = dict(e0=e0, pre1=W.num(p["pre1"], step=5), pre2=W.num(p["pre2"], step=5), norm1=W.num(p["norm1"], step=10),
             norm2=W.num(p["norm2"] or -10, step=10), nnorm=W.combo([1, 2, 3], int(p["nnorm"])),
             smooth_ev=W.num(p["smooth_ev"], 0, 10, 0.5))
    row = W.fields((T("E0 固定", "Fix E0"), e0), ("pre1", w["pre1"]), ("pre2", w["pre2"]), ("norm1", w["norm1"]),
                   (T("norm2（≤0 距末端）", "norm2 (≤0 from end)"), w["norm2"]), ("nnorm", w["nnorm"]),
                   (T("E0 平滑 σ", "E0 smoothing σ"), w["smooth_ev"]))

    def read():
        try:
            e = float(e0.text()) if e0.text().strip() else None
        except ValueError:
            e = None
        return dict(e0=e, pre1=w["pre1"].value(), pre2=w["pre2"].value(), norm1=w["norm1"].value(),
                    norm2=w["norm2"].value(), nnorm=w["nnorm"].value(), smooth_ev=w["smooth_ev"].value())

    def connect(fn):
        e0.editingFinished.connect(fn)
        for k in ("pre1", "pre2", "norm1", "norm2", "smooth_ev"):
            w[k].valueChanged.connect(lambda *_: fn())
        w["nnorm"].currentIndexChanged.connect(lambda *_: fn())
    row.read, row.connect = read, connect
    return row
