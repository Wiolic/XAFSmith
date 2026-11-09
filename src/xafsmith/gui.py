"""XAFS 图形界面（Streamlit）：类似 Athena（数据处理）+ Artemis（FEFF 路径拟合）。

启动：xafsmith gui [--project <项目目录>]（或双击项目中的“打开图形界面.bat”）
浏览器打开 http://localhost:8501

所有处理都在原始数据的副本上进行；原始文件只读。
"""
import io as _io
import os
import subprocess
import json
import re
import sys
import datetime
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import streamlit as st

from xafsmith import io as xio                                     # noqa: E402
from xafsmith import qc as xqc                                     # noqa: E402
from xafsmith import calib as xcal                                 # noqa: E402
from xafsmith import normalize as xnorm                            # noqa: E402
from xafsmith import autobk as xbkg                                # noqa: E402
from xafsmith import ft as xft                                     # noqa: E402
from xafsmith import wavelet as xwav                               # noqa: E402
from xafsmith import structures as xstruct                         # noqa: E402
from xafsmith import feff_wrap as xfeff                            # noqa: E402
from xafsmith import fit_exafs as xfit                             # noqa: E402
from xafsmith import fit_lcf as xlcf                               # noqa: E402
from xafsmith import mut_planner as xmut                           # noqa: E402
from xafsmith.common import n_idp, r_resolution, edge_energy, write_params  # noqa
from xafsmith import paths                                          # noqa: E402
from xafsmith import pipeline as pl                                 # noqa: E402

if paths.is_project(paths.ROOT):
    paths.ensure()

st.set_page_config(page_title="XAFSmith", layout="wide", page_icon="📈")
S = st.session_state
S.setdefault("groups", {})      # label -> Group
if "calib" not in S:            # 参比文件 -> 校准记录（output/calib/calib.json，按参比文件索引）
    S.calib = pl.load_calib() if paths.is_project(paths.ROOT) else {}
S.setdefault("fits", [])        # list of dict(summary, result, curves, model)
S.setdefault("norm_par", dict(xnorm.DEFAULT_NORM))
S.setdefault("bkg_par", dict(xbkg.DEFAULT_BKG))
S.setdefault("ft_par", dict(xft.DEFAULT_FT))

NOPHASE = "R (Å) — 未相移校正"
FUNCS = {"sqrt", "exp", "log", "abs", "min", "max", "pi", "sin", "cos", "tan", "reff", "degen",
         "e", "log10"}


# ----------------------------------------------------------------------------- helpers
def groups_list(filter_fn=None):
    return [k for k, g in S.groups.items() if filter_fn is None or filter_fn(g)]


def edge_key(g):
    return f"{g.element}_{g.edge}"


def load_cfg():
    from xafsmith import pipeline as pl
    return pl.load_config() if pl.CONFIG.exists() else {"edges": {}}


def ref_candidates():
    """可作参比的文件：meta.csv 中 role=reference 的文件 + 文件名像单质箔/粉的原始文件"""
    from xafsmith import pipeline as pl
    out = list(pl.load_meta().query("role == 'reference'").file) if pl.META.exists() else []
    for p in paths.RAW.rglob("*"):
        if p.is_file() and re.search(r"foil|powder|metal", p.name, re.I) and xio.is_bsrf(p):
            out.append(p.relative_to(paths.ROOT).as_posix())
    return list(dict.fromkeys(out))


def ref_calib(ref, e_table=None, smooth_ev=1.0, force=False):
    """参比文件的校准记录（S.calib 中没有就当场计算并存入 S.calib 与 output/calib/calib.json）"""
    from xafsmith import pipeline as pl
    if ref in S.calib and not force:
        return S.calib[ref]
    cfg = load_cfg()
    if e_table is not None:      # GUI 中手动给了表值 / 平滑
        cfg = json.loads(json.dumps(cfg))
        g0 = xio.read_bsrf(paths.ROOT / ref)
        e = cfg["edges"].setdefault(f"{g0.element}_{g0.edge}", {})
        e["e_table"] = e_table
        e.setdefault("norm", {})["smooth_ev"] = smooth_ev
    r = pl.calibrate_ref_file(ref, cfg)
    S.calib[ref] = r
    xcal.save_calib(S.calib, paths.CALIB_JSON)
    return r


def calib_status(g):
    """(状态文字, 是否已按参比校准)"""
    refs = [r for r in str(getattr(g, "calib_ref", "") or "").split(";") if r]
    de = getattr(g, "e_shift", 0.0) or 0.0
    if not refs:
        return ("✘ 未按参比校准" if de == 0 else f"⚠ 平移 {de:+.2f} eV，来源不明"), False
    miss = [r for r in refs if r not in S.calib]
    if miss:
        return f"⚠ 参比 {Path(miss[0]).name} 无校准记录", False
    want = float(np.mean([S.calib[r]["delta_e"] for r in refs]))
    if abs(de - want) > 1e-6:
        return f"⚠ ΔE={de:+.2f} 与参比的 {want:+.2f} 不一致", False
    return "✔ " + " + ".join(f"{Path(r).name}" for r in refs), True


def apply_ref(keys, ref):
    """把参比 ref 的 ΔE 加到所选谱（只改处理副本）；边不一致的谱跳过。返回 (已校准, 跳过)"""
    r = S.calib[ref]
    done, skipped = [], []
    for k in keys:
        g = S.groups[k]
        if edge_key(g) != r["edge_key"]:
            skipped.append(k)
            continue
        xcal.apply_shift([g], r["delta_e"])
        g.calib_ref = ref
        for a in ("e0", "norm", "norm_params", "chi", "k", "chir_mag"):
            if hasattr(g, a):
                delattr(g, a)
        done.append(k)
    return done, skipped


def has_chi(g):
    return hasattr(g, "chi") and hasattr(g, "k")


def process(g, norm=True, bkg=True, ft=True):
    if norm:
        xnorm.normalize(g, **S.norm_par)
    if bkg:
        xbkg.autobk(g, **S.bkg_par)
    if ft:
        xft.forward(g, **S.ft_par)
    return g


def fig_layout(fig, x, y, h=420):
    fig.update_layout(xaxis_title=x, yaxis_title=y, height=h, margin=dict(l=10, r=10, t=30, b=10),
                      legend=dict(font=dict(size=10)))
    return fig


def idents(expr):
    if expr is None:
        return []
    s = str(expr)
    if re.fullmatch(r"\s*[-+]?[\d.]+([eE][-+]?\d+)?\s*", s):
        return []
    return [t for t in re.findall(r"[A-Za-z_]\w*", s) if t not in FUNCS]


def raw_files():
    """data/raw 下的数据文件 + 项目中的 Athena .prj"""
    out = [p for p in paths.RAW.rglob("*") if p.is_file()
           and (xio.is_bsrf(p) or p.suffix.lower() in (".dat", ".xmu", ".nor", ".txt", ".prj"))]
    out += [p for p in paths.ROOT.rglob("*.prj") if ".venv" not in p.parts]
    return sorted(set(out))


