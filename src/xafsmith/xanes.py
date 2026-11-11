"""xanes —— XANES 定量：边位置、白线、价态标定（边位置–价态线性关系）、边前峰拟合。

定义（全项目统一，写入结果表）：
  E0_deriv   归一化后平滑一阶导数最大值（与 normalize 的 E0 相同）
  E_half     归一化 μ 首次达到 0.5 的能量（线性插值；在 E0 ± 30 eV 内寻找）
  WL_E       白线峰位：E0 至 E0+wl_window 内归一化 μ（flattened）的最大值位置
  WL_height  白线峰高（flattened，边跳 = 1）
  WL_area    白线面积：∫ max(flat − 1, 0) dE，积分区间 E0 … E0+wl_window（eV）
价态标定：用已知价态的实测标样，对所选边位置定义做线性最小二乘 E = a·价态 + b，
          样品价态 = (E − b)/a，误差由拟合协方差传递（不含标样本身的不确定性与化学环境差异）。
边前峰：在 [E0+emin, E0+emax] 内用 n 个高斯峰（σ ≤ 2.5 eV）+ 误差函数（或反正切）台阶 + 常数拟合 flattened μ；
        台阶中心限制在半高点 E_half ± 6 eV，代表主边上升沿。

结论提醒：边位置同时受价态、配位数与配体影响；只有同类配体、相近结构的标样才能做价态标定。
"""
from xafsmith import logs
import math

import numpy as np
import pandas as pd


def _need_norm(g):
    if not hasattr(g, "flat"):
        raise ValueError(f"{getattr(g, 'label', '')}: 需要先归一化")


def edge_features(g, wl_window=30.0, half_search=30.0):
    """返回一条谱的边位置与白线参数 dict"""
    _need_norm(g)
    e, f, e0 = np.asarray(g.energy), np.asarray(g.flat), float(g.e0)
    # 半高点
    m = (e > e0 - half_search) & (e < e0 + half_search)
    ee, ff = e[m], f[m]
    e_half = np.nan
    idx = np.where((ff[:-1] < 0.5) & (ff[1:] >= 0.5))[0]
    if len(idx):
        i = idx[0]
        e_half = float(ee[i] + (0.5 - ff[i]) * (ee[i + 1] - ee[i]) / (ff[i + 1] - ff[i]))
    # 白线
    w = (e >= e0) & (e <= e0 + wl_window)
    wl_e = wl_h = wl_area = np.nan
    if w.sum() > 2:
        i = int(np.argmax(f[w]))
        wl_e, wl_h = float(e[w][i]), float(f[w][i])
        wl_area = float(np.trapezoid(np.clip(f[w] - 1.0, 0, None), e[w])) if hasattr(np, "trapezoid") \
            else float(np.trapz(np.clip(f[w] - 1.0, 0, None), e[w]))
    return dict(sample=getattr(g, "label", ""), edge=f"{getattr(g, 'element', '')} {getattr(g, 'edge', '')}",
                mode=getattr(g, "mode", ""), E0_deriv=e0, E_half=e_half, WL_E=wl_e, WL_height=wl_h,
                WL_area=wl_area, wl_window=wl_window, edge_step=float(getattr(g, "edge_step", np.nan)))


def features_table(groups, wl_window=30.0):
    return pd.DataFrame([edge_features(g, wl_window) for g in groups])


def valence_calibration(positions, valences):
    """线性标定 E = a·v + b。返回 dict(a, b, cov, r2, n)。至少需要 2 个标样（3 个以上才有误差）。"""
    x, y = np.asarray(valences, float), np.asarray(positions, float)
    if len(x) < 2 or len(set(x)) < 2:
        raise ValueError("至少需要两个不同价态的标样")
    if len(x) > 2:
        (a, b), cov = np.polyfit(x, y, 1, cov=True)
    else:
        a, b = np.polyfit(x, y, 1)
        cov = np.full((2, 2), np.nan)
    yf = a * x + b
    ss = float(np.sum((y - y.mean()) ** 2))
    r2 = 1 - float(np.sum((y - yf) ** 2)) / ss if ss > 0 else np.nan
    return dict(a=float(a), b=float(b), cov=cov.tolist(), r2=r2, n=len(x),
                a_err=float(math.sqrt(cov[0][0])) if np.isfinite(cov[0][0]) else np.nan,
                b_err=float(math.sqrt(cov[1][1])) if np.isfinite(cov[1][1]) else np.nan)


def predict_valence(cal, position):
    """由边位置估算价态及其误差（只含标定直线的统计误差）"""
    a, b = cal["a"], cal["b"]
    v = (position - b) / a
    cov = np.asarray(cal["cov"], float)
    if np.all(np.isfinite(cov)):
        J = np.array([-(position - b) / a ** 2, -1 / a])          # ∂v/∂a, ∂v/∂b
        err = float(math.sqrt(max(J @ cov @ J, 0)))
    else:
        err = np.nan
    return float(v), err


