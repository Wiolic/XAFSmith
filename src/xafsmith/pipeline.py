"""pipeline —— 配置驱动的批处理：meta.csv + config.json → 校准 → 归一化 → 合并 → χ(k) → FT。

文件约定（相对项目根目录）：
  （目录标准见 paths.py）
  data/raw/                原始数据（只读）
  data/meta.csv            每个文件一行：file, sample, edge_key, mode, role, use, time, ..., batch, ref_file
                             role ∈ reference（校准用参比箔）| standard（标样）| sample
                             同一 sample 名的多行 = 多次扫描，处理时合并
                             use = 0 表示不用（须在 note 写理由）
                             batch = data/raw 下第一级文件夹（一次测量批次）
                             ref_file = 校准本条谱所用的参比（默认：同批次、同吸收边的 role=reference 文件）
                             —— 没有 ref_file 的谱不能处理（必须与参比一起校准）
  xafsmith.json            每个吸收边（edge_key，如 Ir_L3）的统一处理参数
  output/processed/        处理结果（.nor / .chik / .chir）与 process_summary.csv
  output/calib/calib.json  校准记录，按参比文件索引：{ref_file: {delta_e, e0_meas, e_table, ...}}

所有函数都从原始数据重新生成结果。
"""
import json
import re
from collections.abc import Callable
from pathlib import Path

import numpy as np
import pandas as pd

from .common import edge_energy, write_params
from . import paths, logs
from . import io as xio
from . import normalize as xnorm
from . import autobk as xbkg
from . import ft as xft
from . import calib as xcal



def __getattr__(name):            # pipeline.META / CONFIG / PROC 始终指向当前项目
    if name in ("META", "CONFIG", "PROC"):
        return getattr(paths, name)
    raise AttributeError(name)
META_COLS = ["file", "sample", "edge_key", "mode", "role", "use", "time", "npts", "emax", "note",
             "batch", "ref_file", "format", "group"]
_DATA_SUFFIX = {".xdi", ".xmu", ".dat", ".txt", ".csv", ".chi", ".prj"}


def safe(name: str) -> str:
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
def scan_raw(raw_dir=None, meta_path=None):
    """扫描 data/raw，生成/更新 meta.csv（已存在的行保留用户的修改）。"""
    meta_path = meta_path or paths.META
    raw_dir = Path(raw_dir or paths.RAW)
    old = pd.read_csv(meta_path, dtype=str).fillna("") if Path(meta_path).exists() else \
        pd.DataFrame(columns=META_COLS)
    for c in META_COLS:
        if c not in old:
            old[c] = ""
    old["batch"] = [b or batch_of(f) for b, f in zip(old.batch, old.file)]
    known = set(zip(old.file, old.group))
    taken = dict(zip(old["sample"], old.batch))      # 样品名 → 批次
    rows, skipped = [], []
    for p in sorted(raw_dir.rglob("*")):
        if not p.is_file():
            continue
        rel = p.relative_to(paths.ROOT).as_posix()
        if (rel, "") in known or any(k[0] == rel for k in known):
            continue
        try:
            fmt, _score = xio.detect_format(p)
        except xio.ReadError as ex:
            logs.log.warning("读取失败 %s: %s", rel, ex, exc_info=True)
            skipped.append((rel, str(ex)))
            continue
        if fmt is None:                              # 不是已知的数据格式（说明文件、图片等），不登记
            if _score >= 10:                         # 像数值表格（通用列文本）但不自动登记：列含义需人工确认
                skipped.append((rel, "像列文本但未自动识别：请用“载入谱 → 列映射向导”保存模板，再在 meta.csv 手工登记"
                                     "（format 列填模板名） / looks like column text: save a template with the column wizard"))
            continue
        try:
            gs = xio.read_file(p, fmt=fmt)
        except Exception as ex:                      # noqa: BLE001
            logs.log.warning("pipeline.scan_raw 出错（已忽略或已提示）", exc_info=True)
            skipped.append((rel, str(ex)))
            continue
        for g in gs:
            if not g.element or not g.edge:
                skipped.append((rel, "无法确定元素与吸收边：请在 meta.csv 手工登记 / cannot determine element and edge"))
                continue
            name = getattr(g, "group_name", None) or (Path(p.name).stem if p.suffix.lower() in _DATA_SUFFIX else p.name)
            role = "reference" if re.search(r"foil|powder|metal", name, re.I) else (
                "sample" if re.search(r"insitu|_\d|ocp|v$|V$", rel, re.I) else "standard")
            sample = re.sub(r"_(\d)$", "", name)          # 去掉 _2/_3 等重复扫描后缀
            if sample not in taken and f"{sample}{p.suffix}" in taken:   # 旧版本按带扩展名的文件名命名过同一样品
                sample = f"{sample}{p.suffix}"
            batch = batch_of(rel)
            if taken.get(sample, batch) != batch:         # 与其他批次重名 → 加批次名，避免误合并
                sample = f"{sample}_{batch}"
            taken.setdefault(sample, batch)
            notes = [w.split(" / ")[0] for w in g.read_warnings]
            if g.meta_guessed:
                notes.append("以下字段为猜测，请核对：" + "、".join(g.meta_guessed))
            rows.append(dict(file=rel, sample=sample, edge_key=f"{g.element}_{g.edge}", mode=g.mode or "",
                             role=role, use="1", time=g.timestamp, npts=str(len(g.energy)),
                             emax=f"{g.energy[-1]:.1f}", note="；".join(notes), batch=batch, ref_file="",
                             format=fmt, group=getattr(g, "group_name", "") if len(gs) > 1 else ""))
    scan_raw.skipped = skipped                       # 读不了的文件（文件名, 原因），由命令行/界面显示
    meta = pd.concat([old, pd.DataFrame(rows, columns=META_COLS)], ignore_index=True)
    meta = assign_refs(meta)
    for i, r in meta.iterrows():
        if not r.ref_file and "ref_file" not in r.note:
            meta.at[i, "note"] = (r.note + "；" if r.note else "") + "本批次无同边参比：请在 ref_file 填参比文件"
    Path(meta_path).parent.mkdir(parents=True, exist_ok=True)
    meta.to_csv(meta_path, index=False, encoding="utf-8-sig")
    return meta, len(rows)


