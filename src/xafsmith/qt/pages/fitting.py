"""结构与拟合：FEFF 路径、EXAFS 拟合（诊断、稳健性）、拟合历史与 F 检验、LCF、XANES 定量"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
from PySide6.QtWidgets import QFileDialog, QTextBrowser, QWidget

from xafsmith import paths
from .. import widgets as W
from ..state import (feff_dirs, fit_label, has_chi, idents, load_model, run_model, safe, save_fit, saved_models)
from ..theme import C
from ..widgets import T, Banner, Card, Page
from .process import rlabel


# ============================================================================= FEFF
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
        card.add(W.hbox(W.label(T("FEFF6L 与 FEFF8L 的 ΔE0 零点不同：换版本后，固定 e0 的模型要重新确定 e0。",
                                  "FEFF6L and FEFF8L have different ΔE0 zeros: re-determine e0 for models that fix it."), "faint"), None, run))
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
            card.add(W.collapsible("feff.inp", W.code_block(inp.read_text(), height=300)))
        self.add(card)


# ============================================================================= 拟合质量
FIT_GUIDE_ZH = """
<p><b>拟合前</b></p>
<ul>
<li><b>先标样、后样品</b>：在结构已知的标样上拟合得到 S0²（通常 0.7–1.0），样品中固定为这个值（在“校准与处理 → 处理参数”中记录来源）。
S0² 与配位数 N 完全相关，两者不能同时自由。</li>
<li><b>数据范围</b>：k 范围按全组最差样品的信噪比定，全组相同；R 窗口只包含要拟合的壳层。先看独立点数 N_idp = 2ΔkΔR/π。</li>
<li><b>变量数</b> ≤ N_idp/2（最好 ≤ N_idp − 3）。参数不够时用约束：相近壳层共用 ΔE0，多重散射路径的 σ²、ΔR 与对应单散射绑定。</li>
<li><b>同时用 k¹、k²、k³ 拟合</b>（k 权重多选），可降低 N–σ²、ΔE0–ΔR 的相关性。</li>
<li><b>从简单到复杂</b>：先第一壳层，再逐条加路径；每加一条都与前一个模型做 F 检验。</li>
</ul>
<p><b>怎样算拟合得好</b>（拟合后，结果下方的“拟合质量检查”会逐条判断）</p>
<ul>
<li><b>R 因子</b>：&lt; 0.02 很好；0.02–0.05 对第一壳层可接受；&gt; 0.05 说明模型或数据有问题。R 因子随窗口变宽而变大，只在相同范围之间比较。</li>
<li><b>残差 / 噪声</b>（拟合诊断）：≈ 1–2 表示已到数据极限；明显大于 2 说明还有系统偏差。</li>
<li><b>χ²_ν</b>：绝对值依赖噪声估计，常远大于 1；用来比较<b>同一数据、同一范围</b>下的不同模型（明显下降才有意义）。</li>
<li><b>参数物理合理</b>：|ΔE0| ≤ 10 eV；σ² &gt; 0，一般 0.001–0.02 Å²（室温第一壳层多为 0.002–0.010）；ΔR 不应偏离 FEFF 结构超过约 0.2 Å；
N 在合理范围内且误差明显小于数值。</li>
<li><b>误差可估</b>：每个变量都有误差；误差大于数值本身，说明数据不能确定这个参数，应固定或约束。</li>
<li><b>不卡边界</b>：参数停在设定的上下限上，说明是限制在起作用，结果不可信。</li>
<li><b>相关系数</b> |r| &gt; 0.9 的参数对要在结论中说明（典型：N–σ²、S0²–N、ΔE0–ΔR）。</li>
<li><b>图上</b>：窗口内 |χ(R)| 与 Re χ(R) 都要对上，Re 对上比 |χ(R)| 对上更严格；k 空间残差不集中在某一段。</li>
<li><b>稳健</b>：改变 kmin、kmax、Rmax 与 k 权重后结论不变（稳健性检查）。</li>
</ul>
<p>“严丝合缝”不是目标：残差已接近噪声时，再加参数只是在拟合噪声。详见“使用指南 → 拟合质量提升教程”。</p>
"""
FIT_GUIDE_EN = """
<p><b>Before fitting</b></p>
<ul>
<li><b>Standard first, then samples</b>: fit S0² on a standard of known structure (usually 0.7–1.0) and fix it for the samples
(record the source under “Calibrate &amp; process → Processing parameters”). S0² and N are fully correlated; never vary both.</li>
<li><b>Ranges</b>: choose the k range from the worst sample of the series and use it for all; the R window should contain only the
shells you fit. Check N_idp = 2ΔkΔR/π first.</li>
<li><b>Variables</b> ≤ N_idp/2 (preferably ≤ N_idp − 3). When information is short, constrain: a shared ΔE0 for close shells,
σ² and ΔR of multiple-scattering paths tied to the matching single-scattering path.</li>
<li><b>Fit k¹, k² and k³ together</b> (select several k-weights) to reduce N–σ² and ΔE0–ΔR correlations.</li>
<li><b>Simple to complex</b>: first shell first, then add paths one at a time, F-testing each against the previous model.</li>
</ul>
<p><b>What counts as a good fit</b> (after fitting, “Fit quality check” below the result checks each point)</p>
<ul>
<li><b>R-factor</b>: &lt; 0.02 very good; 0.02–0.05 acceptable for a first shell; &gt; 0.05 points to a problem with the model or
the data. It grows with the window, so compare only fits over the same ranges.</li>
<li><b>Residual / noise</b> (fit diagnosis): ≈ 1–2 means the data limit is reached; well above 2 means a systematic residual.</li>
<li><b>χ²_ν</b>: its absolute value depends on the noise estimate and is often ≫ 1; use it to compare models on <b>the same data and
ranges</b> (only a clear drop matters).</li>
<li><b>Physical parameters</b>: |ΔE0| ≤ 10 eV; σ² &gt; 0, typically 0.001–0.02 Å² (first shells at room temperature mostly
0.002–0.010); ΔR within about 0.2 Å of the FEFF structure; N plausible, with an error clearly smaller than its value.</li>
<li><b>Errors defined</b>: every variable has an error; an error larger than the value means the data cannot determine that
parameter — fix or constrain it.</li>
<li><b>Not at a bound</b>: a parameter sitting on its min / max is held by the limit, not by the data.</li>
<li><b>Correlations</b> with |r| &gt; 0.9 should be reported (typical: N–σ², S0²–N, ΔE0–ΔR).</li>
<li><b>Plots</b>: both |χ(R)| and Re χ(R) match inside the window — matching Re is stricter; the k-space residual is not
concentrated in one region.</li>
<li><b>Robust</b>: conclusions survive changes of kmin, kmax, Rmax and k-weight (robustness check).</li>
</ul>
<p>A “perfect” match is not the goal: once the residual is near the noise, extra parameters only fit noise. See
“Help → Improving fit quality”.</p>
"""


def quality_checks(fit, dg=None):
    """[(True/False/None, 文字)]：True 通过，False 需注意，None 仅提示"""
    s, md = fit["summ"], fit["model"]
    out = []
    rf = s["rfactor"]
    if rf < 0.02:
        out.append((True, T(f"R 因子 {rf:.4f} &lt; 0.02：很好", f"R-factor {rf:.4f} &lt; 0.02: very good")))
    elif rf <= 0.05:
        out.append((True, T(f"R 因子 {rf:.4f}（0.02–0.05）：第一壳层可接受", f"R-factor {rf:.4f} (0.02–0.05): acceptable for a first shell")))
    else:
        out.append((False, T(f"R 因子 {rf:.4f} &gt; 0.05：检查模型、R 窗口与数据", f"R-factor {rf:.4f} &gt; 0.05: check the model, R window and data")))
    nv, ni = s["nvarys"], s["n_idp"]
    ok = nv <= ni / 2
    out.append((ok, T(f"变量数 {nv}，N_idp/2 = {ni / 2:.1f}", f"{nv} variables, N_idp/2 = {ni / 2:.1f}")
                + ("" if ok else T("：变量太多，请固定或约束参数", ": too many; fix or constrain some"))))
    if dg is not None:
        r = dg["ratio"]
        out.append((r <= 2.5, T(f"残差 / 噪声 = {r:.1f}", f"Residual / noise = {r:.1f}")
                    + (T("：已接近数据极限", ": close to the data limit") if r <= 2.5
                       else T("：残差是系统性的（见下方拟合诊断）", ": systematic residual (see fit diagnosis)"))))
    P = s["params"]
    mpar = md.get("params", {})
    for name, v in P.items():
        if not v["vary"] or v["expr"]:
            continue
        val, err = v["value"], v["stderr"]
        if err is None:
            out.append((False, T(f"{name}：误差无法估计（参数可能过多或高度相关）",
                                 f"{name}: error could not be estimated (too many or strongly correlated parameters)")))
        elif abs(err) > abs(val) and not name.lower().startswith(("e0", "de", "dr", "del")):
            out.append((False, T(f"{name} = {val:.4g} ± {err:.2g}：误差大于数值，数据不能确定它",
                                 f"{name} = {val:.4g} ± {err:.2g}: error exceeds the value; not determined by the data")))
        spec = mpar.get(name)
        if isinstance(spec, dict):
            lo, hi = spec.get("min"), spec.get("max")
            span = (hi - lo) if (lo is not None and hi is not None) else max(abs(val), 1e-3)
            for b, lab in ((lo, "min"), (hi, "max")):
                if b is not None and abs(val - b) <= 0.01 * span:
                    out.append((False, T(f"{name} 停在边界 {lab} = {b:g}：由限制而非数据决定",
                                         f"{name} sits at its {lab} = {b:g}: held by the bound, not the data")))
    e0s = [(k, v["value"]) for k, v in P.items() if "e0" in k.lower() and v["vary"] and not v["expr"]]
    if e0s:
        bad = [f"{k} = {x:.1f}" for k, x in e0s if abs(x) > 10]
        out.append((not bad, (T("ΔE0 超出 ±10 eV：", "ΔE0 beyond ±10 eV: ") + ", ".join(bad)) if bad
                    else T("ΔE0 在 ±10 eV 以内", "ΔE0 within ±10 eV")))
    ss = [(p["path"], p["sigma2"]) for p in s["paths"]]
    neg = [f"{a}: {b:.4f}" for a, b in ss if b <= 0]
    big = [f"{a}: {b:.4f}" for a, b in ss if b > 0.03]
    if neg:
        out.append((False, T("σ² ≤ 0（非物理）：", "σ² ≤ 0 (unphysical): ") + "; ".join(neg)))
    if big:
        out.append((False, T("σ² &gt; 0.03 Å²（很大，可能在补偿 N 或别的路径）：",
                             "σ² &gt; 0.03 Å² (very large; may be compensating N or another path): ") + "; ".join(big)))
    if not neg and not big:
        out.append((True, T("所有路径 σ² 为正且不过大", "All σ² positive and not excessive")))
    dr = [f"{p['path']}: {p['deltar']:+.3f} Å" for p in s["paths"] if abs(p["deltar"]) > 0.2]
    out.append((not dr, (T("ΔR 超过 0.2 Å，结构模型可能不合适：", "ΔR beyond 0.2 Å; the structural model may not fit: ") + "; ".join(dr))
                if dr else T("所有路径 |ΔR| ≤ 0.2 Å", "All paths |ΔR| ≤ 0.2 Å")))
    try:
        pars = fit["result"].params
        seen, hi = set(), []
        for a, pa in pars.items():
            if a not in P or not pa.vary or not pa.correl:
                continue
            for b, r in pa.correl.items():
                if b in P and abs(r) > 0.9 and (b, a) not in seen:
                    seen.add((a, b))
                    hi.append(f"{a}–{b}: {r:+.2f}")
        out.append((not hi, (T("强相关（|r| &gt; 0.9），结论中要说明：", "Strong correlations (|r| &gt; 0.9) to report: ") + "; ".join(hi))
                    if hi else T("没有 |r| &gt; 0.9 的强相关参数对", "No parameter pair with |r| &gt; 0.9")))
    except Exception:
        pass
    kws = md.get("kweight")
    if not (isinstance(kws, list) and len(kws) > 1):
        out.append((None, T("只用了单一 k 权重：同时拟合 k¹、k²、k³ 能降低相关性",
                            "Single k-weight: fitting k¹, k², k³ together reduces correlations")))
    if fit.get("robust") is None:
        out.append((None, T("尚未运行稳健性检查（见下方）", "Robustness check not run yet (below)")))
    return out


# ============================================================================= 拟合结果视图
class FitView(QWidget):
    """一个拟合的结果：指标、参数、路径、k / R 图、报告、保存、诊断、稳健性"""
    def __init__(self, page, fit, key=""):
        super().__init__()
        self.page, self.fit = page, fit
        S = page.S
        s, c, md = fit["summ"], fit["curves"], fit["model"]
        lay = W.QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(14)
        card = Card(T(f"拟合结果 · {s['model']}", f"Fit result · {s['model']}"))
        card.add(W.metrics((T("R 因子", "R-factor"), f"{s['rfactor']:.4f}"), ("χ²_ν", f"{s['chi2_reduced']:.1f}"),
                           ("N_idp", f"{s['n_idp']:.1f}"), (T("变量数", "Variables"), s["nvarys"]),
                           (T("样品", "Sample"), s["sample"])))
        for w_ in s["warnings"]:
            card.add(Banner("warn", w_))
        pt = pd.DataFrame([{T("参数", "Parameter"): k, T("值", "Value"): v["value"], T("误差", "Error"): v["stderr"],
                            T("变化", "Vary"): v["vary"], T("表达式", "Expr"): v["expr"]} for k, v in s["params"].items()])
        card.add(W.Table(pt, max_height=320))
        card.add(W.Table(pd.DataFrame(s["paths"]), max_height=320))
        kw = W.combo([1, 2, 3], page.state.get("kwshow", 2))
        plot = W.Plot(380, 1, 2)
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
            a2.plot(gf.r, gf.chir_re, color="#B5487A", lw=0.9, ls="--", label=T("Re 拟合", "Re fit"))
            a2.axvspan(md["rmin"], md["rmax"], color=C["text3"], alpha=0.1, lw=0)
            a2.set_xlim(0, 6)
            a2.set_xlabel(rlabel())
            plot.draw()
            self._kw = k
        kw.currentIndexChanged.connect(lambda *_: draw())
        draw()

        def save():
            base = save_fit(fit)
            W.toast(page, T(f"已保存：output/fits/exafs_fits.csv、models/{base}.json、报告与拟合图",
                            f"Saved: output/fits/exafs_fits.csv, models/{base}.json, report and figure"))
        card.add(W.hbox(W.collapsible(T("完整拟合报告", "Full fit report"), W.code_block(fit["report"], height=320)), None,
                        W.button(T("保存结果", "Save result"), primary=True, icon_name="save", slot=save)))
        lay.addWidget(card)
        lay.addWidget(self._quality())
        lay.addWidget(self._diagnose())
        lay.addWidget(self._robust())

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
                self._dg_cache = ex
        return self._dg_cache

    def _quality(self):
        card = Card(T("拟合质量检查", "Fit quality check"))
        self._quality_card = card
        dg = self._dg()
        for state, txt in quality_checks(self.fit, None if isinstance(dg, Exception) else dg):
            col, mark = {True: (C["ok"], "✓"), False: (C["warn"], "⚠"), None: (C["text3"], "•")}[state]
            card.add(W.label(f'<span style="color:{col};font-weight:700">{mark}</span>&nbsp;&nbsp;{txt}', rich=True))
        card.add(W.label(T("这些是必要条件，不是充分条件：新增的壳层还要通过“拟合历史”中的 F 检验（p &lt; 0.05），并在稳健性检查中稳定。",
                           "These are necessary, not sufficient: an added shell must also pass the F-test in “Fit history” "
                           "(p &lt; 0.05) and stay stable in the robustness check."), "faint", rich=True))
        return card

    def _diagnose(self):
        fit = self.fit
        body = Card(flat=True)
        dg = self._dg()
        if isinstance(dg, Exception):
            body.add(Banner("err", str(dg)))
            return W.collapsible(T("拟合诊断：残差在哪里、为什么对不上", "Fit diagnosis: where is the residual and why"), body)
        body.add(W.metrics((T("窗口内残差 RMS", "Residual RMS in window"), f"{dg['resid_R']:.4f}"),
                           (T("白噪声估计 (R 15–25 Å)", "White noise (R 15–25 Å)"), f"{dg['noise_R']:.4f}"),
                           (T("残差 / 噪声", "Residual / noise"), f"{dg['ratio']:.1f}")))
        for h in dg["hints"]:
            body.add(Banner("info", h))
        c, md, kw = fit["curves"], fit["model"], getattr(self, "_kw", 2)
        p = W.Plot(300)
        p.ax.plot(c["k"], c["chi"] * c["k"] ** kw, color=C["text"], lw=1, label=T("数据", "data"))
        p.ax.plot(dg["k"], dg["resid_k"], color=C["accent"], lw=1, label=T("残差", "residual"))
        p.ax.axvspan(md["kmin"], md["kmax"], color="#C29A1C", alpha=0.08, lw=0)
        for kk, _, _ in dg["spikes"]:
            p.ax.axvline(kk, color="#B5487A", ls=":", lw=1)
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
        return W.collapsible(T("拟合诊断：残差在哪里、为什么对不上", "Fit diagnosis: where is the residual and why"), body)

    def _robust(self):
        fit, page = self.fit, self.page
        body = Card(flat=True)
        out = W.vbox()
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

        def go():
            from xafsmith import fit_exafs as fx, pipeline as pl
            g = page.S.groups.get(fit["summ"]["sample"])

            def work(progress):
                gg = g
                if gg is None:
                    gg, _ = pl.build_sample(fit["summ"]["sample"])
                return fx.robustness(gg, fit["model"], progress=lambda f, n: progress(f, n))
            W.run_task(page, work, lambda r: (fit.__setitem__("robust", r), show()), T("稳健性检查…", "Robustness…"), btn, progress=True)
        btn.clicked.connect(go)
        body.add(W.hbox(None, btn))
        body.add(out)
        if fit.get("robust"):
            show()
        return W.collapsible(T("稳健性检查：改变拟合条件重复拟合", "Robustness check: refit under varied conditions"), body,
                             expanded=bool(fit.get("robust")))


# ============================================================================= EXAFS 拟合
class FitPage(Page):
    title_zh, title_en, icon_name = "EXAFS 拟合", "EXAFS fitting", "fit"

    def build(self):
        S = self.S
        self.header(T("先在标样上确定 S0²，样品中固定；加壳层要通过 F 检验。变量数 ≤ N_idp/2。",
                      "Determine S0² on the standard and fix it for samples; added shells must pass the F-test. Variables ≤ N_idp/2."))
        tb = QTextBrowser()
        tb.setObjectName("doc")
        tb.setHtml(FIT_GUIDE_EN if W.en() else FIT_GUIDE_ZH)
        tb.setMinimumHeight(600)
        self.add(W.collapsible(T("注意事项与“拟合得好”的标准", "Before you fit, and what counts as a good fit"), tb,
                               expanded=not S.fits))
        self.add(self._saved())
        cands = [k for k, g in S.groups.items() if has_chi(g)]
        dirs = feff_dirs()
        if not cands or not dirs:
            self.add(Banner("info", T("需要：已载入并算出 χ(k) 的数据（载入谱 / χ(k) 与 FT）与 FEFF 计算（FEFF 路径）。",
                                      "Needs data with χ(k) (Load spectra / χ(k) & FT) and a FEFF calculation (FEFF paths).")))
            if S.fits:
                self.add(FitView(self, S.fits[-1], "last"))
            return
        # 1 数据与路径来源
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
        c1.add(W.hbox(W.field(T("数据", "Data"), data), W.field(T("FEFF 目录", "FEFF folders"), fdirs), spacing=12))
        c1.lay.itemAt(c1.lay.count() - 1).widget().layout().setStretch(1, 2)
        self.add(c1)
        sel_dirs = fdirs.value()
        if not sel_dirs:
            if S.fits:
                self.add(FitView(self, S.fits[-1], "last"))
            return
        self._model_cards(data.value(), sel_dirs)
        if S.fits:
            self.add(FitView(self, S.fits[-1], "last"))

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
                msmp = json.loads((paths.MODELS / mf.value()).read_text(encoding="utf-8")).get("sample", "")
            except Exception:
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
                W.toast(self, T(f"完成 {len(fits)} 个拟合（见下方与“拟合历史”）", f"{len(fits)} fit(s) done (below and in “Fit history”)"))
                self.refresh()
            W.run_task(self, work, done, T("拟合中…", "Fitting…"), btn, progress=True)
        btn.clicked.connect(go)
        body.add(W.hbox(W.field(T("模型", "Model"), mf), W.field(T("样品", "Samples"), smp), W.vbox(None, btn), spacing=12))
        return W.collapsible(T(f"运行已保存的模型（models/ 中 {len(models)} 个）", f"Run a saved model ({len(models)} in models/)"), body,
                             expanded=self.state.get("saved_open", False))

    def _model_cards(self, data_k, fdirs):
        from xafsmith import feff_wrap as xfeff, fit_exafs as xfit
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
        c2.add(W.fields(("kmin", w["kmin"]), ("kmax", w["kmax"]), ("dk", w["dk"]), (T("窗", "Window"), w["win"]),
                        (T("k 权重", "k-weights"), w["kws"]), ("Rmin", w["rmin"]), ("Rmax", w["rmax"]),
                        (T("拟合空间", "Fit space"), w["space"])))
        nid = W.label("", rich=True)
        c2.add(nid)
        self.add(c2)
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
        c3.add(W.label(T("勾选使用；N 留空 = FEFF 简并度；N、s02、e0、deltar、sigma2 都可以写表达式（如 ss1*1.5）。双击单元格修改。",
                         "Tick to use; empty N = FEFF degeneracy; N, s02, e0, deltar, sigma2 accept expressions (e.g. ss1*1.5). "
                         "Double-click to edit."), "faint"))
        ptab = W.Table(self.state[key], editable=["use", "label", "N", "s02", "e0", "deltar", "sigma2", "third"],
                       bools=["use"], max_height=360)
        ptab.hide_cols("file")
        c3.add(ptab)
        self.add(c3)
        # 4 参数
        c4 = Card(T("4  参数", "4  Parameters"))
        c4.add(W.label(T("vary 不勾 = 固定；expr 非空 = 约束。", "Untick vary = fixed; non-empty expr = constrained."), "faint"))
        holder = W.vbox()
        c4.add(holder)
        nv = W.label("", rich=True)
        c4.add(nv)
        self.add(c4)
        defaults = {"s02": (0.85, True, 0.3, 1.5), "e0": (0.0, True, -15, 15)}
        cur = {}

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
            t = W.Table(df, editable=["value", "vary", "min", "max", "expr"], bools=["vary"], max_height=320)
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
        # 拟合
        names, used = names_used()
        mname = W.text(self.state.get("mname_" + data_k, f"{Path(data_k).name}_{len(used)}paths"))
        mname.textChanged.connect(lambda s: self.state.__setitem__("mname_" + data_k, s))
        btn = W.button(T("拟合", "Fit"), primary=True, icon_name="play")

        def go():
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
                self.refresh()
            W.run_task(self, lambda: run_model(S, model, S.groups[data_k]), done, T("拟合中…", "Fitting…"), btn)
        btn.clicked.connect(go)
        self.add(W.hbox(W.field(T("模型名", "Model name"), mname), None, W.vbox(None, btn), spacing=12))


# ============================================================================= 拟合历史
class HistoryPage(Page):
    title_zh, title_en, icon_name = "拟合历史", "Fit history", "history"

    def build(self):
        from xafsmith import fit_exafs as xfit
        S = self.S
        self.header(T("本次会话的全部拟合；嵌套模型用 Hamilton F 检验比较，p < 0.05 才能说新增的壳层显著。",
                      "All fits of this session; compare nested models with the Hamilton F-test — only p < 0.05 makes an added shell significant."))
        if not S.fits:
            self.add(Banner("info", T("暂无拟合。", "No fits yet.")))
            return
        card = Card(T("拟合", "Fits"))
        rows = [dict(i=i + 1, time=f["time"], sample=f["summ"]["sample"], model=f["summ"]["model"], rfactor=f["summ"]["rfactor"],
                     chi2r=f["summ"]["chi2_reduced"], nvarys=f["summ"]["nvarys"], n_idp=f["summ"]["n_idp"]) for i, f in enumerate(S.fits)]
        card.add(W.Table(pd.DataFrame(rows), max_height=320))

        def save_all():
            for f in S.fits:
                save_fit(f)
            W.toast(self, T(f"已保存 {len(S.fits)} 个拟合", f"{len(S.fits)} fits saved"))
        card.add(W.hbox(None, W.button(T("全部保存到 output/fits/（汇总与 SI 会用到）", "Save all to output/fits/ (used by summary and SI)"),
                                       icon_name="save", slot=lambda: W.wait_cursor(save_all))))
        self.add(card)
        ft = Card(T("F 检验（Hamilton）", "F-test (Hamilton)"))
        idx = list(range(len(S.fits)))
        a = W.combo(idx, self.state.get("a", 0), fmt=lambda i: fit_label(S.fits[i]))
        b = W.combo(idx, self.state.get("b", len(S.fits) - 1), fmt=lambda i: fit_label(S.fits[i]))
        out = W.vbox()

        def go():
            self.state.update(a=a.value(), b=b.value())
            r = xfit.hamilton_test(S.fits[a.value()]["result"], S.fits[b.value()]["result"])
            W._clear_layout(out.layout())
            out.layout().addWidget(W.Table(pd.DataFrame([{"key": k, "value": str(v)} for k, v in r.items()])))
        ft.add(W.hbox(W.field(T("简单模型", "Simpler model"), a), W.field(T("复杂模型", "More complex model"), b),
                      W.vbox(None, W.button(T("比较", "Compare"), primary=True, slot=go)), spacing=12))
        ft.add(out)
        self.add(ft)
        view = W.combo(idx, self.state.get("view", len(S.fits) - 1), fmt=lambda i: fit_label(S.fits[i]))
        view.currentIndexChanged.connect(lambda *_: (self.state.__setitem__("view", view.value()), self.refresh()))
        self.add(W.hbox(W.label(T("查看拟合", "View fit"), "h3"), view, None))
        self.add(FitView(self, S.fits[view.value()], f"h{view.value()}"))


# ============================================================================= LCF
class LCFPage(Page):
    title_zh, title_en, icon_name = "LCF", "LCF", "layers"

    def build(self):
        from xafsmith import fit_lcf as xlcf
        from xafsmith.common import append_csv
        from ..state import ensure_norm, process
        S = self.S
        self.header(T("线性组合拟合。端点必须是实测标样；同时与“只用单一标样”的拟合比较。",
                      "Linear combination fitting. End-members must be measured standards; compare with single-standard fits."))
        if len(S.groups) < 2:
            self.add(Banner("info", T("至少需要两条谱（载入谱）。", "Needs at least two spectra (Load spectra).")))
            return
        for g in S.groups.values():
            try:
                ensure_norm(S, g)
            except Exception:
                pass
        card = Card()
        keys = list(S.groups)
        smp = W.combo(keys, self.state.get("smp"))
        stds = W.MultiSelect([k for k in keys], self.state.get("stds", []), T("端点标样（实测）", "Standards (measured)"))
        space = W.combo(["norm", "dmude", "chik"], self.state.get("space", "norm"))
        lo, hi = W.num(self.state.get("lo", -20.0), -500, 500, 1), W.num(self.state.get("hi", 30.0), -500, 500, 1)

        def sp_changed():
            if space.value() == "chik":
                lo.setValue(3.0); hi.setValue(10.0)
            else:
                lo.setValue(-20.0); hi.setValue(30.0)
        space.currentIndexChanged.connect(lambda *_: sp_changed())
        s1, bd, es = W.check(T("权重和 = 1", "Σw = 1"), True), W.check("0 ≤ w ≤ 1", True), W.check(T("拟合能量平移", "Fit E shift"), False)
        note = W.text("", T("使用非实测端点时必须在此注明为假设", "If an end-member is not measured, state the assumption here"))
        card.add(W.hbox(W.field(T("样品", "Sample"), smp), W.field(T("标样", "Standards"), stds), spacing=12))
        card.add(W.hbox(W.field(T("空间", "Space"), space), W.field(T("下限（E−E0 或 k）", "From (E−E0 or k)"), lo),
                        W.field(T("上限", "To"), hi), W.vbox(None, s1), W.vbox(None, bd), W.vbox(None, es), spacing=12))
        card.add(W.field(T("备注", "Note"), note))
        btn = W.button("LCF", primary=True, icon_name="play")

        def go():
            st_ = [k for k in stds.value() if k != smp.value()]
            if not st_:
                return
            self.state.update(smp=smp.value(), stds=stds.value(), space=space.value(), lo=lo.value(), hi=hi.value())
            if space.value() == "chik":
                for k in [smp.value()] + st_:
                    if not has_chi(S.groups[k]):
                        process(S, S.groups[k], norm=False, ft=False)
            G = S.groups
            r = xlcf.lcf(G[smp.value()], [G[k] for k in st_], xmin=lo.value(), xmax=hi.value(), space=space.value(),
                         sum_to_one=s1.isChecked(), bounds=bd.isChecked(), fit_eshift=es.isChecked(), kweight=2)
            S.extra["lcf"] = dict(r=r, single=xlcf.single_standard_compare(G[smp.value()], [G[k] for k in st_], xmin=lo.value(),
                                                                         xmax=hi.value(), space=space.value()),
                                  combo=xlcf.fit_all_combinations(G[smp.value()], [G[k] for k in st_], xmin=lo.value(), xmax=hi.value(),
                                                                  space=space.value(), sum_to_one=s1.isChecked(), bounds=bd.isChecked())
                                  if len(st_) > 2 else None)
            paths.LCF.mkdir(parents=True, exist_ok=True)
            append_csv(pd.DataFrame([xlcf.result_row(r, note.text())]), paths.LCF_CSV)
            self.refresh()
        btn.clicked.connect(lambda: W.wait_cursor(go))
        card.add(W.hbox(W.label(T("结果追加到 output/lcf/lcf_results.csv", "Results are appended to output/lcf/lcf_results.csv"), "faint"), None, btn))
        self.add(card)
        L = S.extra.get("lcf")
        if not L:
            return
        r = L["r"]
        res = Card(T("结果", "Result"))
        res.add(W.metrics((T("R 因子", "R-factor"), f"{r['rfactor']:.5f}"), ("χ²_ν", f"{r['chi2_reduced']:.2e}"),
                          ("Σw", f"{r['sum_weights']:.3f}")))
        res.add(W.Table(pd.DataFrame({T("标样", "Standard"): list(r["weights"]), T("权重", "Weight"): list(r["weights"].values()),
                                      T("误差", "Error"): [r["weights_err"].get(k) for k in r["weights"]]})))
        cv = r["curves"]
        p = W.Plot(380)
        p.ax.plot(cv["x"], cv["y"], color=C["text"], label=T("样品", "sample"))
        p.ax.plot(cv["x"], cv["fit"], color=C["err"], ls="--", label="LCF")
        for k, v in cv["comps"].items():
            p.ax.plot(cv["x"], v, lw=1, label=k)
        p.ax.plot(cv["x"], cv["y"] - cv["fit"], color=C["text3"], lw=1, label=T("残差", "residual"))
        p.ax.set_xlabel("E − E0 (eV)" if r["space"] != "chik" else "k (Å⁻¹)")
        p.draw()
        res.add(p)
        res.add(W.label(T("单一标样拟合比较", "Single-standard comparison"), "h3"))
        res.add(W.Table(L["single"]))
        if L.get("combo") is not None:
            res.add(W.label(T("所有组合（按 R 因子排序）", "All combinations (by R-factor)"), "h3"))
            res.add(W.Table(L["combo"]))
        self.add(res)


# ============================================================================= XANES 定量
class XanesPage(Page):
    title_zh, title_en, icon_name = "XANES 定量", "XANES quantification", "peak"

    def build(self):
        from ..state import ensure_norm
        S = self.S
        self.header(T("边位置同时受价态、配位数和配体影响：价态标定只适用于配体相同、结构相近的标样与样品。",
                      "Edge position depends on oxidation state, coordination and ligands: valence calibration only holds "
                      "for standards and samples with the same ligands and similar structures."))
        for g in S.groups.values():
            try:
                ensure_norm(S, g)
            except Exception:
                pass
        cands = [k for k, g in S.groups.items() if hasattr(g, "flat")]
        if not cands:
            self.add(Banner("info", T("先在“载入谱”中载入样品。", "Load samples under “Load spectra” first.")))
            return
        self.add(W.tabs((T("边位置与白线", "Edge & white line"), self._features(cands)),
                        (T("价态标定", "Valence calibration"), self._valence(cands)),
                        (T("边前峰拟合", "Pre-edge fitting"), self._preedge(cands))))

    def _features(self, cands):
        from xafsmith import xanes as xx
        S = self.S
        w = QWidget()
        lay = W.QVBoxLayout(w)
        lay.setContentsMargins(0, 10, 0, 0)
        sel = W.MultiSelect(cands, self.state.get("fsel", cands[:6]), T("选择谱", "Choose spectra"))
        wl = W.num(30, 5, 100, 5)
        lay.addWidget(W.hbox(W.field(T("谱", "Spectra"), sel), W.field(T("白线积分：E0 至 E0 + (eV)", "White-line window: E0 to E0 + (eV)"), wl), spacing=12))
        tabw, plot = W.vbox(), W.Plot(360)
        lay.addWidget(tabw)
        lay.addWidget(W.label(T("E0_deriv：导数最大值；E_half：归一化 μ = 0.5 处；WL_E / WL_height：白线峰位与峰高；WL_area：E0 至 E0+区间内超过 1 的面积 (eV)。",
                                "E0_deriv: derivative max; E_half: normalized μ = 0.5; WL_E / WL_height: white-line position and height; "
                                "WL_area: area above 1 from E0 to E0 + window (eV)."), "faint"))
        lay.addWidget(plot)
        cur = {}

        def upd():
            v = sel.value()
            self.state["fsel"] = v
            W._clear_layout(tabw.layout())
            if not v:
                return
            tab = xx.features_table([S.groups[k] for k in v], wl.value())
            cur["tab"] = tab
            tabw.layout().addWidget(W.Table(tab.round(4)))
            plot.clear()
            for k in v:
                g = S.groups[k]
                plot.ax.plot(g.energy, g.flat, label=k)
            e0 = S.groups[v[0]].e0
            plot.ax.set_xlim(e0 - 30, e0 + 70)
            for y in (0.5, 1.0):
                plot.ax.axhline(y, color=C["text3"], ls=":", lw=0.8)
            plot.ax.set_xlabel("E (eV)")
            plot.draw()

        def save():
            tab = cur.get("tab")
            if tab is None:
                return
            paths.XANES.mkdir(parents=True, exist_ok=True)
            old = pd.read_csv(paths.XANES_CSV, encoding="utf-8-sig") if paths.XANES_CSV.exists() else None
            new = tab if old is None else pd.concat([old[~old["sample"].isin(tab["sample"])], tab])
            new.to_csv(paths.XANES_CSV, index=False, encoding="utf-8-sig")
            W.toast(self, T(f"已保存 {len(tab)} 条（同名样品覆盖）", f"Saved {len(tab)} rows (same samples replaced)"))
        sel.changed.connect(lambda *_: upd())
        wl.valueChanged.connect(lambda *_: upd())
        lay.addWidget(W.hbox(None, W.button(T("保存到 output/xanes/xanes_features.csv", "Save to output/xanes/xanes_features.csv"),
                                            icon_name="save", slot=save)))
        upd()
        lay.addStretch(1)
        return w

    def _valence(self, cands):
        from xafsmith import xanes as xx
        S = self.S
        w = QWidget()
        lay = W.QVBoxLayout(w)
        lay.setContentsMargins(0, 10, 0, 0)
        lay.addWidget(W.label(T("1 选已知价态的实测标样并填写价态；2 选边位置定义；3 选要估算的样品。",
                                "1 choose measured standards of known valence and enter it; 2 choose the edge definition; 3 choose samples."), "muted"))
        stds = W.MultiSelect(cands, self.state.get("vstd", []), T("标样", "Standards"))
        how = W.combo(["E_half", "E0_deriv", "WL_E"], self.state.get("how", "E_half"),
                      fmt=lambda h: {"E_half": T("E_half（半高点）", "E_half (half height)"), "E0_deriv": T("E0_deriv（导数最大值）", "E0_deriv (derivative max)"),
                                     "WL_E": T("WL_E（白线峰位）", "WL_E (white-line peak)")}[h])
        smp = W.MultiSelect(cands, self.state.get("vsmp", []), T("要估算价态的样品", "Samples to estimate"))
        lay.addWidget(W.hbox(W.field(T("标样", "Standards"), stds), W.field(T("边位置定义", "Edge definition"), how),
                             W.field(T("样品", "Samples"), smp), spacing=12))
        holder = W.vbox()
        lay.addWidget(holder)
        lay.addStretch(1)

        def upd():
            self.state.update(vstd=stds.value(), how=how.value(), vsmp=smp.value())
            W._clear_layout(holder.layout())
            st_ = stds.value()
            if not st_:
                return
            vals = self.state.setdefault("vals", {})
            vt = pd.DataFrame({T("标样", "Standard"): st_, T("价态", "Valence"): [float(vals.get(k, 0.0)) for k in st_]})
            t = W.Table(vt, editable=[T("价态", "Valence")])
            holder.layout().addWidget(t)
            out = W.vbox()
            holder.layout().addWidget(out)

            def calc():
                df = t.df()
                for k, v in zip(df.iloc[:, 0], df.iloc[:, 1]):
                    vals[k] = float(v)
                W._clear_layout(out.layout())
                col = how.value()
                feats = xx.features_table([S.groups[k] for k in st_]).set_index("sample")
                pos = [float(feats.loc[k, col]) for k in st_]
                val = [vals[k] for k in st_]
                try:
                    cal = xx.valence_calibration(pos, val)
                except Exception as ex:      # noqa: BLE001
                    out.layout().addWidget(Banner("info", str(ex)))
                    return
                out.layout().addWidget(W.label(T(f"E = <b>{cal['a']:.3f}</b>·价态 + <b>{cal['b']:.2f}</b> eV；R² = {cal['r2']:.4f}；斜率误差 {cal['a_err']:.3f} eV/价（{cal['n']} 个标样）",
                                                 f"E = <b>{cal['a']:.3f}</b>·valence + <b>{cal['b']:.2f}</b> eV; R² = {cal['r2']:.4f}; slope error {cal['a_err']:.3f} eV per unit ({cal['n']} standards)"), rich=True))
                if cal["n"] < 3:
                    out.layout().addWidget(Banner("warn", T("只有 2 个标样：直线没有统计误差，估算的价态误差未知。",
                                                            "Only 2 standards: the line has no statistical error; valence errors are unknown.")))
                p = W.Plot(320)
                p.ax.scatter(val, pos, color=C["accent"], zorder=3, label=T("标样", "standards"))
                for x, y, k in zip(val, pos, st_):
                    p.ax.annotate(k, (x, y), textcoords="offset points", xytext=(4, 4), fontsize=8)
                xs = np.linspace(min(val) - 0.5, max(val) + 0.5, 20)
                p.ax.plot(xs, cal["a"] * xs + cal["b"], ls="--", color=C["text3"], label=T("标定直线", "calibration"))
                rows = []
                if smp.value():
                    sf = xx.features_table([S.groups[k] for k in smp.value()]).set_index("sample")
                    for k in smp.value():
                        v, err = xx.predict_valence(cal, float(sf.loc[k, col]))
                        rows.append({T("样品", "Sample"): k, T("边位置", "Edge position"): float(sf.loc[k, col]),
                                     T("价态", "Valence"): round(v, 3), T("误差", "Error"): None if not np.isfinite(err) else round(err, 3),
                                     T("外推", "Extrapolated"): T("是", "yes") if not (min(val) <= v <= max(val)) else ""})
                        p.ax.scatter([v], [float(sf.loc[k, col])], marker="x", s=50, label=k)
                p.ax.set_xlabel(T("价态", "valence"))
                p.ax.set_ylabel(f"{col} (eV)")
                p.draw()
                if rows:
                    rt = pd.DataFrame(rows)
                    out.layout().addWidget(W.Table(rt))
                    out.layout().addWidget(W.label(T("误差只来自标定直线的统计误差，不含化学环境差异；超出标样价态范围的为外推。",
                                                     "Errors come from the calibration line only, not from chemical differences; outside the standards' range is extrapolation."), "faint"))

                    def save():
                        paths.XANES.mkdir(parents=True, exist_ok=True)
                        rt.assign(定义=col, 斜率=cal["a"], 截距=cal["b"], R2=cal["r2"],
                                  标样="; ".join(f"{a}={b}" for a, b in zip(st_, val))).to_csv(
                            paths.XANES / f"valence_{col}.csv", index=False, encoding="utf-8-sig")
                        W.toast(self, T(f"已保存 output/xanes/valence_{col}.csv", f"Saved output/xanes/valence_{col}.csv"))
                    out.layout().addWidget(W.hbox(None, W.button(T("保存价态估算", "Save valence estimates"), icon_name="save", slot=save)))
                out.layout().addWidget(p)
            t.edited.connect(calc)
            calc()
        stds.changed.connect(lambda *_: upd())
        how.currentIndexChanged.connect(lambda *_: upd())
        smp.changed.connect(lambda *_: upd())
        upd()
        return w

    def _preedge(self, cands):
        from xafsmith import xanes as xx
        S = self.S
        w = QWidget()
        lay = W.QVBoxLayout(w)
        lay.setContentsMargins(0, 10, 0, 0)
        k = W.combo(cands, self.state.get("pk"))
        lo, hi = W.num(-20, -60, 0, 1), W.num(-5, -30, 20, 1)
        n = W.combo([1, 2, 3], 1)
        stp = W.combo(["erf", "arctan", "none"], "erf")
        lay.addWidget(W.fields((T("谱", "Spectrum"), k), (T("下限 E−E0 (eV)", "From E−E0 (eV)"), lo), (T("上限 E−E0 (eV)", "To E−E0 (eV)"), hi),
                               (T("峰数", "Peaks"), n), (T("主边基线", "Edge baseline"), stp)))
        lay.addWidget(W.label(T("模型：n 个高斯峰（σ ≤ 2.5 eV）+ 台阶（主边上升沿，中心限制在半高点 ±6 eV）+ 常数。峰位贴边或面积≈0 时会提示。",
                                "Model: n Gaussians (σ ≤ 2.5 eV) + a step (rising edge, centre within ±6 eV of half height) + constant. "
                                "Warnings flag peaks at the bounds or with ≈0 area."), "faint"))
        out = W.vbox()

        def go():
            self.state["pk"] = k.value()
            r = xx.preedge_fit(S.groups[k.value()], lo.value(), hi.value(), n.value(), stp.value())
            W._clear_layout(out.layout())
            for w_ in r["warnings"]:
                out.layout().addWidget(Banner("warn", w_))
            pk = pd.DataFrame(r["peaks"])
            out.layout().addWidget(W.Table(pk.round(4)))
            out.layout().addWidget(W.label(T(f"总面积 <b>{r['total_area']:.4f}</b> eV；面积加权质心 <b>{r['centroid']:.2f}</b> eV；R 因子 {r['rfactor']:.2e}",
                                             f"Total area <b>{r['total_area']:.4f}</b> eV; area-weighted centroid <b>{r['centroid']:.2f}</b> eV; R-factor {r['rfactor']:.2e}"), rich=True))
            cv = r["curves"]
            p = W.Plot(340)
            p.ax.plot(cv["x"], cv["y"], color=C["text"], label=T("数据", "data"))
            p.ax.plot(cv["x"], cv["fit"], color=C["err"], ls="--", label=T("拟合", "fit"))
            for nm, v in cv["comps"].items():
                p.ax.plot(cv["x"], v, lw=1, label=nm)
            p.ax.plot(cv["x"], cv["y"] - cv["fit"], color=C["text3"], lw=1, label=T("残差", "residual"))
            p.ax.set_xlabel("E (eV)")
            p.draw()
            out.layout().addWidget(p)

            def save():
                paths.XANES.mkdir(parents=True, exist_ok=True)
                fn = paths.XANES / f"preedge_{safe(k.value())}.csv"
                pk.assign(sample=k.value(), emin=lo.value(), emax=hi.value(), step=stp.value(), centroid=r["centroid"],
                          total_area=r["total_area"], rfactor=r["rfactor"]).to_csv(fn, index=False, encoding="utf-8-sig")
                W.toast(self, T(f"已保存 {paths.rel(fn)}", f"Saved {paths.rel(fn)}"))
            out.layout().addWidget(W.hbox(None, W.button(T("保存边前峰结果", "Save pre-edge result"), icon_name="save", slot=save)))
        lay.addWidget(W.hbox(None, W.button(T("拟合边前峰", "Fit pre-edge"), primary=True, icon_name="play", slot=lambda: W.wait_cursor(go))))
        lay.addWidget(out)
        lay.addStretch(1)
        return w
