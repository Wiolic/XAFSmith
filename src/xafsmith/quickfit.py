"""quickfit —— 快速拟合：只拟合第一壳层，并用人话判定结果是否可信（纯计算，不依赖 Qt）。

流程：第一壳层成员（first_shell）→ 自动 Rmin（auto_rmin）→ 建普通模型 dict（build_model）→
现有 fit_exafs.run_fit 拟合（run）→ 判定（verdict）。产物模型与精细拟合 / CLI 同格式，可保存、可在精细拟合里继续。
规则只看散射元素与距离，不含任何具体元素名。
Quick fit: fit only the first shell and state in plain words whether the result is trustworthy
(pure computation, no Qt). The model is an ordinary model dict; rules look only at scatterer element and distance.
"""
from __future__ import annotations

import copy
import html
import math
import re
from datetime import datetime
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

from . import fitcheck

# ---------------------------------------------------------------- 阈值（设计：quick-fit-f2.md；不得放宽）
SHELL_GAP = 0.3         # Å：同一壳层内相邻路径的 Reff 间隔上限；≥ 此值（或异种元素）即另一壳层（≈ EXAFS 分辨率量级，与 GLOSSARY 的“第一壳层”一致）
RMIN_LO = 0.7           # Å：自动 Rmin 的搜索下端（低于它是 FT 低 R 的背景残余）
RMIN_BELOW_PEAK = 0.6   # Å：Rmin 不低于 R_p − 0.6（第一峰低 R 侧半宽约 0.4–0.5 Å；再往下是背景残余，Opus 2026-11-24 定）
RMIN_DEFAULT = 1.0      # Å：|χ(R)| 在 0.7 Å 到第一峰之间没有极小时的 Rmin；同时是第一峰搜索下端
RMAX_DEFAULT = 2.5      # Å：用户未给时的 Rmax
PEAK_KWEIGHT = 2        # 自动 Rmin / Rmax 检查用的 |χ(R)| 的 k 权重（k² 为处理默认；f2 简报未指定，见交接说明）
DEFAULT_KWEIGHT = [1, 2, 3]          # 与精细拟合新建模型的默认相同
R_CIF_TOL = 0.15        # Å：拟合 R 与 CIF 加权平均 Reff 之差的上限
N_RATIO_MAX = 1.5       # 样品 N ≤ 1.5·N_ref，超过多半是 N 与 σ² 互相补偿或标样 S0² 不适用
RMAX_LEAK = 0.30        # Rmax 处 |χ(R)| 超过第一峰的 30% → 窗口可能切进第二壳层
# 参数初值与范围（沿用精细拟合默认）
E0_INIT, E0_RANGE = 0.0, (-15.0, 15.0)
DR_INIT, DR_RANGE = 0.0, (-0.5, 0.5)
SS_INIT, SS_RANGE = 0.003, (0.0, 0.05)
S02_INIT, S02_RANGE = 0.85, (0.3, 1.5)
N_MAX_FACTOR = 2.0      # 样品模式 N 的范围 [0, 2·N_ref]


class QuickFitError(ValueError):
    """快速拟合输入不合规（中英文消息），调用方（CLI / 界面）直接显示。"""


# ---------------------------------------------------------------- 第一壳层
@dataclass
class FirstShell:
    members: list                       # [{file, label, reff, degen}]，按 Reff 升序
    absorber: str
    scatterer: str
    n_ref: float                        # 成员简并度之和
    r_cif: float                        # 简并度加权平均 Reff
    other_elements: list = field(default_factory=list)   # [(元素, Reff)]：第一层 SHELL_GAP 内的异种元素单散射路径

    @property
    def files(self):
        return [m["file"] for m in self.members]


_EL = re.compile(r"[A-Z][a-z]?")


def _el(s):
    """label 片段 → 元素符号（去掉位点编号、括号等：'O1'、'O(2)' → 'O'）；读不出 → None。"""
    m = _EL.match(str(s).strip())
    return m.group(0) if m else None


