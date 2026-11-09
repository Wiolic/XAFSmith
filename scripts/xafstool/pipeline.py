"""pipeline —— 配置驱动的批处理：meta.csv + config.json → 校准 → 归一化 → 合并 → χ(k) → FT。

文件约定（相对项目根目录）：
  data/raw/                原始数据（只读）
  data/meta.csv            每个文件一行：file, sample, edge_key, mode, role, use, time, ..., batch, ref_file
                             role ∈ reference（校准用参比箔）| standard（标样）| sample
                             同一 sample 名的多行 = 多次扫描，处理时合并
                             use = 0 表示不用（须在 note 写理由）
                             batch = data/raw 下第一级文件夹（一次测量批次）
                             ref_file = 校准本条谱所用的参比（默认：同批次、同吸收边的 role=reference 文件）
                             —— 没有 ref_file 的谱不能处理（必须与参比一起校准）
  config.json              每个吸收边（edge_key，如 Ir_L3）的统一处理参数
  results/processed/       处理结果（.nor / .chik / .chir）与 process_summary.csv
  results/calib.json       校准记录，按参比文件索引：{ref_file: {delta_e, e0_meas, e_table, ...}}

所有函数都从原始数据重新生成结果。
"""
import json
import re
from pathlib import Path

import numpy as np
import pandas as pd

from .common import PROJECT_ROOT, edge_energy, write_params
from . import io as xio
from . import normalize as xnorm
from . import autobk as xbkg
from . import ft as xft
from . import calib as xcal

META = PROJECT_ROOT / "data" / "meta.csv"
CONFIG = PROJECT_ROOT / "config.json"
RESULTS = PROJECT_ROOT / "results"
PROC = RESULTS / "processed"
META_COLS = ["file", "sample", "edge_key", "mode", "role", "use", "time", "npts", "emax", "note",
             "batch", "ref_file"]


def safe(name):
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", str(name)).strip("_")


def batch_of(rel):
    """data/raw/<批次>/... → 批次名"""
    parts = Path(rel).as_posix().split("/")
    return parts[2] if len(parts) > 3 and parts[:2] == ["data", "raw"] else ""


def assign_refs(meta):
    """给 ref_file 为空的行填参比：同批次、同吸收边的 role=reference 文件（多个时取测量时间最近的）。"""
    from .calib import time_gap_hours
    meta = meta.copy()
    for c in ("batch", "ref_file"):
        if c not in meta:
            meta[c] = ""
    meta["batch"] = [b or batch_of(f) for b, f in zip(meta.batch, meta.file)]
    for i, r in meta.iterrows():
        if r.ref_file:
            continue
        refs = meta[(meta.role == "reference") & (meta.edge_key == r.edge_key) & (meta.batch == r.batch)]
        if r.role == "reference":
            meta.at[i, "ref_file"] = r.file
        elif len(refs):
            gaps = [time_gap_hours(r.time, t) for t in refs.time]
            j = int(np.argmin([g if g is not None else 1e9 for g in gaps]))
            meta.at[i, "ref_file"] = refs.file.iloc[j]
    return meta


# ------------------------------------------------------------------ meta / config
def scan_raw(raw_dir=None, meta_path=META):
    """扫描 data/raw，生成/更新 meta.csv（已存在的行保留用户的修改）。"""
    raw_dir = Path(raw_dir or PROJECT_ROOT / "data" / "raw")
    old = pd.read_csv(meta_path, dtype=str).fillna("") if Path(meta_path).exists() else \
        pd.DataFrame(columns=META_COLS)
    for c in META_COLS:
        if c not in old:
            old[c] = ""
    old["batch"] = [b or batch_of(f) for b, f in zip(old.batch, old.file)]
    known = set(old.file)
    taken = dict(zip(old["sample"], old.batch))      # 样品名 → 批次
    rows = []
    for p in sorted(raw_dir.rglob("*")):
        if not p.is_file():
            continue
        rel = p.relative_to(PROJECT_ROOT).as_posix()
        if rel in known or not xio.is_bsrf(p):
            continue
        try:
            g = xio.read_bsrf(p)
        except Exception:
            continue
        name = p.name
        role = "reference" if re.search(r"foil|powder|metal", name, re.I) else \
            ("sample" if re.search(r"insitu|_\d|ocp|v$|V$", rel, re.I) else "standard")
        sample = re.sub(r"_(\d)$", "", name)          # 去掉 _2/_3 等重复扫描后缀
        batch = batch_of(rel)
        if taken.get(sample, batch) != batch:         # 与其他批次重名 → 加批次名，避免误合并
            sample = f"{sample}_{batch}"
        taken.setdefault(sample, batch)
        rows.append(dict(file=rel, sample=sample, edge_key=f"{g.element}_{g.edge}", mode=g.mode,
                         role=role, use="1", time=g.timestamp, npts=str(len(g.energy)),
                         emax=f"{g.energy[-1]:.1f}", note="", batch=batch, ref_file=""))
    meta = pd.concat([old, pd.DataFrame(rows, columns=META_COLS)], ignore_index=True)
    meta = assign_refs(meta)
    for i, r in meta.iterrows():
        if not r.ref_file and "ref_file" not in r.note:
            meta.at[i, "note"] = (r.note + "；" if r.note else "") + "本批次无同边参比：请在 ref_file 填参比文件"
    Path(meta_path).parent.mkdir(parents=True, exist_ok=True)
    meta.to_csv(meta_path, index=False, encoding="utf-8-sig")
    return meta, len(rows)


