"""小波变换页面。"""

from __future__ import annotations

from xafsmith import logs
import numpy as np
import pandas as pd
from xafsmith import paths
from ... import widgets as W
from ...state import has_chi, safe
from ...widgets import T, Banner, Card, Page

from .._common import rlabel


WT_HELP_ZH = """
<h3>小波图上看什么</h3>
<p>横轴是 k，纵轴是 R（未相移校正）。在同一个 R 处，<b>散射体越重，|W| 的极大值出现在越高的 k</b>
（背散射振幅的包络随原子序数增大移向高 k）。所以 FT 中 R 相近、分不开的两个峰，可以在小波图上按 k 位置分开。</p>

<h3>η 与 σ（Morlet）</h3>
<p>本软件的 Morlet 定义中，图的形状只由乘积 <b>ησ</b> 决定；单独改 η 只改变整体幅度。在某个 R 处：</p>
<ul>
<li>k 方向的模糊宽度 ≈ ησ / (2R)</li>
<li>R 方向的模糊宽度 ≈ R / (ησ)</li>
</ul>
<p>两者此消彼长。例：R = 2 Å、η = 10、σ = 1 时，k 方向约 2.5 Å⁻¹，R 方向约 0.2 Å。</p>
<ul>
<li><b>ησ 调大</b>：R 方向更锐利，能分开相近的壳层；但 k 方向变宽，轻、重散射体的 k 位置更难区分。</li>
<li><b>ησ 调小</b>：k 方向更锐利，便于比较极大值的 k 位置；但相近 R 的壳层会糊在一起。</li>
<li><b>建议</b>：先用 η ≈ 10、σ ≈ 1，再上下各调一次，确认结论不变。</li>
</ul>

<h3>k 权重</h3>
<ul>
<li>权重越高，高 k 部分被放大，<b>所有极大值都向高 k 移动</b>；重散射体相对增强，轻散射体（O、C、N）减弱。</li>
<li>只比较<b>同一 k 权重</b>下的 k 位置。</li>
<li>判断某个特征是轻还是重散射体：k¹ 与 k³ 都看，随权重升高明显减弱的是轻散射体。</li>
</ul>

<h3>k 范围、Rmax 与 Cauchy</h3>
<ul>
<li>k 范围用到“χ(k) 与 FT”中的 kmax 为止。靠近数据两端（约一个 k 方向宽度以内）的图形会变形；高 k 噪声会随 k 权重放大。</li>
<li><b>Rmax</b> 只改变显示范围。</li>
<li><b>Cauchy</b> 小波（Larch 实现）形状固定、没有可调参数，可用来交叉检查 Morlet 的结论。</li>
</ul>

<h3>适合分析什么</h3>
<ul>
<li>第二壳层是 M–M，还是 M–O / M–O–M；</li>
<li>单原子与团簇 / 纳米颗粒：有没有高 k 的 M–M 极大值；</li>
<li>识别 FT 中重叠的壳层；</li>
<li>判断一个小峰是不是真实散射：真实散射在 k 方向有连续的极大值，噪声与截断旁瓣通常没有。</li>
</ul>

<h3>不适合做什么</h3>
<p>给出配位数、键长或组成——这些要靠拟合；小波图只提供定性判据。不同样品对比时，所有参数（k 范围、k 权重、η、σ）必须相同。</p>
"""