# ----------------------------------------------------------------------------- pages
def page_import():
    st.header("① 数据导入")
    from xafsmith import pipeline as pl
    if pl.META.exists() and pl.CONFIG.exists():
        with st.container(border=True):
            st.markdown("**按 data/meta.csv + config.json 载入**（与命令行 `xafs.py process` 完全相同："
                        "已校准、已归一化、重复扫描已合并、χ(k)/FT 已算）")
            meta = pl.load_meta()
            samples = list(dict.fromkeys(meta["sample"]))
            c1, c2 = st.columns([3, 1])
            ms = c1.multiselect("样品", samples, key="meta_samples")
            edges = sorted(set(meta.edge_key))
            ek = c2.selectbox("或整条边", [""] + edges, key="meta_edge")
            sel_refs = sorted(set(meta[meta["sample"].isin(ms)].ref_file) - {""})
            if ms:
                st.caption("校准参比（同批次单质箔/粉，会一起载入）：" + ("、".join(sel_refs) or "⚠ 无"))
            if st.button("载入样品", type="primary", key="load_meta"):
                todo = ms or ([s for s in samples if meta[meta["sample"] == s].edge_key.iloc[0] == ek] if ek else [])
                # 参比必须一起载入：把所选样品用到的参比（ref_file 对应的样品）加进来
                refs = set(meta[meta["sample"].isin(todo)].ref_file) - {""}
                todo = list(dict.fromkeys(list(meta[meta.file.isin(refs)]["sample"]) + todo))
                cfg = pl.load_config()
                for s in todo:
                    try:
                        g, rep = pl.build_sample(s, cfg, meta)
                        S.groups[s] = g
                    except Exception as ex:
                        st.error(f"{s}: {ex}")
                if todo:
                    c = pl.edge_cfg(cfg, S.groups[todo[0]].edge_key) if todo[0] in S.groups else None
                    if c:   # GUI 参数同步为该边 config.json 中的参数
                        S.norm_par.update(c["norm"]); S.bkg_par.update(c["bkg"]); S.ft_par.update(c["ft"])
                st.rerun()
    st.markdown("**或直接读入文件**——必须同时选择**参比**（与这些谱同一批测量的单质箔/粉）："
                "参比会一起读入，并用它的 ΔE 校准所有谱。.prj 中的谱保持原样。")
    c1, c2 = st.columns([2, 1])
    with c1:
        files = raw_files()
        rel = [p.relative_to(paths.ROOT).as_posix() for p in files]
        sel = st.multiselect("从项目中选择文件（BSRF 文本 / Athena .prj / 列文本）", rel)
        up = st.file_uploader("或上传文件（保存到 data/raw/uploads/，只读）", accept_multiple_files=True)
        cands = ref_candidates()
        from xafsmith.pipeline import batch_of
        if S.get("imp_ref_for") != tuple(sel):      # 文件选择变了 → 默认选同批次参比
            same = [c for c in cands if sel and batch_of(c) == batch_of(sel[0])]
            S["imp_ref"] = same[0] if same else None
            S["imp_ref_for"] = tuple(sel)
        ref = st.selectbox("参比（必选，同批次单质箔/粉）", cands, index=None,
                           placeholder="— 请选择参比 —", key="imp_ref")
        if ref and sel and batch_of(ref) != batch_of(sel[0]):
            st.warning(f"参比来自批次 {batch_of(ref)}，所选谱来自 {batch_of(sel[0])}：不同批次之间单色器状态可能不同。")
    with c2:
        mode = st.selectbox("模式", ["自动(按文件头)", "trans", "fluo"])
        st.caption("透射 μ=ln(I0/I1)；荧光 μ=If/I0")
        with st.expander("通用列文本设置"):
            ecol = st.number_input("能量列", 0, 20, 0)
            i0c = st.number_input("I0 列(-1 无)", -1, 20, 1)
            i1c = st.number_input("I1 列(-1 无)", -1, 20, 2)
            ifc = st.number_input("If 列(-1 无)", -1, 20, 3)
            muc = st.number_input("μ 列(-1 由 I 计算)", -1, 20, -1)
            elem = st.text_input("元素", "")
    need_ref = any(not r.lower().endswith(".prj") for r in sel) or bool(up)
    if need_ref and not ref:
        st.info("请先选择参比，再读入。")
    if st.button("读入", type="primary", disabled=need_ref and not ref):
        fpaths = [paths.ROOT / r for r in sel]
        if ref:
            try:
                rc = ref_calib(ref)
                fpaths = [paths.ROOT / ref] + [p for p in fpaths if p != paths.ROOT / ref]
                st.toast(f"参比 {Path(ref).name}：ΔE = {rc['delta_e']:+.3f} eV")
            except Exception as ex:
                st.error(f"参比 {ref}: {ex}")
                return
        if up:
            ud = paths.RAW / "uploads"
            ud.mkdir(parents=True, exist_ok=True)
            for f in up:
                p = ud / f.name
                if not p.exists():
                    p.write_bytes(f.getvalue())
                paths.append(p)
        errs = []
        for p in fpaths:
            try:
                kws = {}
                if mode != "自动(按文件头)":
                    kws["mode"] = mode
                if p.suffix.lower() == ".prj":
                    for lab, g in xio.read_prj(p).items():
                        S.groups[f"{p.stem}:{lab}"] = g
                    continue
                if xio.is_bsrf(p):
                    g = xio.read_bsrf(p, **kws)
                else:
                    nz = lambda v: None if v < 0 else int(v)
                    g = xio.read_columns(p, ecol=int(ecol), i0col=nz(i0c), i1col=nz(i1c), ifcol=nz(ifc),
                                         mucol=nz(muc), mode=kws.get("mode", "trans"),
                                         element=elem or None)
                lab = p.relative_to(paths.ROOT).as_posix()
                g.label = lab
                S.groups[lab] = g
                done, skipped = apply_ref([lab], ref)       # 用所选参比的 ΔE 校准
                if skipped:
                    S.groups.pop(lab)
                    errs.append(f"{p.name}：吸收边 {edge_key(g)} 与参比 {S.calib[ref]['edge_key']} 不同，"
                                "未读入（请为它选择同边的参比，分开读入）")
            except Exception as ex:
                errs.append(f"{p.name}: {ex}")
        for e in errs:
            st.error(e)
        if not errs:
            st.rerun()

    if S.groups:
        rows = [dict(label=k, element=g.element, edge=g.edge, mode=g.mode, npts=len(g.energy),
                     E_range=f"{g.energy[0]:.0f}–{g.energy[-1]:.0f}", time=g.timestamp,
                     dE_cal=round(getattr(g, "e_shift", 0.0), 3), 校准=calib_status(g)[0],
                     E0=round(getattr(g, "e0", np.nan), 2)) for k, g in S.groups.items()]
        st.dataframe(pd.DataFrame(rows), width="stretch", hide_index=True)
        c1, c2 = st.columns(2)
        with c1:
            rm = st.multiselect("删除", list(S.groups))
            if st.button("删除所选") and rm:
                for k in rm:
                    S.groups.pop(k, None)
                st.rerun()
        with c2:
            show = st.multiselect("查看原始 μ(E) 和通道", list(S.groups), max_selections=8)
        if show:
            fig = make_subplots(rows=1, cols=2, subplot_titles=("μ(E)", "I0 / I1 / If"))
            for k in show:
                g = S.groups[k]
                fig.add_trace(go.Scatter(x=g.energy, y=g.mu, name=k), 1, 1)
                for ch in ("i0", "i1", "ifl"):
                    a = getattr(g, ch, None)
                    if a is not None:
                        fig.add_trace(go.Scatter(x=g.energy, y=a / np.max(np.abs(a)), name=f"{ch}:{k}",
                                                 line=dict(width=1)), 1, 2)
            st.plotly_chart(fig_layout(fig, "E (eV)", ""), width="stretch")


def page_qc():
    st.header("② 数据质量检查 (QC)")
    sel = st.multiselect("选择谱", list(S.groups), default=list(S.groups))
    if st.button("运行 QC", type="primary") and sel:
        rows = []
        for k in sel:
            g = S.groups[k]
            try:
                if not hasattr(g, "norm_params"):
                    xnorm.normalize(g, **S.norm_par)
                rows.append(xqc.check(g))
            except Exception as ex:
                rows.append(dict(label=k, error=str(ex)))
        df = pd.DataFrame(rows)
        df.to_csv(paths.QC_CSV, index=False, encoding="utf-8-sig")
        S.qc = df
    if "qc" in S:
        st.dataframe(S.qc, width="stretch")
        st.caption("已保存 output/qc/qc_report.csv。delta_mut：透射边跳（与增益无关）；"
                   "self_abs_risk：荧光谱由 I1 通道估计的样品(+电解池) Δμt；"
                   "k_snr3：k²χ 包络降到 3×噪声的位置，可作 kmax 的参考。")


