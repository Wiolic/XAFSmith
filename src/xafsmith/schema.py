"""数据标准：meta.csv、xafsmith.json、拟合模型 JSON 的字段定义与检查（xafsmith validate）。

完整说明见 docs/数据标准.md。

分级原则：
- 错误：流程会崩溃，或会悄悄算错（范围颠倒、类型不对、找不到文件、重复登记、变量数 ≥ N_idp）。
- 警告：能运行，但违反数据规范或可能不物理（k 范围超出数据或越过干扰边、变量数 > N_idp/2、rbkg 偏大）。
"""
from xafsmith import logs
import json

import pandas as pd

from . import paths

# ---------------------------------------------------------------- meta.csv
META_COLS = ["file", "sample", "edge_key", "mode", "role", "use", "time", "npts", "emax", "note",
             "batch", "ref_file", "format", "group"]      # format、group 为可选列（schema 1.1）
META_REQUIRED = ["file", "sample", "edge_key", "mode", "role", "use", "ref_file"]
ROLES = {"reference", "standard", "sample"}
MODES = {"trans", "fluo", ""}

# ---------------------------------------------------------------- xafsmith.json
EDGE_REQUIRED = ["element", "edge", "e_table", "norm", "bkg", "ft"]
NORM_KEYS = ["pre1", "pre2", "norm1", "norm2", "nnorm"]
BKG_KEYS = ["rbkg", "kweight"]
FT_KEYS = ["kmin", "kmax", "dk", "window", "kweight"]
# ---------------------------------------------------------------- 模型 JSON
MODEL_REQUIRED = ["name", "sample", "kmin", "kmax", "rmin", "rmax", "kweight", "params", "paths"]
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


def _isnum(v):
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def _isnum_or_list(v):
    return _isnum(v) or (isinstance(v, list) and len(v) > 0 and all(_isnum(x) for x in v))


FT_WINDOWS = ("kai", "han", "par", "wel", "gau", "sin")     # larch xafsft.FT_WINDOWS_SHORT：按名称前 3 个字母识别


def _window_ok(v):
    return isinstance(v, str) and v.strip().lower()[:3] in FT_WINDOWS


from .common import n_idp          # noqa: E402  独立点数 N_idp = 2ΔkΔR/π，与拟合共用同一实现


def count_varied(params):
    """与 fit_exafs._mkparam 一致：数字 = 变量；字符串或带 expr = 约束；dict 默认 vary=True。"""
    n = 0
    for spec in (params or {}).values():
        if _isnum(spec):
            n += 1
        elif isinstance(spec, dict) and not spec.get("expr") and spec.get("vary", True):
            n += 1
    return n


