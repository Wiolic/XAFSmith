"""“多重散射绑定…”对话框（B5）：按 FEFF 路径几何给已勾选的多重散射路径建议 deltar / sigma2，逐行确认后写进路径表。

只给建议；点“应用”之前不改任何东西。计算在 xafsmith.msbind，这里不做数值。
"""
from __future__ import annotations

import pandas as pd
from PySide6.QtWidgets import QDialog, QDialogButtonBox, QVBoxLayout

from xafsmith import msbind

from ... import widgets as W
from ...widgets import T


def build_table(rows, sugg):
    """suggest 的结果 → 对话框表（DataFrame）。同时返回 {行号: 建议}，行号是对话框表里的行。"""
    recs = []
    for s in sugg:
        r = rows[s["index"]]
        d_same = s["deltar"] is not None and msbind.equivalent(r["deltar"], s["deltar"])
        s_same = s["sigma2"] is not None and msbind.equivalent(r["sigma2"], s["sigma2"])
        can_d = s["deltar"] is not None and not d_same
        can_s = s["sigma2"] is not None and not s_same
        if s["problem"]:
            status = T("无建议", "No suggestion")
        elif not (can_d or can_s):
            status = T("已一致" if not s["sigma2_problem"] else "ΔR 已一致，σ² 无建议",
                       "Already consistent" if not s["sigma2_problem"] else "ΔR consistent, no σ² suggestion")
        else:
            status = T("建议", "Suggestion")
        basis = s["problem"] or " | ".join(x for x in (s["basis_deltar"], s["basis_sigma2"], s["sigma2_problem"]) if x)
        recs.append(dict(apply=bool(can_d or can_s), path=s["label"], reff=float(r["reff"]), nleg=int(r["nleg"]),
                         dr_now=str(r["deltar"]), dr_new=s["deltar"] or "", ss_now=str(r["sigma2"]), ss_new=s["sigma2"] or "",
                         status=status, basis=basis, _can_d=can_d, _can_s=can_s, _i=s["index"], _note=s["note"]))
    return pd.DataFrame(recs)


class MsBindDialog(QDialog):
    def __init__(self, parent, rows, sugg):
        super().__init__(parent)
        self.setWindowTitle(T("多重散射绑定", "Multiple-scattering binding"))
        self.resize(1100, 420)
        self.sugg = sugg
        self.df = build_table(rows, sugg)
        v = QVBoxLayout(self)
        v.addWidget(W.label(T("按 FEFF 路径几何，用已勾选的单散射路径的表达式组合出多重散射路径的 deltar / sigma2。"
                              "勾选“应用”的行才会改；不勾不改，也不新建参数。",
                              "From the FEFF path geometry, combine the expressions of the ticked single-scattering paths into "
                              "deltar / sigma2 for the multiple-scattering paths. Only rows with “Apply” ticked are changed; "
                              "no parameters are created."), "faint"))
        hdr = dict(apply=T("应用", "Apply"), path=T("路径", "Path"), reff="Reff", nleg="nleg", dr_now=T("现 deltar", "deltar now"),
                   dr_new=T("建议 deltar", "deltar suggested"), ss_now=T("现 σ²", "σ² now"), ss_new=T("建议 σ²", "σ² suggested"),
                   status=T("状态", "Status"), basis=T("依据", "Basis"))
        if len(self.df):
            show = self.df[list(hdr)]
            self.tab = W.Table(show, editable=["apply"], bools=["apply"], header_fmt=lambda c: hdr.get(c, c), stretch=True,
                               max_height=320)
            v.addWidget(self.tab)
        else:
            self.tab = None
            v.addWidget(W.label(T("没有已勾选的多重散射路径（nleg > 2）。", "No ticked multiple-scattering paths (nleg > 2)."),
                                "faint"))
        v.addWidget(W.label(T("建议依赖几何假设，见依据列；三角路径的 σ² 是独立键近似（忽略不同键之间的相关）。",
                              "Suggestions depend on geometric assumptions, see the Basis column; the σ² of a triangular path is "
                              "an independent-bond approximation (correlations between bonds are ignored)."), "faint"))
        bb = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        bb.button(QDialogButtonBox.StandardButton.Ok).setText(T("应用", "Apply"))
        bb.button(QDialogButtonBox.StandardButton.Cancel).setText(T("取消", "Cancel"))
        bb.accepted.connect(self.accept)
        bb.rejected.connect(self.reject)
        v.addWidget(bb)

    def spec(self):
        """→ [dict(index, deltar|None, sigma2|None, note, label)]：只含勾选且确有改动的行；index 是路径表行号。"""
        if self.tab is None:
            return []
        ticked = self.tab.df()["apply"].astype(bool).tolist()
        out = []
        for ok, (_, r) in zip(ticked, self.df.iterrows()):
            if not ok or not (r["_can_d"] or r["_can_s"]):
                continue
            out.append(dict(index=int(r["_i"]), label=r["path"], deltar=r["dr_new"] if r["_can_d"] else None,
                            sigma2=r["ss_new"] if r["_can_s"] else None, note=r["_note"]))
        return out
