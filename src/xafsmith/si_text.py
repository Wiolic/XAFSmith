"""si_text —— 由已保存的拟合（output/fits/exafs_fits.csv）与模型（models/*.json）生成可放进 Supporting Information 的
EXAFS 拟合方法文本与参数表（中文 / English）。只写项目中有记录的事实。

命令行：xafsmith si [--fits "样品|模型" ...] [--lang en|zh]
"""
from xafsmith import logs
import json
import math
import re
from pathlib import Path

import numpy as np
import pandas as pd

from . import paths

_MATH = {k: getattr(math, k) for k in ("sqrt", "sin", "cos", "exp", "log", "pi")}


def load_fits():
    """每个（样品, 模型）最后一次保存的拟合：DataFrame（每行一条路径）"""
    if not paths.FITS_CSV.exists():
        return pd.DataFrame()
    d = pd.read_csv(paths.FITS_CSV, encoding="utf-8-sig")
    if not len(d):
        return d
    # 同一（样品, 模型）多次保存时，只取最后一次保存的那一组连续行
    key = d["sample"].astype(str) + "\x00" + d["model"].astype(str)
    d["_b"] = (key != key.shift()).cumsum()
    keep = d.groupby(key)["_b"].transform("max") == d["_b"]
    return d[keep].drop(columns=["_b"])


def fit_keys(fits=None):
    fits = load_fits() if fits is None else fits
    if not len(fits):
        return []
    return list(dict.fromkeys(f"{s}|{m}" for s, m in zip(fits["sample"], fits["model"])))


def _model_json(name, sample=None):
    """按模型名找 models/ 中的模型（兼容“模型@样品”与样品名被替换的情况）"""
    cands = [name, str(name).split("@")[0], str(name).split("[")[0]]
    for c in cands:
        f = paths.MODELS / f"{c}.json"
        if f.exists():
            try:
                return json.loads(f.read_text(encoding="utf-8-sig"))
            except Exception:
                logs.log.debug("si_text._model_json 出错（已忽略或已提示）", exc_info=True)
                pass
    if sample and paths.MODELS.exists():          # 模型名中的样品名被换掉了：找 name 中把 sample 换回模板样品的模型
        for f in paths.MODELS.glob("*.json"):
            try:
                m = json.loads(f.read_text(encoding="utf-8-sig"))
            except Exception:
                logs.log.debug("si_text._model_json 出错（已忽略或已提示）", exc_info=True)
                continue
            old = m.get("sample")
            if old and sample in name and name.replace(sample, old) in (f.stem, m.get("name")):
                return m
    return None


def _pval(params, name):
    v = params.get(name)
    return (None, None) if v is None else (v[0], v[1])


def _eval(expr, values):
    try:
        return float(eval(str(expr), {"__builtins__": {}}, {**_MATH, **values}))
    except Exception:
        logs.log.debug("si_text._eval 出错（已忽略或已提示）", exc_info=True)
        return None


def _prop_err(expr, params):
    """表达式的误差（各变量独立传递，忽略相关性）"""
    vals = {k: v[0] for k, v in params.items() if v and v[0] is not None}
    f0 = _eval(expr, vals)
    if f0 is None:
        return None
    s = 0.0
    used = False
    for k, (v, e) in params.items():
        if e and re.search(rf"\b{re.escape(k)}\b", str(expr)):
            f1 = _eval(expr, {**vals, k: v + e})
            if f1 is not None:
                s += (f1 - f0) ** 2
                used = True
    return math.sqrt(s) if used else None


def _spec(model, name):
    """模型参数的状态：('free'|'fixed'|'expr', value, expr)"""
    p = (model or {}).get("params", {}).get(name)
    if p is None:
        return None
    if isinstance(p, (int, float)):
        return ("free", p, None)
    if isinstance(p, str):
        return ("expr", None, p)
    if p.get("expr"):
        return ("expr", None, p["expr"])
    return ("free" if p.get("vary", True) else "fixed", p.get("value"), None)


def _model_paths(model, row=None):
    """该结果行对应的模型路径：旧格式 = model["paths"]；多数据集 = 行的 dataset 列（没有则按 sample）所指数据集的 paths。"""
    if not model:
        return []
    if "datasets" not in model:
        return model.get("paths", [])
    from .fit_exafs import dataset_of
    for col in ("dataset", "sample"):
        key = None if row is None else row.get(col)
        key = None if key is None or (isinstance(key, float) and key != key) else str(key)   # NaN / 数字 id
        if key:
            try:
                return dataset_of(model, key)["paths"]
            except (KeyError, ValueError):
                logs.log.debug("si_text._model_paths 找不到数据集", exc_info=True)
    return []