def _ends(label):
    """单散射路径 label 'A-B' → (吸收元素, 散射元素)，只取元素符号。"""
    parts = str(label).split("-")
    return (_el(parts[0]), _el(parts[1])) if len(parts) >= 2 else (None, None)


def first_shell(paths_df) -> FirstShell:
    """paths_df：feff_wrap.list_paths 的结果（file, label, reff, degen, nleg）。
    单散射路径（nleg = 2）按 Reff 升序；最近一条为起点，向外并入同散射元素且与前一条 Reff 相差 < SHELL_GAP 的路径，
    遇到第一个间隔 ≥ SHELL_GAP 或异种元素即停。其后 SHELL_GAP 内的异种元素路径记入 other_elements（提示用）。"""
    ss = paths_df[paths_df["nleg"] == 2].sort_values("reff", kind="stable")
    if not len(ss):
        raise QuickFitError("FEFF 路径里没有单散射路径 / no single-scattering path in the FEFF output")
    rows = [dict(file=str(r.file), label=str(r.label), reff=float(r.reff), degen=float(r.degen),
                 el=_ends(r.label)[1]) for r in ss.itertuples()]
    absorber, scat = _ends(rows[0]["label"])
    if not scat:
        raise QuickFitError(f"无法从路径 label 读出散射元素：{rows[0]['label']} / cannot read the scatterer from label {rows[0]['label']}")
    members = [rows[0]]
    for r in rows[1:]:
        if r["el"] == scat and r["reff"] - members[-1]["reff"] < SHELL_GAP:
            members.append(r)
        else:
            break
    last = members[-1]["reff"]
    others = [(r["el"], r["reff"]) for r in rows[len(members):] if r["el"] != scat and r["reff"] - last < SHELL_GAP]
    n_ref = sum(m["degen"] for m in members)
    r_cif = sum(m["degen"] * m["reff"] for m in members) / n_ref
    return FirstShell([{k: m[k] for k in ("file", "label", "reff", "degen")} for m in members],
                      absorber, scat, n_ref, r_cif, others)


# ---------------------------------------------------------------- 自动 Rmin
def peak_stats(r, chir_mag, rmax):
    """(第一峰 R_p, 峰高, Rmax 处 |χ(R)|)：峰 = |χ(R)| 在 [RMIN_DEFAULT, rmax] 内的最大值。"""
    r, m = np.asarray(r, float), np.asarray(chir_mag, float)
    sel = (r >= RMIN_DEFAULT) & (r <= rmax)
    if not sel.any():
        raise QuickFitError(f"Rmax = {rmax:g} Å 太小，找不到第一峰（需要大于 {RMIN_DEFAULT:g} Å） / "
                            f"Rmax = {rmax:g} Å is too small to find the first peak (must exceed {RMIN_DEFAULT:g} Å)")
    i = np.flatnonzero(sel)[int(np.argmax(m[sel]))]
    return float(r[i]), float(m[i]), float(np.interp(rmax, r, m))


def auto_rmin(r, chir_mag, rmax):
    """(Rmin, R_p)。R_p = |χ(R)| 在 [1.0 Å, rmax] 内最大值所在的 R；在 [0.7 Å, R_p] 找最小值，
    最小值落在 0.7 Å 端点（该范围内无极小，|χ(R)| 单调上升）或不在 R_p 之前 → Rmin = 1.0 Å；
    找到的极小低于 R_p − RMIN_BELOW_PEAK → 取 R_p − RMIN_BELOW_PEAK。"""
    r, m = np.asarray(r, float), np.asarray(chir_mag, float)
    r_p, _, _ = peak_stats(r, m, rmax)
    idx = np.flatnonzero((r >= RMIN_LO) & (r <= r_p))
    i = idx[int(np.argmin(m[idx]))]
    if i == idx[0] or r[i] >= r_p:
        return RMIN_DEFAULT, r_p
    return max(float(r[i]), round(r_p - RMIN_BELOW_PEAK, 4)), r_p


