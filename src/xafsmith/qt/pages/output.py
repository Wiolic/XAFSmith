"""结果与导出：报告导出、图片导出（含 Origin 工程）、方法导出；工具：制样指导、吸收边查询、AI 助手、使用指南"""
from __future__ import annotations

from xafsmith import logs
import datetime
import re
from pathlib import Path

import pandas as pd
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QGridLayout, QPushButton, QWidget

from xafsmith import paths
from .. import widgets as W
from ..state import fit_label, has_chi, load_cfg, plain_rc, save_cfg, save_fit
from ..theme import C
from ..widgets import T, Banner, Card, Page


# ============================================================================= 报告导出
class SummaryPage(Page):
    title_zh, title_en, icon_name = "报告导出", "Report export", "doc"

    def build(self):
        from xafsmith import summary
        S = self.S
        self.header(T("把项目中已保存的全部结果整理成一个 Excel 工作簿和一份带图的 HTML 报告（图为缩略图，点击放大、滚轮缩放）。",
                      "Collect every saved result into one Excel workbook and an HTML report (figures as thumbnails: click to "
                      "enlarge, wheel to zoom)."))
        card = Card(T("生成报告", "Build report"))
        if S.fits:
            card.add(Banner("info", T(f"本项目当前有 {len(S.fits)} 个拟合；只有保存过的拟合会进入报告。",
                                      f"{len(S.fits)} fits open; only saved fits are included.")))
        btn = W.button(T("生成报告", "Build report"), primary=True, icon_name="play")

        def save_session_fits():
            for f in S.fits:
                save_fit(f)
            W.toast(self, T("已保存", "Saved"))

        def go():
            def work():
                with plain_rc():
                    return str(summary.build())
            W.run_task(self, work, lambda d: (S.extra.__setitem__("summary_dir", d), self.refresh()), T("整理中…", "Building…"), btn)
        btn.clicked.connect(go)
        row = [None, btn]
        if S.fits:
            row.insert(0, W.button(T("先保存当前的全部拟合", "Save all open fits first"), icon_name="save",
                                   slot=lambda: W.wait_cursor(save_session_fits)))
        card.add(W.hbox(*row))
        d = S.extra.get("summary_dir")
        if d and (Path(d) / "汇总.xlsx").exists():
            out = Path(d)
            card.add(Banner("ok", T(f"已生成：{paths.rel(out)}", f"Built: {paths.rel(out)}")))
            card.add(W.hbox(W.button(T("打开报告文件夹", "Open report folder"), icon_name="external", slot=lambda: W.open_folder(out)),
                            W.button(T("另存 汇总.xlsx…", "Save 汇总.xlsx as…"), icon_name="download",
                                     slot=lambda: W.save_file_dialog(self, f"{paths.ROOT.name}_汇总.xlsx", (out / "汇总.xlsx").read_bytes())),
                            W.button(T("在浏览器中打开报告", "Open report in browser"), icon_name="external",
                                     slot=lambda: __import__("webbrowser").open((out / "汇总报告.html").as_uri())), None))
        self.add(card)
        sheets = summary.collect()
        prev = Card(T("预览", "Preview"))
        if sheets:
            name = W.combo(list(sheets), self.state.get("sheet"))
            holder = W.vbox()

            def show():
                self.state["sheet"] = name.value()
                W._clear_layout(holder.layout())
                holder.layout().addWidget(W.Table(sheets[name.value()], max_height=440))
            name.currentIndexChanged.connect(lambda *_: show())
            prev.add(name)
            prev.add(holder)
            show()
        else:
            prev.add(W.label(T("项目中还没有结果：先在“校准与处理”中处理，再做拟合。", "No results yet: process under “Calibrate & process”, then fit."), "faint"))
        self.add(prev)


