"""归一化页面。"""

from __future__ import annotations

from xafsmith import logs
import numpy as np
import pandas as pd
from PySide6.QtWidgets import QWidget
from xafsmith import paths
from ... import widgets as W
from ...state import safe
from ...theme import C
from ...widgets import T, Banner, Card, Page

from ._shared import need_groups, norm_fields, reset_button


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
        flat = W.check(T("展平（flattened）", "flattened"), self.state.get("flat", True))
        rel = W.check(T("横轴 E − E0", "x axis E − E0"), self.state.get("rel", False))
        ctl.add(nf)
        ctl.add(W.hbox(reset_button(self, "norm", nf.set_values, lambda: sel.value()), None))
        ctl.add(W.hbox(W.field(T("谱", "Spectra"), sel), W.field(T("显示边前 / 边后线的谱", "Pre/post-edge lines for"), cur), spacing=12))
        self.add(ctl)
        p1, p2, p3 = W.Plot(380), W.Plot(420), W.Plot(380)
        e0lbl = W.label("", "muted")
        merge = self._merge(sel)
        self.add(W.tabs((T("μ(E) 与边前 / 边后", "μ(E) with pre/post-edge"), W.vbox(p1, e0lbl)),
                        (T("归一化叠加", "Normalized overlay"), W.vbox(W.hbox(flat, rel, None), p2)),
                        (T("导数", "Derivative"), p3), (T("合并扫描", "Merge scans"), merge),
                        state=self.state, key="tab"))

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
            errs = []
            for k in v:
                try:
                    xnorm.normalize(S.groups[k], **{**S.norm_par, "e0": S.norm_par.get("e0") if len(v) == 1 else None})
                except Exception as ex:      # noqa: BLE001
                    logs.log.warning("qt.pages.process.update 出错（已忽略或已提示）", exc_info=True)
                    errs.append(f"{k}: {ex}")
            if errs:
                self._set_update_notice(errs)
            else:
                self.clear_notice("norm")
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
        self.redraw = update
        upd_d = W.debounced(self, update)        # 参数框连续微调只重画一次
        nf.connect(upd_d)
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
                logs.log.warning("qt.pages.process.export_prj 出错（已忽略或已提示）", exc_info=True)
                self.notice("err", T("导出 .prj 失败", "Export .prj failed"), [str(ex)])
        exp.add(W.hbox(W.button(T("导出所选归一化数据到 output/gui/norm/", "Export selected to output/gui/norm/"), icon_name="download",
                                slot=export_nor), None))
        exp.add(W.label(T("Athena 工程（.prj）：写入已校准能量与 μ(E)，以及本软件的 E0、边前/边后范围、rbkg、k 范围、窗函数，可在 Athena / Artemis 中直接对照。",
                          "Athena project (.prj): calibrated energy and μ(E) plus this software's E0, pre/post-edge ranges, rbkg, "
                          "k range and window, for a direct comparison in Athena / Artemis."), "faint"))
        exp.add(W.hbox(W.field(T("文件名", "File name"), prj_name), W.vbox(None, W.button(T("导出 .prj", "Export .prj"),
                                                                                        icon_name="download", slot=export_prj)), None))
        self.add(exp)

    def _set_update_notice(self, errs):
        """归一化出错：汇总成一条提示（不逐条弹出）"""
        self.notice("err", T(f"{len(errs)} 条谱归一化失败", f"{len(errs)} spectra failed to normalize"), errs, key="norm")

    def _merge(self, sel):
        from xafsmith import normalize as xnorm
        S = self.S
        w = QWidget()
        lay = W.QVBoxLayout(w)
        lay.setContentsMargins(0, 8, 0, 0)
        lay.addWidget(W.label(T("先逐条检查再平均：与中位谱 RMS 偏差超过阈值的扫描自动剔除，也可手动剔除。",
                                "Inspect, then average: scans deviating from the median by more than the threshold are "
                                "rejected automatically; you can also reject scans manually."), "faint"))
        st = self.state
        msel = W.MultiSelect(list(S.groups), st.get("m_sel", sel.value()), T("要合并的扫描", "Scans to merge"))
        rej = W.MultiSelect(list(S.groups), st.get("m_rej", []), T("手动剔除", "Reject manually"))
        tol = W.num(st.get("m_tol", 4.0), 1, 20, 0.5)
        name = W.text(st.get("m_name", "merge"))
        msel.changed.connect(lambda v: st.__setitem__("m_sel", v))
        rej.changed.connect(lambda v: st.__setitem__("m_rej", v))
        tol.valueChanged.connect(lambda v: st.__setitem__("m_tol", v))
        name.textChanged.connect(lambda v: st.__setitem__("m_name", v))
        out = W.vbox()
        lay.addWidget(W.fields((T("扫描", "Scans"), msel), (T("手动剔除", "Reject"), rej), (T("阈值（×中位 RMS）", "Threshold (× median RMS)"), tol),
                               (T("合并后名称", "Merged name"), name)))

        def go():
            v = msel.value()
            if len(v) < 2:
                W.toast(self, T("合并至少需要选择 2 条扫描", "Select at least 2 scans to merge"), "info")
                return
            if name.text() in S.groups and not W.ask(self, T("覆盖同名谱", "Overwrite"), T(
                    f"“{name.text()}”已存在，合并结果将覆盖它。继续吗？",
                    f"“{name.text()}” already exists and will be overwritten. Continue?")):
                return
            m, rep = xnorm.merge_scans([S.groups[k] for k in v], label=name.text(), reject=rej.value(), tol_sigma=tol.value())
            S.groups[name.text()] = m
            pd.DataFrame(rep).to_csv(paths.GUI / f"merge_{safe(name.text())}.csv", index=False, encoding="utf-8-sig")
            W._clear_layout(out.layout())
            out.layout().addWidget(Banner("ok", T(f"已生成 {name.text()}（{m.nscans} 条扫描）", f"Created {name.text()} ({m.nscans} scans)")))
            out.layout().addWidget(W.Table(pd.DataFrame(rep)))
            S.emit("groups")              # 不 ack：回到本页时重建，下拉框里才有新合并的谱
        lay.addWidget(W.hbox(None, W.button(T("合并", "Merge"), primary=True, slot=lambda: W.wait_cursor(go))))
        lay.addWidget(out)
        lay.addStretch(1)
        return w
