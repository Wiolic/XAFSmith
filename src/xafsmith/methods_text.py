"""methods_text —— 根据项目中实际使用的参数，自动生成论文“实验方法 / XAFS 数据分析”段落（中文 + 英文）。

只写项目文件里有记录的事实：xafsmith.json（处理参数、S0² 及来源、表值来源）、output/calib/calib.json
（参比与 ΔE）、data/meta.csv（测量模式、扫描数）、output/fits/exafs_fits.csv（拟合范围、k 权重、N_idp、
变量数）、output/lcf/lcf_results.csv、output/xanes/。光源、线站、单色器、探测器等项目中没有的信息，
从 xafsmith.json 的 "instrument" 读取；没有填写时用【方括号占位】，提醒使用者补全。
生成的段落是草稿：投稿前务必逐句核对。
"""
from xafsmith import logs
import json

import numpy as np
import pandas as pd

from . import paths

INSTRUMENT_KEYS = {
    "facility": ("光源", "facility"),
    "beamline": ("线站", "beamline"),
    "monochromator": ("单色器", "monochromator"),
    "detection": ("探测方式 / 探测器", "detectors"),
}


def _versions():
    out = {}
    for mod in ("larch", "xraydb", "lmfit"):
        try:
            out[mod] = __import__(mod).__version__
        except Exception:
            logs.log.debug("methods_text._versions 出错（已忽略或已提示）", exc_info=True)
            out[mod] = "?"
    from . import __version__
    out["xafsmith"] = __version__
    return out


def _fmt_list(xs, sep="、"):
    xs = [str(x) for x in xs if str(x)]
    return sep.join(dict.fromkeys(xs))


SUP = str.maketrans("0123456789", "⁰¹²³⁴⁵⁶⁷⁸⁹")


def _dash(s):
    return str(s).replace("-", "–")


def _rng(vals, nd=1):
    v = sorted(set(round(float(x), nd) for x in vals if pd.notna(x)))
    if not v:
        return ""
    return f"{v[0]:g}" if len(v) == 1 else f"{v[0]:g}–{v[-1]:g}"


def collect(samples=None):
    """收集生成段落所需的事实；samples=None 表示 meta.csv 中 use≠0 的全部样品"""
    from .pipeline import load_meta
    cfg = json.loads(paths.CONFIG.read_text(encoding="utf-8-sig")) if paths.CONFIG.exists() else {}
    meta = load_meta() if paths.META.exists() else pd.DataFrame(columns=["sample", "edge_key", "mode", "use"])
    meta = meta[meta["use"].astype(str) != "0"]
    if samples:
        meta = meta[meta["sample"].isin(samples)]
    cal = json.loads(paths.CALIB_JSON.read_text(encoding="utf-8-sig")) if paths.CALIB_JSON.exists() else {}
    fits = pd.read_csv(paths.FITS_CSV, encoding="utf-8-sig") if paths.FITS_CSV.exists() else pd.DataFrame()
    if len(fits) and samples:
        fits = fits[fits["sample"].isin(samples)]
    lcf = pd.read_csv(paths.LCF_CSV, encoding="utf-8-sig") if paths.LCF_CSV.exists() else pd.DataFrame()
    if len(lcf) and samples and "sample" in lcf:
        lcf = lcf[lcf["sample"].isin(samples)]
    xanes = paths.XANES_CSV.exists() if hasattr(paths, "XANES_CSV") else False
    edges = []
    for ek, g in meta.groupby("edge_key", sort=False):
        c = cfg.get("edges", {}).get(ek, {})
        refs = [v for v in cal.values() if v.get("edge_key") == ek]
        nscan = g.groupby("sample").size()
        edges.append(dict(
            key=ek, element=c.get("element", ek.split("_")[0]), edge=c.get("edge", ek.split("_")[-1]),
            modes=sorted(set(g["mode"])), n_samples=g["sample"].nunique(),
            scans=f"{nscan.min()}–{nscan.max()}" if nscan.min() != nscan.max() else str(nscan.min()),
            e_table=c.get("e_table"), e_table_source=c.get("e_table_source", "xraydb"),
            refs=sorted(set(r.get("reference", "") for r in refs)),
            dE=_rng([r["delta_e"] for r in refs], 2), norm=c.get("norm", {}), bkg=c.get("bkg", {}),
            ft=c.get("ft", {}), s02=c.get("s02_recommended", {})))
    fit_rows = []
    roles = dict(zip(meta["sample"], meta["role"])) if "role" in meta else {}
    if len(fits):
        for (s, m), g in fits.groupby(["sample", "model"], sort=False):
            r = g.iloc[-1]
            fit_rows.append(dict(sample=s, model=m, k=r["k_range"], R=r["R_range"], kw=r["kweight"],
                                 nidp=r["n_idp"], nvarys=r["nvarys"], rfactor=r["rfactor"], S02=r.get("S02"),
                                 role=roles.get(s, ""), feff=_feff_code(m)))
    return dict(cfg=cfg, instrument=cfg.get("instrument", {}), edges=edges, fits=pd.DataFrame(fit_rows),
                lcf=lcf, xanes=xanes, versions=_versions())


