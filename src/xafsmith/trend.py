"""C2：联合拟合的序列趋势表（无 Qt）。

每个（数据集, 路径）一行：N、R、σ²、ΔE0 及其 1σ 误差、实测边位置 E0_edge、该字段是否在各数据集之间共享。
数值与误差直接取联合拟合摘要（summarize_multi；larch 的误差已按 √χ²_ν 缩放），这里不重算、不改任何已有结果。

序列变量（横轴）见 seq_values：meta.csv 的 seq 列 → time 列（距最早一个的小时数）→ 数据集顺序；不混用，
有一个数据集缺就整体降一级并说明哪些缺。

N_err 规则（设计 6.2，已确定）：
  N 字段为空 / 数字           → N 固定，N_err 空（图上不画误差棒）
  N 字段是单个参数名           → 该参数的 stderr
  N 字段是其他表达式           → 仅当 N 的参考 S0² 固定时取 amp_err / S0²参考（amp_err = 路径 s02 的 stderr），否则留空
"""
from __future__ import annotations

import re

import numpy as np
import pandas as pd

from . import paths

COLUMNS = ["dataset", "sample", "seq", "seq_source", "path", "N", "N_err", "R", "R_err", "sigma2", "sigma2_err",
           "dE0", "dE0_err", "E0_edge", "shared_N", "shared_R", "shared_sigma2", "shared_dE0"]

# 缺省轴标题（界面可改）
SEQ_LABELS = {"seq": "Sequence", "time": "Measurement time (h)", "order": "Dataset"}

_NAME = re.compile(r"^[A-Za-z_]\w*$")
_TEMPK = re.compile(r"\btempK\b")
# 模型路径字段 → 趋势表 shared_ 列；缺省字符串与 fit_exafs.build_paths 一致
_SHARED = (("N", "N", ""), ("R", "deltar", "0"), ("sigma2", "sigma2", "0.003"), ("dE0", "e0", "e0"))


def load_project_tables():
    """(meta, process_summary)：读当前项目；缺文件给 None。"""
    meta = proc = None
    if paths.META.exists():
        meta = pd.read_csv(paths.META, dtype=str, encoding="utf-8-sig").fillna("")
    f = paths.PROC / "process_summary.csv"
    if f.exists():
        proc = pd.read_csv(f, encoding="utf-8-sig")
    return meta, proc


# ------------------------------------------------------------------ 序列变量
def _sample_seq(rows):
    """一个样品的 seq：非空值必须全部是数字且一致 → (值, None)；否则 (None, 原因)。空值忽略。"""
    vals = [str(v).strip() for v in rows["seq"] if str(v).strip()]
    if not vals:
        return None, "meta.csv 的 seq 为空"
    try:
        nums = [float(v) for v in vals]
    except ValueError:
        return None, f"seq 不是数字（{vals[0]!r}）"
    if not all(np.isfinite(nums)):
        return None, "seq 不是有限数"
    if len(set(nums)) > 1:
        return None, "同一样品多行的 seq 不一致"
    return nums[0], None


def _sample_time(rows):
    """一个样品的测量时间 = 该样品各行 time 中最早的一个（Timestamp）；解析不了 → (None, 原因)。"""
    vals = [str(v).strip() for v in rows["time"] if str(v).strip()]
    if not vals:
        return None, "meta.csv 的 time 为空"
    ts = pd.to_datetime(pd.Series(vals), errors="coerce")
    if ts.isna().any():
        return None, f"time 无法解析（{vals[0]!r}）"
    return ts.min(), None