# ---------------------------------------------------------------- 建模型
def resolve_feff_dir(feff, root=None):
    """FEFF 文件夹：直接含 feff*.dat，或其下恰有一个含 feff*.dat 的子文件夹（如 site0）。"""
    from . import paths
    root = Path(root) if root else paths.ROOT
    d = Path(feff)
    d = d if d.is_absolute() else root / d
    if not d.is_dir():
        raise QuickFitError(f"找不到 FEFF 文件夹：{d} / FEFF folder not found: {d}")
    if any(d.glob("feff[0-9]*.dat")):
        return d
    subs = sorted(s for s in d.iterdir() if s.is_dir() and any(s.glob("feff[0-9]*.dat")))
    if len(subs) == 1:
        return subs[0]
    if not subs:
        raise QuickFitError(f"{d} 里没有 feffNNNN.dat / no feffNNNN.dat in {d}")
    raise QuickFitError(f"{d} 下有多个位点文件夹（{', '.join(s.name for s in subs)}），请指定其中一个 / "
                        f"several site folders under {d} ({', '.join(s.name for s in subs)}); choose one")


def _rel_file(f, root):
    try:
        return Path(f).resolve().relative_to(Path(root).resolve()).as_posix()
    except ValueError:
        return Path(f).resolve().as_posix()


def _ft_window(cfg, edge_key, sample):
    """该样品处理时的 FT 窗（含个别样品覆盖）；缺任何一项 → 报错（不猜）。"""
    from . import pipeline as pl
    c = pl.edge_cfg(cfg, edge_key, sample)
    ft = c.get("ft") or {}
    miss = [k for k in ("kmin", "kmax", "dk", "window") if ft.get(k) is None]
    if miss:
        raise QuickFitError(f"样品 {sample}（{edge_key}）的处理设置里没有 k 窗：缺 {', '.join(miss)}，请先在“处理”里设置 / "
                            f"no k window in the processing settings of {sample} ({edge_key}): missing {', '.join(miss)}")
    return c, {k: ft[k] for k in ("kmin", "kmax", "dk", "window")}


def _chir(g, win):
    """用给定窗对（拷贝的）谱做 FT，返回 (r, |χ(R)|)；k 权重 PEAK_KWEIGHT。"""
    from . import ft as xft
    g2 = copy.deepcopy(g)
    xft.forward(g2, kmin=win["kmin"], kmax=win["kmax"], dk=win["dk"], window=win["window"], kweight=PEAK_KWEIGHT)
    return np.asarray(g2.r), np.asarray(g2.chir_mag)


