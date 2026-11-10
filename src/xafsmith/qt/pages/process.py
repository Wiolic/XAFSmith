"""数据处理：载入谱、质量检查与去毛刺、能量校准、归一化、χ(k) 与 FT、小波变换"""
from __future__ import annotations

import re
from pathlib import Path

import numpy as np
import pandas as pd
from PySide6.QtWidgets import QWidget

from xafsmith import paths
from .. import widgets as W
from ..state import (apply_ref, calib_status, edge_key, has_chi, load_cfg, raw_files, ref_calib, ref_candidates,
                     safe, save_cfg)
from ..theme import C
from ..widgets import T, Banner, Card, Page

NOPHASE = "R (Å) — 未相移校正"


def rlabel():
    return T(NOPHASE, "R (Å) — not phase-corrected")


def need_groups(page):
    if not page.S.groups:
        page.add(Banner("info", T("先在“载入谱”中载入样品。", "Load samples under “Load spectra” first.")))
        btn = W.button(T("去载入谱", "Go to Load spectra"), primary=True, slot=lambda: page.app.go("load"))
        page.add(W.hbox(btn, None))
        return False
    return True


# ============================================================================= 载入谱
class LoadPage(Page):
    title_zh, title_en, icon_name = "载入谱", "Load spectra", "upload"

    def build(self):
        from xafsmith import pipeline as pl
        S = self.S
        self.header(T("按样品载入的谱已校准、已归一化、重复扫描已合并，χ(k) 与 FT 已算（与命令行 process 相同）。",
                      "Samples load calibrated, normalized, merged, with χ(k) and FT (same as the process command)."))
        if pl.META.exists() and pl.CONFIG.exists():
            meta = pl.load_meta()
            samples = list(dict.fromkeys(meta["sample"]))
            edges = sorted(set(meta.edge_key))
            card = Card(T("按样品载入", "Load by sample"))
            ms = W.MultiSelect(samples, self.state.get("samples", []), T("选择样品", "Choose samples"))
            ek = W.combo([""] + edges, self.state.get("edge", ""), fmt=lambda e: e or T("—", "—"))
            refl = W.label("", "faint")

            def upd_refs(sel):
                self.state["samples"] = sel
                refs = sorted(set(meta[meta["sample"].isin(sel)].ref_file) - {""})
                refl.setText(T("校准参比（会一起载入）：", "Calibration references (loaded too): ")
                             + (", ".join(refs) or "—") if sel else "")
            ms.changed.connect(upd_refs)
            upd_refs(ms.value())
            btn = W.button(T("载入", "Load"), primary=True, icon_name="upload")

            def load():
                e = ek.value()
                todo = ms.value() or ([s for s in samples if meta[meta["sample"] == s].edge_key.iloc[0] == e] if e else [])
                if not todo:
                    return
                refs = set(meta[meta["sample"].isin(todo)].ref_file) - {""}
                todo = list(dict.fromkeys(list(meta[meta.file.isin(refs)]["sample"]) + todo))

                def work():
                    cfg = pl.load_config()
                    out, errs = {}, []
                    for s in todo:
                        try:
                            out[s], _ = pl.build_sample(s, cfg, meta)
                        except Exception as ex:      # noqa: BLE001
                            errs.append(f"{s}: {ex}")
                    return out, errs, cfg

                def done(r):
                    out, errs, cfg = r
                    S.groups.update(out)
                    if out:
                        c = pl.edge_cfg(cfg, next(iter(out.values())).edge_key)
                        if c:
                            S.norm_par.update(c["norm"]); S.bkg_par.update(c["bkg"]); S.ft_par.update(c["ft"])
                    S.emit("groups")
                    for e_ in errs:
                        W.toast(self, e_, "err")
                    self.refresh()
                W.run_task(self, work, done, T("载入中…", "Loading…"), btn)
            btn.clicked.connect(load)
            card.add(W.hbox(W.field(T("样品", "Samples"), ms), W.field(T("或整条吸收边", "or a whole edge"), ek),
                            W.vbox(None, btn), spacing=12))
            card.lay.itemAt(card.lay.count() - 1).widget().layout().setStretch(0, 4)
            card.add(refl)
            self.add(card)
        self.add(W.collapsible(T("直接读入文件（BSRF 文本 / Athena .prj / 列文本）", "Read files directly (BSRF / Athena .prj / columns)"),
                               self._direct(), expanded=not (pl.META.exists() and pl.CONFIG.exists())))
        if S.groups:
            self.add(self._loaded())

    def _direct(self):
        from xafsmith import io as xio
        from xafsmith.pipeline import batch_of
        S = self.S
        card = Card()
        rel = [p.relative_to(paths.ROOT).as_posix() for p in raw_files()]
        files = W.tag(W.MultiSelect(rel, [], T("从项目中选择文件", "Choose files from the project")), "imp_files")
        cands = ref_candidates()
        ref = W.tag(W.combo([""] + cands, "", fmt=lambda r: r or T("— 请选择参比 —", "— choose a reference —")), "imp_ref")

        def default_ref(sel):
            same = [c for c in cands if sel and batch_of(c) == batch_of(sel[0])]
            if same:
                ref.setCurrentIndex(cands.index(same[0]) + 1)
        files.changed.connect(default_ref)
        mode = W.combo(["auto", "trans", "fluo"], "auto",
                       fmt=lambda m: {"auto": T("自动（按文件头）", "Auto (from header)"), "trans": "trans", "fluo": "fluo"}[m])
        card.add(W.fields((T("文件", "Files"), files), (T("参比（必选，同批次单质箔 / 粉）", "Reference (required, same batch)"), ref),
                          (T("模式", "Mode"), mode)))
        ecol, i0c, i1c, ifc, muc = W.inum(0, 0, 50), W.inum(1, -1, 50), W.inum(2, -1, 50), W.inum(3, -1, 50), W.inum(-1, -1, 50)
        elem = W.text("")
        card.add(W.collapsible(T("通用列文本设置", "Generic column text"),
                               W.fields((T("能量列", "Energy col"), ecol), (T("I0 列", "I0 col"), i0c), (T("I1 列", "I1 col"), i1c),
                                        (T("If 列", "If col"), ifc), (T("μ 列（-1 由 I 计算）", "μ col (-1: from I)"), muc),
                                        (T("元素", "Element"), elem))))
        card.add(W.label(T("透射 μ = ln(I0/I1)；荧光 μ = If/I0。参比会一起读入，并用它的 ΔE 校准所有谱；.prj 中的谱保持原样。",
                           "Transmission μ = ln(I0/I1); fluorescence μ = If/I0. The reference is read too and its ΔE "
                           "calibrates every spectrum; spectra in .prj files are kept as they are."), "faint"))

        def read():
            sel = files.value()
            r = ref.value()
            if any(not s.lower().endswith(".prj") for s in sel) and not r:
                W.toast(self, T("请先选择参比", "Choose a reference first"), "warn")
                return
            fpaths = [paths.ROOT / s for s in sel]
            errs = []
            if r:
                try:
                    rc = ref_calib(S, r)
                    fpaths = [paths.ROOT / r] + [p for p in fpaths if p != paths.ROOT / r]
                    W.toast(self, T(f"参比 {Path(r).name}：ΔE = {rc['delta_e']:+.3f} eV", f"Reference {Path(r).name}: ΔE = {rc['delta_e']:+.3f} eV"))
                except Exception as ex:      # noqa: BLE001
                    W.toast(self, f"{r}: {ex}", "err")
                    return
            for p in fpaths:
                try:
                    kws = {} if mode.value() == "auto" else {"mode": mode.value()}
                    if p.suffix.lower() == ".prj":
                        for lab, g in xio.read_prj(p).items():
                            S.groups[f"{p.stem}:{lab}"] = g
                        continue
                    if xio.is_bsrf(p):
                        g = xio.read_bsrf(p, **kws)
                    else:
                        nz = lambda v: None if v < 0 else int(v)      # noqa: E731
                        g = xio.read_columns(p, ecol=ecol.value(), i0col=nz(i0c.value()), i1col=nz(i1c.value()),
                                             ifcol=nz(ifc.value()), mucol=nz(muc.value()), mode=kws.get("mode", "trans"),
                                             element=elem.text() or None)
                    lab = p.relative_to(paths.ROOT).as_posix()
                    g.label = lab
                    S.groups[lab] = g
                    done, skipped = apply_ref(S, [lab], r)
                    if skipped:
                        S.groups.pop(lab)
                        errs.append(T(f"{p.name}：吸收边 {edge_key(g)} 与参比不同，未读入", f"{p.name}: edge {edge_key(g)} differs from the reference; skipped"))
                except Exception as ex:      # noqa: BLE001
                    errs.append(f"{p.name}: {ex}")
            for e in errs:
                W.toast(self, e, "err")
            S.emit("groups")
            self.refresh()
        card.add(W.hbox(None, W.button(T("读入", "Read"), primary=True, icon_name="upload", slot=lambda: W.wait_cursor(read))))
        return card

    def _loaded(self):
        S = self.S
        card = Card(T(f"已载入 {len(S.groups)} 条谱", f"{len(S.groups)} spectra loaded"))
        rows = [dict(label=k, element=g.element, edge=g.edge, mode=g.mode, npts=len(g.energy),
                     E_range=f"{g.energy[0]:.0f}–{g.energy[-1]:.0f}", time=getattr(g, "timestamp", ""),
                     dE_cal=round(getattr(g, "e_shift", 0.0) or 0.0, 3),
                     **{T("校准", "calibration"): calib_status(S, g, W.en())[0]},
                     E0=round(getattr(g, "e0", np.nan), 2)) for k, g in S.groups.items()]
        card.add(W.Table(pd.DataFrame(rows), max_height=360))
        rm = W.MultiSelect(list(S.groups), [], T("选择要移除的谱", "Spectra to remove"))

        def remove():
            for k in rm.value():
                S.groups.pop(k, None)
            S.emit("groups")
            self.refresh()
        show = W.MultiSelect(list(S.groups), self.state.get("show", list(S.groups)[:1]), T("选择谱", "Choose spectra"), max_sel=8)
        card.add(W.hbox(W.field(T("查看原始 μ(E) 与通道", "Raw μ(E) and channels"), show),
                        W.field(T("移出会话（不删除文件）", "Remove from session (files kept)"), rm),
                        W.vbox(None, W.button(T("移除", "Remove"), slot=remove)), spacing=12))
        plot = W.Plot(360, 1, 2)
        card.add(plot)

        def draw(sel):
            self.state["show"] = sel
            plot.clear()
            a1, a2 = plot.axes
            for k in sel:
                g = S.groups[k]
                a1.plot(g.energy, g.mu, label=k)
                for ch in ("i0", "i1", "ifl"):
                    a = getattr(g, ch, None)
                    if isinstance(a, np.ndarray) and len(a) == len(g.energy):
                        a2.plot(g.energy, a / np.max(np.abs(a)), lw=1, label=f"{ch}: {Path(k).name}")
            a1.set_title("μ(E)")
            a2.set_title("I0 / I1 / If")
            for a in plot.axes:
                a.set_xlabel("E (eV)")
            plot.draw()
        show.changed.connect(draw)
        draw(show.value())
        return card


