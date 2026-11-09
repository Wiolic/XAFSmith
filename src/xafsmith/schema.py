"""数据标准：meta.csv、xafsmith.json、拟合模型 JSON 的字段定义与检查（xafsmith validate）。

完整说明见 docs/数据标准.md。
"""
import json
from pathlib import Path

import pandas as pd

from . import paths

# ---------------------------------------------------------------- meta.csv
META_COLS = ["file", "sample", "edge_key", "mode", "role", "use", "time", "npts", "emax", "note",
             "batch", "ref_file"]
META_REQUIRED = ["file", "sample", "edge_key", "mode", "role", "use", "ref_file"]
ROLES = {"reference", "standard", "sample"}
MODES = {"trans", "fluo", ""}

# ---------------------------------------------------------------- xafsmith.json
EDGE_REQUIRED = ["element", "edge", "e_table", "norm", "bkg", "ft"]
NORM_KEYS = ["pre1", "pre2", "norm1", "norm2", "nnorm"]
BKG_KEYS = ["rbkg", "kweight"]
FT_KEYS = ["kmin", "kmax", "dk", "window", "kweight"]
TOP_OPTIONAL = ["overrides", "overrides_reason", "deglitch", "deglitch_reason"]

# ---------------------------------------------------------------- 模型 JSON
MODEL_REQUIRED = ["name", "sample", "kmin", "kmax", "rmin", "rmax", "kweight", "params", "paths"]
PATH_REQUIRED = ["file"]


class Report:
    def __init__(self):
        self.items = []

    def err(self, where, msg):
        self.items.append(("错误", where, msg))

    def warn(self, where, msg):
        self.items.append(("警告", where, msg))

    @property
    def n_err(self):
        return sum(1 for i in self.items if i[0] == "错误")

    def table(self):
        return pd.DataFrame(self.items, columns=["级别", "位置", "说明"])


def check_layout(rep):
    if not paths.CONFIG.exists():
        rep.err(paths.MARKER, "缺少项目标识文件（用 xafsmith new 创建项目，或 xafsmith init 生成）")
    for d in paths.INPUT_DIRS:
        if not d.exists():
            rep.warn(paths.rel(d), "目录不存在（xafsmith init 会创建）")


def check_config(rep, cfg):
    if cfg.get("xafsmith", {}).get("schema") is None:
        rep.warn(paths.MARKER, '缺少 "xafsmith": {"schema": ...}')
    edges = cfg.get("edges", {})
    if not edges:
        rep.warn(paths.MARKER, "edges 为空（xafsmith init 会按 meta.csv 生成）")
    for ek, c in edges.items():
        w = f"{paths.MARKER} edges.{ek}"
        for k in EDGE_REQUIRED:
            if k not in c:
                rep.err(w, f"缺少字段 {k}")
        for sec, keys in (("norm", NORM_KEYS), ("bkg", BKG_KEYS), ("ft", FT_KEYS)):
            for k in keys:
                if k not in c.get(sec, {}):
                    rep.err(w, f"{sec} 缺少 {k}")
        ft = c.get("ft", {})
        if ft.get("kmin", 0) >= ft.get("kmax", 1):
            rep.err(w, "ft.kmin ≥ ft.kmax")
        if "elements_in_sample" not in c:
            rep.warn(w, "缺少 elements_in_sample（干扰边检查需要）")
    for name in cfg.get("overrides", {}):
        if name not in cfg.get("overrides_reason", {}):
            rep.err(f"{paths.MARKER} overrides.{name}", "个别样品改参数必须在 overrides_reason 写理由")
    for name in cfg.get("deglitch", {}):
        if name not in cfg.get("deglitch_reason", {}):
            rep.err(f"{paths.MARKER} deglitch.{name}", "去毛刺必须在 deglitch_reason 写理由")


def check_meta(rep, meta, cfg):
    w = paths.rel(paths.META)
    for c in META_REQUIRED:
        if c not in meta:
            rep.err(w, f"缺少列 {c}")
            return
    refs = set(meta[meta.role == "reference"].file)
    for i, r in meta.iterrows():
        at = f"{w} 第 {i + 2} 行（{r.file}）"
        if not paths.resolve(r.file).exists():
            rep.err(at, "原始文件不存在")
        if r.role not in ROLES:
            rep.err(at, f"role 应为 {sorted(ROLES)}")
        if r["mode"] not in MODES:
            rep.err(at, "mode 应为 trans / fluo")
        if str(r.use) not in ("0", "1", ""):
            rep.err(at, "use 应为 0 或 1")
        if str(r.use) == "0" and not str(r.note).strip():
            rep.err(at, "use=0 必须在 note 写理由")
        if r.edge_key not in cfg.get("edges", {}):
            rep.warn(at, f"{paths.MARKER} 中没有吸收边 {r.edge_key}")
        if not r.ref_file:
            rep.err(at, "没有参比 ref_file：不能校准（数据标准要求每条谱与同批参比一起处理）")
        elif r.ref_file not in refs:
            rep.warn(at, f"ref_file {r.ref_file} 在 meta.csv 中不是 role=reference")
    # 同一样品名 = 同一吸收边、同一模式
    for s, g in meta.groupby("sample"):
        if g.edge_key.nunique() > 1:
            rep.err(f"{w} 样品 {s}", "同名样品跨吸收边（同名多行会被合并）")
        if g["mode"].nunique() > 1:
            rep.warn(f"{w} 样品 {s}", "同名样品混合透射与荧光")


def check_models(rep, meta):
    samples = set(meta["sample"]) if meta is not None else set()
    for f in sorted(paths.MODELS.glob("*.json")):
        if f.name.startswith("_"):          # 模板
            continue
        at = paths.rel(f)
        try:
            m = json.loads(f.read_text(encoding="utf-8"))
        except Exception as ex:
            rep.err(at, f"JSON 解析失败：{ex}")
            continue
        for k in MODEL_REQUIRED:
            if k not in m:
                rep.err(at, f"缺少字段 {k}")
        if samples and m.get("sample") not in samples:
            rep.warn(at, f"样品 {m.get('sample')} 不在 meta.csv 中")
        missing = [p["file"] for p in m.get("paths", []) if not paths.resolve(p["file"]).exists()]
        if missing:
            rep.warn(at, f"{len(missing)} 个 FEFF 路径文件不存在（先运行 xafsmith feff），如 {missing[0]}")


def check_structures(rep):
    from .structures import list_structures, read_structure
    for name in list_structures():
        try:
            read_structure(name)
        except Exception as ex:
            rep.err(f"structures/{name}", f"无法读入：{ex}")


def validate(structures=True):
    from .pipeline import load_meta
    rep = Report()
    check_layout(rep)
    cfg = json.loads(paths.CONFIG.read_text(encoding="utf-8")) if paths.CONFIG.exists() else {}
    if cfg:
        check_config(rep, cfg)
    meta = None
    if paths.META.exists():
        meta = load_meta()
        check_meta(rep, meta, cfg)
    else:
        rep.warn(paths.rel(paths.META), "尚无 meta.csv（把原始数据放进 data/raw/<批次>/ 后运行 xafsmith init）")
    if paths.MODELS.exists():
        check_models(rep, meta)
    if structures:
        check_structures(rep)
    return rep
