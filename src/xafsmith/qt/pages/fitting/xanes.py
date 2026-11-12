"""XANES 分析页面。"""

from __future__ import annotations

from xafsmith import logs
import numpy as np
import pandas as pd
from PySide6.QtWidgets import QWidget
from xafsmith import paths
from ... import widgets as W
from ...state import safe
from ...theme import C
from ...widgets import T, Banner, Page


class XanesPage(Page):
    title_zh, title_en, icon_name = "XANES 定量", "XANES quantification", "peak"

    def build(self):
        from ...state import ensure_norm
        S = self.S
        self.header(T("边位置同时受价态、配位数和配体影响：价态标定只适用于配体相同、结构相近的标样与样品。",
                      "Edge position depends on oxidation state, coordination and ligands: valence calibration only holds "
                      "for standards and samples with the same ligands and similar structures."))
        for g in S.groups.values():
            try:
                ensure_norm(S, g)
            except Exception:
                logs.log.warning("qt.pages.fitting.build 出错（已忽略或已提示）", exc_info=True)
                pass
        cands = [k for k, g in S.groups.items() if hasattr(g, "flat")]
        if not cands:
            self.add(Banner("info", T("先在“载入谱”中载入样品。", "Load samples under “Load spectra” first.")))
            return
        self.add(W.tabs((T("边位置与白线", "Edge & white line"), self._features(cands)),
                        (T("价态标定", "Valence calibration"), self._valence(cands)),
                        (T("边前峰拟合", "Pre-edge fitting"), self._preedge(cands)),
                        state=self.state, key="tab"))

    def _features(self, cands):
        from xafsmith import xanes as xx
        S = self.S
        w = QWidget()
        lay = W.QVBoxLayout(w)
        lay.setContentsMargins(0, 10, 0, 0)
        sel = W.MultiSelect(cands, self.state.get("fsel", cands[:6]), T("选择谱", "Choose spectra"))
        wl = W.num(30, 5, 100, 5)
        lay.addWidget(W.hbox(W.field(T("谱", "Spectra"), sel), W.field(T("白线积分：E0 至 E0 + (eV)", "White-line window: E0 to E0 + (eV)"), wl), spacing=12))
        tabw, plot = W.vbox(), W.Plot(360)
        lay.addWidget(tabw)
        lay.addWidget(W.label(T("E0_deriv：导数最大值；E_half：归一化 μ = 0.5 处；WL_E / WL_height：白线峰位与峰高；WL_area：E0 至 E0+区间内超过 1 的面积 (eV)。",
                                "E0_deriv: derivative max; E_half: normalized μ = 0.5; WL_E / WL_height: white-line position and height; "
                                "WL_area: area above 1 from E0 to E0 + window (eV)."), "faint"))
        lay.addWidget(plot)
        cur = {}

        def upd():
            v = sel.value()
            self.state["fsel"] = v
            W._clear_layout(tabw.layout())
            if not v:
                return
            tab = xx.features_table([S.groups[k] for k in v], wl.value())
            cur["tab"] = tab
            tabw.layout().addWidget(W.Table(tab.round(4)))
            plot.clear()
            for k in v:
                g = S.groups[k]
                plot.ax.plot(g.energy, g.flat, label=k)
            e0 = S.groups[v[0]].e0
            plot.ax.set_xlim(e0 - 30, e0 + 70)
            for y in (0.5, 1.0):
                plot.ax.axhline(y, color=C["text3"], ls=":", lw=0.8)
            plot.ax.set_xlabel("E (eV)")
            plot.draw()

        def save():
            tab = cur.get("tab")
            if tab is None:
                return
            paths.XANES.mkdir(parents=True, exist_ok=True)
            old = pd.read_csv(paths.XANES_CSV, encoding="utf-8-sig") if paths.XANES_CSV.exists() else None
            new = tab if old is None else pd.concat([old[~old["sample"].isin(tab["sample"])], tab])
            new.to_csv(paths.XANES_CSV, index=False, encoding="utf-8-sig")
            W.toast(self, T(f"已保存 {len(tab)} 条（同名样品覆盖）", f"Saved {len(tab)} rows (same samples replaced)"))
        sel.changed.connect(lambda *_: upd())
        wl.valueChanged.connect(lambda *_: upd())
        lay.addWidget(W.hbox(None, W.button(T("保存到 output/xanes/xanes_features.csv", "Save to output/xanes/xanes_features.csv"),
                                            icon_name="save", slot=save)))
        upd()
        lay.addStretch(1)
        return w

    def _valence(self, cands):
        from xafsmith import xanes as xx
        S = self.S
        w = QWidget()
        lay = W.QVBoxLayout(w)
        lay.setContentsMargins(0, 10, 0, 0)
        lay.addWidget(W.label(T("1 选已知价态的实测标样并填写价态；2 选边位置定义；3 选要估算的样品。",
                                "1 choose measured standards of known valence and enter it; 2 choose the edge definition; 3 choose samples."), "muted"))
        stds = W.MultiSelect(cands, self.state.get("vstd", []), T("标样", "Standards"))
        how = W.combo(["E_half", "E0_deriv", "WL_E"], self.state.get("how", "E_half"),
                      fmt=lambda h: {"E_half": T("E_half（半高点）", "E_half (half height)"), "E0_deriv": T("E0_deriv（导数最大值）", "E0_deriv (derivative max)"),
                                     "WL_E": T("WL_E（白线峰位）", "WL_E (white-line peak)")}[h])
        smp = W.MultiSelect(cands, self.state.get("vsmp", []), T("要估算价态的样品", "Samples to estimate"))
        lay.addWidget(W.hbox(W.field(T("标样", "Standards"), stds), W.field(T("边位置定义", "Edge definition"), how),
                             W.field(T("样品", "Samples"), smp), spacing=12))
        holder = W.vbox()
        lay.addWidget(holder)
        lay.addStretch(1)

        def upd():
            self.state.update(vstd=stds.value(), how=how.value(), vsmp=smp.value())
            W._clear_layout(holder.layout())
            st_ = stds.value()
            if not st_:
                return
            vals = self.state.setdefault("vals", {})
            vt = pd.DataFrame({T("标样", "Standard"): st_, T("价态", "Valence"): [float(vals.get(k, 0.0)) for k in st_]})
            t = W.Table(vt, editable=[T("价态", "Valence")])
            holder.layout().addWidget(t)
            out = W.vbox()
            holder.layout().addWidget(out)

            def calc():
                df = t.df()
                for k, v in zip(df.iloc[:, 0], df.iloc[:, 1]):
                    vals[k] = float(v)
                W._clear_layout(out.layout())
                col = how.value()
                feats = xx.features_table([S.groups[k] for k in st_]).set_index("sample")
                pos = [float(feats.loc[k, col]) for k in st_]
                val = [vals[k] for k in st_]
                try:
                    cal = xx.valence_calibration(pos, val)
                except Exception as ex:      # noqa: BLE001
                    logs.log.warning("qt.pages.fitting.calc 出错（已忽略或已提示）", exc_info=True)
                    out.layout().addWidget(Banner("info", str(ex)))
                    return
                out.layout().addWidget(W.label(T(f"E = <b>{cal['a']:.3f}</b>·价态 + <b>{cal['b']:.2f}</b> eV；R² = {cal['r2']:.4f}；斜率误差 {cal['a_err']:.3f} eV/价（{cal['n']} 个标样）",
                                                 f"E = <b>{cal['a']:.3f}</b>·valence + <b>{cal['b']:.2f}</b> eV; R² = {cal['r2']:.4f}; slope error {cal['a_err']:.3f} eV per unit ({cal['n']} standards)"), rich=True))
                if cal["n"] < 3:
                    out.layout().addWidget(Banner("warn", T("只有 2 个标样：直线没有统计误差，估算的价态误差未知。",
                                                            "Only 2 standards: the line has no statistical error; valence errors are unknown.")))
                p = W.Plot(320)
                p.ax.scatter(val, pos, color=C["accent"], zorder=3, label=T("标样", "standards"))
                for x, y, k in zip(val, pos, st_):
                    p.ax.annotate(k, (x, y), textcoords="offset points", xytext=(4, 4), fontsize=8)
                xs = np.linspace(min(val) - 0.5, max(val) + 0.5, 20)
                p.ax.plot(xs, cal["a"] * xs + cal["b"], ls="--", color=C["text3"], label=T("标定直线", "calibration"))
                rows = []
                if smp.value():
                    sf = xx.features_table([S.groups[k] for k in smp.value()]).set_index("sample")
                    for k in smp.value():
                        v, err = xx.predict_valence(cal, float(sf.loc[k, col]))
                        rows.append({T("样品", "Sample"): k, T("边位置", "Edge position"): float(sf.loc[k, col]),
                                     T("价态", "Valence"): round(v, 3), T("误差", "Error"): None if not np.isfinite(err) else round(err, 3),
                                     T("外推", "Extrapolated"): T("是", "yes") if not (min(val) <= v <= max(val)) else ""})
                        p.ax.scatter([v], [float(sf.loc[k, col])], marker="x", s=50, label=k)
                p.ax.set_xlabel(T("价态", "valence"))
                p.ax.set_ylabel(f"{col} (eV)")
                p.draw()
                if rows:
                    rt = pd.DataFrame(rows)
                    out.layout().addWidget(W.Table(rt))
                    out.layout().addWidget(W.label(T("误差只来自标定直线的统计误差，不含化学环境差异；超出标样价态范围的为外推。",
                                                     "Errors come from the calibration line only, not from chemical differences; outside the standards' range is extrapolation."), "faint"))

                    def save():
                        paths.XANES.mkdir(parents=True, exist_ok=True)
                        rt.assign(定义=col, 斜率=cal["a"], 截距=cal["b"], R2=cal["r2"],
                                  标样="; ".join(f"{a}={b}" for a, b in zip(st_, val))).to_csv(
                            paths.XANES / f"valence_{col}.csv", index=False, encoding="utf-8-sig")
                        W.toast(self, T(f"已保存 output/xanes/valence_{col}.csv", f"Saved output/xanes/valence_{col}.csv"))
                    out.layout().addWidget(W.hbox(None, W.button(T("保存价态估算", "Save valence estimates"), icon_name="save", slot=save)))
                out.layout().addWidget(p)
            t.edited.connect(calc)
            calc()
        stds.changed.connect(lambda *_: upd())
        how.currentIndexChanged.connect(lambda *_: upd())
        smp.changed.connect(lambda *_: upd())
        upd()
        return w

    def _preedge(self, cands):
        from xafsmith import xanes as xx
        S = self.S
        w = QWidget()
        lay = W.QVBoxLayout(w)
        lay.setContentsMargins(0, 10, 0, 0)
        k = W.combo(cands, self.state.get("pk"))
        lo, hi = W.num(-20, -60, 0, 1), W.num(-5, -30, 20, 1)
        n = W.combo([1, 2, 3], 1)
        stp = W.combo(["erf", "arctan", "none"], "erf")
        lay.addWidget(W.fields((T("谱", "Spectrum"), k), (T("下限 E−E0 (eV)", "From E−E0 (eV)"), lo), (T("上限 E−E0 (eV)", "To E−E0 (eV)"), hi),
                               (T("峰数", "Peaks"), n), (T("主边基线", "Edge baseline"), stp)))
        lay.addWidget(W.label(T("模型：n 个高斯峰（σ ≤ 2.5 eV）+ 台阶（主边上升沿，中心限制在半高点 ±6 eV）+ 常数。峰位贴边或面积≈0 时会提示。",
                                "Model: n Gaussians (σ ≤ 2.5 eV) + a step (rising edge, centre within ±6 eV of half height) + constant. "
                                "Warnings flag peaks at the bounds or with ≈0 area."), "faint"))
        out = W.vbox()

        def go():
            self.state["pk"] = k.value()
            r = xx.preedge_fit(S.groups[k.value()], lo.value(), hi.value(), n.value(), stp.value())
            W._clear_layout(out.layout())
            for w_ in r["warnings"]:
                out.layout().addWidget(Banner("warn", w_))
            pk = pd.DataFrame(r["peaks"])
            out.layout().addWidget(W.Table(pk.round(4)))
            out.layout().addWidget(W.label(T(f"总面积 <b>{r['total_area']:.4f}</b> eV；面积加权质心 <b>{r['centroid']:.2f}</b> eV；R 因子 {r['rfactor']:.2e}",
                                             f"Total area <b>{r['total_area']:.4f}</b> eV; area-weighted centroid <b>{r['centroid']:.2f}</b> eV; R-factor {r['rfactor']:.2e}"), rich=True))
            cv = r["curves"]
            p = W.Plot(340)
            p.ax.plot(cv["x"], cv["y"], color=C["text"], label=T("数据", "data"))
            p.ax.plot(cv["x"], cv["fit"], color=C["err"], ls="--", label=T("拟合", "fit"))
            for nm, v in cv["comps"].items():
                p.ax.plot(cv["x"], v, lw=1, label=nm)
            p.ax.plot(cv["x"], cv["y"] - cv["fit"], color=C["text3"], lw=1, label=T("残差", "residual"))
            p.ax.set_xlabel("E (eV)")
            p.draw()
            out.layout().addWidget(p)

            def save():
                paths.XANES.mkdir(parents=True, exist_ok=True)
                fn = paths.XANES / f"preedge_{safe(k.value())}.csv"
                pk.assign(sample=k.value(), emin=lo.value(), emax=hi.value(), step=stp.value(), centroid=r["centroid"],
                          total_area=r["total_area"], rfactor=r["rfactor"]).to_csv(fn, index=False, encoding="utf-8-sig")
                W.toast(self, T(f"已保存 {paths.rel(fn)}", f"Saved {paths.rel(fn)}"))
            out.layout().addWidget(W.hbox(None, W.button(T("保存边前峰结果", "Save pre-edge result"), icon_name="save", slot=save)))
        lay.addWidget(W.hbox(None, W.button(T("拟合边前峰", "Fit pre-edge"), primary=True, icon_name="play", slot=lambda: W.wait_cursor(go))))
        lay.addWidget(out)
        lay.addStretch(1)
        return w
