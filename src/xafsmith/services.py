"""单一业务层：CLI 与 GUI 共用的“运行模型 / 保存拟合 / 稳健性 / 模型比较 / LCF / XANES / QC / 校准落盘”。

无 Qt、无 print：只做计算与落盘，返回写了哪些文件（调用方负责打印或提示）。
每种保存都写 params.json（可追溯性，见《数据标准》）。
"""
from __future__ import annotations

import datetime
import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, cast

from xafsmith import logs, paths, pipeline as pl
from xafsmith.common import write_params, write_text_atomic
from xafsmith.typedefs import FitRecord, ModelDict

safe = pl.safe                                   # 文件名清洗唯一规则（连续非法字符合成一个 “_”，去首尾 “_”）


def fit_base_candidates(name) -> list[str]:
    """按模型名找已存在文件时的候选文件名主干：先 `pipeline.safe`，再旧 GUI 规则（逐字符替换）。"""
    out = [safe(name), re.sub(r"[^A-Za-z0-9_.-]", "_", str(name))]
    return list(dict.fromkeys(out))


def now() -> str:
    return datetime.datetime.now().strftime("%H:%M:%S")


class plain_rc:
    """导出文件用 matplotlib 默认样式（不带界面主题色），结束后恢复界面样式"""
    def __enter__(self):
        import matplotlib
        self._ctx = matplotlib.rc_context()
        self._ctx.__enter__()
        matplotlib.rcdefaults()
        return self

    def __exit__(self, *a):
        self._ctx.__exit__(*a)


# ----------------------------------------------------------------------------- 精细拟合页：模型字典拼装（纯函数）
PARAM_TABLE_COLS = ["name", "value", "vary", "min", "max", "expr"]


def default_param_row(name: str) -> dict[str, Any]:
    """参数表里新参数（旧表里没有的名字）的默认行：按名字取 `defaults.FIT_PARAM_DEFAULTS`（thD/thE → ss0_ → ss → dr → 其他）。"""
    from xafsmith.defaults import FIT_PARAM_DEFAULTS as D
    v, vary, lo, hi = D["exact"].get(name) or (
        D["theta"] if name.startswith(("thD", "thE")) else
        D["ss0"] if name.startswith("ss0_") else
        D["ss"] if name.startswith("ss") else
        D["dr"] if name.startswith("dr") else D["other"])
    return dict(name=name, value=v, vary=vary, min=lo, max=hi, expr="")


def params_from_table(df) -> dict:
    """参数表 DataFrame → 模型 `params`：expr 非空 → {"expr"}；否则 value / vary / min / max（NaN → None）。"""
    import pandas as pd
    params: dict[str, Any] = {}
    for _, r in df.iterrows():
        if isinstance(r.expr, str) and r.expr.strip():
            params[r["name"]] = {"expr": r.expr}
        else:
            params[r["name"]] = {"value": float(r.value), "vary": bool(r.vary),
                                 "min": None if pd.isna(r["min"]) else float(r["min"]),
                                 "max": None if pd.isna(r["max"]) else float(r["max"])}
    return params


def paths_from_table(used) -> list[dict]:
    """已勾选的路径表行 → 模型 `paths`：N 非空才写；third / note 非空才写（note 去首尾空白，只是说明、计算忽略）。"""
    out = []
    for _, r in used.iterrows():
        d = dict(file=r.file, label=r.label, s02=r.s02, e0=r.e0, deltar=r.deltar, sigma2=r.sigma2)
        if str(r.N).strip():
            d["N"] = str(r.N)
        if isinstance(r.third, str) and r.third.strip():
            d["third"] = r.third
        if isinstance(r.note, str) and r.note.strip():
            d["note"] = r.note.strip()
        out.append(d)
    return out