WT_HELP_EN = """
<h3>What the map shows</h3>
<p>k on the horizontal axis, R (not phase-corrected) on the vertical axis. At the same R, <b>the heavier the scatterer, the higher
the k of the |W| maximum</b> (the backscattering amplitude envelope moves to higher k with atomic number). Two FT peaks at similar
R can therefore be separated by their k position.</p>

<h3>η and σ (Morlet)</h3>
<p>In this software's Morlet definition the shape of the map depends only on the product <b>ησ</b>; η alone only rescales the
amplitude. At a given R:</p>
<ul>
<li>blur along k ≈ ησ / (2R)</li>
<li>blur along R ≈ R / (ησ)</li>
</ul>
<p>One improves as the other worsens. Example: R = 2 Å, η = 10, σ = 1 gives ≈ 2.5 Å⁻¹ along k and ≈ 0.2 Å along R.</p>
<ul>
<li><b>Larger ησ</b>: sharper in R, separates close shells, but broader in k, so light and heavy scatterers are harder to tell apart.</li>
<li><b>Smaller ησ</b>: sharper in k, better for comparing the k of maxima, but close shells merge.</li>
<li><b>Advice</b>: start with η ≈ 10, σ ≈ 1, then try one step up and down and check that the conclusion does not change.</li>
</ul>

<h3>k-weight</h3>
<ul>
<li>Higher weights amplify high k and <b>shift every maximum to higher k</b>; heavy scatterers gain, light ones (O, C, N) fade.</li>
<li>Compare k positions only at the <b>same k-weight</b>.</li>
<li>To decide whether a feature is light or heavy, look at k¹ and k³: features that fade at higher weight are light scatterers.</li>
</ul>

<h3>k range, Rmax and Cauchy</h3>
<ul>
<li>The k range runs up to kmax set under “χ(k) &amp; FT”. Features within about one k-blur width of either end are distorted;
high-k noise is amplified by the k-weight.</li>
<li><b>Rmax</b> only changes the display.</li>
<li>The <b>Cauchy</b> wavelet (Larch) has a fixed shape and no parameters — use it to cross-check Morlet results.</li>
</ul>

<h3>Good for</h3>
<ul>
<li>telling whether a second shell is M–M or M–O / M–O–M;</li>
<li>single atoms vs clusters / nanoparticles: is there a high-k M–M maximum?</li>
<li>spotting overlapping shells;</li>
<li>checking whether a small FT peak is real scattering: real scattering has a coherent maximum along k, noise and truncation
ripples usually do not.</li>
</ul>

<h3>Not for</h3>
<p>Coordination numbers, bond lengths or composition — those need fitting; the wavelet map is a qualitative criterion. When
comparing samples, use identical k range, k-weight, η and σ.</p>
"""


def show_wavelet_guide(parent):
    W.info_window(parent, "wt_guide", T("小波变换：参数怎么调、适合分析什么", "Wavelet transform: parameters and what it is good for"),
                  WT_HELP_EN if W.en() else WT_HELP_ZH)


