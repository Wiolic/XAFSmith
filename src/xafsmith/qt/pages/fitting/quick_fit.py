"""快速拟合页：只拟合第一壳层并给出人话判定。

四块：① 样品（多选）+ FEFF 文件夹（选后显示第一壳层）；② 用途（标样 / 样品）、S0²、Rmax；③ 开始拟合（后台）；④ 结果。
1 个样品 → build_model + run；≥ 2 个样品（样品用途）→ build_joint_model + run_joint（共享 ΔE0、统一窗口）。
计算全在 xafsmith.quickfit，这里只做界面；后台线程不碰控件与 State（谱在界面线程深拷贝）。
Quick fit page: first shell only, with a plain-words verdict. All numerics live in xafsmith.quickfit; this module is UI only.
"""

from __future__ import annotations

import copy

from PySide6.QtWidgets import (QAbstractItemView, QCheckBox, QDialog, QDialogButtonBox, QTableWidget, QTableWidgetItem, QVBoxLayout)

from xafsmith import logs, paths, quickfit as qf, s02_source as s2
from ... import widgets as W
from ...state import edge_key, feff_dirs, has_chi
from ...theme import C
from ...widgets import T, Banner, Card, Page


# ---------------------------------------------------------------- 后台任务（须在界面线程调用，返回无控件引用的函数）
def quick_job(S, samples, feff, rmax, mode, s02, src, name=None, feff2=None):
    """快速拟合的后台任务。样品的谱在这里深拷贝（取会话里已有 χ(k) 的，与精细拟合一致）；会话里没有的（仅命令行 / 兜底）在后台线程现建。
    feff2：第二相（混合相）的 FEFF 文件夹，只用于样品用途。
    返回 work(progress) → dict(kind="single"|"joint", res, table)；res 是 QuickResult 或 JointResult。"""
    from xafsmith import pipeline as pl
    snap = {s: copy.deepcopy(S.groups[s]) for s in samples if s in S.groups and has_chi(S.groups[s])}
    samples = list(samples)

    def work(progress):
        progress(0.05, T("准备谱与模型…", "Preparing spectra and model…"))
        if len(samples) == 1:
            s = samples[0]
            g = snap[s] if s in snap else pl.build_sample(s)[0]        # 只建一次，自动 Rmin 与拟合共用
            model = qf.build_model(s, feff, rmax, mode, s02=s02, s02_source=src, name=name or None, group=g, feff_dir2=feff2)
            progress(0.4, T("拟合中…", "Fitting…"))
            res = qf.run(model, group=g)
            return dict(kind="single", res=res, table=None)
        groups = {pl.safe(s): (snap[s] if s in snap else pl.build_sample(s)[0]) for s in samples}
        model = qf.build_joint_model(samples, feff, rmax, s02=s02, s02_source=src, name=name or None, groups=groups, feff_dir2=feff2)
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


# ---------------------------------------------------------------- 判定后的操作按钮（只在界面层映射，不改 quickfit.VerdictItem）
RMAX_STEP = 0.2         # “Rmax 改为 X”按钮：X = 当前 Rmax − 0.2
_CONTINUE = ("nvarys", "err_none", "err_big", "at_bound", "correl", "noise", "sigma2_neg", "sigma2_big")
ACTIONS = {"rmax_leak": ["rmax"], "n_ratio": ["s02"],
           **{c: ["structure"] for c in ("peak_pos", "r_cif", "dr", "rfactor")}, "e0": ["structure", "calib"],
           **{c: ["detailed"] for c in _CONTINUE}}


def rmax_target(rmax, r_cif_min):
    """“Rmax 改为 X 并重新拟合”的 X = round(当前 Rmax − 0.2, 2)；X 小于第一壳层 R_CIF（混合相取较短者）→ None（不画按钮）"""
    x = round(float(rmax) - RMAX_STEP, 2)
    return None if x < float(r_cif_min) else x


def item_actions(item, rmax=None, r_cif_min=None):
    """未通过条目的操作按钮：[(动作键, 中文, 英文)]；只对 level == "fail" 给"""
    if item.level != "fail":
        return []
    out = []
    for a in ACTIONS.get(item.code, []):
        if a == "rmax":
            x = None if rmax is None or r_cif_min is None else rmax_target(rmax, r_cif_min)
            if x is not None:
                out.append((a, f"Rmax 改为 {x:g} Å 并重新拟合", f"Set Rmax to {x:g} Å and refit"))
        elif a == "structure":
            out.append((a, "换结构…", "Change structure…"))
        elif a == "calib":
            out.append((a, "去能量校准", "Go to energy calibration"))
        elif a == "s02":
            out.append((a, "选取标样 S0²…", "Pick a standard's S0²…"))
        elif a == "detailed":
            out.append((a, "在精细拟合中继续", "Continue in Detailed fit"))
    return out


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