# ============================================================================= 方法导出
class MethodsPage(Page):
    """论文“方法”段落（中英文）+ 补充材料用的拟合参数表"""
    title_zh, title_en, icon_name = "方法导出", "Methods export", "quote"

    def build(self):
        self.header(T("由项目文件生成论文“方法”段落（中、英文）与拟合参数表。只写有记录的事实；投稿前请逐句核对。",
                      "Generate the Methods paragraph (Chinese and English) and the fit-parameter table from the project files. "
                      "States only recorded facts; check every sentence before submission."))
        self.add(self._methods())
        self.add(self._table())

    def _methods(self):
        from xafsmith import methods_text as mt, pipeline as pl
        S = self.S
        card = Card(T("“方法”段落", "Methods paragraph"))
        card.add(W.label(T("写入：参比与 ΔE、处理参数、拟合范围、N_idp、S0² 来源、软件版本。光源、线站等在下面填写；没填的用【方括号】占位。",
                           "Includes references and ΔE, processing parameters, fit ranges, N_idp, S0² source and versions. Fill in "
                           "the facility below; blanks stay as [placeholders]."), "faint"))
        cfg = load_cfg()
        ins = cfg.get("instrument", {})
        eds = {}
        items = []
        for k, (zh, en_) in mt.INSTRUMENT_KEYS.items():
            eds[k] = W.text(ins.get(k, ""))
            items.append((en_.capitalize() if W.en() else f"{zh} / {en_}", eds[k]))
        card.add(W.fields(*items, cols=3))

        def save_ins():
            c = load_cfg()
            c["instrument"] = {k: e.text() for k, e in eds.items()}
            save_cfg(c)
            W.toast(self, T("已保存到 xafsmith.json", "Saved to xafsmith.json"))
        samples = list(dict.fromkeys(pl.load_meta()["sample"])) if paths.META.exists() else []
        sel = W.MultiSelect(samples, self.state.get("mt", []), T("全部使用中的样品", "All samples in use"))
        out = W.vbox(spacing=10)

        def gen():
            self.state["mt"] = sel.value()
            p, r = mt.save(sel.value() or None)
            S.extra["methods"] = r
            W.toast(self, T(f"已保存 {paths.rel(p)}", f"Saved {paths.rel(p)}"))
            show()

        def show():
            r = S.extra.get("methods")
            W._clear_layout(out.layout())
            if r:
                for title, key in ((T("中文", "Chinese"), "zh"), ("English", "en")):
                    out.layout().addWidget(W.hbox(W.label(title, "h3"), None, W.copy_button(r[key])))
                    tb = W.prose_browser(html="".join(f"<p>{__import__('html').escape(x)}</p>" for x in r[key].split("\n\n")),
                                         size=11, bg=C["card"])
                    tb.setMinimumHeight(260)
                    out.layout().addWidget(tb)
        card.add(W.hbox(W.field(T("范围：只写这些样品", "Scope: only these samples"), sel),
                        W.vbox(None, W.button(T("保存仪器信息", "Save facility info"), icon_name="save", slot=save_ins)),
                        W.vbox(None, W.button(T("生成方法段落", "Generate"), primary=True, icon_name="play", slot=lambda: W.wait_cursor(gen))),
                        spacing=12))
        card.add(out)
        show()
        return card

    def _table(self):
        from xafsmith import si_text as si
        card = Card(T("拟合参数表（补充材料 Table S[n]）", "Fit-parameter table (Supporting Information, Table S[n])"))
        keys = si.fit_keys()
        if not keys:
            card.add(W.label(T("还没有保存的拟合：在“EXAFS 拟合”中拟合后点“保存结果”。",
                               "No saved fits yet: fit under “EXAFS fitting” and click “Save result”."), "faint"))
            return card
        sel = W.MultiSelect(keys, [k for k in self.state.get("sel", keys[-1:]) if k in keys], T("选择拟合", "Choose fits"),
                            fmt=lambda x: x.replace("|", " — "))
        sel.changed.connect(lambda v: (self.state.__setitem__("sel", v), self.refresh()))
        card.add(W.field(T("拟合", "Fits"), sel))
        if not sel.value():
            return card
        tab = si.table(sel.value())
        card.add(W.Table(tab.drop(columns=["Model"], errors="ignore"), max_height=420))
        r = si.build(sel.value())
        md = "# EXAFS fitting\n\n" + r["en"] + "\n\n" + si.table_markdown(tab) + "\n\n# EXAFS 拟合\n\n" + r["zh"] + "\n"
        card.add(W.hbox(W.label(T("粘贴到 Excel 直接成表；在 Word 中粘贴后用“文本转换成表格”。“S[n]”编号与结构来源请按论文修改。",
                                  "Pastes as a table in Excel; in Word use “Convert Text to Table”. Adjust “S[n]” and structure sources."),
                                "faint"), None,
                        W.copy_button(si.table_tsv(tab), T("复制表格", "Copy table")),
                        W.button(T("另存 .csv…", "Save .csv…"), icon_name="download",
                                 slot=lambda: W.save_file_dialog(self, "SI_EXAFS_fit_table.csv", tab.to_csv(index=False).encode("utf-8-sig"))),
                        W.button(T("另存 .md（含拟合说明）…", "Save .md (with fit text)…"), icon_name="download",
                                 slot=lambda: W.save_file_dialog(self, "SI_EXAFS_fitting.md", md.encode("utf-8")))))
        return card


def _fit_key(S, fit, keys):
    """拟合属于哪条谱（会话中的键）：拟合记录的样品名可能是键名，也可能是谱的显示名 g.label"""
    names = {fit["summ"].get("sample"), (fit.get("model") or {}).get("sample")}
    for k in keys:
        if k in names or getattr(S.groups.get(k), "label", None) in names:
            return k
    return None


