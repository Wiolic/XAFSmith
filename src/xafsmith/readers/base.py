"""readers.base —— 各格式 reader 共用的部分：错误类型、Group 构造、文本表格解析、列名映射。

设计见 docs/dev/io_readers.md。要点：
  * Group.mode 只表示测量模式（trans / fluo / None）；μ 的来源记在 Group.mu_from（channels / file）。
  * 文件里同时有原始通道与 μ 列时，一律由通道计算 μ；通道不全才用文件 μ 列。
  * 列按名称映射，不按列号；映射不唯一或缺必需列时抛 ReadError，不猜。
"""
from xafsmith import logs
import re
from pathlib import Path

import numpy as np
from larch import Group

from ..common import guess_edge


class ReadError(Exception):
    """读入失败：同时带中文与英文说明。"""

    def __init__(self, zh, en=None):
        self.zh, self.en = zh, en or zh
        super().__init__(f"{zh}（{self.en}）" if en else zh)


class Reader:
    """格式 reader 基类。detect 返回 0–100 的置信度；read 返回 Group 列表。"""
    name = ""
    label = ("", "")
    suffixes = ()

    def detect(self, path, head):
        return 0

    def read(self, path, mode=None, columns=None, group=None):
        raise NotImplementedError


# ------------------------------------------------------------------ μ 与 Group
def compute_mu(i0, i1=None, ifl=None, mode="trans"):
    if mode == "trans":
        return np.log(np.abs(i0) / np.abs(i1))
    if mode == "fluo":
        return ifl / i0
    raise ValueError(f"未知模式 {mode}")


def make_group(energy, i0=None, i1=None, ifl=None, mu=None, mode="trans", element=None, edge=None,
               e_nominal=None, filename="", label=None, timestamp="", source="", fmt="",
               mu_from=None, columns=None, guessed=None, warnings=None, description=""):
    """统一构造 Group：按能量排序、去重复点；mu 为空时由通道按 mode 计算。"""
    energy = np.asarray(energy, float)
    order = np.argsort(energy, kind="stable")
    energy = energy[order]

    def _o(a):
        return None if a is None else np.asarray(a, float)[order]

    i0, i1, ifl, mu = _o(i0), _o(i1), _o(ifl), _o(mu)
    keep = np.concatenate([[True], np.diff(energy) > 1e-6])
    energy = energy[keep]
    i0, i1, ifl, mu = [None if a is None else a[keep] for a in (i0, i1, ifl, mu)]
    if mu is None:
        mu = compute_mu(i0, i1, ifl, mode)
        mu_from = mu_from or "channels"
    else:
        mu_from = mu_from or "file"
    if element and not edge and e_nominal:
        edge = guess_edge(element, e_nominal)
    return Group(energy=energy, mu=mu, i0=i0, i1=i1, ifl=ifl, mode=mode, element=element,
                 edge=edge, e_nominal=e_nominal, filename=str(filename),
                 label=label or Path(filename).name, timestamp=timestamp, source=source or fmt,
                 e_shift=0.0, format=fmt, mu_from=mu_from, columns=dict(columns or {}),
                 meta_guessed=list(guessed or []), read_warnings=list(warnings or []),
                 description=description)


# ------------------------------------------------------------------ 文本表格
def read_text(path, nbytes=None):
    with open(path, "r", encoding="utf-8", errors="ignore") as f:
        return f.read() if nbytes is None else f.read(nbytes)


def split_table(text):
    """把文本分成 (数据行之前的行, 数据数组)。以 # 开头的行不当作数据；列数取出现最多的列数。"""
    pre, rows = [], []
    for line in text.splitlines():
        s = line.strip()
        if not s:
            continue
        if s[0] != "#":
            try:
                vals = [float(x) for x in re.split(r"[\s,]+", s)]
            except ValueError:
                vals = None
            if vals is not None and len(vals) >= 2:
                rows.append(vals)
                continue
        if not rows:
            pre.append(s)
    if not rows:
        raise ReadError("文件中没有找到数值数据表", "No numeric data table found in the file")
    lens = [len(r) for r in rows]
    n = max(set(lens), key=lens.count)
    return pre, np.array([r for r in rows if len(r) == n], float)