def build_model(sample, feff_dir, rmax=RMAX_DEFAULT, mode="sample", s02=None, s02_source=None, rmin=None,
                krange=None, kweight=None, name=None, group=None, root=None) -> dict:
    """建快速拟合的普通模型 dict。
    mode："standard"（标样：N = FEFF 简并度，S0² 拟合）或 "sample"（样品：S0² 固定为 s02，N 拟合）。
    krange：dict，可含 kmin/kmax/dk/window，覆盖样品处理设置里的 k 窗；kweight：列表（缺省 [1,2,3]）；rmin 缺省自动。
    group：该样品已处理的谱（缺省按项目配置现建；界面线程应传深拷贝）。s02_source：{"model","value","stderr"} 或
    {"manual": True, "value"}；样品模式未给则记为手填。"""
    from . import paths, pipeline as pl
    from .feff_wrap import list_paths
    if mode not in ("standard", "sample"):
        raise QuickFitError(f"mode 应为 standard / sample，实际 {mode!r} / mode must be standard or sample")
    if mode == "sample" and s02 is None:
        raise QuickFitError("样品模式需要 S0²（取自标样，或手填） / sample mode needs S0² (from a standard, or entered by hand)")
    root = Path(root) if root else paths.ROOT
    d = resolve_feff_dir(feff_dir, root)
    shell = first_shell(list_paths(d))
    cfg, meta = pl.load_config(), pl.load_meta()
    rows = meta[(meta["sample"] == sample) & (meta["use"] != "0")]
    if not len(rows):
        raise QuickFitError(f"meta.csv 中没有可用的样品 {sample} / no usable sample {sample} in meta.csv")
    ek = rows.edge_key.iloc[0]
    c, win = _ft_window(cfg, ek, sample)
    if krange:
        win.update({k: v for k, v in krange.items() if k in win and v is not None})
    el = c.get("element")
    if el and shell.absorber and el != shell.absorber:
        raise QuickFitError(f"FEFF 的吸收原子是 {shell.absorber}，样品 {sample} 的吸收边是 {ek} / "
                            f"the FEFF absorber is {shell.absorber} but sample {sample} is on {ek}")
    rmax = float(rmax)
    r_peak = None
    if rmin is None:
        g = group if group is not None else pl.build_sample(sample, cfg, meta)[0]
        rmin, r_peak = auto_rmin(*_chir(g, win), rmax)
    rmin = float(rmin)
    if rmax - rmin < 0.3:
        raise QuickFitError(f"Rmin = {rmin:.2f}、Rmax = {rmax:.2f} Å 太窄 / the R window {rmin:.2f}–{rmax:.2f} Å is too narrow")
    kw = list(kweight) if kweight else list(DEFAULT_KWEIGHT)
    spec = lambda v, rg, vary=True: dict(value=v, vary=vary, min=rg[0], max=rg[1])    # noqa: E731
    params = {"e0": spec(E0_INIT, E0_RANGE), "dr1": spec(DR_INIT, DR_RANGE), "ss1": spec(SS_INIT, SS_RANGE)}
    if mode == "standard":
        params = {"s02": spec(S02_INIT, S02_RANGE), **params}
    else:
        params = {"s02": dict(value=float(s02), vary=False), "n1": dict(value=shell.n_ref, vary=True, min=0.0,
                                                                      max=N_MAX_FACTOR * shell.n_ref), **params}
    mpaths = []
    for m in shell.members:
        p = dict(file=_rel_file(m["file"], root), label=f"{m['label']}@{m['reff']:.3f}",
                 s02="s02", e0="e0", deltar="dr1", sigma2="ss1")
        if mode == "sample":
            p["N"] = f"n1*{m['degen']!r}/{shell.n_ref!r}"
        mpaths.append(p)
    model = dict(name=name or f"QF_{sample}", sample=sample, kmin=win["kmin"], kmax=win["kmax"], dk=win["dk"],
                 window=win["window"], kweight=kw, rmin=rmin, rmax=rmax, fitspace="r", params=params, paths=mpaths,
                 norm=dict(c["norm"]), bkg=dict(c["bkg"]))
    if mode == "sample":
        model["s02_source"] = dict(s02_source) if s02_source else dict(manual=True, value=float(s02))
    return model


# ---------------------------------------------------------------- 判定
@dataclass
class VerdictItem:
    level: str                  # "pass" | "fail" | "note"
    code: str
    zh: str
    en: str
    advice_zh: str = ""
    advice_en: str = ""


@dataclass
class Verdict:
    ok: bool                    # 没有任何 fail 条目
    items: list

    @property
    def failed(self):
        return [i for i in self.items if i.level == "fail"]

    @property
    def notes(self):
        return [i for i in self.items if i.level == "note"]

    def summary(self, lang="zh"):
        """一句话：可信，或 n 项需注意。"""
        zh = lang == "zh"
        if self.ok:
            return "✅ 可信" if zh else "✅ Trustworthy"
        return f"⚠ {len(self.failed)} 项需注意" if zh else f"⚠ {len(self.failed)} issue(s) to look at"


