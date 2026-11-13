"""msbind —— 多重散射路径的 ΔR / σ² 绑定建议（B5）。纯计算，不依赖 Qt，不改任何输入。

规则（设计固定，容差属甲档，执行档不得改）：
  半路径长 Reff = ½ Σ 各腿长；ΔR、σ² 都是半路径长的平移与方差。
  ΔR 按腿逐条（一阶线性）：
    1. 腿含吸收原子 A（A–X）：δL = X 匹配的单散射行的 deltar；
    2. 腿 Xi–Xj 不含 A，且与 A 共线（A 处夹角 < COLLINEAR_DEG 或 > 180 − COLLINEAR_DEG）：
       同侧 δL = d_far − d_near，两侧 δL = d_i + d_j（精确）；
    3. 否则，腿的元素对 = {A 的元素, 某单散射元素} 且腿长与该单散射 reff 相差 ≤ BOND_TOL：δL = 该行的 deltar（等价键）；
    4. 否则按“键角不变”线性化：δL = [(r_i − r_j cosθ) d_i + (r_j − r_i cosθ) d_j] / L_ij。
  σ²：把 ΔReff 写成 Σ c_b Δr_b（b 为互相独立的键），σ²_path = Σ c_b² σ²_b（独立键近似，忽略键间相关）。
  单散射 σ² 是温度模型调用（sigma2_debye / sigma2_eins）时不做线性组合：所涉各行必须是同一表达式（同一调用、同一 θ），
  多重散射路径沿用它（B6 已按本路径几何展开）；否则不给 σ² 建议。
原子 X 对应的单散射行：已勾选、nleg = 2、同一 FEFF 目录、散射元素相同、|reff − r_X| ≤ SS_TOL（取最近）。
系数为 0 的原子（如共线路径的近端原子，贡献相互抵消）不需要单散射行。
"""
from __future__ import annotations

import ast
import math
import random
import re
from pathlib import Path

SS_TOL = 0.05            # 单散射行匹配 |reff − r_X| 容差（Å）
BOND_TOL = 0.05          # 规则 3 等价键：腿长与单散射 reff 的容差（Å）
COLLINEAR_DEG = 5.0      # 规则 2 共线判据：A 处夹角 < 5° 或 > 175°
_ZERO = 1e-9             # 抵消后的系数视为 0
_DROP = 1e-4             # 写表达式时略去的系数

_geom_cache: dict = {}


def path_atoms(file, root=None) -> list:
    """FEFF 路径文件 → [(元素, (x, y, z))]；第 0 个是吸收原子 A（原点），其后是散射原子。"""
    from .paths import ROOT
    root = ROOT if root is None else root
    f = Path(file)
    if root and not f.is_absolute():
        f = Path(root) / f
    key = str(f)
    if key not in _geom_cache:
        from larch.xafs import feffpath
        p = feffpath(str(f))
        _geom_cache[key] = [(str(g[0]), (float(g[4]), float(g[5]), float(g[6]))) for g in p.geom]
    return _geom_cache[key]


def _sub(a, b):
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def _norm(v):
    return math.sqrt(v[0] ** 2 + v[1] ** 2 + v[2] ** 2)


def _dot(a, b):
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def _key(pos):
    return tuple(round(x, 3) for x in pos)


# ---------------------------------------------------------------- 表达式
_IDENT = re.compile(r"^[A-Za-z_]\w*$")
_NUM = re.compile(r"^\d+(\.\d+)?([eE][-+]?\d+)?$")


def _simple(expr: str) -> bool:
    return bool(_IDENT.match(expr) or _NUM.match(expr))


def _combine(terms: list) -> str:
    """[(系数, 表达式)] → 'c1*(e1) + c2*e2 …'。系数 :.4g，|c| < 1e-4 略去，c = 1 不写，表达式是单个名字/数字时不加括号。"""
    terms = [(c, e.strip()) for c, e in terms if abs(c) >= _DROP]
    if not terms:
        return "0"
    out = ""
    for i, (c, e) in enumerate(terms):
        mag = abs(c)
        one = float(f"{mag:.4g}") == 1.0
        if one and len(terms) == 1 and c > 0:
            s = e                                         # 单项、系数 1：原样（如 2*dr1）
        else:
            body = e if _simple(e) else f"({e})"
            s = body if one else f"{mag:.4g}*{body}"
        if i == 0:
            out = s if c > 0 else f"-{s}"
        else:
            out += (" + " if c > 0 else " - ") + s
    return out