def _json_error(ex):
    """JSONDecodeError → “第 N 行第 M 列：说明”。"""
    if isinstance(ex, json.JSONDecodeError):
        return f"第 {ex.lineno} 行第 {ex.colno} 列：{ex.msg}"
    return str(ex)


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
        ft, nm, bk = c.get("ft", {}), c.get("norm", {}), c.get("bkg", {})
        for sec, keys in (("norm", NORM_KEYS), ("bkg", BKG_KEYS), ("ft", FT_KEYS)):
            for k in keys:
                v = c.get(sec, {}).get(k)
                if v is None or k == "window":
                    continue
                listy = (sec, k) == ("ft", "kweight")
                if not (_isnum_or_list(v) if listy else _isnum(v)):
                    rep.err(f"{w}.{sec}.{k}", f"应为数字{'或数字列表' if listy else ''}，实际是 {v!r}")
        if "window" in ft and not _window_ok(ft["window"]):
            rep.err(f"{w}.ft.window", f"窗函数 {ft['window']!r} 无法识别（可用 hanning、kaiser、parzen、welch、gaussian、sine）")
        if _isnum(ft.get("kmin")) and ft["kmin"] < 0:
            rep.err(f"{w}.ft.kmin", "不能为负")
        if _isnum(ft.get("kmin")) and _isnum(ft.get("kmax")) and ft["kmin"] >= ft["kmax"]:
            rep.err(f"{w}.ft", "kmin 应小于 kmax")
        if _isnum(ft.get("dk")) and ft["dk"] < 0:
            rep.err(f"{w}.ft.dk", "不能为负")
        if _isnum(nm.get("pre1")) and _isnum(nm.get("pre2")):
            if nm["pre1"] >= nm["pre2"]:
                rep.err(f"{w}.norm", "pre1 应小于 pre2（边前拟合范围）")
            if nm["pre2"] > 0:
                rep.warn(f"{w}.norm.pre2", "边前范围应在 E0 以下（pre2 通常为负）")
        if _isnum(nm.get("norm1")):
            if nm["norm1"] <= 0:
                rep.warn(f"{w}.norm.norm1", "边后范围应在 E0 以上（norm1 通常 > 0）")
            if _isnum(nm.get("norm2")) and nm["norm2"] > 0 and nm["norm1"] >= nm["norm2"]:
                rep.err(f"{w}.norm", "norm1 应小于 norm2（norm2 ≤ 0 表示距数据末端的距离）")
        if _isnum(bk.get("rbkg")):
            if bk["rbkg"] <= 0:
                rep.err(f"{w}.bkg.rbkg", "应大于 0")
            elif bk["rbkg"] > 1.5:
                rep.warn(f"{w}.bkg.rbkg", f"rbkg = {bk['rbkg']} Å 偏大，可能扣掉第一壳层信号（通常约为第一壳层峰位的一半）")
        if _isnum(bk.get("kweight")) and bk["kweight"] not in (0, 1, 2, 3):
            rep.warn(f"{w}.bkg.kweight", "通常取 1、2 或 3")
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
    key = ["file", "group"] if "group" in meta else ["file"]      # .prj 一个文件含多个 group，按 (file, group) 判重
    dup = meta[meta.duplicated(key, keep=False)]
    for _, g in dup.groupby(key):
        rep.err(w, f"文件 {g.iloc[0].file}" + (f"（group {g.iloc[0].group!r}）" if "group" in meta else "")
                + f" 重复登记，位于第 {', '.join(str(i + 2) for i in g.index)} 行")
    # ref_file 只记文件名：一个文件（.prj）里只能有一个参比组，否则校准不知道用哪一组
    for f, g in meta[meta.role == "reference"].groupby("file"):
        if len(g) > 1:
            rep.err(w, f"文件 {f} 中有 {len(g)} 个 role=reference 的组（第 {', '.join(str(i + 2) for i in g.index)} 行）："
                       "ref_file 只能指向文件，无法区分组；请只保留一个参比组，其余改为 standard，或把参比另存为单独文件")
    for i, r in meta.iterrows():
        at = f"{w} 第 {i + 2} 行（{r.file}）"
        for c in ("file", "sample", "edge_key"):
            if not str(r[c]).strip():
                rep.err(f"{w} 第 {i + 2} 行 列 {c}", "不能为空")
        for c in ("npts", "emax"):
            v = str(r.get(c, "") or "").strip()
            if v:
                try:
                    float(v)
                except ValueError:
                    rep.warn(f"{w} 第 {i + 2} 行 列 {c}", f"应为数字，实际是 {v!r}（由 xafsmith init 生成，可重新生成）")
        if not paths.resolve(r.file).exists():
            rep.err(at, "原始文件不存在")
        if r.role not in ROLES:
            rep.err(at, f"role 应为 {sorted(ROLES)}")
        if r["mode"] not in MODES:
            rep.err(at, "mode 应为 trans / fluo")
        fmt = str(r.get("format", "") or "")
        if fmt:
            from .readers import BY_NAME
            if fmt not in BY_NAME and fmt not in (cfg.get("formats") or {}):
                rep.err(at, f"format “{fmt}” 不是已支持的格式，也不在 {paths.MARKER} 的 formats 模板中"
                            f"（可用：{', '.join(BY_NAME)}）")
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


def sample_elements(cfg, edge_key, sample):
    """干扰边检查用的元素：overrides.<样品>.elements_in_sample 优先，否则取该边的 elements_in_sample。"""
    c = cfg.get("edges", {}).get(edge_key) or {}
    ov = cfg.get("overrides", {}).get(sample, {}).get("elements_in_sample")
    return list(ov or c.get("elements_in_sample") or [c.get("element")])


