"""fitcheck —— 拟合结果的质量检查（纯逻辑，不依赖 Qt；精细拟合页与快速拟合判定共用）。

返回结构化条目 Check(ok, code, zh, en)：ok 为 True 通过、False 需注意、None 仅提示；code 是检查项的稳定标识
（快速拟合按 code 配建议）；zh / en 是中英文字。精细拟合页用 T(zh, en) 显示，文字与顺序与拆分前逐字相同
（tests/unit/test_fitcheck.py 锁定）。
Quality checks for a fit result (pure logic, no Qt; shared by the Detailed-fit page and the quick-fit verdict).
"""
from __future__ import annotations

from dataclasses import dataclass

from xafsmith import logs


@dataclass(frozen=True)
class Check:
    ok: bool | None          # True 通过 / False 需注意 / None 仅提示
    code: str
    zh: str
    en: str


class _Bi:
    """中英成对的文字，可用 + 拼接（与普通字符串或另一个 _Bi）。"""
    __slots__ = ("zh", "en")

    def __init__(self, zh, en):
        self.zh, self.en = zh, en

    def __add__(self, o):
        return _Bi(self.zh + o.zh, self.en + o.en) if isinstance(o, _Bi) else _Bi(self.zh + o, self.en + o)

    def __radd__(self, o):
        return _Bi(o + self.zh, o + self.en)


def _chk(ok, code, t):
    return Check(ok, code, t.zh, t.en)