def page_calib():
    st.header("③ 能量校准")
    st.info("**规则**：每条谱都用**与它同一批测量的单质参比**（金属箔/粉）校准：ΔE = E_table − E0_meas"
            "（E0 取一阶导数最大值）。同一参比下的所有谱加同一个 ΔE，不对单个样品各自校准。"
            "读入时必须选参比（① 页），meta.csv 的 ref_file 列记录每条谱用的参比。")

    # 1) 参比校准值
    st.subheader("1. 参比校准值（每个参比文件一个 ΔE）")
    rows = [dict(参比=ref, 吸收边=r.get("edge_key", ""), 批次=r.get("batch", ""), E_table=r.get("e_table"),
                 E0_meas=round(r["e0_meas"], 2), ΔE=round(r["delta_e"], 3),
                 参比测量时间=r.get("ref_time", ""), 表值来源=r.get("table_source", ""))
            for ref, r in S.calib.items()]
    if rows:
        st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch")
    else:
        st.warning("还没有校准值：在 ① 读入时选参比，或在下方第 3 步测定，或命令行运行 `xafs.py calib`。")

    # 2) 已载入谱的状态
    st.subheader("2. 已载入谱的校准状态")
    if not S.groups:
        st.caption("尚未载入谱（① 数据导入）。")
    else:
        srows = []
        for k, g in S.groups.items():
            refs = [r for r in str(getattr(g, "calib_ref", "") or "").split(";") if r in S.calib]
            h = xcal.time_gap_hours(getattr(g, "timestamp", ""), S.calib[refs[0]].get("ref_time")) if refs else None
            srows.append(dict(谱=k, 吸收边=edge_key(g), 当前ΔE=round(getattr(g, "e_shift", 0.0) or 0.0, 3),
                              状态=calib_status(g)[0], 与参比时间差_h=None if h is None else round(h, 2)))
        st.dataframe(pd.DataFrame(srows), hide_index=True, width="stretch")
        st.caption("无第三电离室同步参比时，ΔE 只代表测参比时的单色器状态；与参比时间差大的谱可能有 ~0.x eV 漂移。")
        if S.calib:
            with st.container(border=True):
                st.markdown("**换参比 / 补校准**")
                c1, c2 = st.columns([2, 1])
                ref = c1.selectbox("参比", list(S.calib), key="cal_apply_ref")
                c1.caption(f"{S.calib[ref].get('edge_key', '')}，ΔE = {S.calib[ref]['delta_e']:+.3f} eV")
                same = [k for k, g in S.groups.items() if edge_key(g) == S.calib[ref].get("edge_key")]
                bad = [k for k in same if not calib_status(S.groups[k])[1]]
                tg = st.multiselect("应用到（只能选同一吸收边的谱）", same, default=bad, key="cal_apply_tg")
                if c2.button("用此参比校准所选谱", type="primary", disabled=not tg):
                    done, _ = apply_ref(tg, ref)
                    st.success(f"已校准 {len(done)} 条谱")
                    st.rerun()

    # 3) 测定 / 重新测定
    with st.expander("3. 测定 / 重新测定参比 ΔE（新参比、参比重测或换表值时）", expanded=not rows):
        cands = ref_candidates()
        if not cands:
            st.warning("没有单质参比文件：在 meta.csv 中把金属箔/粉标为 role=reference。")
            return
        ref = st.selectbox("单质参比文件", cands, key="cal_ref")
        g = xio.read_bsrf(paths.ROOT / ref)
        ek = f"{g.element}_{g.edge}"
        cfg = load_cfg()
        c1, c2 = st.columns(2)
        e_def = cfg["edges"].get(ek, {}).get("e_table") or edge_energy(g.element, g.edge)
        etab = c1.number_input(f"{g.element} 单质的标准边能量 E_table (eV)", value=float(e_def), format="%.2f",
                               help="默认 config.json / xraydb (Elam) 表值；可改为 Bearden 或文献值")
        sm = c2.number_input("导数平滑 σ (eV)", 0.0, 5.0, 1.0, 0.1)
        r = xcal.calibrate_reference(g, e_table=etab, smooth_ev=sm)
        eg, dmu = g.calib_curve
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=eg, y=dmu, name="dμ/dE (平滑)"))
        fig.add_vline(x=r["e0_meas"], line_dash="dash", annotation_text=f"E0_meas={r['e0_meas']:.2f}")
        fig.add_vline(x=etab, line_dash="dot", line_color="red", annotation_text=f"E_table={etab:.2f}",
                      annotation_position="bottom right")
        st.plotly_chart(fig_layout(fig, f"E (eV, 未校准) — {Path(ref).name}", "dμ/dE"), width="stretch")
        old = S.calib.get(ref)
        c1, c2 = st.columns(2)
        c1.metric("ΔE = E_table − E0_meas", f"{r['delta_e']:+.3f} eV",
                  None if old is None else f"{r['delta_e'] - old['delta_e']:+.3f} vs 已保存", delta_color="off")
        c2.metric("已保存的值", "—" if old is None else f"{old['delta_e']:+.3f} eV", delta_color="off")
        users = [k for k, x in S.groups.items() if ref in str(getattr(x, "calib_ref", ""))]
        if st.button(f"保存此参比的 ΔE（并重新校准用它的 {len(users)} 条已载入谱）", key="cal_save"):
            r = ref_calib(ref, e_table=etab, smooth_ev=sm, force=True)
            done, _ = apply_ref(users, ref)
            st.success(f"已保存到 output/calib/calib.json，重新校准 {len(done)} 条谱。"
                       "注意：命令行 `xafs.py calib` 会用 config.json 的表值重新计算并覆盖此文件。")
            st.rerun()


def norm_controls(prefix=""):
    p = S.norm_par
    c = st.columns(7)
    e0fix = c[0].text_input("E0 固定(空=导数最大)", "" if p.get("e0") is None else str(p["e0"]), key=prefix + "e0")
    p["pre1"] = c[1].number_input("pre1", value=float(p["pre1"]), step=5.0, key=prefix + "pre1")
    p["pre2"] = c[2].number_input("pre2", value=float(p["pre2"]), step=5.0, key=prefix + "pre2")
    p["norm1"] = c[3].number_input("norm1", value=float(p["norm1"]), step=10.0, key=prefix + "n1")
    n2 = c[4].number_input("norm2 (≤0: 距末端)", value=float(p["norm2"] or -10), step=10.0, key=prefix + "n2")
    p["norm2"] = n2
    p["nnorm"] = c[5].selectbox("nnorm", [1, 2, 3], index=[1, 2, 3].index(int(p["nnorm"])), key=prefix + "nn")
    p["smooth_ev"] = c[6].number_input("E0 平滑σ", value=float(p["smooth_ev"]), step=0.5, key=prefix + "sm")
    p["e0"] = float(e0fix) if e0fix.strip() else None
    return p


def page_norm():
    st.header("④ 归一化（Athena）")
    if not S.groups:
        st.info("先导入数据")
        return
    st.caption("所有样品使用同一套归一化参数（相对 E0 的 eV）。E0 = 平滑后一阶导数最大值。")
    norm_controls()
    sel = st.multiselect("选择谱", list(S.groups), default=list(S.groups)[:1])
    if not sel:
        return
    for k in sel:
        try:
            xnorm.normalize(S.groups[k], **{**S.norm_par, "e0": S.norm_par.get("e0") if len(sel) == 1 else None})
        except Exception as ex:
            st.error(f"{k}: {ex}")
    cur = st.selectbox("当前谱（显示边前/边后线）", sel)
    g = S.groups[cur]
    tab1, tab2, tab3, tab4 = st.tabs(["μ(E) + 边前/边后", "归一化叠加", "导数", "合并扫描"])
    with tab1:
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=g.energy, y=g.mu, name="μ(E)"))
        fig.add_trace(go.Scatter(x=g.energy, y=g.pre_edge, name="pre-edge", line=dict(dash="dash")))
        fig.add_trace(go.Scatter(x=g.energy, y=g.post_edge, name="post-edge", line=dict(dash="dash")))
        p = g.norm_params
        for x in (p["pre1"], p["pre2"], p["norm1"], p["norm2"]):
            fig.add_vline(x=g.e0 + x, line_color="gray", line_width=0.5)
        fig.add_vline(x=g.e0, line_color="red", annotation_text=f"E0={g.e0:.2f}")
        st.plotly_chart(fig_layout(fig, "E (eV)", "μ(E)"), width="stretch")
        st.write(f"E0 = **{g.e0:.2f} eV**，edge step = **{g.edge_step:.4f}**"
                 + ("（透射：= Δμt）" if g.mode == "trans" else ""))
    with tab2:
        flat = st.checkbox("flattened", True)
        rel = st.checkbox("横轴 E−E0", False)
        fig = go.Figure()
        for k in sel:
            gg = S.groups[k]
            fig.add_trace(go.Scatter(x=gg.energy - (gg.e0 if rel else 0), y=gg.flat if flat else gg.norm, name=k))
        st.plotly_chart(fig_layout(fig, "E − E0 (eV)" if rel else "E (eV)", "归一化 μ(E)", 500),
                        width="stretch")
    with tab3:
        fig = go.Figure()
        for k in sel:
            gg = S.groups[k]
            fig.add_trace(go.Scatter(x=gg.energy, y=np.gradient(gg.flat, gg.energy), name=k))
        st.plotly_chart(fig_layout(fig, "E (eV)", "d(norm μ)/dE"), width="stretch")
    with tab4:
        st.caption("先逐条检查再平均：与中位谱 RMS 偏差超过阈值的扫描自动剔除，也可手动剔除。")
        msel = st.multiselect("要合并的扫描（同一样品同一条件）", sel, default=sel)
        rej = st.multiselect("手动剔除", msel)
        tol = st.number_input("自动剔除阈值 (×中位 RMS)", 1.0, 20.0, 4.0)
        name = st.text_input("合并后名称", "merge_" + Path(msel[0]).name if msel else "merge")
        if st.button("合并") and len(msel) >= 2:
            m, rep = xnorm.merge_scans([S.groups[k] for k in msel], label=name, reject=rej, tol_sigma=tol)
            S.groups[name] = m
            st.dataframe(pd.DataFrame(rep), hide_index=True)
            pd.DataFrame(rep).to_csv(paths.GUI / f"merge_{re.sub(r'[^A-Za-z0-9_.-]', '_', name)}.csv",
                                     index=False, encoding="utf-8-sig")
            st.success(f"已生成 {name}（{m.nscans} 条扫描）")
    if st.button("导出所选归一化数据到 output/gui/norm/"):
        od = paths.GUI / "norm"
        od.mkdir(exist_ok=True)
        for k in sel:
            fn = od / (re.sub(r"[^A-Za-z0-9_.-]", "_", k) + ".nor")
            xio.write_group_columns(S.groups[k], fn)
        write_params(od / "norm.params.json", S.norm_par, "gui:normalize")
        st.success(f"已导出 {len(sel)} 条到 {od}")