def _feff_desc(model):
    from .feff_wrap import feff_info
    from .fit_exafs import model_path_files
    files = model_path_files(model) if model else []
    if not files:
        return None, None
    d = (paths.ROOT / files[0]).parent
    code = "feff6"
    try:
        code = feff_info(d)["code"]
    except Exception:
        logs.log.debug("si_text._feff_desc 出错（已忽略或已提示）", exc_info=True)
        pass
    m = re.match(r"(.+?)_([A-Z][a-z]?)(K|L1|L2|L3|M\d)(_feff8)?$", d.parent.name)
    struct = m.group(1) if m else d.parent.name
    return code, struct


def _sample_info(sample):
    from . import pipeline as pl
    try:
        meta = pl.load_meta()
        r = meta[meta["sample"] == sample]
        if not len(r):
            return {}
        el, edge = str(r.iloc[0]["edge_key"]).split("_")
        return dict(edge=f"{el} {edge}", mode=str(r.iloc[0]["mode"]), scans=int((r["use"].astype(str) != "0").sum()))
    except Exception:
        logs.log.debug("si_text._sample_info 出错（已忽略或已提示）", exc_info=True)
        return {}


def _fmt(v, e=None, nd=3):
    if v is None or (isinstance(v, float) and not np.isfinite(v)):
        return "—"
    if e is None or not np.isfinite(e) or e == 0:
        return f"{v:.{nd}f}"
    return f"{v:.{nd}f}({int(round(e * 10 ** nd))})" if e * 10 ** nd < 100 else f"{v:.{nd}f} ± {e:.{nd}f}"


def table(keys=None):
    """SI 参数表：每行一条路径"""
    fits = load_fits()
    keys = keys or fit_keys(fits)
    rows = []
    for k in keys:
        s, mname = k.split("|", 1)
        g = fits[(fits["sample"] == s) & (fits["model"] == mname)]
        if not len(g):
            continue
        model = _model_json(mname, s)
        params = json.loads(g.iloc[0]["params"]) if isinstance(g.iloc[0]["params"], str) else {}
        for _, r in g.iterrows():
            mpaths = {p.get("label"): p for p in _model_paths(model, r)}
            mp = mpaths.get(r["path"]) or next((p for lab, p in mpaths.items() if lab and str(r["path"]).startswith(lab)), None)
            nerr = rerr = serr = None
            if mp:
                if not re.fullmatch(r"[\d.]+", str(mp.get("N", ""))) and mp.get("N"):
                    nerr = _prop_err(mp["N"], params)
                rerr = _prop_err(mp.get("deltar", "0"), params) if mp.get("deltar") else None
                serr = _prop_err(mp.get("sigma2", "0"), params) if mp.get("sigma2") else None
            e0, e0e = _pval(params, "e0")
            rows.append({"Sample": s, "Model": mname, "Path": str(r["path"]).replace("-", "–"),
                         "N": _fmt(r["N"], nerr, 1), "R (Å)": _fmt(r["R"], rerr, 3),
                         "σ² (Å²)": _fmt(r["sigma2"], serr, 4),
                         "ΔE0 (eV)": _fmt(r["dE0"], e0e if e0 is not None else None, 1),
                         "R-factor": f"{r['rfactor']:.4f}", "χ²ν": f"{r['chi2_reduced']:.1f}",
                         "N_idp / N_var": f"{r['n_idp']:.1f} / {int(r['nvarys'])}"})
    return pd.DataFrame(rows)


def _group_models(keys, fits):
    """按（基础模型）分组：同一模型用于多个样品时只描述一次"""
    groups = {}
    for k in keys:
        s, mname = k.split("|", 1)
        model = _model_json(mname, s)
        base = (model or {}).get("name") or mname.split("@")[0]
        groups.setdefault(base, dict(model=model, samples=[], rows=[]))
        groups[base]["samples"].append(s)
        groups[base]["rows"].append(fits[(fits["sample"] == s) & (fits["model"] == mname)].iloc[0])
    return groups


def _kw_txt(kw, en):
    ks = kw if isinstance(kw, (list, tuple)) else [kw]
    sup = str.maketrans("0123456789", "⁰¹²³⁴⁵⁶⁷⁸⁹")
    if en:
        return (", ".join(f"k{str(k).translate(sup)}" for k in ks) + ("-weighted χ(k) were fitted simultaneously"
                if len(ks) > 1 else "-weighted χ(k) was fitted"))
    return "、".join(f"k{str(k).translate(sup)}" for k in ks) + (" 加权的 χ(k) 同时拟合" if len(ks) > 1 else " 加权的 χ(k)")


