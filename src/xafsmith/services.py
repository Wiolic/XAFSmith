"""单一业务层：CLI 与 GUI 共用的“运行模型 / 保存拟合 / 稳健性 / 模型比较 / LCF / XANES / QC / 校准落盘”。

无 Qt、无 print：只做计算与落盘，返回写了哪些文件（调用方负责打印或提示）。
每种保存都写 params.json（可追溯性，见《数据标准》）。
"""
from __future__ import annotations

import datetime
import json
import re

from xafsmith import paths, pipeline as pl

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


# ----------------------------------------------------------------------------- 读 / 运行模型
def load_model(name_or_file, sample=None) -> dict:
    """读模型 json（`paths.model_file`：给路径用路径，只给名字在 models/ 中找，带不带 .json 都行）。
    多数据集模型原样返回；旧格式模型给了 sample 就换样品（名字里的旧样品名同步替换）。"""
    f = paths.model_file(name_or_file)
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
