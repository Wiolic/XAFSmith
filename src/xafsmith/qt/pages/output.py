"""结果与导出：汇总报告（含方法段落）、期刊出图、SI 方法；工具：样品设计、AI 助手、使用指南"""
from __future__ import annotations

import datetime
import re
from pathlib import Path

import pandas as pd
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QTextBrowser, QWidget

from xafsmith import paths
from .. import widgets as W
from ..state import fit_label, has_chi, is_project, load_cfg, plain_rc, save_cfg, save_fit
from ..theme import C
from ..widgets import T, Banner, Card, Page


# ============================================================================= 汇总
class SummaryPage(Page):
    title_zh, title_en, icon_name = "汇总报告", "Summary report", "doc"

    def build(self):
        from xafsmith import summary
        S = self.S
        self.header(T("把项目中已保存的全部结果整理成一个 Excel 工作簿和一份带图的 HTML 报告。",
                      "Collect every saved result into one Excel workbook and an HTML report with figures."))
        card = Card(T("生成汇总", "Build summary"))
        if S.fits:
            card.add(Banner("info", T(f"本次会话有 {len(S.fits)} 个拟合；只有保存过的拟合会进入汇总。",
                                      f"{len(S.fits)} fits in this session; only saved fits are included.")))
        btn = W.button(T("生成汇总", "Build summary"), primary=True, icon_name="play")

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
            row.insert(0, W.button(T("先保存本次会话的全部拟合", "Save this session's fits first"), icon_name="save",
                                   slot=lambda: W.wait_cursor(save_session_fits)))
        card.add(W.hbox(*row))
        d = S.extra.get("summary_dir")
        if d and (Path(d) / "汇总.xlsx").exists():
            out = Path(d)
            card.add(Banner("ok", T(f"已生成：{paths.rel(out)}", f"Built: {paths.rel(out)}")))
            card.add(W.hbox(W.button(T("打开汇总文件夹", "Open summary folder"), icon_name="external", slot=lambda: W.open_folder(out)),
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
        self.add(self._methods())

    def _methods(self):
        from xafsmith import methods_text as mt, pipeline as pl
        S = self.S
        card = Card(T("“方法”段落", "Methods paragraph"))
        card.add(W.label(T("只写项目文件中有记录的事实（参比、ΔE、处理参数、拟合范围、N_idp、S0² 来源、软件版本）。光源、线站等在下面填写；没填的用【方括号】占位。投稿前请逐句核对。",
                           "States only facts recorded in the project (references, ΔE, processing parameters, fit ranges, N_idp, S0² "
                           "source, versions). Fill in the facility below; blanks stay as [placeholders]. Check every sentence before submission."), "faint"))
        cfg = load_cfg()
        ins = cfg.get("instrument", {})
        eds = {}
        items = []
        for k, (zh, en_) in mt.INSTRUMENT_KEYS.items():
            eds[k] = W.text(ins.get(k, ""))
            items.append((en_.capitalize() if W.en() else f"{zh} / {en_}", eds[k]))
        card.add(W.fields(*items, cols=4))

        def save_ins():
            c = load_cfg()
            c["instrument"] = {k: e.text() for k, e in eds.items()}
            save_cfg(c)
            W.toast(self, T("已保存到 xafsmith.json", "Saved to xafsmith.json"))
        samples = list(dict.fromkeys(pl.load_meta()["sample"])) if paths.META.exists() else []
        sel = W.MultiSelect(samples, self.state.get("mt", []), T("全部使用中的样品", "All samples in use"))
        out = W.vbox()

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
                out.layout().addWidget(W.label(T("中文", "Chinese"), "h3"))
                out.layout().addWidget(W.code_block(r["zh"], copy=True, wrap=True, height=200))
                out.layout().addWidget(W.label("English", "h3"))
                out.layout().addWidget(W.code_block(r["en"], copy=True, wrap=True, height=200))
        card.add(W.hbox(W.field(T("范围：只写这些样品", "Scope: only these samples"), sel),
                        W.vbox(None, W.button(T("保存仪器信息", "Save facility info"), icon_name="save", slot=save_ins)),
                        W.vbox(None, W.button(T("生成方法段落", "Generate"), primary=True, icon_name="play", slot=lambda: W.wait_cursor(gen))),
                        spacing=12))
        card.add(out)
        show()
        return card


# ============================================================================= 期刊出图
class PubFigPage(Page):
    title_zh, title_en, icon_name = "期刊出图", "Journal figures", "chart"

    KINDS = ["xanes", "deriv", "chik", "chir", "fit"]

    def build(self):
        from xafsmith import pubfig as pf
        S = self.S
        self.header(T("统一字体（Arial）、线宽、色盲友好配色；导出 600 dpi TIFF（LZW）/ PNG 与矢量 SVG / PDF，并写英文图注。",
                      "Arial, consistent line widths, colour-blind-safe palette; 600 dpi TIFF (LZW) / PNG and vector SVG / PDF, "
                      "with an English caption."))
        names = {"xanes": T("归一化 XANES", "Normalized XANES"), "deriv": T("XANES 导数", "XANES derivative"), "chik": "kⁿχ(k)",
                 "chir": "|χ(R)|", "fit": T("拟合（k + R）", "Fit (k + R)")}
        sizes = {"单栏 85 mm": T("单栏 85 mm", "Single column 85 mm"), "1.5 栏 120 mm": T("1.5 栏 120 mm", "1.5 column 120 mm"),
                 "双栏 178 mm": T("双栏 178 mm", "Double column 178 mm"), "汇报 16:9": T("汇报 16:9", "Slide 16:9")}
        ctl = Card()
        kind = W.Segmented(self.KINDS, self.state.get("kind", "xanes"), fmt=lambda k: names[k])
        kind.changed.connect(lambda v: (self.state.__setitem__("kind", v), self.refresh()))
        size = W.combo(list(pf.SIZES), self.state.get("size", "单栏 85 mm"), fmt=lambda s: sizes.get(s, s))
        fmts = W.MultiSelect(["tiff", "png", "svg", "pdf"], self.state.get("fmts", ["tiff", "png", "svg"]))
        name = W.text(self.state.get("name", f"fig_{datetime.datetime.now():%Y%m%d_%H%M}"))
        ctl.add(kind)
        k_ = self.state.get("kind", "xanes")
        opt = {}
        if k_ == "fit":
            if not S.fits:
                self.add(ctl)
                self.add(Banner("info", T("本次会话还没有拟合：在“EXAFS 拟合”中拟合或运行已保存的模型。",
                                          "No fits in this session: fit or run a saved model under “EXAFS fitting”.")))
                return
            opt["fit"] = W.combo(list(range(len(S.fits))), self.state.get("fit", len(S.fits) - 1), fmt=lambda i: fit_label(S.fits[i]))
            opt["kw"] = W.combo([1, 2, 3], self.state.get("kw", 2))
            opt["rmax"] = W.num(self.state.get("rmax", 6.0), 2, 10, 0.5)
            ctl.add(W.fields((T("拟合", "Fit"), opt["fit"]), (T("k 权重", "k-weight"), opt["kw"]), (T("R 上限", "R max"), opt["rmax"])))
        else:
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
            ctl.add(W.fields(*items))
            ctl.add(W.hbox(opt["sub"], *( [opt["re"]] if "re" in opt else []), None))
        ctl.add(W.fields((T("尺寸", "Size"), size), (T("格式", "Formats"), fmts), (T("文件名", "File name"), name)))
        self.add(ctl)
        view = Card(T("预览", "Preview"))
        holder = W.vbox()
        cap = W.label("", "faint")
        view.add(holder)
        view.add(cap)
        cur = {}

        def render():
            self.state.update(size=size.value(), fmts=fmts.value(), name=name.text())
            for k, wdg in opt.items():
                v = wdg.value() if hasattr(wdg, "value") else wdg.isChecked()
                if isinstance(wdg, W.QCheckBox):
                    v = wdg.isChecked()
                self.state[k] = v
            import matplotlib.pyplot as plt
            if cur.get("fig") is not None:
                plt.close(cur["fig"])
            with plain_rc():
                if k_ == "fit":
                    f_ = S.fits[opt["fit"].value()]
                    fig, c = pf.fit(f_["curves"], f_["summ"], size.value(), kweight=opt["kw"].value(), rmax=opt["rmax"].value(),
                                    model=f_["model"])
                else:
                    sel = opt["sel"].value()
                    if not sel:
                        W._clear_layout(holder.layout())
                        cur["fig"] = None
                        return
                    gs = [S.groups[k] for k in sel]
                    sub = opt["sub"].isChecked()
                    if k_ in ("xanes", "deriv"):
                        fig, c = pf.xanes(gs, size.value(), (opt["lo"].value(), opt["hi"].value()), opt["off"].value(),
                                          deriv=k_ == "deriv", sub=sub)
                    elif k_ == "chik":
                        fig, c = pf.chik(gs, size.value(), opt["kw"].value(), opt["off"].value(), sub=sub)
                    else:
                        fig, c = pf.chir(gs, size.value(), opt["kw"].value(), opt["rmax"].value(), opt["off"].value(),
                                         opt["re"].isChecked(), sub=sub)
                from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
                canvas = FigureCanvasQTAgg(fig)
                fig.set_dpi(110 if size.value() != "汇报 16:9" else 70)
                wpx, hpx = fig.get_size_inches() * fig.dpi
                canvas.setFixedSize(int(wpx), int(hpx))
                canvas.draw()
            cur.update(fig=fig, cap=c)
            W._clear_layout(holder.layout())
            holder.layout().addWidget(W.hbox(canvas, None))
            cap.setText(T("图注：", "Caption: ") + c)
        for wdg in list(opt.values()) + [size]:
            if hasattr(wdg, "changed"):
                wdg.changed.connect(lambda *_: W.wait_cursor(render))
            elif hasattr(wdg, "currentIndexChanged"):
                wdg.currentIndexChanged.connect(lambda *_: W.wait_cursor(render))
            elif hasattr(wdg, "valueChanged"):
                wdg.valueChanged.connect(lambda *_: W.wait_cursor(render))
            elif hasattr(wdg, "toggled"):
                wdg.toggled.connect(lambda *_: W.wait_cursor(render))

        def save():
            if cur.get("fig") is None or not fmts.value():
                return
            with plain_rc():
                cur["fig"].set_dpi(100)
                files = pf.save(cur["fig"], cur["cap"], paths.PUBFIGS / re.sub(r"[^\w.-]+", "_", name.text()), fmts.value())
            cur["fig"] = None
            W.toast(self, T("已保存：", "Saved: ") + ", ".join(p.name for p in files))
            W.wait_cursor(render)
        self.add(view)
        self.add(W.hbox(W.button(T("打开 output/figs/journal", "Open output/figs/journal"), icon_name="external",
                                 slot=lambda: W.open_folder(paths.PUBFIGS)), None,
                        W.button(T("保存到 output/figs/journal/", "Save to output/figs/journal/"), primary=True, icon_name="save", slot=save)))
        W.wait_cursor(render)


# ============================================================================= SI
class SIPage(Page):
    title_zh, title_en, icon_name = "SI 方法", "SI methods", "quote"

    def build(self):
        from xafsmith import si_text as si
        self.header(T("选择已保存的拟合，一键复制补充材料（SI）用的拟合方法文字与参数表。",
                      "Pick saved fits and copy the fitting text and parameter table for the Supporting Information."))
        keys = si.fit_keys()
        if not keys:
            self.add(Banner("info", T("还没有保存的拟合：在“EXAFS 拟合”中拟合后点“保存结果”。",
                                      "No saved fits yet: fit under “EXAFS fitting” and click “Save result”.")))
            return
        sel = W.MultiSelect(keys, [k for k in self.state.get("sel", keys[-1:]) if k in keys], T("选择要写进 SI 的拟合", "Choose fits for the SI"),
                            fmt=lambda x: x.replace("|", " — "))
        lang = W.Segmented(["en", "zh"], self.state.get("lang", "en"), fmt=lambda x: "English" if x == "en" else "中文")
        sel.changed.connect(lambda v: (self.state.__setitem__("sel", v), self.refresh()))
        lang.changed.connect(lambda v: (self.state.__setitem__("lang", v), self.refresh()))
        self.add(W.hbox(sel, lang, spacing=12))
        if not sel.value():
            return
        r = si.build(sel.value())
        txt = r["en"] if self.state.get("lang", "en") == "en" else r["zh"]
        tab = r["table"]
        m = Card(T("方法", "Methods"), actions=[W.copy_button(txt)])
        tb = QTextBrowser()
        tb.setObjectName("prose")
        import html
        tb.setHtml("".join(f"<p style='margin:0 0 12px 0;line-height:150%'>{html.escape(x)}</p>" for x in txt.split("\n\n")))
        tb.setMinimumHeight(360)
        m.add(tb)
        t = Card(T("表 S[n]", "Table S[n]"), actions=[W.copy_button(si.table_tsv(tab), T("复制（粘贴到 Excel / Word）", "Copy (paste into Excel / Word)"))])
        t.add(W.Table(tab.drop(columns=["Model"]), max_height=420))
        md = "# EXAFS fitting\n\n" + r["en"] + "\n\n" + si.table_markdown(tab) + "\n\n# EXAFS 拟合\n\n" + r["zh"] + "\n"
        t.add(W.hbox(None, W.button(T("另存 .md…", "Save .md…"), icon_name="download",
                                    slot=lambda: W.save_file_dialog(self, "SI_EXAFS_fitting.md", md.encode("utf-8"))),
                     W.button(T("另存 .csv…", "Save .csv…"), icon_name="download",
                              slot=lambda: W.save_file_dialog(self, "SI_EXAFS_fit_table.csv", tab.to_csv(index=False).encode("utf-8-sig")))))
        t.add(W.label(T("粘贴到 Excel 直接成表；在 Word 中粘贴后用“文本转换成表格”。“S[n]”编号与结构来源请按论文修改。",
                        "Pastes as a table in Excel; in Word use “Convert Text to Table”. Adjust “S[n]” and structure sources to your paper."), "faint"))
        self.add(W.tabs((T("方法", "Methods"), m), (T("表 S[n]", "Table S[n]"), t)))


# ============================================================================= 样品设计
class PlannerPage(Page):
    title_zh, title_en, icon_name = "样品设计", "Sample design", "flask"

    def build(self):
        from xafsmith import mut_planner as xmut
        from xafsmith.common import edge_energy
        self.header(T("透射样品：总 μt 1.5–2.6 最佳，Δμt ≥ 0.2；均匀性比 Δμt 精确匹配更重要。数据：xraydb（Elam 表）。",
                      "Transmission: total μt 1.5–2.6 is best, Δμt ≥ 0.2; uniformity matters more than matching Δμt. Data: xraydb (Elam)."))
        st = self.state
        card = Card(T("压片质量", "Pellet mass"))
        w = dict(formula=W.text(st.get("formula", "IrO2")), el=W.text(st.get("el", "Ir")), ed=W.combo(["K", "L3", "L2", "L1"], st.get("ed", "L3")),
                 area=W.num(st.get("area", 1.327), 0.1, 10, 0.1, 3), dil=W.text(st.get("dil", "BN")), mdil=W.num(st.get("mdil", 100), 0, 1000, 10),
                 tgt=W.num(st.get("tgt", 2.0), 0.5, 4, 0.1), mass=W.num(st.get("mass", 0.0), 0, 1000, 1))
        card.add(W.fields((T("样品化学式", "Formula"), w["formula"]), (T("目标元素", "Element"), w["el"]), (T("吸收边", "Edge"), w["ed"]),
                          (T("压片面积 (cm²)", "Pellet area (cm²)"), w["area"], T("φ13 mm = 1.327 cm²", "φ13 mm = 1.327 cm²"))))
        card.add(W.fields((T("稀释剂（空 = 无）", "Diluent (empty = none)"), w["dil"]), (T("稀释剂质量 (mg)", "Diluent mass (mg)"), w["mdil"]),
                          (T("目标总 μt", "Target total μt"), w["tgt"]), (T("样品质量 (mg，0 = 只推荐)", "Sample mass (mg, 0 = recommend only)"), w["mass"])))
        res = W.vbox()
        card.add(res)
        self.add(card)
        ie = Card(T("干扰吸收边", "Interfering edges"))
        elems = W.text(st.get("elems", "Ir,Ta,Co,O,K"))
        emax = W.num(st.get("emax", 0) or 0, 0, 200000, 100, 0)
        ie.add(W.fields((T("体系中全部元素", "All elements in the system"), elems), (T("扫描上限 (eV)", "Scan end (eV)"), emax)))
        ires = W.vbox()
        ie.add(ires)
        self.add(ie)

        def upd():
            for k, x in w.items():
                st[k] = x.value() if hasattr(x, "value") else x.text()
            st.update(elems=elems.text())
            W._clear_layout(res.layout())
            try:
                r = xmut.recommend_mass(st["formula"], st["area"], st["el"], st["ed"], st["tgt"], st["dil"] or None, st["mdil"])
                res.layout().addWidget(W.metrics((T("推荐样品质量", "Recommended mass"), f"{r['mass_mg']:.2f} mg"),
                                                 (T("边后总 μt", "Total μt above edge"), f"{r['mut_above']:.2f}"),
                                                 (T("边跳 Δμt", "Edge step Δμt"), f"{r['edge_step']:.2f}")))
                res.layout().addWidget(W.label(r["advice"], "muted"))
                if st["mass"] > 0:
                    m = xmut.mut_for_mass(st["formula"], st["mass"], st["area"], st["el"], st["ed"], st["dil"] or None, st["mdil"])
                    res.layout().addWidget(W.Table(pd.DataFrame([{"key": k, "value": v} for k, v in m.items()])))
            except Exception as ex:      # noqa: BLE001
                res.layout().addWidget(Banner("err", str(ex)))
            W._clear_layout(ires.layout())
            try:
                e_end = emax.value() or edge_energy(st["el"], st["ed"]) + 1000
                df = xmut.interfering_edges([e.strip() for e in elems.text().split(",") if e.strip()], st["el"], st["ed"], e_end)
                ires.layout().addWidget(W.Table(df))
            except Exception as ex:      # noqa: BLE001
                ires.layout().addWidget(Banner("err", str(ex)))
        for x in w.values():
            if hasattr(x, "editingFinished"):
                x.editingFinished.connect(upd)
            elif hasattr(x, "currentIndexChanged"):
                x.currentIndexChanged.connect(lambda *_: upd())
        elems.editingFinished.connect(upd)
        emax.editingFinished.connect(upd)
        upd()


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
                         (T("全部数值结果在 output/；分析记录在 notes/", "All numbers are in output/; analysis notes in notes/"), "home"),
                         (T("期刊图在 output/figs/journal/，汇总报告在 output/reports/", "Journal figures in output/figs/journal/, reports in output/reports/"), "summary")):
            c4.add(W.hbox(W.label("•  " + txt), None, W.link(T("打开 →", "Open →"), lambda k=key: self.app.go(k))))
        self.add(c4)


# ============================================================================= 使用指南
class HelpPage(Page):
    title_zh, title_en, icon_name = "使用指南", "Help", "help"

    def build(self):
        from xafsmith import __version__, about, update as xup
        self.header()
        ab = Card()
        ab.add(W.label(f"<b>XAFSmith {__version__}</b> · Agent-ready synchrotron XAFS (XANES / EXAFS) analysis software<br/>"
                       f"<b style='color:{C['accent_text']}'>Developed by Eggy &amp; Claude Opus 5.5</b> (Anthropic)<br/>"
                       "Built on <a href='https://xraypy.github.io/xraylarch/'>xraylarch</a> (FEFF6L, FEFF8L, feffit), xraydb, lmfit, "
                       f"pymatgen, PySide6 and matplotlib · <a href='{about.REPO}'>{about.REPO}</a>", rich=True))
        ab.add(Banner("warn", about.DISCLAIMER_EN if W.en() else about.DISCLAIMER_CN))
        ab.add(W.hbox(W.button(T("免责声明与引用", "Disclaimer & citation"), icon_name="shield", slot=self.app.show_disclaimer), None))
        self.add(ab)
        up = Card(T("检查更新", "Updates"))
        s = xup.load_settings()
        auto = W.check(T("启动时自动检查新版本（只访问 github.com，不发送任何数据）", "Check for updates at start-up (contacts github.com only, sends nothing)"),
                       s.get("check_updates", True))
        auto.toggled.connect(lambda v: xup.save_settings(check_updates=bool(v)))
        res = W.vbox()

        def show(u):
            W._clear_layout(res.layout())
            if u.get("latest") is None:
                res.layout().addWidget(Banner("warn", T("无法连接 GitHub（离线或被网络阻止）。", "Cannot reach GitHub (offline or blocked).")))
            elif u.get("newer"):
                res.layout().addWidget(Banner("ok", T(f"有新版本 {u['latest']}（当前 {u['current']}）", f"New version {u['latest']} (current {u['current']})")))
                if u.get("editable"):
                    res.layout().addWidget(W.label(T("开发安装：请在源码目录用 git pull 更新。", "Development install: update with git pull in the source folder."), "faint"))
                else:
                    b = W.button(T("更新到最新版", "Update now"), primary=True)
                    b.clicked.connect(lambda: W.run_task(self, xup.upgrade, lambda r: res.layout().addWidget(
                        Banner("ok", T("更新完成：请关闭 XAFSmith 并重新打开。", "Updated: close and reopen XAFSmith.")) if r[0]
                        else W.code_block(r[1][-2000:])), T("正在从 GitHub 下载并安装（约 1–5 分钟）…", "Downloading and installing (1–5 min)…"), b))
                    res.layout().addWidget(W.hbox(b, None))
            else:
                res.layout().addWidget(Banner("info", T(f"已是最新版本 {u['current']}", f"Up to date ({u['current']})")))
        btn = W.button(T("现在检查", "Check now"), icon_name="refresh")
        btn.clicked.connect(lambda: W.run_task(self, xup.check, show, T("检查中…", "Checking…"), btn))
        up.add(W.hbox(auto, None, btn))
        up.add(res)
        self.add(up)
        if self.app._update:
            show(self.app._update)
        ddir = Path(__file__).resolve().parent.parent.parent / "docs"
        docs = [(T("XAFS 基础讲义", "XAFS basics"), "XAFS_basics_en.md" if W.en() else "XAFS基础讲义.md"),
                (T("图形界面使用指南", "GUI guide"), "GUI_guide_en.md" if W.en() else "图形界面使用指南.md"),
                (T("零基础拟合教程", "Beginner fitting tutorial"), "fitting_tutorial_en.md" if W.en() else "零基础拟合教程.md"),
                (T("拟合质量提升教程", "Improving fit quality"), "fit_quality_guide_en.md" if W.en() else "拟合质量提升教程.md")]
        tabs = []
        for title, fn in docs:
            tb = QTextBrowser()
            tb.setObjectName("doc")
            tb.setOpenExternalLinks(True)
            tb.setSearchPaths([str(ddir)])           # 讲义中的图片与公式（images/…）
            p = ddir / fn
            tb.setMarkdown(p.read_text(encoding="utf-8") if p.exists() else fn)
            tb.setMinimumHeight(760)
            tb.document().setDefaultStyleSheet(f"h1,h2,h3{{color:{C['text']};}} code{{background:{C['code']};}}")
            tabs.append((title, tb))
        self.add(W.tabs(*tabs))