def _path_txt(mp, model, en):
    lab = str(mp.get("label", "")).replace("-", "–")
    parts = []
    n = str(mp.get("N", ""))
    if not n:
        parts.append("N fixed at the crystallographic value" if en else "N 固定为晶体学值")
    elif re.fullmatch(r"[\d.]+", n):
        parts.append(f"N fixed at {n}" if en else f"N 固定为 {n}")
    elif n:
        sp = _spec(model, n)
        parts.append(f"N refined ({n})" if en and sp and sp[0] == "free" else
                     (f"N = {n}" if en else (f"N 精修（{n}）" if sp and sp[0] == "free" else f"N = {n}")))
    for key, sym in (("deltar", "ΔR"), ("sigma2", "σ²")):
        ex = mp.get(key)
        if not ex:
            continue
        sp = _spec(model, ex)
        if sp and sp[0] == "fixed":
            parts.append(f"{sym} fixed at {sp[1]:g}" if en else f"{sym} 固定为 {sp[1]:g}")
        elif sp and sp[0] == "free":
            parts.append(f"{sym} = {ex}")
        else:
            parts.append(f"{sym} = {ex}")
    return f"{lab} ({'; '.join(parts)})" if en else f"{lab}（{'；'.join(parts)}）"


def build(keys=None):
    """返回 dict(zh=文本, en=文本, table=DataFrame)"""
    from . import __version__
    from . import pipeline as pl
    fits = load_fits()
    keys = keys or fit_keys(fits)
    tab = table(keys)
    if not keys or not len(tab):
        return dict(zh="", en="", table=tab)
    cfg = pl.load_config() if hasattr(pl, "load_config") else json.loads(paths.CONFIG.read_text(encoding="utf-8-sig"))
    try:
        import larch
        lv = larch.__version__
    except Exception:
        logs.log.debug("si_text.build 出错（已忽略或已提示）", exc_info=True)
        lv = "?"
    zh, en = [], []
    for base, g in _group_models(keys, fits).items():
        model, r0 = g["model"], g["rows"][0]
        smp = list(dict.fromkeys(g["samples"]))
        info = _sample_info(smp[0])
        code, struct = _feff_desc(model)
        feff_en = "FEFF8L (self-consistent potentials)" if code == "feff8" else "FEFF6L"
        feff_zh = "FEFF8L（自洽势）" if code == "feff8" else "FEFF6L"
        kmin, kmax = str(r0["k_range"]).split("-", 1)
        rmin, rmax = str(r0["R_range"]).split("-", 1)
        kw = json.loads(r0["kweight"]) if str(r0["kweight"]).startswith("[") else r0["kweight"]
        win = (model or {}).get("window", "hanning").capitalize()
        dk = (model or {}).get("dk", 1)
        space = "R" if (model or {}).get("fitspace", "r") == "r" else "k"
        nidp = sorted({round(float(x["n_idp"]), 1) for x in g["rows"]})
        nvar = sorted({int(x["nvarys"]) for x in g["rows"]})
        rng = lambda v: f"{v[0]}" if len(v) == 1 else f"{v[0]}–{v[-1]}"
        # S0²
        s02 = _spec(model, "s02") if model else None
        edge_key = info.get("edge", "").replace(" ", "_")
        s0c = cfg.get("edges", {}).get(edge_key, {}).get("s02_recommended", {}) if edge_key else {}
        if s02 and s02[0] == "fixed":
            same = s0c.get("value") is not None and abs(float(s0c["value"]) - float(s02[1])) < 1e-6
            src = s0c.get("source") if same else None
            err = f" ± {s0c['err']}" if same and s0c.get("err") else ""
            src_en = src if src and not re.search(r"[一-鿿]", src) else None
            s0_en = (f"The amplitude reduction factor was fixed at S0² = {s02[1]:g}{err}"
                     + ((f", determined from a reference of known structure ({src_en})." if src_en else
                         ", determined from a reference of known structure.") if same else "."))
            s0_zh = f"振幅衰减因子固定为 S0² = {s02[1]:g}{err}" + (f"，由结构已知的标样拟合确定（{src}）。" if src else "。")
        else:
            s0_en, s0_zh = "S0² was refined.", "S0² 作为变量精修。"
        e0sp = _spec(model, "e0") if model else None
        e0_en = ("A single energy shift ΔE0 was refined for all paths." if e0sp and e0sp[0] == "free"
                 else (f"ΔE0 was fixed at {e0sp[1]:g} eV." if e0sp and e0sp[0] == "fixed" else ""))
        e0_zh = ("所有路径共用一个能量偏移 ΔE0 并精修。" if e0sp and e0sp[0] == "free"
                 else (f"ΔE0 固定为 {e0sp[1]:g} eV。" if e0sp and e0sp[0] == "fixed" else ""))
        ptxt_en = "; ".join(_path_txt(p, model, True) for p in _model_paths(model, r0))
        ptxt_zh = "；".join(_path_txt(p, model, False) for p in _model_paths(model, r0))
        data_en = (f"{info.get('edge', '')}-edge EXAFS of {', '.join(smp)}"
                   + (f" ({'transmission' if info.get('mode') == 'trans' else 'fluorescence'} mode)" if info.get("mode") else ""))
        data_zh = (f"{'、'.join(smp)} 的 {info.get('edge', '')} 边 EXAFS"
                   + (f"（{'透射' if info.get('mode') == 'trans' else '荧光'}）" if info.get("mode") else ""))
        en.append(
            f"{data_en} {'was' if len(smp) == 1 else 'were'} fitted in {space} space with feffit in Larch {lv} [Newville 2013], "
            f"using scattering paths calculated with {feff_en} from the crystal structure of {struct or '[structure]'}. "
            f"The {_kw_txt(kw, True)} over k = {kmin}–{kmax} Å⁻¹ ({win} window, dk = {dk} Å⁻¹) and R = {rmin}–{rmax} Å "
            f"(not phase-corrected). The number of independent points was {rng(nidp)} and the number of variables {rng(nvar)}. "
            f"{s0_en} {e0_en} "
            + (f"Paths included: {ptxt_en}. Parameters sharing a name were constrained to be equal. " if ptxt_en else "")
            + "Uncertainties were estimated from the covariance matrix scaled by the square root of the reduced χ²; "
              "uncertainties of constrained quantities were propagated from the refined variables. "
              "Fit results are listed in Table S[n].")
        zh.append(
            f"{data_zh}用 Larch {lv} 的 feffit 在 {space} 空间拟合 [Newville 2013]，散射路径由 {feff_zh} 根据 "
            f"{struct or '【结构】'} 晶体结构计算。{_kw_txt(kw, False)}，k = {kmin}–{kmax} Å⁻¹（{win} 窗，dk = {dk} Å⁻¹），"
            f"R = {rmin}–{rmax} Å（未相移校正）。独立点数 {rng(nidp)}，变量数 {rng(nvar)}。{s0_zh}{e0_zh}"
            + (f"包含的路径：{ptxt_zh}。同名参数约束为相等。" if ptxt_zh else "")
            + "参数误差由协方差矩阵得到并按约化 χ² 的平方根修正，受约束量的误差由精修变量传递。拟合结果见表 S[n]。")
    tail_en = (f"Data processing and fitting were performed with XAFSmith {__version__} "
               f"(https://github.com/Wiolic/XAFSmith); FEFF6 [Zabinsky 1995]"
               + (", FEFF8 [Ankudinov 1998]" if "FEFF8L" in " ".join(en) else "") + ".")
    tail_zh = (f"数据处理与拟合使用 XAFSmith {__version__}（https://github.com/Wiolic/XAFSmith）；FEFF6 [Zabinsky 1995]"
               + ("、FEFF8 [Ankudinov 1998]" if "FEFF8L" in " ".join(zh) else "") + "。")
    return dict(zh="\n\n".join(zh + [tail_zh]), en="\n\n".join(en + [tail_en]), table=tab)