# ============================================================================= 图片导出
class PubFigPage(Page):
    title_zh, title_en, icon_name = "图片导出", "Figure export", "chart"

    KINDS = ["xanes", "deriv", "chik", "chir"]

    def build(self):
        from xafsmith import pubfig as pf
        S = self.S
        self.header(T("统一字体（Arial）、线宽与配色；导出 600 dpi TIFF（LZW）/ PNG、矢量 SVG / PDF 与英文图注，也可直接导出 Origin 工程（.opju）。",
                      "Arial, consistent line widths and palettes; 600 dpi TIFF (LZW) / PNG, vector SVG / PDF and an English "
                      "caption, or an Origin project (.opju)."))
        names = {"xanes": T("归一化 XANES", "Normalized XANES"), "deriv": T("XANES 导数", "XANES derivative"), "chik": "kⁿχ(k)",
                 "chir": "|χ(R)|"}
        sizes = {"单栏 85 mm": T("单栏 85 mm", "Single column 85 mm"), "1.5 栏 120 mm": T("1.5 栏 120 mm", "1.5 column 120 mm"),
                 "双栏 178 mm": T("双栏 178 mm", "Double column 178 mm"), "汇报 16:9": T("汇报 16:9", "Slide 16:9")}
        ctl = Card()
        kind = W.Segmented(self.KINDS, self.state.get("kind", "xanes"), fmt=lambda k: names[k])
        kind.changed.connect(lambda v: (self.state.__setitem__("kind", v), self.refresh()))
        size = W.combo(list(pf.SIZES), self.state.get("size", "单栏 85 mm"), fmt=lambda s: sizes.get(s, s))
        fmts = W.MultiSelect(["tiff", "png", "svg", "pdf"], self.state.get("fmts", ["tiff", "png", "svg"]))
        name = W.text(self.state.get("name", f"fig_{datetime.datetime.now():%Y%m%d_%H%M}"))
        pal = W.combo(list(pf.PALETTES), self.state.get("pal", pf.DEFAULT_PALETTE),
                      fmt=lambda k: T(pf.PALETTES[k]["zh"], pf.PALETTES[k]["en"]))
        ctl.add(kind)
        k_ = self.state.get("kind", "xanes")
        if k_ not in self.KINDS:       # 旧版本的“拟合（k + R）”并入 χ(k)/|χ(R)| 的“叠加拟合”
            k_ = "chir"
        opt = {}
        if True:
            need_chi = k_ in ("chik", "chir")
            cands = [k for k, g in S.groups.items() if (has_chi(g) if need_chi else hasattr(g, "flat"))]
            if not cands:
                self.add(ctl)
                self.add(Banner("info", T("先载入样品" + ("，并在“χ(k) 与 FT”中计算 χ(k)" if need_chi else ""),
                                          "Load samples first" + (" and compute χ(k)" if need_chi else ""))))
                return
            opt["sel"] = W.MultiSelect(cands, [c for c in self.state.get("sel", cands[:3]) if c in cands], T("谱（按顺序作图）", "Spectra (plot order)"))
            opt["off"] = W.num(self.state.get("off", 0.0), 0, 50, 0.1)
            opt["sub"] = W.check(T("化学式下标（IrO2→IrO₂）", "Formula subscripts (IrO2→IrO₂)"), self.state.get("sub", True))
            items = [(T("谱", "Spectra"), opt["sel"]), (T("错开量", "Offset"), opt["off"])]
            if k_ in ("xanes", "deriv"):
                opt["lo"], opt["hi"] = W.num(self.state.get("lo", -20), -100, 0, 5), W.num(self.state.get("hi", 60), 10, 300, 5)
                items += [(T("E−E0 下限", "E−E0 from"), opt["lo"]), (T("E−E0 上限", "E−E0 to"), opt["hi"])]
            else:
                opt["kw"] = W.combo([1, 2, 3], self.state.get("kw", 2))
                items.append((T("k 权重", "k-weight"), opt["kw"]))
                if k_ == "chir":
                    opt["rmax"] = W.num(self.state.get("rmax", 6.0), 2, 10, 0.5)
                    opt["re"] = W.check(T("同时画 Re χ(R)（虚线）", "Also Re χ(R) (dashed)"), self.state.get("re", False))
                    items.append((T("R 上限", "R max"), opt["rmax"]))
                # 叠加拟合：每条谱默认取最近一次拟合，也可在列表中指定
                fit_ids = [i for i, f_ in enumerate(S.fits) if _fit_key(S, f_, cands)]
                latest = {}
                for i in fit_ids:
                    latest[_fit_key(S, S.fits[i], cands)] = i
                opt["usefit"] = W.check(T("叠加拟合曲线（虚线）", "Overlay fit (dashed)"), self.state.get("usefit", False) and bool(fit_ids))
                saved = [i for i in self.state.get("fits", []) if i in fit_ids]
                opt["fits"] = W.MultiSelect(fit_ids, saved or list(latest.values()),
                                            T("无拟合：先在“EXAFS 拟合”中拟合", "No fits: fit under “EXAFS fitting” first"),
                                            fmt=lambda i: fit_label(S.fits[i]))
            ctl.add(W.fields(*items))
            refs0 = self.state.get("refs")
            if refs0 is None:
                refs0 = pf.default_refs(cands)
            opt["refs"] = W.MultiSelect(cands, [c for c in refs0 if c in cands], T("无（全部按样品配色）", "None (all as samples)"))
            ctl.add(W.fields((T("配色方案", "Palette"), pal),
                             (T("参比 / 标样（用灰色画，线稍细）", "References / standards (grey, thinner)"), opt["refs"])))
            if "fits" in opt:       # 单独一行：放在上面一行会把页面撑宽，预览被裁掉
                ctl.add(W.fields((T("叠加的拟合（每条谱默认取最近一次）", "Fits to overlay (latest per spectrum by default)"), opt["fits"])))
            ctl.add(W.hbox(opt["sub"], *([opt["re"]] if "re" in opt else []), *([opt["usefit"]] if "usefit" in opt else []), None))
        ctl.add(W.fields((T("尺寸", "Size"), size), (T("格式", "Formats"), fmts), (T("文件名", "File name"), name)))
        self.add(ctl)
        view = Card(T("预览", "Preview"))
        holder = W.vbox()
        cap = W.label("", "muted")
        cap.setStyleSheet("font-size:10.5pt;")
        view.add(holder)
        view.add(W.label(T("图注（英文，随图保存为 .txt）", "Caption (saved with the figure as .txt)"), "h3"))
        view.add(cap)
        cur = {}

        def render():
            self.state.update(size=size.value(), fmts=fmts.value(), name=name.text(), pal=pal.value())
            for k, wdg in opt.items():
                v = wdg.isChecked() if isinstance(wdg, W.QCheckBox) else wdg.value()
                self.state[k] = v
            import matplotlib.pyplot as plt
            if cur.get("fig") is not None:
                plt.close(cur["fig"])
            with plain_rc():
                if True:
                    sel = opt["sel"].value()
                    if not sel:
                        W._clear_layout(holder.layout())
                        cur["fig"] = None
                        return
                    gs = [S.groups[k] for k in sel]
                    sub = opt["sub"].isChecked()
                    cols = pf.series_colors(sel, pal.value(), opt["refs"].value())
                    fits = None
                    if "usefit" in opt and opt["usefit"].isChecked():
                        # 按谱的显示名（g.label）对应：会话里的键名与 g.label 不一定相同
                        fits = {}
                        for i in opt["fits"].value():
                            smp = _fit_key(S, S.fits[i], sel)
                            if smp:
                                fits[S.groups[smp].label] = S.fits[i]
                        fits = fits or None
                    if k_ in ("xanes", "deriv"):
                        fig, c = pf.xanes(gs, size.value(), (opt["lo"].value(), opt["hi"].value()), opt["off"].value(),
                                          deriv=k_ == "deriv", sub=sub, colors=cols)
                    elif k_ == "chik":
                        fig, c = pf.chik(gs, size.value(), opt["kw"].value(), opt["off"].value(), sub=sub, colors=cols, fits=fits)
                    else:
                        fig, c = pf.chir(gs, size.value(), opt["kw"].value(), opt["rmax"].value(), opt["off"].value(),
                                         opt["re"].isChecked(), sub=sub, colors=cols, fits=fits)
                from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
                canvas = FigureCanvasQTAgg(fig)
                fig.set_dpi(150 if size.value() != "汇报 16:9" else 70)
                wpx, hpx = fig.get_size_inches() * fig.dpi
                canvas.setFixedSize(int(wpx), int(hpx))
                canvas.draw()
            cur.update(fig=fig, cap=c)
            W._clear_layout(holder.layout())
            holder.layout().addWidget(W.hbox(canvas, None))
            cap.setText(c)
        for wdg in list(opt.values()) + [size, pal]:
            if hasattr(wdg, "changed"):
                wdg.changed.connect(lambda *_: W.wait_cursor(render))
            elif hasattr(wdg, "currentIndexChanged"):
                wdg.currentIndexChanged.connect(lambda *_: W.wait_cursor(render))
            elif hasattr(wdg, "valueChanged"):
                wdg.valueChanged.connect(lambda *_: W.wait_cursor(render))
            elif hasattr(wdg, "toggled"):
                wdg.toggled.connect(lambda *_: W.wait_cursor(render))

        def base_name():
            return re.sub(r"[^\w.-]+", "_", name.text()) or "figure"

        def save():
            if cur.get("fig") is None or not fmts.value():
                return
            with plain_rc():
                cur["fig"].set_dpi(100)
                files = pf.save(cur["fig"], cur["cap"], paths.PUBFIGS / base_name(), fmts.value())
            cur["fig"] = None
            W.toast(self, T("已保存：", "Saved: ") + ", ".join(p.name for p in files))
            W.wait_cursor(render)

        obtn = W.button(T("导出 Origin 工程 (.opju)", "Export Origin project (.opju)"), icon_name="download",
                        tip=T("每条曲线写成工作表中的一对 X/Y 列，并按统一格式作图（图层 25×19 cm、Arial 32 pt、四边框、刻度朝外）。"
                              "本机有 Origin 时直接生成 .opju；否则写出数据与 build_origin.py，在 Origin 脚本窗口运行即可。",
                              "Each curve becomes an X/Y column pair; graphs use one format (25×19 cm layer, Arial 32 pt, boxed axes, "
                              "outward ticks). With Origin installed the .opju is built directly; otherwise data and build_origin.py "
                              "are written for Origin's script window."))

        def origin():
            if cur.get("fig") is None:
                return
            from xafsmith import origin_export as oe
            fig = cur["fig"]
            od = paths.PUBFIGS / "origin" / base_name()

            def done(r):
                if r["mode"] == "originpro":
                    W.toast(self, T(f"已生成 Origin 工程：{paths.rel(Path(r['opju']))}", f"Origin project: {paths.rel(Path(r['opju']))}"))
                else:
                    W.toast(self, T(f"未找到 Origin（originpro）：已写出数据与脚本到 {paths.rel(Path(r['folder']))}，"
                                    "在 Origin 脚本窗口运行 build_origin.py（见 README_Origin.txt）",
                                    f"Origin (originpro) not found: data and script written to {paths.rel(Path(r['folder']))}; "
                                    "run build_origin.py in Origin's script window (see README_Origin.txt)"), "warn")
                W.open_folder(Path(r["folder"]))
            # Origin 通过 COM 调用：在界面线程中运行（底部显示进度提示）
            self.app.busy(True, T("正在生成 Origin 工程（启动 Origin 约 10–30 秒）…", "Building the Origin project (Origin starts in 10–30 s)…"))
            from PySide6.QtWidgets import QApplication
            QApplication.processEvents()
            try:
                r = W.wait_cursor(lambda: oe.export(fig, od, base_name(), kind=k_))
            except Exception as ex:      # noqa: BLE001
                logs.log.warning("qt.pages.output.done 出错（已忽略或已提示）", exc_info=True)
                W.ERRORS.append(f"origin: {ex}")
                W.toast(self, T(f"Origin 导出失败：{ex}", f"Origin export failed: {ex}"), "err")
                return
            finally:
                self.app.busy(False)
            if r:
                done(r)
        obtn.clicked.connect(origin)
        self.add(W.hbox(W.button(T("打开 output/figs/journal", "Open output/figs/journal"), icon_name="external",
                                 slot=lambda: W.open_folder(paths.PUBFIGS)), None, obtn,
                        W.button(T("保存到 output/figs/journal/", "Save to output/figs/journal/"), primary=True, icon_name="save", slot=save)))
        self.add(view)
        W.wait_cursor(render)