def load_meta(path: str | Path | None = None) -> pd.DataFrame:
    path = path or paths.META
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


def init_config(meta, path=None):
    path = path or paths.CONFIG
    cfg = json.loads(Path(path).read_text(encoding="utf-8-sig")) if Path(path).exists() else \
        {"xafsmith": {"schema": paths.SCHEMA_VERSION}, "edges": {}}
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


def load_config(path: str | Path | None = None) -> dict:
    path = path or paths.CONFIG
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


# ------------------------------------------------------------------ calibration
def meta_row(rel):
    """meta.csv 中某个文件的登记行（找不到返回空字典）；用来取该文件的 format / group / mode。"""
    try:
        m = pd.read_csv(paths.META, dtype=str, encoding="utf-8-sig").fillna("")
        hit = m[m.file == rel]
        return hit.iloc[0].to_dict() if len(hit) else {}
    except Exception:                                # noqa: BLE001
        logs.log.warning("pipeline.meta_row 出错（已忽略或已提示）", exc_info=True)
        return {}


def read_meta_row(row, cfg=None, mode=None):
    """按 meta.csv 的一行（或 meta_row 的结果）读入一条谱；format / group 列缺省 = 自动识别。"""
    row = dict(row)
    m = mode if mode in ("trans", "fluo") else (row.get("mode") if row.get("mode") in ("trans", "fluo") else None)
    return xio.read_scan(paths.ROOT / row["file"], fmt=row.get("format") or None, mode=m,
                         group=row.get("group") or None, templates=(cfg or {}).get("formats"))


def ref_row(ref_file):
    """参比文件在 meta.csv 中的登记行：多组文件（.prj）取 role=reference 的那一组。
    同一文件有多个参比组时无法区分（ref_file 只记文件名）→ 报错，而不是悄悄取第一组。"""
    try:
        m = pd.read_csv(paths.META, dtype=str, encoding="utf-8-sig").fillna("")
    except (OSError, ValueError):
        return {"file": ref_file}
    hit = m[m.file == ref_file]
    if len(hit) <= 1:
        return hit.iloc[0].to_dict() if len(hit) else {"file": ref_file}
    refs = hit[hit.role == "reference"]
    if len(refs) == 1:
        return refs.iloc[0].to_dict()
    raise ValueError(f"{ref_file} 含 {len(hit)} 组谱，其中 role=reference 的有 {len(refs)} 组：无法确定用哪一组校准。"
                     "请在 meta.csv 中只把一组设为 reference")


def calibrate_ref_file(ref_file, cfg, edge_key=None):
    """用一个参比文件（相对项目根目录）求 ΔE；E_table 取 config.json 中该边的值。"""
    g = read_meta_row(ref_row(ref_file), cfg)
    ek = edge_key or f"{g.element}_{g.edge}"
    c = cfg["edges"].get(ek, {})
    g.element, g.edge = c.get("element", g.element), c.get("edge", g.edge)
    r = xcal.calibrate_reference(g, e_table=c.get("e_table"),
                                 smooth_ev=c.get("norm", {}).get("smooth_ev", 1.0))
    r.update(reference=Path(ref_file).name, reference_file=ref_file, edge_key=ek,
             batch=batch_of(ref_file), table_source=c.get("e_table_source", r["table_source"]))
    return r