def build_fit_model(*, name, rng, params, norm, bkg, restraints=None, datasets=None,
                    sample=None, paths=None, temperature=None) -> ModelDict:
    """拼模型字典（键的插入顺序即保存的 json 的键顺序，逐字节同旧界面代码）。
    rng：拟合范围状态 {kmin, kmax, dk, win, kws, rmin, rmax, space}；
    多数据集给 datasets = [{id, sample, over: {覆盖范围}, temperature: 可选, paths}]；单数据集给 sample / paths / temperature。
    restraints 为空 → 不写 restraints 键。"""
    r = dict(kmin=rng["kmin"], kmax=rng["kmax"], dk=rng["dk"], window=rng["win"], kweight=rng["kws"] or [2],
             rmin=rng["rmin"], rmax=rng["rmax"], fitspace=rng["space"])
    extra = dict(restraints=restraints) if restraints else {}
    if datasets is not None:
        dsl = []
        for ds in datasets:
            d = dict(id=ds["id"], sample=ds["sample"])
            d.update(ds.get("over") or {})
            if ds.get("temperature") is not None:
                d["temperature"] = ds["temperature"]
            d["paths"] = ds["paths"]
            dsl.append(d)
        return cast(ModelDict, dict(name=name, params=params, **r, datasets=dsl, norm=dict(norm), bkg=dict(bkg), **extra))
    model: dict[str, Any] = dict(name=name, sample=sample, **r, params=params, paths=paths, norm=dict(norm), bkg=dict(bkg), **extra)
    if temperature is not None:
        model["temperature"] = temperature
    return cast(ModelDict, model)


# ----------------------------------------------------------------------------- 读 / 运行模型
def load_model(name_or_file, sample=None) -> ModelDict:
    """读模型 json：只给名字（带不带 .json 都行）且 models/ 中有就用它，否则 `paths.model_file`（给路径用路径）。
    多数据集模型原样返回；旧格式模型给了 sample 就换样品（名字里的旧样品名同步替换）。"""
    s = str(name_or_file)
    q = paths.MODELS / (s if s.endswith(".json") else f"{s}.json")
    # 只给名字（界面列表里的 models/ 文件名）时先取 models/：避免项目根同名 json（如 xafsmith.json）被当成模型
    f = q if ("/" not in s and "\\" not in s and q.exists()) else paths.model_file(name_or_file)
    m = json.loads(f.read_text(encoding="utf-8-sig"))
    m.setdefault("name", f.stem)
    if "datasets" in m:            # 多数据集：样品由模型内 datasets 决定，不替换
        return m
    old = m.get("sample")
    if sample and sample != old:
        m["sample"] = sample
        m["name"] = m["name"].replace(old, sample) if old and old in m["name"] else f"{m['name']}@{sample}"
    return m


def resolve_groups(model, fallback=None):
    """模型的数据：旧格式 → Group；多数据集 → {数据集 id: Group}。
    先按项目配置建（与命令行一致），建不出来（谱没有登记）再取 fallback（{谱名: Group}，界面传会话里已载入的谱）。"""
    from xafsmith import fit_exafs as xfit
    if xfit.is_multi(model):
        nm = xfit.normalize_model(model)
        try:
            return pl.build_model_groups(model)
        except KeyError:
            fb = fallback or {}
            if [d["sample"] for d in nm["datasets"] if d["sample"] not in fb]:
                raise
            return {d["id"]: fb[d["sample"]] for d in nm["datasets"]}
    if not model.get("sample"):
        raise KeyError("模型文件中没有 sample，请选择样品 / the model file has no sample; choose one")
    try:
        return pl.build_sample(model["sample"])[0]
    except KeyError:
        if fallback is None:
            raise
        return fallback[model["sample"]]


def run_model(model, groups=None, fallback=None) -> dict:
    """运行一个模型（dict），返回拟合记录（不保存文件）：model / summ / result / curves / report / time（多数据集另有 multi）。
    groups：旧格式给 Group、多数据集给 {数据集 id: Group}；不给则 `resolve_groups`。"""
    from xafsmith import fit_exafs as xfit
    if groups is None:
        groups = resolve_groups(model, fallback)
    if xfit.is_multi(model):
        nm = xfit.normalize_model(model)
        res, dsets, summ = xfit.fit_multi(groups, model)
        return dict(model=model, summ=summ, result=res, curves=xfit.model_curves_all(dsets, nm),
                    report=xfit.report_text(res), time=now(), multi=True)
    res, dset, summ = xfit.run_fit(groups, model)
    return dict(model=model, summ=summ, result=res, curves=xfit.model_curves(dset),
                report=xfit.report_text(res), time=now())


# ----------------------------------------------------------------------------- 保存拟合
@dataclass
class SaveResult:
    """一次保存写出了什么：base 为文件名主干；files 为写出的文件（绝对路径，含趋势 CSV）；trend 为趋势 CSV 或 None。"""
    base: str
    files: list = field(default_factory=list)
    trend: Path | None = None


def _last_kw(kw):
    return kw[-1] if isinstance(kw, list) else kw