def k_limits(cfg, meta, min_span_frac=0.9):
    """每个 (样品, 吸收边) 的可用 k 上限 {(样品, edge_key): (k_lim, 原因, 干扰元素或 None)}。
    k_lim = min(合并后数据末端 k, 第一个干扰边 k − 0.3)（mut_planner.k_limit）。
    与 normalize.merge_scans 一致：能量跨度不到最长扫描 min_span_frac 的短扫描不参与合并，因此也不计入。
    查不到吸收边数据时跳过该样品。"""
    from .mut_planner import k_limit
    from .common import e2k, edge_energy
    out = {}
    if meta is None or "emax" not in meta:
        return out
    used = meta[meta.use.astype(str) != "0"].copy()
    used["_emax"] = pd.to_numeric(used.emax, errors="coerce")
    for (sample, ek), g in used.dropna(subset=["_emax"]).groupby(["sample", "edge_key"]):
        c = cfg.get("edges", {}).get(ek) or {}
        if "element" not in c or "edge" not in c:
            continue
        try:
            e0 = edge_energy(c["element"], c["edge"])
            span = g._emax - e0                    # 起点相近时，用 emax − E0 近似能量跨度
            emax = float(g._emax[span >= min_span_frac * span.max()].min())
            kl, df = k_limit(sample_elements(cfg, ek, sample), c["element"], c["edge"], emax)
            kdata = float(e2k(emax - e0))
            if len(df) and kl < kdata - 1e-6:
                out[(sample, ek)] = (kl, f"{df.element.iloc[0]} {df.edge.iloc[0]} 边在 k = {df.k.iloc[0]:.2f}",
                                     df.element.iloc[0])
            else:
                out[(sample, ek)] = (kl, f"数据末端 {emax:.0f} eV", None)
        except Exception:                           # noqa: BLE001  xraydb 查不到时不阻断校验
            logs.log.debug("schema.k_limits 出错（已忽略或已提示）", exc_info=True)
            continue
    return out


def check_krange(rep, cfg, meta, klim):
    """ft.kmax（含 overrides）不得超过可用 k 上限（CLAUDE.md 4.9：没有干扰边检查不得选 k 范围）。
    同一吸收边、同一原因的样品合并成一条警告。"""
    groups = {}
    for (sample, ek), (kl, why, el) in sorted(klim.items()):
        kmax = (cfg.get("overrides", {}).get(sample, {}).get("ft", {}).get("kmax")
                or cfg.get("edges", {}).get(ek, {}).get("ft", {}).get("kmax"))
        if _isnum(kmax) and kmax > kl + 0.05:
            groups.setdefault((ek, kmax, round(kl, 2), why, el), []).append(sample)
    for (ek, kmax, kl, why, el), ss in groups.items():
        msg = f"kmax = {kmax} 超过可用上限 {kl:.2f} Å⁻¹（{why}）；涉及 {len(ss)} 个样品：{', '.join(ss)}"
        if el:
            msg += (f"。若其中有样品不含 {el}，在 overrides.<样品>.elements_in_sample 写该样品的实际元素"
                    f"（只影响此检查，需在 overrides_reason 写理由）")
        rep.warn(f"{paths.MARKER} edges.{ek}.ft.kmax", msg)