def header_names(pre, ncols, xdi_cols=None):
    """列名：优先 XDI 的 Column.N；否则取数据前最后一个列数相同、全是非数字词的行。"""
    if xdi_cols and len(xdi_cols) == ncols:
        return [c[0] for c in xdi_cols], [c[1] for c in xdi_cols]
    for line in reversed(pre):
        toks = line.lstrip("#").strip().split()
        if len(toks) != ncols:
            continue
        ok = True
        for t in toks:
            try:
                float(t)
                ok = False
                break
            except ValueError:
                pass
        if ok and all(re.match(r"^[A-Za-z]", t) for t in toks):
            return toks, [""] * ncols
    return None, None


# ------------------------------------------------------------------ 列名映射
def _norm(name):
    return re.sub(r"[^a-z0-9/()_.]", "", str(name).lower()).replace("_", "")


_ROLE_RULES = [
    ("energy", r"^(e|ener.*|energy.*|ev|eev|ekev)$"),
    ("i0", r"^(i0|io|izero|imon|mon|monitor)$"),
    ("it", r"^(it|i1|itrans|itr|itransmission|trans|transmission)$"),
    ("if", r"^(if|ifl|ifluo|ifluor|ifluorescence|fluo|fluor|ff|if\d+|ifl\d+|ch\d+|roi\d*|sdd\d*)$"),
    ("mu", r"^(mu|xmu|mutrans|mutr|mut|mufluor|mufluo|muf|ln\(i0/i1\)|lni0/i1|if/i0|abs|absorption)$"),
]
_IF_TOTAL = {"if", "ifl", "ifluo", "ifluor", "ifluorescence", "fluo", "fluor", "ff"}
_MU_MODE_HINT = {"mutrans": "trans", "mutr": "trans", "mut": "trans", "ln(i0/i1)": "trans",
                 "lni0/i1": "trans", "mufluor": "fluo", "mufluo": "fluo", "muf": "fluo", "if/i0": "fluo"}


def auto_roles(names):
    """按列名猜角色 → ({角色: [列号, ...]}, 警告列表, μ 列名给出的模式提示)。"""
    roles, warns, hint = {}, [], None
    for i, nm in enumerate(names):
        key = _norm(nm)
        for role, pat in _ROLE_RULES:
            if re.match(pat, key):
                roles.setdefault(role, []).append(i)
                if role == "mu" and hint is None:
                    hint = _MU_MODE_HINT.get(key)
                break
    for role in ("energy", "i0", "it", "mu"):
        if len(roles.get(role, [])) > 1:
            warns.append(f"角色 {role} 匹配到多列 {[names[i] for i in roles[role]]}，取第一列"
                         f" / role {role} matched several columns, using the first")
            roles[role] = roles[role][:1]
    if len(roles.get("if", [])) > 1:
        tot = [i for i in roles["if"] if _norm(names[i]) in _IF_TOTAL]
        if tot:
            roles["if"] = tot[:1]
        else:
            warns.append(f"荧光通道 {[names[i] for i in roles['if']]} 已求和"
                         f" / fluorescence channels summed")
    return roles, warns, hint


def user_roles(columns, names, ncols):
    """用户给的映射：{角色: 列名 | 列号 | [..]}（也接受 "i1" 作为 it 的别名）。"""
    roles = {}
    for key, val in columns.items():
        role = {"i1": "it", "ifl": "if"}.get(key, key)
        if role not in ("energy", "i0", "it", "if", "mu"):
            continue
        vals = val if isinstance(val, (list, tuple)) else [val]
        idx = []
        for v in vals:
            if isinstance(v, (int, np.integer)):
                if not 0 <= v < ncols:
                    raise ReadError(f"列号 {v} 超出范围（共 {ncols} 列）",
                                    f"Column index {v} out of range ({ncols} columns)")
                idx.append(int(v))
                continue
            if names is None:
                raise ReadError("文件没有列名行，请用列号指定映射",
                                "The file has no column names; give column indices")
            hit = [i for i, nm in enumerate(names) if str(nm) == str(v)] or \
                  [i for i, nm in enumerate(names) if _norm(nm) == _norm(v)]
            if not hit:
                raise ReadError(f"找不到列“{v}”，文件中的列名：{names}",
                                f"Column '{v}' not found; columns: {names}")
            idx.append(hit[0])
        roles[role] = idx
    return roles