# ============================================================================= 制样指导
class PlannerPage(Page):
    title_zh, title_en, icon_name = "制样指导", "Sample preparation", "flask"

    def build(self):
        from xafsmith import mut_planner as xmut
        from xafsmith.common import edge_energy
        self.header(T("透射样品：总 μt 1.5–2.6 最佳，Δμt ≥ 0.2；均匀性比 Δμt 精确匹配更重要。数据：xraydb（Elam 表）。",
                      "Transmission: total μt 1.5–2.6 is best, Δμt ≥ 0.2; uniformity matters more than matching Δμt. Data: xraydb (Elam)."))
        st = self.state
        # 样品信息：两个工具共用
        info = Card(T("样品信息", "Sample"))
        formula = W.text(st.get("formula", "IrO2"))
        try:
            import xraydb
            fel = list(xraydb.chemparse(formula.text()))
            parse_err = None
        except Exception as ex:      # noqa: BLE001
            logs.log.warning("qt.pages.output.build 出错（已忽略或已提示）", exc_info=True)
            fel, parse_err = [], str(ex)
        from pymatgen.core import Element as _El
        heavy = max(fel, key=lambda e: _El(e).Z) if fel else "Ir"
        el = W.combo(fel or [heavy], st.get("el") if st.get("el") in fel else heavy)
        z = _El(el.value()).Z
        ed = W.combo(["K", "L3", "L2", "L1"], st.get("ed") or ("K" if z <= 50 else "L3"))
        info.add(W.fields((T("化学式", "Formula"), formula, T("如 IrO2、IrCo0.2Ox 写成 IrCo0.2O2、Ta2O5", "e.g. IrO2, Ta2O5")),
                          (T("目标元素（从化学式读取）", "Absorber (from the formula)"), el), (T("吸收边", "Edge"), ed), cols=3))
        if parse_err:
            info.add(Banner("err", T(f"化学式无法解析：{parse_err}", f"Cannot parse the formula: {parse_err}")))
        try:
            e0 = edge_energy(el.value(), ed.value())
            info.add(W.label(T(f"体系中的元素：{', '.join(fel) or '—'}；{el.value()} {ed.value()} 边 = {e0:.0f} eV",
                               f"Elements: {', '.join(fel) or '—'}; {el.value()} {ed.value()} edge = {e0:.0f} eV"), "muted"))
        except Exception:
            logs.log.warning("qt.pages.output.build 出错（已忽略或已提示）", exc_info=True)
            pass

        def re_formula():
            st["formula"] = formula.text().strip()
            st.pop("el", None)
            st.pop("ed", None)
            self.refresh()
        formula.editingFinished.connect(lambda: formula.text().strip() != st.get("formula", "IrO2") and re_formula())
        el.currentIndexChanged.connect(lambda *_: (st.__setitem__("el", el.value()), st.pop("ed", None), self.refresh()))
        ed.currentIndexChanged.connect(lambda *_: (st.__setitem__("ed", ed.value()), self.refresh()))
        self.add(info)
        # 压片制样计算器
        card = Card(T("压片制样计算器", "Pellet calculator"))
        w = dict(area=W.num(st.get("area", 1.327), 0.1, 10, 0.1, 3), dil=W.text(st.get("dil", "BN")),
                 mdil=W.num(st.get("mdil", 100), 0, 1000, 10), tgt=W.num(st.get("tgt", 2.0), 0.5, 4, 0.1),
                 mass=W.num(st.get("mass", 0.0), 0, 1000, 1))
        card.add(W.fields((T("压片面积 (cm²)", "Pellet area (cm²)"), w["area"], T("φ13 mm = 1.327 cm²", "φ13 mm = 1.327 cm²")),
                          (T("稀释剂（空 = 无）", "Diluent (empty = none)"), w["dil"]), (T("稀释剂质量 (mg)", "Diluent mass (mg)"), w["mdil"]),
                          (T("目标总 μt", "Target total μt"), w["tgt"]),
                          (T("样品质量 (mg，0 = 只推荐)", "Sample mass (mg, 0 = recommend only)"), w["mass"]), cols=5))
        res = W.vbox()
        card.add(res)
        self.add(card)
        # 干扰吸收边筛查
        ie = Card(T("干扰吸收边筛查", "Interfering-edge screening"))
        extra = W.text(st.get("extra", ""), T("如 K, Cl（可空）", "e.g. K, Cl (optional)"))
        emax = W.num(st.get("emax", 0) or 0, 0, 200000, 100, 0)
        ie.add(W.fields((T("其他共存元素（化学式之外，可空）", "Other elements present (optional)"), extra),
                        (T("扫描上限 (eV，0 = 边后 1000 eV)", "Scan end (eV, 0 = edge + 1000 eV)"), emax), cols=2))
        used = W.label("", "muted")
        ie.add(used)
        ires = W.vbox()
        ie.add(ires)
        self.add(ie)

        def upd():
            for k, x in w.items():
                st[k] = x.value() if hasattr(x, "value") else x.text()
            st.update(extra=extra.text(), emax=emax.value(), formula=formula.text().strip(), el=el.value(), ed=ed.value())
            f, e_, edg = st["formula"], el.value(), ed.value()
            W._clear_layout(res.layout())
            try:
                r = xmut.recommend_mass(f, st["area"], e_, edg, st["tgt"], st["dil"] or None, st["mdil"])
                res.layout().addWidget(W.metrics((T("推荐样品质量", "Recommended mass"), f"{r['mass_mg']:.2f} mg"),
                                                 (T("边后总 μt", "Total μt above edge"), f"{r['mut_above']:.2f}"),
                                                 (T("边跳 Δμt", "Edge step Δμt"), f"{r['edge_step']:.2f}")))
                res.layout().addWidget(W.label(r["advice"], "muted"))
                if st["mass"] > 0:
                    m = xmut.mut_for_mass(f, st["mass"], st["area"], e_, edg, st["dil"] or None, st["mdil"])
                    res.layout().addWidget(W.Table(pd.DataFrame([{"key": k, "value": v} for k, v in m.items()])))
            except Exception as ex:      # noqa: BLE001
                logs.log.warning("qt.pages.output.upd 出错（已忽略或已提示）", exc_info=True)
                res.layout().addWidget(Banner("err", str(ex)))
            W._clear_layout(ires.layout())
            try:
                import xraydb
                els = list(fel)
                if st["dil"]:
                    els += [x for x in xraydb.chemparse(st["dil"]) if x not in els]
                els += [x.strip() for x in re.split(r"[,，;\s]+", extra.text()) if x.strip() and x.strip() not in els]
                used.setText(T("参与筛查的元素：", "Elements screened: ") + ", ".join(els))
                e_end = emax.value() or edge_energy(e_, edg) + 1000
                df = xmut.interfering_edges(els, e_, edg, e_end)
                if len(df):
                    ires.layout().addWidget(Banner("warn", T(f"扫描范围内有 {len(df)} 个其他吸收边：k 上限取第一个干扰边之前（k ≈ {df.k.iloc[0]:.1f} Å⁻¹ 减 0.3）",
                                                             f"{len(df)} other edge(s) in the scan: keep kmax below the first one (k ≈ {df.k.iloc[0]:.1f} Å⁻¹ minus 0.3)")))
                    ires.layout().addWidget(W.Table(df))
                else:
                    ires.layout().addWidget(Banner("ok", T("扫描范围内没有其他吸收边。", "No other edge within the scan.")))
            except Exception as ex:      # noqa: BLE001
                logs.log.warning("qt.pages.output.upd 出错（已忽略或已提示）", exc_info=True)
                ires.layout().addWidget(Banner("err", str(ex)))
        for x in w.values():
            if hasattr(x, "editingFinished"):
                x.editingFinished.connect(upd)
        extra.editingFinished.connect(upd)
        emax.editingFinished.connect(upd)
        upd()


