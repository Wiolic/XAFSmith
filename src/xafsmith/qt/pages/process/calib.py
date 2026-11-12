"""能量校准页面。"""

from __future__ import annotations

from pathlib import Path
import pandas as pd
from ... import widgets as W
from ...state import apply_ref, calib_status, edge_key, load_cfg, ref_calib, ref_candidates
from ...theme import C
from ...widgets import T, Banner, Card, Page


class CalibPage(Page):
    title_zh, title_en, icon_name = "能量校准", "Energy calibration", "target"

    def build(self):
        from xafsmith import calib as xcal
        from xafsmith.common import edge_energy
        S = self.S
        self.header(T("每条谱都用同一批测量的单质参比校准：ΔE = E_table − E0_meas（E0 取一阶导数最大值）。同一参比下的谱加同一个 ΔE。",
                      "Every spectrum is calibrated with the elemental reference of the same batch: ΔE = E_table − E0_meas "
                      "(E0 = first-derivative maximum). All spectra of one reference get the same ΔE."))
        c1 = Card(T("参比校准值", "Reference calibrations"))
        rows = [dict(参比=ref, 吸收边=r.get("edge_key", ""), 批次=r.get("batch", ""), E_table=r.get("e_table"),
                     E0_meas=round(r["e0_meas"], 2), ΔE=round(r["delta_e"], 3), 参比测量时间=r.get("ref_time", ""),
                     表值来源=r.get("table_source", "")) for ref, r in S.calib.items()]
        if rows:
            df = pd.DataFrame(rows)
            if W.en():
                df.columns = ["Reference", "Edge", "Batch", "E_table", "E0_meas", "ΔE", "Measured", "Table source"]
            c1.add(W.Table(df))
        else:
            c1.add(Banner("warn", T("还没有校准值：在“载入谱”读入时选参比，或在下方测定，或在“校准与处理”中运行 ②。",
                                    "No calibrations yet: choose a reference when reading, determine one below, or run ② under “Calibrate & process”.")))
        self.add(c1)
        if S.groups:
            c2 = Card(T("已载入谱的校准状态", "Calibration of loaded spectra"))
            srows = []
            for k, g in S.groups.items():
                refs = [r for r in str(getattr(g, "calib_ref", "") or "").split(";") if r in S.calib]
                h = xcal.time_gap_hours(getattr(g, "timestamp", ""), S.calib[refs[0]].get("ref_time")) if refs else None
                srows.append({T("谱", "Spectrum"): k, T("吸收边", "Edge"): edge_key(g),
                              T("当前ΔE", "ΔE now"): round(getattr(g, "e_shift", 0.0) or 0.0, 3),
                              T("状态", "Status"): calib_status(S, g, W.en())[0],
                              T("与参比时间差 (h)", "Gap to reference (h)"): None if h is None else round(h, 2)})
            c2.add(W.Table(pd.DataFrame(srows)))
            if S.calib:
                refsel = W.combo(list(S.calib), self.state.get("ref"), fmt=lambda r: f"{Path(r).name}  ({S.calib[r].get('edge_key', '')}, ΔE {S.calib[r]['delta_e']:+.3f} eV)")
                tg = W.MultiSelect([], [], T("应用到（同一吸收边的谱）", "Apply to (same edge)"))

                def upd():
                    r = refsel.value()
                    self.state["ref"] = r
                    same = [k for k, g in S.groups.items() if edge_key(g) == S.calib[r].get("edge_key")]
                    tg.set_options(same, [k for k in same if not calib_status(S, S.groups[k])[1]])
                refsel.currentIndexChanged.connect(lambda *_: upd())
                upd()

                def apply():
                    done, _ = apply_ref(S, tg.value(), refsel.value())
                    W.toast(self, T(f"已校准 {len(done)} 条谱", f"{len(done)} spectra calibrated"))
                    S.emit("groups")
                    self.refresh()
                c2.add(W.label(T("换参比 / 补校准", "Change reference / calibrate"), "h3"))
                c2.add(W.hbox(W.field(T("参比", "Reference"), refsel), W.field(T("谱", "Spectra"), tg),
                              W.vbox(None, W.button(T("校准所选谱", "Calibrate selected"), primary=True, slot=apply)), spacing=12))
            self.add(c2)
        # 测定
        cands = ref_candidates()
        body = Card()
        if not cands:
            body.add(Banner("warn", T("没有单质参比文件：在 meta.csv 中把金属箔 / 粉标为 role=reference。",
                                      "No elemental reference files: mark foils / powders as role=reference in meta.csv.")))
        else:
            ref = W.combo(cands, self.state.get("cal_ref"))
            etab = W.num(0, 0, 200000, 0.1, 2)
            sm = W.num(1.0, 0, 5, 0.1, 2)
            info = W.label("", "muted")
            plot = W.Plot(320)
            cur = {}

            def load_ref():
                self.state["cal_ref"] = ref.value()
                from xafsmith import pipeline as pl_
                cfg = load_cfg()
                g = pl_.read_meta_row(pl_.meta_row(ref.value()) or {"file": ref.value()}, cfg)
                ek = f"{g.element}_{g.edge}"
                etab.blockSignals(True)
                etab.setValue(float(cfg["edges"].get(ek, {}).get("e_table") or edge_energy(g.element, g.edge)))
                etab.blockSignals(False)
                cur["g"] = g
                calc()

            def calc():
                g = cur["g"]
                r = xcal.calibrate_reference(g, e_table=etab.value(), smooth_ev=sm.value())
                cur["r"] = r
                eg, dmu = g.calib_curve
                plot.clear()
                plot.ax.plot(eg, dmu, label=T("dμ/dE（平滑）", "dμ/dE (smoothed)"))
                plot.ax.axvline(r["e0_meas"], color=C["accent"], ls="--", lw=1, label=f"E0_meas = {r['e0_meas']:.2f}")
                plot.ax.axvline(etab.value(), color=C["err"], ls=":", lw=1, label=f"E_table = {etab.value():.2f}")
                plot.ax.set_xlabel(T("E (eV，未校准)", "E (eV, uncalibrated)") + f" — {Path(ref.value()).name}")
                plot.ax.set_ylabel("dμ/dE")
                plot.draw()
                old = S.calib.get(ref.value())
                info.setText(f"ΔE = E_table − E0_meas = {r['delta_e']:+.3f} eV" +
                             (T(f"　（已保存 {old['delta_e']:+.3f} eV）", f"   (saved {old['delta_e']:+.3f} eV)") if old else ""))
            ref.currentIndexChanged.connect(lambda *_: W.wait_cursor(load_ref))
            calc_d = W.debounced(self, calc)
            etab.valueChanged.connect(calc_d)
            sm.valueChanged.connect(calc_d)

            def save():
                r_ = ref.value()
                ref_calib(S, r_, e_table=etab.value(), smooth_ev=sm.value(), force=True)
                users = [k for k, x in S.groups.items() if r_ in str(getattr(x, "calib_ref", ""))]
                done, _ = apply_ref(S, users, r_)
                W.toast(self, T(f"已保存到 output/calib/calib.json，重新校准 {len(done)} 条谱。",
                                f"Saved to output/calib/calib.json; {len(done)} spectra recalibrated."))
                S.emit("groups")
                self.refresh()
            body.add(W.fields((T("单质参比文件", "Elemental reference"), ref), (T("标准边能量 E_table (eV)", "Tabulated edge E_table (eV)"), etab,
                                                                           T("默认 xafsmith.json / xraydb (Elam) 表值；可改为 Bearden 或文献值",
                                                                             "Default from xafsmith.json / xraydb (Elam); Bearden or literature values allowed")),
                              (T("导数平滑 σ (eV)", "Derivative smoothing σ (eV)"), sm)))
            body.add(plot)
            body.add(W.hbox(info, None, W.button(T("保存此参比的 ΔE 并重新校准用它的谱", "Save ΔE and recalibrate its spectra"),
                                                 primary=True, icon_name="save", slot=save)))
            W.wait_cursor(load_ref)
        self.add(W.collapsible(T("测定 / 重新测定参比 ΔE", "Determine / redetermine a reference ΔE"), body, expanded=not rows))