def load_meta(path=META):
    m = pd.read_csv(path, dtype=str, encoding="utf-8-sig").fillna("")
    m["use"] = m["use"].replace("", "1")
    return assign_refs(m)


def default_edge_config(element, edge, elements_in_sample=None):
    return dict(element=element, edge=edge, e_table=round(edge_energy(element, edge), 2),
                e_table_source="xraydb (Elam)", reference=None,
                elements_in_sample=elements_in_sample or [element],
                norm=dict(pre1=-150, pre2=-30, norm1=100, norm2=-10, nnorm=2, smooth_ev=1.0),
                bkg=dict(rbkg=1.0, kweight=2),
                ft=dict(kmin=3.0, kmax=12.0, dk=1.0, window="hanning", kweight=2))


def init_config(meta, path=CONFIG):
    cfg = json.loads(Path(path).read_text(encoding="utf-8")) if Path(path).exists() else \
        {"edges": {}}
    for ek in sorted(set(meta.edge_key)):
        if ek in cfg["edges"]:
            continue
        el, ed = ek.split("_")
        c = default_edge_config(el, ed)
        refs = meta[(meta.edge_key == ek) & (meta.role == "reference")]
        if len(refs):
            c["reference"] = refs.file.iloc[0]
        cfg["edges"][ek] = c
    Path(path).write_text(json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8")
    return cfg


def load_config(path=CONFIG):
    return json.loads(Path(path).read_text(encoding="utf-8"))


# ------------------------------------------------------------------ calibration
def calibrate_ref_file(ref_file, cfg, edge_key=None):
    """用一个参比文件（相对项目根目录）求 ΔE；E_table 取 config.json 中该边的值。"""
    g = xio.read_bsrf(PROJECT_ROOT / ref_file)
    ek = edge_key or f"{g.element}_{g.edge}"
    c = cfg["edges"].get(ek, {})
    g.element, g.edge = c.get("element", g.element), c.get("edge", g.edge)
    r = xcal.calibrate_reference(g, e_table=c.get("e_table"),
                                 smooth_ev=c.get("norm", {}).get("smooth_ev", 1.0))
    r.update(reference=Path(ref_file).name, reference_file=ref_file, edge_key=ek,
             batch=batch_of(ref_file), table_source=c.get("e_table_source", r["table_source"]))
    return r


def run_calib(cfg, meta, out=RESULTS / "calib.json"):
    """每个参比文件求一个 ΔE，作用于 meta.csv 中 ref_file 指向它的所有谱。"""
    res = {}
    for ref in sorted(set(meta.ref_file) - {""}):
        r = calibrate_ref_file(ref, cfg)
        gaps = {}
        for _, row in meta[meta.ref_file == ref].iterrows():
            h = xcal.time_gap_hours(row.time, r["ref_time"])
            gaps[row.file] = None if h is None else round(h, 2)
        r["time_gap_hours"] = gaps
        res[ref] = r
    xcal.save_calib(res, out)
    return res


def load_calib(path=RESULTS / "calib.json"):
    """{ref_file: 校准记录}；旧格式（按吸收边索引）自动换成按参比文件索引。"""
    p = Path(path)
    d = json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}
    return {v.get("reference_file", k): v for k, v in d.items() if isinstance(v, dict) and "delta_e" in v}


# ------------------------------------------------------------------ processing
def edge_cfg(cfg, edge_key, sample=None):
    """该边的参数；config.json 的 "overrides": {样品名: {"norm": {...}, "bkg": {...}, "ft": {...}}}
    可对个别样品改参数（必须在 "overrides_reason" 中写理由，如干扰边落在边前范围）。"""
    import copy as _copy
    c = _copy.deepcopy(cfg["edges"][edge_key])
    ov = cfg.get("overrides", {}).get(sample or "", {})
    for sec in ("norm", "bkg", "ft"):
        c[sec].update(ov.get(sec, {}))
    return c


def load_scan(row, cfg, calib):
    c = edge_cfg(cfg, row.edge_key, row["sample"])
    mode = row["mode"] if row["mode"] in ("trans", "fluo") else None
    g = xio.read_bsrf(PROJECT_ROOT / row.file, mode=mode)
    g.label = row["sample"] if not row.get("scan_label") else row.scan_label
    g.scan_file = row.file
    g.element, g.edge = c["element"], c["edge"]
    ref = row.get("ref_file", "")
    if not ref:
        raise ValueError(f"{row.file}：meta.csv 未指定参比 ref_file，不能校准（必须与参比一起处理）")
    if ref not in calib:                       # 尚未运行 calib：当场计算（不写文件）
        calib[ref] = calibrate_ref_file(ref, cfg, row.edge_key)
    xcal.apply_shift([g], calib[ref]["delta_e"])
    g.calib_ref = ref
    # config.json "deglitch": {样品名: [[E_lo, E_hi], ...]}（校准后能量；理由写在 "deglitch_reason"）
    dg = cfg.get("deglitch", {}).get(row["sample"])
    if dg:
        from .qc import deglitch
        deglitch(g, dg)
    xnorm.normalize(g, **c["norm"])
    return g


