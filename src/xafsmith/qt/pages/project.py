"""项目：首页（打开 / 新建、流程进度、输出）、数据登记、一键处理（含处理参数）"""
from __future__ import annotations

from xafsmith import logs
import shutil
from pathlib import Path

import pandas as pd
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFileDialog, QListWidget, QListWidgetItem

from xafsmith import paths
from .. import widgets as W
from ..state import is_project, load_cfg, recent_projects, save_cfg
from ..theme import C, icon
from ..widgets import T, Banner, Card, Page


class HomePage(Page):
    """打开或新建项目（侧栏“打开 / 新建项目”进入；不在导航中显示）。流程进度与本项目信息在侧栏“流程与本项目”的悬浮窗口中。"""
    title_zh, title_en, icon_name = "打开或新建项目", "Open or create a project", "home"

    def title(self):
        return T("打开或新建项目", "Open or create a project") if is_project() else T("欢迎使用 XAFSmith", "Welcome to XAFSmith")

    def focus_open(self):
        self.refresh()

    def build(self):
        if not is_project():
            self.header(T("可连接 AI 助手的同步辐射 XAFS 分析软件。打开一个项目文件夹，或新建一个。",
                          "Agent-ready synchrotron XAFS analysis. Open a project folder or create a new one."))
        else:
            self.header(T(f"当前项目：{paths.ROOT.name}。流程进度与本项目信息：把鼠标移到右上角“流程与本项目”。",
                          f"Current project: {paths.ROOT.name}. Workflow and project info: hover “Workflow & project” at the top right."),
                        actions=[W.button(T("打开当前项目文件夹", "Open current project folder"), icon_name="folder",
                                          slot=lambda: W.open_folder(paths.ROOT), tip=str(paths.ROOT))])
        self.add(self._open_card_w(True))

    # ---------------------------------------------------------------- 打开 / 新建
    def _open_card_w(self, expanded):
        card = Card(T("打开或新建项目", "Open or create a project"))
        self._open_card = card
        rec = recent_projects()
        if rec:
            lw = QListWidget()
            for p in rec:
                it = QListWidgetItem(icon("folder", C["text2"], 16), f"{Path(p).name}    —    {p}")
                it.setData(Qt.ItemDataRole.UserRole, p)
                lw.addItem(it)
            lw.setFixedHeight(min(260, 34 * len(rec) + 12))
            lw.itemDoubleClicked.connect(lambda it: self.app.open_project(it.data(Qt.ItemDataRole.UserRole)))
            card.add(W.label(T("最近的项目（双击打开）", "Recent projects (double-click to open)"), "faint"))
            card.add(lw)
        path = W.text(self.state.get("prj_path", ""), T("项目文件夹路径", "Project folder path"))
        path.textChanged.connect(lambda s: self.state.__setitem__("prj_path", s))

        def browse():
            d = QFileDialog.getExistingDirectory(self, T("选择项目文件夹", "Choose project folder"),
                                                 path.text() or str(Path.home()))
            if d:
                path.setText(str(Path(d)))

        def open_():
            f = path.text().strip()
            if not f:
                return
            if paths.is_project(f):
                self.app.open_project(f)
            else:
                W.toast(self, T(f"{f} 中没有 xafsmith.json，不是项目；可以点“新建项目”。",
                                f"{f} has no xafsmith.json; click “Create project”."), "warn")

        def create():
            f = path.text().strip()
            if not f:
                return
            from xafsmith.cli import create_project
            create_project(f)
            self.app.open_project(f)
        card.add(W.hbox(path, W.button(T("浏览…", "Browse…"), icon_name="folder", slot=browse), spacing=8))
        card.add(W.hbox(W.button(T("打开", "Open"), slot=open_),
                        W.button(T("新建项目", "Create project"), primary=True, icon_name="plus", slot=create),
                        W.label(T("已有文件不会被覆盖", "Existing files are never overwritten"), "faint"), None))
        return card


