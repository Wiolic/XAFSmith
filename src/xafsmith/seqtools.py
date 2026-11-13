"""C2：联合拟合序列工具（无 Qt）——“σ² 各数据集独立”与“路径勾选同步”的核心逻辑，界面（拟合页）只负责取表、写回。

σ² 独立（设计 6.6，命名与初值规则已确定）：
  * 对每个数据集已勾选路径的 sigma2 字段，把在 ≥2 个数据集中出现的 σ² 参数名（整词替换，表达式里也换，如 ss1*1.5 → ss1_IrTa_100*1.5）
    改成 <名>_<id>；id 中非 [A-Za-z0-9_] 的字符换成 _；撞名加 _2、_3…
  * 新参数行复制原参数的 value / vary / min / max / expr；原参数不再被用到时由拟合页按名字重建参数表时消失
  * 已带后缀（名字以 _<id> 结尾）的不再加；只改 σ²，N / ΔR 不提供
"""
from __future__ import annotations

import re

import pandas as pd

# 不是参数名的标识符（与 qt.state.FUNCS 一致）
NOT_PARAM = {"sqrt", "exp", "log", "abs", "min", "max", "pi", "sin", "cos", "tan", "reff", "degen", "e", "log10",
             "sigma2_debye", "sigma2_eins", "tempK"}
_TOKEN = re.compile(r"(?<![\w.])([A-Za-z_]\w*)(?!\w)")
PATH_COLS = ("N", "s02", "e0", "deltar", "sigma2", "third", "fourth", "ei")
PARAM_COLS = ["name", "value", "vary", "min", "max", "expr"]


def safe_id(ds_id) -> str:
    """数据集 id → 可放进参数名的后缀（非 [A-Za-z0-9_] 换成 _）。"""
    return re.sub(r"[^A-Za-z0-9_]", "_", str(ds_id))


def param_names(expr) -> list[str]:
    """表达式里的参数名（按出现顺序、去重）：不含函数名、保留符号、数字（含 1e-3 这类写法）。"""
    if expr is None or (isinstance(expr, float) and pd.isna(expr)):
        return []
    out = []
    for m in _TOKEN.finditer(str(expr)):
        n = m.group(1)
        if n in NOT_PARAM or str(expr)[m.end():].lstrip().startswith("("):
            continue
        if n not in out:
            out.append(n)
    return out


def _replace_word(expr, old, new):
    return re.sub(rf"(?<![\w.]){re.escape(old)}(?!\w)", new, str(expr))


def _used(df):
    return df[df["use"].astype(bool)] if "use" in df else df


def sigma2_independent(tables: dict, params: pd.DataFrame):
    """tables：{数据集 id: 路径表 DataFrame（列 use、sigma2 …）}；params：当前参数表（列 name value vary min max expr，可为空）。
    返回 (新路径表 dict, 新参数表 DataFrame, 改动列表 [(数据集 id, 旧名, 新名)])。输入不被修改。
    没有在 ≥2 个数据集中出现的 σ² 参数时，原样返回（改动列表为空）。"""
    ids = list(tables)
    per = {i: [n for r in _used(tables[i]).itertuples() for n in param_names(getattr(r, "sigma2", ""))] for i in ids}
    count = {}
    for i in ids:
        for n in dict.fromkeys(per[i]):
            count[n] = count.get(n, 0) + 1
    # 被别的参数的 expr 引用的名字不改（如 ss2 = ss1*1.2：改掉 ss1 后它从参数表消失，ss2 的表达式就找不到它）
    in_expr = {n for e in (params["expr"] if len(params) and "expr" in params else []) for n in param_names(e)}
    shared = [n for n in dict.fromkeys(n for i in ids for n in per[i]) if count[n] >= 2 and n not in in_expr]
    taken = set(params["name"]) if len(params) else set()
    for i in ids:
        for col in PATH_COLS:
            if col in tables[i]:
                for v in tables[i][col]:
                    taken.update(param_names(v))
    new_tables = {i: tables[i].copy() for i in ids}
    new_rows, changes = [], []
    for i in ids:
        sid = safe_id(i)
        mapping = {}
        for n in shared:
            if n not in per[i] or n.endswith("_" + sid):
                continue                                  # 本数据集没用它 / 已带本数据集的后缀（幂等）
            new, k = f"{n}_{sid}", 2
            while new in taken:
                new, k = f"{n}_{sid}_{k}", k + 1
            taken.add(new)
            mapping[n] = new
        if not mapping:
            continue
        df = new_tables[i]
        for idx in _used(df).index:
            s = df.at[idx, "sigma2"]
            for old, new in mapping.items():
                s = _replace_word(s, old, new)
            df.at[idx, "sigma2"] = s
        for old, new in mapping.items():
            changes.append((i, old, new))
            src = params[params["name"] == old] if len(params) else params
            if len(src):
                row = src.iloc[0].to_dict()
                row["name"] = new
                new_rows.append(row)
    newp = params.copy()
    if new_rows:
        newp = pd.concat([params, pd.DataFrame(new_rows, columns=PARAM_COLS)], ignore_index=True)
    return new_tables, newp, changes


def sync_targets(tables: dict, src_id, key, value: bool) -> list:
    """路径勾选同步：在 src_id 之外的数据集里，(dir, file) == key 且 use 与 value 不同的行 → [(数据集 id, 行号)]。
    只看 use（不动表达式）；没有这一行的数据集跳过。不修改 tables。"""
    hit = []
    for i, df in tables.items():
        if i == src_id or "dir" not in df or "file" not in df:
            continue
        for r in df.index[(df["dir"] == key[0]) & (df["file"] == key[1])]:
            if bool(df.at[r, "use"]) != bool(value):
                hit.append((i, int(r)))
    return hit


def sync_use(tables: dict, src_id, key, value: bool) -> list:
    """sync_targets 的结果直接写进 tables 里的 DataFrame（无界面场合 / 测试用）；返回同样的列表。"""
    hit = sync_targets(tables, src_id, key, value)
    for i, r in hit:
        tables[i].at[r, "use"] = bool(value)
    return hit
