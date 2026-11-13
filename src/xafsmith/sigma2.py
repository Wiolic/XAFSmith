"""sigma2 —— σ² 的 Debye / Einstein 温度模型（B6）。纯函数，GUI 与 CLI 共用，不碰拟合。

larch 在路径表达式里已内置 sigma2_debye(t, theta) 与 sigma2_eins(t, theta)（求值时 larch 把当前路径存进 feffpath 符号），
这里只给"拿一个 FEFF 路径文件算 σ²(T)"与"由某温度下的 σ² 反算 θ"的直接入口。
Debye 为相关 Debye 模型（FEFF6 sigms 算法，用路径全部原子的坐标与质量）；Einstein 为 σ² = ħ²/(2μk_Bθ)·coth(θ/2T)，
μ 为路径全部原子的约化质量。不含任何文献 θ 值。
"""
from __future__ import annotations

import numpy as np

KINDS = ("debye", "einstein")
THETA_BRACKET = (10.0, 5000.0)        # theta_from_sigma2 的搜索区间（K）


def _kind(kind: str) -> str:
    k = str(kind).strip().lower()
    if k in ("eins", "einstein", "e"):
        return "einstein"
    if k in ("debye", "d"):
        return "debye"
    raise ValueError(f"未知的 σ² 模型 {kind!r}（应为 debye 或 einstein） / unknown σ² model {kind!r} (use debye or einstein)")


def _load(path_file):
    from larch.xafs import feffpath
    return feffpath(str(path_file))


def _fn(kind: str):
    from larch.xafs.sigma2_models import sigma2_debye, sigma2_eins
    return sigma2_debye if kind == "debye" else sigma2_eins


def sigma2_curve(path_file, kind, theta, temps, static=0.0) -> np.ndarray:
    """σ²(T) = 模型(T, θ) + static，单位 Å²。path_file：FEFF 路径文件（feffNNNN.dat）。"""
    kind = _kind(kind)
    fn = _fn(kind)
    path = _load(path_file)
    temps = np.atleast_1d(np.asarray(temps, dtype=float))
    return np.array([float(fn(float(t), float(theta), path)) for t in temps]) + float(static)


def theta_from_sigma2(path_file, kind, T, sigma2, static=0.0):
    """由温度 T 下的 σ² 反算 θ（brentq，θ ∈ [10, 5000] K）。无解（目标低于零点值、高于 10 K 的值等）返回 None。"""
    from scipy.optimize import brentq
    kind = _kind(kind)
    fn = _fn(kind)
    path = _load(path_file)
    target = float(sigma2) - float(static)
    if not np.isfinite(target) or target <= 0 or not float(T) > 0:
        return None

    def f(th):
        return float(fn(float(T), th, path)) - target
    lo, hi = THETA_BRACKET
    flo, fhi = f(lo), f(hi)
    if not (np.isfinite(flo) and np.isfinite(fhi)) or flo * fhi > 0:
        return None
    return float(brentq(f, lo, hi, xtol=1e-12, rtol=1e-14))


# ------------------------------------------------------------------ 模型 JSON 合法性（B6，6.1-4；schema 与 normalize_model 共用）
import ast
import math
from pathlib import Path
import re

FUNCS = ("sigma2_debye", "sigma2_eins")
RESERVED = ("tempK",) + FUNCS
_TEMPK_RE = re.compile(r"\btempK\b")
PATH_FIELDS = ("N", "s02", "e0", "deltar", "sigma2", "third", "fourth", "ei")


def parse_temperature(v, where="temperature"):
    """temperature（K）：None → None；数字且有限且 > 0 → float；否则 ValueError（双语）。"""
    if v is None:
        return None
    if isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v) or v <= 0:
        raise ValueError(f"{where} 应为大于 0 的有限数字（K），实际是 {v!r} / "
                         f"{where} must be a finite number > 0 (kelvin), got {v!r}")
    return float(v)