def page_chi():
    st.header("⑤ 背景扣除 χ(k) 与傅里叶变换")
    if not S.groups:
        st.info("先导入数据")
        return
    b, f = S.bkg_par, S.ft_par
    c = st.columns(8)
    b["rbkg"] = c[0].number_input("rbkg", 0.5, 3.0, float(b["rbkg"]), 0.1)
    b["kweight"] = c[1].number_input("bkg kw", 0, 3, int(b["kweight"]))
    f["kmin"] = c[2].number_input("kmin", 0.0, 10.0, float(f["kmin"]), 0.1)
    f["kmax"] = c[3].number_input("kmax", 3.0, 25.0, float(f["kmax"]), 0.1)
    f["dk"] = c[4].number_input("dk", 0.0, 5.0, float(f["dk"]), 0.1)
    f["window"] = c[5].selectbox("窗函数", ["hanning", "kaiser", "sine", "parzen", "welch"],
                                 index=["hanning", "kaiser", "sine", "parzen", "welch"].index(f["window"]))
    f["kweight"] = c[6].selectbox("FT kw", [1, 2, 3], index=[1, 2, 3].index(int(f["kweight"])))
    rmaxp = c[7].number_input("作图 Rmax", 2.0, 10.0, 6.0)
    sel = st.multiselect("选择谱", list(S.groups), default=list(S.groups)[:1])
    if not sel:
        return
    for k in sel:
        try:
            g = S.groups[k]
            if not hasattr(g, "norm_params"):
                xnorm.normalize(g, **S.norm_par)
            xbkg.autobk(g, **b)
            xft.forward(g, **f)
        except Exception as ex:
            st.error(f"{k}: {ex}")
    kw = int(f["kweight"])
    t1, t2, t3, t4 = st.tabs(["χ(k)", "|χ(R)| / Re", "背景 μ0(E)", "k 范围检查"])
    with t1:
        fig = go.Figure()
        for k in sel:
            g = S.groups[k]
            fig.add_trace(go.Scatter(x=g.k, y=g.chi * g.k ** kw, name=k))
        g0 = S.groups[sel[0]]
        sc = max(np.max(np.abs(S.groups[k].chi * S.groups[k].k ** kw)) for k in sel)
        fig.add_trace(go.Scatter(x=g0.k, y=g0.kwin * sc, name="窗函数", line=dict(dash="dot", color="gray")))
        st.plotly_chart(fig_layout(fig, "k (Å⁻¹)", f"k^{kw}χ(k)"), width="stretch")
    with t2:
        showre = st.checkbox("显示 Re χ(R)", False)
        fig = go.Figure()
        for k in sel:
            g = S.groups[k]
            fig.add_trace(go.Scatter(x=g.r, y=g.chir_mag, name=f"|χ(R)| {k}"))
            if showre:
                fig.add_trace(go.Scatter(x=g.r, y=g.chir_re, name=f"Re {k}", line=dict(width=1)))
        fig.update_xaxes(range=[0, rmaxp])
        st.plotly_chart(fig_layout(fig, NOPHASE, f"|χ(R)| (Å^-{kw + 1})", 480), width="stretch")
        st.caption("R 轴未相移校正：峰位比真实键长短约 0.3–0.5 Å。")
    with t3:
        g = S.groups[sel[0]]
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=g.energy, y=g.mu, name="μ(E)"))
        fig.add_trace(go.Scatter(x=g.energy, y=g.bkg, name="μ0(E) 背景"))
        st.plotly_chart(fig_layout(fig, "E (eV)", "μ"), width="stretch")
    with t4:
        g = S.groups[sel[0]]
        elems = st.text_input("样品中所有元素（逗号分隔，用于干扰边检查）", g.element or "")
        try:
            kl, df = xmut.k_limit([e.strip() for e in elems.split(",") if e.strip()], g.element, g.edge,
                                  g.energy[-1])
            st.write(f"数据末端 k = {g.k[-1]:.2f} Å⁻¹；考虑干扰边后可用 k 上限 ≈ **{kl:.2f} Å⁻¹**")
            st.dataframe(df, hide_index=True)
        except Exception as ex:
            st.error(ex)
        c1, c2 = st.columns(2)
        rmin_ = c1.number_input("拟合 Rmin", 0.5, 6.0, 1.0)
        rmax_ = c2.number_input("拟合 Rmax", 1.0, 8.0, 3.0)
        st.write(f"ΔR 分辨率 = π/(2Δk) = **{r_resolution(f['kmin'], f['kmax']):.3f} Å**；"
                 f"N_idp = 2ΔkΔR/π = **{n_idp(f['kmin'], f['kmax'], rmin_, rmax_):.1f}**")
    if st.button("导出 χ(k) 与 χ(R) 到 output/gui/chi/"):
        od = paths.GUI / "chi"
        od.mkdir(exist_ok=True)
        for k in sel:
            g = S.groups[k]
            base = re.sub(r"[^A-Za-z0-9_.-]", "_", k)
            np.savetxt(od / f"{base}.chik", np.column_stack([g.k, g.chi, g.chi * g.k ** kw, g.kwin]),
                       header=f"k chi chi*k^{kw} win", fmt="%.6g")
            np.savetxt(od / f"{base}.chir", np.column_stack([g.r, g.chir_mag, g.chir_re, g.chir_im]),
                       header="r(no phase corr) mag re im", fmt="%.6g")
        write_params(od / "chi.params.json", dict(norm=S.norm_par, bkg=b, ft=f), "gui:chi")
        st.success(f"已导出到 {od}")


def page_wavelet():
    st.header("⑥ 小波变换")
    cands = groups_list(has_chi)
    if not cands:
        st.info("先在 ⑤ 中计算 χ(k)")
        return
    k = st.selectbox("谱", cands)
    c = st.columns(5)
    kind = c[0].selectbox("母小波", ["Morlet", "Cauchy"])
    kw = c[1].selectbox("k 权重", [1, 2, 3], index=1)
    eta = c[2].number_input("η (Morlet)", 1.0, 30.0, 10.0)
    sig = c[3].number_input("σ (Morlet)", 0.2, 5.0, 1.0)
    rmax = c[4].number_input("Rmax", 2.0, 8.0, 5.0)
    g = S.groups[k]
    kmax = S.ft_par["kmax"]
    sel = g.k <= kmax
    if kind == "Morlet":
        kk, rr, W = xwav.morlet(g.k[sel], g.chi[sel], kweight=kw, rmax=rmax, eta=eta, sigma=sig)
    else:
        from larch import Group
        t = Group(k=g.k[sel], chi=g.chi[sel])
        kk, rr, W = xwav.cauchy(t, kweight=kw, rmax_out=rmax)
        m = rr <= rmax
        rr, W = rr[m], W[m]
    fig = go.Figure(go.Heatmap(x=kk, y=rr, z=W, colorscale="Jet"))
    st.plotly_chart(fig_layout(fig, "k (Å⁻¹)", NOPHASE, 550), width="stretch")
    st.caption("重散射体的最大值出现在较高 k，轻散射体（O 等）在较低 k。")


def page_feff():
    st.header("⑦ FEFF 路径计算")
    c1, c2 = st.columns(2)
    with c1:
        src = st.radio("结构来源", ["structures/ 文件夹", "内置结构", "上传（保存到 structures/）"], horizontal=True)
        if src == "内置结构":
            name = st.selectbox("结构", xstruct.BUILTIN_NAMES)
            st.caption(xstruct.SOURCES[name])
            struct = xstruct.builtin(name)
        elif src.startswith("structures"):
            files = xstruct.list_structures()
            if not files:
                st.info("structures/ 中还没有结构文件：把 CIF / POSCAR 放进去，或选“上传”。")
                return
            fn = st.selectbox("结构文件", files)
            name = Path(fn).stem
            struct = xstruct.read_structure(fn)
        else:
            f = st.file_uploader("CIF / POSCAR / .vasp", type=["cif", "vasp", "poscar"])
            if not f:
                return
            dst = paths.STRUCT / f.name
            if not dst.exists():
                dst.write_bytes(f.getvalue())
                st.caption(f"已保存到 {paths.rel(dst)}")
            name = Path(f.name).stem
            struct = xstruct.read_structure(f.name)
        st.text(str(struct.composition) + f"   空间群: {struct.get_space_group_info()}")
    with c2:
        elems = sorted(set(s.specie.symbol for s in struct))
        absorber = st.selectbox("吸收原子", elems)
        edge = st.selectbox("吸收边", ["K", "L3", "L2", "L1"], index=1 if absorber not in ("Co", "Fe", "Ni", "Cu", "Mn", "O") else 0)
        sites = xfeff.inequivalent_sites(struct, absorber)
        site = st.selectbox("不等价位点 (index, 多重度)", sites, format_func=lambda s: f"site {s[0]} ×{s[1]}")
        rmax = st.number_input("RMAX (Å)", 2.0, 10.0, 6.0)
        nleg = st.selectbox("NLEG", [2, 3, 4], index=2)
        out = st.text_input("输出目录", f"{paths.rel(paths.FEFF)}/{name}_{absorber}{edge}/site{site[0]}")
    if st.button("运行 FEFF6L", type="primary"):
        with st.spinner("FEFF 运行中…"):
            try:
                df = xfeff.build(struct, absorber, edge, paths.ROOT / out, site_index=site[0],
                                 rmax=rmax, nleg=nleg, title=name)
                st.success(f"完成：{len(df)} 条路径 → {out}")
            except Exception as ex:
                st.error(ex)
    st.subheader("已有 FEFF 计算")
    dirs = sorted([d for d in paths.FEFF.rglob("*") if d.is_dir() and list(d.glob("feff0001.dat"))])
    if dirs:
        d = st.selectbox("目录", dirs, format_func=lambda p: str(p.relative_to(paths.ROOT)))
        df = xfeff.list_paths(d)
        st.dataframe(df.drop(columns=["file"]), hide_index=True, width="stretch")
        inp = d / "feff.inp"
        if inp.exists():
            with st.expander("feff.inp"):
                st.code(inp.read_text())


