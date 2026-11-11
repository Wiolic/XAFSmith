"""背景扣除 χ(k) 与傅里叶变换页面。"""

from __future__ import annotations

from xafsmith import logs
import numpy as np
from PySide6.QtWidgets import QWidget
from xafsmith import paths
from ... import widgets as W
from ...state import has_chi, safe
from ...theme import C
from ...widgets import T, Banner, Card, Page

from ._shared import need_groups
from .._common import rlabel


class ChiPage(Page):
    title_zh, title_en, icon_name = "χ(k) 与 FT", "χ(k) & FT", "wave"

    def build(self):
        from xafsmith import autobk as xbkg, ft as xft, mut_planner as xmut, normalize as xnorm
        from xafsmith.common import n_idp, r_resolution, write_params
        S = self.S
        self.header(T("背景扣除与傅里叶变换。k¹ / k² / k³ 都要看；k 范围按最差样品的信噪比定，一组样品用同一个范围。",
                      "Background removal and Fourier transform. Look at k¹ / k² / k³; set the k range from the worst sample "
                      "and use one range for the whole series."))
        if not need_groups(self):
            return
        b, f = S.bkg_par, S.ft_par
        ctl = Card()
        w = dict(rbkg=W.num(b["rbkg"], 0.5, 3, 0.1), bkw=W.combo([0, 1, 2, 3], int(b["kweight"])),
                 kmin=W.num(f["kmin"], 0, 10, 0.1), kmax=W.num(f["kmax"], 3, 25, 0.1), dk=W.num(f["dk"], 0, 5, 0.1),
                 win=W.combo(["hanning", "kaiser", "sine", "parzen", "welch"], f["window"]),
                 fkw=W.combo([1, 2, 3], int(f["kweight"])), rmax=W.num(self.state.get("rmax", 6.0), 2, 10, 0.5))
        ctl.add(W.fields(("rbkg", w["rbkg"]), (T("背景 k 权重", "bkg k-weight"), w["bkw"]), ("kmin", w["kmin"]),
                         ("kmax", w["kmax"]), ("dk", w["dk"]), (T("窗函数", "Window"), w["win"]),
                         (T("FT k 权重", "FT k-weight"), w["fkw"]), (T("作图 Rmax", "Plot Rmax"), w["rmax"])))
        sel = W.MultiSelect(list(S.groups), self.state.get("sel", list(S.groups)[:1]), T("选择谱", "Choose spectra"))
        showre = W.check(T("显示 Re χ(R)", "Show Re χ(R)"), self.state.get("re", False))
        ctl.add(W.hbox(sel, showre, spacing=12))
        self.add(ctl)
        pk, pr, pb = W.Plot(380), W.Plot(400), W.Plot(360)
        kcheck = QWidget()
        kl = W.QVBoxLayout(kcheck)
        kl.setContentsMargins(0, 8, 0, 0)
        g0 = S.groups[sel.value()[0]] if sel.value() else next(iter(S.groups.values()))
        elems = W.text(self.state.get("elems", g0.element or ""))
        rmin_, rmax_ = W.num(1.0, 0.5, 6, 0.05), W.num(3.0, 1, 8, 0.05)
        kres = W.vbox()
        kl.addWidget(W.fields((T("样品中所有元素（逗号分隔）", "All elements in the sample (comma-separated)"), elems),
                              (T("拟合 Rmin", "Fit Rmin"), rmin_), (T("拟合 Rmax", "Fit Rmax"), rmax_)))
        kl.addWidget(kres)
        kl.addStretch(1)
        self.add(W.tabs(("χ(k)", pk), ("|χ(R)| / Re", W.vbox(pr, W.label(T("R 轴未相移校正：峰位比真实键长短约 0.3–0.5 Å。",
                                                                            "R is not phase-corrected: peaks appear ~0.3–0.5 Å shorter than bond lengths."), "faint"))),
                        (T("背景 μ0(E)", "Background μ0(E)"), pb), (T("k 范围检查", "k-range check"), kcheck)))

        def update():
            b.update(rbkg=w["rbkg"].value(), kweight=w["bkw"].value())
            f.update(kmin=w["kmin"].value(), kmax=w["kmax"].value(), dk=w["dk"].value(), window=w["win"].value(),
                     kweight=w["fkw"].value())
            v = sel.value()
            self.state.update(sel=v, re=showre.isChecked(), rmax=w["rmax"].value(), elems=elems.text())
            for k in v:
                try:
                    g = S.groups[k]
                    if not hasattr(g, "norm_params"):
                        xnorm.normalize(g, **S.norm_par)
                    xbkg.autobk(g, **b)
                    xft.forward(g, **f)
                except Exception as ex:      # noqa: BLE001
                    logs.log.warning("qt.pages.process.update 出错（已忽略或已提示）", exc_info=True)
                    W.toast(self, f"{k}: {ex}", "err")
            v = [k for k in v if has_chi(S.groups[k])]
            if not v:
                for p in (pk, pr, pb):
                    p.message(T("选择谱", "Choose spectra"))
                return
            kw = int(f["kweight"])
            pk.clear()
            for k in v:
                g = S.groups[k]
                pk.ax.plot(g.k, g.chi * g.k ** kw, label=k)
            g0 = S.groups[v[0]]
            sc = max(np.max(np.abs(S.groups[k].chi * S.groups[k].k ** kw)) for k in v)
            pk.ax.plot(g0.k, g0.kwin * sc, ls=":", color=C["text3"], label=T("窗函数", "window"))
            pk.ax.set_xlabel("k (Å⁻¹)")
            pk.ax.set_ylabel(f"k$^{kw}$χ(k)")
            pk.draw()
            pr.clear()
            for k in v:
                g = S.groups[k]
                pr.ax.plot(g.r, g.chir_mag, label=f"|χ(R)| {k}")
                if showre.isChecked():
                    pr.ax.plot(g.r, g.chir_re, lw=0.9, label=f"Re {k}")
            pr.ax.set_xlim(0, w["rmax"].value())
            pr.ax.set_xlabel(rlabel())
            pr.ax.set_ylabel(f"|χ(R)| (Å$^{{-{kw + 1}}}$)")
            pr.draw()
            pb.clear()
            pb.ax.plot(g0.energy, g0.mu, label="μ(E)")
            pb.ax.plot(g0.energy, g0.bkg, label=T("μ0(E) 背景", "μ0(E) background"))
            pb.ax.set_xlabel("E (eV)")
            pb.draw()
            W._clear_layout(kres.layout())
            try:
                kl_, df = xmut.k_limit([e.strip() for e in elems.text().split(",") if e.strip()], g0.element, g0.edge,
                                       g0.energy[-1])
                kres.layout().addWidget(W.label(T(f"数据末端 k = {g0.k[-1]:.2f} Å⁻¹；考虑干扰边后可用 k 上限 ≈ <b>{kl_:.2f} Å⁻¹</b>",
                                                  f"Data end k = {g0.k[-1]:.2f} Å⁻¹; usable k limit with interfering edges ≈ <b>{kl_:.2f} Å⁻¹</b>"), rich=True))
                kres.layout().addWidget(W.Table(df))
            except Exception as ex:      # noqa: BLE001
                logs.log.warning("qt.pages.process.update 出错（已忽略或已提示）", exc_info=True)
                kres.layout().addWidget(Banner("err", str(ex)))
            kres.layout().addWidget(W.label(
                T(f"ΔR 分辨率 = π/(2Δk) = <b>{r_resolution(f['kmin'], f['kmax']):.3f} Å</b>；N_idp = 2ΔkΔR/π = "
                  f"<b>{n_idp(f['kmin'], f['kmax'], rmin_.value(), rmax_.value()):.1f}</b>",
                  f"ΔR resolution = π/(2Δk) = <b>{r_resolution(f['kmin'], f['kmax']):.3f} Å</b>; N_idp = 2ΔkΔR/π = "
                  f"<b>{n_idp(f['kmin'], f['kmax'], rmin_.value(), rmax_.value()):.1f}</b>"), rich=True))
        for x in ("rbkg", "kmin", "kmax", "dk", "rmax"):
            w[x].valueChanged.connect(lambda *_: W.wait_cursor(update))
        for x in ("bkw", "win", "fkw"):
            w[x].currentIndexChanged.connect(lambda *_: W.wait_cursor(update))
        sel.changed.connect(lambda *_: W.wait_cursor(update))
        showre.toggled.connect(lambda *_: update())
        elems.editingFinished.connect(update)
        rmin_.valueChanged.connect(lambda *_: update())
        rmax_.valueChanged.connect(lambda *_: update())
        W.wait_cursor(update)

        def export():
            od = paths.GUI / "chi"
            od.mkdir(parents=True, exist_ok=True)
            kw = int(f["kweight"])
            for k in sel.value():
                g = S.groups[k]
                base = safe(k)
                np.savetxt(od / f"{base}.chik", np.column_stack([g.k, g.chi, g.chi * g.k ** kw, g.kwin]),
                           header=f"k chi chi*k^{kw} win", fmt="%.6g")
                np.savetxt(od / f"{base}.chir", np.column_stack([g.r, g.chir_mag, g.chir_re, g.chir_im]),
                           header="r(no phase corr) mag re im", fmt="%.6g")
            write_params(od / "chi.params.json", dict(norm=S.norm_par, bkg=b, ft=f), "gui:chi")
            W.toast(self, T(f"已导出到 {paths.rel(od)}", f"Exported to {paths.rel(od)}"))
        self.add(W.hbox(None, W.button(T("导出 χ(k) 与 χ(R) 到 output/gui/chi/", "Export χ(k) and χ(R) to output/gui/chi/"),
                                       icon_name="download", slot=export)))