def preedge_fit(g, emin=-20.0, emax=0.0, npeaks=1, step="erf", centers=None):
    """边前峰拟合（能量相对 E0）。返回 dict(peaks=[...], centroid, total_area, rfactor, curves, report)"""
    from lmfit.models import ConstantModel, GaussianModel, StepModel
    _need_norm(g)
    e0 = float(g.e0)
    x = np.asarray(g.energy) - e0
    m = (x >= emin) & (x <= emax)
    x, y = x[m], np.asarray(g.flat)[m]
    if len(x) < 10:
        raise ValueError("拟合区间内数据点太少")
    model = ConstantModel(prefix="c_")
    pars = model.make_params(c=float(np.min(y[: max(3, len(y) // 10)])))
    if step in ("erf", "arctan"):
        sm = StepModel(form="erf" if step == "erf" else "arctan", prefix="st_")
        model = model + sm
        # 台阶代表主边的上升沿：中心放在半高点附近（可在区间之外），幅度约为边跳 1
        eh = edge_features(g)["E_half"]
        sc = (eh - e0) if np.isfinite(eh) else emax + 5.0
        p = sm.make_params(amplitude=1.0, center=sc, sigma=2.0)
        p["st_amplitude"].set(min=0.3, max=1.5)
        p["st_sigma"].set(min=0.5, max=8)
        p["st_center"].set(min=sc - 6, max=sc + 6)
        pars.update(p)
    # 第一步：只拟合基线（常数 + 台阶），得到残差，用残差的峰作为边前峰初值
    base = model.fit(y, pars, x=x)
    pars = base.params.copy()
    resid = y - base.best_fit
    if centers is None:
        span = emax - emin
        try:
            from scipy.signal import find_peaks
            pk, _ = find_peaks(resid, distance=max(1, len(x) // (npeaks * 3)))
            pk = sorted(pk, key=lambda i: -resid[i])[:npeaks]
            centers = sorted(float(x[i]) for i in pk)
        except Exception:
            logs.log.warning("xanes.preedge_fit 出错（已忽略或已提示）", exc_info=True)
            centers = []
        while len(centers) < npeaks:
            centers.append(emin + span * (len(centers) + 1) / (npeaks + 2))
        centers = sorted(centers)
    for i, c in enumerate(centers[:npeaks]):
        gm = GaussianModel(prefix=f"p{i + 1}_")
        model = model + gm
        h0 = max(float(np.interp(c, x, resid)), 1e-3)
        p = gm.make_params(center=c, sigma=1.0, amplitude=h0 * 2.5)
        p[f"p{i + 1}_amplitude"].set(min=0, max=2.0)
        p[f"p{i + 1}_sigma"].set(min=0.3, max=2.5)          # 边前峰宽度有限，防止高斯吃掉主边
        p[f"p{i + 1}_center"].set(min=emin, max=emax)
        pars.update(p)
    res = model.fit(y, pars, x=x)
    comps = res.eval_components(x=x)
    peaks = []
    for i in range(npeaks):
        pre = f"p{i + 1}_"
        P = res.params
        sd = lambda n: None if P[pre + n].stderr is None else float(P[pre + n].stderr)   # noqa: E731
        peaks.append(dict(peak=i + 1, center=float(P[pre + "center"].value) + e0, center_err=sd("center"),
                          area=float(P[pre + "amplitude"].value), area_err=sd("amplitude"),
                          height=float(P[pre + "height"].value), fwhm=float(P[pre + "fwhm"].value)))
    tot = sum(p["area"] for p in peaks)
    centroid = sum(p["area"] * p["center"] for p in peaks) / tot if tot > 0 else np.nan
    rf = float(np.sum((y - res.best_fit) ** 2) / np.sum(y ** 2))
    curves = dict(x=x + e0, y=y, fit=res.best_fit,
                  comps={k.rstrip("_"): (v if np.ndim(v) else np.full_like(x, v)) for k, v in comps.items()})
    warn = [f"峰 {p['peak']} 的位置贴近拟合区间边界（{p['center']:.2f} eV）：调整区间或减少峰数"
            for p in peaks if min(abs(p["center"] - e0 - emin), abs(p["center"] - e0 - emax)) < 0.5]
    warn += [f"峰 {p['peak']} 面积≈0：该峰不需要" for p in peaks if p["area"] < 1e-3]
    if step in ("erf", "arctan") and abs(res.params["st_center"].value - pars["st_center"].min) < 0.05:
        warn.append("台阶中心贴近下限：主边基线可能没有拟合好")
    return dict(sample=getattr(g, "label", ""), e0=e0, emin=emin, emax=emax, npeaks=npeaks, step=step,
                peaks=peaks, total_area=tot, centroid=centroid, rfactor=rf, curves=curves, warnings=warn,
                report=res.fit_report())