# ============================================================================= 质量检查
class QCPage(Page):
    title_zh, title_en, icon_name = "质量检查", "Quality check", "shield"

    def build(self):
        from xafsmith import normalize as xnorm, qc as xqc
        S = self.S
        self.header(T("噪声、毛刺、I0 掉点、边跳、可用 k 范围（k_snr3）、荧光自吸收风险。",
                      "Noise, glitches, I0 drop-outs, edge step, usable k (k_snr3), fluorescence self-absorption risk."))
        if not need_groups(self):
            return
        card = Card(T("检查已载入的谱", "Check loaded spectra"))
        sel = W.MultiSelect(list(S.groups), self.state.get("sel", list(S.groups)), T("选择谱", "Choose spectra"))
        sel.changed.connect(lambda v: self.state.__setitem__("sel", v))

        def run():
            rows = []
            for k in sel.value():
                g = S.groups[k]
                try:
                    if not hasattr(g, "norm_params"):
                        xnorm.normalize(g, **S.norm_par)
                    rows.append(xqc.check(g))
                except Exception as ex:      # noqa: BLE001
                    rows.append(dict(label=k, error=str(ex)))
            df = pd.DataFrame(rows)
            paths.QC.mkdir(parents=True, exist_ok=True)
            df.to_csv(paths.QC_CSV, index=False, encoding="utf-8-sig")
            S.qc = df
            self.refresh()
        card.add(W.hbox(sel, W.button(T("运行检查", "Run check"), primary=True, icon_name="play",
                                      slot=lambda: W.wait_cursor(run)), spacing=12))
        if S.qc is not None:
            card.add(W.Table(S.qc, max_height=420))
            card.add(W.label(T("已保存 output/qc/qc_report.csv。delta_mut：透射边跳；self_abs_risk：荧光谱由 I1 估计的 Δμt；"
                               "k_snr3：k²χ 包络降到 3×噪声处，可作 kmax 参考。",
                               "Saved output/qc/qc_report.csv. delta_mut: transmission edge step; self_abs_risk: Δμt estimated "
                               "from I1 for fluorescence; k_snr3: where the k²χ envelope falls to 3× noise — a guide for kmax."),
                             "faint"))
        self.add(card)
        self.add(self._deglitch())

    def _deglitch(self):
        from xafsmith import pipeline as pl
        S = self.S
        card = Card(T("去毛刺", "Deglitch"))
        card.add(W.label(T("毛刺只占 1–3 个点、宽度远小于 EXAFS 振荡（k≈5 Å⁻¹ 时一个振荡约 30 eV），常在多个样品同一能量出现、I0 也有凹陷；"
                           "真实结构不要删。区间用校准后能量，写进 xafsmith.json 的 deglitch（理由必填），原始文件不变。",
                           "A glitch spans 1–3 points, far narrower than an EXAFS oscillation (~30 eV at k≈5 Å⁻¹), often at the same "
                           "energy in several samples with a dip in I0; never remove real structure. Ranges use calibrated energy and "
                           "are written to deglitch in xafsmith.json (reason required); raw files are untouched."), "faint"))
        if not (pl.META.exists() and pl.CONFIG.exists()):
            card.add(Banner("info", T("需要项目的 meta.csv 与 xafsmith.json", "Needs meta.csv and xafsmith.json")))
            return card
        meta = pl.load_meta()
        samples = [s for s in S.groups if s in set(meta["sample"])]
        if not samples:
            card.add(Banner("info", T("先在“载入谱”中按样品载入。", "Load samples by name under “Load spectra” first.")))
            return card
        cfg = pl.load_config()
        dg, why = cfg.get("deglitch", {}), cfg.get("deglitch_reason", {})
        sel = W.MultiSelect(samples, self.state.get("dg", samples[:1]), T("选择样品（同一区间用于全部所选）", "Samples (same ranges for all)"))
        rng = W.text("", "9984.5-9990; 10321-10327.5")
        reason = W.text("", T("理由（必填）", "Reason (required)"))
        plot = W.Plot(440, 2, 1, sharex=True, height_ratios=[2, 1])

        def draw(v):
            self.state["dg"] = v
            plot.clear()
            a1, a2 = plot.axes
            for i, s in enumerate(v):
                g = S.groups[s]
                y = getattr(g, "flat", getattr(g, "norm", g.mu))
                a1.plot(g.energy, y + 0.1 * i, marker=".", ms=2.5, lw=1, label=s)
                if isinstance(getattr(g, "i0", None), np.ndarray) and len(g.i0) == len(g.energy):
                    a2.plot(g.energy, g.i0 / np.median(g.i0), lw=1)
                for lo, hi in dg.get(s, []):
                    for a in (a1, a2):
                        a.axvspan(lo, hi, color=C["err"], alpha=0.15, lw=0)
            if S.qc is not None and "glitch_E" in S.qc:
                for _, r in S.qc.iterrows():
                    if isinstance(r.get("glitch_E"), str) and any(str(r.get("label", "")).endswith(s) for s in v):
                        for e in r.glitch_E.split(";"):
                            a1.axvline(float(e), color=C["text3"], lw=0.8, ls=":")
            a1.set_title(T("归一化 μ(E)（依次上移 0.1）；灰虚线 = 疑似毛刺，红色 = 已删除", "Normalized μ(E) (offset 0.1); dotted = suspected glitch, red = removed"))
            a2.set_ylabel("I0 / median")
            a2.set_xlabel("E (eV)")
            plot.draw()
            if v:
                rng.setText("; ".join(f"{lo:g}-{hi:g}" for lo, hi in dg.get(v[0], [])))
                reason.setText(why.get(v[0], ""))
        sel.changed.connect(draw)
        card.add(sel)
        card.add(plot)
        card.add(W.fields((T("删除区间（eV，校准后；多个用 ; 分隔）", "Ranges to remove (eV, calibrated; separate with ;)"), rng),
                          (T("理由", "Reason"), reason)))

        def apply(clear=False):
            from ..state import parse_ranges
            v = sel.value()
            if not v:
                return
            try:
                r = [] if clear else parse_ranges(rng.text())
            except ValueError as ex:
                W.toast(self, str(ex), "err")
                return
            if r and not reason.text().strip():
                W.toast(self, T("请填写理由", "Please give a reason"), "warn")
                return
            for s in v:
                if r:
                    dg[s], why[s] = r, reason.text().strip()
                else:
                    dg.pop(s, None); why.pop(s, None)
            cfg["deglitch"], cfg["deglitch_reason"] = dg, why
            save_cfg(cfg)
            for s in v:
                S.groups[s], _ = pl.build_sample(s, cfg, meta)
            S.qc = None
            W.toast(self, T(f"已写入 xafsmith.json 并重新载入 {len(v)} 个样品；请重新运行检查",
                            f"Written to xafsmith.json and {len(v)} samples reloaded; run the check again"))
            self.refresh()
        card.add(W.hbox(None, W.button(T("清除所选样品的去毛刺", "Clear deglitch for selected"), slot=lambda: W.wait_cursor(lambda: apply(True))),
                        W.button(T("保存并重新载入", "Save and reload"), primary=True, icon_name="save",
                                 slot=lambda: W.wait_cursor(apply))))
        draw(sel.value())
        return card


