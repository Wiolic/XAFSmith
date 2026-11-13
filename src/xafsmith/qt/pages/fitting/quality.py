"""拟合质量检查（纯逻辑，不含控件）。"""

from __future__ import annotations

from xafsmith import logs
from ...widgets import T


def quality_checks(fit, dg=None):
    """[(True/False/None, 文字)]：True 通过，False 需注意，None 仅提示"""
    s, md = fit["summ"], fit["model"]
    out = []
    rf = s["rfactor"]
    if rf < 0.02:
        out.append((True, T(f"R 因子 {rf:.4f} &lt; 0.02：很好", f"R-factor {rf:.4f} &lt; 0.02: very good")))
    elif rf <= 0.05:
        out.append((True, T(f"R 因子 {rf:.4f}（0.02–0.05）：第一壳层可接受", f"R-factor {rf:.4f} (0.02–0.05): acceptable for a first shell")))
    else:
        out.append((False, T(f"R 因子 {rf:.4f} &gt; 0.05：检查模型、R 窗口与数据", f"R-factor {rf:.4f} &gt; 0.05: check the model, R window and data")))
    nv, ni = s["nvarys"], s["n_idp"]
    ok = nv <= ni / 2
    out.append((ok, T(f"变量数 {nv}，N_idp/2 = {ni / 2:.1f}", f"{nv} variables, N_idp/2 = {ni / 2:.1f}")
                + ("" if ok else T("：变量太多，请固定或约束参数", ": too many; fix or constrain some"))))
    if dg is not None:
        r = dg["ratio"]
        out.append((r <= 2.5, T(f"残差 / 噪声 = {r:.1f}", f"Residual / noise = {r:.1f}")
                    + (T("：已接近数据极限", ": close to the data limit") if r <= 2.5
                       else T("：残差是系统性的（见“诊断”标签）", ": systematic residual (see the Diagnosis tab)"))))
    P = s["params"]
    mpar = md.get("params", {})
    for name, v in P.items():
        if not v["vary"] or v["expr"]:
            continue
        val, err = v["value"], v["stderr"]
        if err is None:
            out.append((False, T(f"{name}：误差无法估计（参数可能过多或高度相关）",
                                 f"{name}: error could not be estimated (too many or strongly correlated parameters)")))
        elif abs(err) > abs(val) and not name.lower().startswith(("e0", "de", "dr", "del")):
            out.append((False, T(f"{name} = {val:.4g} ± {err:.2g}：误差大于数值，数据不能确定它",
                                 f"{name} = {val:.4g} ± {err:.2g}: error exceeds the value; not determined by the data")))
        spec = mpar.get(name)
        if isinstance(spec, dict):
            lo, hi = spec.get("min"), spec.get("max")
            span = (hi - lo) if (lo is not None and hi is not None) else max(abs(val), 1e-3)
            for b, lab in ((lo, "min"), (hi, "max")):
                if b is not None and abs(val - b) <= 0.01 * span:
                    out.append((False, T(f"{name} 停在边界 {lab} = {b:g}：由限制而非数据决定",
                                         f"{name} sits at its {lab} = {b:g}: held by the bound, not the data")))
    e0s = [(k, v["value"]) for k, v in P.items() if "e0" in k.lower() and v["vary"] and not v["expr"]]
    if e0s:
        bad = [f"{k} = {x:.1f}" for k, x in e0s if abs(x) > 10]
        out.append((not bad, (T("ΔE0 超出 ±10 eV：", "ΔE0 beyond ±10 eV: ") + ", ".join(bad)) if bad
                    else T("ΔE0 在 ±10 eV 以内", "ΔE0 within ±10 eV")))
    ss = [(p["path"], p["sigma2"]) for p in s["paths"]]
    neg = [f"{a}: {b:.4f}" for a, b in ss if b <= 0]
    big = [f"{a}: {b:.4f}" for a, b in ss if b > 0.03]
    if neg:
        out.append((False, T("σ² ≤ 0（非物理）：", "σ² ≤ 0 (unphysical): ") + "; ".join(neg)))
    if big:
        out.append((False, T("σ² &gt; 0.03 Å²（很大，可能在补偿 N 或别的路径）：",
                             "σ² &gt; 0.03 Å² (very large; may be compensating N or another path): ") + "; ".join(big)))
    if not neg and not big:
        out.append((True, T("所有路径 σ² 为正且不过大", "All σ² positive and not excessive")))
    dr = [f"{p['path']}: {p['deltar']:+.3f} Å" for p in s["paths"] if abs(p["deltar"]) > 0.2]
    out.append((not dr, (T("ΔR 超过 0.2 Å，结构模型可能不合适：", "ΔR beyond 0.2 Å; the structural model may not fit: ") + "; ".join(dr))
                if dr else T("所有路径 |ΔR| ≤ 0.2 Å", "All paths |ΔR| ≤ 0.2 Å")))
    try:
        pars = fit["result"].params
        seen, hi = set(), []
        for a, pa in pars.items():
            if a not in P or not pa.vary or not pa.correl:
                continue
            for b, r in pa.correl.items():
                if b in P and abs(r) > 0.9 and (b, a) not in seen:
                    seen.add((a, b))
                    hi.append(f"{a}–{b}: {r:+.2f}")
        out.append((not hi, (T("强相关（|r| &gt; 0.9），结论中要说明：", "Strong correlations (|r| &gt; 0.9) to report: ") + "; ".join(hi))
                    if hi else T("没有 |r| &gt; 0.9 的强相关参数对", "No parameter pair with |r| &gt; 0.9")))
    except Exception:
        logs.log.warning("qt.pages.fitting.quality_checks 出错（已忽略或已提示）", exc_info=True)
        pass
    kws = md.get("kweight")
    if not (isinstance(kws, list) and len(kws) > 1):
        out.append((None, T("只用了单一 k 权重：同时拟合 k¹、k²、k³ 能降低相关性",
                            "Single k-weight: fitting k¹, k², k³ together reduces correlations")))
    if fit.get("robust") is None and not s.get("dataset"):      # 多数据集暂无稳健性检查，不提示
        out.append((None, T("尚未运行稳健性检查（见“稳健性”标签）", "Robustness check not run yet (Robustness tab)")))
    return out