def save_fit(fit, tool, *, write_model=True, trend=True) -> SaveResult:
    """保存一个拟合记录（唯一实现）：结果表一行（多数据集每条路径一行）、models/<base>.json（write_model）、
    fits/<base>.fit_report.txt、拟合图（单数据集 <base>_fit.png；多数据集每个数据集一张 <base>_<id>_fit.png）、
    fits/<base>.params.json，多数据集且 ≥ 2 个数据集时另写趋势表（失败只记日志）。"""
    from xafsmith import fit_exafs as xfit, report as xrep
    summ, md = fit["summ"], fit["model"]
    base = safe(summ["model"])
    out = SaveResult(base)
    for d in (paths.FITS, paths.FIGS) + ((paths.MODELS,) if write_model else ()):
        d.mkdir(parents=True, exist_ok=True)
    xfit.write_result_row(summ, paths.FITS_CSV)
    out.files.append(paths.FITS_CSV)
    if write_model:
        f = paths.MODELS / f"{base}.json"
        write_text_atomic(f, json.dumps(md, ensure_ascii=False, indent=2))
        out.files.append(f)
    f = paths.FITS / f"{base}.fit_report.txt"
    f.write_text(fit["report"], encoding="utf-8")
    out.files.append(f)
    with plain_rc():
        if summ.get("multi"):
            for d in xfit.normalize_model(md)["datasets"]:
                f = paths.FIGS / f"{base}_{safe(d['id'])}_fit.png"
                xrep.plot_fit(fit["curves"][d["id"]], xfit.dataset_view(summ, d["id"]), kweight=_last_kw(d["kweight"]), out=f)
                out.files.append(f)
        else:
            f = paths.FIGS / f"{base}_fit.png"
            xrep.plot_fit(fit["curves"], summ, kweight=_last_kw(md["kweight"]), out=f)
            out.files.append(f)
    out.files.append(write_params(paths.FITS / f"{base}.params.json", md, tool))
    if trend and summ.get("multi") and len(summ["datasets"]) >= 2:      # C2：联合拟合顺带写趋势表（失败不影响已保存的结果）
        try:
            from xafsmith import trend as xtr
            meta, proc = xtr.load_project_tables()
            out.trend = xtr.save_trend(xtr.ordered(xtr.trend_table(summ, md, meta, proc), fit.get("trend_order")),
                                       base, summ["model"], tool)
            out.files += [out.trend, out.trend.with_name(f"{base}_trend.params.json")]
        except Exception:      # noqa: BLE001
            logs.log.warning("services.save_fit：趋势表未保存（已忽略）", exc_info=True)
    return out


# ----------------------------------------------------------------------------- 稳健性 / 模型比较
def save_robustness(fit: FitRecord, tab, ver, tool) -> list[Path]:
    """稳健性检查结果 → fits/<base>_robustness.csv、<base>_robustness_summary.csv 与 <base>_robustness.params.json
    （params = 模型 dict）。fit 是拟合记录（取 fit["summ"]["model"] 与 fit["model"]）；返回写出的三个文件。"""
    base = safe(fit["summ"]["model"])
    paths.FITS.mkdir(parents=True, exist_ok=True)
    f1, f2 = paths.FITS / f"{base}_robustness.csv", paths.FITS / f"{base}_robustness_summary.csv"
    tab.to_csv(f1, index=False, encoding="utf-8-sig")
    ver.to_csv(f2, index=False, encoding="utf-8-sig")
    f3 = write_params(paths.FITS / f"{base}_robustness.params.json", fit["model"], tool)
    return [f1, f2, f3]


def save_compare(df, models, tool, out=None) -> Path:
    """模型比较表 → CSV（缺省 fits/model_compare.csv）与同名 .params.json（params = {"models": 模型名列表}）。"""
    out = Path(out) if out else paths.FITS / "model_compare.csv"
    out.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(out, index=False, encoding="utf-8-sig")
    write_params(out.with_suffix(".params.json"), {"models": list(models)}, tool)
    return out