# 每个检查项的建议（只给“需注意”时显示）
ADVICE = {
    "rfactor": ("检查 Rmin / Rmax 窗口，以及 FEFF 结构是否对应这个样品；必要时到精细拟合里加路径。",
                "Check the Rmin / Rmax window and that the FEFF structure matches this sample; add paths in Detailed fit if needed."),
    "nvarys": ("缩小变量数：固定 S0²（样品应来自标样），或放宽 R 窗口以增加独立点数。",
               "Reduce the variables: keep S0² fixed (from a standard), or widen the R window to gain independent points."),
    "err_none": ("参数之间高度相关或变量过多，误差无法估计；换更宽的 k / R 窗口，或到精细拟合里固定部分参数。",
                 "Parameters are strongly correlated or too many; use a wider k / R window or fix some parameters in Detailed fit."),
    "err_big": ("数据不能确定这个参数，不要引用它的数值；考虑固定它，或换更宽的 k 窗口。",
                "The data cannot determine this parameter; do not quote its value; consider fixing it or widening the k window."),
    "at_bound": ("参数被范围限制住了，数值不可信；检查结构模型是否合适，必要时到精细拟合里放宽范围。",
                 "The parameter is held by its bound, so its value is not reliable; check the structural model, or relax the bound in Detailed fit."),
    "e0": ("ΔE0 过大，通常说明 FEFF 结构与样品不符，或边位校准有问题。",
           "ΔE0 is too large; usually the FEFF structure does not match the sample or the energy calibration is off."),
    "sigma2_neg": ("σ² 不能为负；N 或窗口设置可能有问题。", "σ² cannot be negative; N or the window may be wrong."),
    "sigma2_big": ("σ² 过大，可能在补偿 N；检查配位数与结构无序度。",
                   "σ² is very large and may be compensating N; check the coordination number and disorder."),
    "dr": ("距离偏离结构模型太多，换一个更合适的结构再试。", "The distance deviates too much from the structure; try a better-matching structure."),
    "correl": ("强相关参数不能分别解释；结论里只报告相关的组合，或固定其中一个。",
               "Strongly correlated parameters cannot be interpreted separately; report them together or fix one."),
    "noise": ("残差是系统性的，模型缺少结构（如另一壳层）。", "The residual is systematic; the model lacks some structure (e.g. another shell)."),
    "r_cif": ("拟合距离与结构（CIF）相差超过阈值；检查结构是否对应这个样品。",
              "The fitted distance differs from the structure (CIF) by more than the tolerance; check that the structure matches the sample."),
    "n_ratio": ("N 远大于结构值，多半与 σ² 互相补偿，或标样 S0² 不适用于此样品。",
                "N is much larger than the structure value, probably compensating σ², or the standard's S0² does not apply to this sample."),
    "rmax_leak": ("Rmax 偏大，窗口可能切进第二壳层；把 Rmax 往小调再试。",
                  "Rmax is too large and the window may cut into the second shell; lower Rmax and retry."),
}