def check_preedge(rep, cfg, meta):
    """其他元素的吸收边落在 [E0+pre1, E0) 内：边前直线被台阶带偏，归一化与边跳受影响。
    按样品的 elements_in_sample（含 overrides）与 norm.pre1/pre2（含 overrides）检查，同一边同一结果合并为一条。"""
    from .mut_planner import pre_edge_edges
    groups = {}
    for (sample, ek), _ in meta[meta.use.astype(str) != "0"].groupby(["sample", "edge_key"]):
        c = cfg.get("edges", {}).get(ek) or {}
        if "element" not in c or "edge" not in c:
            continue
        nm = dict(c.get("norm", {}))
        nm.update(cfg.get("overrides", {}).get(sample, {}).get("norm", {}))
        if not (_isnum(nm.get("pre1")) and _isnum(nm.get("pre2"))):
            continue
        try:
            df = pre_edge_edges(sample_elements(cfg, ek, sample), c["element"], c["edge"], nm["pre1"], 0.0)
        except Exception:                           # noqa: BLE001  xraydb 查不到时不阻断校验
            logs.log.debug("schema.check_preedge 出错（已忽略或已提示）", exc_info=True)
            continue
        if len(df):
            where = "; ".join(f"{r.element} {r.edge} {r.energy:.0f} eV（E0{r.dE:+.0f}，"
                              + ("在边前拟合范围内" if r.dE <= nm["pre2"] else "在 pre2 与 E0 之间，叠加在主边上") + "）"
                              for r in df.itertuples())
            groups.setdefault((ek, nm["pre1"], nm["pre2"], where), []).append(sample)
    for (ek, p1, p2, where), ss in groups.items():
        rep.warn(f"{paths.MARKER} edges.{ek}.norm（pre1 = {p1}, pre2 = {p2}）",
                 f"边前范围内有其他吸收边：{where}；涉及 {len(ss)} 个样品：{', '.join(ss)}。"
                 "缩小边前范围使其避开，或在 overrides 为这些样品单独设置；样品不含该元素时改 elements_in_sample")


MODEL_REQUIRED_MULTI = ["name", "params", "datasets"]
_DS_INHERIT = ("kmin", "kmax", "dk", "window", "kweight", "rmin", "rmax", "fitspace")


def _check_ranges(rep, where, m):
    """范围、kweight、window（旧格式与多数据集的每个数据集共用；旧格式提示文字与位置与 v1.1 相同）。"""
    for k in ("kmin", "kmax", "rmin", "rmax"):
        if k in m and not _isnum(m[k]):
            rep.err(f"{where} {k}", f"应为数字，实际是 {m[k]!r}")
        elif _isnum(m.get(k)) and m[k] < 0:
            rep.err(f"{where} {k}", "不能为负")
    for lo, hi in (("kmin", "kmax"), ("rmin", "rmax")):
        if _isnum(m.get(lo)) and _isnum(m.get(hi)) and m[lo] >= m[hi]:
            rep.err(f"{where} {lo}/{hi}", f"{lo} 应小于 {hi}")
    if "kweight" in m and not _isnum_or_list(m["kweight"]):
        rep.err(f"{where} kweight", f"应为数字或数字列表，实际是 {m['kweight']!r}")
    if "window" in m and not _window_ok(m["window"]):
        rep.err(f"{where} window", f"窗函数 {m['window']!r} 无法识别")


def _valid_range(m):
    rng = [m.get(k) for k in ("kmin", "kmax", "rmin", "rmax")]
    return rng if all(_isnum(v) for v in rng) and rng[0] < rng[1] and rng[2] < rng[3] else None


def _check_paths(rep, where, m, klim, samples):
    """k 上限、paths 结构、样品是否登记、FEFF 文件是否存在（同上，共用）。"""
    # 模型不写吸收边：样品只在一个吸收边登记时才能确定对照哪个上限
    mk = [v for (s, _ek), v in klim.items() if s == m.get("sample")]
    if _isnum(m.get("kmax")) and len(mk) == 1 and m["kmax"] > mk[0][0] + 0.05:
        kl, why, _ = mk[0]
        rep.warn(f"{where} kmax", f"kmax = {m['kmax']} 超过可用上限 {kl:.2f} Å⁻¹（{why}）")
    if not isinstance(m.get("paths", []), list) or not m.get("paths", [1]):
        rep.err(f"{where} paths", "应是非空数组")
    for j, pth in enumerate(m.get("paths", []) if isinstance(m.get("paths", []), list) else []):
        if not isinstance(pth, dict) or "file" not in pth:
            rep.err(f"{where} paths[{j}]", "每条路径需要 file 字段")
        elif "note" in pth and not isinstance(pth["note"], str):         # B5：note 是可选说明字符串，计算忽略
            rep.err(f"{where} paths[{j}].note", "note 应是字符串")
    if samples and m.get("sample") not in samples:
        rep.warn(where, f"样品 {m.get('sample')} 不在 meta.csv 中")
    missing = [p["file"] for p in (m.get("paths", []) if isinstance(m.get("paths", []), list) else [])
               if isinstance(p, dict) and "file" in p and not paths.resolve(p["file"]).exists()]
    if missing:
        rep.warn(where, f"{len(missing)} 个 FEFF 路径文件不存在（先运行 xafsmith feff），如 {missing[0]}")