def seq_values(datasets, meta=None):
    """datasets：[{id, sample}]（normalize_model 的数据集即可）。返回 dict(values, source, notes, labels)：
    values 与 datasets 同序；source ∈ seq / time / order；notes 是降级原因（中文，逐条）；labels = 数据集 id（order 时作刻度）。
    不混用：只要有一个数据集缺 seq 就整体降到 time，再缺就降到 order。"""
    ids = [d["id"] for d in datasets]
    notes = []
    if meta is not None and len(meta):
        for col, source in (("seq", "seq"), ("time", "time")):
            if col not in meta.columns:
                if col == "seq":
                    notes.append("meta.csv 没有 seq 列")
                continue
            got, bad = [], []
            for d in datasets:
                rows = meta[meta["sample"] == d["sample"]]
                v, why = (_sample_seq if col == "seq" else _sample_time)(rows) if len(rows) else (None, "meta.csv 中没有该样品")
                got.append(v)
                if v is None:
                    bad.append(f"{d['id']}（{why}）")
            if not bad:
                if source == "time":
                    t0 = min(got)
                    got = [(t - t0).total_seconds() / 3600.0 for t in got]
                return dict(values=[float(x) for x in got], source=source, notes=notes, labels=ids)
            notes.append(f"{'、'.join(bad)} 缺 {col}，不使用 {col} 作横轴")
    elif meta is None:
        notes.append("没有 meta.csv")
    return dict(values=[float(i + 1) for i in range(len(datasets))], source="order", notes=notes, labels=ids)


# ------------------------------------------------------------------ N_err
def _param_fixed(p):
    return (not p["vary"]) and not p.get("expr")


def _s02_ref_param(spec, params):
    """N 的参考 S0²（与 fit_exafs._s02_ref 同一规则）：路径 s02 字段是参数表里的名字 → 该参数；
    否则全局 S0²（s02 / amp / s0_2 / S02 中第一个存在的）；都没有 → None（= 常数 1.0，固定）。"""
    aname = spec.get("s02", "s02") if isinstance(spec, dict) else "s02"
    if isinstance(aname, str) and aname in params:
        return params[aname]
    for k in ("s02", "amp", "s0_2", "S02"):
        if k in params:
            return params[k]
    return None


def n_err(spec, row, params):
    """(N_err 或 None, 是否复合表达式且没给误差)。spec：模型里的路径字典（可能为空 {}）；row：摘要路径行；params：摘要参数表。"""
    nf = spec.get("N") if isinstance(spec, dict) else None
    if nf is None or (isinstance(nf, str) and not nf.strip()):
        return None, False
    if isinstance(nf, (int, float)) and not isinstance(nf, bool):
        return None, False
    if isinstance(nf, str):
        s = nf.strip()
        try:
            float(s)
            return None, False
        except ValueError:
            pass
        if _NAME.match(s):
            p = params.get(s)
            e = None if p is None else p.get("stderr")
            return (None if e is None else float(e)), False
        ref = _s02_ref_param(spec, params)
        amp_err = row.get("amp_err")
        if (ref is None or _param_fixed(ref)) and amp_err is not None:
            v = 1.0 if ref is None else float(ref["value"])
            return float(amp_err) / max(v, 1e-9), False
        return None, True
    return None, False


# ------------------------------------------------------------------ 共享标记
def _shared_flags(nm):
    """{路径标签: {列: bool}}：模型 JSON 里该路径该字段的字符串在包含它的所有数据集中完全相同（且至少两个数据集）。
    由路径位置与摘要标签对应：标签 = 路径 label，缺省 p<序号>（与 build_paths 同；重复标签加文件号的情形不匹配 → 不共享）。"""
    by = {}
    temps = {d["id"]: d.get("temperature") for d in nm["datasets"]}
    for d in nm["datasets"]:
        for i, ps in enumerate(d["paths"]):
            lab = ps.get("label") or f"p{i + 1}"
            by.setdefault(lab, []).append((d["id"], ps))
    out = {}
    for lab, items in by.items():
        fl = {}
        for col, key, default in _SHARED:
            strs = [str(ps.get(key, default) if ps.get(key) is not None else default) for _, ps in items]
            same = len(items) >= 2 and len(set(strs)) == 1
            if same and _TEMPK.search(strs[0]) and len({temps[i] for i, _ in items}) > 1:
                same = False                       # tempK 在各数据集里代入不同温度 → 字符串相同但数值不同
            fl["shared_" + col] = bool(same)
        out[lab] = fl
    return out