def table_markdown(tab):
    if not len(tab):
        return ""
    cols = [c for c in tab.columns if c != "Model"]
    lines = ["| " + " | ".join(cols) + " |", "|" + "---|" * len(cols)]
    prev = None
    for _, r in tab.iterrows():
        cells = [str(r[c]) for c in cols]
        if r["Sample"] == prev:
            cells[0] = ""
            for i, c in enumerate(cols):
                if c in ("R-factor", "χ²ν", "N_idp / N_var"):
                    cells[i] = ""
        prev = r["Sample"]
        lines.append("| " + " | ".join(cells) + " |")
    return "\n".join(lines)


def table_tsv(tab):
    """制表符分隔：粘贴到 Excel 直接成表；Word 中“文本转换成表格”"""
    if not len(tab):
        return ""
    cols = [c for c in tab.columns if c != "Model"]
    return "\n".join(["\t".join(cols)] + ["\t".join(str(r[c]) for c in cols) for _, r in tab.iterrows()])


def save(keys=None, out_dir=None):
    r = build(keys)
    d = Path(out_dir or paths.REPORTS)
    d.mkdir(parents=True, exist_ok=True)
    p = d / "SI_EXAFS拟合方法.md"
    p.write_text("# EXAFS fitting (Supporting Information)\n\n" + r["en"] + "\n\n" + table_markdown(r["table"])
                 + "\n\n---\n\n# EXAFS 拟合（补充材料）\n\n" + r["zh"] + "\n", encoding="utf-8")
    r["table"].to_csv(d / "SI_EXAFS拟合参数表.csv", index=False, encoding="utf-8-sig")
    return p, r