def fit_checks(fit, dg=None, stern=False, robust_hint=True):
    """fit：拟合记录（summ / model / result / robust）；dg：诊断结果（可缺省）。
    stern=False（精细拟合）：变量数与 N_idp/2 比较，超过即“需注意”。
    stern=True（快速拟合）：变量数 ≤ N_idp 为通过（Stern 准则），> N_idp/2 另给一条提示“信息量偏少”，> N_idp 为需注意。
    robust_hint=False：不给“尚未运行稳健性检查”的提示。"""
    s, md = fit["summ"], fit["model"]
    out = []
    rf = s["rfactor"]
    if rf < 0.02:
        out.append(_chk(True, "rfactor", _Bi(f"R 因子 {rf:.4f} &lt; 0.02：很好", f"R-factor {rf:.4f} &lt; 0.02: very good")))
    elif rf <= 0.05:
        out.append(_chk(True, "rfactor", _Bi(f"R 因子 {rf:.4f}（0.02–0.05）：第一壳层可接受", f"R-factor {rf:.4f} (0.02–0.05): acceptable for a first shell")))
    else:
        out.append(_chk(False, "rfactor", _Bi(f"R 因子 {rf:.4f} &gt; 0.05：检查模型、R 窗口与数据", f"R-factor {rf:.4f} &gt; 0.05: check the model, R window and data")))
    nv, ni = s["nvarys"], s["n_idp"]
    jt = _Bi("（全部数据集合计）", " (all datasets)") if s.get("joint") else _Bi("", "")
    if s.get("joint"):                     # 联合拟合：变量是共享的，与全部数据集的 N_idp 之和比较
        ni = s["joint"]["n_idp"]
    if stern:
        ok = nv <= ni
        out.append(_chk(ok, "nvarys", _Bi(f"变量数 {nv}，N_idp = {ni:.1f}{jt.zh}", f"{nv} variables, N_idp = {ni:.1f}{jt.en}")
                        + ("" if ok else _Bi("：变量数超过独立点数，请固定或约束参数", ": more variables than independent points; fix or constrain some"))))
        if ok and nv > ni / 2:
            out.append(_chk(None, "nvarys_low_info", _Bi(f"变量数 {nv} 超过 N_idp/2 = {ni / 2:.1f}：信息量偏少，结果的误差会偏大",
                                                         f"{nv} variables exceed N_idp/2 = {ni / 2:.1f}: little information; expect large errors")))
    else:
        ok = nv <= ni / 2
        out.append(_chk(ok, "nvarys", _Bi(f"变量数 {nv}，N_idp/2 = {ni / 2:.1f}{jt.zh}", f"{nv} variables, N_idp/2 = {ni / 2:.1f}{jt.en}")
                        + ("" if ok else _Bi("：变量太多，请固定或约束参数", ": too many; fix or constrain some"))))
    if dg is not None:
        r = dg["ratio"]
        out.append(_chk(r <= 2.5, "noise", _Bi(f"残差 / 噪声 = {r:.1f}", f"Residual / noise = {r:.1f}")
                        + (_Bi("：已接近数据极限", ": close to the data limit") if r <= 2.5
                           else _Bi("：残差是系统性的（见“诊断”标签）", ": systematic residual (see the Diagnosis tab)"))))
    P = s["params"]
    mpar = md.get("params", {})
    for name, v in P.items():
        if not v["vary"] or v["expr"]:
            continue
        val, err = v["value"], v["stderr"]
        if err is None:
            out.append(_chk(False, "err_none", _Bi(f"{name}：误差无法估计（参数可能过多或高度相关）",
                                                   f"{name}: error could not be estimated (too many or strongly correlated parameters)")))
        elif abs(err) > abs(val) and not name.lower().startswith(("e0", "de", "dr", "del")):
            out.append(_chk(False, "err_big", _Bi(f"{name} = {val:.4g} ± {err:.2g}：误差大于数值，数据不能确定它",
                                                  f"{name} = {val:.4g} ± {err:.2g}: error exceeds the value; not determined by the data")))
        spec = mpar.get(name)
        if isinstance(spec, dict):
            lo, hi = spec.get("min"), spec.get("max")
            span = (hi - lo) if (lo is not None and hi is not None) else max(abs(val), 1e-3)
            for b, lab in ((lo, "min"), (hi, "max")):
                if b is not None and abs(val - b) <= 0.01 * span:
                    out.append(_chk(False, "at_bound", _Bi(f"{name} 停在边界 {lab} = {b:g}：由限制而非数据决定",
                                                           f"{name} sits at its {lab} = {b:g}: held by the bound, not the data")))
    e0s = [(k, v["value"]) for k, v in P.items() if "e0" in k.lower() and v["vary"] and not v["expr"]]
    if e0s:
        bad = [f"{k} = {x:.1f}" for k, x in e0s if abs(x) > 10]
        out.append(_chk(not bad, "e0", (_Bi("ΔE0 超出 ±10 eV：", "ΔE0 beyond ±10 eV: ") + ", ".join(bad)) if bad
                        else _Bi("ΔE0 在 ±10 eV 以内", "ΔE0 within ±10 eV")))
    ss = [(p["path"], p["sigma2"]) for p in s["paths"]]
    neg = [f"{a}: {b:.4f}" for a, b in ss if b <= 0]
    big = [f"{a}: {b:.4f}" for a, b in ss if b > 0.03]
    if neg:
        out.append(_chk(False, "sigma2_neg", _Bi("σ² ≤ 0（非物理）：", "σ² ≤ 0 (unphysical): ") + "; ".join(neg)))
    if big:
        out.append(_chk(False, "sigma2_big", _Bi("σ² &gt; 0.03 Å²（很大，可能在补偿 N 或别的路径）：",
                                                 "σ² &gt; 0.03 Å² (very large; may be compensating N or another path): ") + "; ".join(big)))
    if not neg and not big:
        out.append(_chk(True, "sigma2_ok", _Bi("所有路径 σ² 为正且不过大", "All σ² positive and not excessive")))
    dr = [f"{p['path']}: {p['deltar']:+.3f} Å" for p in s["paths"] if abs(p["deltar"]) > 0.2]
    out.append(_chk(not dr, "dr", (_Bi("ΔR 超过 0.2 Å，结构模型可能不合适：", "ΔR beyond 0.2 Å; the structural model may not fit: ") + "; ".join(dr))
                    if dr else _Bi("所有路径 |ΔR| ≤ 0.2 Å", "All paths |ΔR| ≤ 0.2 Å")))
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
        out.append(_chk(not hi, "correl", (_Bi("强相关（|r| &gt; 0.9），结论中要说明：", "Strong correlations (|r| &gt; 0.9) to report: ") + "; ".join(hi))
                        if hi else _Bi("没有 |r| &gt; 0.9 的强相关参数对", "No parameter pair with |r| &gt; 0.9")))
    except Exception:
        logs.log.warning("fitcheck.fit_checks 出错（已忽略或已提示）：%s", s.get("sample"), exc_info=True)
    kws = md.get("kweight")
    if not (isinstance(kws, list) and len(kws) > 1):
        out.append(_chk(None, "single_k", _Bi("只用了单一 k 权重：同时拟合 k¹、k²、k³ 能降低相关性",
                                              "Single k-weight: fitting k¹, k², k³ together reduces correlations")))
    if robust_hint and fit.get("robust") is None and not s.get("dataset"):      # 多数据集暂无稳健性检查，不提示
        out.append(_chk(None, "robust", _Bi("尚未运行稳健性检查（见“稳健性”标签）", "Robustness check not run yet (Robustness tab)")))
    return out
