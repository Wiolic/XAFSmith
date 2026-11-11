"""EXAFS 拟合页面。"""

from __future__ import annotations

from xafsmith import logs
import json
from pathlib import Path
import pandas as pd
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QWidget
from xafsmith import paths
from ... import widgets as W
from ...state import feff_dirs, has_chi, idents, load_model, run_model, saved_models
from ...theme import C
from ...widgets import T, Banner, Card, Page

from .guides import show_fit_guide
from .fit_view import FitView


class FitPage(Page):
    """左右分栏：左侧依次设置数据、范围、路径、参数（“拟合”按钮固定在左下角），右侧始终显示最近一次拟合。
    改参数 → 拟合 → 看结果 → 再改，全程不用上下翻页。"""
    title_zh, title_en, icon_name = "EXAFS 拟合", "EXAFS fitting", "fit"
    fill = True
    max_width = 100000

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
                                      slot=lambda: show_fit_guide(self))])
        sp = QSplitter(Qt.Orientation.Horizontal)
        sp.setChildrenCollapsible(False)
        sp.setHandleWidth(10)
        # 左：设置（可滚动）+ 固定的拟合按钮栏
        left = QWidget()
        lv = W.QVBoxLayout(left)
        lv.setContentsMargins(0, 0, 0, 0)
        lv.setSpacing(8)
        lsa, lcol = self._scroll()
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
        add(self._saved())
        cands = [k for k, g in S.groups.items() if has_chi(g)]
        dirs = feff_dirs()
        if not cands or not dirs:
            add(Banner("info", T("需要：已载入并算出 χ(k) 的数据（载入谱 / χ(k) 与 FT）与 FEFF 计算（FEFF 路径）。",
                                 "Needs data with χ(k) (Load spectra / χ(k) & FT) and a FEFF calculation (FEFF paths).")))
        else:
            c1 = Card(T("1  数据与 FEFF", "1  Data and FEFF"))
            data = W.combo(cands, self.state.get("data"))
            g = S.groups[data.value()]
            tag = f"_{g.element}{g.edge}"
            match = [d for d in dirs if tag in str(d.relative_to(paths.FEFF))]
            fd_key = "fdirs_" + data.value()
            fdirs = W.MultiSelect(dirs, [Path(x) for x in self.state.get(fd_key, [str(d) for d in match[:1]])],
                                  T("选择 FEFF 目录（可多选：多物相 / 多位点）", "FEFF folders (several: phases / sites)"),
                                  fmt=lambda p: str(p.relative_to(paths.ROOT)))
            data.currentIndexChanged.connect(lambda *_: (self.state.__setitem__("data", data.value()), self.refresh()))
            fdirs.changed.connect(lambda v: (self.state.__setitem__(fd_key, [str(x) for x in v]), self.refresh()))
            c1.add(W.field(T("数据", "Data"), data))
            c1.add(W.field(T("FEFF 目录", "FEFF folders"), fdirs))
            add(c1)
            if fdirs.value():
                self._model_cards(add, data.value(), fdirs.value())
            else:
                add(Banner("info", T("选择至少一个 FEFF 目录。", "Choose at least one FEFF folder.")))
        lcol.addStretch(1)
        self._show_result(S.fits[-1] if S.fits else None)

    def _scroll(self):
        from PySide6.QtWidgets import QScrollArea
        sa = QScrollArea()
        sa.setWidgetResizable(True)
        sa.setFrameShape(W.QFrame.Shape.NoFrame)
        sa.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        inner = QWidget()
        inner.setObjectName("page")
        col = W.QVBoxLayout(inner)
        col.setContentsMargins(2, 2, 10, 8)
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

        def upd():
            self.state["mf"] = mf.value()
            try:
                msmp = json.loads((paths.MODELS / mf.value()).read_text(encoding="utf-8-sig")).get("sample", "")
            except Exception:
                logs.log.warning("qt.pages.fitting.upd 出错（已忽略或已提示）", exc_info=True)
                msmp = ""
            meta_s = list(pl.load_meta().query("use != '0'")["sample"]) if pl.META.exists() else []
            opts = [o for o in dict.fromkeys([msmp] + meta_s + list(S.groups)) if o]
            smp.set_options(opts, [msmp] if msmp in opts else [])
        mf.currentIndexChanged.connect(lambda *_: upd())
        upd()
        btn = W.button(T("运行", "Run"), primary=True, icon_name="play")

        def go():
            todo = smp.value() or [None]
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
            W.run_task(self, work, done, T("拟合中…", "Fitting…"), btn, progress=True)
        btn.clicked.connect(go)
        body.add(W.field(T("模型", "Model"), mf))
        body.add(W.hbox(W.field(T("样品", "Samples"), smp), W.vbox(None, btn), spacing=10))
        cl = W.collapsible(T(f"运行已保存的模型（models/ 中 {len(models)} 个）", f"Run a saved model ({len(models)} in models/)"), body,
                           expanded=self.state.get("saved_open", False))
        cl.findChild(W.QToolButton).toggled.connect(lambda on: self.state.__setitem__("saved_open", on))
        return cl

    def _model_cards(self, add, data_k, fdirs):
        from xafsmith import feff_wrap as xfeff
        from xafsmith.common import n_idp
        S = self.S
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
        nid = W.label("", rich=True)
        c2.add(nid)
        add(c2)
        # 3 路径
        key = "pathtab_" + "|".join(str(d) for d in fdirs)
        if key not in self.state:
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
            self.state[key] = pd.DataFrame(rows)
        c3 = Card(T("3  路径", "3  Paths"))
        c3.add(W.label(T("勾选使用；单击单元格即可修改。N 留空 = FEFF 简并度；N、s02、e0、deltar、sigma2 都可以写表达式（如 ss1*1.5）。",
                         "Tick to use; click a cell to edit. Empty N = FEFF degeneracy; N, s02, e0, deltar, sigma2 accept "
                         "expressions (e.g. ss1*1.5)."), "faint"))
        ptab = W.Table(self.state[key], editable=["use", "label", "N", "s02", "e0", "deltar", "sigma2", "third"],
                       bools=["use"], max_height=280, click_edit=True)
        ptab.hide_cols("file")
        c3.add(ptab)
        add(c3)
        # 4 参数
        c4 = Card(T("4  参数", "4  Parameters"))
        c4.add(W.label(T("vary 不勾 = 固定；expr 非空 = 约束。value 可输入任意位小数；拟合后可在右侧点“采纳拟合值到参数”。",
                         "Untick vary = fixed; non-empty expr = constrained. Values take any number of decimals; after a fit, "
                         "“Use fitted values as start” copies the results here."), "faint"))
        holder = W.vbox()
        c4.add(holder)
        nv = W.label("", rich=True)
        c4.add(nv)
        add(c4)
        defaults = {"s02": (0.85, True, 0.3, 1.5), "e0": (0.0, True, -15, 15)}
        cur = {}
        self._ptab = cur

        def names_used():
            used = ptab.df()
            used = used[used.use.astype(bool)]
            out = []
            for _, r in used.iterrows():
                for col in ("N", "s02", "e0", "deltar", "sigma2", "third"):
                    for t in idents(r[col]):
                        if t not in out:
                            out.append(t)
            return out, used

        def rebuild_params():
            self.state[key] = ptab.df()
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
                    v, vary, lo, hi = defaults.get(n, (0.003, True, 0.0, 0.05) if n.startswith("ss") else
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

        def count():
            for k_ in ("kmin", "kmax", "dk", "rmin", "rmax"):
                st[k_] = w[k_].value()
            st.update(win=w["win"].value(), kws=w["kws"].value(), space=w["space"].value())
            ni = n_idp(st["kmin"], st["kmax"], st["rmin"], st["rmax"])
            nid.setText(T(f"N_idp = <b>{ni:.1f}</b>；变量数建议 ≤ N_idp/2 = <b>{ni / 2:.1f}</b>",
                          f"N_idp = <b>{ni:.1f}</b>; keep variables ≤ N_idp/2 = <b>{ni / 2:.1f}</b>"))
            if "tab" in cur:
                t = cur["tab"].df()
                n = int(((t.vary.astype(bool)) & (t.expr.fillna("").astype(str).str.strip() == "")).sum())
                col = C["warn"] if n > ni / 2 else C["text2"]
                nv.setText(f'<span style="color:{col}">' + T(f"变量数 = {n}（N_idp/2 = {ni / 2:.1f}）", f"Variables = {n} (N_idp/2 = {ni / 2:.1f})")
                           + "</span>")
        ptab.edited.connect(rebuild_params)
        for k_ in ("kmin", "kmax", "dk", "rmin", "rmax"):
            w[k_].valueChanged.connect(lambda *_: count())
        for k_ in ("win", "space"):
            w[k_].currentIndexChanged.connect(lambda *_: count())
        w["kws"].changed.connect(lambda *_: count())
        rebuild_params()
        # 拟合按钮栏（固定在左下角，不随左侧滚动）
        names, used = names_used()
        mname = W.text(self.state.get("mname_" + data_k, f"{Path(data_k).name}_{len(used)}paths"))
        mname.textChanged.connect(lambda s: self.state.__setitem__("mname_" + data_k, s))
        btn = W.button(T("拟合", "Fit"), primary=True, icon_name="play", tip="Ctrl+Enter")
        btn.setMinimumWidth(110)

        def go():
            if not btn.isEnabled():
                return
            count()
            _, used = names_used()
            if not len(used):
                W.toast(self, T("至少勾选一条路径", "Tick at least one path"), "warn")
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
            mpaths = []
            for _, r in used.iterrows():
                d = dict(file=r.file, label=r.label, s02=r.s02, e0=r.e0, deltar=r.deltar, sigma2=r.sigma2)
                if str(r.N).strip():
                    d["N"] = str(r.N)
                if isinstance(r.third, str) and r.third.strip():
                    d["third"] = r.third
                mpaths.append(d)
            model = dict(name=mname.text(), sample=data_k, kmin=st["kmin"], kmax=st["kmax"], dk=st["dk"], window=st["win"],
                         kweight=st["kws"] or [2], rmin=st["rmin"], rmax=st["rmax"], fitspace=st["space"], params=params,
                         paths=mpaths, norm=dict(S.norm_par), bkg=dict(S.bkg_par))

            def done(fit):
                S.fits.append(fit)
                S.emit("fits")
                self._show_result(fit)          # 只更新右侧：左侧的设置与滚动位置不变
            W.run_task(self, lambda: run_model(S, model, S.groups[data_k]), done, T("拟合中…", "Fitting…"), btn)
        btn.clicked.connect(go)
        self._fit_go = go
        self._bar.addWidget(W.label(T("模型名", "Model name"), "faint"))
        self._bar.addWidget(mname, 1)
        self._bar.addWidget(btn)