def _check_multi(rep, at, m, klim, samples):
    """多数据集模型（有 datasets 键）。数据标准 4.1。"""
    for k in MODEL_REQUIRED_MULTI:
        if k not in m:
            rep.err(at, f"缺少字段 {k}")
    for k in ("sample", "paths"):
        if k in m:
            rep.err(f"{at} {k}", f"多数据集模型不得有顶层 {k}（写进 datasets[i]），否则旧代码会误读")
    if "params" in m and not isinstance(m["params"], dict):
        rep.err(f"{at} params", "应是对象 {名称: 初值或 {value, vary, min, max, expr}}")
    dl = m.get("datasets")
    if not isinstance(dl, list) or not dl:
        rep.err(f"{at} datasets", "应是非空数组")
        return
    ids, ni_tot, all_ok, fsp, by_sample = set(), 0.0, True, set(), {}
    for i, d in enumerate(dl):
        if not isinstance(d, dict):
            rep.err(f"{at} datasets[{i}]", "应是对象 { sample, paths, … }")
            all_ok = False
            continue
        did = d.get("id", d.get("sample"))
        where = f"{at} datasets[{i}]({did})"
        for k in ("sample", "paths"):
            if k not in d:
                rep.err(where, f"缺少字段 {k}")
        if "id" in d and (not isinstance(d["id"], str) or not d["id"].strip()):
            rep.err(f"{where} id", "不能为空")
        elif did is not None:
            if did in ids:
                rep.err(f"{where} id", f"id {did} 重复（缺省 id = sample）")
            ids.add(did)
        if "epsilon_k" in d and not (_isnum(d["epsilon_k"]) and d["epsilon_k"] > 0):
            rep.err(f"{where} epsilon_k", f"应为正数，实际是 {d['epsilon_k']!r}")
        blk = {k: d[k] if k in d else m[k] for k in _DS_INHERIT if k in d or k in m}
        blk.update(sample=d.get("sample"), paths=d.get("paths", []))
        miss = [k for k in ("kmin", "kmax", "rmin", "rmax", "kweight") if k not in blk]
        if miss:
            rep.err(where, f"缺少 {', '.join(miss)}（数据集与顶层都没有）")
        _check_ranges(rep, where, blk)
        rng = _valid_range(blk)
        if rng:
            ni_tot += n_idp(*rng)
        else:
            all_ok = False
        fsp.add(blk.get("fitspace", "r"))
        if d.get("sample") is not None:
            by_sample.setdefault(d["sample"], []).append(str(did))
        _check_paths(rep, where, blk, klim, samples)
    if all_ok and isinstance(m.get("params"), dict):
        nv = count_varied(m["params"])
        if nv >= ni_tot:
            rep.err(f"{at} params", f"变量数 {nv} ≥ Σ N_idp = {ni_tot:.1f}（2ΔkΔR/π，全部数据集合计），拟合欠定")
        elif nv > ni_tot / 2:
            rep.warn(f"{at} params", f"变量数 {nv} > Σ N_idp/2 = {ni_tot / 2:.1f}（2ΔkΔR/π，全部数据集合计），超出处理规范"
                                     "（XAFS 处理规范：变量数不多于 N_idp 的一半，最好 ≤ N_idp − 3），结果可靠性低")
    for smp, lst in by_sample.items():
        if len(lst) > 1:
            rep.warn(f"{at} datasets", f"样品 {smp} 在数据集 {'、'.join(lst)} 中重复使用：同一数据计入两次，误差会被低估")
    if len(fsp) > 1:
        rep.warn(f"{at} datasets", f"各数据集 fitspace 不同（{'、'.join(sorted(map(str, fsp)))}）：合计 R 因子把不同空间的"
                                   "残差相加，难以解释")


