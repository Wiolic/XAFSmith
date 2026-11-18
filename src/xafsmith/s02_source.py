"""S0² 的标样来源（F1·G2，纯计算，不依赖 Qt）：列出“可供样品载入 S0² 的标样拟合”。

候选 = 本会话拟合记录（S.fits）+ 已保存的拟合（output/fits/exafs_fits.csv）。只收同时满足的：
  1. 吸收边相同：拟合涉及的每个样品，在 data/meta.csv 里的 edge_key 都等于目标边（查不到的样品 → 不收，不猜）；
  2. S0² 是拟合量：会话记录用 summ["params"]["s02"] 的 vary 且无 expr；已保存的用 csv 的 params 列
     （{参数名: [值, 误差]}，误差不为空 ⇔ 该参数当时是变量），并与 models/<名>.json 里 s02 的写法互相核对
     （json 说 s02 是固定值 / 表达式 → 不收）。没有误差的 S0² 不收（载入后无法写 s02_source.stderr）。
已保存结果为什么用 exafs_fits.csv：output/fits/ 里只有它同时带模型名、样品、s02 值与误差、R 因子；
*.params.json 是运行参数（无结果），*.fit_report.txt 无样品 / 吸收边。csv 没有时间列，时间取 models/<名>.json
（保存拟合时写入）的修改时间。
"""
from __future__ import annotations

import json
import math
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path


@dataclass
class S02Candidate:
    model: str
    samples: tuple
    value: float
    stderr: float
    rfactor: float | None
    time: str                    # "YYYY-MM-DD HH:MM:SS"，未知为 ""
    origin: str                  # "session" | "saved"

    def source(self) -> dict:
        """写进 ShellModel.s02.source / 模型 s02_source 的内容。"""
        return {"model": self.model, "value": self.value, "stderr": self.stderr}

    @property
    def sample_text(self) -> str:
        return " + ".join(self.samples)


def _safe(name) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", str(name)).strip("_")


def _good(x) -> bool:
    try:
        return x is not None and math.isfinite(float(x))
    except (TypeError, ValueError):
        return False


def sample_edges(meta) -> dict:
    """meta（DataFrame，需 sample / edge_key 列）→ {样品: {edge_key…}}。"""
    out: dict = {}
    for s, e in zip(meta["sample"], meta["edge_key"]):
        if str(s) and str(e):
            out.setdefault(str(s), set()).add(str(e))
    return out


def _on_edge(samples, edge_key, edges) -> bool:
    return bool(samples) and all(edges.get(s) == {edge_key} for s in samples)


def _from_session(fits, edge_key, edges) -> list:
    out = []
    for f in fits or []:
        try:
            summ = f["summ"]
            p = (summ.get("params") or {}).get("s02")
            if not p or not p.get("vary") or p.get("expr") or not _good(p.get("value")) or not _good(p.get("stderr")):
                continue
            samples = tuple(dict.fromkeys(d["sample"] for d in summ["datasets"])) if summ.get("multi") \
                else (summ["sample"],)
            if not _on_edge(samples, edge_key, edges):
                continue
            rf = summ.get("rfactor")
            out.append(S02Candidate(str(summ["model"]), samples, float(p["value"]), float(p["stderr"]),
                                    float(rf) if _good(rf) else None, str(f.get("time", ""))[:19].replace("T", " "),
                                    "session"))
        except (KeyError, TypeError):
            continue
    return out


def _model_says_not_fitted(models_dir: Path, name) -> bool:
    """models/<名>.json 里 s02 明确是固定值或表达式 → True（文件读不到 / 没写清 → False）。"""
    f = models_dir / f"{_safe(name)}.json"
    try:
        spec = json.loads(f.read_text(encoding="utf-8-sig")).get("params", {}).get("s02")
    except (OSError, ValueError):
        return False
    return isinstance(spec, dict) and (bool(spec.get("expr")) or spec.get("vary") is False)


def _saved_time(models_dir: Path, name) -> str:
    f = models_dir / f"{_safe(name)}.json"
    try:
        return datetime.fromtimestamp(f.stat().st_mtime).strftime("%Y-%m-%d %H:%M:%S")
    except OSError:
        return ""


def _from_saved(fits_csv: Path, models_dir: Path, edge_key, edges) -> list:
    import pandas as pd
    if not fits_csv.exists():
        return []
    df = pd.read_csv(fits_csv, encoding="utf-8-sig", dtype=str, keep_default_na=False)
    if not {"sample", "model", "params"} <= set(df.columns):
        return []
    latest: dict = {}                         # (模型, 样品集) → 最后一次保存（同一模型重存多次只取最后）
    for _, r in df.iterrows():
        latest.setdefault(r["model"], []).append(r)
    out = []
    for model, rows in latest.items():
        last = rows[-1]["params"]
        grp = [r for r in rows if r["params"] == last]          # 最后一次保存的各路径行（多数据集：各数据集的行）
        samples = tuple(dict.fromkeys(r["sample"] for r in grp))
        if not _on_edge(samples, edge_key, edges):
            continue
        try:
            val, err = json.loads(last)["s02"][:2]
        except (ValueError, KeyError, TypeError):
            continue
        if not _good(val) or not _good(err) or _model_says_not_fitted(models_dir, model):
            continue
        try:
            rf = float(grp[0]["rfactor"])
        except (ValueError, KeyError):
            rf = None
        out.append(S02Candidate(model, samples, float(val), float(err), rf, _saved_time(models_dir, model), "saved"))
    return out


def list_candidates(edge_key, session_fits=(), root=None) -> list:
    """同吸收边、S0² 为拟合量的标样拟合，新的在前。root：项目根目录（缺省用当前项目）。
    会话记录与已保存记录重复（同模型名、同样品、同值）时只留会话的。"""
    import pandas as pd
    from . import paths
    root = Path(root) if root else paths.ROOT
    meta_f = root / "data" / "meta.csv"
    if not meta_f.exists() or not edge_key:
        return []
    edges = sample_edges(pd.read_csv(meta_f, dtype=str, encoding="utf-8-sig").fillna(""))
    out = _from_session(session_fits, edge_key, edges)
    seen = {(c.model, c.samples, round(c.value, 9)) for c in out}
    for c in _from_saved(root / "output" / "fits" / "exafs_fits.csv", root / "models", edge_key, edges):
        if (c.model, c.samples, round(c.value, 9)) not in seen:
            out.append(c)
    out.sort(key=lambda c: c.time, reverse=True)
    return out


def edge_of_samples(samples, root=None):
    """一批样品共同的 edge_key；查不到或不一致返回 None（页面用它决定拟合页当前的吸收边）。"""
    import pandas as pd
    from . import paths
    root = Path(root) if root else paths.ROOT
    f = root / "data" / "meta.csv"
    if not f.exists():
        return None
    edges = sample_edges(pd.read_csv(f, dtype=str, encoding="utf-8-sig").fillna(""))
    es = [edges.get(s) for s in samples]
    if not es or any(not e or len(e) != 1 for e in es):
        return None
    ks = {next(iter(e)) for e in es}
    return ks.pop() if len(ks) == 1 else None