# ------------------------------------------------------------------ 趋势表
def trend_table(summ, model, meta=None, processed=None):
    """联合拟合摘要 → 趋势表（列见 COLUMNS）。summ：summarize_multi 的结果（路径行需有 dataset）；
    model：模型 JSON（dict）。df.attrs：seq_source、seq_notes（降级原因）、n_composite（N 为复合表达式、未给误差的路径）。
    单数据集摘要 → ValueError。"""
    from .fit_exafs import normalize_model
    if not summ.get("multi") or len(summ.get("datasets", [])) < 2:
        raise ValueError("趋势表需要 ≥2 个数据集的联合拟合 / the trend table needs a joint fit of ≥2 datasets")
    nm = normalize_model(model)
    dsets = nm["datasets"]
    sv = seq_values(dsets, meta)
    seq_of = dict(zip([d["id"] for d in dsets], sv["values"]))
    sample_of = {d["id"]: d["sample"] for d in dsets}
    shared = _shared_flags(nm)
    e0e = {}
    if processed is not None and len(processed) and {"sample", "E0"} <= set(processed.columns):
        for s, v in zip(processed["sample"], processed["E0"]):
            if s not in e0e and pd.notna(v):
                e0e[s] = float(v)
    params = summ.get("params", {})
    rows, composite = [], []
    for d in dsets:
        prs = [r for r in summ["paths"] if r.get("dataset") == d["id"]]
        specs = d["paths"] if len(d["paths"]) == len(prs) else [{}] * len(prs)      # 位置对应；不对应时不给规格
        for spec, r in zip(specs, prs):
            ne, comp = n_err(spec, r, params)
            if comp and r["path"] not in composite:
                composite.append(r["path"])
            row = dict(dataset=d["id"], sample=d["sample"], seq=seq_of[d["id"]], seq_source=sv["source"],
                       path=r["path"], N=r["N"], N_err=ne, R=r["R"], R_err=r.get("R_err"), sigma2=r["sigma2"],
                       sigma2_err=r.get("sigma2_err"), dE0=r["e0"], dE0_err=r.get("e0_err"),
                       E0_edge=e0e.get(sample_of[d["id"]]))
            fl = shared.get(r["path"], {})
            for col, _, _ in _SHARED:
                row["shared_" + col] = fl.get("shared_" + col, False)
            rows.append(row)
    df = pd.DataFrame(rows, columns=COLUMNS)
    edge = ""
    if meta is not None and {"sample", "edge_key"} <= set(meta.columns):
        eks = sorted({str(e) for e in meta[meta["sample"].isin([d["sample"] for d in dsets])]["edge_key"] if str(e).strip()})
        edge = ", ".join(e.replace("_", " ") + "-edge" for e in eks)
    df.attrs.update(seq_source=sv["source"], seq_notes=sv["notes"], n_composite=composite,
                    seq_labels=sv["labels"], edge=edge)
    return df


def save_trend(table, base, model_name="", tool="xafsmith trend"):
    """趋势表 → output/fits/<base>_trend.csv（utf-8-sig）与 <base>_trend.params.json；返回 CSV 路径。"""
    from .common import write_params
    csv = paths.FITS / f"{base}_trend.csv"
    csv.parent.mkdir(parents=True, exist_ok=True)
    table.to_csv(csv, index=False, encoding="utf-8-sig")
    write_params(paths.FITS / f"{base}_trend.params.json",
                 dict(model=model_name or base, seq_source=table.attrs.get("seq_source"),
                      seq_notes=table.attrs.get("seq_notes", []), n_composite=table.attrs.get("n_composite", []),
                      columns=list(table.columns), rows=int(len(table)),
                      note="1-sigma errors from the fit (Larch, scaled by sqrt(chi2_reduced)); fit results, "
                           "model-dependent; E0_edge is the measured edge position, not a fit result"), tool)
    return csv