def _energy_to_ev(e, name, unit, guessed):
    txt = f"{name} {unit}".lower()
    med = float(np.median(e))
    if "kev" in txt:
        return e * 1000.0
    if re.search(r"deg|angle|theta|bragg", txt):
        raise ReadError("能量列看起来是角度，请先换算成能量(eV)",
                        "The energy column looks like an angle; convert to eV first")
    if med < 2:
        raise ReadError(f"能量列中位数 {med:g} 太小，既不像 eV 也不像 keV（可能是角度或点序号）",
                        f"Energy median {med:g} is neither eV nor keV (angle or index?)")
    if med < 100:
        guessed.append("energy_unit")
        return e * 1000.0
    return e


def table_to_group(path, fmt, pre, data, names, units, columns=None, mode=None, element=None,
                   edge=None, e_nominal=None, timestamp="", label=None, guessed=None,
                   description="", warnings=None, strict_energy=True):
    """文本表格 → Group（列映射、模式判定、μ 计算与一致性检查都在这里）。"""
    guessed, warnings = list(guessed or []), list(warnings or [])
    ncols = data.shape[1]
    hint = None
    if columns:
        roles = user_roles(columns, names, ncols)
        mode = mode or columns.get("mode")
    else:
        if names is None:
            raise ReadError("没有识别到列名行，请指定列映射（能量、I0、It / If 或 μ 所在列）",
                            "No column-name line found; specify the column mapping")
        roles, w, hint = auto_roles(names)
        warnings += w
    if "energy" not in roles:
        raise ReadError(f"没有找到能量列，文件中的列名：{names}", f"No energy column; columns: {names}")
    ie = roles["energy"][0]
    energy = _energy_to_ev(data[:, ie], names[ie] if names else "", units[ie] if units else "", guessed)
    d = np.diff(energy)
    if strict_energy and len(d) and (d < 0).any() and (d > 0).any() and (d < 0).mean() > 0.02:
        raise ReadError("能量列不单调（既有上升又有下降），可能选错了列或文件含多段扫描",
                        "Energy column is not monotonic (wrong column or multi-scan file?)")

    def col(r):
        return None if r not in roles else data[:, roles[r][0]]

    i0, it, mu_file = col("i0"), col("it"), col("mu")
    ifl = None if "if" not in roles else data[:, roles["if"]].sum(axis=1)
    mapped = {r: [(names[i] if names else i) for i in ix] for r, ix in roles.items()}

    has_t, has_f = i0 is not None and it is not None, i0 is not None and ifl is not None
    if mode not in ("trans", "fluo"):
        mode = None
    if mode is None:
        if has_t and not has_f:
            mode = "trans"
        elif has_f and not has_t:
            mode = "fluo"
        elif has_t and has_f:
            mode = "trans"
            guessed.append("mode")
        else:
            mode = hint
    use_channels = (mode == "trans" and has_t) or (mode == "fluo" and has_f)
    mu = None
    if use_channels:
        if mu_file is not None:
            calc = np.log(np.abs(i0) / np.abs(it)) if mode == "trans" else ifl / i0
            ok = np.isfinite(calc) & np.isfinite(mu_file)
            if ok.sum() > 5 and np.std(calc[ok]) > 0 and np.std(mu_file[ok]) > 0:
                r = float(np.corrcoef(calc[ok], mu_file[ok])[0, 1])
                if r < 0.999:
                    warnings.append(f"由通道算出的 μ 与文件 μ 列相关系数 {r:.4f} < 0.999，请核对列映射"
                                    f" / computed μ vs file μ column correlation {r:.4f} < 0.999; check the mapping")
    elif mu_file is not None:
        mu = mu_file
    else:
        raise ReadError(f"通道不全，无法计算 μ：已识别 {mapped}（透射需要 I0+It，荧光需要 I0+If，或提供 μ 列）",
                        f"Cannot compute μ from channels {mapped}")
    if element is None or edge is None:
        mu_chk = mu if mu is not None else compute_mu(i0, it, ifl, mode)
        el, ed, cands = guess_element_edge(energy, mu_chk)
        if element is not None and edge is None:        # 文件头只给了元素：在候选里找该元素的边
            same = [c for c in cands if c[0] == element]
            if same:
                edge, e_nominal = same[0][1], e_nominal or same[0][2]
                guessed.append("edge")
        elif el and element is None:
            element, edge = el, ed
            e_nominal = e_nominal or cands[0][2]
            guessed += ["element", "edge"]
            if len(cands) > 1:
                warnings.append("吸收边按能量猜测，候选：" + "、".join(f"{a} {b}" for a, b, _ in cands) +
                                "，请核对 / edge guessed from energy; candidates: " +
                                ", ".join(f"{a} {b}" for a, b, _ in cands))
    return make_group(energy, i0=i0, i1=it, ifl=ifl, mu=mu, mode=mode, element=element, edge=edge,
                      e_nominal=e_nominal, filename=path, label=label, timestamp=timestamp, fmt=fmt,
                      columns=mapped, guessed=guessed, warnings=warnings, description=description,
                      mu_from="channels" if use_channels else "file")