def verdict(fit, shell, mode, rmax, peak_amp=None, amp_at_rmax=None, s02_source=None) -> Verdict:
    """fit：run_model 同形的拟合记录（summ / model / result）；shell：FirstShell；mode：standard / sample。
    peak_amp、amp_at_rmax：|χ(R)| 的第一峰高与 Rmax 处的值（缺省则不做窗口检查）。
    条目：fitcheck 各项（变量数用 Stern 准则）+ R 与 CIF 之差、样品 N / N_ref、Rmax 处残余；
    手动 S0² 与第一层有异种元素只作 note，不判失败。"""
    items = []
    for c in fitcheck.fit_checks(fit, None, stern=True, robust_hint=False):
        lvl = "note" if c.ok is None else ("pass" if c.ok else "fail")
        a = ADVICE.get(c.code, ("", "")) if lvl == "fail" else ("", "")
        items.append(VerdictItem(lvl, c.code, c.zh, c.en, *a))
    summ = fit["summ"]
    rows = summ["paths"]
    r_fit = sum(m["degen"] * p["R"] for m, p in zip(shell.members, rows)) / shell.n_ref
    d = abs(r_fit - shell.r_cif)
    ok = d <= R_CIF_TOL
    items.append(VerdictItem("pass" if ok else "fail", "r_cif",
                             f"拟合 R = {r_fit:.3f} Å，结构 {shell.r_cif:.3f} Å，相差 {d:.3f} Å"
                             + (f"（≤ {R_CIF_TOL} Å）" if ok else f"：超过 {R_CIF_TOL} Å"),
                             f"Fitted R = {r_fit:.3f} Å vs structure {shell.r_cif:.3f} Å, difference {d:.3f} Å"
                             + (f" (within {R_CIF_TOL} Å)" if ok else f": beyond {R_CIF_TOL} Å"),
                             *(("", "") if ok else ADVICE["r_cif"])))
    if mode == "sample":
        n = summ["params"]["n1"]["value"]
        ok = n <= N_RATIO_MAX * shell.n_ref
        items.append(VerdictItem("pass" if ok else "fail", "n_ratio",
                                 f"N = {n:.2f}，结构值 {shell.n_ref:g}（{n / shell.n_ref:.2f} 倍）"
                                 + ("" if ok else f"：超过 {N_RATIO_MAX} 倍"),
                                 f"N = {n:.2f} vs structure {shell.n_ref:g} ({n / shell.n_ref:.2f}×)"
                                 + ("" if ok else f": beyond {N_RATIO_MAX}×"),
                                 *(("", "") if ok else ADVICE["n_ratio"])))
    if peak_amp is not None and amp_at_rmax is not None:
        frac = amp_at_rmax / peak_amp if peak_amp > 0 else math.inf
        ok = frac <= RMAX_LEAK
        items.append(VerdictItem("pass" if ok else "fail", "rmax_leak",
                                 f"Rmax = {rmax:g} Å 处 |χ(R)| 是第一峰的 {frac * 100:.0f}%"
                                 + ("" if ok else f"：超过 {RMAX_LEAK * 100:.0f}%，窗口可能切进第二壳层"),
                                 f"|χ(R)| at Rmax = {rmax:g} Å is {frac * 100:.0f}% of the first peak"
                                 + ("" if ok else f": beyond {RMAX_LEAK * 100:.0f}%; the window may cut into the second shell"),
                                 *(("", "") if ok else ADVICE["rmax_leak"])))
    if mode == "sample" and (s02_source or {}).get("manual"):
        items.append(VerdictItem("note", "manual_s02", f"手动 S0² = {s02_source['value']:g}，没有标样依据",
                                 f"Manual S0² = {s02_source['value']:g}, no standard behind it"))
    if shell.other_elements:
        els = ", ".join(f"{e}（{r:.2f} Å）" for e, r in shell.other_elements)
        els_en = ", ".join(f"{e} ({r:.2f} Å)" for e, r in shell.other_elements)
        items.append(VerdictItem("note", "other_elements", f"第一层还有 {els}，未考虑",
                                 f"The first layer also has {els_en}, not included"))
    return Verdict(not any(i.level == "fail" for i in items), items)


# ---------------------------------------------------------------- 运行
@dataclass
class QuickResult:
    sample: str
    mode: str
    model: dict
    shell: FirstShell
    n: float
    n_err: float | None
    r: float
    r_err: float | None
    sigma2: float
    sigma2_err: float | None
    e0: float
    e0_err: float | None
    s02: float
    s02_err: float | None
    rfactor: float
    n_idp: float
    nvarys: int
    window: dict                # kmin, kmax, dk, window, kweight, rmin, rmax
    verdict: Verdict
    fit: dict                   # run_model 同形：model, summ, result, curves, report, time（可进会话历史 / 写 csv）
    r_peak: float | None = None
    peak_amp: float | None = None
    amp_at_rmax: float | None = None


def shell_of_model(model, root=None) -> FirstShell:
    """由快速拟合模型还原第一壳层（读模型第一条路径所在的 FEFF 文件夹）。"""
    from . import paths
    from .feff_wrap import list_paths
    root = Path(root) if root else paths.ROOT
    f = Path(model["paths"][0]["file"])
    f = f if f.is_absolute() else root / f
    sh = first_shell(list_paths(f.parent))
    want = [Path(p["file"]).name for p in model["paths"]]
    if [Path(x).name for x in sh.files] != want:
        raise QuickFitError("模型的路径不是该 FEFF 文件夹的第一壳层（模型被改过？），请在精细拟合里查看 / "
                            "the model paths are not the first shell of their FEFF folder (edited?); open it in Detailed fit")
    return sh