def run_saved_model(mf):
    m = json.loads((paths.MODELS / mf).read_text(encoding="utf-8"))
    m.setdefault("name", Path(mf).stem)
    g, _ = pl.build_sample(m["sample"])
    res, dset, summ = xfit.run_fit(g, m)
    S.fits.append(dict(model=m, summ=summ, result=res, curves=xfit.model_curves(dset),
                       report=xfit.report_text(res), time=datetime.datetime.now().strftime("%H:%M:%S")))


def page_fit():
    st.header("⑧ EXAFS 拟合（Artemis）")
    models = sorted(f.name for f in paths.MODELS.glob("*.json") if not f.name.startswith("_")) \
        if paths.MODELS.exists() else []
    with st.expander(f"运行已保存的模型（models/ 中 {len(models)} 个）", expanded=False):
        if models:
            c1, c2 = st.columns([4, 1])
            mf = c1.selectbox("模型", models, key="saved_model")
            if c2.button("运行", key="run_saved", type="primary"):
                try:
                    with st.spinner("拟合中…"):
                        run_saved_model(mf)
                    st.success("完成，结果见下方与“⑨ 拟合历史”")
                except Exception as ex:
                    st.exception(ex)
        else:
            st.caption("在下方建立模型并点“保存结果”后，模型会存入 models/，以后可在这里一键重跑。")
    cands = groups_list(has_chi)
    dirs = sorted([d for d in paths.FEFF.rglob("*") if d.is_dir() and list(d.glob("feff0001.dat"))])
    if not cands or not dirs:
        st.info("需要：⑤ 中已计算 χ(k) 的数据 + ⑦ 中的 FEFF 计算")
        return
    c1, c2 = st.columns(2)
    data_k = c1.selectbox("数据", cands)
    gsel = S.groups[data_k]
    tag = f"_{gsel.element}{gsel.edge}"
    match = [d for d in dirs if tag in str(d.relative_to(paths.FEFF))]
    fdirs = c2.multiselect("FEFF 目录（可多选，多物相/多位点）", dirs,
                           default=match[:1], format_func=lambda p: str(p.relative_to(paths.ROOT)),
                           key="fdirs_" + data_k)
    if not fdirs:
        return
    allp = pd.concat([xfeff.list_paths(d).assign(dir=str(d.relative_to(paths.ROOT))) for d in fdirs],
                     ignore_index=True)
    st.subheader("1. 拟合范围")
    c = st.columns(8)
    kmin = c[0].number_input("kmin", 0.0, 10.0, float(S.ft_par["kmin"]), 0.1, key="fkmin")
    kmax = c[1].number_input("kmax", 3.0, 25.0, float(S.ft_par["kmax"]), 0.1, key="fkmax")
    dk = c[2].number_input("dk", 0.0, 5.0, float(S.ft_par["dk"]), 0.1, key="fdk")
    win = c[3].selectbox("窗", ["hanning", "kaiser", "sine"], key="fwin")
    kws = c[4].multiselect("k 权重", [1, 2, 3], default=[1, 2, 3], key="fkw")
    rmin = c[5].number_input("Rmin", 0.0, 6.0, 1.0, 0.05, key="frmin")
    rmax = c[6].number_input("Rmax", 0.5, 10.0, 3.0, 0.05, key="frmax")
    space = c[7].selectbox("拟合空间", ["r", "k", "q"], key="fsp")
    nidp = n_idp(kmin, kmax, rmin, rmax)
    st.write(f"N_idp = **{nidp:.1f}**；参数上限建议 ≤ N_idp/2 = **{nidp / 2:.1f}**")

    st.subheader("2. 路径（勾选使用；N 留空=FEFF 简并度；均可写表达式）")
    key = "pathtab_" + "|".join(str(d) for d in fdirs)
    if key not in S:
        # 默认：同一散射元素、reff 相差 <0.1 Å 的路径共用 ΔR/σ²（一个“壳层”）；
        # 只勾选第一个壳层；N 默认为 FEFF 简并度（固定数值）
        rows, shells = [], []
        for i, r in allp.iterrows():
            key_ = (r.label, r.nleg)
            sh = next((j for j, (k0, r0) in enumerate(shells) if k0 == key_ and abs(r.reff - r0) < 0.1), None)
            if sh is None:
                shells.append((key_, r.reff))
                sh = len(shells) - 1
            rows.append(dict(use=bool(sh == 0), file=r.file, label=f"{r.label}@{r.reff:.3f}", reff=r.reff,
                             degen=r.degen, nleg=r.nleg, amp_ratio=r.amp_ratio, N=f"{r.degen:g}",
                             s02="s02", e0="e0", deltar=f"dr{sh + 1}", sigma2=f"ss{sh + 1}", third="",
                             dir=r.dir))
        S[key] = pd.DataFrame(rows)
    ptab = st.data_editor(S[key], hide_index=True, width="stretch",
                          disabled=["file", "reff", "degen", "nleg", "amp_ratio", "dir"],
                          column_config={"file": None}, key=key + "_ed")
    used = ptab[ptab.use]
    names = []
    for _, r in used.iterrows():
        for col in ("N", "s02", "e0", "deltar", "sigma2", "third"):
            for t in idents(r[col]):
                if t not in names:
                    names.append(t)

    st.subheader("3. 参数（vary=否 即固定；expr 非空 即约束）")
    ptk = "partab"
    old = S.get(ptk, pd.DataFrame(columns=["name", "value", "vary", "min", "max", "expr"]))
    defaults = {"s02": (0.85, True, 0.3, 1.5), "e0": (0.0, True, -15, 15)}
    rows = []
    for n in names:
        if n in set(old.name):
            rows.append(old[old.name == n].iloc[0].to_dict())
        else:
            v, vary, lo, hi = defaults.get(n, (0.003, True, 0.0, 0.05) if n.startswith("ss") else
                                           (0.0, True, -0.5, 0.5) if n.startswith("dr") else
                                           (1.0, True, None, None))
            rows.append(dict(name=n, value=v, vary=vary, min=lo, max=hi, expr=""))
    ptab2 = st.data_editor(pd.DataFrame(rows, columns=["name", "value", "vary", "min", "max", "expr"]),
                           hide_index=True, width="stretch", disabled=["name"], key="pared")
    S[ptk] = pd.concat([old[~old.name.isin(ptab2.name)], ptab2], ignore_index=True)
    nvary = int(((ptab2.vary) & (ptab2.expr.fillna("") == "")).sum())
    (st.warning if nvary > nidp / 2 else st.write)(f"变量数 = {nvary}（N_idp/2 = {nidp / 2:.1f}）")

    mname = st.text_input("模型名", f"{Path(data_k).name}_{len(used)}paths")
    if st.button("拟合", type="primary") and len(used):
        params = {}
        for _, r in ptab2.iterrows():
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
        model = dict(name=mname, kmin=kmin, kmax=kmax, dk=dk, window=win, kweight=kws or [2],
                     rmin=rmin, rmax=rmax, fitspace=space, params=params, paths=mpaths,
                     norm=S.norm_par, bkg=S.bkg_par)
        try:
            with st.spinner("拟合中…"):
                res, dset, summ = xfit.run_fit(S.groups[data_k], model)
            S.fits.append(dict(model=model, summ=summ, result=res, curves=xfit.model_curves(dset),
                               report=xfit.report_text(res), time=datetime.datetime.now().strftime("%H:%M:%S")))
        except Exception as ex:
            st.exception(ex)
    if S.fits:
        show_fit(S.fits[-1], key="last")


