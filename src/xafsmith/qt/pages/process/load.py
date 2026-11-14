"""载入谱页面。"""

from __future__ import annotations

from xafsmith import logs
from pathlib import Path
import numpy as np
import pandas as pd
from xafsmith import paths
from ... import widgets as W
from ...state import apply_ref, calib_status, edge_key, load_cfg, raw_files, ref_calib, ref_candidates
from ...widgets import T, Card, Page


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
            W.bind_task(btn, "load", "groups")

            def load():
                e = ek.value()
                todo = ms.value() or ([s for s in samples if meta[meta["sample"] == s].edge_key.iloc[0] == e] if e else [])
                if not todo:
                    return
                refs = set(meta[meta["sample"].isin(todo)].ref_file) - {""}
                todo = list(dict.fromkeys(list(meta[meta.file.isin(refs)]["sample"]) + todo))

                def work(progress):
                    cfg = pl.load_config()
                    out, errs = {}, []
                    for i, s in enumerate(todo):
                        progress(i / len(todo), f"{s} ({i + 1}/{len(todo)})")      # 取消点：样品之间
                        try:
                            out[s], _ = pl.build_sample(s, cfg, meta)
                        except Exception as ex:      # noqa: BLE001
                            logs.log.warning("qt.pages.process.work 出错（已忽略或已提示）", exc_info=True)
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
                    if errs:
                        self.notice("err", T(f"{len(errs)} 个样品载入失败", f"{len(errs)} sample(s) failed to load"), errs)       # 提示条在重建后仍显示
                    self.refresh()
                W.run_task(self, work, done, T("载入中…", "Loading…"), btn, progress=True, key="load", excl="groups")
            btn.clicked.connect(load)
            card.add(W.hbox(W.field(T("样品", "Samples"), ms), W.field(T("或整条吸收边", "or a whole edge"), ek),
                            W.vbox(None, btn), spacing=12))
            card.lay.itemAt(card.lay.count() - 1).widget().layout().setStretch(0, 4)
            card.add(refl)
            self.add(card)
        self.add(W.collapsible(T("直接读入文件（自动识别格式）", "Read files directly (format auto-detected)"),
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

        edge_cache = {}            # 文件 → 吸收边；本卡片内只读一次 meta.csv、每个文件最多解析一次

        def edge_of(rel):
            """文件的吸收边（meta.csv 里有就用登记值，否则读文件头）；读不出返回 None。"""
            if not edge_cache:
                try:
                    m = pd.read_csv(paths.META, dtype=str, encoding="utf-8-sig").fillna("") if paths.META.exists() else None
                    edge_cache["__meta__"] = {} if m is None else dict(zip(m.file, m.edge_key))
                except (OSError, ValueError):
                    edge_cache["__meta__"] = {}
            if rel in edge_cache:
                return edge_cache[rel]
            ek = edge_cache["__meta__"].get(rel) or None
            if ek is None:
                try:
                    g_ = xio.read_scan(paths.ROOT / rel)
                    ek = f"{g_.element}_{g_.edge}"
                except Exception:      # noqa: BLE001  多组文件、未知格式等：不参与按吸收边筛选
                    logs.log.debug("qt.pages.process.edge_of 无法读出吸收边：%s", rel, exc_info=True)
            edge_cache[rel] = ek
            return ek

        def default_ref(sel):
            same = [c for c in cands if sel and batch_of(c) == batch_of(sel[0])]
            if same and len(same) > 1:           # 同一批次里有多个元素的参比：只取同一吸收边的
                ek = edge_of(sel[0])
                same = [c for c in same if edge_of(c) == ek] or same
            if same:
                ref.setCurrentIndex(cands.index(same[0]) + 1)
        files.changed.connect(default_ref)
        mode = W.combo(["auto", "trans", "fluo"], "auto",
                       fmt=lambda m: {"auto": T("自动（按文件头）", "Auto (from header)"), "trans": "trans", "fluo": "fluo"}[m])
        fcfg = load_cfg().get("formats", {}) or {}
        fmts = ["auto"] + [n for n, _z, _e in xio.list_formats()] + ["columns_by_index"] + list(fcfg)
        zh_en = {n: T(z, e) for n, z, e in xio.list_formats()}
        fmt = W.combo(fmts, "auto", fmt=lambda f: {"auto": T("自动识别", "Auto-detect"),
                                                   "columns_by_index": T("通用列文本（按下方列号）", "Column text (by number, below)")}
                      .get(f, zh_en.get(f, T(f"模板：{f}", f"Template: {f}"))))
        card.add(W.fields((T("文件", "Files"), files), (T("参比（必选，同批次单质箔 / 粉）", "Reference (required, same batch)"), ref),
                          (T("格式", "Format"), fmt), (T("模式", "Mode"), mode)))
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
                    logs.log.warning("qt.pages.process.read 出错（已忽略或已提示）", exc_info=True)
                    W.toast(self, f"{r}: {ex}", "err")
                    return
            for p in fpaths:
                try:
                    kws = {} if mode.value() == "auto" else {"mode": mode.value()}
                    fm = fmt.value()
                    cols = None
                    if fm == "columns_by_index":
                        nz = lambda v: None if v < 0 else int(v)      # noqa: E731
                        cols = {k: v for k, v in (("energy", ecol.value()), ("i0", nz(i0c.value())), ("it", nz(i1c.value())),
                                                  ("if", nz(ifc.value())), ("mu", nz(muc.value()))) if v is not None}
                        fm = "columns"
                    fm = None if fm == "auto" else fm
                    if p.suffix.lower() == ".prj" and fm in (None, "prj"):
                        for lab, g in xio.read_prj(p).items():
                            S.groups[f"{p.stem}:{lab}"] = g
                        continue
                    g = xio.read_scan(p, fmt=fm, columns=cols, templates=fcfg, **kws)
                    if elem.text().strip():
                        from xafsmith.common import guess_edge
                        g.element = elem.text().strip()
                        g.edge = guess_edge(g.element, float(np.median(g.energy)))
                    for w_ in g.read_warnings:
                        W.toast(self, f"{p.name}: {w_.split(' / ')[0] if T('中', 'en') == '中' else w_.split(' / ')[-1]}", "warn")
                    lab = p.relative_to(paths.ROOT).as_posix()
                    g.label = lab
                    S.groups[lab] = g
                    done, skipped = apply_ref(S, [lab], r)
                    if skipped:
                        S.groups.pop(lab)
                        errs.append(T(f"{p.name}：吸收边 {edge_key(g)} 与参比不同，未读入", f"{p.name}: edge {edge_key(g)} differs from the reference; skipped"))
                except Exception as ex:      # noqa: BLE001
                    logs.log.warning("qt.pages.process.read 出错（已忽略或已提示）", exc_info=True)
                    errs.append(f"{p.name}: {ex}")
            S.emit("groups")
            if errs:
                self.notice("err", T(f"{len(errs)} 个文件未读入", f"{len(errs)} file(s) not read"), errs)       # 提示条在重建后仍显示
            self.refresh()
        def wizard():
            sel = files.value()
            if not sel:
                W.toast(self, T("先在“文件”里选一个数据文件", "Choose a data file under “Files” first"), "warn")
                return
            from ...colwizard import ColumnWizard
            dlg = ColumnWizard(self.window(), paths.ROOT / sel[0])
            dlg.exec()
            if dlg.saved:
                W.toast(self, T(f"已保存格式模板“{dlg.saved}”，可在“格式”中选用，也可写进 meta.csv 的 format 列",
                                f"Template “{dlg.saved}” saved; pick it under “Format” or put it in the format column of meta.csv"))
                self.refresh()
        card.add(W.hbox(W.button(T("列映射向导…", "Column mapping wizard…"), slot=wizard,
                                 tip=T("文件格式不被自动识别、或列名不规范时：预览各列 → 指定能量 / I0 / It / If → 试读 → 保存为模板",
                                       "When a file is not recognised or its column names are non-standard: preview, map columns, test, save as a template")),
                        None, W.button(T("读入", "Read"), primary=True, icon_name="upload", slot=lambda: W.wait_cursor(read))))
        return card

    def _loaded(self):
        S = self.S
        card = Card(T(f"已载入 {len(S.groups)} 条谱", f"{len(S.groups)} spectra loaded"),
                    actions=[W.button(T("清空工作区", "Clear workspace"), icon_name="refresh",
                                      slot=lambda: self.window().clear_workspace(),
                                      tip=T("移出全部已载入的谱和本次拟合，在同一项目里换一批样品从头处理（文件与 output/ 不删）",
                                            "Remove all loaded spectra and fits to start over with other samples in this project (files and output/ kept)"))])
        rows = [dict(label=k, element=g.element, edge=g.edge, mode=g.mode, npts=len(g.energy),
                     E_range=f"{g.energy[0]:.0f}–{g.energy[-1]:.0f}", time=getattr(g, "timestamp", ""),
                     dE_cal=round(getattr(g, "e_shift", 0.0) or 0.0, 3),
                     **{T("校准", "calibration"): calib_status(S, g, W.en())[0]},
                     E0=round(getattr(g, "e0", np.nan), 2)) for k, g in S.groups.items()]
        card.add(W.Table(pd.DataFrame(rows), max_height=360))
        rm = W.MultiSelect(list(S.groups), [], T("选择要移除的谱", "Spectra to remove"))

        def remove():
            v = rm.value()
            if not v:
                return
            if not W.ask(self, T("移除谱", "Remove spectra"), T(
                    f"从会话中移除 {len(v)} 条谱（{', '.join(v[:3])}{'…' if len(v) > 3 else ''}）？文件不会被删除，但未保存的处理结果会丢失。",
                    f"Remove {len(v)} spectra from the session ({', '.join(v[:3])}{'…' if len(v) > 3 else ''})? "
                    "Files are kept, but unsaved processing results are lost.")):
                return
            for k in v:
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