class BuiltinDialog(QDialog):
    """「用内置结构计算 FEFF」：列出含吸收元素的内置结构（查不到样品的吸收边时列全部），选一行，可勾“重新计算”。
    没有任何内置结构含该元素 → 只提示并给“去 FEFF 页”。"""

    def __init__(self, parent, element, edge, names, existing=()):
        super().__init__(parent)
        from xafsmith import structures as xs
        self.setWindowTitle(T("用内置结构计算 FEFF", "Compute FEFF from a built-in structure"))
        self.names, self.element, self.edge, self.goto_feff = list(names), element, edge, False
        self.tab = None
        lay = QVBoxLayout(self)
        if not self.names:
            lay.addWidget(W.label(T("没有内置结构含吸收元素 " + (element or "?") + "，请到 FEFF 路径页添加 CIF。",
                                    "No built-in structure contains the absorber " + (element or "?") + "; add a CIF on the FEFF paths page."), "muted"))
            bb = QDialogButtonBox(QDialogButtonBox.StandardButton.Cancel)
            go = bb.addButton(T("去 FEFF 页", "Go to FEFF page"), QDialogButtonBox.ButtonRole.AcceptRole)
            bb.button(QDialogButtonBox.StandardButton.Cancel).setText(T("取消", "Cancel"))
            go.clicked.connect(lambda *_: setattr(self, "goto_feff", True))
            bb.accepted.connect(self.accept)
            bb.rejected.connect(self.reject)
            lay.addWidget(bb)
            return
        head = (T(f"吸收元素 {element}，吸收边 {edge}；", f"Absorber {element}, edge {edge}; ") if element else
                T("样品的吸收边不明确，列出全部内置结构（吸收元素取结构里最重的元素）；", "The samples' edge is unclear: all built-in structures are listed (absorber = the heaviest element); "))
        lay.addWidget(W.label(head + T("用 FEFF6L（默认参数同 FEFF 路径页）。已有结果直接选用，不重算。",
                                       "FEFF6L with the same defaults as the FEFF paths page. An existing result is reused."), "muted"))
        self.tab = QTableWidget(len(self.names), 3)
        self.tab.setHorizontalHeaderLabels([T("结构", "Structure"), T("来源", "Source"), T("状态", "Status")])
        for i, n in enumerate(self.names):
            for j, v in enumerate([n, xs.SOURCES.get(n, ""), T("已有计算", "already computed") if n in existing else ""]):
                self.tab.setItem(i, j, QTableWidgetItem(v))
        self.tab.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.tab.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.tab.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.tab.horizontalHeader().setStretchLastSection(True)
        self.tab.resizeColumnsToContents()
        self.tab.selectRow(0)
        self.tab.doubleClicked.connect(lambda *_: self.accept())
        lay.addWidget(self.tab)
        self.redo = QCheckBox(T("重新计算（覆盖已有结果）", "Recompute (overwrite an existing result)"))
        lay.addWidget(self.redo)
        bb = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        bb.button(QDialogButtonBox.StandardButton.Ok).setText(T("计算 / 选用", "Compute / use"))
        bb.button(QDialogButtonBox.StandardButton.Cancel).setText(T("取消", "Cancel"))
        bb.accepted.connect(self.accept)
        bb.rejected.connect(self.reject)
        lay.addWidget(bb)
        self.resize(760, 360)

    def chosen(self):
        r = self.tab.currentRow() if self.tab is not None else -1
        return self.names[r] if 0 <= r < len(self.names) else None