def show_fit(fit, key=""):
    s, c = fit["summ"], fit["curves"]
    m = st.columns(5)
    m[0].metric("R 因子", f"{s['rfactor']:.4f}")
    m[1].metric("χ²_ν", f"{s['chi2_reduced']:.1f}")
    m[2].metric("N_idp", f"{s['n_idp']:.1f}")
    m[3].metric("变量数", s["nvarys"])
    m[4].metric("模型", s["model"])
    for w in s["warnings"]:
        st.warning(w)
    pt = pd.DataFrame([dict(参数=k, 值=v["value"], 误差=v["stderr"], 变化=v["vary"], 表达式=v["expr"])
                       for k, v in s["params"].items()])
    pp = pd.DataFrame(s["paths"])
    c1, c2 = st.columns(2)
    c1.dataframe(pt, hide_index=True, width="stretch")
    c2.dataframe(pp, hide_index=True, width="stretch")
    kw = st.selectbox("显示 k 权重", [1, 2, 3], index=1, key="kwshow" + key)
    fig = make_subplots(rows=1, cols=2, subplot_titles=(f"k^{kw}χ(k)", "χ(R)（未相移校正）"))
    fig.add_trace(go.Scatter(x=c["k"], y=c["chi"] * c["k"] ** kw, name="数据", line=dict(color="black")), 1, 1)
    fig.add_trace(go.Scatter(x=c["kfit"], y=c["chifit"] * c["kfit"] ** kw, name="拟合",
                             line=dict(color="red", dash="dash")), 1, 1)
    # R 空间按所选 kw 重新变换
    from larch import Group
    from larch.xafs import xftf
    md = fit["model"]
    gd = Group(k=c["k"], chi=c["chi"])
    gf = Group(k=c["kfit"], chi=c["chifit"])
    for gg in (gd, gf):
        xftf(gg, kmin=md["kmin"], kmax=md["kmax"], dk=md["dk"], window=md["window"], kweight=kw)
    fig.add_trace(go.Scatter(x=gd.r, y=gd.chir_mag, name="|χ(R)| 数据", line=dict(color="black")), 1, 2)
    fig.add_trace(go.Scatter(x=gf.r, y=gf.chir_mag, name="|χ(R)| 拟合", line=dict(color="red", dash="dash")), 1, 2)
    fig.add_trace(go.Scatter(x=gd.r, y=gd.chir_re, name="Re 数据", line=dict(color="blue", width=1)), 1, 2)
    fig.add_trace(go.Scatter(x=gf.r, y=gf.chir_re, name="Re 拟合", line=dict(color="magenta", width=1, dash="dash")), 1, 2)
    fig.add_vrect(x0=md["rmin"], x1=md["rmax"], fillcolor="gray", opacity=0.12, row=1, col=2)
    fig.update_xaxes(range=[0, 6], row=1, col=2)
    st.plotly_chart(fig_layout(fig, "", "", 480), width="stretch")
    with st.expander("完整拟合报告 (feffit_report)"):
        st.code(fit["report"])
    c1, c2, c3 = st.columns(3)
    if c1.button("保存结果到 output/fits/exafs_fits.csv", key="save" + key):
        xfit.write_result_row(s, paths.FITS_CSV)
        base = re.sub(r"[^A-Za-z0-9_.-]", "_", s["model"])
        (paths.MODELS / f"{base}.json").write_text(json.dumps(md, ensure_ascii=False, indent=2), encoding="utf-8")
        (paths.FITS / f"{base}.fit_report.txt").write_text(fit["report"], encoding="utf-8")
        from xafsmith import report as xrep
        xrep.plot_fit(c, s, kweight=kw, out=paths.FIGS / f"{base}_fit.png")
        st.success("已保存：output/fits/exafs_fits.csv、output/fits/*.fit_report.txt、models/*.json、output/figs/*_fit.png")


def page_history():
    st.header("⑨ 拟合历史与 F 检验")
    if not S.fits:
        st.info("暂无拟合")
        return
    rows = [dict(i=i, time=f["time"], sample=f["summ"]["sample"], model=f["summ"]["model"],
                 rfactor=f["summ"]["rfactor"], chi2r=f["summ"]["chi2_reduced"],
                 nvarys=f["summ"]["nvarys"], n_idp=f["summ"]["n_idp"]) for i, f in enumerate(S.fits)]
    st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch")
    if st.button("把以上全部拟合保存到 output/fits/（汇总报告会用到）"):
        for f in S.fits:
            save_fit(f)
        st.success(f"已保存 {len(S.fits)} 个拟合")
    i = st.selectbox("查看拟合", range(len(S.fits)), index=len(S.fits) - 1)
    show_fit(S.fits[i], key=f"h{i}")
    st.subheader("F 检验（Hamilton）：嵌套模型比较")
    c1, c2 = st.columns(2)
    a = c1.selectbox("简单模型", range(len(S.fits)), key="fa")
    b = c2.selectbox("复杂模型", range(len(S.fits)), key="fb", index=len(S.fits) - 1)
    if st.button("比较"):
        st.json(xfit.hamilton_test(S.fits[a]["result"], S.fits[b]["result"]))


def page_lcf():
    st.header("⑩ 线性组合拟合 (LCF)")
    if len(S.groups) < 2:
        st.info("至少需要两条谱")
        return
    for g in S.groups.values():
        if not hasattr(g, "flat"):
            xnorm.normalize(g, **S.norm_par)
    c1, c2 = st.columns(2)
    smp = c1.selectbox("样品", list(S.groups))
    stds = c2.multiselect("端点标样（必须是实测标样）", [k for k in S.groups if k != smp])
    c = st.columns(6)
    space = c[0].selectbox("空间", ["norm", "dmude", "chik"])
    xmin = c[1].number_input("下限 (eV 相对E0 或 k)", value=-20.0 if space != "chik" else 3.0)
    xmax = c[2].number_input("上限", value=30.0 if space != "chik" else 10.0)
    s1 = c[3].checkbox("权重和=1", True)
    bd = c[4].checkbox("0≤w≤1", True)
    es = c[5].checkbox("拟合能量平移", False)
    note = st.text_input("备注（如使用非实测端点，必须在此注明为假设）", "")
    if stds and st.button("LCF", type="primary"):
        try:
            if space == "chik":
                for k in [smp] + stds:
                    if not has_chi(S.groups[k]):
                        process(S.groups[k], norm=False, ft=False)
            r = xlcf.lcf(S.groups[smp], [S.groups[k] for k in stds], xmin=xmin, xmax=xmax, space=space,
                         sum_to_one=s1, bounds=bd, fit_eshift=es, kweight=2)
            S.lcf_last = r
            S.lcf_single = xlcf.single_standard_compare(S.groups[smp], [S.groups[k] for k in stds],
                                                        xmin=xmin, xmax=xmax, space=space)
            if len(stds) > 2:
                S.lcf_combo = xlcf.fit_all_combinations(S.groups[smp], [S.groups[k] for k in stds],
                                                        xmin=xmin, xmax=xmax, space=space,
                                                        sum_to_one=s1, bounds=bd)
            else:
                S.pop("lcf_combo", None)
            row = xlcf.result_row(r, note)
            csv = paths.LCF_CSV
            pd.DataFrame([row]).to_csv(csv, mode="a", header=not csv.exists(), index=False, encoding="utf-8-sig")
        except Exception as ex:
            st.exception(ex)
    if "lcf_last" in S:
        r = S.lcf_last
        m = st.columns(3)
        m[0].metric("R 因子", f"{r['rfactor']:.5f}")
        m[1].metric("χ²_ν", f"{r['chi2_reduced']:.2e}")
        m[2].metric("Σw", f"{r['sum_weights']:.3f}")
        st.dataframe(pd.DataFrame(dict(权重=r["weights"], 误差=r["weights_err"])), width="stretch")
        cv = r["curves"]
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=cv["x"], y=cv["y"], name="样品", line=dict(color="black")))
        fig.add_trace(go.Scatter(x=cv["x"], y=cv["fit"], name="LCF", line=dict(color="red", dash="dash")))
        for k, v in cv["comps"].items():
            fig.add_trace(go.Scatter(x=cv["x"], y=v, name=k, line=dict(width=1)))
        fig.add_trace(go.Scatter(x=cv["x"], y=cv["y"] - cv["fit"], name="残差", line=dict(color="gray", width=1)))
        st.plotly_chart(fig_layout(fig, "E − E0 (eV)" if r["space"] != "chik" else "k (Å⁻¹)", ""),
                        width="stretch")
        st.write("单一标样拟合比较：")
        st.dataframe(S.lcf_single, hide_index=True)
        if "lcf_combo" in S:
            st.write("所有组合（按 R 因子排序）：")
            st.dataframe(S.lcf_combo, hide_index=True)
        st.caption("结果追加到 output/lcf/lcf_results.csv")


def page_planner():
    st.header("⑪ 样品设计（透射 μt / 边跳 / 干扰边）")
    c = st.columns(4)
    formula = c[0].text_input("样品化学式", "IrO2")
    el = c[1].text_input("目标元素", "Ir")
    ed = c[2].selectbox("吸收边", ["K", "L3", "L2", "L1"], index=1)
    area = c[3].number_input("压片面积 (cm²)", 0.1, 10.0, 1.327, help="φ13 mm = 1.327 cm²")
    c = st.columns(4)
    dil = c[0].text_input("稀释剂（空=无）", "BN")
    mdil = c[1].number_input("稀释剂质量 (mg)", 0.0, 1000.0, 100.0)
    tgt = c[2].number_input("目标总 μt", 0.5, 4.0, 2.0)
    mass = c[3].number_input("样品质量 (mg，0=只推荐)", 0.0, 1000.0, 0.0)
    try:
        r = xmut.recommend_mass(formula, area, el, ed, tgt, dil or None, mdil)
        st.write(f"推荐样品质量 **{r['mass_mg']:.2f} mg** → 边后总 μt={r['mut_above']:.2f}，"
                 f"边跳 Δμt={r['edge_step']:.2f}。{r['advice']}")
        if mass > 0:
            st.json(xmut.mut_for_mass(formula, mass, area, el, ed, dil or None, mdil))
    except Exception as ex:
        st.error(ex)
    elems = st.text_input("体系中全部元素（干扰边检查）", "Ir,Ta,Co,O,K")
    emax = st.number_input("扫描上限 (eV)", value=float(edge_energy(el, ed) + 1000))
    df = xmut.interfering_edges([e.strip() for e in elems.split(",") if e.strip()], el, ed, emax)
    st.dataframe(df, hide_index=True)
    st.caption("数据：xraydb (Elam 表)。总 μt 1.5–2.6 最佳，Δμt ≥ 0.2；均匀性比 Δμt 精确匹配更重要。")


