"""快速拟合页：只拟合第一壳层并给出人话判定。

四块：① 样品（多选）+ FEFF 文件夹（选后显示第一壳层）；② 用途（标样 / 样品）、S0²、Rmax；③ 开始拟合（后台）；④ 结果。
1 个样品 → build_model + run；≥ 2 个样品（样品用途）→ build_joint_model + run_joint（共享 ΔE0、统一窗口）。
计算全在 xafsmith.quickfit，这里只做界面；后台线程不碰控件与 State（谱在界面线程深拷贝）。
Quick fit page: first shell only, with a plain-words verdict. All numerics live in xafsmith.quickfit; this module is UI only.
"""

from __future__ import annotations

import copy

from PySide6.QtWidgets import (QAbstractItemView, QDialog, QDialogButtonBox, QTableWidget, QTableWidgetItem, QVBoxLayout)

from xafsmith import logs, paths, quickfit as qf, s02_source as s2
from ... import widgets as W
from ...state import edge_key, feff_dirs, has_chi
from ...theme import C
from ...widgets import T, Banner, Card, Page


# ---------------------------------------------------------------- 后台任务（须在界面线程调用，返回无控件引用的函数）
def quick_job(S, samples, feff, rmax, mode, s02, src, name=None):
    """快速拟合的后台任务。样品的谱在这里深拷贝（会话里已有 χ(k) 的用会话的，与精细拟合一致），其余在后台线程现建。
    返回 work(progress) → dict(kind="single"|"joint", res, table)；res 是 QuickResult 或 JointResult。"""
    from xafsmith import pipeline as pl
    snap = {s: copy.deepcopy(S.groups[s]) for s in samples if s in S.groups and has_chi(S.groups[s])}
    samples = list(samples)

    def work(progress):
        progress(0.05, T("准备谱与模型…", "Preparing spectra and model…"))
        if len(samples) == 1:
            s = samples[0]
            model = qf.build_model(s, feff, rmax, mode, s02=s02, s02_source=src, name=name or None, group=snap.get(s))
            progress(0.4, T("拟合中…", "Fitting…"))
            res = qf.run(model, group=snap.get(s))
            return dict(kind="single", res=res, table=None)
        groups = {pl.safe(s): g for s, g in snap.items()}
        model = qf.build_joint_model(samples, feff, rmax, s02=s02, s02_source=src, name=name or None, groups=groups)
        progress(0.4, T("联合拟合中…", "Joint fitting…"))
        res = qf.run(model, groups)
        progress(0.9, T("趋势表…", "Trend table…"))
        try:
            table = res.trend()
        except Exception:      # noqa: BLE001
            logs.log.warning("快速拟合：趋势表失败（已忽略，图与表略去）", exc_info=True)
            table = None
        return dict(kind="joint", res=res, table=table)
    return work


class S02Dialog(QDialog):
    """「选取标样值」：列出同吸收边、S0² 为拟合量的标样拟合（会话 + 已保存），选一行。"""

    def __init__(self, parent, cands):
        super().__init__(parent)
        self.setWindowTitle(T("选取标样值", "Pick a standard's S0²"))
        self.cands = cands
        lay = QVBoxLayout(self)
        lay.addWidget(W.label(T("同一吸收边、S0² 为拟合量的标样拟合；选中一行，S0² 与来源写入快速拟合。",
                                "Standard fits on the same edge with a fitted S0²; pick one to use its S0² and record the source."), "muted"))
        self.tab = QTableWidget(len(cands), 5)
        self.tab.setHorizontalHeaderLabels([T("模型", "Model"), T("样品", "Sample"), "S0² ± σ", T("R 因子", "R-factor"), T("时间", "Time")])
        for i, c in enumerate(cands):
            vals = [c.model, c.sample_text, f"{c.value:.4f} ± {c.stderr:.4f}", "" if c.rfactor is None else f"{c.rfactor:.4f}",
                    c.time + (T("（本会话）", " (this session)") if c.origin == "session" else "")]
            for j, v in enumerate(vals):
                self.tab.setItem(i, j, QTableWidgetItem(v))
        self.tab.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.tab.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.tab.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.tab.horizontalHeader().setStretchLastSection(True)
        self.tab.resizeColumnsToContents()
        if cands:
            self.tab.selectRow(0)
        self.tab.doubleClicked.connect(lambda *_: self.accept())
        lay.addWidget(self.tab)
        bb = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        bb.button(QDialogButtonBox.StandardButton.Ok).setText(T("使用", "Use"))
        bb.button(QDialogButtonBox.StandardButton.Cancel).setText(T("取消", "Cancel"))
        bb.accepted.connect(self.accept)
        bb.rejected.connect(self.reject)
        lay.addWidget(bb)
        self.resize(760, 320)

    def chosen(self):
        r = self.tab.currentRow()
        return self.cands[r] if 0 <= r < len(self.cands) else None


