"""单个拟合结果的展示：质量、诊断、稳健性检查。"""

from __future__ import annotations

from xafsmith import logs
import pandas as pd
from PySide6.QtWidgets import QWidget
from xafsmith import paths
from ... import widgets as W
from ...state import fit_dataset, fit_ds_ids, safe, save_fit
from ...theme import C
from ...widgets import T, Banner, Card
from .._common import rlabel

from .quality import quality_checks


class FitView(QWidget):
    """一个拟合的结果：指标与按钮、k / R 图；参数、路径、质量检查、诊断、稳健性、完整报告放在标签页里（不用上下翻）。
    adopt：把拟合值写回参数表的回调（EXAFS 拟合页提供；拟合历史页没有）"""
    def __init__(self, page, fit, key="", adopt=None):
        super().__init__()
        self.page, self.full, self.adopt = page, fit, adopt
        self.multi = bool(fit["summ"].get("multi"))
        self._lay = W.QVBoxLayout(self)
        self._lay.setContentsMargins(0, 0, 0, 0)
        self._lay.setSpacing(12)
        self._build()

    def _rebuild(self):
        # 用 singleShot：切换控件正在发信号，不能在它自己的槽里把它删掉
        from PySide6.QtCore import QTimer
        QTimer.singleShot(0, self._build)

    def _build(self):
        page, adopt, full = self.page, self.adopt, self.full
        W._clear_layout(self._lay)
        self.__dict__.pop("_dg_cache", None)
        s0 = full["summ"]
        ids = fit_ds_ids(full)
        if ids:       # 多数据集：作图、路径、质量检查、诊断按所选数据集；参数、完整报告为联合
            cur = page.state.get("fit_ds")
            self.ds = cur if cur in ids else ids[0]
            fit = fit_dataset(full, self.ds)
        else:
            self.ds, fit = None, full
        self.fit = fit
        s, c, md = fit["summ"], fit["curves"], fit["model"]
        lay = self._lay
        card = Card()
        head = W.QHBoxLayout()
        t = W.label(T(f"拟合结果 · {s0['model']}", f"Fit result · {s0['model']}"), "h2")
        t.setWordWrap(True)
        head.addWidget(t, 1)

        def save():
            base = save_fit(full)
            if ids:
                W.toast(page, T(f"已保存：output/fits/exafs_fits.csv、models/{base}.json、报告与 {len(ids)} 张拟合图",
                                f"Saved: output/fits/exafs_fits.csv, models/{base}.json, report and {len(ids)} figures"))
            else:
                W.toast(page, T(f"已保存：output/fits/exafs_fits.csv、models/{base}.json、报告与拟合图",
                                f"Saved: output/fits/exafs_fits.csv, models/{base}.json, report and figure"))
        if adopt is not None:
            head.addWidget(W.button(T("采纳拟合值到参数", "Use fitted values as start"), icon_name="check",
                                    slot=lambda: adopt(full),
                                    tip=T("把本次拟合得到的变量值写回左侧参数表的 value 列，作为下一次拟合的初值",
                                          "Copy the fitted values into the value column of the parameter table (start values for the next fit)")))
        head.addWidget(W.button(T("保存结果", "Save result"), primary=True, icon_name="save", slot=save))
        card.add(head)
        if ids:
            card.add(W.metrics((T("联合 R 因子", "Joint R-factor"), f"{s0['rfactor']:.4f}"),
                               ("χ²_ν", f"{s0['chi2_reduced']:.1f}"), (T("Σ N_idp", "Σ N_idp"), f"{s0['n_idp']:.1f}"),
                               (T("变量数", "Variables"), s0["nvarys"]), (T("数据集", "Datasets"), s0["n_datasets"])))
            row = next(r for r in s0["datasets"] if r["id"] == self.ds)
            dsc = W.combo(ids, self.ds)
            dsc.currentIndexChanged.connect(lambda *_: (page.state.__setitem__("fit_ds", dsc.value()), self._rebuild()))
            card.add(W.hbox(W.label(T("查看数据集", "Dataset"), "faint"), dsc,
                            W.label(T(f"R 因子 <b>{row['rfactor']:.4f}</b>　N_idp <b>{row['n_idp']:.1f}</b>　χ² 占比 <b>{row['chi2_share']:.2f}</b>"
                                      f"　（样品 {row['sample']}）",
                                      f"R-factor <b>{row['rfactor']:.4f}</b>　N_idp <b>{row['n_idp']:.1f}</b>　χ² share <b>{row['chi2_share']:.2f}</b>"
                                      f"　(sample {row['sample']})"), rich=True), None))
        else:
            card.add(W.metrics((T("R 因子", "R-factor"), f"{s['rfactor']:.4f}"), ("χ²_ν", f"{s['chi2_reduced']:.1f}"),
                               ("N_idp", f"{s['n_idp']:.1f}"), (T("变量数", "Variables"), s["nvarys"]),
                               (T("样品", "Sample"), s["sample"])))
        for w_ in s["warnings"]:
            card.add(Banner("warn", w_))
        kw = W.combo([1, 2, 3], page.state.get("kwshow", 2))
        plot = W.Plot(280, 1, 2)
        card.add(W.hbox(W.label(T("显示 k 权重", "Display k-weight"), "faint"), kw, None))
        card.add(plot)

        def draw():
            from larch import Group
            from larch.xafs import xftf
            k = kw.value()
            page.state["kwshow"] = k
            plot.clear()
            a1, a2 = plot.axes
            a1.plot(c["k"], c["chi"] * c["k"] ** k, color=C["text"], lw=1.2, label=T("数据", "data"))
            a1.plot(c["kfit"], c["chifit"] * c["kfit"] ** k, color=C["err"], ls="--", label=T("拟合", "fit"))
            a1.set_xlabel("k (Å⁻¹)")
            a1.set_ylabel(f"k$^{k}$χ(k)")
            gd, gf = Group(k=c["k"], chi=c["chi"]), Group(k=c["kfit"], chi=c["chifit"])
            for gg in (gd, gf):
                xftf(gg, kmin=md["kmin"], kmax=md["kmax"], dk=md["dk"], window=md["window"], kweight=k)
            a2.plot(gd.r, gd.chir_mag, color=C["text"], lw=1.2, label="|χ(R)|")
            a2.plot(gf.r, gf.chir_mag, color=C["err"], ls="--", label=T("|χ(R)| 拟合", "|χ(R)| fit"))
            a2.plot(gd.r, gd.chir_re, color=C["accent"], lw=0.9, label="Re")
            a2.plot(gf.r, gf.chir_re, color=C["magenta"], lw=0.9, ls="--", label=T("Re 拟合", "Re fit"))
            a2.axvspan(md["rmin"], md["rmax"], color=C["text3"], alpha=0.1, lw=0)
            a2.set_xlim(0, 6)
            a2.set_xlabel(rlabel())
            plot.draw()
            self._kw = k
        kw.currentIndexChanged.connect(lambda *_: draw())
        draw()
        lay.addWidget(card)
        # 详细内容：标签页
        pt = pd.DataFrame([{T("参数", "Parameter"): k, T("值", "Value"): v["value"], T("误差", "Error"): v["stderr"],
                            T("变化", "Vary"): v["vary"], T("表达式", "Expr"): v["expr"]} for k, v in s["params"].items()])
        p_tab = W.vbox(W.Table(pt, max_height=420))
        path_tab = W.vbox(W.Table(pd.DataFrame(s["paths"]), max_height=420))
        q = self._quality()
        nwarn = sum(1 for st_, _ in self._checks if st_ is False)
        rep = W.vbox(W.code_block(fit["report"], height=360))
        tabs = W.tabs((T("参数", "Parameters"), p_tab), (T("路径", "Paths"), path_tab),
                      (T("质量检查", "Quality") + (f"  ⚠ {nwarn}" if nwarn else "  ✓"), q),
                      (T("诊断", "Diagnosis"), self._diagnose()), (T("稳健性", "Robustness"), self._robust()),
                      (T("完整报告", "Full report"), rep))
        tabs.setCurrentIndex(page.state.get("fit_tab", 0))
        tabs.currentChanged.connect(lambda i: page.state.__setitem__("fit_tab", i))
        lay.addWidget(tabs)

    def _dg(self):
        """拟合诊断（只算一次，质量检查与诊断共用）"""
        if not hasattr(self, "_dg_cache"):
            from xafsmith import fit_exafs as xfit
            g = self.page.S.groups.get(self.fit["summ"]["sample"])
            try:
                self._dg_cache = xfit.diagnose(self.fit["curves"], self.fit["model"],
                                               e0=getattr(g, "e0", None) if g is not None else None,
                                               kweight=getattr(self, "_kw", 2))
            except Exception as ex:      # noqa: BLE001
                logs.log.warning("qt.pages.fitting._dg 出错（已忽略或已提示）", exc_info=True)
                self._dg_cache = ex
        return self._dg_cache

    def _quality(self):
        card = Card(T("拟合质量检查", "Fit quality check"), flat=True)
        card.lay.setContentsMargins(4, 12, 4, 4)
        self._quality_card = card
        dg = self._dg()
        self._checks = quality_checks(self.fit, None if isinstance(dg, Exception) else dg)
        for state, txt in self._checks:
            col, mark = {True: (C["ok"], "✓"), False: (C["warn"], "⚠"), None: (C["text3"], "•")}[state]
            card.add(W.label(f'<span style="color:{col};font-weight:700">{mark}</span>&nbsp;&nbsp;{txt}', rich=True))
        card.add(W.label(T("这些是必要条件，不是充分条件：新增的壳层还要通过“拟合历史”中的 F 检验（p &lt; 0.05），并在稳健性检查中稳定。",
                           "These are necessary, not sufficient: an added shell must also pass the F-test in “Fit history” "
                           "(p &lt; 0.05) and stay stable in the robustness check."), "faint", rich=True))
        card.lay.addStretch(1)
        return card

    def _diagnose(self):
        fit = self.fit
        body = Card(flat=True)
        body.lay.setContentsMargins(4, 12, 4, 4)
        dg = self._dg()
        if isinstance(dg, Exception):
            body.add(Banner("err", str(dg)))
            return body
        body.add(W.label(T("拟合诊断：残差在哪里、为什么对不上", "Fit diagnosis: where is the residual and why"), "h3"))
        body.add(W.metrics((T("窗口内残差 RMS", "Residual RMS in window"), f"{dg['resid_R']:.4f}"),
                           (T("白噪声估计 (R 15–25 Å)", "White noise (R 15–25 Å)"), f"{dg['noise_R']:.4f}"),
                           (T("残差 / 噪声", "Residual / noise"), f"{dg['ratio']:.1f}")))
        for h in dg["hints"]:
            body.add(Banner("info", h))
        c, md, kw = fit["curves"], fit["model"], getattr(self, "_kw", 2)
        p = W.Plot(280)
        p.ax.plot(c["k"], c["chi"] * c["k"] ** kw, color=C["text"], lw=1, label=T("数据", "data"))
        p.ax.plot(dg["k"], dg["resid_k"], color=C["accent"], lw=1, label=T("残差", "residual"))
        p.ax.axvspan(md["kmin"], md["kmax"], color=C["gold"], alpha=0.08, lw=0)
        for kk, _, _ in dg["spikes"]:
            p.ax.axvline(kk, color=C["magenta"], ls=":", lw=1)
        p.ax.set_xlabel("k (Å⁻¹)")
        p.draw()
        body.add(p)
        body.add(W.hbox(W.vbox(W.label(T("k 分段残差（相对中位数 > 1.5 为偏大）", "k-segment residual (> 1.5 × median is large)"), "faint"),
                               W.Table(dg["k_segments"].round(3))),
                        W.vbox(W.label(T("R 分段局部失配 = Σ|数据−拟合|² / Σ|数据|²", "R-segment mismatch = Σ|data−fit|² / Σ|data|²"), "faint"),
                               W.Table(dg["r_segments"].round(3))), spacing=12))
        body.add(W.label(T("残差/噪声 ≈ 1–2 时已到数据极限；≫ 2 说明残差是系统性的。系统偏差不一定能、也不一定应该用加参数消除——每加一条路径都要通过 F 检验与稳健性检查。",
                           "Residual/noise ≈ 1–2 means the data limit is reached; ≫ 2 means a systematic residual. It cannot "
                           "always be — and should not always be — removed by adding parameters: every added path must pass "
                           "the F-test and the robustness check."), "faint"))
        return body

    def _robust(self):
        fit, page = self.fit, self.page
        body = Card(flat=True)
        body.lay.setContentsMargins(4, 12, 4, 4)
        if self.multi:
            b = Banner("info", T("多数据集模型暂不支持稳健性检查（与命令行一致）。",
                                 "Robustness checks are not yet supported for multi-dataset models (same as the command line)."))
            b.setSizePolicy(W.QSizePolicy.Policy.Preferred, W.QSizePolicy.Policy.Maximum)   # 只占文字高度，不把标签页撑高
            body.add(b)
            return body
        out = W.vbox()
        body.add(W.label(T("稳健性检查：改变拟合条件重复拟合", "Robustness check: refit under varied conditions"), "h3"))
        body.add(W.label(T("依次改变 kmin ±0.5、kmax ±1、Rmax ±0.2 Å，以及（多 k 权重时）单独用 k¹/k²/k³，看变量的变化是否超过统计误差。",
                           "Vary kmin ±0.5, kmax ±1, Rmax ±0.2 Å and (with several k-weights) use k¹/k²/k³ alone; check whether "
                           "each variable moves by more than its statistical error."), "faint"))

        def show():
            W._clear_layout(out.layout())
            tab, ver = fit["robust"]
            bad = ver[ver["判断"] == "不稳"]
            out.layout().addWidget(Banner("warn" if len(bad) else "ok",
                                          (T("不稳的参数：", "Unstable: ") + ", ".join(bad["参数"]) +
                                           T("。结论应以多种条件下的范围报告，或检查模型。", ". Report ranges or revisit the model."))
                                          if len(bad) else T("所有变量随拟合条件的变化都在统计误差以内。",
                                                             "All variables stay within their statistical errors.")))
            out.layout().addWidget(W.Table(ver.round(5)))
            out.layout().addWidget(W.Table(tab.round(5)))

            def save():
                base = safe(fit["summ"]["model"])
                tab.to_csv(paths.FITS / f"{base}_robustness.csv", index=False, encoding="utf-8-sig")
                ver.to_csv(paths.FITS / f"{base}_robustness_summary.csv", index=False, encoding="utf-8-sig")
                W.toast(page, T(f"已保存 output/fits/{base}_robustness*.csv", f"Saved output/fits/{base}_robustness*.csv"))
            out.layout().addWidget(W.hbox(None, W.button(T("保存到 output/fits/", "Save to output/fits/"), icon_name="save", slot=save)))
        btn = W.button(T("运行稳健性检查", "Run robustness check"), icon_name="play")
        W.bind_task(btn, "fit_robust")

        def go():
            from xafsmith import fit_exafs as fx, pipeline as pl
            g = page.S.groups.get(fit["summ"]["sample"])

            def work(progress):
                gg = g
                if gg is None:
                    gg, _ = pl.build_sample(fit["summ"]["sample"])
                return fx.robustness(gg, fit["model"], progress=lambda f, n: progress(f, n))
            W.run_task(page, work, lambda r: (fit.__setitem__("robust", r), show()), T("稳健性检查…", "Robustness…"), btn, progress=True,
                       key="fit_robust")
        btn.clicked.connect(go)
        body.add(W.hbox(None, btn))
        body.add(out)
        if fit.get("robust"):
            show()
        body.lay.addStretch(1)
        return body