# ============================================================================= 能量校准
class CalibPage(Page):
    title_zh, title_en, icon_name = "能量校准", "Energy calibration", "target"

    def build(self):
        from xafsmith import calib as xcal, io as xio
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
                g = xio.read_bsrf(paths.ROOT / ref.value())
                cfg = load_cfg()
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
            etab.valueChanged.connect(lambda *_: calc())
            sm.valueChanged.connect(lambda *_: calc())

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


# ============================================================================= 归一化
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


class NormPage(Page):
    title_zh, title_en, icon_name = "归一化", "Normalization", "edge"

    def build(self):
        from xafsmith import io as xio, normalize as xnorm
        from xafsmith.common import write_params
        S = self.S
        self.header(T("所有样品使用同一套归一化参数（相对 E0 的 eV）。", "One normalization parameter set for all samples (eV relative to E0)."))
        if not need_groups(self):
            return
        ctl = Card()
        nf = norm_fields(S.norm_par)
        sel = W.MultiSelect(list(S.groups), self.state.get("sel", list(S.groups)[:1]), T("选择谱", "Choose spectra"))
        cur = W.combo(sel.value() or list(S.groups)[:1], self.state.get("cur"))
        flat = W.check("flattened", self.state.get("flat", True))
        rel = W.check(T("横轴 E − E0", "x axis E − E0"), self.state.get("rel", False))
        ctl.add(nf)
        ctl.add(W.hbox(W.field(T("谱", "Spectra"), sel), W.field(T("显示边前 / 边后线的谱", "Pre/post-edge lines for"), cur), spacing=12))
        self.add(ctl)
        p1, p2, p3 = W.Plot(380), W.Plot(420), W.Plot(380)
        e0lbl = W.label("", "muted")
        merge = self._merge(sel)
        self.add(W.tabs((T("μ(E) 与边前 / 边后", "μ(E) with pre/post-edge"), W.vbox(p1, e0lbl)),
                        (T("归一化叠加", "Normalized overlay"), W.vbox(W.hbox(flat, rel, None), p2)),
                        (T("导数", "Derivative"), p3), (T("合并扫描", "Merge scans"), merge)))

        def update():
            S.norm_par.update(nf.read())
            v = sel.value()
            self.state.update(sel=v, flat=flat.isChecked(), rel=rel.isChecked())
            cur.blockSignals(True)
            keep = cur.value()
            cur.clear()
            cur._vals = v or []
            cur.addItems(v)
            if keep in v:
                cur.setCurrentIndex(v.index(keep))
            cur.blockSignals(False)
            for k in v:
                try:
                    xnorm.normalize(S.groups[k], **{**S.norm_par, "e0": S.norm_par.get("e0") if len(v) == 1 else None})
                except Exception as ex:      # noqa: BLE001
                    W.toast(self, f"{k}: {ex}", "err")
            if not v:
                for p in (p1, p2, p3):
                    p.message(T("选择谱", "Choose spectra"))
                return
            g = S.groups[cur.value() or v[0]]
            self.state["cur"] = cur.value()
            p1.clear()
            a = p1.ax
            a.plot(g.energy, g.mu, label="μ(E)")
            a.plot(g.energy, g.pre_edge, ls="--", lw=1, label="pre-edge")
            a.plot(g.energy, g.post_edge, ls="--", lw=1, label="post-edge")
            pp = g.norm_params
            for x in (pp["pre1"], pp["pre2"], pp["norm1"], pp["norm2"]):
                a.axvline(g.e0 + x, color=C["text3"], lw=0.6)
            a.axvline(g.e0, color=C["err"], lw=1)
            a.set_xlabel("E (eV)")
            a.set_ylabel("μ(E)")
            p1.draw()
            e0lbl.setText(f"E0 = {g.e0:.2f} eV,  edge step = {g.edge_step:.4f}" +
                          (T("（透射：= Δμt）", " (transmission: = Δμt)") if g.mode == "trans" else ""))
            p2.clear()
            for k in v:
                gg = S.groups[k]
                p2.ax.plot(gg.energy - (gg.e0 if rel.isChecked() else 0), gg.flat if flat.isChecked() else gg.norm, label=k)
            p2.ax.set_xlabel("E − E0 (eV)" if rel.isChecked() else "E (eV)")
            p2.ax.set_ylabel(T("归一化 μ(E)", "normalized μ(E)"))
            p2.draw()
            p3.clear()
            for k in v:
                gg = S.groups[k]
                p3.ax.plot(gg.energy, np.gradient(gg.flat, gg.energy), label=k)
            p3.ax.set_xlabel("E (eV)")
            p3.ax.set_ylabel("d(norm μ)/dE")
            p3.draw()
        nf.connect(update)
        sel.changed.connect(lambda *_: update())
        cur.currentIndexChanged.connect(lambda *_: update())
        flat.toggled.connect(lambda *_: update())
        rel.toggled.connect(lambda *_: update())
        update()

        exp = Card(T("导出", "Export"))

        def export_nor():
            od = paths.GUI / "norm"
            od.mkdir(parents=True, exist_ok=True)
            for k in sel.value():
                xio.write_group_columns(S.groups[k], od / (safe(k) + ".nor"))
            write_params(od / "norm.params.json", S.norm_par, "gui:normalize")
            W.toast(self, T(f"已导出 {len(sel.value())} 条到 {paths.rel(od)}", f"Exported {len(sel.value())} to {paths.rel(od)}"))
        prj_name = W.tag(W.text(f"{paths.ROOT.name}_xafsmith.prj"), "prj_name")

        def export_prj():
            try:
                fn = paths.GUI / "athena" / (prj_name.text() if prj_name.text().endswith(".prj") else prj_name.text() + ".prj")
                fn.parent.mkdir(parents=True, exist_ok=True)
                xio.write_prj([S.groups[k] for k in sel.value()], fn,
                              norm={k: v for k, v in S.norm_par.items() if k in ("pre1", "pre2", "norm1", "nnorm")},
                              bkg=S.bkg_par, ft=S.ft_par)
                W.toast(self, T(f"已导出 {paths.rel(fn)}（{len(sel.value())} 条谱）", f"Exported {paths.rel(fn)} ({len(sel.value())} spectra)"))
            except Exception as ex:      # noqa: BLE001
                W.toast(self, str(ex), "err")
        exp.add(W.hbox(W.button(T("导出所选归一化数据到 output/gui/norm/", "Export selected to output/gui/norm/"), icon_name="download",
                                slot=export_nor), None))
        exp.add(W.label(T("Athena 工程（.prj）：写入已校准能量与 μ(E)，以及本软件的 E0、边前/边后范围、rbkg、k 范围、窗函数，可在 Athena / Artemis 中直接对照。",
                          "Athena project (.prj): calibrated energy and μ(E) plus this software's E0, pre/post-edge ranges, rbkg, "
                          "k range and window, for a direct comparison in Athena / Artemis."), "faint"))
        exp.add(W.hbox(W.field(T("文件名", "File name"), prj_name), W.vbox(None, W.button(T("导出 .prj", "Export .prj"),
                                                                                        icon_name="download", slot=export_prj)), None))
        self.add(exp)

    def _merge(self, sel):
        from xafsmith import normalize as xnorm
        S = self.S
        w = QWidget()
        lay = W.QVBoxLayout(w)
        lay.setContentsMargins(0, 8, 0, 0)
        lay.addWidget(W.label(T("先逐条检查再平均：与中位谱 RMS 偏差超过阈值的扫描自动剔除，也可手动剔除。",
                                "Inspect, then average: scans deviating from the median by more than the threshold are "
                                "rejected automatically; you can also reject scans manually."), "faint"))
        msel = W.MultiSelect(list(S.groups), sel.value(), T("要合并的扫描", "Scans to merge"))
        rej = W.MultiSelect(list(S.groups), [], T("手动剔除", "Reject manually"))
        tol = W.num(4.0, 1, 20, 0.5)
        name = W.text("merge")
        out = W.vbox()
        lay.addWidget(W.fields((T("扫描", "Scans"), msel), (T("手动剔除", "Reject"), rej), (T("阈值（×中位 RMS）", "Threshold (× median RMS)"), tol),
                               (T("合并后名称", "Merged name"), name)))

        def go():
            v = msel.value()
            if len(v) < 2:
                return
            m, rep = xnorm.merge_scans([S.groups[k] for k in v], label=name.text(), reject=rej.value(), tol_sigma=tol.value())
            S.groups[name.text()] = m
            pd.DataFrame(rep).to_csv(paths.GUI / f"merge_{safe(name.text())}.csv", index=False, encoding="utf-8-sig")
            W._clear_layout(out.layout())
            out.layout().addWidget(Banner("ok", T(f"已生成 {name.text()}（{m.nscans} 条扫描）", f"Created {name.text()} ({m.nscans} scans)")))
            out.layout().addWidget(W.Table(pd.DataFrame(rep)))
            S.emit("groups")
        lay.addWidget(W.hbox(None, W.button(T("合并", "Merge"), primary=True, slot=lambda: W.wait_cursor(go))))
        lay.addWidget(out)
        lay.addStretch(1)
        return w


