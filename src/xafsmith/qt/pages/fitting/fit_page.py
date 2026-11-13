"""EXAFS 拟合页面。"""

from __future__ import annotations

from xafsmith import logs
import json
import re
from pathlib import Path
import pandas as pd
from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import QWidget
from xafsmith import paths
from ... import widgets as W
from ...state import feff_dirs, has_chi, idents, load_model, run_model, saved_models
from ...theme import C, SP
from ...widgets import T, Banner, Card, Page

from .guides import show_fit_guide
from .fit_view import FitView

_TMODEL_RE = re.compile(r"\bsigma2_debye\b|\bsigma2_eins\b|\btempK\b")   # B6：路径 σ² 用了温度模型


class FitPage(Page):
    """左右分栏：左侧依次设置数据、范围、路径、参数（“拟合”按钮固定在左下角），右侧始终显示最近一次拟合。
    改参数 → 拟合 → 看结果 → 再改，全程不用上下翻页。"""
    title_zh, title_en, icon_name = "EXAFS 拟合", "EXAFS fitting", "fit"
    fill = True
    max_width = 100000

    def refresh(self):
        lsa = getattr(self, "_lsa", None)          # 重建前记下左侧滚动位置，重建后恢复
        try:
            if lsa is not None:
                self.state["lscroll"] = lsa.verticalScrollBar().value()
        except RuntimeError:                       # C++ 对象已删除
            pass
        super().refresh()

    def build(self):
        from PySide6.QtGui import QKeySequence, QShortcut
        from PySide6.QtWidgets import QSplitter
        S = self.S
        self._fit_go = None
        self.__dict__.pop("_ptab", None)
        if not hasattr(self, "_shortcuts"):           # 只建一次（页面重建时不重复）
            self._shortcuts = []
            for seq in ("Ctrl+Return", "Ctrl+Enter"):
                sc = QShortcut(QKeySequence(seq), self)
                sc.activated.connect(lambda: self._fit_go and self._fit_go())
                self._shortcuts.append(sc)
        self.header(T("先在标样上确定 S0²，样品中固定；加壳层要通过 F 检验。变量数 ≤ N_idp/2。",
                      "Determine S0² on the standard and fix it for samples; added shells must pass the F-test. Variables ≤ N_idp/2."),
                    actions=[W.button(T("注意事项与“拟合得好”的标准", "Before you fit · what is a good fit"), icon_name="help",
                                      slot=lambda: show_fit_guide(self, 2 if self.state.get("multi") else None))])
        sp = QSplitter(Qt.Orientation.Horizontal)
        sp.setChildrenCollapsible(False)
        sp.setHandleWidth(10)
        # 左：设置（可滚动）+ 固定的拟合按钮栏
        left = QWidget()
        lv = W.QVBoxLayout(left)
        lv.setContentsMargins(0, 0, 0, 0)
        lv.setSpacing(8)
        lsa, lcol = self._scroll()
        self._lsa = lsa
        lv.addWidget(lsa, 1)
        self._bar = W.QHBoxLayout()
        self._bar.setContentsMargins(0, 4, 4, 0)
        lv.addLayout(self._bar)
        # 右：结果（可滚动）
        rsa, rcol = self._scroll()
        self._right = rcol
        sp.addWidget(left)
        sp.addWidget(rsa)
        sp.setStretchFactor(0, 9)
        sp.setStretchFactor(1, 11)
        sizes = self.state.get("split")
        if sizes:
            sp.setSizes(sizes)
        else:
            sp.setSizes([620, 760])
        sp.splitterMoved.connect(lambda *_: self.state.__setitem__("split", sp.sizes()))
        self.body.addWidget(sp, 1)
        add = lcol.addWidget
        add(self._drafts())
        add(self._saved())
        cands = [k for k, g in S.groups.items() if has_chi(g)]
        dirs = feff_dirs()
        if not cands or not dirs:
            add(Banner("info", T("需要：已载入并算出 χ(k) 的数据（载入谱 / χ(k) 与 FT）与 FEFF 计算（FEFF 路径）。",
                                 "Needs data with χ(k) (Load spectra / χ(k) & FT) and a FEFF calculation (FEFF paths).")))
        else:
            multi = bool(self.state.get("multi"))
            c1 = Card(T("1  数据与 FEFF", "1  Data and FEFF"))
            seg = W.Segmented([False, True], multi, fmt=lambda v: T("多个数据集联合", "Joint fit of several datasets") if v
                              else T("单个数据集", "Single dataset"))
            seg.changed.connect(lambda v: (self.state.__setitem__("multi", bool(v)), self.refresh()))
            c1.add(W.field(T("拟合方式", "Mode"), seg,
                           tip=T("联合拟合：几个数据集同时拟合，同名参数共享（如不同温度的样品共用 S0² 与 ΔR）",
                                 "Joint fit: several datasets fitted simultaneously; parameters with the same name are shared "
                                 "(e.g. samples at different temperatures share S0² and ΔR)")))
            if multi:
                sel0 = [k for k in self.state.get("datas", []) if k in cands] or cands[:2]
                datas = W.MultiSelect(cands, sel0, T("选择数据集（联合拟合至少 2 个）", "Datasets (at least 2 for a joint fit)"))
                keys = datas.value()
                g = S.groups[keys[0]] if keys else None
                tag = f"_{g.element}{g.edge}" if g is not None else None
                match = [d for d in dirs if tag and tag in str(d.relative_to(paths.FEFF))]
                fdirs = W.MultiSelect(dirs, [Path(x) for x in self.state.get("fdirs_multi", [str(d) for d in match[:1]])],
                                      T("选择 FEFF 目录（所有数据集共用；可多选：多物相 / 多位点）",
                                        "FEFF folders (shared by all datasets; several: phases / sites)"),
                                      fmt=lambda p: str(p.relative_to(paths.ROOT)))
                datas.committed.connect(lambda v: (self.state.__setitem__("datas", list(v)), self.refresh()))
                fdirs.committed.connect(lambda v: (self.state.__setitem__("fdirs_multi", [str(x) for x in v]), self.refresh()))
                c1.add(W.field(T("数据（多选）", "Data (several)"), datas))
                c1.add(W.field(T("FEFF 目录", "FEFF folders"), fdirs))
                add(c1)
                if not keys:
                    add(Banner("info", T("选择至少一个数据集（联合拟合至少 2 个；只选 1 个等同于单数据集拟合）。",
                                         "Choose at least one dataset (a joint fit needs 2 or more; one dataset equals a single fit).")))
                elif fdirs.value():
                    self._model_cards(add, keys, fdirs.value(), True)
                else:
                    add(Banner("info", T("选择至少一个 FEFF 目录。", "Choose at least one FEFF folder.")))
            else:
                data = W.combo(cands, self.state.get("data"))
                g = S.groups[data.value()]
                tag = f"_{g.element}{g.edge}"
                match = [d for d in dirs if tag in str(d.relative_to(paths.FEFF))]
                fd_key = "fdirs_" + data.value()
                fdirs = W.MultiSelect(dirs, [Path(x) for x in self.state.get(fd_key, [str(d) for d in match[:1]])],
                                      T("选择 FEFF 目录（可多选：多物相 / 多位点）", "FEFF folders (several: phases / sites)"),
                                      fmt=lambda p: str(p.relative_to(paths.ROOT)))
                data.currentIndexChanged.connect(lambda *_: (self.state.__setitem__("data", data.value()), self.refresh()))
                fdirs.committed.connect(lambda v: (self.state.__setitem__(fd_key, [str(x) for x in v]), self.refresh()))
                c1.add(W.field(T("数据", "Data"), data))
                c1.add(W.field(T("FEFF 目录", "FEFF folders"), fdirs))
                add(c1)
                if fdirs.value():
                    self._model_cards(add, [data.value()], fdirs.value(), False)
                else:
                    add(Banner("info", T("选择至少一个 FEFF 目录。", "Choose at least one FEFF folder.")))
        lcol.addStretch(1)
        self._show_result(S.fits[-1] if S.fits else None)
        y = self.state.get("lscroll", 0)
        if y:
            QTimer.singleShot(0, lambda: lsa.verticalScrollBar().setValue(y))

    def _scroll(self):
        from PySide6.QtWidgets import QScrollArea
        sa = QScrollArea()
        sa.setWidgetResizable(True)
        sa.setFrameShape(W.QFrame.Shape.NoFrame)
        sa.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        inner = QWidget()
        inner.setObjectName("page")
        col = W.QVBoxLayout(inner)
        col.setContentsMargins(SP['xs'], SP['xs'], SP['md'], SP['sm'])
        col.setSpacing(12)
        sa.setWidget(inner)
        return sa, col

    def _show_result(self, fit):
        W._clear_layout(self._right)
        if fit is None:
            self._right.addWidget(Banner("info", T("还没有拟合。在左侧选好路径与参数后点“拟合”（或按 Ctrl+Enter），结果显示在这里。",
                                                   "No fit yet. Set paths and parameters on the left and click “Fit” (or Ctrl+Enter); "
                                                   "the result appears here.")))
        else:
            self._right.addWidget(FitView(self, fit, "last", adopt=self._adopt if hasattr(self, "_ptab") else None))
        self._right.addStretch(1)

    def _adopt(self, fit):
        """把拟合值写回参数表（只改变量；固定与约束的参数不动）"""
        cur = getattr(self, "_ptab", {})
        t = cur.get("tab")
        if t is None:
            return
        fp = fit["summ"]["params"]
        m = t.m
        m.beginResetModel()
        n = 0
        for i, r in m.df.iterrows():
            v = fp.get(r["name"])
            if v is None or v.get("expr") or not v.get("vary", True):
                continue
            if isinstance(r["expr"], str) and r["expr"].strip():
                continue
            m.df.at[i, "value"] = float(v["value"])
            n += 1
        m.endResetModel()
        t.edited.emit()
        self.state["partab"] = pd.concat([self.state.get("partab", m.df.iloc[0:0])[lambda d: ~d.name.isin(m.df.name)], m.df],
                                         ignore_index=True)
        W.toast(self, T(f"已把 {n} 个变量的拟合值写入参数表（作为下次拟合的初值）",
                        f"{n} fitted values copied into the parameter table (start values for the next fit)"))

    def _drafts(self):
        """拟合草稿：把当前的数据、拟合范围、路径表、参数表存成命名草稿，以后随时接着做。
        草稿不含拟合结果本身；完成的拟合请用“保存结果”。"""
        from ... import session
        app = self.window()
        drafts = session.list_drafts()
        body = Card(flat=True)
        body.add(W.label(T("草稿保存数据选择、FEFF 目录、拟合范围、路径表与参数表（含你改过的初值与约束），存在 output/gui/drafts/。"
                           "关闭软件时这些设置也会自动保存，下次打开自动恢复。",
                           "A draft stores the data choice, FEFF folders, fit range, path table and parameter table (including your edited "
                           "start values and constraints) in output/gui/drafts/. These settings are also saved automatically when you "
                           "close the app and restored next time."), "faint"))
        mk = "mname_multi" if self.state.get("multi") else "mname_" + str(self.state.get("data", ""))
        name = W.text(self.state.get(mk, "") or T("草稿", "draft"))

        def save():
            n = name.text().strip()
            if not n:
                return
            f = session.drafts_dir() / (session.safe_name(n) + ".json")
            if f.exists() and not W.ask(self, T("覆盖草稿", "Overwrite draft"),
                                        T(f"已有同名草稿（文件 {f.name}），覆盖吗？", f"A draft with this name exists ({f.name}). Overwrite it?")):
                return
            try:
                session.save_draft(n, self.S, app.pages)
            except Exception:                                  # noqa: BLE001
                logs.log.warning("保存草稿失败", exc_info=True)
                W.toast(self, T("保存草稿失败（详情见日志）", "Could not save the draft (see the log)"), "err")
                return
            W.toast(self, T(f"草稿“{n}”已保存", f"Draft “{n}” saved"))
            self.refresh()
        body.add(W.hbox(W.field(T("草稿名", "Draft name"), name), W.vbox(None, W.button(T("保存草稿", "Save draft"), slot=save)),
                        spacing=10))
        if drafts:
            sel = W.combo(drafts, drafts[0], fmt=lambda d: f"{d['name']}    ({d['saved'].replace('T', ' ')})")

            def open_():
                d = sel.value()
                snap = session.load_draft(d["file"])
                if snap is None:
                    W.toast(self, T("草稿文件无法读取", "Cannot read the draft file"), "err")
                    return
                app.restore_session(snap, only=tuple(snap.get("only") or ("fit",)), quiet=True)
                W.toast(self, T(f"已打开草稿“{d['name']}”", f"Draft “{d['name']}” opened"))

            def delete():
                d = sel.value()
                if not W.ask(self, T("删除草稿", "Delete draft"), T(f"删除草稿“{d['name']}”？此操作不能撤销。",
                                                                    f"Delete draft “{d['name']}”? This cannot be undone.")):
                    return
                session.delete_draft(d["file"])
                self.refresh()
            body.add(W.hbox(W.field(T("已有草稿", "Saved drafts"), sel),
                            W.vbox(None, W.hbox(W.button(T("打开", "Open"), primary=True, slot=open_),
                                                W.button(T("删除", "Delete"), slot=delete), spacing=6)), spacing=10))
        cl = W.collapsible(T(f"拟合草稿（{len(drafts)} 个）", f"Fit drafts ({len(drafts)})"), body,
                           expanded=self.state.get("drafts_open", False))
        cl.findChild(W.QToolButton).toggled.connect(lambda on: self.state.__setitem__("drafts_open", on))
        return cl

    def _saved(self):
        S = self.S
        models = saved_models()
        body = Card(flat=True)
        if not models:
            body.add(W.label(T("建立模型并点“保存结果”后，模型存入 models/，以后可在这里一键重跑。",
                               "After “Save result”, models go to models/ and can be rerun here in one click."), "faint"))
            return W.collapsible(T("运行已保存的模型", "Run a saved model"), body)
        from xafsmith import pipeline as pl
        mf = W.combo(models, self.state.get("mf"))
        smp = W.tag(W.MultiSelect([], [], T("样品（可多选：同一模型依次用于每个样品）", "Samples (several: model applied to each)")), "saved_smp")

        hint = W.label(T("这是多数据集模型：样品由模型内 datasets 决定，直接运行一次。",
                         "This is a multi-dataset model: the samples are set by its datasets; it runs once."), "faint")
        hint.setVisible(False)

        def upd():
            self.state["mf"] = mf.value()
            multi_ = False
            try:
                md_ = json.loads((paths.MODELS / mf.value()).read_text(encoding="utf-8-sig"))
                msmp, multi_ = md_.get("sample", ""), "datasets" in md_
            except Exception:
                logs.log.warning("qt.pages.fitting.upd 出错（已忽略或已提示）", exc_info=True)
                msmp = ""
            smp.setEnabled(not multi_)
            hint.setVisible(multi_)
            if multi_:
                smp.set_options([], [])
                return
            meta_s = list(pl.load_meta().query("use != '0'")["sample"]) if pl.META.exists() else []
            opts = [o for o in dict.fromkeys([msmp] + meta_s + list(S.groups)) if o]
            smp.set_options(opts, [msmp] if msmp in opts else [])
        mf.currentIndexChanged.connect(lambda *_: upd())
        upd()
        btn = W.button(T("运行", "Run"), primary=True, icon_name="play")
        W.bind_task(btn, "fit_saved", "fit")

        def go():
            todo = [None] if not smp.isEnabled() else (smp.value() or [None])
            names = list(todo)

            def work(progress):
                out = []
                for i, s_ in enumerate(names):
                    progress(i / len(names), s_ or "")
                    out.append(run_model(S, load_model(mf.value(), s_)))
                return out

            def done(fits):
                S.fits.extend(fits)
                S.emit("fits")
                W.toast(self, T(f"完成 {len(fits)} 个拟合（右侧与“拟合历史”）", f"{len(fits)} fit(s) done (right and in “Fit history”)"))
                self._show_result(fits[-1] if fits else None)
                self.ack()
            W.run_task(self, work, done, T("拟合中…", "Fitting…"), btn, progress=True, key="fit_saved", excl="fit")
        btn.clicked.connect(go)
        body.add(W.field(T("模型", "Model"), mf))
        body.add(W.hbox(W.field(T("样品", "Samples"), smp), W.vbox(None, btn), spacing=10))
        body.add(hint)
        cl = W.collapsible(T(f"运行已保存的模型（models/ 中 {len(models)} 个）", f"Run a saved model ({len(models)} in models/)"), body,
                           expanded=self.state.get("saved_open", False))
        cl.findChild(W.QToolButton).toggled.connect(lambda on: self.state.__setitem__("saved_open", on))
        return cl

    _RCOLS = ["name", "expr", "value", "sigma", "note"]

    def _restraint_section(self, card):
        """B3：软约束（restraint）表，单数据集与多数据集共用；状态存 self.state["restraints"]（草稿随页面状态保存）。"""
        card.add(W.label(T("软约束（restraint，可选）", "Restraints (optional)"), "h3"))
        card.add(W.label(T("把参数拉向先验值：在 χ² 中加入 ((expr − value)/σ)² × χ²_ν(无约束)。σ 按报告误差的尺度填，"
                           "例如标样拟合的 S0² = 0.816 ± 0.05。expr 是参数表达式（如 s02 或 ss1 − ss2）；只在有独立先验时使用。",
                           "Pulls parameters towards a prior value: adds ((expr − value)/σ)² × χ²_ν(unrestrained) to χ². "
                           "Give σ on the scale of the reported errors, e.g. S0² = 0.816 ± 0.05 from a standard fit. expr is a "
                           "parameter expression (e.g. s02 or ss1 − ss2); use it only with an independent prior."), "faint"))
        df = self.state.get("restraints")
        if not isinstance(df, pd.DataFrame) or list(df.columns) != self._RCOLS:
            df = pd.DataFrame({"name": pd.Series([], dtype=object), "expr": pd.Series([], dtype=object),
                               "value": pd.Series([], dtype=float), "sigma": pd.Series([], dtype=float),
                               "note": pd.Series([], dtype=object)})
        for c_ in ("name", "expr", "note"):
            df[c_] = df[c_].fillna("").astype(object)
        for c_ in ("value", "sigma"):
            df[c_] = pd.to_numeric(df[c_], errors="coerce").astype(float)
        self.state["restraints"] = df
        cur = {}
        holder = W.vbox()
        card.add(holder)

        def build(df_):
            W._clear_layout(holder.layout())
            if len(df_):
                t = W.Table(df_, editable=self._RCOLS, max_height=200, decimals=6)
                t.edited.connect(lambda: self.state.__setitem__("restraints", t.df()))
                holder.layout().addWidget(t)
                cur["tab"] = t
            else:
                cur.pop("tab", None)

        def add_row():
            d = self._restraints_df(cur)
            d.loc[len(d)] = dict(name="", expr="", value=float("nan"), sigma=float("nan"), note="")
            d["value"], d["sigma"] = d["value"].astype(float), d["sigma"].astype(float)
            self.state["restraints"] = d
            build(d)

        def del_row():
            t = cur.get("tab")
            if t is None:
                return
            rows = sorted({i.row() for i in t.selectionModel().selectedRows()} |
                          ({t.currentIndex().row()} if t.currentIndex().isValid() else set()))
            d = self._restraints_df(cur)
            d = d.drop(index=[r for r in rows if r < len(d)]).reset_index(drop=True)
            self.state["restraints"] = d
            build(d)
        build(df)
        card.add(W.hbox(W.button(T("添加一行", "Add a row"), slot=add_row),
                        W.button(T("删除选中行", "Delete selected row"), slot=del_row), None, spacing=6))
        return cur

    def _restraints_df(self, cur):
        t = cur.get("tab")
        return t.df() if t is not None else self.state["restraints"].copy()

    def _restraints_from_table(self, cur):
        """表 → 模型 restraints 列表（expr 为空的行忽略）；value / sigma 不是数字或 sigma ≤ 0 → toast 并返回 False。"""
        import math
        d = self._restraints_df(cur)
        self.state["restraints"] = d
        out = []
        for i, r in d.iterrows():
            if not str(r["expr"]).strip():
                continue
            ok = all(isinstance(r[k], (int, float)) and math.isfinite(float(r[k])) for k in ("value", "sigma"))
            if not ok or float(r["sigma"]) <= 0:
                W.toast(self, T(f"软约束第 {i + 1} 行：value 与 sigma 必须是数字，且 sigma > 0",
                                f"Restraint row {i + 1}: value and sigma must be numbers with sigma > 0"), "warn")
                return False
            item = dict(expr=str(r["expr"]).strip(), value=float(r["value"]), sigma=float(r["sigma"]))
            if str(r["name"]).strip():
                item["name"] = str(r["name"]).strip()
            if str(r["note"]).strip():
                item["note"] = str(r["note"]).strip()
            out.append(item)
        return out

    def _temp_row(self, edit_w, edit, k):
        """B6：一行“温度 (K) [输入框] [σ² 模型…]”，标签、输入框、按钮垂直居中对齐。"""
        lb = W.label(T("温度 (K)", "Temperature (K)"), wrap=False)
        btn = self._sigma2_button(edit, k)
        h = max(edit_w.sizeHint().height(), btn.sizeHint().height())
        for w_ in (lb, edit_w, btn):                       # 同一高度：输入框与按钮上下边齐平，标签文字居中
            w_.setFixedHeight(h)
        lb.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        row = W.hbox(lb, edit_w, btn, None, spacing=SP["sm"])
        lay = row.layout()
        for w_ in (lb, edit_w, btn):
            lay.setAlignment(w_, Qt.AlignmentFlag.AlignVCenter)
        return row

    @staticmethod
    def _sigma2_button(edit, k):
        b = W.button(T("σ² 模型…", "σ² model…"),
                     tip=T("把选中路径的 σ² 写成 Debye / Einstein 温度模型（多个温度共用一个 θ）", "Write the selected path's σ² as a "
                           "Debye / Einstein temperature model (one θ shared by all temperatures)"))
        b.clicked.connect(lambda *_: edit(k))
        return b

    def _apply_sigma2(self, spec, k, row, keys, ptabs, cur):
        """把对话框结果写进路径表与参数表。row：路径表行号；联合拟合且 apply_all 时，其他数据集里同名路径（label 相同）一起改。
        参数：已存在的同名参数不动（保留用户设置），只新建所缺的。"""
        targets = [(k, row)]
        if spec["apply_all"] and len(keys) > 1:
            label = ptabs[k].df().iloc[row]["label"]
            for k2 in keys:
                if k2 == k:
                    continue
                d2 = ptabs[k2].df()
                hit = d2.index[d2.label == label]
                if len(hit):
                    targets.append((k2, int(hit[0])))
        old = cur["tab"].df() if "tab" in cur else self.state.get("partab", pd.DataFrame(columns=["name", "value", "vary", "min", "max", "expr"]))
        new = [dict(name=n, expr="", **p) for n, p in spec["params"].items() if n not in set(old.name)]
        if new:
            self.state["partab"] = pd.concat([old, pd.DataFrame(new, columns=["name", "value", "vary", "min", "max", "expr"])],
                                             ignore_index=True)
        for k_, r_ in targets:
            m = ptabs[k_].m
            m.setData(m.index(r_, list(m.df.columns).index("sigma2")), spec["expr"])

    def _model_cards(self, add, keys, fdirs, multi):
        """keys：参与拟合的数据（单数据集模式只有 1 个）；multi：联合拟合模式（路径表按数据集分标签页，参数表共享）"""
        from xafsmith import feff_wrap as xfeff, pipeline as pl
        from xafsmith.common import n_idp
        S = self.S
        data_k = keys[0]
        ids = {}                      # 数据 → 数据集 id（pipeline.safe(文件名)，重名加序号）
        for k in keys:
            base_ = pl.safe(Path(k).name) or "data"
            i_, n_ = base_, 2
            while i_ in ids.values():
                i_, n_ = f"{base_}_{n_}", n_ + 1
            ids[k] = i_
        dsum = "|".join(str(d) for d in fdirs)

        def tkey(k):
            return "pathtab_" + (ids[k] + "|" if multi else "") + dsum
        allp = pd.concat([xfeff.list_paths(d).assign(dir=str(d.relative_to(paths.ROOT))) for d in fdirs], ignore_index=True)
        # 2 拟合范围
        c2 = Card(T("2  拟合范围", "2  Fit range"))
        st = self.state.setdefault("range", dict(kmin=S.ft_par["kmin"], kmax=S.ft_par["kmax"], dk=S.ft_par["dk"], win="hanning",
                                                 kws=[1, 2, 3], rmin=1.0, rmax=3.0, space="r"))
        w = dict(kmin=W.num(st["kmin"], 0, 10, 0.1), kmax=W.num(st["kmax"], 3, 25, 0.1), dk=W.num(st["dk"], 0, 5, 0.1),
                 win=W.combo(["hanning", "kaiser", "sine"], st["win"]), kws=W.MultiSelect([1, 2, 3], st["kws"]),
                 rmin=W.num(st["rmin"], 0, 6, 0.05), rmax=W.num(st["rmax"], 0.5, 10, 0.05), space=W.combo(["r", "k", "q"], st["space"]))
        c2.add(W.fields(("kmin", w["kmin"]), ("kmax", w["kmax"]), ("dk", w["dk"]), (T("窗", "Window"), w["win"]), cols=4))
        c2.add(W.fields((T("k 权重", "k-weights"), w["kws"]), ("Rmin", w["rmin"]), ("Rmax", w["rmax"]),
                        (T("拟合空间", "Fit space"), w["space"]), cols=4))
        W.link_range(w["kmin"], w["kmax"], 0.5)          # kmin < kmax、Rmin < Rmax 自动联动
        W.link_range(w["rmin"], w["rmax"], 0.1)
        if multi:
            c2.add(W.label(T("这是所有数据集的共同范围；个别数据集要用不同的 k / R 范围，在下面“路径”里该数据集的标签页覆盖。",
                             "This is the common range for all datasets; to give one dataset a different k / R range, override it "
                             "on that dataset's tab under “Paths”."), "faint"))
        nid = W.label("", rich=True)
        c2.add(nid)
        add(c2)

        # 3 路径
        def default_rows():
            rows, shells = [], []
            for _, r in allp.iterrows():
                k_ = (r.label, r.nleg)
                sh = next((j for j, (k0, r0) in enumerate(shells) if k0 == k_ and abs(r.reff - r0) < 0.1), None)
                if sh is None:
                    shells.append((k_, r.reff))
                    sh = len(shells) - 1
                rows.append(dict(use=bool(sh == 0), label=f"{r.label}@{r.reff:.3f}", reff=r.reff, degen=r.degen, nleg=r.nleg,
                                 amp_ratio=r.amp_ratio, N=f"{r.degen:g}", s02="s02", e0="e0", deltar=f"dr{sh + 1}",
                                 sigma2=f"ss{sh + 1}", third="", dir=r.dir, file=r.file))
            return pd.DataFrame(rows)
        for k in keys:
            if tkey(k) not in self.state:
                src = self.state.get(tkey(keys[0])) if k != keys[0] else None      # 新数据集：复制第一个数据集当前的路径表
                self.state[tkey(k)] = src.copy() if src is not None else default_rows()
        c3 = Card(T("3  路径", "3  Paths"))
        c3.add(W.label(T("勾选使用；单击单元格即可修改。N 留空 = FEFF 简并度；N、s02、e0、deltar、sigma2 都可以写表达式（如 ss1*1.5）。",
                         "Tick to use; click a cell to edit. Empty N = FEFF degeneracy; N, s02, e0, deltar, sigma2 accept "
                         "expressions (e.g. ss1*1.5)."), "faint"))
        if multi:
            c3.add(W.label(T("同名参数在数据集之间共享；要各自独立就改名（如 ss1_300K）。",
                             "Parameters with the same name are shared between datasets; rename to make them independent "
                             "(e.g. ss1_300K)."), "faint"))
        def edit_sigma2(k):
            """B6：“σ² 模型…”——改路径表当前行的 sigma2 单元格，并在参数表里建所缺的 θ / 静态项参数。"""
            from .sigma2_dialog import Sigma2Dialog, current_sigma2_value
            df = ptabs[k].df()
            if not len(df):
                return
            r = ptabs[k].currentIndex().row()
            if not 0 <= r < len(df):
                used_ = df.index[df.use.astype(bool)]
                r = int(used_[0]) if len(used_) else 0
            row = df.iloc[r].to_dict()
            try:
                tnow = float(temps[k].text())
                tnow = tnow if tnow > 0 else None
            except ValueError:
                tnow = None
            pt = cur["tab"].df() if "tab" in cur else self.state.get("partab")
            dlg_ = Sigma2Dialog(self, row, tnow, current_sigma2_value(row["sigma2"], pt), multi=multi)
            if not dlg_.exec():
                return
            self._apply_sigma2(dlg_.spec(), k, r, keys, ptabs, cur)
            if dlg_.spec()["kind"] != "free" and not str(temps[k].text()).strip():
                W.toast(self, T("已写入 σ² 模型。该数据集还没有温度：请填写“温度 (K)”，否则无法拟合。",
                                "σ² model written. This dataset has no temperature yet: fill in “Temperature (K)”, "
                                "otherwise the fit cannot run."), "warn")

        ptabs, over, temps = {}, {}, {}
        for k in keys:
            # B6：温度（K），空 = 模型里不写 temperature；σ² 模型（sigma2_debye / sigma2_eins）与 tempK 用它
            temps[k] = W.text(str(self.state.get("temp_" + ids[k], "")), T("不写", "not set"))
            temps[k].setMaximumWidth(120)
            temps[k].setToolTip(T("测量温度（K）。σ² 写成 sigma2_debye(tempK, thD) 时，tempK 取这里的值；空 = 模型里不写 temperature。",
                                  "Measurement temperature (K). In sigma2_debye(tempK, thD), tempK takes this value; empty = no "
                                  "temperature in the model."))
            temps[k].textChanged.connect(lambda s_, k=k: self.state.__setitem__("temp_" + ids[k], s_.strip()))
            ptab = W.Table(self.state[tkey(k)], editable=["use", "label", "N", "s02", "e0", "deltar", "sigma2", "third"],
                           bools=["use"], max_height=280, click_edit=True)
            ptab.hide_cols("file")
            ptabs[k] = ptab
        # B6：勾选“使用 σ² 温度模型”才显示温度框与“σ² 模型…”按钮；不勾 = 模型里不写 temperature
        def uses_tmodel():
            return any(_TMODEL_RE.search(str(v)) for k_ in keys for v in (ptabs[k_].df().get("sigma2", []) if k_ in ptabs else []))
        tm_on = bool(self.state.get("use_tmodel")) or uses_tmodel()
        tcheck = W.check(T("使用 σ² 温度模型（Debye / Einstein：多个温度共用一个 θ）",
                           "Use a σ² temperature model (Debye / Einstein: one θ shared by all temperatures)"), tm_on)
        tcheck.setToolTip(T("一般不用勾。只有同一样品在不同温度下测量、想用一个 θ 描述 σ² 随温度的变化时才用。",
                            "Usually leave unticked. Use it only for one sample measured at several temperatures, "
                            "to describe how σ² changes with temperature by a single θ."))
        trows = {k: self._temp_row(temps[k], edit_sigma2, k) for k in keys}
        for r_ in trows.values():
            r_.setVisible(tm_on)

        def on_tcheck(on):
            self.state["use_tmodel"] = bool(on)
            for r_ in trows.values():
                r_.setVisible(bool(on))
        tcheck.toggled.connect(on_tcheck)
        c3.add(tcheck)
        if not multi:
            c3.add(trows[data_k])
            c3.add(ptabs[data_k])
        else:
            pages_ = []
            for k in keys:
                ov0 = self.state.get("over_" + ids[k], {})
                over[k] = {f_: W.text(str(ov0.get(f_, "")), T("同共同范围", "common")) for f_ in ("kmin", "kmax", "rmin", "rmax")}
                others = [k2 for k2 in keys if k2 != k]

                def copy_to_others(k=k, others=others):
                    for k2 in others:
                        self.state[tkey(k2)] = ptabs[k].df().copy()
                    W.toast(self, T(f"已把 {ids[k]} 的路径表复制到其他 {len(others)} 个数据集",
                                    f"Copied the path table of {ids[k]} to the other {len(others)} dataset(s)"))
                    self.refresh()
                ow = over[k]
                col = W.vbox(trows[k],
                             ptabs[k],
                             W.label(T("覆盖拟合范围（留空 = 用上面“拟合范围”的共同值）",
                                       "Override the fit range (empty = the common range above)"), "faint"),
                             W.fields(("kmin", ow["kmin"]), ("kmax", ow["kmax"]), ("Rmin", ow["rmin"]), ("Rmax", ow["rmax"]), cols=4),
                             *([W.hbox(W.button(T("把本页路径表复制到其他数据集", "Copy this path table to the other datasets"),
                                                slot=copy_to_others), None)] if others else []))
                pages_.append((ids[k], col))
            c3.add(W.tabs(*pages_, state=self.state, key="pathtab_sel"))
        add(c3)
        # 4 参数
        c4 = Card(T("4  参数", "4  Parameters"))
        c4.add(W.label(T("vary 不勾 = 固定；expr 非空 = 约束。value 可输入任意位小数；拟合后可在右侧点“采纳拟合值到参数”。",
                         "Untick vary = fixed; non-empty expr = constrained. Values take any number of decimals; after a fit, "
                         "“Use fitted values as start” copies the results here."), "faint"))
        if multi:
            c4.add(W.label(T("一张共享参数表：名字取自所有数据集已勾选的路径。",
                             "One shared table: names come from the ticked paths of all datasets."), "faint"))
        holder = W.vbox()
        c4.add(holder)
        nv = W.label("", rich=True)
        c4.add(nv)
        rcur = self._restraint_section(c4)
        add(c4)
        defaults = {"s02": (0.85, True, 0.3, 1.5), "e0": (0.0, True, -15, 15)}
        cur = {}
        self._ptab = cur

        def names_used():
            """（参数名并集, {数据: 已勾选路径表}）"""
            out, used_by = [], {}
            for k in keys:
                used = ptabs[k].df()
                used = used[used.use.astype(bool)]
                used_by[k] = used
                for _, r in used.iterrows():
                    for col in ("N", "s02", "e0", "deltar", "sigma2", "third"):
                        for t in idents(r[col]):
                            if t not in out:
                                out.append(t)
            return out, used_by

        def rebuild_params():
            for k in keys:
                self.state[tkey(k)] = ptabs[k].df()
            old = self.state.get("partab", pd.DataFrame(columns=["name", "value", "vary", "min", "max", "expr"]))
            if "tab" in cur:
                t = cur["tab"].df()
                old = pd.concat([old[~old.name.isin(t.name)], t], ignore_index=True)
                self.state["partab"] = old
            names, _ = names_used()
            rows = []
            for n in names:
                if n in set(old.name):
                    rows.append(old[old.name == n].iloc[0].to_dict())
                else:
                    v, vary, lo, hi = defaults.get(n, (300.0, True, 50.0, 2000.0) if n.startswith(("thD", "thE")) else
                                                   (0.0, True, None, None) if n.startswith("ss0_") else
                                                   (0.003, True, 0.0, 0.05) if n.startswith("ss") else
                                                   (0.0, True, -0.5, 0.5) if n.startswith("dr") else (1.0, True, None, None))
                    rows.append(dict(name=n, value=v, vary=vary, min=lo, max=hi, expr=""))
            df = pd.DataFrame(rows, columns=["name", "value", "vary", "min", "max", "expr"])
            for c_ in ("value", "min", "max"):
                df[c_] = pd.to_numeric(df[c_], errors="coerce").astype(float)
            df["expr"] = df["expr"].fillna("").astype(object)
            df["vary"] = df["vary"].astype(bool)
            W._clear_layout(holder.layout())
            t = W.Table(df, editable=["value", "vary", "min", "max", "expr"], bools=["vary"], max_height=300, click_edit=True,
                        decimals=6)
            t.edited.connect(count)
            holder.layout().addWidget(t)
            cur["tab"] = t
            count()

        def over_vals(k):
            """该数据集的覆盖范围：({键: 数值}, 无法识别的键)"""
            vals, bad = {}, []
            for f_, wd in over[k].items():
                txt = wd.text().strip()
                if not txt:
                    continue
                try:
                    vals[f_] = float(txt)
                except ValueError:
                    bad.append(f_)
            return vals, bad

        def eff_range(k):
            r = {f_: st[f_] for f_ in ("kmin", "kmax", "rmin", "rmax")}
            if multi:
                r.update(over_vals(k)[0])
            return r

        def count():
            for k_ in ("kmin", "kmax", "dk", "rmin", "rmax"):
                st[k_] = w[k_].value()
            st.update(win=w["win"].value(), kws=w["kws"].value(), space=w["space"].value())
            if multi:
                for k in keys:
                    self.state["over_" + ids[k]] = {f_: wd.text().strip() for f_, wd in over[k].items() if wd.text().strip()}
                    for f_, wd in over[k].items():
                        wd.setPlaceholderText(f"{st[f_]:g}")
                nis = [n_idp(**eff_range(k)) for k in keys]
                ni = float(sum(nis))
                nid.setText(T(f"Σ N_idp = <b>{ni:.1f}</b>（各数据集 " + "、".join(f"{ids[k]}: {x:.1f}" for k, x in zip(keys, nis))
                              + f"）；变量数建议 ≤ Σ N_idp/2 = <b>{ni / 2:.1f}</b>",
                              f"Σ N_idp = <b>{ni:.1f}</b> (datasets: " + ", ".join(f"{ids[k]}: {x:.1f}" for k, x in zip(keys, nis))
                              + f"); keep variables ≤ Σ N_idp/2 = <b>{ni / 2:.1f}</b>"))
            else:
                ni = n_idp(st["kmin"], st["kmax"], st["rmin"], st["rmax"])
                nid.setText(T(f"N_idp = <b>{ni:.1f}</b>；变量数建议 ≤ N_idp/2 = <b>{ni / 2:.1f}</b>",
                              f"N_idp = <b>{ni:.1f}</b>; keep variables ≤ N_idp/2 = <b>{ni / 2:.1f}</b>"))
            if "tab" in cur:
                t = cur["tab"].df()
                n = int(((t.vary.astype(bool)) & (t.expr.fillna("").astype(str).str.strip() == "")).sum())
                col = C["warn"] if n > ni / 2 else C["text2"]
                nm = "Σ N_idp/2" if multi else "N_idp/2"
                nv.setText(f'<span style="color:{col}">' + T(f"变量数 = {n}（{nm} = {ni / 2:.1f}）", f"Variables = {n} ({nm} = {ni / 2:.1f})")
                           + "</span>")
        for k in keys:
            ptabs[k].edited.connect(rebuild_params)
        for k_ in ("kmin", "kmax", "dk", "rmin", "rmax"):
            w[k_].valueChanged.connect(lambda *_: count())
        for k_ in ("win", "space"):
            w[k_].currentIndexChanged.connect(lambda *_: count())
        w["kws"].changed.connect(lambda *_: count())
        for k in keys:
            for wd in over.get(k, {}).values():
                wd.textChanged.connect(lambda *_: count())
        rebuild_params()
        # 拟合按钮栏（固定在左下角，不随左侧滚动）
        names, used_by = names_used()
        mkey = "mname_multi" if multi else "mname_" + data_k
        mname = W.text(self.state.get(mkey, ("+".join(ids[k] for k in keys) + "_joint") if multi
                                      else f"{Path(data_k).name}_{len(used_by[data_k])}paths"))
        mname.textChanged.connect(lambda s: self.state.__setitem__(mkey, s))
        btn = W.button(T("拟合", "Fit"), primary=True, icon_name="play", tip="Ctrl+Enter")
        btn.setMinimumWidth(110)
        W.bind_task(btn, "fit", "fit")

        def go():
            if W.task_running(excl="fit"):
                return
            count()
            _, used_by = names_used()
            bad_ds = [ids[k] for k in keys if not len(used_by[k])]
            if bad_ds:
                W.toast(self, T("至少勾选一条路径" + (f"（数据集 {', '.join(bad_ds)} 没有勾选）" if multi else ""),
                                "Tick at least one path" + (f" (none ticked for {', '.join(bad_ds)})" if multi else "")), "warn")
                return
            for k in keys:
                if multi and over_vals(k)[1]:
                    W.toast(self, T(f"数据集 {ids[k]} 的覆盖范围里有无法识别的数字：{', '.join(over_vals(k)[1])}",
                                    f"Unreadable number in the range override of {ids[k]}: {', '.join(over_vals(k)[1])}"), "warn")
                    return
            t = cur["tab"].df()
            self.state["partab"] = pd.concat([self.state.get("partab", t.iloc[0:0])[lambda d: ~d.name.isin(t.name)], t],
                                             ignore_index=True)
            params = {}
            for _, r in t.iterrows():
                if isinstance(r.expr, str) and r.expr.strip():
                    params[r["name"]] = {"expr": r.expr}
                else:
                    params[r["name"]] = {"value": float(r.value), "vary": bool(r.vary),
                                         "min": None if pd.isna(r["min"]) else float(r["min"]),
                                         "max": None if pd.isna(r["max"]) else float(r["max"])}

            restraints = self._restraints_from_table(rcur)
            if restraints is False:
                return
            tvals = {}
            if not tcheck.isChecked() and uses_tmodel():
                W.toast(self, T("路径 σ² 用了温度模型（sigma2_debye / sigma2_eins / tempK）：请勾选“使用 σ² 温度模型”并填温度，"
                                "或把 σ² 改回普通参数。",
                                "A path σ² uses a temperature model (sigma2_debye / sigma2_eins / tempK): tick “Use a σ² "
                                "temperature model” and fill in the temperature, or change σ² back to a plain parameter."), "warn")
                return
            for k in (keys if tcheck.isChecked() else []):
                txt = temps[k].text().strip()
                if not txt:
                    continue
                try:
                    tv = float(txt)
                    if not (tv > 0 and tv < float("inf")):
                        raise ValueError
                except ValueError:
                    W.toast(self, T(f"数据集 {ids[k]} 的温度应是大于 0 的数字（K）：{txt!r}",
                                    f"Temperature of {ids[k]} must be a number > 0 (K): {txt!r}"), "warn")
                    return
                tvals[k] = tv

            def mk_paths(used):
                mpaths = []
                for _, r in used.iterrows():
                    d = dict(file=r.file, label=r.label, s02=r.s02, e0=r.e0, deltar=r.deltar, sigma2=r.sigma2)
                    if str(r.N).strip():
                        d["N"] = str(r.N)
                    if isinstance(r.third, str) and r.third.strip():
                        d["third"] = r.third
                    mpaths.append(d)
                return mpaths
            rng = dict(kmin=st["kmin"], kmax=st["kmax"], dk=st["dk"], window=st["win"], kweight=st["kws"] or [2],
                       rmin=st["rmin"], rmax=st["rmax"], fitspace=st["space"])
            extra = dict(restraints=restraints) if restraints else {}        # 表为空 → 模型不写 restraints 键
            if multi:
                dsl = []
                for k in keys:
                    d = dict(id=ids[k], sample=k)
                    d.update(over_vals(k)[0])
                    if k in tvals:
                        d["temperature"] = tvals[k]
                    d["paths"] = mk_paths(used_by[k])
                    dsl.append(d)
                model = dict(name=mname.text(), params=params, **rng, datasets=dsl, norm=dict(S.norm_par), bkg=dict(S.bkg_par), **extra)
                groups = {ids[k]: S.groups[k] for k in keys}
            else:
                model = dict(name=mname.text(), sample=data_k, **rng, params=params, paths=mk_paths(used_by[data_k]),
                             norm=dict(S.norm_par), bkg=dict(S.bkg_par), **extra)
                if data_k in tvals:
                    model["temperature"] = tvals[data_k]
                groups = S.groups[data_k]

            def done(fit):
                S.fits.append(fit)
                S.emit("fits")
                self._show_result(fit)          # 只更新右侧：左侧的设置与滚动位置不变
                self.ack()
            W.run_task(self, lambda: run_model(S, model, groups), done, T("拟合中…", "Fitting…"), btn,
                       key="fit", excl="fit")
        btn.clicked.connect(go)
        self._fit_go = go
        self._bar.addWidget(W.label(T("模型名", "Model name"), "faint"))
        self._bar.addWidget(mname, 1)
        self._bar.addWidget(btn)