def _norm_expr(s) -> str:
    return re.sub(r"\s+", "", str(s or ""))


def equivalent(a, b) -> bool:
    """两个表达式在随机取值下数值相同（只允许名字、数字、四则与括号、函数调用）→ True；无法判断 → 比较去空白后的文本。"""
    if _norm_expr(a) == _norm_expr(b):
        return True
    try:
        ta, tb = ast.parse(str(a), mode="eval"), ast.parse(str(b), mode="eval")
        names = sorted({n.id for t in (ta, tb) for n in ast.walk(t) if isinstance(n, ast.Name)})
        for t in (ta, tb):
            for n in ast.walk(t):
                if isinstance(n, ast.Call):
                    return False                              # 含函数调用（σ² 温度模型等）不数值比较
        rng = random.Random(12345)
        for _ in range(3):
            env = {n: rng.uniform(0.5, 2.0) for n in names}
            va = eval(compile(ta, "<a>", "eval"), {"__builtins__": {}}, env)
            vb = eval(compile(tb, "<b>", "eval"), {"__builtins__": {}}, env)
            if abs(va - vb) > 1e-9 * max(1.0, abs(va)):
                return False
        return True
    except Exception:
        return False


# ---------------------------------------------------------------- 主计算
def _bool(v):
    if isinstance(v, str):
        return v.strip().lower() in ("1", "true", "yes", "y", "t")
    try:
        return bool(v)
    except Exception:
        return False


def _has_call(expr) -> bool:
    return isinstance(expr, str) and ("sigma2_debye" in expr or "sigma2_eins" in expr)


def suggest(rows, root=None) -> list[dict]:
    """路径表行 → 每个已勾选 nleg > 2 行的建议。

    rows：[dict(file, nleg, reff, label, use, deltar, sigma2)]（可选 geom=[(元素,(x,y,z)),…] 直接给几何，不读文件）。
    返回：[dict(index, label, deltar, sigma2, basis_deltar, basis_sigma2, exact, exact_sigma2, problem, sigma2_problem, note)]
      deltar / sigma2：建议表达式（无建议为 None）；problem：ΔR 与 σ² 都无建议的原因；sigma2_problem：只是 σ² 无建议的原因；
      exact：ΔR 只用了规则 1、2（精确）；exact_sigma2：只剩一根独立键（精确）；note：可写进路径 note 字段的一句话。"""
    rows = [dict(r) for r in rows]

    def geom_of(r):
        g = r.get("geom")
        return list(g) if g is not None else path_atoms(r["file"], root)

    def dirof(r):
        return str(Path(str(r.get("file", ""))).parent).replace("\\", "/")

    singles = []                                   # 已勾选的单散射行
    for i, r in enumerate(rows):
        if _bool(r.get("use")) and int(r.get("nleg", 0)) == 2:
            try:
                el = geom_of(r)[1][0]
            except Exception:
                continue
            singles.append(dict(i=i, el=el, reff=float(r["reff"]), dir=dirof(r), deltar=str(r.get("deltar", "")).strip(),
                                sigma2=str(r.get("sigma2", "")).strip(), label=str(r.get("label", ""))))
    out = []
    for i, r in enumerate(rows):
        if not (_bool(r.get("use")) and int(r.get("nleg", 0)) > 2):
            continue
        res = dict(index=i, label=str(r.get("label", "")), deltar=None, sigma2=None, basis_deltar="", basis_sigma2="",
                   exact=False, exact_sigma2=False, problem="", sigma2_problem="", note="")
        out.append(res)
        try:
            _one(r, res, singles, geom_of(r), dirof(r))
        except Exception as ex:
            res["deltar"] = res["sigma2"] = None
            res["problem"] = f"无法读取路径几何：{ex} / cannot read the path geometry: {ex}"
    return out