def _calls(expr):
    """表达式里对 sigma2_debye/eins 的调用节点；解析失败返回 []。"""
    if not isinstance(expr, str) or not any(f in expr for f in FUNCS):
        return []
    try:
        tree = ast.parse(expr, mode="eval")
    except (SyntaxError, ValueError):
        return []
    return [n for n in ast.walk(tree) if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
            and n.func.id in FUNCS]


def _tkey(arg, temp):
    """调用第 1 个参数对应的温度：数字字面量 / tempK（取数据集 temperature）；其他 None（未知）。"""
    if isinstance(arg, ast.Constant) and isinstance(arg.value, (int, float)) and not isinstance(arg.value, bool):
        return float(arg.value)
    if isinstance(arg, ast.Name) and arg.id == "tempK":
        return temp
    return None


def model_issues(m) -> list:
    """模型 JSON（旧格式或多数据集，未规范化）→ [(级别 'error'|'warn', 位置, 中文, English)]。
    只在用到 temperature / tempK / sigma2_debye / sigma2_eins 时才有输出；结构不对的部分跳过（由别处报告）。"""
    out = []
    if not isinstance(m, dict):
        return out

    def add(level, where, zh, en):
        out.append((level, where, zh, en))
    multi = isinstance(m.get("datasets"), list)
    blocks = [(f"datasets[{i}]", d) for i, d in enumerate(m["datasets"]) if isinstance(d, dict)] if multi \
        else [("", m)]
    params = m.get("params") if isinstance(m.get("params"), dict) else {}
    for n in RESERVED:
        if n in params:
            add("error", f"params.{n}", f"参数名 {n} 是保留名", f"parameter name {n} is reserved")
    # 参数表达式与软约束里不得出现 sigma2 模型函数
    for name, spec in params.items():
        ex = spec if isinstance(spec, str) else (spec.get("expr") if isinstance(spec, dict) else None)
        if _calls(ex):
            add("error", f"params.{name}", "σ² 模型函数只能写在路径的 sigma2 字段里（这里的 feffpath 是最后求值的那条路径，值会悄悄算错）",
                "sigma2_debye/sigma2_eins may only be used in a path's sigma2 field (here feffpath is the last evaluated path and the value would be silently wrong)")
    rs = m.get("restraints")
    for i, r in enumerate(rs if isinstance(rs, list) else []):
        if isinstance(r, dict) and _calls(r.get("expr")):
            add("error", f"restraints[{i}].expr", "σ² 模型函数只能写在路径的 sigma2 字段里（这里的 feffpath 是最后求值的那条路径，值会悄悄算错）",
                "sigma2_debye/sigma2_eins may only be used in a path's sigma2 field (here feffpath is the last evaluated path and the value would be silently wrong)")
    theta_T = {}          # θ 参数名 -> {已知温度集合, 有无未知}
    for pre, b in blocks:
        tw = f"{pre}.temperature" if pre else "temperature"
        tv = b["temperature"] if "temperature" in b else m.get("temperature")
        temp = None
        if tv is not None:
            try:
                temp = parse_temperature(tv, tw)
            except ValueError as ex:
                zh, en = str(ex).split(" / ", 1)
                add("error", tw, zh, en)
        for j, ps in enumerate(b.get("paths") or []):
            if not isinstance(ps, dict):
                continue
            pw = f"{pre}.paths[{j}]" if pre else f"paths[{j}]"
            for k in PATH_FIELDS:
                v = ps.get(k)
                if not isinstance(v, str):
                    continue
                if _TEMPK_RE.search(v) and temp is None and tv is None:
                    add("error", f"{pw}.{k}", "用了 tempK，但该数据集没有 temperature", "uses tempK but the dataset has no temperature")
                for c in _calls(v):
                    if k != "sigma2":
                        add("error", f"{pw}.{k}", "σ² 模型函数只能写在路径的 sigma2 字段里（其他字段里 feffpath 指向最后求值的路径，值会悄悄算错）",
                            "sigma2_debye/sigma2_eins may only be used in a path's sigma2 field")
                        continue
                    if len(c.args) != 2 or c.keywords:
                        add("error", f"{pw}.{k}", f"{c.func.id} 需要恰好 2 个位置参数 (温度, θ)",
                            f"{c.func.id} needs exactly 2 positional arguments (temperature, theta)")
                        continue
                    th = c.args[1]
                    if isinstance(th, ast.Name) and th.id in params:
                        e = theta_T.setdefault(th.id, dict(temps=set(), unknown=False, where=f"{pw}.{k}"))
                        key = _tkey(c.args[0], temp)
                        if key is None:
                            e["unknown"] = True
                        else:
                            e["temps"].add(key)
    for name, e in theta_T.items():
        spec = params[name]
        if isinstance(spec, str) or (isinstance(spec, dict) and spec.get("expr")):
            continue                                   # 表达式参数不是变量
        varied = isinstance(spec, (int, float)) or spec.get("vary", True)
        if not varied:
            continue
        mn = spec.get("min") if isinstance(spec, dict) else None
        if not (isinstance(mn, (int, float)) and not isinstance(mn, bool) and mn > 0):
            add("warn", f"params.{name}", f"θ 参数 {name} 是可变参数但没有大于 0 的 min（larch 把 θ 夹到 1e-5 K，σ² 发散）",
                f"theta parameter {name} is varied but has no min > 0 (larch clamps theta to 1e-5 K and sigma2 diverges)")
        if len(e["temps"]) <= 1 and not e["unknown"]:
            add("warn", f"params.{name}", f"单一温度：θ 参数 {name} 只是 σ² 换了参数化，不提供额外信息；若同时放开静态项则二者不可分",
                f"single temperature: theta parameter {name} is just a re-parameterisation of sigma2 and adds no information; "
                "if a static term is also varied the two are inseparable")
    return out