class DataPage(Page):
    title_zh, title_en, icon_name = "数据登记", "Register data", "table"

    def build(self):
        from xafsmith import pipeline as pl
        self.header(T("原始数据放在 data/raw/<批次>/，每个批次带同批测量的单质参比（文件名含 foil / powder / metal）。原始文件只读。",
                      "Raw data go to data/raw/<batch>/, each batch with its elemental reference (file name containing "
                      "foil / powder / metal). Raw files are read-only."))
        # 添加文件
        up = Card(T("添加原始数据", "Add raw data"))
        batch = W.text(self.state.get("batch", "batch1" if W.en() else "批次1"))
        batch.textChanged.connect(lambda s: self.state.__setitem__("batch", s))

        def add_files():
            fs, _ = QFileDialog.getOpenFileNames(self, T("选择原始数据文件", "Choose raw data files"), str(Path.home()))
            if not fs:
                return
            d = paths.RAW / (batch.text().strip() or "batch1")
            d.mkdir(parents=True, exist_ok=True)
            copied, skipped, failed = [], [], []
            for f in fs:
                dst = d / Path(f).name
                if dst.exists():
                    skipped.append(dst.name)
                    continue
                try:
                    shutil.copy2(f, dst)
                    copied.append(dst.name)
                except Exception as ex:      # noqa: BLE001
                    logs.log.warning("qt.pages.project.add_files 出错（已忽略或已提示）", exc_info=True)
                    failed.append(f"{Path(f).name}: {ex}")
            meta, nreg = pl.scan_raw()           # 复制后直接登记
            pl.init_config(meta)
            msg = T(f"复制 {len(copied)} 个文件到 {paths.rel(d)}", f"Copied {len(copied)} files to {paths.rel(d)}")
            if skipped:
                msg += T(f"；{len(skipped)} 个同名文件已存在，未覆盖", f"; {len(skipped)} already there, not overwritten")
            msg += T(f"；登记新文件 {nreg} 个", f"; {nreg} new files registered")
            W.toast(self, msg, "err" if failed else "ok")
            for e in failed:
                W.toast(self, e, "err")
            self.refresh()

        def scan():
            meta, n = pl.scan_raw()
            cfg = pl.init_config(meta)
            W.toast(self, T(f"新增 {n} 行；吸收边 {list(cfg['edges'])}", f"{n} new rows; edges {list(cfg['edges'])}"))
            self.refresh()
        up.add(W.hbox(W.field(T("批次文件夹", "Batch folder"), batch),
                      W.vbox(None, W.button(T("选择文件，复制到批次并登记…", "Choose files, copy to batch and register…"),
                                            primary=True, icon_name="upload", slot=add_files)),
                      W.vbox(None, W.button(T("扫描 data/raw，登记新文件", "Scan data/raw and register new files"),
                                            icon_name="refresh", slot=scan,
                                            tip=T("用资源管理器直接把文件放进 data/raw 后，点这里登记",
                                                  "After copying files into data/raw with Explorer, click here to register them"))),
                      None, spacing=12))
        self.add(up)
        # meta.csv
        card = Card("data/meta.csv", actions=[W.button(T("打开 data 文件夹", "Open data folder"), icon_name="external",
                                                       slot=lambda: W.open_folder(paths.DATA))])
        if paths.META.exists():
            meta = pd.read_csv(paths.META, dtype=str, encoding="utf-8-sig").fillna("")
        else:
            meta = pd.DataFrame()
        if len(meta):
            card.add(W.label(T("双击单元格修改：sample（同名 = 合并）、role、use（0 = 不用，须写 note）、ref_file（校准参比）、note。",
                               "Double-click to edit: sample (same name = merged), role, use (0 = excluded, note required), "
                               "ref_file (calibration reference), note."), "faint"))
            refs = [""] + sorted(set(meta[meta.role == "reference"].file)) if "role" in meta else [""]
            editable = [c for c in meta.columns if c not in ("file", "edge_key", "time", "npts", "emax", "batch")]
            tab = W.Table(meta, editable=editable,
                          choices={"role": ["reference", "standard", "sample"], "use": ["1", "0"],
                                   "mode": ["trans", "fluo"], "ref_file": refs}, max_height=460)
            card.add(tab)

            def save():
                tab.df().to_csv(paths.META, index=False, encoding="utf-8-sig")
                W.toast(self, T("已保存 meta.csv。改了 ref_file 或 role 后请在“校准与处理”中重新校准。",
                                "meta.csv saved. After changing ref_file or role, recalibrate under “Calibrate & process”."))
            card.add(W.hbox(None, W.button(T("保存 meta.csv", "Save meta.csv"), primary=True, icon_name="save", slot=save)))
        else:
            card.add(Banner("info", T("meta.csv 还是空的：添加数据后点“扫描 data/raw”。",
                                      "meta.csv is empty: add data, then click “Scan data/raw”.")))
        self.add(card)
        # 检查
        chk = Card(T("按数据标准检查", "Validate against the data standard"))
        out = W.vbox()

        def validate():
            from xafsmith import schema
            rep = schema.validate(structures=True)
            tab = rep.table()
            W._clear_layout(out.layout())
            out.layout().addWidget(Banner("err" if rep.n_err else "ok",
                                          T(f"{rep.n_err} 个错误，{len(tab) - rep.n_err} 个警告",
                                            f"{rep.n_err} errors, {len(tab) - rep.n_err} warnings")))
            if len(tab):
                out.layout().addWidget(W.Table(tab))
        chk.add(W.hbox(W.label(T("文件是否存在、每条谱是否有参比、参数是否完整、模型路径是否存在。",
                                 "Files present, a reference for every spectrum, complete parameters, model paths present."),
                               "muted"), None, W.button(T("运行检查", "Run check"), icon_name="shield", slot=validate)))
        chk.add(out)
        self.add(chk)