# ----------------------------------------------------------------------------- LCF
def save_lcf(r, *, sample, standards, kwargs, note, tool, figure=True) -> list[Path]:
    """LCF 结果：追加一行到 lcf/lcf_results.csv；figure 为真时另写 figs/lcf_<safe(样品)>.png；
    lcf/lcf_<safe(样品)>.params.json 记录样品、标样、全部 lcf 关键字参数（kwargs 之外取 `fit_lcf.lcf` 的缺省值）与备注。"""
    import inspect

    import pandas as pd

    from xafsmith import fit_lcf as xlcf, report as xrep
    from xafsmith.common import append_csv
    base = safe(sample)
    for d in (paths.LCF, paths.FIGS):
        d.mkdir(parents=True, exist_ok=True)
    append_csv(pd.DataFrame([xlcf.result_row(r, note)]), paths.LCF_CSV)
    files = [paths.LCF_CSV]
    if figure:
        f = paths.FIGS / f"lcf_{base}.png"
        with plain_rc():
            xrep.plot_lcf(r, out=f)
        files.append(f)
    eff = {k: v.default for k, v in inspect.signature(xlcf.lcf).parameters.items()
           if k not in ("sample", "standards") and v.default is not inspect.Parameter.empty}
    eff.update(kwargs)
    files.append(write_params(paths.LCF / f"lcf_{base}.params.json",
                              dict(sample=sample, standards=list(standards), **eff, note=note), tool))
    return files


# ----------------------------------------------------------------------------- XANES 特征表
def save_xanes(tab, *, wl_window, tool) -> Path:
    """XANES 特征表 → xanes/xanes_features.csv，按样品合并：新表里出现的样品替换旧行，其余旧行保留（旧行在前、新行在后）。
    xanes_features.params.json 的 params = {"samples": {样品: {wl_window, tool, time}}}，读旧的再按样品更新。"""
    import pandas as pd
    out = paths.XANES_CSV
    out.parent.mkdir(parents=True, exist_ok=True)
    old = pd.read_csv(out, encoding="utf-8-sig", dtype={"sample": str}) if out.exists() else None   # 样品名按字符串比（“50”不读成 50）
    new = tab if old is None else pd.concat([old[~old["sample"].isin(tab["sample"].astype(str))], tab])
    new.to_csv(out, index=False, encoding="utf-8-sig")
    pf = out.with_suffix(".params.json")
    samples = {}
    if pf.exists():
        try:
            samples = dict(json.loads(pf.read_text(encoding="utf-8-sig"))["params"]["samples"])
        except Exception:      # noqa: BLE001
            logs.log.warning("services.save_xanes：旧 params.json 无法读取，从空开始：%s", pf, exc_info=True)
            samples = {}
    stamp = datetime.datetime.now().isoformat(timespec="seconds")
    for s in tab["sample"]:
        samples[str(s)] = dict(wl_window=wl_window, tool=tool, time=stamp)
    write_params(pf, {"samples": samples}, tool)
    return out


# ----------------------------------------------------------------------------- QC 表 / 校准记录
def merge_scans(groups, *, label, reject=None, tol_sigma=4.0, tool="gui:normalize"):
    """合并多条扫描（`normalize.merge_scans`）并把报告写到 `paths.GUI / merge_<safe(label)>.csv`（utf-8-sig，无索引列）。
    返回 (合并后的 group, 报告 DataFrame, csv 路径)。tool 只记入日志（合并报告历来没有 params.json，不新增文件）。"""
    import pandas as pd
    from xafsmith import normalize as xnorm
    m, rep = xnorm.merge_scans(groups, label=label, reject=reject, tol_sigma=tol_sigma)
    df = pd.DataFrame(rep)
    out = paths.GUI / f"merge_{safe(label)}.csv"
    df.to_csv(out, index=False, encoding="utf-8-sig")
    logs.log.info("merge_scans（%s）：%d 条 → %s（%d 条被采用）", tool, len(groups), label, getattr(m, "nscans", 0))
    return m, df, out


def save_qc(df, *, norm_params, tool) -> Path:
    """QC 表 → qc/qc_report.csv，与 qc_report.params.json（params = 所用归一化参数）。"""
    paths.QC.mkdir(parents=True, exist_ok=True)
    df.to_csv(paths.QC_CSV, index=False, encoding="utf-8-sig")
    write_params(paths.QC_CSV.with_suffix(".params.json"), {"norm": norm_params}, tool)
    return paths.QC_CSV


def save_calib(calib, *, tool, params, path=None) -> Path:
    """校准记录 → calib/calib.json（path 缺省），与 calib.params.json（params 由调用方给：参比与所用配置）。"""
    from xafsmith import calib as xcal
    path = Path(path) if path else paths.CALIB_JSON
    xcal.save_calib(calib, path)
    write_params(path.with_suffix(".params.json"), params, tool)
    return path