def raise_on_errors(m):
    """normalize_model 用：有任何 error 级问题 → ValueError（双语，列出全部）。"""
    errs = [i for i in model_issues(m) if i[0] == "error"]
    if errs:
        raise ValueError("; ".join(f"{w}: {zh}" for _, w, zh, _en in errs) + " / "
                         + "; ".join(f"{w}: {en}" for _, w, _zh, en in errs))


def sigma2_info(expr):
    """路径 sigma2 表达式 → (模型 'debye'|'einstein'|None, θ 参数名|None)；取第一个 σ² 模型调用。"""
    cs = _calls(expr)
    if not cs:
        return None, None
    c = cs[0]
    kind = "debye" if c.func.id == "sigma2_debye" else "einstein"
    th = c.args[1].id if len(c.args) == 2 and isinstance(c.args[1], ast.Name) else None
    return kind, th


def sigma2_extra(specs, temperature):
    """摘要的路径行要不要加 σ² 模型字段：有 temperature 或有路径用了 σ² 模型。返回 [(model, theta_param)] 或 None。"""
    info = [sigma2_info(sp.get("sigma2") if isinstance(sp, dict) else None) for sp in specs]
    if temperature is None and all(k is None for k, _ in info):
        return None
    return info


def einstein_ms_warning(label, nleg):
    """Einstein 用在 nleg > 2 的路径上的警告文字（中文 / English）。"""
    return (f"路径 {label}（nleg={nleg}）用了 sigma2_eins：Einstein 模型把多重散射路径当成一个约化质量振子，只是近似；多重散射建议用 Debye / "
            f"path {label} (nleg={nleg}) uses sigma2_eins: the Einstein model treats a multiple-scattering path as one reduced-mass oscillator, "
            "which is only an approximation; Debye is recommended for multiple scattering")