# ============================================================================= 吸收边查询（同 Hephaestus 的周期表）
_PT = [  # (Z, 行, 列)：1–7 行为周期表，9、10 行为镧系、锕系
]
for _z, _r, _c in [(1, 1, 1), (2, 1, 18)]:
    _PT.append((_z, _r, _c))
for _p, _z0 in ((2, 3), (3, 11)):
    _PT += [(_z0, _p, 1), (_z0 + 1, _p, 2)] + [(_z0 + 2 + i, _p, 13 + i) for i in range(6)]
_PT += [(19 + i, 4, 1 + i) for i in range(18)] + [(37 + i, 5, 1 + i) for i in range(18)]
_PT += [(55, 6, 1), (56, 6, 2), (57, 6, 3)] + [(72 + i, 6, 4 + i) for i in range(15)]
_PT += [(87, 7, 1), (88, 7, 2), (89, 7, 3)]
_PT += [(58 + i, 9, 4 + i) for i in range(14)] + [(90 + i, 10, 4 + i) for i in range(9)]


class ElementsPage(Page):
    """点元素：吸收边（能量、荧光产额、跳跃比）、荧光线、荧光滤片（同 Hephaestus 的 Absorption / Filter）"""
    title_zh, title_en, icon_name = "吸收边查询", "Edge lookup", "target"
    max_width = 1600

    def build(self):
        from xafsmith import mut_planner as xmut
        import xraydb
        self.header(T("点击元素：查看吸收边、荧光线与荧光测量用的滤片。数据：xraydb（Elam 表）。",
                      "Click an element: absorption edges, fluorescence lines and a filter for fluorescence measurements. "
                      "Data: xraydb (Elam)."))
        cur = self.state.get("el", "Ir")
        pt = Card()
        grid = QGridLayout()
        grid.setHorizontalSpacing(3)
        grid.setVerticalSpacing(3)
        for z, r, c in _PT:
            sym = xraydb.atomic_symbol(z)
            b = QPushButton(sym)
            b.setCheckable(True)
            b.setChecked(sym == cur)
            b.setFixedSize(40, 32)
            b.setToolTip(f"{z} {xraydb.atomic_name(z)}")
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            on = sym == cur
            b.setStyleSheet(f"QPushButton{{padding:0;border-radius:6px;font-size:9.5pt;font-weight:600;"
                            f"border:1px solid {C['accent'] if on else C['border']};"
                            f"background:{C['accent'] if on else C['card']};color:{'#FFFFFF' if on else C['text']};}}"
                            f"QPushButton:hover{{border-color:{C['accent']};}}")
            b.clicked.connect(lambda _=False, s=sym: (self.state.__setitem__("el", s), self.refresh()))
            grid.addWidget(b, r, c)
        grid.setRowMinimumHeight(8, 10)
        box = QWidget()
        box.setLayout(grid)
        pt.add(W.hbox(None, box, None))
        self.add(pt)
        try:
            inf = xmut.element_info(cur)
            et = xmut.edge_table(cur)
            lt = xmut.line_table(cur)
        except Exception as ex:      # noqa: BLE001
            logs.log.warning("qt.pages.output.build 出错（已忽略或已提示）", exc_info=True)
            self.add(Banner("err", str(ex)))
            return
        self.add(W.label(f"<span style='font-size:18pt;font-weight:600'>{cur}</span>&nbsp;&nbsp;"
                         f"<span style='color:{C['text2']}'>{inf['name']} · Z = {inf['Z']} · "
                         + T(f"相对原子质量 {inf['mass']:.3f} · 密度 {inf['density']:.3g} g/cm³",
                             f"atomic mass {inf['mass']:.3f} · density {inf['density']:.3g} g/cm³") + "</span>", rich=True))
        ec = Card(T("吸收边", "Absorption edges"))
        e2 = et.rename(columns={"edge": T("吸收边", "Edge"), "energy": T("能量 (eV)", "Energy (eV)"),
                                "fyield": T("荧光产额", "Fluorescence yield"), "jump_ratio": T("跳跃比", "Jump ratio")})
        ec.add(W.Table(e2, height=360, decimals=4, fit=True))
        lc = Card(T("荧光线", "Fluorescence lines"))
        l2 = lt.rename(columns={"line": T("谱线", "Line"), "energy": T("能量 (eV)", "Energy (eV)"),
                                "intensity": T("相对强度", "Intensity"), "transition": T("跃迁", "Transition")})
        lc.add(W.Table(l2, height=360, decimals=4, fit=True))
        row = W.hbox(ec, lc, spacing=14)
        self.add(row)
        note = W.label(T("荧光线的相对强度在同一初始能级（同一个吸收边）的谱线之间归一；只列出强度 ≥ 0.001 的谱线。",
                         "Line intensities are normalised within lines from the same initial level; lines below 0.001 are omitted."),
                       "faint")
        # 滤片
        fc = Card(T("荧光滤片", "Fluorescence filter"))
        row.layout().addWidget(fc)
        for i_ in range(3):
            row.layout().setStretch(i_, 1)
        self.add(note)
        edges = [e for e in ("K", "L3", "L2", "L1") if e in set(et.edge) and float(et[et.edge == e].energy.iloc[0]) > 2000]
        if not edges:
            fc.add(W.label(T("该元素的吸收边能量太低，不适合硬 X 射线荧光测量。", "Edges too low for hard-X-ray fluorescence."), "faint"))
            for c_ in (ec, lc, fc):
                c_.lay.addStretch(1)
            return
        fe = W.combo(edges, self.state.get("fedge") if self.state.get("fedge") in edges else
                     ("K" if "K" in edges and float(et[et.edge == "K"].energy.iloc[0]) < 40000 else edges[min(1, len(edges) - 1)]))
        nab = W.num(self.state.get("nab", 3.0), 0.5, 10, 0.5, 1)
        out = W.vbox()
        fc.add(W.fields((T("测量的吸收边", "Edge measured"), fe), (T("滤片厚度 μx", "Thickness μx"), nab), cols=2))
        fc.add(out)

        def upd():
            self.state.update(fedge=fe.value(), nab=nab.value())
            W._clear_layout(out.layout())
            try:
                r = xmut.fluor_filter(cur, fe.value(), nab.value())
            except Exception as ex:      # noqa: BLE001
                logs.log.warning("qt.pages.output.upd 出错（已忽略或已提示）", exc_info=True)
                out.layout().addWidget(Banner("err", str(ex)))
                return
            out.layout().addWidget(W.label(T(f"{cur} {fe.value()} 边 {r['edge_energy']:.0f} eV；主荧光线 {r['line']} {r['line_energy']:.0f} eV。"
                                             "滤片的吸收边要落在两者之间：吸收入射能量附近的散射，让荧光线通过。",
                                             f"{cur} {fe.value()} edge {r['edge_energy']:.0f} eV; main line {r['line']} {r['line_energy']:.0f} eV. "
                                             "The filter edge must lie between them: it absorbs scatter near the incident energy and "
                                             "passes the fluorescence line."), "muted"))

            df = r["table"].drop(columns=["Z"]).rename(columns={"filter": T("滤片", "Filter"), "edge": T("边", "Edge"),
                                            "edge_energy": "eV",
                                            "thickness_um": T("厚度 μm", "μm"),
                                            "line_transmission": T("透过率", "Transm.")})
            if len(df):
                out.layout().addWidget(W.Table(df, decimals=3, fit=True))
                out.layout().addWidget(W.label(T(f"厚度：μx = {nab.value():g}（目标边以上 50 eV）；透过率：主荧光线穿过该厚度的比例。",
                                                 f"Thickness for μx = {nab.value():g} (50 eV above the edge); transmission of the main line."), "faint"))
                out.layout().addWidget(W.label(T("按荧光线透过率排序（同样吸收散射时，透过越多越好）；第一行通常就是 Z−1（或 Z−2）元素。"
                                                 "厚度按单质密度、目标边以上 50 eV 计算；实际滤片多为氧化物涂层，按面密度换算。",
                                                 "Sorted by line transmission (more is better for the same scatter suppression); the first row is "
                                                 "usually the Z−1 (or Z−2) element. Thickness uses the elemental density at 50 eV above the edge; "
                                                 "real filters are often oxide coatings — convert by areal density."), "faint"))
            else:
                out.layout().addWidget(W.label(T("没有合适的滤片元素。", "No suitable filter element."), "faint"))
        fe.currentIndexChanged.connect(lambda *_: upd())
        nab.editingFinished.connect(upd)
        upd()
        for c_ in (ec, lc, fc):          # 三张卡片等高、内容靠上（标题对齐）
            c_.lay.addStretch(1)


