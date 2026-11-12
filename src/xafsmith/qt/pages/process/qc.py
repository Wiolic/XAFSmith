"""质量检查与去毛刺页面。"""

from __future__ import annotations

from xafsmith import logs
import numpy as np
import pandas as pd
from xafsmith import paths
from ... import widgets as W
from ...state import save_cfg
from ...theme import C
from ...widgets import T, Banner, Card, Page

from ._shared import need_groups


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

        run_btn = W.button(T("运行检查", "Run check"), primary=True, icon_name="play")
        W.bind_task(run_btn, "qc")

        def run():
            import copy
            keys = list(sel.value())
            gs = {k: copy.deepcopy(S.groups[k]) for k in keys}     # 界面线程里复制；后台只读写副本，不碰 State
            par = dict(S.norm_par)

            def work(progress):
                rows = []
                for i, k in enumerate(keys):
                    progress(i / max(len(keys), 1), k)
                    g = gs[k]
                    try:
                        if not hasattr(g, "norm_params"):
                            xnorm.normalize(g, **par)
                        rows.append(xqc.check(g))
                    except Exception as ex:      # noqa: BLE001
                        logs.log.warning("qt.pages.process.run 出错（已忽略或已提示）", exc_info=True)
                        rows.append(dict(label=k, error=str(ex)))
                return pd.DataFrame(rows)

            def done(df):
                paths.QC.mkdir(parents=True, exist_ok=True)
                df.to_csv(paths.QC_CSV, index=False, encoding="utf-8-sig")
                S.qc = df
                S.emit("qc")
                self.refresh()
            W.run_task(self, work, done, T("质量检查中…", "Checking…"), run_btn, progress=True, key="qc")
        run_btn.clicked.connect(lambda *_: run())
        card.add(W.hbox(sel, run_btn, spacing=12))
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
                        for e in filter(None, r.glitch_E.split(";")):      # 无毛刺时为空串
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
            from ...state import parse_ranges
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
            S.emit("qc")
            W.toast(self, T(f"已写入 xafsmith.json 并重新载入 {len(v)} 个样品；请重新运行检查",
                            f"Written to xafsmith.json and {len(v)} samples reloaded; run the check again"))
            self.refresh()
        card.add(W.hbox(None, W.button(T("清除所选样品的去毛刺", "Clear deglitch for selected"), slot=lambda: W.wait_cursor(lambda: apply(True))),
                        W.button(T("保存并重新载入", "Save and reload"), primary=True, icon_name="save",
                                 slot=lambda: W.wait_cursor(apply))))
        draw(sel.value())
        return card