def run(model, group=None, root=None) -> QuickResult:
    """拟合并判定。group：该样品已处理的谱（缺省现建）；不保存任何文件（调用方决定，fit 记录可进会话历史）。"""
    from . import fit_exafs as fx, pipeline as pl
    sample = model["sample"]
    g = group if group is not None else pl.build_sample(sample)[0]
    shell = shell_of_model(model, root)
    n1 = model["params"].get("n1")
    mode = "sample" if n1 is not None else "standard"
    win = {k: model[k] for k in ("kmin", "kmax", "dk", "window")}
    r_pk, pk, at_rmax = peak_stats(*_chir(g, win), model["rmax"])
    res, dset, summ = fx.run_fit(g, model, root)
    fit = dict(model=model, summ=summ, result=res, curves=fx.model_curves(dset), report=fx.report_text(res),
               time=datetime.now().strftime("%H:%M:%S"))
    v = verdict(fit, shell, mode, model["rmax"], pk, at_rmax, model.get("s02_source"))
    P = summ["params"]

    def pv(k):
        return (P[k]["value"], P[k]["stderr"]) if k in P else (None, None)
    r_fit = sum(m["degen"] * p["R"] for m, p in zip(shell.members, summ["paths"])) / shell.n_ref
    n_v, n_e = pv("n1") if mode == "sample" else (shell.n_ref, None)
    return QuickResult(sample, mode, model, shell, n_v, n_e, r_fit, pv("dr1")[1], *pv("ss1"), *pv("e0"),
                       *(pv("s02") if mode == "standard" else (P["s02"]["value"], None)),
                       summ["rfactor"], summ["n_idp"], summ["nvarys"],
                       dict(win, kweight=model["kweight"], rmin=model["rmin"], rmax=model["rmax"]), v, fit, r_pk, pk, at_rmax)


def format_text(res: QuickResult, lang="zh") -> str:
    """一个样品的结果与判定（CLI 用；HTML 实体已还原）。"""
    zh = lang == "zh"
    s, w = res.shell, res.window
    ex = lambda v, e, f: (f"{v:{f}}" if e is None else f"{v:{f}} ± {e:{f}}") if v is not None else "-"    # noqa: E731
    L = [f"== {res.sample}（{'标样' if res.mode == 'standard' else '样品'}）" if zh else
         f"== {res.sample} ({res.mode})",
         ("第一壳层：" if zh else "First shell: ") + f"{s.absorber}–{s.scatterer}, N_ref = {s.n_ref:g}, R_CIF = {s.r_cif:.3f} Å"]
    L += [f"    {m['label']}  Reff {m['reff']:.4f}  degen {m['degen']:g}  {Path(m['file']).name}" for m in s.members]
    L.append(f"k {w['kmin']:g}–{w['kmax']:g} (dk {w['dk']:g}, {w['window']}), kweight {w['kweight']}, "
             f"R {w['rmin']:.2f}–{w['rmax']:.2f} Å" + (f"（自动 Rmin，第一峰 {res.r_peak:.2f} Å）" if zh and res.r_peak
                                                       else (f" (first peak {res.r_peak:.2f} Å)" if res.r_peak else "")))
    L.append(f"N {ex(res.n, res.n_err, '.2f')} | R {ex(res.r, res.r_err, '.4f')} Å | σ² {ex(res.sigma2, res.sigma2_err, '.5f')} Å² | "
             f"ΔE0 {ex(res.e0, res.e0_err, '.2f')} eV | S0² {ex(res.s02, res.s02_err, '.3f')}"
             f"{'（固定）' if res.mode == 'sample' and zh else (' (fixed)' if res.mode == 'sample' else '')} | "
             f"R-factor {res.rfactor:.4f} | N_idp {res.n_idp:.1f}, vars {res.nvarys}")
    L.append(("判定：" if zh else "Verdict: ") + res.verdict.summary(lang))
    mark = {"pass": "✓", "fail": "✗", "note": "·"}
    for i in res.verdict.items:
        L.append(f"  {mark[i.level]} " + html.unescape(i.zh if zh else i.en))
        if i.level == "fail" and (i.advice_zh if zh else i.advice_en):
            L.append("      → " + (i.advice_zh if zh else i.advice_en))
    return "\n".join(L)