def _names_in(expr):
    """表达式里的变量名（排除作为函数被调用的名字与 pi）；解析失败返回 None。"""
    import ast
    try:
        tree = ast.parse(expr, mode="eval")
    except (SyntaxError, ValueError):
        return None
    called = {n.func.id for n in ast.walk(tree) if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)}
    return {n.id for n in ast.walk(tree) if isinstance(n, ast.Name) and n.id not in called and n.id != "pi"}


_PATH_EXPR_DEFAULT = dict(e0="e0", s02="s02", sigma2="0.003", deltar="0")


def _check_restraints(rep, at, m):
    """B3 软约束（数据标准 4.2），旧格式与多数据集共用。"""
    import math
    rs = m.get("restraints")
    if rs is None:
        return
    if not isinstance(rs, list):
        rep.err(f"{at} restraints", "应是数组 [{expr, value, sigma, name?, note?}]")
        return
    params = m.get("params") if isinstance(m.get("params"), dict) else None
    # 被路径字段或参数表达式用到的名字（与 larch 的 fix_unused_variables 判断一致）
    used = set()
    blocks = [d for d in m["datasets"] if isinstance(d, dict)] if isinstance(m.get("datasets"), list) else [m]
    for b in blocks:
        for ps in b.get("paths") or []:
            if not isinstance(ps, dict):
                continue
            for k in ("e0", "s02", "sigma2", "deltar", "N", "third", "fourth", "ei"):
                v = ps.get(k, _PATH_EXPR_DEFAULT.get(k))
                if isinstance(v, str):
                    used |= _names_in(v) or set()
    for spec in (params or {}).values():
        ex = spec if isinstance(spec, str) else (spec.get("expr") if isinstance(spec, dict) else None)
        if isinstance(ex, str):
            used |= _names_in(ex) or set()
    seen = set()
    for i, r in enumerate(rs):
        where = f"{at} restraints[{i}]"
        if not isinstance(r, dict):
            rep.err(where, "应是对象 {expr, value, sigma}")
            continue
        for k in ("expr", "value", "sigma"):
            if k not in r:
                rep.err(where, f"缺少字段 {k}")
        if "value" in r and not (_isnum(r["value"]) and math.isfinite(r["value"])):
            rep.err(f"{where} value", f"应为有限数字，实际是 {r['value']!r}")
        if "sigma" in r and not (_isnum(r["sigma"]) and math.isfinite(r["sigma"]) and r["sigma"] > 0):
            rep.err(f"{where} sigma", f"应为大于 0 的有限数字，实际是 {r['sigma']!r}")
        name = r.get("name", f"r{i + 1}")
        if not isinstance(name, str) or not name.strip():
            rep.err(f"{where} name", "不能为空")
        elif name in seen:
            rep.err(f"{where} name", f"名称 {name} 重复（缺省名为 r1、r2…按位置）")
        else:
            seen.add(name)
        if "expr" not in r:
            continue
        ex = r["expr"]
        if not isinstance(ex, str) or not ex.strip():
            rep.err(f"{where} expr", "应是非空的参数表达式字符串")
            continue
        names = _names_in(ex)
        if names is None:
            rep.err(f"{where} expr", f"表达式无法解析：{ex!r}")
            continue
        if params is None:
            continue
        unknown = sorted(n for n in names if n not in params)
        if unknown:
            rep.err(f"{where} expr", f"引用了 params 里没有的名字：{', '.join(unknown)}")
        ref = [n for n in names if n in params]
        if not unknown and not ref:
            rep.err(f"{where} expr", "没有引用任何模型参数")
            continue
        if ref and all(isinstance(params[n], dict) and not params[n].get("expr") and not params[n].get("vary", True)
                       for n in ref):
            rep.warn(f"{where} expr", "只涉及固定参数，软约束不起作用")
        for n in ref:
            sp = params[n]
            varied = _isnum(sp) or (isinstance(sp, dict) and not sp.get("expr") and sp.get("vary", True))
            if varied and n not in used:
                rep.warn(f"{where} expr", f"参数 {n} 不在任何路径中，larch 会把它固定，软约束对它不起作用")