# ============================================================================= χ(k) 与 FT
class ChiPage(Page):
    title_zh, title_en, icon_name = "χ(k) 与 FT", "χ(k) & FT", "wave"

    def build(self):
        from xafsmith import autobk as xbkg, ft as xft, mut_planner as xmut, normalize as xnorm
        from xafsmith.common import n_idp, r_resolution, write_params
        S = self.S
        self.header(T("背景扣除与傅里叶变换。k¹ / k² / k³ 都要看；k 范围按最差样品的信噪比定，一组样品用同一个范围。",
                      "Background removal and Fourier transform. Look at k¹ / k² / k³; set the k range from the worst sample "
                      "and use one range for the whole series."))
        if not need_groups(self):
            return
        b, f = S.bkg_par, S.ft_par
        ctl = Card()
        w = dict(rbkg=W.num(b["rbkg"], 0.5, 3, 0.1), bkw=W.combo([0, 1, 2, 3], int(b["kweight"])),
                 kmin=W.num(f["kmin"], 0, 10, 0.1), kmax=W.num(f["kmax"], 3, 25, 0.1), dk=W.num(f["dk"], 0, 5, 0.1),
                 win=W.combo(["hanning", "kaiser", "sine", "parzen", "welch"], f["window"]),
                 fkw=W.combo([1, 2, 3], int(f["kweight"])), rmax=W.num(self.state.get("rmax", 6.0), 2, 10, 0.5))
        ctl.add(W.fields(("rbkg", w["rbkg"]), (T("背景 k 权重", "bkg k-weight"), w["bkw"]), ("kmin", w["kmin"]),
                         ("kmax", w["kmax"]), ("dk", w["dk"]), (T("窗函数", "Window"), w["win"]),
                         (T("FT k 权重", "FT k-weight"), w["fkw"]), (T("作图 Rmax", "Plot Rmax"), w["rmax"])))
        sel = W.MultiSelect(list(S.groups), self.state.get("sel", list(S.groups)[:1]), T("选择谱", "Choose spectra"))
        showre = W.check(T("显示 Re χ(R)", "Show Re χ(R)"), self.state.get("re", False))
        ctl.add(W.hbox(sel, showre, spacing=12))
        self.add(ctl)
        pk, pr, pb = W.Plot(380), W.Plot(400), W.Plot(360)
        kcheck = QWidget()
        kl = W.QVBoxLayout(kcheck)
        kl.setContentsMargins(0, 8, 0, 0)
        g0 = S.groups[sel.value()[0]] if sel.value() else next(iter(S.groups.values()))
        elems = W.text(self.state.get("elems", g0.element or ""))
        rmin_, rmax_ = W.num(1.0, 0.5, 6, 0.05), W.num(3.0, 1, 8, 0.05)
        kres = W.vbox()
        kl.addWidget(W.fields((T("样品中所有元素（逗号分隔）", "All elements in the sample (comma-separated)"), elems),
                              (T("拟合 Rmin", "Fit Rmin"), rmin_), (T("拟合 Rmax", "Fit Rmax"), rmax_)))
        kl.addWidget(kres)
        kl.addStretch(1)
        self.add(W.tabs(("χ(k)", pk), ("|χ(R)| / Re", W.vbox(pr, W.label(T("R 轴未相移校正：峰位比真实键长短约 0.3–0.5 Å。",
                                                                            "R is not phase-corrected: peaks appear ~0.3–0.5 Å shorter than bond lengths."), "faint"))),
                        (T("背景 μ0(E)", "Background μ0(E)"), pb), (T("k 范围检查", "k-range check"), kcheck)))

        def update():
            b.update(rbkg=w["rbkg"].value(), kweight=w["bkw"].value())
            f.update(kmin=w["kmin"].value(), kmax=w["kmax"].value(), dk=w["dk"].value(), window=w["win"].value(),
                     kweight=w["fkw"].value())
            v = sel.value()
            self.state.update(sel=v, re=showre.isChecked(), rmax=w["rmax"].value(), elems=elems.text())
            for k in v:
                try:
                    g = S.groups[k]
                    if not hasattr(g, "norm_params"):
                        xnorm.normalize(g, **S.norm_par)
                    xbkg.autobk(g, **b)
                    xft.forward(g, **f)
                except Exception as ex:      # noqa: BLE001
                    W.toast(self, f"{k}: {ex}", "err")
            v = [k for k in v if has_chi(S.groups[k])]
            if not v:
                for p in (pk, pr, pb):
                    p.message(T("选择谱", "Choose spectra"))
                return
            kw = int(f["kweight"])
            pk.clear()
            for k in v:
                g = S.groups[k]
                pk.ax.plot(g.k, g.chi * g.k ** kw, label=k)
            g0 = S.groups[v[0]]
            sc = max(np.max(np.abs(S.groups[k].chi * S.groups[k].k ** kw)) for k in v)
            pk.ax.plot(g0.k, g0.kwin * sc, ls=":", color=C["text3"], label=T("窗函数", "window"))
            pk.ax.set_xlabel("k (Å⁻¹)")
            pk.ax.set_ylabel(f"k$^{kw}$χ(k)")
            pk.draw()
            pr.clear()
            for k in v:
                g = S.groups[k]
                pr.ax.plot(g.r, g.chir_mag, label=f"|χ(R)| {k}")
                if showre.isChecked():
                    pr.ax.plot(g.r, g.chir_re, lw=0.9, label=f"Re {k}")
            pr.ax.set_xlim(0, w["rmax"].value())
            pr.ax.set_xlabel(rlabel())
            pr.ax.set_ylabel(f"|χ(R)| (Å$^{{-{kw + 1}}}$)")
            pr.draw()
            pb.clear()
            pb.ax.plot(g0.energy, g0.mu, label="μ(E)")
            pb.ax.plot(g0.energy, g0.bkg, label=T("μ0(E) 背景", "μ0(E) background"))
            pb.ax.set_xlabel("E (eV)")
            pb.draw()
            W._clear_layout(kres.layout())
            try:
                kl_, df = xmut.k_limit([e.strip() for e in elems.text().split(",") if e.strip()], g0.element, g0.edge,
                                       g0.energy[-1])
                kres.layout().addWidget(W.label(T(f"数据末端 k = {g0.k[-1]:.2f} Å⁻¹；考虑干扰边后可用 k 上限 ≈ <b>{kl_:.2f} Å⁻¹</b>",
                                                  f"Data end k = {g0.k[-1]:.2f} Å⁻¹; usable k limit with interfering edges ≈ <b>{kl_:.2f} Å⁻¹</b>"), rich=True))
                kres.layout().addWidget(W.Table(df))
            except Exception as ex:      # noqa: BLE001
                kres.layout().addWidget(Banner("err", str(ex)))
            kres.layout().addWidget(W.label(
                T(f"ΔR 分辨率 = π/(2Δk) = <b>{r_resolution(f['kmin'], f['kmax']):.3f} Å</b>；N_idp = 2ΔkΔR/π = "
                  f"<b>{n_idp(f['kmin'], f['kmax'], rmin_.value(), rmax_.value()):.1f}</b>",
                  f"ΔR resolution = π/(2Δk) = <b>{r_resolution(f['kmin'], f['kmax']):.3f} Å</b>; N_idp = 2ΔkΔR/π = "
                  f"<b>{n_idp(f['kmin'], f['kmax'], rmin_.value(), rmax_.value()):.1f}</b>"), rich=True))
        for x in ("rbkg", "kmin", "kmax", "dk", "rmax"):
            w[x].valueChanged.connect(lambda *_: W.wait_cursor(update))
        for x in ("bkw", "win", "fkw"):
            w[x].currentIndexChanged.connect(lambda *_: W.wait_cursor(update))
        sel.changed.connect(lambda *_: W.wait_cursor(update))
        showre.toggled.connect(lambda *_: update())
        elems.editingFinished.connect(update)
        rmin_.valueChanged.connect(lambda *_: update())
        rmax_.valueChanged.connect(lambda *_: update())
        W.wait_cursor(update)

        def export():
            od = paths.GUI / "chi"
            od.mkdir(parents=True, exist_ok=True)
            kw = int(f["kweight"])
            for k in sel.value():
                g = S.groups[k]
                base = safe(k)
                np.savetxt(od / f"{base}.chik", np.column_stack([g.k, g.chi, g.chi * g.k ** kw, g.kwin]),
                           header=f"k chi chi*k^{kw} win", fmt="%.6g")
                np.savetxt(od / f"{base}.chir", np.column_stack([g.r, g.chir_mag, g.chir_re, g.chir_im]),
                           header="r(no phase corr) mag re im", fmt="%.6g")
            write_params(od / "chi.params.json", dict(norm=S.norm_par, bkg=b, ft=f), "gui:chi")
            W.toast(self, T(f"已导出到 {paths.rel(od)}", f"Exported to {paths.rel(od)}"))
        self.add(W.hbox(None, W.button(T("导出 χ(k) 与 χ(R) 到 output/gui/chi/", "Export χ(k) and χ(R) to output/gui/chi/"),
                                       icon_name="download", slot=export)))