def run_calib(cfg: dict, meta: pd.DataFrame, out: str | Path | None = None,
              progress: Callable[[float, str], None] | None = None) -> dict:
    """每个参比文件求一个 ΔE，作用于 meta.csv 中 ref_file 指向它的所有谱。
    progress(f, 名称)：可选，每个参比开始前调用（同时是取消点）。"""
    out = out or paths.CALIB_JSON
    res = {}
    refs = sorted(set(meta.ref_file) - {""})
    for i, ref in enumerate(refs):
        if progress:
            progress(i / len(refs), ref)
        r = calibrate_ref_file(ref, cfg)
        gaps = {}
        for _, row in meta[meta.ref_file == ref].iterrows():
            h = xcal.time_gap_hours(row.time, r["ref_time"])
            gaps[row.file] = None if h is None else round(h, 2)
        r["time_gap_hours"] = gaps
        res[ref] = r
    xcal.save_calib(res, out)
    return res


def load_calib(path: str | Path | None = None) -> dict:
    """{ref_file: 校准记录}；旧格式（按吸收边索引）自动换成按参比文件索引。"""
    path = path or paths.CALIB_JSON
    p = Path(path)
    d = json.loads(p.read_text(encoding="utf-8-sig")) if p.exists() else {}
    return {v.get("reference_file", k): v for k, v in d.items() if isinstance(v, dict) and "delta_e" in v}


# ------------------------------------------------------------------ processing
def edge_cfg(cfg: dict, edge_key: str, sample: str | None = None) -> dict:
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
    g = read_meta_row(row.to_dict() if hasattr(row, "to_dict") else row, cfg, mode=mode)
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


def build_sample(sample: str, cfg: dict | None = None, meta: pd.DataFrame | None = None,
                 calib: dict | None = None, do_chi: bool = True) -> tuple:
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


def process_all(cfg: dict | None = None, meta: pd.DataFrame | None = None, edge_keys: list[str] | None = None,
                make_figs: bool = True, progress: Callable[[float, str], None] | None = None) -> tuple[pd.DataFrame, dict]:
    """处理全部样品。progress(f, 名称)：可选，每个样品开始前调用（同时是取消点）；取消时已写出的样品文件保留。"""
    from . import report as xrep
    cfg = cfg or load_config()
    meta = meta if meta is not None else load_meta()
    calib = load_calib()
    paths.PROC.mkdir(parents=True, exist_ok=True)
    summary, groups = [], {}
    samples = list(dict.fromkeys(meta["sample"]))
    for i, sample in enumerate(samples):
        rows = meta[meta["sample"] == sample]
        ek = rows.edge_key.iloc[0]
        if edge_keys and ek not in edge_keys:
            continue
        if (rows["use"] == "0").all():
            continue
        if progress:
            progress(0.9 * i / len(samples), sample)
        try:
            g, rep = build_sample(sample, cfg, meta, calib)
        except Exception as ex:
            logs.log.exception("处理样品失败: %s", sample)
            summary.append(dict(sample=sample, edge_key=ek, error=str(ex)))
            continue
        groups[sample] = g
        base = paths.PROC / safe(sample)
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
    df.to_csv(paths.PROC / "process_summary.csv", index=False, encoding="utf-8-sig")
    write_params(paths.PROC / "process.params.json", cfg, "pipeline.process_all")
    if make_figs:
        if progress:
            progress(0.9, "作图 / figures")
        figs = paths.FIGS
        figs.mkdir(parents=True, exist_ok=True)
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


def run_qc(edge_key: str | None = None, cfg: dict | None = None, meta: pd.DataFrame | None = None,
           progress: Callable[[float, str], None] | None = None) -> pd.DataFrame:
    """逐条扫描质量检查 → output/qc/qc_report.csv；返回 DataFrame。progress(f, 文件名)：可选，每条谱开始前调用（同时是取消点）"""
    from . import qc
    cfg = cfg or load_config()
    meta = meta if meta is not None else load_meta()
    calib = load_calib()
    rows = []
    for i, (_, r) in enumerate(meta.iterrows()):
        if edge_key and r.edge_key != edge_key:
            continue
        if progress:
            progress(i / len(meta), r.file)
        try:
            g = load_scan(r, cfg, calib)
            g.label = r.file
            row = qc.check(g)
        except Exception as ex:
            logs.log.exception("QC 失败: %s", r.file)
            row = dict(label=r.file, error=str(ex))
        row["sample"] = r["sample"]
        rows.append(row)
    df = pd.DataFrame(rows)
    paths.QC.mkdir(parents=True, exist_ok=True)
    df.to_csv(paths.QC_CSV, index=False, encoding="utf-8-sig")
    return df