def _check_sigma2(rep, at, m):
    """B6：temperature / tempK / sigma2_debye / sigma2_eins（数据标准 4.3；规则在 sigma2.model_issues）。"""
    from .sigma2 import model_issues
    for level, where, zh, _en in model_issues(m):
        (rep.err if level == "error" else rep.warn)(f"{at} {where}", zh)


def check_models(rep, meta, klim=None):
    samples = set(meta["sample"]) if meta is not None else set()
    klim = klim or {}
    for f in sorted(paths.MODELS.glob("*.json")):
        if f.name.startswith("_"):          # 模板
            continue
        at = paths.rel(f)
        try:
            m = json.loads(f.read_text(encoding="utf-8-sig"))
        except Exception as ex:
            logs.log.debug("schema.check_models 出错（已忽略或已提示）", exc_info=True)
            rep.err(at, f"JSON 解析失败：{_json_error(ex)}")
            continue
        if not isinstance(m, dict):
            rep.err(at, "顶层应是对象 { … }")
            continue
        if "datasets" in m:
            _check_multi(rep, at, m, klim, samples)
            _check_restraints(rep, at, m)
            _check_sigma2(rep, at, m)
            continue
        for k in MODEL_REQUIRED:
            if k not in m:
                rep.err(at, f"缺少字段 {k}")
        _check_ranges(rep, at, m)
        rng = [m.get(k) for k in ("kmin", "kmax", "rmin", "rmax")]
        if "params" in m and not isinstance(m["params"], dict):
            rep.err(f"{at} params", "应是对象 {名称: 初值或 {value, vary, min, max, expr}}")
        elif all(_isnum(v) for v in rng) and rng[0] < rng[1] and rng[2] < rng[3]:
            ni, nv = n_idp(*rng), count_varied(m.get("params"))
            if nv >= ni:
                rep.err(f"{at} params", f"变量数 {nv} ≥ N_idp = {ni:.1f}（2ΔkΔR/π），拟合欠定")
            elif nv > ni / 2:
                rep.warn(f"{at} params", f"变量数 {nv} > N_idp/2 = {ni / 2:.1f}（2ΔkΔR/π），超出处理规范"
                                         "（XAFS 处理规范：变量数不多于 N_idp 的一半，最好 ≤ N_idp − 3），结果可靠性低")
        _check_paths(rep, at, m, klim, samples)
        _check_restraints(rep, at, m)
        _check_sigma2(rep, at, m)


def check_structures(rep):
    from .structures import list_structures, read_structure
    for name in list_structures():
        try:
            read_structure(name)
        except Exception as ex:
            logs.log.debug("schema.check_structures 出错（已忽略或已提示）", exc_info=True)
            rep.err(f"structures/{name}", f"无法读入：{ex}")


def validate(structures=True):
    from .pipeline import load_meta
    rep = Report()
    check_layout(rep)
    cfg = {}
    if paths.CONFIG.exists():
        try:
            cfg = json.loads(paths.CONFIG.read_text(encoding="utf-8-sig"))
        except Exception as ex:
            logs.log.debug("schema.validate 出错（已忽略或已提示）", exc_info=True)
            rep.err(paths.MARKER, f"JSON 解析失败：{_json_error(ex)}")
    if cfg:
        check_config(rep, cfg)
    meta = None
    if paths.META.exists():
        try:
            meta = load_meta()
        except Exception as ex:
            logs.log.debug("schema.validate 出错（已忽略或已提示）", exc_info=True)
            rep.err(paths.rel(paths.META), f"无法读入：{ex}")
        if meta is not None:
            check_meta(rep, meta, cfg)
    else:
        rep.warn(paths.rel(paths.META), "尚无 meta.csv（把原始数据放进 data/raw/<批次>/ 后运行 xafsmith init）")
    klim = {}
    if cfg and meta is not None:
        klim = k_limits(cfg, meta)
        check_krange(rep, cfg, meta, klim)
        check_preedge(rep, cfg, meta)
    if paths.MODELS.exists():
        check_models(rep, meta, klim)
    if structures:
        check_structures(rep)
    return rep