# ============================================================================= AI 助手
class AgentPage(Page):
    title_zh, title_en, icon_name = "AI 助手", "AI assistant", "spark"

    def build(self):
        from xafsmith import agent
        self.header(T("XAFSmith 项目是标准化的文件夹，AI 助手可以直接读懂并替你处理、拟合、导出；每一步都写进项目文件，可以随时在这里检查、修改。",
                      "An XAFSmith project is a standard folder an AI assistant can read and work in: it processes, fits and exports "
                      "for you, and every step is written to project files you can inspect and change here."))
        s = agent.status(paths.ROOT)
        c1 = Card(T("接入", "Connect"))
        c1.add(W.hbox(W.pill("AGENTS.md · " + (T("已接入", "connected") if s["current"] else (T("需更新", "needs update") if s["block"] else T("未接入", "not connected"))),
                             s["current"]),
                      W.pill("CLAUDE.md · " + (T("已接入", "connected") if s["claude_md"] else T("未接入", "not connected")), s["claude_md"]), None))
        c1.add(W.label(T("本机 xafsmith 命令（AI 用它运行所有步骤）", "The xafsmith command on this computer (the AI runs every step with it)"), "faint"))
        c1.add(W.code_block(s["command"], copy=True))

        def write():
            ch = agent.write(paths.ROOT)
            W.toast(self, (T("已更新：", "Updated: ") + ", ".join(p.name for p in ch)) if ch else T("已是最新，无需改动", "Already up to date"))
            self.refresh()
        c1.add(W.hbox(W.label(T("只更新 AGENTS.md 中 XAFSmith 标记之间的部分；你自己写的内容会保留。",
                                "Only the part between the XAFSmith markers in AGENTS.md is updated; your own text is kept."), "faint"), None,
                      W.button(T("写入 / 更新 AI 说明文件", "Write / update AI instruction files"), primary=True, icon_name="save", slot=write)))
        self.add(c1)
        c2 = Card(T("第 1 步：在项目文件夹里打开 AI 助手", "Step 1: open the AI assistant in the project folder"))
        rows = [(T("Claude Code 桌面版", "Claude Code desktop"), T("新建会话 → 选择本项目文件夹", "New session → choose this project folder")),
                (T("Claude Code 命令行", "Claude Code CLI"), T("在本项目文件夹中打开终端，输入 claude", "Open a terminal in this folder and type claude")),
                ("Codex", T("在本项目文件夹中打开终端输入 codex，或在 Codex 应用中打开该文件夹", "Type codex in a terminal here, or open the folder in the Codex app")),
                ("Cursor / VS Code", T("文件 → 打开文件夹 → 本项目文件夹，打开 AI 对话面板", "File → Open Folder → this folder, then the AI chat panel"))]
        c2.add(W.Table(pd.DataFrame(rows, columns=[T("AI 助手", "Assistant"), T("怎么打开", "How to open")])))
        c2.add(W.code_block(str(paths.ROOT), copy=True))
        self.add(c2)
        c3 = Card(T("第 2 步：用自己的话告诉它要做什么", "Step 2: tell it what to do in your own words"))
        for e in (agent.EXAMPLES_EN if W.en() else agent.EXAMPLES_ZH):
            c3.add(W.code_block(e, copy=True, wrap=True, height=64))
        self.add(c3)
        c4 = Card(T("第 3 步：检查 AI 的结果", "Step 3: check the AI's work"))
        for txt, key in ((T("拟合模型在 models/：“EXAFS 拟合”顶部“运行已保存的模型”可重跑，并看诊断与稳健性", "Fit models are in models/: rerun them at the top of “EXAFS fitting” and check diagnosis and robustness"), "fit"),
                         (T("全部数值结果在 output/；分析记录在 notes/", "All numbers are in output/; analysis notes in notes/"), "data"),
                         (T("导出的图在 output/figs/journal/，报告在 output/reports/", "Exported figures in output/figs/journal/, reports in output/reports/"), "summary")):
            c4.add(W.hbox(W.label("•  " + txt), None, W.link(T("打开 →", "Open →"), lambda k=key: self.app.go(k))))
        self.add(c4)


# ============================================================================= 使用指南
class HelpPage(Page):
    """侧栏中的“使用指南”：点击后打开独立的使用指南窗口（qt/help.py），主窗口停在当前页"""
    title_zh, title_en, icon_name = "使用指南", "Help", "help"

    def build(self):
        self.app.open_help()
