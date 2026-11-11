"""线性组合拟合页面。"""

from __future__ import annotations

from xafsmith import logs
import pandas as pd
from xafsmith import paths
from ... import widgets as W
from ...state import has_chi
from ...theme import C
from ...widgets import T, Banner, Card, Page


class LCFPage(Page):
    title_zh, title_en, icon_name = "LCF", "LCF", "layers"

    def build(self):
        from xafsmith import fit_lcf as xlcf
        from xafsmith.common import append_csv
        from ...state import ensure_norm, process
        S = self.S
        self.header(T("线性组合拟合。端点必须是实测标样；同时与“只用单一标样”的拟合比较。",
                      "Linear combination fitting. End-members must be measured standards; compare with single-standard fits."))
        if len(S.groups) < 2:
            self.add(Banner("info", T("至少需要两条谱（载入谱）。", "Needs at least two spectra (Load spectra).")))
            return
        for g in S.groups.values():
            try:
                ensure_norm(S, g)
            except Exception:
                logs.log.warning("qt.pages.fitting.build 出错（已忽略或已提示）", exc_info=True)
                pass
        card = Card()
        keys = list(S.groups)
        smp = W.combo(keys, self.state.get("smp"))
        stds = W.MultiSelect([k for k in keys], self.state.get("stds", []), T("端点标样（实测）", "Standards (measured)"))
        space = W.combo(["norm", "dmude", "chik"], self.state.get("space", "norm"))
        lo, hi = W.num(self.state.get("lo", -20.0), -500, 500, 1), W.num(self.state.get("hi", 30.0), -500, 500, 1)

        def sp_changed():
            if space.value() == "chik":
                lo.setValue(3.0); hi.setValue(10.0)
            else:
                lo.setValue(-20.0); hi.setValue(30.0)
        space.currentIndexChanged.connect(lambda *_: sp_changed())
        s1, bd, es = W.check(T("权重和 = 1", "Σw = 1"), True), W.check("0 ≤ w ≤ 1", True), W.check(T("拟合能量平移", "Fit E shift"), False)
        note = W.text("", T("使用非实测端点时必须在此注明为假设", "If an end-member is not measured, state the assumption here"))
        card.add(W.hbox(W.field(T("样品", "Sample"), smp), W.field(T("标样", "Standards"), stds), spacing=12))
        card.add(W.hbox(W.field(T("空间", "Space"), space), W.field(T("下限（E−E0 或 k）", "From (E−E0 or k)"), lo),
                        W.field(T("上限", "To"), hi), W.vbox(None, s1), W.vbox(None, bd), W.vbox(None, es), spacing=12))
        card.add(W.field(T("备注", "Note"), note))
        btn = W.button("LCF", primary=True, icon_name="play")

        def go():
            st_ = [k for k in stds.value() if k != smp.value()]
            if not st_:
                return
            self.state.update(smp=smp.value(), stds=stds.value(), space=space.value(), lo=lo.value(), hi=hi.value())
            if space.value() == "chik":
                for k in [smp.value()] + st_:
                    if not has_chi(S.groups[k]):
                        process(S, S.groups[k], norm=False, ft=False)
            G = S.groups
            smp_k, lo_v, hi_v, sp_v = smp.value(), lo.value(), hi.value(), space.value()
            sum1, bnd, esh, note_t = s1.isChecked(), bd.isChecked(), es.isChecked(), note.text()
            import copy
            # 界面线程里复制：后台计算期间用户可能在归一化等页面重算同一批谱
            sample_g, std_g = copy.deepcopy(G[smp_k]), [copy.deepcopy(G[k]) for k in st_]

            def work():
                r = xlcf.lcf(sample_g, std_g, xmin=lo_v, xmax=hi_v, space=sp_v,
                             sum_to_one=sum1, bounds=bnd, fit_eshift=esh, kweight=2)
                return dict(r=r, single=xlcf.single_standard_compare(sample_g, std_g, xmin=lo_v, xmax=hi_v, space=sp_v),
                            combo=xlcf.fit_all_combinations(sample_g, std_g, xmin=lo_v, xmax=hi_v, space=sp_v,
                                                            sum_to_one=sum1, bounds=bnd) if len(std_g) > 2 else None)

            def done(res):
                S.extra["lcf"] = res
                paths.LCF.mkdir(parents=True, exist_ok=True)
                append_csv(pd.DataFrame([xlcf.result_row(res["r"], note_t)]), paths.LCF_CSV)
                self.refresh()
            W.run_task(self, work, done, T("LCF 拟合中…", "LCF fitting…"), btn)
        btn.clicked.connect(lambda *_: go())
        card.add(W.hbox(W.label(T("结果追加到 output/lcf/lcf_results.csv", "Results are appended to output/lcf/lcf_results.csv"), "faint"), None, btn))
        self.add(card)
        L = S.extra.get("lcf")
        if not L:
            return
        r = L["r"]
        res = Card(T("结果", "Result"))
        res.add(W.metrics((T("R 因子", "R-factor"), f"{r['rfactor']:.5f}"), ("χ²_ν", f"{r['chi2_reduced']:.2e}"),
                          ("Σw", f"{r['sum_weights']:.3f}")))
        res.add(W.Table(pd.DataFrame({T("标样", "Standard"): list(r["weights"]), T("权重", "Weight"): list(r["weights"].values()),
                                      T("误差", "Error"): [r["weights_err"].get(k) for k in r["weights"]]})))
        cv = r["curves"]
        p = W.Plot(380)
        p.ax.plot(cv["x"], cv["y"], color=C["text"], label=T("样品", "sample"))
        p.ax.plot(cv["x"], cv["fit"], color=C["err"], ls="--", label="LCF")
        for k, v in cv["comps"].items():
            p.ax.plot(cv["x"], v, lw=1, label=k)
        p.ax.plot(cv["x"], cv["y"] - cv["fit"], color=C["text3"], lw=1, label=T("残差", "residual"))
        p.ax.set_xlabel("E − E0 (eV)" if r["space"] != "chik" else "k (Å⁻¹)")
        p.draw()
        res.add(p)
        res.add(W.label(T("单一标样拟合比较", "Single-standard comparison"), "h3"))
        res.add(W.Table(L["single"]))
        if L.get("combo") is not None:
            res.add(W.label(T("所有组合（按 R 因子排序）", "All combinations (by R-factor)"), "h3"))
            res.add(W.Table(L["combo"]))
        self.add(res)
