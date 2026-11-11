"""fit_lcf —— XANES / EXAFS 线性组合拟合。

  * 空间：'norm'（归一化 μ）、'dmude'（导数）、'chik'（k^w χ(k)）
  * 端点必须是实测标样；使用非实测端点须在 note 中注明为假设
  * 约束：权重 ∈ [0,1]（可关），权重和 = 1（可关），可选允许整体能量平移 dE
  * 输出：权重 ± 误差、R 因子 = Σ(d−f)²/Σd²、χ²_ν；同时给出“只用单一标样”的拟合做比较
  * fit_all_combinations：列举端点组合（2..nmax 个），按 R 因子排序

用法：
  python -m xafsmith.fit_lcf <样品> <标样1> <标样2> ... --emin -20 --emax 30
"""
import argparse
import itertools

import numpy as np
import pandas as pd


def _get_space(g, space, kweight=2):
    if space == "norm":
        return g.energy - g.e0, g.flat if hasattr(g, "flat") else g.norm
    if space == "dmude":
        y = np.gradient(g.flat if hasattr(g, "flat") else g.norm, g.energy)
        return g.energy - g.e0, y
    if space == "chik":
        return g.k, g.chi * g.k ** kweight
    raise ValueError(space)


def lcf(sample, standards, xmin=-20, xmax=30, space="norm", kweight=2, sum_to_one=True,
        bounds=True, fit_eshift=False, labels=None):
    """standards：Group 列表（已归一化，E0 用同一定义）。
    xmin/xmax：space='norm'/'dmude' 时为相对 E0 的 eV；'chik' 时为 k。"""
    labels = labels or [s.label for s in standards]
    xs, ys = _get_space(sample, space, kweight)
    sel = (xs >= xmin) & (xs <= xmax)
    x, y = xs[sel], ys[sel]
    # 能量对齐用绝对能量：标样的 x 轴也相对各自 E0。为保持“同一定义”，用样品 E0 作参考。
    comps = []
    for s in standards:
        xs_s, ys_s = _get_space(s, space, kweight)
        if space in ("norm", "dmude"):
            xs_s = s.energy - sample.e0   # 用绝对能量对齐（校准后的能量轴）
        comps.append((xs_s, ys_s))

    from lmfit import Parameters, minimize  # lmfit 导入约 0.8 秒：用到时才导入
    params = Parameters()
    n = len(standards)
    # 每个权重都独立带边界；“和为 1”用强罚项实现（避免用表达式时最后一个权重越界）
    for i in range(n):
        params.add(f"w{i}", value=1.0 / n, min=0 if bounds else -np.inf,
                   max=1 if bounds else np.inf)
    pen = 1e3 * np.sqrt(len(x)) * (np.max(np.abs(y)) + 1e-12)
    params.add("de", value=0.0, vary=bool(fit_eshift and space != "chik"), min=-5, max=5)

    def model(p):
        tot = np.zeros_like(x)
        for i, (xs_s, ys_s) in enumerate(comps):
            tot += p[f"w{i}"].value * np.interp(x - p["de"].value, xs_s, ys_s)
        return tot

    def resid(p):
        r = model(p) - y
        if sum_to_one and n > 1:
            r = np.append(r, pen * (sum(p[f"w{i}"].value for i in range(n)) - 1.0))
        return r

    res = minimize(resid, params)
    fit = model(res.params)
    rfac = float(np.sum((y - fit) ** 2) / np.sum(y ** 2))
    chi2 = float(np.sum((y - fit) ** 2))
    out = dict(sample=sample.label, standards=labels, space=space, xmin=xmin, xmax=xmax,
               rfactor=rfac, chi2=chi2, chi2_reduced=chi2 / max(len(x) - res.nvarys + (sum_to_one and n > 1), 1),
               nvarys=res.nvarys, npts=len(x), sum_to_one=sum_to_one,
               de=float(res.params["de"].value))
    w, we = [], []
    for i in range(n):
        p = res.params[f"w{i}"]
        w.append(float(p.value))
        we.append(float(p.stderr) if p.stderr is not None else np.nan)
    out["weights"] = dict(zip(labels, w))
    out["weights_err"] = dict(zip(labels, we))
    out["sum_weights"] = float(np.sum(w))
    out["curves"] = dict(x=x, y=y, fit=fit,
                         comps={labels[i]: w[i] * np.interp(x - out["de"], *comps[i])
                                for i in range(n)})
    return out


def single_standard_compare(sample, standards, **kws):
    """每个标样单独拟合（权重自由，不要求和为 1 时可看振幅比）"""
    rows = []
    for s in standards:
        r = lcf(sample, [s], sum_to_one=False, bounds=False, **kws)
        rows.append(dict(standard=s.label, weight=r["weights"][s.label], rfactor=r["rfactor"],
                         chi2_reduced=r["chi2_reduced"]))
    return pd.DataFrame(rows).sort_values("rfactor")


def fit_all_combinations(sample, standards, nmin=1, nmax=3, **kws):
    rows = []
    for n in range(nmin, min(nmax, len(standards)) + 1):
        for combo in itertools.combinations(standards, n):
            r = lcf(sample, list(combo), **kws)
            row = dict(n=n, rfactor=r["rfactor"], chi2_reduced=r["chi2_reduced"])
            for lab in r["weights"]:
                row[lab] = round(r["weights"][lab], 4)
                row[lab + "_err"] = r["weights_err"][lab]
            rows.append(row)
    return pd.DataFrame(rows).sort_values("rfactor").reset_index(drop=True)


def result_row(r: dict, note: str = "") -> dict:
    d = dict(sample=r["sample"], space=r["space"], range=f"{r['xmin']}..{r['xmax']}",
             rfactor=r["rfactor"], chi2_reduced=r["chi2_reduced"], sum_weights=r["sum_weights"],
             de=r["de"], note=note)
    for k, v in r["weights"].items():
        d[f"w[{k}]"] = v
        d[f"err[{k}]"] = r["weights_err"][k]
    return d


def main():
    from .io import read_any
    from .normalize import normalize
    ap = argparse.ArgumentParser()
    ap.add_argument("sample")
    ap.add_argument("standards", nargs="+")
    ap.add_argument("--emin", type=float, default=-20)
    ap.add_argument("--emax", type=float, default=30)
    ap.add_argument("--space", default="norm")
    a = ap.parse_args()
    s = normalize(read_any(a.sample))
    stds = [normalize(read_any(f)) for f in a.standards]
    r = lcf(s, stds, xmin=a.emin, xmax=a.emax, space=a.space)
    print({k: v for k, v in r.items() if k != "curves"})
    print(single_standard_compare(s, stds, xmin=a.emin, xmax=a.emax, space=a.space))


if __name__ == "__main__":
    main()