# ============================================================================= 小波
WT_HELP_ZH = """
<h3>小波图上看什么</h3>
<p>横轴是 k，纵轴是 R（未相移校正）。在同一个 R 处，<b>散射体越重，|W| 的极大值出现在越高的 k</b>
（背散射振幅的包络随原子序数增大移向高 k）。所以 FT 中 R 相近、分不开的两个峰，可以在小波图上按 k 位置分开。</p>

<h3>η 与 σ（Morlet）</h3>
<p>本软件的 Morlet 定义中，图的形状只由乘积 <b>ησ</b> 决定；单独改 η 只改变整体幅度。在某个 R 处：</p>
<ul>
<li>k 方向的模糊宽度 ≈ ησ / (2R)</li>
<li>R 方向的模糊宽度 ≈ R / (ησ)</li>
</ul>
<p>两者此消彼长。例：R = 2 Å、η = 10、σ = 1 时，k 方向约 2.5 Å⁻¹，R 方向约 0.2 Å。</p>
<ul>
<li><b>ησ 调大</b>：R 方向更锐利，能分开相近的壳层；但 k 方向变宽，轻、重散射体的 k 位置更难区分。</li>
<li><b>ησ 调小</b>：k 方向更锐利，便于比较极大值的 k 位置；但相近 R 的壳层会糊在一起。</li>
<li><b>建议</b>：先用 η ≈ 10、σ ≈ 1，再上下各调一次，确认结论不变。</li>
</ul>

<h3>k 权重</h3>
<ul>
<li>权重越高，高 k 部分被放大，<b>所有极大值都向高 k 移动</b>；重散射体相对增强，轻散射体（O、C、N）减弱。</li>
<li>只比较<b>同一 k 权重</b>下的 k 位置。</li>
<li>判断某个特征是轻还是重散射体：k¹ 与 k³ 都看，随权重升高明显减弱的是轻散射体。</li>
</ul>

<h3>k 范围、Rmax 与 Cauchy</h3>
<ul>
<li>k 范围用到“χ(k) 与 FT”中的 kmax 为止。靠近数据两端（约一个 k 方向宽度以内）的图形会变形；高 k 噪声会随 k 权重放大。</li>
<li><b>Rmax</b> 只改变显示范围。</li>
<li><b>Cauchy</b> 小波（Larch 实现）形状固定、没有可调参数，可用来交叉检查 Morlet 的结论。</li>
</ul>

<h3>适合分析什么</h3>
<ul>
<li>第二壳层是 M–M，还是 M–O / M–O–M；</li>
<li>单原子与团簇 / 纳米颗粒：有没有高 k 的 M–M 极大值；</li>
<li>识别 FT 中重叠的壳层；</li>
<li>判断一个小峰是不是真实散射：真实散射在 k 方向有连续的极大值，噪声与截断旁瓣通常没有。</li>
</ul>

<h3>不适合做什么</h3>
<p>给出配位数、键长或组成——这些要靠拟合；小波图只提供定性判据。不同样品对比时，所有参数（k 范围、k 权重、η、σ）必须相同。</p>
"""
WT_HELP_EN = """
<h3>What the map shows</h3>
<p>k on the horizontal axis, R (not phase-corrected) on the vertical axis. At the same R, <b>the heavier the scatterer, the higher
the k of the |W| maximum</b> (the backscattering amplitude envelope moves to higher k with atomic number). Two FT peaks at similar
R can therefore be separated by their k position.</p>

<h3>η and σ (Morlet)</h3>
<p>In this software's Morlet definition the shape of the map depends only on the product <b>ησ</b>; η alone only rescales the
amplitude. At a given R:</p>
<ul>
<li>blur along k ≈ ησ / (2R)</li>
<li>blur along R ≈ R / (ησ)</li>
</ul>
<p>One improves as the other worsens. Example: R = 2 Å, η = 10, σ = 1 gives ≈ 2.5 Å⁻¹ along k and ≈ 0.2 Å along R.</p>
<ul>
<li><b>Larger ησ</b>: sharper in R, separates close shells, but broader in k, so light and heavy scatterers are harder to tell apart.</li>
<li><b>Smaller ησ</b>: sharper in k, better for comparing the k of maxima, but close shells merge.</li>
<li><b>Advice</b>: start with η ≈ 10, σ ≈ 1, then try one step up and down and check that the conclusion does not change.</li>
</ul>

<h3>k-weight</h3>
<ul>
<li>Higher weights amplify high k and <b>shift every maximum to higher k</b>; heavy scatterers gain, light ones (O, C, N) fade.</li>
<li>Compare k positions only at the <b>same k-weight</b>.</li>
<li>To decide whether a feature is light or heavy, look at k¹ and k³: features that fade at higher weight are light scatterers.</li>
</ul>

<h3>k range, Rmax and Cauchy</h3>
<ul>
<li>The k range runs up to kmax set under “χ(k) &amp; FT”. Features within about one k-blur width of either end are distorted;
high-k noise is amplified by the k-weight.</li>
<li><b>Rmax</b> only changes the display.</li>
<li>The <b>Cauchy</b> wavelet (Larch) has a fixed shape and no parameters — use it to cross-check Morlet results.</li>
</ul>

<h3>Good for</h3>
<ul>
<li>telling whether a second shell is M–M or M–O / M–O–M;</li>
<li>single atoms vs clusters / nanoparticles: is there a high-k M–M maximum?</li>
<li>spotting overlapping shells;</li>
<li>checking whether a small FT peak is real scattering: real scattering has a coherent maximum along k, noise and truncation
ripples usually do not.</li>
</ul>

<h3>Not for</h3>
<p>Coordination numbers, bond lengths or composition — those need fitting; the wavelet map is a qualitative criterion. When
comparing samples, use identical k range, k-weight, η and σ.</p>
"""


