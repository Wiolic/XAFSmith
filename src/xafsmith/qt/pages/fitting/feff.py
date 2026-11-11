"""FEFF 路径页面。"""

from __future__ import annotations

from xafsmith import logs
from pathlib import Path
from PySide6.QtWidgets import QFileDialog
from xafsmith import paths
from ... import widgets as W
from ...state import feff_dirs
from ...widgets import T, Banner, Card, Page


class FeffPage(Page):
    title_zh, title_en, icon_name = "FEFF 路径", "FEFF paths", "atom"

    def build(self):
        from xafsmith import feff_wrap as xfeff, structures as xstruct
        self.header(T("由晶体结构计算散射路径。FEFF6L 几秒；FEFF8L 自洽势约 1–3 分钟，ΔE0 通常更接近 0。",
                      "Scattering paths from a crystal structure. FEFF6L takes seconds; FEFF8L (self-consistent) 1–3 min, "
                      "ΔE0 usually closer to 0."))
        card = Card(T("新计算", "New calculation"))
        src = W.Segmented(["dir", "builtin"], self.state.get("src", "dir"),
                          fmt=lambda s: {"dir": T("structures/ 文件夹", "structures/ folder"), "builtin": T("内置结构", "Built-in")}[s])
        src.changed.connect(lambda v: (self.state.__setitem__("src", v), self.refresh()))

        def upload():
            fs, _ = QFileDialog.getOpenFileNames(self, T("选择结构文件", "Choose structure files"), str(Path.home()),
                                                 "Structures (*.cif *.vasp *.poscar POSCAR CONTCAR);;All (*.*)")
            import shutil
            paths.STRUCT.mkdir(parents=True, exist_ok=True)
            for f in fs:
                shutil.copy2(f, paths.STRUCT / Path(f).name)
            if fs:
                self.state["src"] = "dir"
                self.refresh()

        def export_builtin():
            W.toast(self, ", ".join(p.name for p in xstruct.export_builtin()))
            self.refresh()
        card.add(W.hbox(src, None, W.button(T("添加结构文件…", "Add structure files…"), icon_name="upload", slot=upload),
                        W.button(T("内置结构导出为 CIF", "Export built-ins as CIF"), slot=export_builtin)))
        try:
            if self.state.get("src", "dir") == "builtin":
                name = W.combo(xstruct.BUILTIN_NAMES, self.state.get("bname"))
                nm = name.value()
                struct = xstruct.builtin(nm)
                note = xstruct.SOURCES[nm]
                name.currentIndexChanged.connect(lambda *_: (self.state.__setitem__("bname", name.value()), self.refresh()))
                pick = W.field(T("结构", "Structure"), name)
            else:
                files = xstruct.list_structures()
                if not files:
                    card.add(Banner("info", T("structures/ 中还没有结构文件：点“添加结构文件…”，或改用内置结构。",
                                              "No files in structures/: click “Add structure files…” or use a built-in.")))
                    self.add(card)
                    self._existing()
                    return
                fn = W.combo(files, self.state.get("file"))
                nm = Path(fn.value()).stem
                struct = xstruct.read_structure(fn.value())
                note = ""
                fn.currentIndexChanged.connect(lambda *_: (self.state.__setitem__("file", fn.value()), self.refresh()))
                pick = W.field(T("结构文件", "Structure file"), fn)
        except Exception as ex:      # noqa: BLE001
            logs.log.warning("qt.pages.fitting.export_builtin 出错（已忽略或已提示）", exc_info=True)
            card.add(Banner("err", str(ex)))
            self.add(card)
            return
        info = f"{struct.composition}   {T('空间群', 'space group')}: {struct.get_space_group_info()}" + (f"   ·   {note}" if note else "")
        elems = sorted(set(s.specie.symbol for s in struct))
        # 吸收原子按结构分别记住；默认取最重的元素（通常就是要测的金属）
        from pymatgen.core import Element
        heavy = max(elems, key=lambda e: Element(e).Z)
        akey = f"abs_{nm}"
        absorber = W.combo(elems, self.state.get(akey) if self.state.get(akey) in elems else heavy)
        z = Element(absorber.value()).Z
        edge = W.combo(["K", "L3", "L2", "L1"], self.state.get(f"edge_{nm}") or ("K" if z <= 40 else "L3"))
        sites = xfeff.inequivalent_sites(struct, absorber.value())
        site = W.combo(sites, None, fmt=lambda s: f"site {s[0]} ×{s[1]}")
        rmax = W.tag(W.num(6.0, 2, 10, 0.5), "feff_rmax")
        nleg = W.combo([2, 3, 4], 4)
        code = W.Segmented(["feff6", "feff8"], self.state.get("code", "feff6"), fmt=lambda c: c.upper().replace("FEFF", "FEFF") + "L")
        scf = W.tag(W.num(4.5, 2.5, 7, 0.5), "feff_scf")
        exch = W.combo(list(xfeff.EXCHANGE), 0, fmt=lambda i: f"{i}: {xfeff.EXCHANGE[i]}")
        out = W.tag(W.text(""), "feff_out")

        def upd_out(*_):
            self.state.update({akey: absorber.value(), f"edge_{nm}": edge.value(), "code": code.value()})
            sfx = "_feff8" if code.value() == "feff8" else ""
            s = site.value() or (0, 1)
            out.setText(f"{paths.rel(paths.FEFF)}/{nm}_{absorber.value()}{edge.value()}{sfx}/site{s[0]}")
            f8.setVisible(code.value() == "feff8")
        absorber.currentIndexChanged.connect(lambda *_: (self.state.__setitem__(akey, absorber.value()),
                                                         self.state.pop(f"edge_{nm}", None), self.refresh()))
        edge.currentIndexChanged.connect(upd_out)
        site.currentIndexChanged.connect(upd_out)
        code.changed.connect(upd_out)
        card.add(W.fields(pick, (T("吸收原子", "Absorber"), absorber), (T("吸收边", "Edge"), edge),
                          (T("不等价位点", "Inequivalent site"), site), ("RMAX (Å)", rmax), ("NLEG", nleg), cols=6)
                 if False else W.hbox(pick, W.field(T("吸收原子", "Absorber"), absorber), W.field(T("吸收边", "Edge"), edge),
                                      W.field(T("不等价位点", "Site"), site), W.field("RMAX (Å)", rmax), W.field("NLEG", nleg), spacing=12))
        card.add(W.label(info, "faint"))
        f8 = W.fields((T("SCF 自洽半径 (Å)", "SCF radius (Å)"), scf, T("一般包含 2–3 个壳层（约 30–60 个原子）；越大越慢",
                                                                       "Usually 2–3 shells (~30–60 atoms); larger is slower")),
                      (T("交换势 EXCHANGE", "Exchange potential"), exch))
        card.add(W.hbox(W.field(T("FEFF 版本", "FEFF version"), code), spacing=12))
        card.add(f8)
        card.add(W.field(T("输出目录", "Output folder"), out))
        run = W.button(T("运行 FEFF", "Run FEFF"), primary=True, icon_name="play")

        def go():
            c = code.value()
            s = site.value()
            W.run_task(self, lambda: xfeff.build(struct, absorber.value(), edge.value(), paths.ROOT / out.text(), site_index=s[0],
                                                 rmax=rmax.value(), nleg=nleg.value(), title=nm, code=c, scf=scf.value(),
                                                 exchange=exch.value()),
                       lambda df: (W.toast(self, T(f"完成：{len(df)} 条路径 → {out.text()}", f"Done: {len(df)} paths → {out.text()}")),
                                   self.state.__setitem__("dir", str(paths.ROOT / out.text())), self.refresh()),
                       T("FEFF 运行中…（FEFF8L 约 1–3 分钟）", "Running FEFF… (FEFF8L 1–3 min)") if c == "feff8" else T("FEFF 运行中…", "Running FEFF…"),
                       run)
        run.clicked.connect(go)
        card.add(W.label(T("注意：FEFF6L 与 FEFF8L 的 ΔE0 零点不同。换 FEFF 版本后，固定 e0 的模型要重新确定 e0。",
                            "Note: FEFF6L and FEFF8L have different ΔE0 zeros. After switching, re-determine e0 for models that fix it."),
                          "faint"))
        card.add(W.hbox(None, run))
        upd_out()
        self.add(card)
        self._existing()

    def _existing(self):
        from xafsmith import feff_wrap as xfeff
        dirs = feff_dirs()
        card = Card(T("已有计算", "Existing calculations"))
        if not dirs:
            card.add(W.label(T("还没有。", "None yet."), "faint"))
            self.add(card)
            return
        cur = self.state.get("dir")
        d = W.combo(dirs, Path(cur) if cur and Path(cur) in dirs else dirs[-1], fmt=lambda p: str(p.relative_to(paths.ROOT)))
        d.currentIndexChanged.connect(lambda *_: (self.state.__setitem__("dir", str(d.value())), self.refresh()))
        card.add(d)
        dd = d.value()
        info = xfeff.feff_info(dd)
        card.add(W.label(T(f"FEFF8L 自洽势：SCF 半径 {info['scf']} Å，交换势 {info['exchange']}，费米能 {info['fermi_ev']} eV",
                           f"FEFF8L self-consistent: SCF radius {info['scf']} Å, exchange {info['exchange']}, Fermi level {info['fermi_ev']} eV")
                         if info["code"] == "feff8" else T("FEFF6L（非自洽势）", "FEFF6L (non-self-consistent)"), "muted"))
        card.add(W.Table(xfeff.list_paths(dd).drop(columns=["file"]), max_height=400))
        inp = dd / "feff.inp"
        if inp.exists():
            card.add(W.collapsible("feff.inp", W.code_block(inp.read_text(encoding="utf-8"), height=300)))
        self.add(card)