def _one(r, res, singles, geom, d):
    A = geom[0][1]
    el_a = geom[0][0]
    n = len(geom) - 1
    atoms = [(geom[j][0], _sub(geom[j][1], A)) for j in range(1, n + 1)]       # 相对 A 的坐标
    rad = [_norm(p) for _, p in atoms]

    def single_for(el, dist, tol):
        c = [s for s in singles if s["dir"] == d and s["el"] == el and abs(s["reff"] - dist) <= tol]
        return min(c, key=lambda s: abs(s["reff"] - dist)) if c else None

    coef: dict = {}                    # 键 -> 系数（对 Δr 的 δL 系数，尚未乘 ½）
    owner: dict = {}                   # 键 -> 单散射行（仅等价键直接记；原子键延后匹配）
    rules = set()
    cos_col = math.cos(math.radians(COLLINEAR_DEG))

    def akey(j):                       # 原子键：相同坐标的原子是同一根键
        return ("a", _key(atoms[j][1]))

    atom_of = {}                       # 键 -> (元素, 距离)
    for j in range(n):
        atom_of[akey(j)] = (atoms[j][0], rad[j])

    def add(k, c):
        coef[k] = coef.get(k, 0.0) + c

    rules.add(1)
    at_a = [r_ < 1e-9 for r_ in rad]                     # 与吸收原子同位置的散射原子（路径折回吸收位点）按 A 处理
    seq = [None] + list(range(n)) + [None]               # None = 吸收原子；腿 = 相邻两项
    for t in range(len(seq) - 1):
        i_, j_ = seq[t], seq[t + 1]
        oi = i_ is None or at_a[i_]
        oj = j_ is None or at_a[j_]
        if oi and oj:
            continue
        if oi or oj:                                     # 规则 1：腿含 A
            add(akey(j_ if oi else i_), 1.0)
            continue
        pi, pj = atoms[i_][1], atoms[j_][1]
        ri, rj = rad[i_], rad[j_]
        L = _norm(_sub(pi, pj))
        if L < 1e-9:
            continue                                     # 同一原子相邻两次：零长度腿
        cos = _dot(pi, pj) / (ri * rj)
        if cos > cos_col or cos < -cos_col:                                      # 规则 2：共线
            rules.add(2)
            if cos > 0:
                far, near = (i_, j_) if ri >= rj else (j_, i_)
                add(akey(far), 1.0)
                add(akey(near), -1.0)
            else:
                add(akey(i_), 1.0)
                add(akey(j_), 1.0)
            continue
        ei, ej = atoms[i_][0], atoms[j_][0]                                      # 规则 3：等价键
        cands = [s for s in singles if s["dir"] == d and abs(s["reff"] - L) <= BOND_TOL
                 and ((ei == el_a and ej == s["el"]) or (ej == el_a and ei == s["el"]))]
        if cands:
            s = min(cands, key=lambda s: abs(s["reff"] - L))
            k = ("e", frozenset((_key(pi), _key(pj))))
            add(k, 1.0)
            owner[k] = s
            rules.add(3)
            continue
        rules.add(4)                                                             # 规则 4：键角不变
        add(akey(i_), (ri - rj * cos) / L)
        add(akey(j_), (rj - ri * cos) / L)

    # 把每根键对应到单散射行
    bonds = []                                                                   # [(c_b, 行)]
    for k, c in coef.items():
        if abs(c) < _ZERO:
            continue
        if k[0] == "a":
            el, dist = atom_of[k]
            s = single_for(el, dist, SS_TOL)
            if s is None:
                res["problem"] = (f"缺少 {el}@{dist:.3f} 的单散射路径（先勾选） / missing single-scattering path for "
                                  f"{el}@{dist:.3f} (tick it first)")
                return
        else:
            s = owner[k]
        if not s["deltar"]:
            res["problem"] = (f"单散射行 {s['label']} 的 deltar 为空 / the deltar of single-scattering row {s['label']} is empty")
            return
        bonds.append((0.5 * c, s))
    if not bonds:
        res["deltar"], res["sigma2"] = "0", "0"
        res["problem"] = "所有键的贡献相互抵消 / all bond contributions cancel"
        return

    order = sorted({s["i"] for _, s in bonds})
    by_row = {i: next(s for _, s in bonds if s["i"] == i) for i in order}

    def merged(field, f):                                # 表达式文本相同的行合并（如 Ir-O 两行都用 dr1）
        acc: dict = {}
        for i in order:
            e = by_row[i][field] or "0"
            acc[_norm_expr(e)] = [acc.get(_norm_expr(e), [0.0, e])[0] + sum(f(c) for c, s in bonds if s["i"] == i), e]
        return [tuple(v) for v in acc.values()]
    res["deltar"] = _combine(merged("deltar", lambda c: c))
    res["exact"] = rules <= {1, 2}
    names = {1: ("A–X 键", "A–X bonds"), 2: ("共线（精确）", "collinear (exact)"),
             3: ("等价键", "equivalent bond"), 4: ("键角不变线性化", "fixed-angle linearisation")}
    res["basis_deltar"] = ("ΔR：" + " + ".join(names[x][0] for x in sorted(rules)) + " / ΔR: "
                           + " + ".join(names[x][1] for x in sorted(rules)))
    res["exact_sigma2"] = rules <= {1, 2} and len(bonds) == 1

    # σ²
    s2 = [by_row[i]["sigma2"] for i in order]
    calls = [_has_call(x) for x in s2]
    if any(calls):
        if not all(calls) or len({_norm_expr(x) for x in s2}) != 1:
            res["sigma2_problem"] = ("所涉单散射行的 σ² 温度模型不同（θ、模型或混用）：不给 σ² 建议 / the single-scattering rows use "
                                     "different σ² temperature models (theta, model, or mixed): no σ² suggestion")
        else:
            res["sigma2"] = s2[0]
            res["basis_sigma2"] = "σ²：沿用同一温度模型调用与 θ / σ²: same temperature-model call and theta"
            if "sigma2_eins" in s2[0]:
                from .sigma2 import einstein_ms_warning
                res["basis_sigma2"] += "；" + einstein_ms_warning(res["label"], int(r["nleg"]))
    else:
        res["sigma2"] = _combine(merged("sigma2", lambda c: c * c))
        res["basis_sigma2"] = ("σ²：独立键近似（精确）" if res["exact_sigma2"] else "σ²：独立键近似") + \
                              (" / σ²: independent-bond approximation (exact)" if res["exact_sigma2"]
                               else " / σ²: independent-bond approximation")
    res["note"] = f"msbind: {res['basis_deltar'].split(' / ')[0]}; {res['basis_sigma2'].split(' / ')[0].split('；')[0]}"