# ------------------------------------------------------------------ 元素与吸收边
def guess_element_edge(energy, mu, window=25.0):
    """由一阶导数最大处能量，在 xraydb（Elam）表中找 K/L1/L2/L3 边 → (元素, 边, 候选[(元素, 边, 表值)])。
    候选多于一个时仍返回第一个（最近的），调用方应把候选写进警告，由用户核对。"""
    import xraydb
    e = np.asarray(energy, float)
    y = np.asarray(mu, float)
    if len(e) < 10:
        return None, None, []
    k = 5
    ys = np.convolve(y, np.ones(k) / k, mode="same")
    d = np.gradient(ys, e)
    d[:k], d[-k:] = 0, 0
    e_d = float(e[int(np.argmax(d))])
    cands = []
    for z in range(3, 93):
        sym = xraydb.atomic_symbol(z)
        try:
            edges = xraydb.xray_edges(sym)
        except Exception:                      # noqa: BLE001
            logs.log.debug("readers.base.guess_element_edge 出错（已忽略或已提示）", exc_info=True)
            continue
        for nm in ("K", "L3", "L2", "L1"):
            if nm in edges and abs(edges[nm].energy - e_d) <= window:
                cands.append((sym, nm, float(edges[nm].energy)))
    # K、L3 边最常测，L2、L1 其次：同一能量窗口内先按这个类别排，再按离 E_d 的距离排。
    # （导数最大值常比表值高 5–15 eV，只按距离排会把 Fe K 误判成能量略高的 Nd L1。）
    prio = {"K": 0, "L3": 0, "L2": 1, "L1": 2}
    cands.sort(key=lambda c: (prio[c[1]], abs(c[2] - e_d)))
    return (cands[0][0], cands[0][1], cands) if cands else (None, None, [])


def nearest_edge(energy, window=10.0):
    """表中离 energy 最近的 K/L 边（文件头只给了 E0 时用）→ (元素, 边, 表值) 或 None。"""
    import xraydb
    best = None
    for z in range(3, 93):
        sym = xraydb.atomic_symbol(z)
        try:
            edges = xraydb.xray_edges(sym)
        except Exception:                      # noqa: BLE001
            logs.log.debug("readers.base.nearest_edge 出错（已忽略或已提示）", exc_info=True)
            continue
        for nm in ("K", "L3", "L2", "L1"):
            if nm in edges:
                dd = abs(edges[nm].energy - energy)
                if dd <= window and (best is None or dd < best[0]):
                    best = (dd, sym, nm, float(edges[nm].energy))
    return None if best is None else best[1:]