def _inst(info, key, lang):
    v = str(info.get(key, "") or "").strip()
    if v:
        return v
    zh, en = INSTRUMENT_KEYS[key]
    return f"【{zh}】" if lang == "zh" else f"[{en}]"


def _mode_txt(modes, lang):
    m = {"trans": ("透射", "transmission"), "fluo": ("荧光", "fluorescence"), "mu": ("μ(E)", "μ(E)")}
    return _fmt_list([m.get(x, (x, x))[0 if lang == "zh" else 1] for x in modes], "、" if lang == "zh" else " and ")


def _feff_code(model_name):
    """由 models/<模型>.json 的路径目录判断 FEFF 版本（feff6 / feff8）；找不到模型时返回 feff6。"""
    import json
    from .feff_wrap import feff_info
    name = str(model_name).split("@")[0].split("[")[0]
    f = paths.MODELS / f"{name}.json"
    try:
        m = json.loads(f.read_text(encoding="utf-8-sig"))
        d = (paths.ROOT / m["paths"][0]["file"]).parent
        return feff_info(d)["code"]
    except Exception:
        logs.log.debug("methods_text._feff_code 出错（已忽略或已提示）", exc_info=True)
        return "feff6"


def build(samples=None):
    """返回 dict(zh=中文段落, en=英文段落, facts=收集到的事实)"""
    f = collect(samples)
    v, ins = f["versions"], f["instrument"]
    zh, en = [], []
    edges = f["edges"]
    if not edges:
        return dict(zh="（项目中还没有登记的数据）", en="(No registered data in the project.)", facts=f)
    e_zh = _fmt_list([f"{e['element']} {e['edge']} 边（{_mode_txt(e['modes'], 'zh')}模式）" for e in edges])
    e_en = "; ".join(f"{e['element']} {e['edge']}-edge ({_mode_txt(e['modes'], 'en')} mode)" for e in edges)
    zh.append(f"X 射线吸收谱（XAS）在{_inst(ins, 'facility', 'zh')}的{_inst(ins, 'beamline', 'zh')}线站采集，"
              f"使用{_inst(ins, 'monochromator', 'zh')}单色器，{_inst(ins, 'detection', 'zh')}，"
              f"测量了{e_zh}。")
    en.append(f"X-ray absorption spectra were collected at beamline {_inst(ins, 'beamline', 'en')} of "
              f"{_inst(ins, 'facility', 'en')} using a {_inst(ins, 'monochromator', 'en')} monochromator "
              f"({_inst(ins, 'detection', 'en')}) at the {e_en}.")
    for e in edges:
        refs = _fmt_list(e["refs"])
        n, b, t = e["norm"], e["bkg"], e["ft"]
        n2 = n.get("norm2")
        n2z = f"距数据末端 {abs(n2):g} eV" if (n2 or 0) <= 0 else f"E0+{n2:g} eV"
        n2e = f"{abs(n2):g} eV below the end of the data" if (n2 or 0) <= 0 else f"E0+{n2:g} eV"
        zh.append(
            f"{e['element']} {e['edge']} 边：每条谱的能量用同一批次同时测量的单质参比（{refs or '【参比】'}）校准，"
            f"取参比归一化谱一阶导数最大值并对齐到表值 {e['e_table']} eV（{e['e_table_source']}），"
            f"同一参比下所有谱平移同一 ΔE（{e['dE']} eV）。"
            + (f"每个样品合并 {e['scans']} 次扫描。" if e["scans"] != "1" else "每个样品 1 次扫描。")
            + 
            f"E0 取平滑后一阶导数最大值；边前直线拟合范围 E0{n.get('pre1', -150):+g} 至 E0{n.get('pre2', -30):+g} eV，"
            f"边后 {n.get('nnorm', 2)} 次多项式拟合范围 E0+{n.get('norm1', 100):g} eV 至{n2z}。"
            f"背景用 AUTOBK 算法扣除（Rbkg = {b.get('rbkg', 1.0)} Å，k 权重 {b.get('kweight', 2)}）。"
            f"k{str(t.get('kweight', 2)).translate(SUP)} 加权的 χ(k) 在 k = {t.get('kmin', 3)}–{t.get('kmax', 12)} Å⁻¹ 范围内用 "
            f"{str(t.get('window', 'hanning')).capitalize()} 窗（dk = {t.get('dk', 1)} Å⁻¹）做傅里叶变换；文中 R 空间谱均未做相移校正。")
        en.append(
            f"For the {e['element']} {e['edge']}-edge, the energy of every spectrum was calibrated with the "
            f"elemental reference measured in the same session ({refs or '[reference]'}): the maximum of the first "
            f"derivative of the reference was aligned to the tabulated value of {e['e_table']} eV "
            f"({e['e_table_source']}), and the same shift ({e['dE']} eV) was applied to all spectra measured with "
            f"that reference. " + (f"{_dash(e['scans'])} scans were merged per sample. " if e["scans"] != "1"
                                  else "One scan was used per sample. ") + "E0 was taken as the maximum of the "
            f"smoothed first derivative. Spectra were normalized with a linear pre-edge line "
            f"(E0{n.get('pre1', -150):+g} to E0{n.get('pre2', -30):+g} eV) and a polynomial of order "
            f"{n.get('nnorm', 2)} for the post-edge (E0+{n.get('norm1', 100):g} eV to {n2e}). The background was "
            f"removed with the AUTOBK algorithm (Rbkg = {b.get('rbkg', 1.0)} Å, k-weight {b.get('kweight', 2)}). "
            f"The k{str(t.get('kweight', 2)).translate(SUP)}-weighted χ(k) was Fourier transformed over k = {t.get('kmin', 3)}–"
            f"{t.get('kmax', 12)} Å⁻¹ with a {str(t.get('window', 'hanning')).capitalize()} window (dk = {t.get('dk', 1)} Å⁻¹); "
            f"R-space data are shown without phase correction.")
    fits = f["fits"]
    uses = set(fits["feff"]) if len(fits) and "feff" in fits else set()
    if len(fits):
        kr_zh, rr_zh = _fmt_list(map(_dash, fits["k"])), _fmt_list(map(_dash, fits["R"]))
        kr_en, rr_en = _fmt_list(map(_dash, fits["k"]), ", "), _fmt_list(map(_dash, fits["R"]), ", ")
        kw = _fmt_list(fits["kw"], "; ")
        over = fits[fits["nvarys"] > fits["nidp"] / 2]
        if uses == {"feff8"}:
            feff_zh, feff_en = "FEFF8L（自洽势）", "FEFF8L (self-consistent potentials)"
        elif "feff8" in uses:
            feff_zh = "FEFF6L 与 FEFF8L（自洽势）"
            feff_en = "FEFF6L and FEFF8L (self-consistent potentials)"
        else:
            feff_zh, feff_en = "FEFF6L", "FEFF6L"
        zh.append(
            f"EXAFS 拟合用 {feff_zh}（xraylarch {v['larch']} 自带）由晶体结构计算散射路径，在 Larch 的 feffit 中进行"
            f"（k 范围 {kr_zh} Å⁻¹，R 范围 {rr_zh} Å，k 权重 {kw}）。独立点数 N_idp = 2ΔkΔR/π 为 "
            f"{_rng(fits['nidp'])}，变量数为 {_rng(fits['nvarys'], 0)}"
            + ("，均不超过 N_idp/2。" if not len(over) else f"；其中 {len(over)} 个拟合的变量数超过 N_idp/2"
               f"（{_fmt_list(over['model'])}），解释时需谨慎。"))
        en.append(
            f"Scattering paths were calculated from crystal structures with {feff_en} (as distributed with xraylarch "
            f"{v['larch']}), and EXAFS fits were performed with feffit in Larch (k = {kr_en} Å⁻¹, R = {rr_en} Å, "
            f"k-weights {kw}). The number of independent points, N_idp = 2ΔkΔR/π, was {_dash(_rng(fits['nidp']))} "
            f"and the number of variables was {_dash(_rng(fits['nvarys'], 0))}"
            + (", always below N_idp/2." if not len(over) else
               f"; {len(over)} fit(s) exceeded N_idp/2 ({_fmt_list(over['model'], ', ')}) and should be "
               f"interpreted with caution."))
        for e in edges:
            s0 = e["s02"].get("value")
            if s0 is None:
                continue
            err = f" ± {e['s02']['err']}" if e["s02"].get("err") is not None else ""
            smp = fits[(fits["role"] == "sample")]
            fixed = len(smp) and np.allclose(pd.to_numeric(smp["S02"], errors="coerce"), float(s0), atol=1e-6)
            zh.append(f"{e['element']} {e['edge']} 边的 S0² 由结构已知的标样拟合得到：{s0}{err}"
                      f"（{e['s02'].get('source', '')}）" + ("，样品拟合中固定为该值。" if fixed else "。"))
            en.append(f"The amplitude reduction factor for the {e['element']} {e['edge']}-edge, S0² = {s0}{err}, was "
                      f"obtained from a reference compound of known structure"
                      + (" and fixed in the sample fits." if fixed else "."))
        zh.append("参数误差由协方差矩阵得到（已按约化 χ² 修正）。")
        en.append("Uncertainties were estimated from the covariance matrix scaled by the reduced χ².")
    lcf = f["lcf"]
    if len(lcf):
        zh.append("XANES 线性组合拟合（LCF）以实测标样为端点，在归一化谱上进行，并与单一标样拟合比较 R 因子。")
        en.append("Linear combination fitting (LCF) of the XANES was performed on normalized spectra using measured "
                  "reference compounds as end members and compared with single-component fits.")
    if f["xanes"]:
        zh.append("边位置取归一化 μ = 0.5 处的能量（半高点）及一阶导数最大值；白线面积为 E0 至 E0+30 eV 内"
                  "归一化 μ 超过 1 部分的积分。")
        en.append("Edge positions were taken at half of the edge step and at the maximum of the first derivative; "
                  "the white-line area was integrated above unity between E0 and E0+30 eV.")
    zh.append(f"数据处理与拟合使用 XAFSmith {v['xafsmith']}（https://github.com/Wiolic/XAFSmith），"
              f"基于 Larch {v['larch']}[Newville 2013]、xraydb {v['xraydb']} 与 FEFF6[Zabinsky 1995]"
              + ("、FEFF8[Ankudinov 1998]" if "feff8" in uses else "") + "。")
    en.append(f"Data were processed and fitted with XAFSmith {v['xafsmith']} (https://github.com/Wiolic/XAFSmith), "
              f"built on Larch {v['larch']} [Newville 2013], xraydb {v['xraydb']} and FEFF6 [Zabinsky 1995]"
              + (" and FEFF8 [Ankudinov 1998]" if "feff8" in uses else "") + ".")
    return dict(zh="".join(zh), en=" ".join(en), facts=f)


def save(samples=None, out_dir=None):
    r = build(samples)
    d = out_dir or paths.REPORTS
    d.mkdir(parents=True, exist_ok=True)
    p = d / "方法段落.md"
    from . import about
    p.write_text("# XAFS 方法段落（自动生成草稿，投稿前逐句核对）\n\n## 中文\n\n" + r["zh"] + "\n\n## English\n\n"
                 + r["en"] + "\n\n## 参考文献 / References\n\n" + "\n".join(f"- {u}" for u in about.UPSTREAM)
                 + f"\n- {about.CITATION_TEXT}\n", encoding="utf-8")
    return p, r