class WaveletPage(Page):
    """小波变换：可选两条谱左右对比（同一套参数），R 区间极大值表合并显示，导出每条谱的数据与图"""
    title_zh, title_en, icon_name = "小波变换", "Wavelet transform", "grid"
    max_width = 1500

    def build(self):
        from xafsmith import wavelet as xwav
        from ...state import parse_ranges
        S = self.S
        self.header(T("同一 R 处，重散射体的极大值出现在较高 k，轻散射体（O 等）在较低 k。可选第二条谱左右对比（参数完全相同）。",
                      "At the same R, heavy scatterers peak at higher k, light scatterers (O, …) at lower k. Pick a second "
                      "spectrum to compare side by side (identical parameters)."),
                    actions=[W.button(T("参数怎么调、适合分析什么", "Parameters · what it is good for"), icon_name="help",
                                      slot=lambda: show_wavelet_guide(self))])
        cands = [k for k, g in S.groups.items() if has_chi(g)]
        if not cands:
            self.add(Banner("info", T("先在“χ(k) 与 FT”中计算 χ(k)。", "Compute χ(k) under “χ(k) & FT” first.")))
            return
        st = self.state
        NONE = ""
        ctl = Card()
        w = dict(k=W.combo(cands, st.get("k")),
                 k2=W.combo([NONE] + cands, st.get("k2", NONE) if st.get("k2", NONE) in cands else NONE,
                            fmt=lambda x: x or T("（不对比）", "(none)")),
                 kind=W.combo(["Morlet", "Cauchy"], st.get("kind", "Morlet")),
                 kw=W.combo([1, 2, 3], st.get("kw", 2)), eta=W.num(st.get("eta", 10), 1, 30, 1),
                 sig=W.num(st.get("sig", 1.0), 0.2, 5, 0.1), rmax=W.num(st.get("rmax", 5.0), 2, 8, 0.5))
        same = W.check(T("两图共用色标（比较绝对强度）", "Shared colour scale (compare absolute |W|)"), st.get("same", False))
        ctl.add(W.fields((T("谱（左）", "Spectrum (left)"), w["k"]), (T("对比谱（右）", "Compare with (right)"), w["k2"]),
                         (T("母小波", "Mother wavelet"), w["kind"]), (T("k 权重", "k-weight"), w["kw"]), cols=4))
        ctl.add(W.fields(("η (Morlet)", w["eta"]), ("σ (Morlet)", w["sig"]), (T("显示 Rmax", "Display Rmax"), w["rmax"]),
                         ("", same), cols=4))
        res = W.label("", "muted", rich=True)
        ctl.add(res)
        self.add(ctl)
        two = bool(st.get("k2")) and st.get("k2") in cands and st.get("k2") != w["k"].value()
        plot = W.Plot(470 if two else 560, 1, 2 if two else 1)
        self.add(plot)
        # 各 R 区间的极大值
        mx = Card(T("各 R 区间的极大值", "Maxima in R windows"))
        rng = W.text(st.get("rng", "1.0-2.0; 2.0-3.6"), "1.0-2.0; 2.0-3.6")
        mx.add(W.field(T("R 区间（Å，未相移校正；多个用 ; 分隔）", "R windows (Å, not phase-corrected; separate with ;)"), rng))
        holder = W.vbox()
        mx.add(holder)
        mx.add(W.label(T("比较两条谱同一 R 区间的“极大值所在 k”：k 越高，该壳层中重散射体的贡献越大。只在参数完全相同时可比。",
                         "Compare the “k at maximum” of one R window between spectra: higher k means more heavy-scatterer "
                         "contribution. Comparable only with identical parameters."), "faint"))
        self.add(mx)
        cur = {}

        def compute(name):
            g = S.groups[name]
            m = g.k <= S.ft_par["kmax"]
            rmax = w["rmax"].value()
            if w["kind"].value() == "Morlet":
                kk, rr, Wt = xwav.morlet(g.k[m], g.chi[m], kweight=w["kw"].value(), rmax=rmax, eta=w["eta"].value(),
                                         sigma=w["sig"].value())
            else:
                from larch import Group
                kk, rr, Wt = xwav.cauchy(Group(k=g.k[m], chi=g.chi[m]), kweight=w["kw"].value(), rmax_out=rmax)
                mm = (rr <= rmax) & (rr > 0)
                rr, Wt = rr[mm], Wt[mm]
            return dict(name=name, g=g, kk=np.asarray(kk), rr=np.asarray(rr), W=np.asarray(Wt))

        def maxima(d):
            rows = []
            wins = parse_ranges(rng.text())
            kk, rr, Wt = d["kk"], d["rr"], d["W"]
            for lo, hi in wins:
                sel = (rr >= lo) & (rr <= hi)
                if not sel.any():
                    continue
                sub = Wt[sel]
                i, j = np.unravel_index(np.argmax(sub), sub.shape)
                rows.append({T("样品", "Sample"): d["name"], T("R 区间 (Å)", "R window (Å)"): f"{lo:g}–{hi:g}",
                             T("极大值所在 k (Å⁻¹)", "k at maximum (Å⁻¹)"): round(float(kk[j]), 2),
                             T("极大值所在 R (Å)", "R at maximum (Å)"): round(float(rr[sel][i]), 2), "|W| max": float(sub[i, j])})
            return pd.DataFrame(rows)

        def update():
            st.update(k=w["k"].value(), k2=w["k2"].value(), kind=w["kind"].value(), kw=w["kw"].value(), eta=w["eta"].value(),
                      sig=w["sig"].value(), rmax=w["rmax"].value(), rng=rng.text(), same=same.isChecked())
            names = [w["k"].value()] + ([w["k2"].value()] if w["k2"].value() and w["k2"].value() != w["k"].value() else [])
            data = [compute(n) for n in names]
            cur["data"] = data
            tabs, err = [], None
            for d in data:
                try:
                    d["tab"] = maxima(d)
                    tabs.append(d["tab"])
                except ValueError as ex:
                    d["tab"], err = None, str(ex)
            vmax = max(float(d["W"].max()) for d in data) if same.isChecked() else None
            for cb in cur.get("cbs", []):
                try:
                    cb.remove()
                except Exception:
                    logs.log.warning("qt.pages.process.update 出错（已忽略或已提示）", exc_info=True)
                    pass
            cur["cbs"] = []
            for ax, d in zip(plot.axes, data):
                ax.clear()
                ax.grid(False)
                im = ax.pcolormesh(d["kk"], d["rr"], d["W"], shading="auto", cmap="jet", vmin=0 if vmax else None, vmax=vmax)
                cur["cbs"].append(plot.fig.colorbar(im, ax=ax, shrink=0.9))
                t = d.get("tab")
                if isinstance(t, pd.DataFrame) and len(t):
                    ax.scatter(t.iloc[:, 2], t.iloc[:, 3], marker="+", s=90, color="white", linewidths=1.6, zorder=3)
                ax.set_xlabel("k (Å⁻¹)")
                ax.set_ylabel(rlabel())
                ax.set_title(d["name"], fontsize=10)
                ax.set_box_aspect(1)            # 图框 1:1
            plot.draw(legend=False)
            W._clear_layout(holder.layout())
            if err:
                holder.layout().addWidget(Banner("err", err))
            elif tabs and sum(len(x) for x in tabs):
                holder.layout().addWidget(W.Table(pd.concat(tabs, ignore_index=True)))
            if w["kind"].value() == "Morlet":
                es = w["eta"].value() * w["sig"].value()
                res.setText(T(f"当前分辨率：R = 2 Å 处 k 方向约 <b>{es / 4:.2f} Å⁻¹</b>、R 方向约 <b>{2 / es:.2f} Å</b>；"
                              f"R = 3 Å 处约 <b>{es / 6:.2f} Å⁻¹</b>、<b>{3 / es:.2f} Å</b>（ησ = {es:g}）",
                              f"Current resolution: at R = 2 Å about <b>{es / 4:.2f} Å⁻¹</b> along k and <b>{2 / es:.2f} Å</b> along R; "
                              f"at R = 3 Å about <b>{es / 6:.2f} Å⁻¹</b> and <b>{3 / es:.2f} Å</b> (ησ = {es:g})"))
            else:
                res.setText(T("Cauchy 小波：形状固定，η、σ 不起作用。", "Cauchy wavelet: fixed shape; η and σ have no effect."))
            w["eta"].setEnabled(w["kind"].value() == "Morlet")
            w["sig"].setEnabled(w["kind"].value() == "Morlet")
        for x in ("k", "k2"):          # 换谱 / 打开或关闭对比：重建页面（一图或左右两图）
            w[x].currentIndexChanged.connect(lambda *_: (st.update(k=w["k"].value(), k2=w["k2"].value()), self.refresh()))
        for x in ("kind", "kw"):
            w[x].currentIndexChanged.connect(lambda *_: W.wait_cursor(update))
        for x in ("eta", "sig", "rmax"):
            w[x].valueChanged.connect(lambda *_: W.wait_cursor(update))
        same.toggled.connect(lambda *_: W.wait_cursor(update))
        rng.editingFinished.connect(lambda: W.wait_cursor(update))
        W.wait_cursor(update)

        def export():
            from xafsmith import pubfig as pf
            from xafsmith.common import write_params
            from ...state import plain_rc
            od = paths.GUI / "wavelet"
            od.mkdir(parents=True, exist_ok=True)
            kind = w["kind"].value()
            names = []
            for d in cur.get("data", []):
                kk, rr, Wt = d["kk"], d["rr"], d["W"]
                base = od / f"{safe(d['name'])}_{kind.lower()}_k{w['kw'].value()}"
                # 矩阵：第一行为 k，第一列为 R
                mat = np.vstack([np.concatenate([[np.nan], kk]), np.column_stack([rr, Wt])])
                np.savetxt(base.with_suffix(".csv"), mat, delimiter=",", fmt="%.6g",
                           header="first row: k (1/A); first column: R (A, not phase-corrected); values: |W|", comments="# ")
                if isinstance(d.get("tab"), pd.DataFrame):
                    d["tab"].to_csv(str(base) + "_maxima.csv", index=False, encoding="utf-8-sig")
                par = dict(sample=d["name"], wavelet=kind, kweight=w["kw"].value(), kmax=S.ft_par["kmax"],
                           rmax=w["rmax"].value(), r_windows=rng.text())
                if kind == "Morlet":
                    par.update(eta=w["eta"].value(), sigma=w["sig"].value())
                write_params(str(base) + ".params.json", par, "gui:wavelet")
                with plain_rc():
                    fig, cap = pf.wavelet(kk, rr, Wt, label=d["name"], rmax=w["rmax"].value(), kweight=w["kw"].value())
                    pf.save(fig, cap, base, ("png", "svg"), dpi=600)
                names.append(base.name)
            W.toast(self, T(f"已导出到 {paths.rel(od)}：", f"Exported to {paths.rel(od)}: ") + "、".join(names)
                    + T("（各含 .csv / _maxima.csv / .png / .svg / .params.json）", " (.csv / _maxima.csv / .png / .svg / .params.json each)"))
        ctl.add(W.hbox(W.button(T("打开 output/gui/wavelet", "Open output/gui/wavelet"), icon_name="external",
                                 slot=lambda: W.open_folder(paths.GUI / "wavelet")), None,
                        W.button(T("导出数据与图", "Export data and figure"), primary=True, icon_name="download",
                                 slot=lambda: W.wait_cursor(export))))
