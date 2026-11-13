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
