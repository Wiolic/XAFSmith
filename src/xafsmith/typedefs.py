"""typedefs —— 配置、模型、拟合摘要等字典的类型声明（只有 TypedDict 与类型别名，零运行时行为；mypy 用）。

键名取自 `schema.py`、`modelcheck.py`、`defaults.py`、`fit_exafs.py` 与《数据标准》；值类型拿不准的写 Any。
所有 TypedDict 都是 `total=False`：磁盘上的 JSON 是否带某个键由数据标准与 `validate` 管，这里只描述“可能有哪些键”。
Type declarations for the dict shapes (config, model, fit summary). Only TypedDicts and aliases — no runtime behaviour.
"""
from __future__ import annotations

from typing import Any, Required, TypedDict

# ------------------------------------------------------------------ xafsmith.json
class NormConfig(TypedDict, total=False):
    pre1: float
    pre2: float
    norm1: float
    norm2: float | None
    nnorm: int
    nvict: int
    e0_method: str
    e0: float | None
    smooth_ev: float


class BkgConfig(TypedDict, total=False):
    rbkg: float
    kweight: float
    kmin: float
    kmax: float | None
    dk: float
    win: str
    nclamp: int
    clamp_lo: float
    clamp_hi: float


class FtConfig(TypedDict, total=False):
    kmin: float
    kmax: float
    dk: float
    window: str
    kweight: float | list[float]
    rmax_out: float


class S02Recommended(TypedDict, total=False):
    value: float
    err: float
    source: str


class EdgeConfig(TypedDict, total=False):
    element: Required[str]
    edge: Required[str]
    e_table: Required[float]
    e_table_source: str
    reference: str | None
    elements_in_sample: list[str]
    norm: Required[NormConfig]
    bkg: Required[BkgConfig]
    ft: Required[FtConfig]
    s02_recommended: S02Recommended


class SchemaTag(TypedDict, total=False):
    schema: str


class Instrument(TypedDict, total=False):
    facility: str
    beamline: str
    monochromator: str
    detection: str


class FormatTemplate(TypedDict, total=False):
    """`formats` 里保存的列映射模板：base 为 reader 名，其余键把角色指到列名或列号（if 可给多个通道）"""
    base: str
    mode: str
    energy: Any
    i0: Any
    it: Any
    mu: Any


class EdgeOverride(TypedDict, total=False):
    """overrides.<样品>：个别样品改参数（必须在 overrides_reason 写理由）"""
    norm: NormConfig
    bkg: BkgConfig
    ft: FtConfig
    elements_in_sample: list[str]


class Config(TypedDict, total=False):
    """xafsmith.json 顶层"""
    xafsmith: SchemaTag
    edges: dict[str, EdgeConfig]
    overrides: dict[str, EdgeOverride]
    overrides_reason: dict[str, str]
    deglitch: dict[str, list[list[float]]]
    deglitch_reason: dict[str, str]
    instrument: Instrument
    formats: dict[str, FormatTemplate]


# ------------------------------------------------------------------ 模型 JSON
class ParamSpec(TypedDict, total=False):
    """params 里的对象写法（也可直接写数字或表达式字符串，见 ParamValue）"""
    value: float
    vary: bool
    min: float
    max: float
    expr: str


ParamValue = float | int | str | ParamSpec
Params = dict[str, ParamValue]


class PathSpec(TypedDict, total=False):
    file: Required[str]
    label: str
    s02: Any
    e0: Any
    deltar: Any
    sigma2: Any
    third: Any
    N: Any
    note: str


class Restraint(TypedDict, total=False):
    expr: Required[str]
    value: Required[float]
    sigma: Required[float]
    name: str
    note: str


class S02Source(TypedDict, total=False):
    model: str
    value: float
    stderr: float
    manual: bool


class _ModelCommon(TypedDict, total=False):
    name: str
    schema: str
    kmin: float
    kmax: float
    dk: float
    window: str
    kweight: float | list[float]
    rmin: float
    rmax: float
    fitspace: str
    temperature: float
    params: Params
    restraints: list[Restraint]
    s02_source: S02Source
    quickfit: dict[str, Any]


class SingleModel(_ModelCommon, total=False):
    """旧格式（单数据集）：顶层有 sample 与 paths"""
    sample: str
    paths: list[PathSpec]


class DatasetSpec(_ModelCommon, total=False):
    id: str
    sample: Required[str]
    paths: Required[list[PathSpec]]
    epsilon_k: float


class MultiModel(_ModelCommon, total=False):
    """多数据集模型：有 datasets，顶层不得有 sample / paths"""
    datasets: Required[list[DatasetSpec]]


ModelDict = SingleModel | MultiModel


# ------------------------------------------------------------------ 拟合摘要（fit_exafs.summarize / summarize_multi）
class FitParam(TypedDict, total=False):
    value: float
    stderr: float | None
    vary: bool
    expr: str | None


class FitPathRow(TypedDict, total=False):
    path: str
    reff: float
    degen: float
    N: float
    amp: float
    R: float
    R_err: float | None
    sigma2: float
    sigma2_err: float | None
    e0: float
    e0_err: float | None
    deltar: float
    dataset: str
    temperature: float | None
    sigma2_model: str | None
    theta_param: str | None


class FitSummary(TypedDict, total=False):
    """services 保存拟合时用的摘要字典（多数据集另有 multi / n_datasets / datasets / path_amp_err）"""
    model: str
    sample: str
    multi: bool
    n_datasets: int
    kmin: float
    kmax: float
    rmin: float
    rmax: float
    kweight: str
    fitspace: str
    n_idp: float
    n_idp_formula: float
    nvarys: int
    rfactor: float
    chi2: float
    chi2_reduced: float
    params: dict[str, FitParam]
    paths: list[FitPathRow]
    warnings: list[str]
    datasets: list[dict[str, Any]]
    path_amp_err: list[float | None]
    restraints: list[dict[str, Any]]
    restraint_chi2: float
    restraint_c0: float
    chi2_data: float
    restraint_share: float


class FitRecord(TypedDict, total=False):
    """services.run_model 返回的拟合记录"""
    model: ModelDict
    summ: FitSummary
    result: Any
    curves: Any
    report: str
    time: str
    multi: bool
    trend_order: Any