# ----------------------------------------------------------------------------- ⓪ 项目
RECENT = Path.home() / ".xafsmith" / "recent.json"


def recent_projects():
    try:
        return [p for p in json.loads(RECENT.read_text(encoding="utf-8")) if paths.is_project(p)]
    except Exception:
        return []


def remember(root):
    lst = [str(root)] + [p for p in recent_projects() if p != str(root)]
    try:
        RECENT.parent.mkdir(parents=True, exist_ok=True)
        RECENT.write_text(json.dumps(lst[:10], ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception:
        pass


def pick_folder(key):
    """弹出本机“选择文件夹”对话框，结果写入 S[key]"""
    try:
        import tkinter as tk
        from tkinter import filedialog
        root = tk.Tk()
        root.withdraw()
        root.wm_attributes("-topmost", 1)
        d = filedialog.askdirectory(title="选择项目文件夹")
        root.destroy()
        if d:
            S[key] = str(Path(d))
    except Exception as ex:
        st.warning(f"无法打开文件夹对话框（{ex}），请直接粘贴路径。")


def switch_project(root):
    paths.set_root(root)
    paths.ensure()
    remember(paths.ROOT)
    for k in list(S.keys()):
        del S[k]
    st.rerun()


def open_folder(p):
    p = Path(p)
    p.mkdir(parents=True, exist_ok=True)
    try:
        os.startfile(str(p))            # Windows
    except AttributeError:
        subprocess.Popen(["open" if sys.platform == "darwin" else "xdg-open", str(p)])


def page_project():
    st.header("⓪ 项目")
    is_proj = paths.is_project(paths.ROOT)
    if is_proj:
        remember(paths.ROOT)
        st.success(f"当前项目：**{paths.ROOT}**")
    else:
        st.warning(f"当前目录不是 XAFSmith 项目：{paths.ROOT}。请在下面打开或新建一个项目。")

    with st.expander("打开 / 新建项目", expanded=not is_proj):
        rec = recent_projects()
        if rec:
            c1, c2 = st.columns([3, 1])
            pick = c1.selectbox("最近的项目", rec, key="prj_recent")
            if c2.button("打开", key="prj_open_recent"):
                switch_project(pick)
        c1, c2 = st.columns([1, 4])
        if c1.button("📁 浏览…", key="prj_browse"):
            pick_folder("prj_path")
        folder = c2.text_input("项目文件夹（点“浏览…”选择，或粘贴路径）", key="prj_path")
        c1, c2 = st.columns(2)
        if c1.button("打开此文件夹", disabled=not folder):
            if paths.is_project(folder):
                switch_project(folder)
            else:
                st.error(f"{folder} 中没有 xafsmith.json，不是项目；可以点“新建项目”。")
        if c2.button("新建项目（已有文件不会被覆盖）", type="primary", disabled=not folder):
            from xafsmith.cli import create_project
            create_project(folder)
            switch_project(folder)
    if not is_proj:
        return

    t = st.tabs(["1 数据登记", "2 检查", "3 一键处理", "4 处理参数", "5 结构文件", "6 输出"])
    with t[0]:
        st.markdown("原始数据放在 **data/raw/<批次>/**，每个批次带该批次测的单质参比（文件名含 foil / powder / metal）。")
        with st.form("upload_raw"):
            c1, c2 = st.columns([1, 2])
            batch = c1.text_input("批次文件夹名", "批次1")
            ups = c2.file_uploader("上传原始数据文件到 data/raw/<批次>/", accept_multiple_files=True)
            if st.form_submit_button("上传") and ups:
                d = paths.RAW / batch
                d.mkdir(parents=True, exist_ok=True)
                n = 0
                for f in ups:
                    if not (d / f.name).exists():
                        (d / f.name).write_bytes(f.getvalue())
                        n += 1
                st.success(f"已保存 {n} 个文件到 {paths.rel(d)}（已存在的同名文件未覆盖）")
        if st.button("扫描 data/raw，登记新文件", type="primary"):
            meta, n = pl.scan_raw()
            cfg = pl.init_config(meta)
            st.success(f"新增 {n} 行；吸收边 {list(cfg['edges'])}")
        if paths.META.exists():
            meta = pd.read_csv(paths.META, dtype=str, encoding="utf-8-sig").fillna("")
            if len(meta):
                st.caption("可以直接改：sample（同名 = 合并）、role、use（0 = 不用，须写 note）、ref_file（校准参比）、note。改完点保存。")
                refs = [""] + sorted(set(meta[meta.role == "reference"].file))
                ed = st.data_editor(
                    meta, hide_index=True, width="stretch", key="meta_editor",
                    disabled=["file", "edge_key", "time", "npts", "emax", "batch"],
                    column_config={
                        "role": st.column_config.SelectboxColumn("role", options=["reference", "standard", "sample"]),
                        "use": st.column_config.SelectboxColumn("use", options=["1", "0"]),
                        "mode": st.column_config.SelectboxColumn("mode", options=["trans", "fluo"]),
                        "ref_file": st.column_config.SelectboxColumn("ref_file", options=refs, width="large"),
                    })
                if st.button("保存 meta.csv"):
                    ed.to_csv(paths.META, index=False, encoding="utf-8-sig")
                    st.success("已保存。改了 ref_file 或 role 后请到“3 一键处理”重新校准。")
            else:
                st.info("meta.csv 还是空的：放入数据后点“扫描 data/raw”。")
    with t[1]:
        st.caption("按数据标准检查：文件是否存在、每条谱是否有参比、参数是否完整、模型路径是否存在。")
        if st.button("运行检查"):
            from xafsmith import schema
            rep = schema.validate(structures=True)
            tab = rep.table()
            (st.error if rep.n_err else st.success)(f"{rep.n_err} 个错误，{len(tab) - rep.n_err} 个警告")
            if len(tab):
                st.dataframe(tab, hide_index=True, width="stretch")
    with t[2]:
        st.caption("按 xafsmith.json 与 meta.csv 批量处理全部样品；结果写入 output/。")
        c1, c2, c3 = st.columns(3)
        if c1.button("① 质量检查", width="stretch"):
            with st.spinner("检查中…"):
                df = pl.run_qc()
            cols = [c for c in ["label", "mode", "e0", "edge_step_mu", "n_glitches", "glitch_E", "i0_drops",
                                "k_snr3", "self_abs_risk", "error"] if c in df]
            st.dataframe(df[cols], hide_index=True, width="stretch")
            st.caption(f"→ {paths.rel(paths.QC_CSV)}")
        if c2.button("② 按参比校准", width="stretch"):
            res = pl.run_calib(pl.load_config(), pl.load_meta())
            S.calib = res
            st.dataframe(pd.DataFrame([dict(参比=k, 吸收边=v["edge_key"], 批次=v.get("batch", ""),
                                            E0_meas=round(v["e0_meas"], 2), E_table=v["e_table"],
                                            ΔE=round(v["delta_e"], 3), 谱数=len(v["time_gap_hours"]))
                                       for k, v in res.items()]), hide_index=True, width="stretch")
            miss = pl.load_meta().query("ref_file == ''")
            if len(miss):
                st.warning(f"{len(miss)} 条谱没有参比，不能处理：" + "，".join(miss.file))
        if c3.button("③ 处理全部样品", type="primary", width="stretch"):
            with st.spinner("校准 → 归一化 → 合并 → χ(k) → FT …"):
                df, _ = pl.process_all()
            st.dataframe(df, hide_index=True, width="stretch")
            st.caption(f"→ {paths.rel(paths.PROC)}/、{paths.rel(paths.FIGS)}/；之后在“① 数据导入”中按样品载入查看")
    with t[3]:
        cfg = pl.load_config()
        edges = list(cfg.get("edges", {}))
        if not edges:
            st.info("还没有吸收边：先在“1 数据登记”中扫描 data/raw。")
        else:
            ek = st.selectbox("吸收边", edges, key="cfg_edge")
            c = cfg["edges"][ek]
            st.caption(f"{c['element']} {c['edge']}，表值 E0 = {c.get('e_table')} eV（{c.get('e_table_source', '')}）。"
                       "同一吸收边的所有样品使用这一套参数。")
            with st.form("cfg_form"):
                el = st.text_input("样品中的全部元素（逗号分隔，用于干扰边检查）",
                                   ", ".join(c.get("elements_in_sample", [c["element"]])))
                st.markdown("**归一化**")
                n = c["norm"]
                cc = st.columns(6)
                pre1 = cc[0].number_input("pre1", value=float(n["pre1"]))
                pre2 = cc[1].number_input("pre2", value=float(n["pre2"]))
                norm1 = cc[2].number_input("norm1", value=float(n["norm1"]))
                norm2 = cc[3].number_input("norm2（≤0 距末端）", value=float(n.get("norm2") or -10))
                nnorm = cc[4].selectbox("nnorm", [1, 2, 3], index=[1, 2, 3].index(int(n["nnorm"])))
                sm = cc[5].number_input("E0 平滑 σ", value=float(n.get("smooth_ev", 1.0)))
                st.markdown("**背景扣除 / 傅里叶变换**")
                b, f = c["bkg"], c["ft"]
                cc = st.columns(7)
                rbkg = cc[0].number_input("rbkg", value=float(b["rbkg"]))
                bkw = cc[1].selectbox("背景 k 权重", [1, 2, 3], index=[1, 2, 3].index(int(b["kweight"])))
                kmin = cc[2].number_input("kmin", value=float(f["kmin"]))
                kmax = cc[3].number_input("kmax", value=float(f["kmax"]))
                dk = cc[4].number_input("dk", value=float(f["dk"]))
                wins = ["hanning", "kaiser", "sine"]
                win = cc[5].selectbox("窗", wins, index=wins.index(f["window"]) if f["window"] in wins else 0)
                fkw = cc[6].selectbox("FT k 权重", [1, 2, 3], index=[1, 2, 3].index(int(f["kweight"])))
                st.markdown("**S0²（标样上拟合得到，样品拟合时固定）**")
                s0 = c.get("s02_recommended", {})
                cc = st.columns(3)
                s0v = cc[0].number_input("S0²", value=float(s0.get("value", 0.8)), step=0.01)
                s0e = cc[1].number_input("误差", value=float(s0.get("err", 0.0)), step=0.01)
                s0s = cc[2].text_input("来源", s0.get("source", ""))
                if st.form_submit_button("保存参数", type="primary"):
                    c["elements_in_sample"] = [x.strip() for x in el.split(",") if x.strip()]
                    c["norm"].update(pre1=pre1, pre2=pre2, norm1=norm1, norm2=norm2, nnorm=nnorm, smooth_ev=sm)
                    c["bkg"].update(rbkg=rbkg, kweight=bkw)
                    c["ft"].update(kmin=kmin, kmax=kmax, dk=dk, window=win, kweight=fkw)
                    c["s02_recommended"] = dict(s0, value=s0v, err=s0e, source=s0s)
                    paths.CONFIG.write_text(json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8")
                    st.success("已保存到 xafsmith.json；改动后请重新“③ 处理全部样品”。")
    with t[4]:
        files = xstruct.list_structures()
        st.write(f"**structures/** 中有 {len(files)} 个结构文件" + ("：" + "，".join(files) if files else "。"))
        ups = st.file_uploader("上传结构文件（CIF / POSCAR / .vasp）到 structures/", accept_multiple_files=True,
                               key="struct_up")
        if ups and st.button("保存结构文件"):
            for f in ups:
                (paths.STRUCT / f.name).write_bytes(f.getvalue())
            st.success("已保存；在 ⑦ FEFF 路径 中选择“structures/ 文件夹”使用。")
        if st.button("把内置结构导出为 CIF（structures/builtin/）"):
            st.success("，".join(p.name for p in xstruct.export_builtin()))
    with t[5]:
        st.write("全部结果都在 **output/**（可以删除后重新生成）：")
        rows = [dict(目录=paths.rel(d), 文件数=sum(1 for x in d.rglob("*") if x.is_file()) if d.exists() else 0)
                for d in paths.OUTPUT_DIRS]
        st.dataframe(pd.DataFrame(rows), hide_index=True)
        c1, c2 = st.columns(2)
        if c1.button("打开 output 文件夹"):
            open_folder(paths.OUT)
        if c2.button("打开项目文件夹"):
            open_folder(paths.ROOT)



# ----------------------------------------------------------------------------- ⑫ 汇总
def save_fit(fit):
    from xafsmith import report as xrep
    s_, md = fit["summ"], fit["model"]
    xfit.write_result_row(s_, paths.FITS_CSV)
    base = re.sub(r"[^A-Za-z0-9_.-]", "_", s_["model"])
    paths.MODELS.mkdir(parents=True, exist_ok=True)
    (paths.MODELS / f"{base}.json").write_text(json.dumps(md, ensure_ascii=False, indent=2), encoding="utf-8")
    (paths.FITS / f"{base}.fit_report.txt").write_text(fit["report"], encoding="utf-8")
    kw = md["kweight"][-1] if isinstance(md["kweight"], list) else md["kweight"]
    xrep.plot_fit(fit["curves"], s_, kweight=kw, out=paths.FIGS / f"{base}_fit.png")


def page_summary():
    st.header("⑫ 汇总报告")
    st.markdown("把项目中**已保存**的全部结果整理成一个 **Excel 工作簿** 和一份 **带图的 HTML 报告**："
                "样品清单、能量校准、质量检查、处理结果、EXAFS 拟合（每个模型一行的概要 + 每条路径的参数）、LCF、处理参数。")
    if S.fits:
        st.info(f"本次会话有 {len(S.fits)} 个拟合。只有保存过的拟合会进入汇总。")
        if st.button("先把本次会话的全部拟合保存"):
            for f in S.fits:
                save_fit(f)
            st.success("已保存")
    from xafsmith import summary
    if st.button("生成汇总", type="primary"):
        with st.spinner("整理中…"):
            S.summary_dir = str(summary.build())
    if S.get("summary_dir"):
        out = Path(S.summary_dir)
        st.success(f"已生成：{paths.rel(out)}")
        c1, c2, c3 = st.columns(3)
        c1.download_button("下载 汇总.xlsx", (out / "汇总.xlsx").read_bytes(), file_name=f"{paths.ROOT.name}_汇总.xlsx")
        c2.download_button("下载 汇总报告.html", (out / "汇总报告.html").read_bytes(),
                           file_name=f"{paths.ROOT.name}_汇总报告.html", mime="text/html")
        if c3.button("打开汇总文件夹"):
            open_folder(out)
        st.caption("HTML 报告与 figs/ 文件夹放在一起才能显示图；用“打开汇总文件夹”后双击 汇总报告.html。")
    sheets = summary.collect()
    if sheets:
        st.subheader("预览")
        name = st.selectbox("表", list(sheets))
        st.dataframe(sheets[name], hide_index=True, width="stretch")
    else:
        st.caption("项目中还没有结果：先在“⓪ 项目 → 一键处理”中处理，再做拟合。")


PAGES = {"⓪ 项目": page_project, "① 数据导入": page_import, "② 质量检查": page_qc, "③ 能量校准": page_calib,
         "④ 归一化 (Athena)": page_norm, "⑤ χ(k) 与 FT": page_chi, "⑥ 小波变换": page_wavelet,
         "⑦ FEFF 路径": page_feff, "⑧ EXAFS 拟合 (Artemis)": page_fit, "⑨ 拟合历史/F检验": page_history,
         "⑩ LCF": page_lcf, "⑪ 样品设计": page_planner,
         "⑫ 汇总报告": page_summary, "❓ 使用指南": None}

with st.sidebar:
    st.title("XAFSmith")
    if paths.is_project(paths.ROOT):
        page = st.radio("功能", list(PAGES), label_visibility="collapsed")
    else:
        page = "⓪ 项目"
        st.info("先打开或新建项目")
    st.divider()
    st.caption(f"已载入 {len(S.groups)} 条谱 · 拟合 {len(S.fits)} 次")
    st.caption(f"项目：{paths.ROOT.name}")
    if st.button("保存会话参数"):
        write_params(paths.GUI / "gui_session.params.json",
                     dict(norm=S.norm_par, bkg=S.bkg_par, ft=S.ft_par, calib=S.calib,
                          groups=list(S.groups)), "gui")
        st.success("已保存 output/gui/gui_session.params.json")
    st.divider()
    from xafsmith import __version__
    st.caption(f"**XAFSmith** v{__version__}  \n"
               "Developed by **Eggy** & **Claude** (Anthropic)  \n"
               "Powered by xraylarch · FEFF6L · xraydb")

if page == "❓ 使用指南":
    from xafsmith import __version__
    with st.container(border=True):
        st.markdown(f"#### About XAFSmith\n"
                    f"Version {__version__} · General-purpose XAFS (XANES/EXAFS) processing and fitting.  \n"
                    "**Developed by Eggy & Claude** (Anthropic).  \n"
                    "Built on [xraylarch](https://xraypy.github.io/xraylarch/) (FEFF6L, feffit), xraydb, lmfit, "
                    "pymatgen and Streamlit.  \n"
                    "Source: https://github.com/Wiolic/XAFSmith")
    st.markdown((Path(__file__).resolve().parent / "docs" / "图形界面使用指南.md").read_text(encoding="utf-8"))
else:
    PAGES[page]()