def build_sample(sample, cfg=None, meta=None, calib=None, do_chi=True):
    """读入某样品所有可用扫描 → 校准 → 归一化 → 合并 → χ(k) → FT。返回 (group, merge_report)"""
    cfg = cfg or load_config()
    meta = meta if meta is not None else load_meta()
    calib = calib if calib is not None else load_calib()
    rows = meta[(meta["sample"] == sample) & (meta["use"] != "0")]
    if not len(rows):
        raise KeyError(f"meta.csv 中没有可用的样品 {sample}")
    ek = rows.edge_key.iloc[0]
    c = edge_cfg(cfg, ek, sample)
    scans = []
    for _, r in rows.iterrows():
        g = load_scan(r, cfg, calib)
        g.label = Path(r.file).name
        scans.append(g)
    if len(scans) > 1:
        g, rep = xnorm.merge_scans(scans, label=sample)
    else:
        g, rep = scans[0], [dict(label=scans[0].label, used=True, reason="单条扫描")]
        g.nscans = 1
    g.label = sample
    g.edge_key = ek
    g.role = rows.role.iloc[0]
    g.calib_ref = ";".join(dict.fromkeys(rows.ref_file))
    g.e_shift = float(np.mean([calib[r]["delta_e"] for r in dict.fromkeys(rows.ref_file)]))
    if do_chi:
        xbkg.autobk(g, **c["bkg"])
        xft.forward(g, **c["ft"])
    return g, rep


def process_all(cfg=None, meta=None, edge_keys=None, make_figs=True):
    from . import report as xrep
    cfg = cfg or load_config()
    meta = meta if meta is not None else load_meta()
    calib = load_calib()
    PROC.mkdir(parents=True, exist_ok=True)
    summary, groups = [], {}
    for sample in dict.fromkeys(meta["sample"]):
        rows = meta[meta["sample"] == sample]
        ek = rows.edge_key.iloc[0]
        if edge_keys and ek not in edge_keys:
            continue
        if (rows["use"] == "0").all():
            continue
        try:
            g, rep = build_sample(sample, cfg, meta, calib)
        except Exception as ex:
            summary.append(dict(sample=sample, edge_key=ek, error=str(ex)))
            continue
        groups[sample] = g
        base = PROC / safe(sample)
        xio.write_group_columns(g, base.with_suffix(".nor"),
                                cols=("energy", "mu", "norm", "flat", "dmude"))
        kw = edge_cfg(cfg, ek, sample)["ft"]["kweight"]
        np.savetxt(base.with_suffix(".chik"), np.column_stack([g.k, g.chi, g.chi * g.k ** kw]),
                   header=f"k chi chi*k^{kw}", fmt="%.6g")
        np.savetxt(base.with_suffix(".chir"), np.column_stack([g.r, g.chir_mag, g.chir_re, g.chir_im]),
                   header="R(未相移校正) mag re im", fmt="%.6g")
        ipk = int(np.argmax(g.chir_mag * (g.r > 1.0)))
        summary.append(dict(sample=sample, edge_key=ek, role=g.role, mode=g.mode,
                            nscans=getattr(g, "nscans", 1),
                            scans_used=";".join(r["label"] for r in rep if r.get("used", True)),
                            scans_rejected=";".join(f"{r['label']}({r['reason']})" for r in rep
                                                    if not r.get("used", True)),
                            ref_file=g.calib_ref, dE_cal=g.e_shift, E0=round(g.e0, 2),
                            edge_step=g.edge_step,
                            kmax_data=round(float(g.k[-1]), 2),
                            R_peak_nophase=round(float(g.r[ipk]), 3),
                            chir_peak=round(float(g.chir_mag[ipk]), 3)))
    df = pd.DataFrame(summary)
    df.to_csv(PROC / "process_summary.csv", index=False, encoding="utf-8-sig")
    write_params(PROC / "process.params.json", cfg, "pipeline.process_all")
    if make_figs:
        figs = PROJECT_ROOT / "figs"
        figs.mkdir(exist_ok=True)
        for ek in sorted(set(df.edge_key)) if len(df) else []:
            gl = [groups[s] for s in df[df.edge_key == ek]["sample"] if s in groups]
            for role in ("reference", "standard", "sample"):
                sub = [g for g in gl if g.role == role]
                if not sub:
                    continue
                for i in range(0, len(sub), 8):
                    chunk = sub[i:i + 8]
                    tag = f"{ek}_{role}_{i // 8}"
                    xrep.plot_norm(chunk, out=figs / f"{tag}_norm.png", title=f"{ek} {role}")
                    xrep.plot_k_r(chunk, kweight=cfg["edges"][ek]["ft"]["kweight"],
                                  out=figs / f"{tag}_k_R.png", title=f"{ek} {role}")
    return df, groups