# ---------------------------------------------------------------- 模型 JSON 辅助（CLI 用）
def path_info(file, root=None) -> tuple:
    """FEFF 路径文件 → (nleg, reff)。"""
    from .paths import ROOT
    root = ROOT if root is None else root
    f = Path(file)
    if root and not f.is_absolute():
        f = Path(root) / f
    from larch.xafs import feffpath
    p = feffpath(str(f))
    return int(p.nleg), float(p.reff)


def model_rows(paths_list, root=None) -> list[dict]:
    """模型 JSON 的路径列表 → suggest 用的行（模型里的路径都是已勾选）。"""
    rows = []
    for ps in paths_list:
        nleg, reff = path_info(ps["file"], root)
        rows.append(dict(file=ps["file"], nleg=nleg, reff=reff, label=ps.get("label", ""), use=True,
                         deltar=str(ps.get("deltar", "0")), sigma2=str(ps.get("sigma2", "0.003"))))
    return rows


def apply_to_paths(paths_list, sugg) -> list[str]:
    """把建议写进模型 JSON 的路径列表（就地修改）：deltar / sigma2 / note。已等价的不动。返回改动说明。"""
    changed = []
    for s in sugg:
        ps = paths_list[s["index"]]
        did = []
        if s["deltar"] is not None and not equivalent(ps.get("deltar", "0"), s["deltar"]):
            ps["deltar"] = s["deltar"]
            did.append("deltar")
        if s["sigma2"] is not None and not equivalent(ps.get("sigma2", "0.003"), s["sigma2"]):
            ps["sigma2"] = s["sigma2"]
            did.append("sigma2")
        if did:
            ps["note"] = s["note"]
            changed.append(f"{s['label']}: " + "+".join(did))
    return changed