class BatchPage(Page):
    title_zh, title_en, icon_name = "校准与处理", "Calibrate & process", "bolt"

    def build(self):
        from xafsmith import pipeline as pl
        self.header(T("每条吸收边一套参数，所有样品共用；保存后按顺序运行 ① ② ③。",
                      "One parameter set per edge, shared by all samples; save, then run ① ② ③ in order."))
        cfg = pl.load_config()
        edges = list(cfg.get("edges", {}))
        if not edges:
            self.add(Banner("info", T("还没有吸收边：先在“数据登记”中扫描 data/raw。",
                                      "No edges yet: scan data/raw under “Register data” first.")))
            return
        self.add(self._params(cfg, edges))
        run = Card(T("批量运行", "Batch run"))
        out = W.vbox()
        self._out = out

        def show(widgets):
            W._clear_layout(out.layout())
            for w in widgets:
                out.layout().addWidget(w)

        b1 = W.button(T("① 质量检查", "① Quality check"), icon_name="shield")
        b2 = W.button(T("② 按参比校准", "② Calibrate with references"), icon_name="target")
        b3 = W.button(T("③ 处理全部样品", "③ Process all samples"), primary=True, icon_name="play")

        def qc_done(df):
            cols = [c for c in ["label", "mode", "e0", "edge_step_mu", "n_glitches", "glitch_E", "i0_drops", "k_snr3",
                                "self_abs_risk", "error"] if c in df]
            self.S.qc = df
            show([W.label(f"→ {paths.rel(paths.QC_CSV)}", "faint"), W.Table(df[cols], max_height=520)])

        def cal_done(res):
            self.S.calib = res
            self.S.emit("calib")
            rows = pd.DataFrame([dict(参比=k, 吸收边=v["edge_key"], 批次=v.get("batch", ""), E0_meas=round(v["e0_meas"], 2),
                                      E_table=v["e_table"], ΔE=round(v["delta_e"], 3), 谱数=len(v["time_gap_hours"]))
                                 for k, v in res.items()])
            if W.en():
                rows.columns = ["Reference", "Edge", "Batch", "E0_meas", "E_table", "ΔE", "Spectra"]
            ws = [W.Table(rows)]
            miss = pl.load_meta().query("ref_file == ''")
            if len(miss):
                ws.insert(0, Banner("warn", T(f"{len(miss)} 条谱没有参比，不能处理：", f"{len(miss)} spectra have no reference: ")
                                    + ", ".join(miss.file)))
            show(ws)

        def proc_done(r):
            df, _ = r
            show([W.label(T(f"→ {paths.rel(paths.PROC)}/、{paths.rel(paths.FIGS)}/；之后在“载入谱”中按样品载入查看",
                            f"→ {paths.rel(paths.PROC)}/, {paths.rel(paths.FIGS)}/; then load samples under “Load spectra”"),
                          "faint"), W.Table(df, max_height=520)])
        b1.clicked.connect(lambda: W.run_task(self, lambda progress: pl.run_qc(progress=progress), qc_done, T("质量检查中…", "Checking…"), b1,
                                              progress=True))
        b2.clicked.connect(lambda: W.run_task(self, lambda progress: pl.run_calib(pl.load_config(), pl.load_meta(), progress=progress),
                                              cal_done, T("校准中…", "Calibrating…"), b2, progress=True))
        b3.clicked.connect(lambda: W.run_task(self, lambda progress: pl.process_all(progress=progress), proc_done,
                                              T("校准 → 归一化 → 合并 → χ(k) → FT …", "Calibrate → normalize → merge → χ(k) → FT …"), b3,
                                              progress=True))
        run.add(W.hbox(b1, b2, b3, None))
        run.add(out)
        self.add(run)

    def _params(self, cfg, edges):
        ek = self.state.get("edge", edges[0])
        ek = ek if ek in edges else edges[0]
        c = cfg["edges"][ek]
        sel = W.combo(edges, ek)

        def switch():
            self.state["edge"] = sel.value()
            self.refresh()
        sel.currentIndexChanged.connect(lambda *_: switch())
        card = Card(T("处理参数", "Processing parameters"), actions=[sel])
        card.add(W.label(T(f"{c['element']} {c['edge']}，表值 E0 = {c.get('e_table')} eV（{c.get('e_table_source', '')}）",
                           f"{c['element']} {c['edge']}, tabulated E0 = {c.get('e_table')} eV ({c.get('e_table_source', '')})"),
                         "muted"))
        el = W.text(", ".join(c.get("elements_in_sample", [c["element"]])))
        card.add(W.field(T("样品中的全部元素（逗号分隔，用于干扰边检查与 k 上限）",
                           "All elements in the sample (comma-separated; for interfering edges and the k limit)"), el))
        n, b, f = c["norm"], c["bkg"], c["ft"]
        pre1, pre2 = W.num(n["pre1"], step=5), W.num(n["pre2"], step=5)
        norm1, norm2 = W.num(n["norm1"], step=10), W.num(n.get("norm2") or -10, step=10)
        nnorm = W.combo([1, 2, 3], int(n["nnorm"]))
        sm = W.num(n.get("smooth_ev", 1.0), 0, 10, 0.5)
        card.add(W.label(T("归一化", "Normalization"), "h3"))
        card.add(W.fields(("pre1", pre1), ("pre2", pre2), ("norm1", norm1), (T("norm2（≤0 距末端）", "norm2 (≤0: from end)"), norm2),
                          ("nnorm", nnorm), (T("E0 平滑 σ", "E0 smoothing σ"), sm)))
        rbkg = W.num(b["rbkg"], 0.3, 4, 0.1)
        bkw = W.combo([1, 2, 3], int(b["kweight"]))
        kmin, kmax, dk = W.num(f["kmin"], 0, 30, 0.1), W.num(f["kmax"], 0, 30, 0.1), W.num(f["dk"], 0, 5, 0.1)
        wins = ["hanning", "kaiser", "sine"]
        win = W.combo(wins, f["window"] if f["window"] in wins else "hanning")
        fkw = W.combo([1, 2, 3], int(f["kweight"]))
        card.add(W.label(T("背景扣除与傅里叶变换", "Background removal & Fourier transform"), "h3"))
        card.add(W.fields(("rbkg", rbkg), (T("背景 k 权重", "bkg k-weight"), bkw), ("kmin", kmin), ("kmax", kmax),
                          ("dk", dk), (T("窗", "Window"), win), (T("FT k 权重", "FT k-weight"), fkw)))
        s0 = c.get("s02_recommended", {})
        s0v, s0e = W.num(s0.get("value", 0.8), 0, 3, 0.01, 3), W.num(s0.get("err", 0.0), 0, 3, 0.01, 3)
        s0s = W.text(s0.get("source", ""))
        card.add(W.label(T("S0²（标样上拟合得到，样品拟合时固定）", "S0² (from the standard; fixed for samples)"), "h3"))
        card.add(W.fields(("S0²", s0v), (T("误差", "Error"), s0e), (T("来源", "Source"), s0s)))

        def save():
            cfg2 = load_cfg()
            c2 = cfg2["edges"][ek]
            c2["elements_in_sample"] = [x.strip() for x in el.text().split(",") if x.strip()]
            c2["norm"].update(pre1=pre1.value(), pre2=pre2.value(), norm1=norm1.value(), norm2=norm2.value(),
                              nnorm=nnorm.value(), smooth_ev=sm.value())
            c2["bkg"].update(rbkg=rbkg.value(), kweight=bkw.value())
            c2["ft"].update(kmin=kmin.value(), kmax=kmax.value(), dk=dk.value(), window=win.value(), kweight=fkw.value())
            c2["s02_recommended"] = dict(s0, value=s0v.value(), err=s0e.value(), source=s0s.text())
            save_cfg(cfg2)
            W.toast(self, T("已保存到 xafsmith.json；改动后请重新“③ 处理全部样品”。",
                            "Saved to xafsmith.json; run “③ Process all samples” again."))
        card.add(W.hbox(None, W.button(T("保存参数", "Save parameters"), primary=True, icon_name="save", slot=save)))
        return card