def parse_temps(temps=None, trange=None):
    """命令行温度列表：'10,100,300' 或 'lo:hi:step'（含两端）→ list[float]；都没给 → ValueError。"""
    if trange:
        try:
            lo, hi, st = (float(x) for x in str(trange).split(":"))
        except ValueError:
            raise ValueError(f"--trange 应为 起:止:步长，实际是 {trange!r} / --trange must be start:stop:step, got {trange!r}") from None
        if st <= 0 or hi < lo or lo <= 0:
            raise ValueError("--trange 需要 0 < 起 ≤ 止 且步长 > 0 / --trange needs 0 < start <= stop and step > 0")
        n = int(math.floor((hi - lo) / st + 1e-9)) + 1
        return [lo + i * st for i in range(n)]
    if temps:
        try:
            out = [float(x) for x in str(temps).split(",") if x.strip()]
        except ValueError:
            raise ValueError(f"--temps 应为逗号分隔的数字，实际是 {temps!r} / --temps must be comma-separated numbers") from None
        if not out or any(t <= 0 for t in out):
            raise ValueError("温度必须 > 0 K / temperatures must be > 0 K")
        return out
    raise ValueError("需要 --temps 或 --trange / --temps or --trange is required")


def sigma2_T_series(summ, nm, root=None, n_curve=60):
    """拟合结果的 σ²(T) 图数据：每个 θ 参数一组。
    返回 [dict(theta_param, model, theta, theta_err, static, points=[(T, σ², σ²_err)], T=曲线温度, sigma2=曲线 σ²)]；没有 σ² 模型 → []。
    曲线 = 模型(T, θ_拟合) + static，T 从 0（取 1 K）到 1.2×最高温度；static = 各点 (拟合 σ² − 模型(T, θ)) 的均值
    （表达式是“模型 + 静态项”时各点相同）。路径文件取自该组第一条路径（模型 JSON 的 paths[j].file，与摘要路径行按顺序对应；
    对应不上 → 跳过该组）。这是拟合结果，依赖所选的 Debye / Einstein 模型。"""
    import numpy as np
    from . import paths as xp
    rows = summ.get("paths") or []
    if not any(r.get("sigma2_model") for r in rows):
        return []
    files = []
    for d in nm["datasets"]:
        files.append([p.get("file") for p in d["paths"]])
    out = {}
    for i, r in enumerate(rows):
        th = r.get("theta_param")
        if not (r.get("sigma2_model") and th and r.get("temperature")):
            continue
        out.setdefault((th, r["sigma2_model"]), []).append((i, r))
    series = []
    for (th, kind), lst in out.items():
        p = (summ.get("params") or {}).get(th)
        if not p:
            continue
        # 该行对应的路径文件
        ids = [d["id"] for d in nm["datasets"]]
        per_ds = {}
        for r in rows:
            per_ds[r.get("dataset", ids[0])] = per_ds.get(r.get("dataset", ids[0]), 0) + 1
        offs, acc = {}, 0
        for did in ids:
            offs[did] = acc
            acc += per_ds.get(did, 0)
        i0, r0 = lst[0]
        did = r0.get("dataset", ids[0])
        j = i0 - offs[did]
        di = ids.index(did)
        if len(files[di]) != per_ds.get(did, 0) or not (0 <= j < len(files[di])):
            continue
        f = xp.resolve(files[di][j]) if root is None else (Path(root) / files[di][j])
        pts = [(float(r["temperature"]), float(r["sigma2"]), r.get("sigma2_err")) for _, r in lst]
        base = sigma2_curve(f, kind, p["value"], [t for t, _, _ in pts])
        static = float(np.mean([s - b for (_, s, _), b in zip(pts, base)]))
        tmax = max(t for t, _, _ in pts)
        tc = np.linspace(1.0, 1.2 * tmax, n_curve)
        series.append(dict(theta_param=th, model=kind, theta=float(p["value"]), theta_err=p.get("stderr"), static=static,
                           points=pts, T=tc, sigma2=sigma2_curve(f, kind, p["value"], tc, static=static)))
    return series
