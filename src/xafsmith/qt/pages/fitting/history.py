"""拟合历史页面。"""

from __future__ import annotations

import pandas as pd
from ... import widgets as W
from ...state import fit_label, save_fit
from ...widgets import T, Banner, Card, Page

from .fit_view import FitView


class HistoryPage(Page):
    title_zh, title_en, icon_name = "拟合历史", "Fit history", "history"

    def build(self):
        from xafsmith import fit_exafs as xfit
        S = self.S
        self.header(T("本次会话的全部拟合；嵌套模型用 Hamilton F 检验比较，p < 0.05 才能说新增的壳层显著。",
                      "All fits of this session; compare nested models with the Hamilton F-test — only p < 0.05 makes an added shell significant."))
        if not S.fits:
            self.add(Banner("info", T("暂无拟合。", "No fits yet.")))
            return
        card = Card(T("拟合", "Fits"))
        rows = [dict(i=i + 1, time=f["time"], sample=f["summ"]["sample"], model=f["summ"]["model"], rfactor=f["summ"]["rfactor"],
                     chi2r=f["summ"]["chi2_reduced"], nvarys=f["summ"]["nvarys"], n_idp=f["summ"]["n_idp"]) for i, f in enumerate(S.fits)]
        card.add(W.Table(pd.DataFrame(rows), max_height=320))

        def save_all():
            for f in S.fits:
                save_fit(f)
            W.toast(self, T(f"已保存 {len(S.fits)} 个拟合", f"{len(S.fits)} fits saved"))
        card.add(W.hbox(None, W.button(T("全部保存到 output/fits/（报告与方法导出会用到）", "Save all to output/fits/ (used by report and methods export)"),
                                       icon_name="save", slot=lambda: W.wait_cursor(save_all))))
        self.add(card)
        ft = Card(T("F 检验（Hamilton）", "F-test (Hamilton)"))
        idx = list(range(len(S.fits)))
        a = W.combo(idx, self.state.get("a", 0), fmt=lambda i: fit_label(S.fits[i]))
        b = W.combo(idx, self.state.get("b", len(S.fits) - 1), fmt=lambda i: fit_label(S.fits[i]))
        out = W.vbox()

        def go():
            self.state.update(a=a.value(), b=b.value())
            r = xfit.hamilton_test(S.fits[a.value()]["result"], S.fits[b.value()]["result"])
            W._clear_layout(out.layout())
            why = xfit.ftest_blockers(S.fits[a.value()]["model"], S.fits[b.value()]["model"])
            if why:
                out.layout().addWidget(Banner("warn", "\n".join(why)))
            out.layout().addWidget(W.Table(pd.DataFrame([{"key": k, "value": str(v)} for k, v in r.items()])))
        ft.add(W.hbox(W.field(T("简单模型", "Simpler model"), a), W.field(T("复杂模型", "More complex model"), b),
                      W.vbox(None, W.button(T("比较", "Compare"), primary=True, slot=go)), spacing=12))
        ft.add(out)
        self.add(ft)
        self.add(self._compare_card(idx))
        view = W.combo(idx, self.state.get("view", len(S.fits) - 1), fmt=lambda i: fit_label(S.fits[i]))
        view.currentIndexChanged.connect(lambda *_: (self.state.__setitem__("view", view.value()), self.refresh()))
        self.add(W.hbox(W.label(T("查看拟合", "View fit"), "h3"), view, None))
        self.add(FitView(self, S.fits[view.value()], f"h{view.value()}"))

    def _compare_card(self, idx):
        """多模型比较表（B4）：F、p 由 hamilton_test 给出，嵌套关系不检查。"""
        from xafsmith import fit_exafs as xfit, paths
        from xafsmith.common import write_params
        S = self.S
        card = Card(T("模型比较表", "Model comparison"))
        chks = [W.check(fit_label(S.fits[i]), True) for i in idx]
        for c in chks:
            card.add(c)
        out = W.vbox()
        last = {}

        def go():
            sel = [i for i, c in zip(idx, chks) if c.isChecked()]
            W._clear_layout(out.layout())
            last.clear()
            if len(sel) < 2:
                out.layout().addWidget(Banner("warn", T("至少选择 2 个拟合。", "Select at least 2 fits.")))
                return
            entries = [dict(name=S.fits[i]["summ"]["model"], model=S.fits[i]["model"], result=S.fits[i]["result"],
                            summ=S.fits[i]["summ"]) for i in sel]
            df = xfit.compare_models(entries)
            last["df"] = df
            last["models"] = [e["name"] for e in entries]
            out.layout().addWidget(W.Table(df, max_height=260))
            out.layout().addWidget(Banner("info", T(*xfit.COMPARE_NOTE.split(" / ", 1))))

        def save():
            if "df" not in last:
                W.toast(self, T("请先点“比较”", "Press Compare first"), "warn")
                return
            f = paths.FITS / "model_compare.csv"
            f.parent.mkdir(parents=True, exist_ok=True)
            last["df"].to_csv(f, index=False, encoding="utf-8-sig")
            write_params(f.with_suffix(".params.json"), {"models": list(last["models"])}, "GUI model comparison")
            W.toast(self, T(f"已保存 {paths.rel(f)}", f"Saved {paths.rel(f)}"))
        card.add(W.hbox(W.button(T("比较", "Compare"), primary=True, slot=go),
                        W.button(T("保存为 CSV", "Save as CSV"), icon_name="save", slot=save), None))
        card.add(out)
        return card
