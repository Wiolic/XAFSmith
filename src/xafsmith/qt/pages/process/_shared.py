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
    """归一化参数行。pre1 < pre2、norm1 < norm2（norm2 > 0 时）自动联动；E0 非数字时红框提示，
    读取时按“空 = 导数最大值”处理但 page 里能看到红框，不再静默改写。"""
    e0 = W.text("" if p.get("e0") is None else str(p["e0"]), T("空 = 导数最大值", "empty = derivative max"))
    w = dict(e0=e0, pre1=W.num(p["pre1"], -2000, -1, 5, 1), pre2=W.num(p["pre2"], -2000, -1, 5, 1),
             norm1=W.num(p["norm1"], 1, 3000, 10, 1), norm2=W.num(p["norm2"] or -10, -3000, 3000, 10, 1),
             nnorm=W.combo([1, 2, 3], int(p["nnorm"])), smooth_ev=W.num(p["smooth_ev"], 0, 10, 0.5))
    W.link_range(w["pre1"], w["pre2"], 1.0)
    row = W.fields((T("E0 固定", "Fix E0"), e0), ("pre1", w["pre1"]), ("pre2", w["pre2"]), ("norm1", w["norm1"]),
                   (T("norm2（≤0 距末端）", "norm2 (≤0 from end)"), w["norm2"]), ("nnorm", w["nnorm"]),
                   (T("E0 平滑 σ", "E0 smoothing σ"), w["smooth_ev"]))

    def _norm2_fix(_v=None):
        n1, n2 = w["norm1"].value(), w["norm2"].value()
        if n2 > 0 and n2 <= n1:
            w["norm2"].setValue(n1 + 10)
    w["norm1"].valueChanged.connect(_norm2_fix)
    w["norm2"].valueChanged.connect(_norm2_fix)

    def read():
        txt = e0.text().strip()
        e = None
        if txt:
            try:
                e = float(txt)
            except ValueError:
                W.set_invalid(e0, True, T("E0 不是数字：已按“导数最大值”处理，请改成数字或清空", "E0 is not a number: using the derivative maximum; enter a number or clear it"))
                return dict(e0=None, pre1=w["pre1"].value(), pre2=w["pre2"].value(), norm1=w["norm1"].value(),
                            norm2=w["norm2"].value(), nnorm=w["nnorm"].value(), smooth_ev=w["smooth_ev"].value())
        W.set_invalid(e0, False)
        return dict(e0=e, pre1=w["pre1"].value(), pre2=w["pre2"].value(), norm1=w["norm1"].value(),
                    norm2=w["norm2"].value(), nnorm=w["nnorm"].value(), smooth_ev=w["smooth_ev"].value())

    def set_values(d):
        """把参数写回各输入框（恢复默认值用）；每个框的变化都会触发重画（已防抖）"""
        e0.setText("" if d.get("e0") is None else str(d["e0"]))
        for k in ("pre1", "pre2", "norm1", "smooth_ev"):
            if d.get(k) is not None:
                w[k].setValue(float(d[k]))
        w["norm2"].setValue(float(d["norm2"] or -10))
        if d.get("nnorm") in w["nnorm"]._vals:
            w["nnorm"].setCurrentIndex(w["nnorm"]._vals.index(d["nnorm"]))
        e0.editingFinished.emit()

    def connect(fn):
        e0.editingFinished.connect(fn)
        for k in ("pre1", "pre2", "norm1", "norm2", "smooth_ev"):
            w[k].valueChanged.connect(lambda *_: fn())
        w["nnorm"].currentIndexChanged.connect(lambda *_: fn())
    row.read, row.connect, row.widgets, row.set_values = read, connect, w, set_values
    row.e0 = e0
    return row


def reset_button(page, sec, apply, names=None, tip=None):
    """“恢复为 xafsmith.json 的值”按钮：apply(参数字典) 把值写回输入框。"""
    def go():
        d, src = page.S.cfg_defaults(sec, names() if callable(names) else names)
        apply(d)
        W.toast(page, T(f"已恢复为 xafsmith.json 的值（{src}）", f"Restored from xafsmith.json ({src})"), "info")
    return W.button(T("恢复为 xafsmith.json 的值", "Restore xafsmith.json values"), icon_name="refresh", slot=go,
                    tip=tip or T("把本卡片的参数改回项目配置文件里的值", "Set this card's parameters back to the values in the project configuration"))