def show_wavelet_guide(parent):
    W.info_window(parent, "wt_guide", T("小波变换：参数怎么调、适合分析什么", "Wavelet transform: parameters and what it is good for"),
                  WT_HELP_EN if W.en() else WT_HELP_ZH)


class WaveletPage(Page):
    """小波变换：可选两条谱左右对比（同一套参数），R 区间极大值表合并显示，导出每条谱的数据与图"""
    title_zh, title_en, icon_name = "小波变换", "Wavelet transform", "grid"
    max_width = 1500

    def build(self):
        from xafsmith import wavelet as xwav
        from ..state import parse_ranges
        S = self.S
        self.header(T("同一 R 处，重散射体的极大值出现在较高 k，轻散射体（O 等）在较低 k。可选第二条谱左右对比（参数完全相同）。",
                      "At the same R, heavy scatterers peak at higher k, light scatterers (O, …) at lower k. Pick a second "
                      "spectrum to compare side by side (identical parameters)."),
                    actions=[W.button(T("参数怎么调、适合分析什么", "Parameters · what it is good for"), icon_name="help",
                                      slot=lambda: show_wavelet_guide(self))])
        cands = [k for k, g in S.groups.items() if has_chi(g)]
        if not cands:
            self.add(Banner("info", T("先在“χ(k) 与 FT”中计算 χ(k)。", "Compute χ(k) under “χ(k) & FT” first.")))
            return
        st = self.state
        NONE = ""
        ctl = Card()
        w = dict(k=W.combo(cands, st.get("k")),
                 k2=W.combo([NONE] + cands, st.get("k2", NONE) if st.get("k2", NONE) in cands else NONE,
                            fmt=lambda x: x or T("（不对比）", "(none)")),
                 kind=W.combo(["Morlet", "Cauchy"], st.get("kind", "Morlet")),
                 kw=W.combo([1, 2, 3], st.get("kw", 2)), eta=W.num(st.get("eta", 10), 1, 30, 1),
                 sig=W.num(st.get("sig", 1.0), 0.2, 5, 0.1), rmax=W.num(st.get("rmax", 5.0), 2, 8, 0.5))
        same = W.check(T("两图共用色标（比较绝对强度）", "Shared colour scale (compare absolute |W|)"), st.get("same", False))
        ctl.add(W.fields((T("谱（左）", "Spectrum (left)"), w["k"]), (T("对比谱（右）", "Compare with (right)"), w["k2"]),
                         (T("母小波", "Mother wavelet"), w["kind"]), (T("k 权重", "k-weight"), w["kw"]), cols=4))
        ctl.add(W.fields(("η (Morlet)", w["eta"]), ("σ (Morlet)", w["sig"]), (T("显示 Rmax", "Display Rmax"), w["rmax"]),
                         ("", same), cols=4))
        res = W.label("", "muted", rich=True)
        ctl.add(res)
        self.add(ctl)
        two = bool(st.get("k2")) and st.get("k2") in cands and st.get("k2") != w["k"].value()
        plot = W.Plot(470 if two else 560, 1, 2 if two else 1)
        self.add(plot)
        # 各 R 区间的极大值
        mx = Card(T("各 R 区间的极大值", "Maxima in R windows"))
        rng = W.text(st.get("rng", "1.0-2.0; 2.0-3.6"), "1.0-2.0; 2.0-3.6")
        mx.add(W.field(T("R 区间（Å，未相移校正；多个用 ; 分隔）", "R windows (Å, not phase-corrected; separate with ;)"), rng))
        holder = W.vbox()
        mx.add(holder)
        mx.add(W.label(T("比较两条谱同一 R 区间的“极大值所在 k”：k 越高，该壳层中重散射体的贡献越大。只在参数完全相同时可比。",
                         "Compare the “k at maximum” of one R window between spectra: higher k means more heavy-scatterer "
                         "contribution. Comparable only with identical parameters."), "faint"))
        self.add(mx)
        cur = {}

        def compute(name):
            g = S.groups[name]
            m = g.k <= S.ft_par["kmax"]
            rmax = w["rmax"].value()
            if w["kind"].value() == "Morlet":
                kk, rr, Wt = xwav.morlet(g.k[m], g.chi[m], kweight=w["kw"].value(), rmax=rmax, eta=w["eta"].value(),
                                         sigma=w["sig"].value())
            else:
                from larch import Group
                kk, rr, Wt = xwav.cauchy(Group(k=g.k[m], chi=g.chi[m]), kweight=w["kw"].value(), rmax_out=rmax)
                mm = (rr <= rmax) & (rr > 0)
                rr, Wt = rr[mm], Wt[mm]
            return dict(name=name, g=g, kk=np.asarray(kk), rr=np.asarray(rr), W=np.asarray(Wt))

        def maxima(d):
            rows = []
            wins = parse_ranges(rng.text())
            kk, rr, Wt = d["kk"], d["rr"], d["W"]
            for lo, hi in wins:
                sel = (rr >= lo) & (rr <= hi)
                if not sel.any():
                    continue
                sub = Wt[sel]
                i, j = np.unravel_index(np.argmax(sub), sub.shape)
                rows.append({T("样品", "Sample"): d["name"], T("R 区间 (Å)", "R window (Å)"): f"{lo:g}–{hi:g}",
                             T("极大值所在 k (Å⁻¹)", "k at maximum (Å⁻¹)"): round(float(kk[j]), 2),
                             T("极大值所在 R (Å)", "R at maximum (Å)"): round(float(rr[sel][i]), 2), "|W| max": float(sub[i, j])})
            return pd.DataFrame(rows)

        def update():
            st.update(k=w["k"].value(), k2=w["k2"].value(), kind=w["kind"].value(), kw=w["kw"].value(), eta=w["eta"].value(),
                      sig=w["sig"].value(), rmax=w["rmax"].value(), rng=rng.text(), same=same.isChecked())
            names = [w["k"].value()] + ([w["k2"].value()] if w["k2"].value() and w["k2"].value() != w["k"].value() else [])
            data = [compute(n) for n in names]
            cur["data"] = data
            tabs, err = [], None
            for d in data:
                try:
                    d["tab"] = maxima(d)
                    tabs.append(d["tab"])
                except ValueError as ex:
                    d["tab"], err = None, str(ex)
            vmax = max(float(d["W"].max()) for d in data) if same.isChecked() else None
            for cb in cur.get("cbs", []):
                try:
                    cb.remove()
                except Exception:
                    pass
            cur["cbs"] = []
            for ax, d in zip(plot.axes, data):
                ax.clear()
                ax.grid(False)
                im = ax.pcolormesh(d["kk"], d["rr"], d["W"], shading="auto", cmap="jet", vmin=0 if vmax else None, vmax=vmax)
                cur["cbs"].append(plot.fig.colorbar(im, ax=ax, shrink=0.9))
                t = d.get("tab")
                if isinstance(t, pd.DataFrame) and len(t):
                    ax.scatter(t.iloc[:, 2], t.iloc[:, 3], marker="+", s=90, color="white", linewidths=1.6, zorder=3)
                ax.set_xlabel("k (Å⁻¹)")
                ax.set_ylabel(rlabel())
                ax.set_title(d["name"], fontsize=10)
                ax.set_box_aspect(1)            # 图框 1:1
            plot.draw(legend=False)
            W._clear_layout(holder.layout())
            if err:
                holder.layout().addWidget(Banner("err", err))
            elif tabs and sum(len(x) for x in tabs):
                holder.layout().addWidget(W.Table(pd.concat(tabs, ignore_index=True)))
            if w["kind"].value() == "Morlet":
                es = w["eta"].value() * w["sig"].value()
                res.setText(T(f"当前分辨率：R = 2 Å 处 k 方向约 <b>{es / 4:.2f} Å⁻¹</b>、R 方向约 <b>{2 / es:.2f} Å</b>；"
                              f"R = 3 Å 处约 <b>{es / 6:.2f} Å⁻¹</b>、<b>{3 / es:.2f} Å</b>（ησ = {es:g}）",
                              f"Current resolution: at R = 2 Å about <b>{es / 4:.2f} Å⁻¹</b> along k and <b>{2 / es:.2f} Å</b> along R; "
                              f"at R = 3 Å about <b>{es / 6:.2f} Å⁻¹</b> and <b>{3 / es:.2f} Å</b> (ησ = {es:g})"))
            else:
                res.setText(T("Cauchy 小波：形状固定，η、σ 不起作用。", "Cauchy wavelet: fixed shape; η and σ have no effect."))
            w["eta"].setEnabled(w["kind"].value() == "Morlet")
            w["sig"].setEnabled(w["kind"].value() == "Morlet")
        for x in ("k", "k2"):          # 换谱 / 打开或关闭对比：重建页面（一图或左右两图）
            w[x].currentIndexChanged.connect(lambda *_: (st.update(k=w["k"].value(), k2=w["k2"].value()), self.refresh()))
        for x in ("kind", "kw"):
            w[x].currentIndexChanged.connect(lambda *_: W.wait_cursor(update))
        for x in ("eta", "sig", "rmax"):
            w[x].valueChanged.connect(lambda *_: W.wait_cursor(update))
        same.toggled.connect(lambda *_: W.wait_cursor(update))
        rng.editingFinished.connect(lambda: W.wait_cursor(update))
        W.wait_cursor(update)

        def export():
            from xafsmith import pubfig as pf
            from xafsmith.common import write_params
            from ..state import plain_rc
            od = paths.GUI / "wavelet"
            od.mkdir(parents=True, exist_ok=True)
            kind = w["kind"].value()
            names = []
            for d in cur.get("data", []):
                kk, rr, Wt = d["kk"], d["rr"], d["W"]
                base = od / f"{safe(d['name'])}_{kind.lower()}_k{w['kw'].value()}"
                # 矩阵：第一行为 k，第一列为 R
                mat = np.vstack([np.concatenate([[np.nan], kk]), np.column_stack([rr, Wt])])
                np.savetxt(base.with_suffix(".csv"), mat, delimiter=",", fmt="%.6g",
                           header="first row: k (1/A); first column: R (A, not phase-corrected); values: |W|", comments="# ")
                if isinstance(d.get("tab"), pd.DataFrame):
                    d["tab"].to_csv(str(base) + "_maxima.csv", index=False, encoding="utf-8-sig")
                par = dict(sample=d["name"], wavelet=kind, kweight=w["kw"].value(), kmax=S.ft_par["kmax"],
                           rmax=w["rmax"].value(), r_windows=rng.text())
                if kind == "Morlet":
                    par.update(eta=w["eta"].value(), sigma=w["sig"].value())
                write_params(str(base) + ".params.json", par, "gui:wavelet")
                with plain_rc():
                    fig, cap = pf.wavelet(kk, rr, Wt, label=d["name"], rmax=w["rmax"].value(), kweight=w["kw"].value())
                    pf.save(fig, cap, base, ("png", "svg"), dpi=600)
                names.append(base.name)
            W.toast(self, T(f"已导出到 {paths.rel(od)}：", f"Exported to {paths.rel(od)}: ") + "、".join(names)
                    + T("（各含 .csv / _maxima.csv / .png / .svg / .params.json）", " (.csv / _maxima.csv / .png / .svg / .params.json each)"))
        ctl.add(W.hbox(W.button(T("打开 output/gui/wavelet", "Open output/gui/wavelet"), icon_name="external",
                                 slot=lambda: W.open_folder(paths.GUI / "wavelet")), None,
                        W.button(T("导出数据与图", "Export data and figure"), primary=True, icon_name="download",
                                 slot=lambda: W.wait_cursor(export))))