class QuickFitPage(Page):
    """快速拟合 / Quick fit"""
    title_zh, title_en, icon_name = "快速拟合", "Quick fit", "fit"
    fill = False
    max_width = 1180

    def __init__(self, app):
        super().__init__(app)
        self._res = None            # 最近一次结果（页面重建后仍在）：dict(kind, res, table, mode, samples)
        self._shell_cache = {}

    # ------------------------------------------------------------ 数据
    def _samples_available(self):
        from xafsmith import pipeline as pl
        if not paths.META.exists():
            return []
        m = pl.load_meta()
        return list(dict.fromkeys(m[m["use"] != "0"]["sample"]))

    def _edge_of(self, samples):
        return s2.edge_of_samples(samples) if samples else None

    def _shell(self, d):
        """FEFF 文件夹的第一壳层（缓存）；读不出 → 抛 QuickFitError"""
        from xafsmith.feff_wrap import list_paths
        k = str(d)
        if k not in self._shell_cache:
            self._shell_cache[k] = qf.first_shell(list_paths(d))
        return self._shell_cache[k]

    def _session_edges(self):
        return {k: edge_key(g) for k, g in self.S.groups.items() if hasattr(g, "element") and hasattr(g, "edge")}

    # ------------------------------------------------------------ 页面
    def build(self):
        st = self.state
        self.header(T("只拟合第一壳层（N、R、σ²、ΔE0），并用人话判定结果是否可信；要逐条设置路径与参数，请切到上方的“精细拟合”。",
                      "Fits the first shell only (N, R, σ², ΔE0) and states in plain words whether the result is trustworthy; "
                      "to set every path and parameter yourself, switch to “Detailed fit” above."))
        samples = self._samples_available()
        dirs = feff_dirs()
        if not samples or not dirs:
            self.add(Banner("info", T("需要：已登记的样品（data/meta.csv）与 FEFF 计算（FEFF 路径）。",
                                      "Needs registered samples (data/meta.csv) and a FEFF calculation (FEFF paths).")))
            self._sel = None
            return
        # ① 样品与 FEFF
        c1 = Card(T("1  样品与 FEFF", "1  Samples and FEFF"))
        self._smp = W.MultiSelect(samples, [s for s in st.get("samples", []) if s in samples],
                                  T("选择样品（≥ 2 个且为样品用途 → 联合拟合）", "Samples (≥ 2 in sample mode → joint fit)"))
        self._smp.setToolTip(T("可多选。选 ≥ 2 个样品（样品用途）时做联合拟合：共享一个 ΔE0，窗口统一；各自的 N、R、σ² 独立。",
                               "Several allowed. ≥ 2 samples in sample mode run a joint fit: one shared ΔE0, one common window; "
                               "N, R, σ² are independent per sample."))
        cur = next((d for d in dirs if str(d) == st.get("feff")), None)
        if cur is None:
            tag = None
            ek = self._edge_of(st.get("samples", []))
            if ek:
                tag = "_" + ek.replace("_", "")
            cur = next((d for d in dirs if tag and tag in str(d.relative_to(paths.FEFF))), dirs[0])
        self._feff = W.combo(dirs, cur, fmt=lambda p: str(p.relative_to(paths.ROOT)))
        self._feff.setToolTip(T("FEFF 计算文件夹（含 feff0001.dat…；多位点时每个位点是一个文件夹）。",
                                "FEFF calculation folder (feff0001.dat …; with several sites each site is its own folder)."))
        c1.add(W.field(T("样品（多选）", "Samples (several)"), self._smp))
        c1.add(W.field(T("FEFF 文件夹", "FEFF folder"), self._feff))
        self._shell_lb = W.label("", rich=True)
        c1.add(self._shell_lb)
        self.add(c1)
        # ② 用途、S0²、Rmax
        c2 = Card(T("2  用途、S0² 与窗口", "2  Purpose, S0² and window"))
        self._mode = W.Segmented(["sample", "standard"], st.get("mode", "sample"),
                                 fmt=lambda m: T("样品", "Sample") if m == "sample" else T("标样", "Standard"))
        self._mode.setToolTip(T("样品：S0² 固定，拟合 N；标样：N 固定为 FEFF 简并度，拟合 S0²（得到的 S0² 可供样品使用）。",
                                "Sample: S0² fixed, N fitted; Standard: N fixed to the FEFF degeneracy, S0² fitted (the result can be used for samples)."))
        c2.add(W.field(T("用途", "Purpose"), self._mode))
        self._s02 = W.text(st.get("s02", ""), T("必填：取自标样，或手填", "required: from a standard, or typed"))
        self._s02.setMaximumWidth(140)
        self._pick = W.button(T("选取标样值…", "Pick standard value…"), slot=self._pick_s02,
                              tip=T("列出同吸收边、S0² 为拟合量的标样拟合，选一个填入（并记录来源）；手改数值则来源变为“手动”。",
                                    "List standard fits on the same edge with a fitted S0²; pick one (the source is recorded); "
                                    "editing the number makes it “manual”."))
        self._s02_lb = W.label("", "faint")
        self._s02_row = W.hbox(W.field("S0²", self._s02), W.vbox(None, self._pick), self._s02_lb, None, spacing=10)
        c2.add(self._s02_row)
        self._rmax = W.num(st.get("rmax", qf.RMAX_DEFAULT), 1.5, 8.0, 0.1)
        self._rmax.setToolTip(T("R 窗口上限（Å）。默认 2.5：只含第一壳层；Rmin 由第一峰自动确定。",
                                "Upper limit of the R window (Å). Default 2.5: first shell only; Rmin is set automatically from the first peak."))
        self._name = W.text(st.get("name", ""), T("留空 = 自动（QF_样品名）", "empty = automatic (QF_sample)"))
        c2.add(W.fields(("Rmax (Å)", self._rmax), (T("Rmin（自动）", "Rmin (automatic)"),
                                                  W.label(T("由第一峰决定，拟合后显示", "from the first peak; shown after the fit"), "faint")),
                        (T("模型名", "Model name"), self._name), cols=3))
        self.add(c2)
        # ③ 开始拟合
        c3 = Card(T("3  开始拟合", "3  Run"))
        self._run = W.button(T("开始拟合", "Start fit"), primary=True, icon_name="play")
        W.bind_task(self._run, "quickfit", "fit")
        self._why = W.label("", "faint")
        c3.add(W.hbox(self._run, self._why, None, spacing=12))
        self.add(c3)
        self._rbox = W.vbox()
        self.add(self._rbox)
        # 事件
        self._smp.changed.connect(lambda *_: self._changed())
        self._feff.currentIndexChanged.connect(lambda *_: self._changed())
        self._mode.changed.connect(lambda *_: self._changed())
        self._rmax.valueChanged.connect(lambda *_: self._changed())
        self._name.textChanged.connect(lambda *_: self._changed())
        self._s02.textEdited.connect(self._s02_typed)
        self._run.clicked.connect(self._go)
        self._changed(rebuild_results=False)
        self._show_results()

    # ------------------------------------------------------------ 输入状态
    def _s02_typed(self, txt):
        self.state["s02_src"] = None            # 手改 → 来源变为手动
        self._changed()

    def _changed(self, rebuild_results=False):
        st = self.state
        st.update(samples=self._smp.value(), feff=str(self._feff.value()), mode=self._mode.value(), s02=self._s02.text().strip(),
                  rmax=self._rmax.value(), name=self._name.text().strip())
        sample_mode = st["mode"] == "sample"
        self._s02_row.setVisible(sample_mode)
        src = st.get("s02_src")
        self._s02_lb.setText("" if not sample_mode else (
            T(f"来源：标样拟合 {src['model']}（{src['value']:.4f} ± {src['stderr']:.4f}）", f"Source: standard fit {src['model']} "
              f"({src['value']:.4f} ± {src['stderr']:.4f})") if src else
            (T("来源：手动（无标样依据）", "Source: manual (no standard behind it)") if st["s02"] else "")))
        self._update_shell()
        self._update_run()

    def _update_shell(self):
        st = self.state
        d = self._feff.value()
        try:
            sh = self._shell(d)
        except Exception as ex:      # noqa: BLE001
            logs.log.debug("快速拟合：第一壳层读取失败 %s", d, exc_info=True)
            self._shell_lb.setText(f'<span style="color:{C["err"]}">' + T(f"无法读取 FEFF 路径：{ex}", f"Cannot read the FEFF paths: {ex}") + "</span>")
            return
        rr = [m["reff"] for m in sh.members]
        rng = f"{min(rr):.2f}–{max(rr):.2f}" if len(rr) > 1 else f"{rr[0]:.2f}"
        txt = T(f"第一壳层：<b>{sh.absorber}–{sh.scatterer} ×{sh.n_ref:g}</b>，{rng} Å（合并 {len(sh.members)} 条路径，"
                f"N_ref = {sh.n_ref:g}，R_ref = {sh.r_cif:.3f} Å）",
                f"First shell: <b>{sh.absorber}–{sh.scatterer} ×{sh.n_ref:g}</b>, {rng} Å ({len(sh.members)} merged path(s), "
                f"N_ref = {sh.n_ref:g}, R_ref = {sh.r_cif:.3f} Å)")
        if sh.other_elements:
            txt += "<br>" + T("提示：第一层还有 " + "、".join(f"{e}（{r:.2f} Å）" for e, r in sh.other_elements) + "，未考虑。",
                              "Note: the first layer also has " + ", ".join(f"{e} ({r:.2f} Å)" for e, r in sh.other_elements)
                              + ", not included.")
        ek = self._edge_of(st.get("samples", []))
        if ek and sh.absorber and ek.split("_")[0] != sh.absorber:
            txt += f'<br><span style="color:{C["warn"]}">' + T(f"⚠ FEFF 的吸收原子是 {sh.absorber}，所选样品的吸收边是 {ek}。",
                                                                  f"⚠ The FEFF absorber is {sh.absorber} but the chosen samples are on {ek}.") + "</span>"
        elif st.get("samples") and not ek:
            txt += f'<br><span style="color:{C["warn"]}">' + T("⚠ 所选样品不在同一个吸收边（联合拟合要求同一吸收边）。",
                                                                  "⚠ The chosen samples are not on one absorption edge (a joint fit needs one).") + "</span>"
        self._shell_lb.setText(txt)

    def _missing(self):
        """不能开始的原因（中英），能开始 → 空串"""
        st = self.state
        n = len(st.get("samples", []))
        if not n:
            return T("先选样品", "Choose samples first")
        if st["mode"] == "standard" and n > 1:
            return T("标样用途只能选一个样品（联合拟合只用于样品）", "Standard mode takes a single sample (joint fits are for samples)")
        if st["mode"] == "sample":
            try:
                ok = float(st["s02_src"]["value"] if st.get("s02_src") else st["s02"]) > 0
            except (ValueError, TypeError):
                ok = False
            if not ok:
                return T("样品用途需要 S0²：点“选取标样值…”，或手填", "Sample mode needs S0²: pick a standard's value, or type one")
        return ""

    def _update_run(self):
        why = self._missing()
        self._why.setText(why)
        self._run.setEnabled(not why and not W.task_running(excl="fit"))

    # ------------------------------------------------------------ 选取标样值
    def _pick_s02(self):
        ek = self._edge_of(self.state.get("samples", []))
        if not ek:
            W.toast(self, T("先选样品（需在同一个吸收边）", "Choose samples first (on one absorption edge)"), "warn")
            return
        cands = s2.list_candidates(ek, self.S.fits, session_edges=self._session_edges())
        if not cands:
            W.toast(self, T(f"没有 {ek} 边、S0² 为拟合量的标样拟合。先在“标样”用途下拟合一个标样（会话里的拟合即可，不必先保存）。",
                            f"No standard fit on {ek} with a fitted S0². Fit a standard first in Standard mode (a session fit is enough)."), "warn")
            return
        dlg = S02Dialog(self, cands)
        if not dlg.exec():
            return
        c = dlg.chosen()
        if c is None:
            return
        self._pick_candidate(c)

    def _pick_candidate(self, c):
        self.state["s02_src"] = c.source()
        self._s02.setText(f"{c.value:.4f}")
        self._changed()

    # ------------------------------------------------------------ 运行
    def _go(self):
        if W.task_running(excl="fit"):
            return
        self._changed()
        st = self.state
        if self._missing():
            return
        samples, mode = list(st["samples"]), st["mode"]
        src = s02 = None
        if mode == "sample":
            src = dict(st["s02_src"]) if st.get("s02_src") else None
            s02 = float(src["value"]) if src else float(st["s02"])
            src = src or dict(manual=True, value=s02)
        work = quick_job(self.S, samples, str(self._feff.value()), float(st["rmax"]), mode, s02, src, st.get("name") or None)
        S = self.S

        def done(out):
            res = out["res"]
            S.fits.append(res.fit)
            S.emit("fits")
            self._res = dict(out, mode=mode, samples=samples)
            self._show_results()
            self.ack()

        def failed(msg):
            first = str(msg).strip().splitlines()[-1] if str(msg).strip() else ""
            self._res = None
            self._show_results(error=first)
        W.run_task(self, work, done, T("快速拟合中…", "Quick fitting…"), self._run, progress=True, on_error=failed,
                   key="quickfit", excl="fit")

    # ------------------------------------------------------------ 结果（第二步实现）
    def _show_results(self, error=None):
        if not hasattr(self, "_rbox"):
            return
        W._clear_layout(self._rbox.layout())
        if error:
            self._rbox.layout().addWidget(Banner("err", error))