class QuickFitPage(Page):
    """快速拟合 / Quick fit"""
    title_zh, title_en, icon_name = "快速拟合", "Quick fit", "fit"
    fill = False
    max_width = 1180

    def __init__(self, app):
        super().__init__(app)
        self._res = None            # 最近一次结果（页面重建后仍在）：dict(kind, res, table, mode, samples)
        self._shell_cache = {}
        self._auto_rmax = False     # 程序改 Rmax 时为 True（区分用户手改）

    def stale_extra(self):
        """图片导出里改了趋势图顺序（存在拟合记录上）→ 回到本页时重建，页内趋势图跟着变"""
        return tuple(tuple(f.get("trend_order") or ()) for f in self.S.fits)

    # ------------------------------------------------------------ 数据
    def _samples_available(self):
        """可拟合的样品 = 当前会话已载入并算出 χ(k) 的谱（与精细拟合同一规则）"""
        return [k for k, g in self.S.groups.items() if has_chi(g)]

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
        self._shell_cache.clear()           # FEFF 可能在同一文件夹重算过
        self.header(T("只拟合第一壳层（N、R、σ²、ΔE0），并用人话判定结果是否可信；要逐条设置路径与参数，请切到上方的“精细拟合”。",
                      "Fits the first shell only (N, R, σ², ΔE0) and states in plain words whether the result is trustworthy; "
                      "to set every path and parameter yourself, switch to “Detailed fit” above."))
        samples = self._samples_available()
        dirs = feff_dirs()
        if not samples:
            self.add(Banner("info", T("需要：已载入并算出 χ(k) 的数据（载入谱 / χ(k) 与 FT）与 FEFF 计算（FEFF 路径）。",
                                      "Needs data with χ(k) (Load spectra / χ(k) & FT) and a FEFF calculation (FEFF paths).")))
            self._sel = None
            return
        if not dirs:                        # 有 χ(k) 但还没有 FEFF：不拦，可直接用内置结构算
            c0 = self._c1 = Card(T("1  样品与 FEFF", "1  Samples and FEFF"))
            c0.add(Banner("info", T("还没有 FEFF 计算。可以直接点“用内置结构计算…”（金属、NiO、IrO2 等常见结构），或到“FEFF 路径”页用自己的 CIF 计算。",
                                    "No FEFF calculation yet. Click “Compute from a built-in structure…” (common metals, NiO, IrO2 …) "
                                    "or use your own CIF on the FEFF paths page.")))
            self._builtin_btn = W.button(T("用内置结构计算…", "Compute from a built-in structure…"), slot=self._builtin_dialog, primary=True)
            c0.add(W.hbox(self._builtin_btn, W.button(T("去 FEFF 页", "Go to FEFF page"), slot=lambda: self.app.go("feff")), None, spacing=8))
            self.add(c0)
            self._sel = None
            return
        # ① 样品与 FEFF
        c1 = self._c1 = Card(T("1  样品与 FEFF", "1  Samples and FEFF"))
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
        cur2 = next((d for d in dirs if str(d) == st.get("feff2")), None)
        self._feff2 = W.combo([None] + list(dirs), cur2, fmt=lambda p: T("（无）", "(none)") if p is None else str(p.relative_to(paths.ROOT)))
        self._feff2.setToolTip(T("混合相（如金属 + 氧化物）：再选第二个 FEFF 文件夹，两相各拟合第一壳层（N、R、σ² 各一套，ΔE0 共用；"
                                 "联合拟合时各样品只有自己的 N，两相的 R、σ² 全批共享）。吸收原子须相同；只用于样品用途。选了第二相，"
                                 "Rmax 缺省改为 3.0 Å。",
                                 "Mixed phases (e.g. metal + oxide): choose a second FEFF folder; each phase fits its first shell (own N, R, σ²; "
                                 "shared ΔE0; in a joint fit each sample has its own N while R and σ² of the two phases are shared by the batch). "
                                 "Same absorber required; Sample mode only. With a second phase the default Rmax becomes 3.0 Å."))
        c1.add(W.field(T("样品（多选）", "Samples (several)"), self._smp))
        self._builtin_btn = W.button(T("用内置结构计算…", "Compute from a built-in structure…"), slot=self._builtin_dialog,
                                     tip=T("没有合适的 FEFF 计算时：从内置结构（常见金属、NiO、IrO2 等）直接算 FEFF6L，算完自动选中。",
                                           "No suitable FEFF calculation yet: run FEFF6L from a built-in structure (common metals, NiO, IrO2 …); "
                                           "it is selected when done."))
        c1.add(W.hbox(W.field(T("FEFF 文件夹", "FEFF folder"), self._feff), W.vbox(None, self._builtin_btn), None, spacing=10))
        c1.add(W.field(T("第二相 FEFF（可选）", "Second-phase FEFF (optional)"), self._feff2))
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
        self._feff2.currentIndexChanged.connect(lambda *_: self._changed())
        self._rmax.valueChanged.connect(self._rmax_edited)
        self._name.textChanged.connect(lambda *_: self._changed())
        self._s02.textEdited.connect(self._s02_typed)
        self._run.clicked.connect(self._go)
        self._changed(rebuild_results=False)
        self._show_results()

    # ------------------------------------------------------------ 输入状态
    def _s02_typed(self, txt):
        self.state["s02_src"] = None            # 手改 → 来源变为手动
        self._changed()

    def _feff2_dir(self):
        """有效的第二相 FEFF 文件夹（字符串）：只在样品用途且选了第二相时有；否则 None"""
        d = self._feff2.value()
        return str(d) if d is not None and self._mode.value() == "sample" else None

    def _rmax_edited(self, *_):
        if self._auto_rmax:
            return
        self.state["rmax_set"] = True           # 用户改过 Rmax：不再随第二相自动换缺省
        self._changed()

    def _changed(self, rebuild_results=False):
        st = self.state
        if not st.get("rmax_set"):              # Rmax 缺省：混合相 3.0 Å，否则 2.5 Å
            want = qf.default_rmax(self._feff2_dir() is not None)
            if abs(self._rmax.value() - want) > 1e-9:
                self._auto_rmax = True
                self._rmax.setValue(want)
                self._auto_rmax = False
        st.update(samples=self._smp.value(), feff=str(self._feff.value()), mode=self._mode.value(), s02=self._s02.text().strip(),
                  rmax=self._rmax.value(), name=self._name.text().strip(), feff2=self._feff2_dir() or "")
        self._feff2.setEnabled(st["mode"] == "sample")
        ek_now = self._edge_of(st["samples"])
        if st.get("s02_src") and ek_now and ek_now != st.get("s02_src_edge"):
            st["s02_src"] = None                # 换了吸收边：标样值不再适用，清空让用户重选
            self._s02.setText("")
            st["s02"] = ""
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
        txt = T("相 1　" if self._feff2_dir() else "", "Phase 1  " if self._feff2_dir() else "") + T(f"第一壳层：<b>{sh.absorber}–{sh.scatterer} ×{sh.n_ref:g}</b>，{rng} Å（合并 {len(sh.members)} 条路径，"
                f"N_ref = {sh.n_ref:g}，R_ref = {sh.r_cif:.3f} Å）",
                f"First shell: <b>{sh.absorber}–{sh.scatterer} ×{sh.n_ref:g}</b>, {rng} Å ({len(sh.members)} merged path(s), "
                f"N_ref = {sh.n_ref:g}, R_ref = {sh.r_cif:.3f} Å)")
        if sh.other_elements:
            txt += "<br>" + T("提示：第一层还有 " + "、".join(f"{e}（{r:.2f} Å）" for e, r in sh.other_elements) + "，未考虑。",
                              "Note: the first layer also has " + ", ".join(f"{e} ({r:.2f} Å)" for e, r in sh.other_elements)
                              + ", not included.")
        d2 = self._feff2_dir()
        if d2:
            try:
                sh2 = self._shell(d2)
                rr2 = [m["reff"] for m in sh2.members]
                rng2 = f"{min(rr2):.2f}–{max(rr2):.2f}" if len(rr2) > 1 else f"{rr2[0]:.2f}"
                txt += "<br>" + T(f"相 2　第一壳层：<b>{sh2.absorber}–{sh2.scatterer} ×{sh2.n_ref:g}</b>，{rng2} Å（合并 {len(sh2.members)} 条路径，"
                                  f"N_ref = {sh2.n_ref:g}，R_ref = {sh2.r_cif:.3f} Å）",
                                  f"Phase 2  first shell: <b>{sh2.absorber}–{sh2.scatterer} ×{sh2.n_ref:g}</b>, {rng2} Å "
                                  f"({len(sh2.members)} merged path(s), N_ref = {sh2.n_ref:g}, R_ref = {sh2.r_cif:.3f} Å)")
                if sh2.absorber != sh.absorber:
                    txt += f'<br><span style="color:{C["err"]}">' + T(f"✗ 两相的吸收原子须相同：{sh.absorber} / {sh2.absorber}。",
                                                                       f"✗ Both phases need the same absorber: {sh.absorber} / {sh2.absorber}.") + "</span>"
            except Exception as ex:      # noqa: BLE001
                logs.log.debug("快速拟合：第二相第一壳层读取失败 %s", d2, exc_info=True)
                txt += f'<br><span style="color:{C["err"]}">' + T(f"无法读取第二相 FEFF 路径：{ex}", f"Cannot read the second-phase FEFF paths: {ex}") + "</span>"
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
        d2 = self._feff2_dir()
        if d2 and d2 == st.get("feff"):
            return T("第二相的 FEFF 文件夹与第一相相同", "The second-phase FEFF folder is the same as the first")
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
        self.state["s02_src_edge"] = self._edge_of(self.state.get("samples", []))
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
        work = quick_job(self.S, samples, str(self._feff.value()), float(st["rmax"]), mode, s02, src, st.get("name") or None,
                         feff2=self._feff2_dir())
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

    # ------------------------------------------------------------ 结果
    def _results(self):
        """(结果行列表 [QuickResult], 整批判定 JointVerdict 或 None)"""
        r = self._res["res"]
        return (r.samples, r.verdict) if self._res["kind"] == "joint" else ([r], None)

    @staticmethod
    def _ex(v, e, f):
        if v is None:
            return "–"
        return f"{v:{f}}" if e is None else f"{v:{f}} ± {e:{f}}"

    @staticmethod
    def _vtext(v):
        return T(v.summary("zh"), v.summary("en"))

    def _ctx(self):
        """操作按钮要用的当前窗口：(Rmax, 第一壳层 R_CIF（混合相取较短者）)"""
        r = self._results()[0][0]
        rc = [r.shell.r_cif] + ([r.phase2["shell2"].r_cif] if r.phase2 else [])
        return r.window["rmax"], min(rc)

    def _items_box(self, items):
        """判定条目逐条：✓ / ✗ / ℹ + 文字，未通过的再给一行建议和操作按钮"""
        col = {"pass": C["ok"], "fail": C["err"], "note": C["text2"]}
        mark = {"pass": "✓", "fail": "✗", "note": "ℹ"}
        box = W.vbox(spacing=4)
        rmax, rcif = self._ctx() if self._res else (None, None)
        for it in items:
            txt = f'<span style="color:{col[it.level]};font-weight:700">{mark[it.level]}</span>&nbsp;' + T(it.zh, it.en)
            if it.level == "fail" and T(it.advice_zh, it.advice_en):
                txt += f'<br><span style="color:{C["text2"]}">&nbsp;&nbsp;&nbsp;→ ' + T(it.advice_zh, it.advice_en) + "</span>"
            box.layout().addWidget(W.label(txt, rich=True))
            acts = item_actions(it, rmax, rcif)
            if acts:
                btns = [W.button(T(zh, en), slot=lambda a=a: self._do_action(a)) for a, zh, en in acts]
                box.layout().addWidget(W.hbox(*btns, None, spacing=8, margins=(24, 0, 0, 0)))
        return box

    def _do_action(self, a):
        if a == "rmax":
            rmax, rcif = self._ctx()
            x = rmax_target(rmax, rcif)
            if x is not None:
                self._rmax.setValue(x)              # 视为手改：_rmax_edited 记 rmax_set，不再随第二相自动换缺省
                self._go()
        elif a == "structure":
            self._change_structure()
        elif a == "calib":
            self.app.go("calib")
        elif a == "s02":
            self._pick_s02()
        elif a == "detailed":
            self._to_detailed()

    def _change_structure(self):
        """滚到 ① 卡片、聚焦 FEFF 下拉，并打开“用内置结构计算…”对话框"""
        self.ensureWidgetVisible(self._c1)
        self._feff.setFocus()
        self._builtin_dialog()

    # ------------------------------------------------------------ 用内置结构计算 FEFF
    def _builtin_target(self):
        """(吸收元素, 吸收边, 内置结构名列表, 已有计算的结构名集合)：元素与边取自当前所选样品（没选 = 全部已载入样品）；
        查不到（样品不在同一吸收边）→ (None, None, 全部内置结构, 空集)"""
        from xafsmith import structures as xs
        sel = self.state.get("samples") or self._samples_available()
        ek = self._edge_of(sel)
        if not ek:
            return None, None, list(xs.BUILTIN_NAMES), set()
        el, edge = ek.split("_", 1)
        names = xs.builtin_for(el)
        have = {n for n in names if any(paths.FEFF.glob(f"{n}_{el}{edge}/site*/feff0001.dat"))} if paths.FEFF.exists() else set()
        return el, edge, names, have

    def _builtin_dialog(self):
        from xafsmith import feff_wrap as xf, structures as xs
        el, edge, names, have = self._builtin_target()
        dlg = BuiltinDialog(self, el, edge, names, have)
        if not dlg.exec():
            return
        if dlg.goto_feff:
            self.app.go("feff")
            return
        name = dlg.chosen()
        if not name:
            return
        redo = dlg.redo.isChecked()
        if el is None:                      # 吸收元素 / 边不明：取该结构里最重的元素，边同 FEFF 页缺省
            from pymatgen.core import Element
            el = max({sp.symbol for sp in xs.builtin(name).composition.elements}, key=lambda e: Element(e).Z)
            edge = xf.default_edge(el)
        pg = self

        def done(res):
            out, reused = res
            pg.state["feff"] = str(out)
            pg._shell_cache.clear()
            pg.refresh()
            W.toast(pg, T(f"已选用已有计算：{paths.rel(out)}" if reused else f"FEFF 完成：{paths.rel(out)}",
                          f"Using the existing calculation: {paths.rel(out)}" if reused else f"FEFF done: {paths.rel(out)}"))
        W.run_task(self, lambda progress: xf.build_builtin(name, el, edge, recompute=redo, progress=progress), done,
                   T(f"FEFF6L 计算 {name}（{el} {edge}）…", f"Running FEFF6L for {name} ({el} {edge})…"), self._builtin_btn,
                   progress=True, cancellable=False, key="feff")

    def _show_results(self, error=None):
        if not hasattr(self, "_rbox"):
            return
        W._clear_layout(self._rbox.layout())
        lay = self._rbox.layout()
        if error:
            lay.addWidget(Banner("err", error))
        if not self._res:
            return
        try:
            self._fill_results(lay)
        except RuntimeError:
            logs.log.debug("quick fit results: widget deleted", exc_info=True)

    def _fill_results(self, lay):
        import pandas as pd
        rs, batch = self._results()
        joint, mode = batch is not None, self._res["mode"]
        c4 = Card(T("4  结果", "4  Result"))
        w = rs[0].window
        win = T(f"窗口：k {w['kmin']:g}–{w['kmax']:g} Å⁻¹（dk {w['dk']:g}，{w['window']}），k 权重 {w['kweight']}，"
                f"R {w['rmin']:.2f}–{w['rmax']:.2f} Å" + ("（全批统一）" if joint else ""),
                f"Window: k {w['kmin']:g}–{w['kmax']:g} Å⁻¹ (dk {w['dk']:g}, {w['window']}), k-weight {w['kweight']}, "
                f"R {w['rmin']:.2f}–{w['rmax']:.2f} Å" + (" (common to the batch)" if joint else ""))
        c4.add(W.label(win, "faint"))
        if rs[0].phase2:
            s1, s2_ = rs[0].shell, rs[0].phase2["shell2"]
            c4.add(W.label(T(f"混合相：相 1 = {s1.absorber}–{s1.scatterer}，相 2 = {s2_.absorber}–{s2_.scatterer}"
                             + ("；两相的 R、σ² 全批共享，各样品只有自己的 N" if joint else "；ΔE0 两相共用"),
                             f"Mixed phases: phase 1 = {s1.absorber}–{s1.scatterer}, phase 2 = {s2_.absorber}–{s2_.scatterer}"
                             + ("; R and σ² of the two phases are shared by the batch, each sample has its own N" if joint
                                else "; ΔE0 is shared by the two phases"), ), "faint"))
        # 整批判定
        if joint:
            res = self._res["res"]
            c4.add(Banner("ok" if batch.ok else "warn",
                          T("整批：", "Batch: ") + self._vtext(batch) + T(f"　联合 R 因子 {res.rfactor:.4f}，共享 ΔE0 = {self._ex(res.e0, res.e0_err, '.2f')} eV",
                                                                      f" · joint R-factor {res.rfactor:.4f}, shared ΔE0 = {self._ex(res.e0, res.e0_err, '.2f')} eV")))
            if batch.items:
                c4.add(self._items_box(batch.items))
        # 结果表
        rows = []
        for r in rs:
            row = {T("样品", "Sample"): r.sample, "N": self._ex(r.n, r.n_err, ".2f"), "R (Å)": self._ex(r.r, r.r_err, ".4f"),
                   "σ² (Å²)": self._ex(r.sigma2, r.sigma2_err, ".5f")}
            if r.phase2:                                    # 混合相：相 2 的 N、R、σ² 与比例（N / N_ref，仅供参考）
                p2 = r.phase2
                row.update({"N₂": self._ex(p2["n"], p2["n_err"], ".2f"), "R₂ (Å)": self._ex(p2["r"], p2["r_err"], ".4f"),
                            "σ²₂ (Å²)": self._ex(p2["sigma2"], p2["sigma2_err"], ".5f"),
                            T("相 2 比例", "Phase-2 fraction"): f"{p2['frac']:.2f}"})
            row.update({"ΔE0 (eV)": self._ex(r.e0, r.e0_err, ".2f"),
                        "S0²": self._ex(r.s02, r.s02_err, ".3f") + (T("（固定）", " (fixed)") if r.mode == "sample" else ""),
                        T("R 因子", "R-factor"): f"{r.rfactor:.4f}", T("判定", "Verdict"): self._vtext(r.verdict)})
            rows.append(row)
        self._tab = W.Table(pd.DataFrame(rows), max_height=300, decimals=5)
        self._tab.setToolTip(T("点一行查看该样品的拟合图与判定", "Click a row to see that sample's fit plot and verdict"))
        c4.add(self._tab)
        if mode == "standard":
            r = rs[0]
            c4.add(Banner("info", T(f"这个标样拟合已进入会话历史：在样品用途下点“选取标样值…”即可使用 S0² = {r.s02:.4f} ± {r.s02_err or 0:.4f}"
                                    "（会话里的拟合即可；保存后重启软件仍可选）。",
                                    f"This standard fit is now in the session history: in Sample mode click “Pick standard value…” to use "
                                    f"S0² = {r.s02:.4f} ± {r.s02_err or 0:.4f} (a session fit is enough; after saving it stays available after a restart).")))
        # 趋势（联合）
        table = self._res.get("table")
        if joint and table is not None and len(table):
            c4.add(self._trend_box(table))
        # 选中样品的详情
        self._detail = W.vbox()
        c4.add(self._detail)
        sm = self._tab.selectionModel()
        sm.currentRowChanged.connect(lambda cur, _prev: self._select(cur.row()))
        self._tab.selectRow(min(self._res.get("row", 0), len(rs) - 1))
        # 操作
        self._b_save = W.button(T("保存", "Save"), icon_name="save", slot=self._save,
                                tip=T("写 models/<名>.json、拟合记录（exafs_fits.csv、报告、图）与参数文件；联合拟合另写趋势 CSV。与命令行 quickfit --save 相同。",
                                      "Write models/<name>.json, the fit records (exafs_fits.csv, report, figure) and the parameter file; a joint fit also "
                                      "writes the trend CSV. Same as the command line quickfit --save."))
        self._b_fig = W.button(T("去图片导出", "Go to Figure export"), slot=self._to_pubfig,
                               tip=T("打开“图片导出”的趋势图并选中这次拟合（需要 ≥ 2 个样品的联合拟合）。",
                                     "Open the trend figure in “Figure export” with this fit selected (needs a joint fit of ≥ 2 samples)."))
        self._b_fig.setEnabled(joint)
        self._b_det = W.button(T("在精细拟合中继续", "Continue in Detailed fit"), slot=self._to_detailed,
                               tip=T("把这个模型（路径、参数、窗口）载入“精细拟合”，在那里逐条修改再拟合。",
                                     "Load this model (paths, parameters, window) into “Detailed fit” to edit it there and refit."))
        c4.add(W.hbox(self._b_save, self._b_fig, self._b_det, None, spacing=8))
        lay.addWidget(c4)

    def _select(self, i):
        rs, _batch = self._results()
        if not 0 <= i < len(rs):
            return
        self._res["row"] = i
        W._clear_layout(self._detail.layout())
        r, lay = rs[i], self._detail.layout()
        v = r.verdict
        lay.addWidget(W.label(f"<b>{r.sample}</b>" + T("　", "&nbsp;&nbsp;") + self._vtext(v), rich=True))
        lay.addWidget(self._rplot(i, r))
        lay.addWidget(self._items_box(v.items))

    def _rplot(self, i, r):
        """|χ(R)| 数据与拟合（在拟合所用的 k 权重与窗口下做 FT），灰带 = 拟合 R 窗口（Rmin–Rmax）"""
        from larch import Group
        from larch.xafs import xftf
        from ...state import fit_dataset
        fit = r.fit
        fd = fit_dataset(fit, fit["summ"]["datasets"][i]["id"]) if fit["summ"].get("multi") else fit
        c, md = fd["curves"], fd["model"]
        kw = md["kweight"][-1] if isinstance(md["kweight"], (list, tuple)) else md["kweight"]
        plot = W.Plot(280)
        gd, gf = Group(k=c["k"], chi=c["chi"]), Group(k=c["kfit"], chi=c["chifit"])
        for g in (gd, gf):
            xftf(g, kmin=md["kmin"], kmax=md["kmax"], dk=md["dk"], window=md["window"], kweight=kw)
        ax = plot.ax
        ax.plot(gd.r, gd.chir_mag, color=C["text"], lw=1.3, label=T("数据", "data"))
        ax.plot(gf.r, gf.chir_mag, color=C["err"], ls="--", lw=1.3, label=T("拟合", "fit"))
        ax.axvspan(md["rmin"], md["rmax"], color=C["text3"], alpha=0.12, lw=0)
        ax.axvline(md["rmin"], color=C["text3"], lw=0.8, ls=":")
        ax.axvline(md["rmax"], color=C["text3"], lw=0.8, ls=":")
        ax.set_xlim(0, max(4.0, md["rmax"] + 1.5))
        ax.set_xlabel(T("R（Å，未做相位校正）", "R (Å, not phase-corrected)"))
        ax.set_ylabel(f"|χ(R)|  (k$^{kw}$)")
        plot.draw()
        return plot

    def _trend_box(self, table):
        """页内趋势图：下拉选 N / R / σ²（带误差棒；横轴按 trend 的序列规则）"""
        from xafsmith import trend as tr
        from .trend_view import draw_trend, notes_for, order_editor, panel_name
        st = self.state
        fit = self._res["res"].fit
        pk = st.get("qf_panel", "N")
        sel = W.combo(["N", "R", "sigma2"], pk if pk in ("N", "R", "sigma2") else "N", fmt=panel_name)
        box = W.vbox()
        paths_ = list(dict.fromkeys(table["path"]))

        def draw(*_):
            st["qf_panel"] = sel.value()
            W._clear_layout(plot_box.layout())
            tab = tr.ordered(table, fit.get("trend_order"))          # 顺序存在拟合记录上（图片导出共用）
            for n in notes_for(tab, [sel.value()], paths_):
                plot_box.layout().addWidget(Banner("info", n))
            plot = W.Plot(240)
            draw_trend([plot.ax], tab, [sel.value()], paths_)
            plot.draw()
            plot_box.layout().addWidget(plot)
        plot_box = W.vbox()
        box.layout().addWidget(W.hbox(W.label(T("趋势图", "Trend"), "h3"), sel, None, spacing=8))
        box.layout().addWidget(plot_box)
        editor, self._trend_order = order_editor(fit, table, lambda: (draw(), self.ack()))
        box.layout().addWidget(W.collapsible(T("横轴顺序", "X-axis order"), editor, expanded=bool(fit.get("trend_order"))))
        sel.currentIndexChanged.connect(draw)
        draw()
        self._trend_sel = sel
        return box

    # ------------------------------------------------------------ 按钮
    def _save(self):
        from xafsmith.common import write_params
        from ...state import safe, save_fit
        if not self._res:
            return
        fit = self._res["res"].fit
        model = fit["model"]
        base = safe(model["name"])
        if (paths.MODELS / f"{base}.json").exists() and not W.ask(
                self, T("覆盖模型", "Overwrite model"),
                T(f"models/{base}.json 已存在，覆盖吗？（拟合记录会追加一行）", f"models/{base}.json exists. Overwrite it? (a row is appended to the fit records)")):
            return
        try:
            save_fit(fit)
            write_params(paths.FITS / f"{base}.params.json", model, "xafsmith quickfit")
        except Exception as ex:      # noqa: BLE001
            logs.log.warning("快速拟合：保存失败", exc_info=True)
            W.toast(self, T(f"保存失败：{ex}", f"Save failed: {ex}"), "err")
            return
        extra = T("（含趋势 CSV）", " (with the trend CSV)") if fit["summ"].get("multi") else ""
        W.toast(self, T(f"已保存模型 {base} 与拟合记录{extra}", f"Saved model {base} and the fit records{extra}"))

    def _fit_index(self):
        fit = self._res["res"].fit
        return next((i for i, f in enumerate(self.S.fits) if f is fit), None)

    def _to_pubfig(self):
        if not self._res or self._res["kind"] != "joint":
            return
        i = self._fit_index()
        if i is None:
            W.toast(self, T("这次拟合已不在会话历史里（工作区被清空？），请重新拟合。",
                            "This fit is no longer in the session history (workspace cleared?). Fit again."), "warn")
            return
        pg = self.app.pages["pubfig"]
        pg.state.update(kind="trend", tr_fit=i)
        pg.state.pop("tr_paths", None)
        self.app.go("pubfig")
        pg.refresh()

    def _to_detailed(self):
        if not self._res:
            return
        box = self.app.pages["fit"]
        pg = box.detailed_page
        if pg.has_content() and not W.ask(
                self, T("覆盖精细拟合", "Overwrite Detailed fit"),
                T("精细拟合里已有路径表 / 参数表，载入这个模型会覆盖它们。继续吗？（可先在精细拟合里存草稿）",
                  "Detailed fit already has path / parameter tables; loading this model overwrites them. Continue? "
                  "(You can save a draft there first.)")):
            return
        try:
            pg.load_model_dict(self._res["res"].fit["model"])
        except Exception as ex:      # noqa: BLE001
            logs.log.warning("快速拟合：载入精细拟合失败", exc_info=True)
            W.toast(self, T(f"无法载入精细拟合：{ex}", f"Cannot load into Detailed fit: {ex}"), "err")
            return
        box.show_detailed()
