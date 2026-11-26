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
from .errors import ModelError

# ---------------------------------------------------------------- 阈值（设计：quick-fit-f2.md；不得放宽）
SHELL_GAP = 0.3         # Å：同一壳层内相邻路径的 Reff 间隔上限；≥ 此值（或异种元素）即另一壳层（≈ EXAFS 分辨率量级，与 GLOSSARY 的“第一壳层”一致）
RMIN_LO = 0.7           # Å：自动 Rmin 的搜索下端（低于它是 FT 低 R 的背景残余）
RMIN_BELOW_PEAK = 0.6   # Å：Rmin 不低于 R_p − 0.6（第一峰低 R 侧半宽约 0.4–0.5 Å；再往下是背景残余，Opus 2026-11-24 定）
RMIN_DEFAULT = 1.0      # Å：|χ(R)| 在 0.7 Å 到第一峰之间没有极小时的 Rmin；同时是第一峰搜索下端
RMAX_DEFAULT = 2.5      # Å：用户未给时的 Rmax
RMAX_DEFAULT_2PHASE = 3.0   # Å：有第二相（混合相）时用户未给的 Rmax（两相第一壳层相隔较远，如 Ir–O 1.9 Å + Ir–Ir 2.7 Å）
PEAK_KWEIGHT = 2        # 自动 Rmin / Rmax 检查用的 |χ(R)| 的 k 权重（k² 为处理默认；f2 简报未指定，见交接说明）
DEFAULT_KWEIGHT = [1, 2, 3]          # 与精细拟合新建模型的默认相同
R_CIF_TOL = 0.15        # Å：拟合 R 与 CIF 加权平均 Reff 之差的上限
N_RATIO_MAX = 1.5       # 样品 N ≤ 1.5·N_ref，超过多半是 N 与 σ² 互相补偿或标样 S0² 不适用
PEAK_SHIFT = (-0.8, 0.1)  # Å：|χ(R)| 第一峰 R_p − R_CIF 的合理范围（FT 未做相位校正，峰比真实距离短约 0.2–0.5 Å）；
                          # 超出 → 数据的主峰与所选结构的第一壳层不对应（Opus 2026-11-24 定，例：金属相样品配氧化物 FEFF）
PEAK_SHIFT_MIN = 0.2     # Å：FT 峰比真实距离短的最小量（未做相位校正，通常 0.2–0.5 Å）；混合相找第一峰的上端用
RMAX_LEAK = 0.30        # Rmax 处 |χ(R)| 超过第一峰的 30% → 窗口可能切进第二壳层
# 参数初值与范围（沿用精细拟合默认）
E0_INIT, E0_RANGE = 0.0, (-15.0, 15.0)
DR_INIT, DR_RANGE = 0.0, (-0.5, 0.5)
SS_INIT, SS_RANGE = 0.003, (0.0, 0.05)
S02_INIT, S02_RANGE = 0.85, (0.3, 1.5)
N_MAX_FACTOR = 2.0      # 样品模式 N 的范围 [0, 2·N_ref]
N_INIT_2PHASE = 0.5     # 混合相：两相 N 的初值各为 N_ref 的一半（单相为 N_ref）
MIN_K_SPAN = 6.0        # Å⁻¹：联合拟合公共 k 窗的最小宽度（再窄则 N_idp 太少，与 σ²、N 难以分开）


class QuickFitError(ModelError):
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


def peak_search_rmax(rmax, shell, shell2=None):
    """自动 Rmin 找第一峰的上端：单相 = Rmax（不变）；混合相 = min(Rmax, 两相较短 R_CIF − PEAK_SHIFT_MIN)，
    让第一峰是距离较短那一相的峰（例：Ir–O 1.98 Å 的峰约 1.6 Å，而不是 Ir–Ir 2.3 Å 的峰；后者的低 R 侧会盖住前者，
    若用后者，Rmin = R_p − 0.6 ≈ 1.7 Å 会把 Ir–O 切在窗外）。上端取 FT 峰相对真实距离的最小位移 0.2 Å。"""
    if shell2 is None:
        return rmax
    return min(rmax, min(shell.r_cif, shell2.r_cif) - PEAK_SHIFT_MIN)


def auto_rmin(r, chir_mag, rmax):
    """(Rmin, R_p)。R_p = |χ(R)| 在 [1.0 Å, rmax] 内最大值所在的 R；在 [0.7 Å, R_p] 找最小值，
    最小值落在 0.7 Å 端点（该范围内无极小，|χ(R)| 单调上升）或不在 R_p 之前 → Rmin = 1.0 Å；
    两种情况都不低于 R_p − RMIN_BELOW_PEAK（例：金属第一峰 2.3 Å、单调上升 → 1.7 Å，而非 1.0 Å）。"""
    r, m = np.asarray(r, float), np.asarray(chir_mag, float)
    r_p, _, _ = peak_stats(r, m, rmax)
    idx = np.flatnonzero((r >= RMIN_LO) & (r <= r_p))
    i = idx[int(np.argmin(m[idx]))]
    floor = round(r_p - RMIN_BELOW_PEAK, 4)
    if i == idx[0] or r[i] >= r_p:
        return max(RMIN_DEFAULT, floor), r_p
    return max(float(r[i]), floor), r_p


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


def default_rmax(two_phase=False):
    """用户未给 Rmax 时的缺省：混合相（有第二相）3.0 Å，否则 2.5 Å。"""
    return RMAX_DEFAULT_2PHASE if two_phase else RMAX_DEFAULT


def second_shell(shell, feff_dir, feff_dir2, root) -> FirstShell:
    """第二相的第一壳层：文件夹须不同于第一相，吸收原子须与第一相相同，否则 QuickFitError。"""
    from .feff_wrap import list_paths
    d1, d2 = resolve_feff_dir(feff_dir, root), resolve_feff_dir(feff_dir2, root)
    if d1.resolve() == d2.resolve():
        raise QuickFitError("第二相的 FEFF 文件夹与第一相相同 / the second-phase FEFF folder is the same as the first")
    sh2 = first_shell(list_paths(d2))
    if sh2.absorber != shell.absorber:
        raise QuickFitError(f"两相的吸收原子须相同：第一相 {shell.absorber}，第二相 {sh2.absorber} / "
                            f"both phases need the same absorber: {shell.absorber} vs {sh2.absorber}")
    return sh2


def _shell_paths(shell, root, n_name, dr, ss, sample_mode=True, taken=()):
    """一个相的路径行：成员的 N = <n_name>*degen/N_ref（样品模式）；label = 原 label@Reff（与已有重名则加 '）。"""
    out, used = [], set(taken)
    for m in shell.members:
        lab = f"{m['label']}@{m['reff']:.3f}"
        while lab in used:
            lab += "'"
        used.add(lab)
        p = dict(file=_rel_file(m["file"], root), label=lab, s02="s02", e0="e0", deltar=dr, sigma2=ss)
        if sample_mode:
            p["N"] = f"{n_name}*{m['degen']!r}/{shell.n_ref!r}"
        out.append(p)
    return out


def build_model(sample, feff_dir, rmax=None, mode="sample", s02=None, s02_source=None, rmin=None,
                krange=None, kweight=None, name=None, group=None, root=None, feff_dir2=None) -> dict:
    """建快速拟合的普通模型 dict。
    mode："standard"（标样：N = FEFF 简并度，S0² 拟合）或 "sample"（样品：S0² 固定为 s02，N 拟合）。
    krange：dict，可含 kmin/kmax/dk/window，覆盖样品处理设置里的 k 窗；kweight：列表（缺省 [1,2,3]）；rmin 缺省自动。
    group：该样品已处理的谱（缺省按项目配置现建；界面线程应传深拷贝）。s02_source：{"model","value","stderr"} 或
    {"manual": True, "value"}；样品模式未给则记为手填。
    feff_dir2：第二相（混合相，如金属 + 氧化物）的 FEFF 文件夹，只用于样品用途：两相各一个第一壳层，参数 n1 / dr1 / ss1 与
    n2 / dr2 / ss2（初值 N 各为 N_ref 的一半），ΔE0 共用；rmax 缺省 = default_rmax(有无第二相)。"""
    from . import paths, pipeline as pl
    from .feff_wrap import list_paths
    if feff_dir2 and mode == "standard":
        raise QuickFitError("标样用途只能用单相（不能加第二相） / Standard mode is single-phase only (no second phase)")
    if mode not in ("standard", "sample"):
        raise QuickFitError(f"mode 应为 standard / sample，实际 {mode!r} / mode must be standard or sample")
    if mode == "sample" and s02 is None:
        raise QuickFitError("样品模式需要 S0²（取自标样，或手填） / sample mode needs S0² (from a standard, or entered by hand)")
    root = Path(root) if root else paths.ROOT
    d = resolve_feff_dir(feff_dir, root)
    shell = first_shell(list_paths(d))
    shell2 = second_shell(shell, feff_dir, feff_dir2, root) if feff_dir2 else None
    if rmax is None:
        rmax = default_rmax(shell2 is not None)
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
        rmin, r_peak = auto_rmin(*_chir(g, win), peak_search_rmax(rmax, shell, shell2))
    rmin = float(rmin)
    if rmax - rmin < 0.3:
        raise QuickFitError(f"Rmin = {rmin:.2f}、Rmax = {rmax:.2f} Å 太窄 / the R window {rmin:.2f}–{rmax:.2f} Å is too narrow")
    kw = list(kweight) if kweight else list(DEFAULT_KWEIGHT)
    spec = lambda v, rg, vary=True: dict(value=v, vary=vary, min=rg[0], max=rg[1])    # noqa: E731
    params = {"e0": spec(E0_INIT, E0_RANGE), "dr1": spec(DR_INIT, DR_RANGE), "ss1": spec(SS_INIT, SS_RANGE)}
    if shell2 is not None:
        nspec = lambda sh: dict(value=N_INIT_2PHASE * sh.n_ref, vary=True, min=0.0, max=N_MAX_FACTOR * sh.n_ref)    # noqa: E731
        params = {"s02": dict(value=float(s02), vary=False), "n1": nspec(shell), "n2": nspec(shell2), **params,
                  "dr2": spec(DR_INIT, DR_RANGE), "ss2": spec(SS_INIT, SS_RANGE)}
    elif mode == "standard":
        params = {"s02": spec(S02_INIT, S02_RANGE), **params}
    else:
        params = {"s02": dict(value=float(s02), vary=False), "n1": dict(value=shell.n_ref, vary=True, min=0.0,
                                                                      max=N_MAX_FACTOR * shell.n_ref), **params}
    mpaths = _shell_paths(shell, root, "n1", "dr1", "ss1", mode == "sample")
    if shell2 is not None:
        mpaths += _shell_paths(shell2, root, "n2", "dr2", "ss2", True, taken=[p["label"] for p in mpaths])
    model = dict(name=name or f"QF_{sample}", sample=sample, kmin=win["kmin"], kmax=win["kmax"], dk=win["dk"],
                 window=win["window"], kweight=kw, rmin=rmin, rmax=rmax, fitspace="r", params=params, paths=mpaths,
                 norm=dict(c["norm"]), bkg=dict(c["bkg"]))
    if mode == "sample":
        model["s02_source"] = dict(s02_source) if s02_source else dict(manual=True, value=float(s02))
    model["quickfit"] = quickfit_key(mode, shell, root, shell2=shell2)
    return model


def _shell_key(shell, root):
    return dict(absorber=shell.absorber, scatterer=shell.scatterer, n_ref=shell.n_ref, r_cif=shell.r_cif,
                members=[dict(m, file=_rel_file(m["file"], root)) for m in shell.members])


def quickfit_key(mode, shell, root, windows=None, shell2=None) -> dict:
    """模型里的说明键 quickfit（计算忽略）：mode ∈ standard / sample / joint；shell = 第一壳层（趋势表用 r_cif 与 n_ref）。
    windows（联合）：{数据集 id: 该样品自己的处理 k 窗}，判定里据此提示 dk / 窗函数不一致。
    shell2（混合相）：第二相的第一壳层，与 shell 同形；单相模型没有这个键。"""
    k = dict(mode=mode, shell=_shell_key(shell, root))
    if shell2 is not None:
        k["shell2"] = _shell_key(shell2, root)
    if windows:
        k["windows"] = windows
    return k


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
    "peak_pos": ("数据 |χ(R)| 的主峰位置与所选结构的第一壳层对不上：检查 FEFF 用的结构（CIF）是否对应这个样品（例如样品是否为金属 / 合金相，或第一近邻是别的元素）。",
                 ("The main |χ(R)| peak of the data does not match the first shell of the chosen structure: check that the FEFF structure (CIF) "
                  "matches this sample (e.g. a metal / alloy phase, or another element as nearest neighbour).")),
    "rmax_leak": ("Rmax 偏大，窗口可能切进第二壳层；把 Rmax 往小调再试。",
                  "Rmax is too large and the window may cut into the second shell; lower Rmax and retry."),
}


def _shell_items(rows, n, shell, mode, rmax, peak_amp, amp_at_rmax, r_peak=None):
    """第一壳层专有的三项检查（单样品与联合的每个样品共用）：R 与结构之差、N / N_ref（样品模式，n 为拟合 N）、Rmax 处残余。
    rows：该样品的路径行（与 shell.members 同序）。"""
    items = []
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
        ok = n <= N_RATIO_MAX * shell.n_ref
        items.append(VerdictItem("pass" if ok else "fail", "n_ratio",
                                 f"N = {n:.2f}，结构值 {shell.n_ref:g}（{n / shell.n_ref:.2f} 倍）"
                                 + ("" if ok else f"：超过 {N_RATIO_MAX} 倍"),
                                 f"N = {n:.2f} vs structure {shell.n_ref:g} ({n / shell.n_ref:.2f}×)"
                                 + ("" if ok else f": beyond {N_RATIO_MAX}×"),
                                 *(("", "") if ok else ADVICE["n_ratio"])))
    if r_peak is not None:
        dp = r_peak - shell.r_cif
        ok = PEAK_SHIFT[0] <= dp <= PEAK_SHIFT[1]
        items.append(VerdictItem("pass" if ok else "fail", "peak_pos",
                                 f"数据第一峰在 {r_peak:.2f} Å，结构第一壳层 {shell.r_cif:.2f} Å"
                                 + ("（位置相符）" if ok else "：位置对不上（FT 峰通常比真实距离短 0.2–0.5 Å）"),
                                 f"Data first peak at {r_peak:.2f} Å, structure first shell {shell.r_cif:.2f} Å"
                                 + (" (consistent)" if ok else ": they do not match (FT peaks usually sit 0.2–0.5 Å below the true distance)"),
                                 *(("", "") if ok else ADVICE["peak_pos"])))
    if peak_amp is not None and amp_at_rmax is not None:
        frac = amp_at_rmax / peak_amp if peak_amp > 0 else math.inf
        ok = frac <= RMAX_LEAK
        items.append(VerdictItem("pass" if ok else "fail", "rmax_leak",
                                 f"Rmax = {rmax:g} Å 处 |χ(R)| 是第一峰的 {frac * 100:.0f}%"
                                 + ("" if ok else f"：超过 {RMAX_LEAK * 100:.0f}%，窗口可能切进第二壳层"),
                                 f"|χ(R)| at Rmax = {rmax:g} Å is {frac * 100:.0f}% of the first peak"
                                 + ("" if ok else f": beyond {RMAX_LEAK * 100:.0f}%; the window may cut into the second shell"),
                                 *(("", "") if ok else ADVICE["rmax_leak"])))
    return items


def _tag(sh, i):
    """混合相条目的前缀：相 1（Ir–O）：/ Phase 1 (Ir–O):"""
    return f"相 {i}（{sh.absorber}–{sh.scatterer}）：", f"Phase {i} ({sh.absorber}–{sh.scatterer}): "


def _shell_items_two(rows, n1, n2, shell, shell2, rmax, peak_amp, amp_at_rmax, r_peak):
    """混合相（两相第一壳层）的检查：每相各做 r_cif 与 n_ratio（文字加“相 1 / 相 2（Ir–O / Ir–Ir）”前缀）；
    peak_pos：数据第一峰与任一相的 R_CIF 满足 PEAK_SHIFT 即通过；rmax_leak 只作提示；note：各相比例 N / N_ref，仅供参考。
    rows：该样品的路径行（相 1 的成员在前，相 2 的在后）。阈值与单相相同。"""
    k = len(shell.members)
    got = _shell_items(rows[:k], n1, shell, "sample", rmax, peak_amp, amp_at_rmax, None)
    got2 = _shell_items(rows[k:], n2, shell2, "sample", rmax, None, None, None)
    out = []
    for code in ("r_cif", "n_ratio"):
        for sh, lst, i in ((shell, got, 1), (shell2, got2, 2)):
            for it in lst:
                if it.code == code:
                    z, e = _tag(sh, i)
                    it.zh, it.en = z + it.zh, e + it.en
                    out.append(it)
    if r_peak is not None:
        dps = [r_peak - sh.r_cif for sh in (shell, shell2)]
        hit = [i + 1 for i, d in enumerate(dps) if PEAK_SHIFT[0] <= d <= PEAK_SHIFT[1]]
        ok = bool(hit)
        out.append(VerdictItem("pass" if ok else "fail", "peak_pos",
                               f"数据第一峰在 {r_peak:.2f} Å，结构第一壳层 相 1 {shell.r_cif:.2f} Å / 相 2 {shell2.r_cif:.2f} Å"
                               + (f"（与相 {hit[0]} 位置相符）" if ok else "：与两相都对不上（FT 峰通常比真实距离短 0.2–0.5 Å）"),
                               f"Data first peak at {r_peak:.2f} Å, structure first shells phase 1 {shell.r_cif:.2f} Å / phase 2 "
                               f"{shell2.r_cif:.2f} Å" + (f" (consistent with phase {hit[0]})" if ok
                                                          else ": matches neither (FT peaks usually sit 0.2–0.5 Å below the true distance)"),
                               *(("", "") if ok else ADVICE["peak_pos"])))
    for it in got:
        if it.code == "rmax_leak":      # 混合相只作提示：较长一相（如金属 Ir–Ir，重散射体的第一峰是宽双峰）的峰到 3 Å 仍高，
            if it.level == "fail":      # 比例超过 30% 多半是这个峰本身，不是切进第二壳层（IrTa 原位 Ir 边实测 3.0 Å 处约 55%）
                it.level, it.advice_zh, it.advice_en = "note", "", ""
                it.zh += "（混合相只作提示：较长一相的第一峰较宽，确认 Rmax 没有切进它的第二壳层即可）"
                it.en += " (a note for mixed phases: the longer phase's first peak is broad; just make sure Rmax does not cut into its second shell)"
            out.append(it)
    f1, f2 = n1 / shell.n_ref, n2 / shell2.n_ref
    out.append(VerdictItem("note", "phase_frac",
                           f"各相比例 N / N_ref：相 1（{shell.absorber}–{shell.scatterer}）≈ {f1:.2f}，相 2（{shell2.absorber}–{shell2.scatterer}）"
                           f"≈ {f2:.2f}；相 2 比例 ≈ {f2:.2f}，仅供参考（N 与 σ² 相关，且 FEFF 振幅与实际有出入）",
                           f"Phase fractions N / N_ref: phase 1 ({shell.absorber}–{shell.scatterer}) ≈ {f1:.2f}, phase 2 "
                           f"({shell2.absorber}–{shell2.scatterer}) ≈ {f2:.2f}; the phase-2 fraction ≈ {f2:.2f} is indicative only "
                           f"(N and σ² are correlated and FEFF amplitudes are approximate)"))
    return out


def _others_note(shell, shell2=None):
    """第一层里还有异种元素的提示条目（混合相时两相各自的，带相前缀）。"""
    out = []
    for i, sh in enumerate((shell, shell2), 1):
        if sh is None or not sh.other_elements:
            continue
        els = ", ".join(f"{e}（{r:.2f} Å）" for e, r in sh.other_elements)
        els_en = ", ".join(f"{e} ({r:.2f} Å)" for e, r in sh.other_elements)
        z, e = _tag(sh, i) if shell2 is not None else ("", "")
        out.append(VerdictItem("note", "other_elements", f"{z}第一层还有 {els}，未考虑", f"{e}The first layer also has {els_en}, not included"))
    return out


def _uncal_item(who=None):
    """meta.csv 的 ref_file = none（没有参比）：只作 note，不判失败。who：联合拟合里受影响的样品名"""
    z = "、".join(who) + " " if who else ""
    e = ", ".join(who) + ": " if who else ""
    return VerdictItem("note", "uncalibrated", f"{z}未按参比校准：ΔE0 与边位绝对值不可靠，R 与 N 不受影响",
                       f"{e}Not calibrated against a reference: ΔE0 and the absolute edge position are unreliable; R and N are not affected")


def verdict(fit, shell, mode, rmax, peak_amp=None, amp_at_rmax=None, s02_source=None, r_peak=None, shell2=None,
            uncalibrated=False) -> Verdict:
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
    n = summ["params"]["n1"]["value"] if mode == "sample" else None
    if shell2 is not None:
        items += _shell_items_two(summ["paths"], n, summ["params"]["n2"]["value"], shell, shell2, rmax, peak_amp, amp_at_rmax, r_peak)
    else:
        items += _shell_items(summ["paths"], n, shell, mode, rmax, peak_amp, amp_at_rmax, r_peak)
    if mode == "sample" and (s02_source or {}).get("manual"):
        items.append(VerdictItem("note", "manual_s02", f"手动 S0² = {s02_source['value']:g}，没有标样依据",
                                 f"Manual S0² = {s02_source['value']:g}, no standard behind it"))
    if uncalibrated:
        items.append(_uncal_item())
    items += _others_note(shell, shell2)
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
    phase2: dict | None = None  # 混合相：第二相的 n, n_err, r, r_err, sigma2, sigma2_err, frac（= n / N_ref）, shell2；单相为 None。
                                # 上面的 n / r / sigma2 … 仍是相 1


def shells_of_model(model, root=None):
    """由快速拟合模型还原 (第一相的第一壳层, 第二相的第一壳层或 None)（读模型路径所在的 FEFF 文件夹）。
    混合相模型（quickfit 键里有 shell2）：路径 = 相 1 的成员 + 相 2 的成员，相 2 的文件夹取第一条不属于相 1 的路径所在的文件夹。"""
    from . import paths
    from .feff_wrap import list_paths
    root = Path(root) if root else paths.ROOT
    blocks = [d["paths"] for d in model["datasets"]] if "datasets" in model else [model["paths"]]
    absf = lambda x: Path(x) if Path(x).is_absolute() else root / x    # noqa: E731
    sh = first_shell(list_paths(absf(blocks[0][0]["file"]).parent))
    want = [Path(x).name for x in sh.files]
    bad = QuickFitError("模型的路径不是该 FEFF 文件夹的第一壳层（模型被改过？），请在精细拟合里查看 / "
                        "the model paths are not the first shell of their FEFF folder (edited?); open it in Detailed fit")
    if not isinstance((model.get("quickfit") or {}).get("shell2"), dict):
        if any([Path(p["file"]).name for p in b] != want for b in blocks):
            raise bad
        return sh, None
    k = len(want)
    if len(blocks[0]) <= k:
        raise bad
    sh2 = first_shell(list_paths(absf(blocks[0][k]["file"]).parent))
    want2 = [Path(x).name for x in sh2.files]
    if any([Path(p["file"]).name for p in b] != want + want2 for b in blocks):
        raise bad
    return sh, sh2


def shell_of_model(model, root=None) -> FirstShell:
    """由快速拟合模型还原第一壳层（混合相模型取相 1；两相见 shells_of_model）。"""
    return shells_of_model(model, root)[0]


def run(model, group=None, root=None) -> QuickResult:
    """拟合并判定。group：该样品已处理的谱（缺省现建）；不保存任何文件（调用方决定，fit 记录可进会话历史）。
    联合模型（有 datasets）→ 转 run_joint（group 此时是 {数据集 id: 谱}），返回 JointResult。"""
    from . import fit_exafs as fx, pipeline as pl
    if "datasets" in model:
        return run_joint(model, group, root)
    sample = model["sample"]
    g = group if group is not None else pl.build_sample(sample)[0]
    shell, shell2 = shells_of_model(model, root)
    n1 = model["params"].get("n1")
    mode = "sample" if n1 is not None else "standard"
    win = {k: model[k] for k in ("kmin", "kmax", "dk", "window")}
    r_pk, pk, at_rmax = peak_stats(*_chir(g, win), model["rmax"])
    with _two_phase_guard(shell2 is not None):
        res, dset, summ = fx.run_fit(g, model, root)
    fit = dict(model=model, summ=summ, result=res, curves=fx.model_curves(dset), report=fx.report_text(res),
               time=datetime.now().strftime("%H:%M:%S"))
    v = verdict(fit, shell, mode, model["rmax"], pk, at_rmax, model.get("s02_source"), r_pk, shell2,
                uncalibrated=bool(getattr(g, "uncalibrated", False)))
    P = summ["params"]

    def pv(k):
        return (P[k]["value"], P[k]["stderr"]) if k in P else (None, None)
    r_fit = sum(m["degen"] * p["R"] for m, p in zip(shell.members, summ["paths"])) / shell.n_ref
    n_v, n_e = pv("n1") if mode == "sample" else (shell.n_ref, None)
    ph2 = None
    if shell2 is not None:
        ph2 = _phase2(shell2, summ["paths"][len(shell.members):], *pv("n2"), pv("dr2")[1], *pv("ss2"))
    return QuickResult(sample, mode, model, shell, n_v, n_e, r_fit, pv("dr1")[1], *pv("ss1"), *pv("e0"),
                       *(pv("s02") if mode == "standard" else (P["s02"]["value"], None)),
                       summ["rfactor"], summ["n_idp"], summ["nvarys"],
                       dict(win, kweight=model["kweight"], rmin=model["rmin"], rmax=model["rmax"]), v, fit, r_pk, pk, at_rmax, ph2)


class _two_phase_guard:
    """混合相拟合的协方差矩阵奇异（变量太多或参数被边界卡住）时，larch 在算误差时抛 LinAlgError：转成说得清楚的 QuickFitError。
    单相不经过这里，行为不变。"""
    def __init__(self, active):
        self.active = active

    def __enter__(self):
        return self

    def __exit__(self, et, ev, tb):
        if self.active and et is not None and issubclass(et, np.linalg.LinAlgError):
            raise QuickFitError("两相拟合的协方差矩阵无法计算：变量相对数据太多（单样品七个自由参数），或参数被边界卡住；"
                                "改用联合拟合（多个样品共享 dr、σ²）、缩小 Rmax 或检查两相结构 / the covariance matrix of the "
                                "two-phase fit could not be computed: too many variables for the data (seven free parameters for "
                                "one sample) or a parameter stuck at its bound; use a joint fit (several samples share dr, σ²), "
                                "adjust Rmax, or check the two structures") from ev
        return False


def _phase2(shell2, rows, n, n_err, dr_err, ss, ss_err) -> dict:
    """第二相的结果字典：R = 该相成员的简并度加权 R（拟合后），frac = N / N_ref。"""
    r = sum(m["degen"] * p["R"] for m, p in zip(shell2.members, rows)) / shell2.n_ref
    return dict(n=n, n_err=n_err, r=r, r_err=dr_err, sigma2=ss, sigma2_err=ss_err, frac=n / shell2.n_ref, shell2=shell2)


def format_text(res: QuickResult, lang="zh") -> str:
    """一个样品的结果与判定（CLI 用；HTML 实体已还原）。"""
    zh = lang == "zh"
    s, w = res.shell, res.window
    ex = lambda v, e, f: (f"{v:{f}}" if e is None else f"{v:{f}} ± {e:{f}}") if v is not None else "-"    # noqa: E731
    L = [f"== {res.sample}（{'标样' if res.mode == 'standard' else '样品'}）" if zh else
         f"== {res.sample} ({res.mode})",
         ("第一壳层：" if zh else "First shell: ") + f"{s.absorber}–{s.scatterer}, N_ref = {s.n_ref:g}, R_CIF = {s.r_cif:.3f} Å"]
    L += [f"    {m['label']}  Reff {m['reff']:.4f}  degen {m['degen']:g}  {Path(m['file']).name}" for m in s.members]
    if res.phase2:
        s2_ = res.phase2["shell2"]
        L.append(("第二相第一壳层：" if zh else "Second-phase first shell: ") + f"{s2_.absorber}–{s2_.scatterer}, N_ref = {s2_.n_ref:g}, "
                 f"R_CIF = {s2_.r_cif:.3f} Å")
        L += [f"    {m['label']}  Reff {m['reff']:.4f}  degen {m['degen']:g}  {Path(m['file']).name}" for m in s2_.members]
    L.append(f"k {w['kmin']:g}–{w['kmax']:g} (dk {w['dk']:g}, {w['window']}), kweight {w['kweight']}, "
             f"R {w['rmin']:.2f}–{w['rmax']:.2f} Å" + (f"（自动 Rmin，第一峰 {res.r_peak:.2f} Å）" if zh and res.r_peak
                                                       else (f" (first peak {res.r_peak:.2f} Å)" if res.r_peak else "")))
    L.append(f"N {ex(res.n, res.n_err, '.2f')} | R {ex(res.r, res.r_err, '.4f')} Å | σ² {ex(res.sigma2, res.sigma2_err, '.5f')} Å² | "
             f"ΔE0 {ex(res.e0, res.e0_err, '.2f')} eV | S0² {ex(res.s02, res.s02_err, '.3f')}"
             f"{'（固定）' if res.mode == 'sample' and zh else (' (fixed)' if res.mode == 'sample' else '')} | "
             f"R-factor {res.rfactor:.4f} | N_idp {res.n_idp:.1f}, vars {res.nvarys}")
    if res.phase2:
        p2 = res.phase2
        L.append(("相 2：" if zh else "Phase 2: ") + f"N {ex(p2['n'], p2['n_err'], '.2f')} | R {ex(p2['r'], p2['r_err'], '.4f')} Å | "
                 f"σ² {ex(p2['sigma2'], p2['sigma2_err'], '.5f')} Å² | " + ("比例 N/N_ref" if zh else "fraction N/N_ref") + f" {p2['frac']:.2f}")
    L.append(("判定：" if zh else "Verdict: ") + res.verdict.summary(lang))
    mark = {"pass": "✓", "fail": "✗", "note": "·"}
    for i in res.verdict.items:
        L.append(f"  {mark[i.level]} " + html.unescape(i.zh if zh else i.en))
        if i.level == "fail" and (i.advice_zh if zh else i.advice_en):
            L.append("      → " + (i.advice_zh if zh else i.advice_en))
    return "\n".join(L)


# ================================================================ 联合快速拟合
# 选 ≥ 2 个样品（样品用途）→ 一个联合模型：S0² 固定；ΔE0（e0）全批共享；每个样品各自 n1_<id>、dr1_<id>、ss1_<id>。
# 窗口全批统一：k 窗 = 各样品处理设置的交集，Rmin = 各样品自动 Rmin 的最大值，Rmax 用户给。
# Joint quick fit: one model for ≥ 2 samples; S0² fixed, one shared ΔE0, per-sample N / ΔR / σ²; one common k window
# (intersection of the processing windows), Rmin = the largest automatic Rmin, Rmax from the user.
def joint_param_names(ds_id, two_phase=False) -> dict:
    """数据集 id → 联合模型里该样品的参数名（id 里不是字母数字下划线的字符换成 _）。
    混合相（two_phase）：每样品只有 n1_<id>、n2_<id>；dr1、ss1、dr2、ss2 全批共享（两相的 N–σ² 强相关，共享才稳），
    返回里的 dr / ss / dr2 / ss2 是这些共享名。"""
    s = re.sub(r"\W", "_", str(ds_id))
    if two_phase:
        return dict(n=f"n1_{s}", n2=f"n2_{s}", dr="dr1", ss="ss1", dr2="dr2", ss2="ss2")
    return dict(n=f"n1_{s}", dr=f"dr1_{s}", ss=f"ss1_{s}")


def _own_names(ds_id, two_phase=False) -> dict:
    """只属于一个样品的参数名（混合相时是 n1_<id>、n2_<id>；共享的 dr / ss 不算）。"""
    d = joint_param_names(ds_id, two_phase)
    return {k: d[k] for k in (("n", "n2") if two_phase else ("n", "dr", "ss"))}


def common_k_window(wins: dict):
    """wins：{数据集 id: {kmin,kmax,dk,window}}（该样品的处理设置）→ 公共 k 窗 dict。
    kmin 取最大、kmax 取最小；dk / 窗函数取第一个样品的（不一致由判定 note 提示）；宽度 < MIN_K_SPAN → QuickFitError。"""
    first = next(iter(wins.values()))
    kmin = max(w["kmin"] for w in wins.values())
    kmax = min(w["kmax"] for w in wins.values())
    if kmax - kmin < MIN_K_SPAN:
        det = "；".join(f"{i}: {w['kmin']:g}–{w['kmax']:g}" for i, w in wins.items())
        det_en = "; ".join(f"{i}: {w['kmin']:g}–{w['kmax']:g}" for i, w in wins.items())
        raise QuickFitError(f"各样品处理 k 窗的交集是 {kmin:g}–{kmax:g} Å⁻¹，不足 {MIN_K_SPAN:g} Å⁻¹，无法联合拟合（{det}）。"
                            f"请先在“处理”里统一 k 窗，或分别快速拟合 / "
                            f"the intersection of the processing k windows is {kmin:g}–{kmax:g} Å⁻¹, below {MIN_K_SPAN:g} Å⁻¹; "
                            f"a joint fit is not possible ({det_en}). Unify the k windows in Processing, or quick-fit them one by one")
    return dict(kmin=kmin, kmax=kmax, dk=first["dk"], window=first["window"])


def build_joint_model(samples, feff_dir, rmax=None, s02=None, s02_source=None, rmin=None, krange=None,
                      kweight=None, name=None, groups=None, root=None, feff_dir2=None) -> dict:
    """联合快速拟合的模型 dict（多数据集格式，数据集 id = pipeline.safe(样品)）。样品必须 ≥ 2 个、同一吸收边、共用 FEFF 与 S0²。
    groups：{数据集 id 或样品名: 已处理的谱}（界面线程应传深拷贝；缺的现建）。krange 覆盖公共 k 窗；rmin 缺省 = 各样品自动 Rmin 的最大值
    （用公共 k 窗算）。参数初值与范围同单样品样品模式；n1 初值 N_ref、范围 [0, 2·N_ref]。
    feff_dir2：第二相（混合相）：每样品 n1_<id>、n2_<id>（初值各 N_ref/2），dr1、ss1、dr2、ss2 全批共享；rmax 缺省 3.0（无第二相 2.5）。"""
    from . import paths, pipeline as pl
    from .feff_wrap import list_paths
    samples = list(dict.fromkeys(samples))
    if len(samples) < 2:
        raise QuickFitError("联合拟合需要至少 2 个样品 / a joint fit needs at least 2 samples")
    if s02 is None:
        raise QuickFitError("联合拟合需要 S0²（取自标样，或手填） / a joint fit needs S0² (from a standard, or entered by hand)")
    root = Path(root) if root else paths.ROOT
    shell = first_shell(list_paths(resolve_feff_dir(feff_dir, root)))
    shell2 = second_shell(shell, feff_dir, feff_dir2, root) if feff_dir2 else None
    two = shell2 is not None
    if rmax is None:
        rmax = default_rmax(two)
    cfg, meta = pl.load_config(), pl.load_meta()
    ids = {sm: pl.safe(sm) for sm in samples}
    pn = {i: joint_param_names(i, two) for i in ids.values()}
    own = {i: _own_names(i, two) for i in ids.values()}
    if len(set(ids.values())) < len(samples) or len({v for d in own.values() for v in d.values()}) < len(own[next(iter(own))]) * len(samples):
        raise QuickFitError("样品名清理后重名（只含字母数字、点、横线、下划线的部分相同） / sample names collide after cleaning")
    wins, eks = {}, set()
    for sm, i in ids.items():
        rows = meta[(meta["sample"] == sm) & (meta["use"] != "0")]
        if not len(rows):
            raise QuickFitError(f"meta.csv 中没有可用的样品 {sm} / no usable sample {sm} in meta.csv")
        ek = rows.edge_key.iloc[0]
        eks.add(ek)
        c, wins[i] = _ft_window(cfg, ek, sm)
        el = c.get("element")
        if el and shell.absorber and el != shell.absorber:
            raise QuickFitError(f"FEFF 的吸收原子是 {shell.absorber}，样品 {sm} 的吸收边是 {ek} / "
                                f"the FEFF absorber is {shell.absorber} but sample {sm} is on {ek}")
    if len(eks) > 1:
        raise QuickFitError(f"联合拟合的样品必须同一吸收边，实际有 {', '.join(sorted(eks))} / "
                            f"samples of a joint fit must share one absorption edge, got {', '.join(sorted(eks))}")
    win = common_k_window(wins)
    if krange:
        win.update({k: v for k, v in krange.items() if k in win and v is not None})
        if win["kmax"] - win["kmin"] < MIN_K_SPAN:
            raise QuickFitError(f"k 窗 {win['kmin']:g}–{win['kmax']:g} Å⁻¹ 不足 {MIN_K_SPAN:g} Å⁻¹ / "
                                f"the k window {win['kmin']:g}–{win['kmax']:g} Å⁻¹ is below {MIN_K_SPAN:g} Å⁻¹")
    rmax = float(rmax)
    if rmin is None:
        rmins = []
        for sm, i in ids.items():
            g = (groups or {}).get(i) or (groups or {}).get(sm)
            if g is None:
                g = pl.build_sample(sm, cfg, meta)[0]
            rmins.append(auto_rmin(*_chir(g, win), peak_search_rmax(rmax, shell, shell2))[0])
        rmin = max(rmins)
    rmin = float(rmin)
    if rmax - rmin < 0.3:
        raise QuickFitError(f"Rmin = {rmin:.2f}、Rmax = {rmax:.2f} Å 太窄 / the R window {rmin:.2f}–{rmax:.2f} Å is too narrow")
    spec = lambda v, rg: dict(value=v, vary=True, min=rg[0], max=rg[1])    # noqa: E731
    params = {"s02": dict(value=float(s02), vary=False), "e0": spec(E0_INIT, E0_RANGE)}
    for i in ids.values():
        if two:
            for key, sh in (("n", shell), ("n2", shell2)):
                params[pn[i][key]] = dict(value=N_INIT_2PHASE * sh.n_ref, vary=True, min=0.0, max=N_MAX_FACTOR * sh.n_ref)
            continue
        params[pn[i]["n"]] = dict(value=shell.n_ref, vary=True, min=0.0, max=N_MAX_FACTOR * shell.n_ref)
        params[pn[i]["dr"]] = spec(DR_INIT, DR_RANGE)
        params[pn[i]["ss"]] = spec(SS_INIT, SS_RANGE)
    if two:
        for k in ("dr1", "ss1", "dr2", "ss2"):
            params[k] = spec(*((DR_INIT, DR_RANGE) if k.startswith("dr") else (SS_INIT, SS_RANGE)))
    datasets = []
    for sm, i in ids.items():
        mp = _shell_paths(shell, root, pn[i]["n"], pn[i]["dr"], pn[i]["ss"])
        if two:
            mp += _shell_paths(shell2, root, pn[i]["n2"], pn[i]["dr2"], pn[i]["ss2"], taken=[p["label"] for p in mp])
        datasets.append(dict(id=i, sample=sm, paths=mp))
    model = dict(name=name or f"QF_joint_{ids[samples[0]]}__{ids[samples[-1]]}", kmin=win["kmin"], kmax=win["kmax"],
                 dk=win["dk"], window=win["window"], kweight=list(kweight) if kweight else list(DEFAULT_KWEIGHT),
                 rmin=rmin, rmax=rmax, fitspace="r", params=params, datasets=datasets,
                 s02_source=dict(s02_source) if s02_source else dict(manual=True, value=float(s02)))
    model["quickfit"] = quickfit_key("joint", shell, root, windows=wins, shell2=shell2)
    return model


@dataclass
class JointVerdict:
    """两层判定：items = 整批条目；samples = {数据集 id: Verdict}（每个样品自己的条目）。任一 fail → ok = False。"""
    ok: bool
    items: list
    samples: dict

    @property
    def failed(self):
        return [i for i in self.items if i.level == "fail"]

    @property
    def notes(self):
        return [i for i in self.items if i.level == "note"]

    @property
    def failed_samples(self):
        return [k for k, v in self.samples.items() if not v.ok]

    def summary(self, lang="zh"):
        zh = lang == "zh"
        if self.ok:
            return "✅ 整批可信" if zh else "✅ Batch trustworthy"
        bad = self.failed_samples
        pz = ([f"整批 {len(self.failed)} 项"] if self.failed else []) + ([f"样品 {', '.join(bad)}"] if bad else [])
        pe = ([f"batch: {len(self.failed)} issue(s)"] if self.failed else []) + ([f"sample(s) {', '.join(bad)}"] if bad else [])
        return ("⚠ 需注意：" + "；".join(pz)) if zh else ("⚠ To look at: " + "; ".join(pe))


_BATCH_CODES = ("rfactor", "nvarys", "nvarys_low_info", "e0", "correl", "single_k")
_BATCH_PARAM_CODES = ("err_none", "err_big", "at_bound")
_SAMPLE_CODES = ("rfactor", "err_none", "err_big", "at_bound", "sigma2_neg", "sigma2_big", "sigma2_ok", "dr")


def _items(checks, codes):
    out = []
    for c in checks:
        if c.code in codes:
            lvl = "note" if c.ok is None else ("pass" if c.ok else "fail")
            a = ADVICE.get(c.code, ("", "")) if lvl == "fail" else ("", "")
            out.append(VerdictItem(lvl, c.code, c.zh, c.en, *a))
    return out


def _restrict(summ, ds_id, names):
    """联合摘要 → 只含一个样品的路径与参数、该样品自己的 R 因子与 N_idp 的摘要（fitcheck 的逐样品检查用）。"""
    row = next(r for r in summ["datasets"] if r["id"] == ds_id)
    keep = set(names.values())
    return dict(summ, params={k: v for k, v in summ["params"].items() if k in keep},
                paths=[p for p in summ["paths"] if p.get("dataset") == ds_id], rfactor=row["rfactor"],
                n_idp=row["n_idp"], sample=row["sample"], dataset=ds_id)


def verdict_joint(fit, shell, rmax, peaks, s02_source=None, windows=None, r_peaks=None, shell2=None, uncalibrated=()) -> JointVerdict:
    """联合模型的两层判定。fit：run_joint 的拟合记录（多数据集 summ）；peaks：{数据集 id: (第一峰高, Rmax 处 |χ(R)|)}；
    windows：{id: 该样品自己的处理 k 窗}（dk / 窗函数不一致 → note）。
    整批：总 R 因子、Stern 准则（对 Σ N_idp）、ΔE0 及其误差 / 边界、强相关；每个样品：自己的 R 因子、R 与结构之差、N 倍数、
    Rmax 处残余、自己参数（n1 / dr1 / ss1）的误差与边界、σ² 与 ΔR 是否合理。手动 S0²、第一层异种元素、窗口参数不一致只作整批 note。"""
    summ = fit["summ"]
    P = summ["params"]
    two = shell2 is not None
    own = {r["id"]: _own_names(r["id"], two) for r in summ["datasets"]}
    mine = {v for d in own.values() for v in d.values()}
    items = _items(fitcheck.fit_checks(fit, None, stern=True, robust_hint=False), _BATCH_CODES)
    shared = dict(fit, summ=dict(summ, params={k: v for k, v in P.items() if k not in mine}))
    items += _items(fitcheck.fit_checks(shared, None, stern=True, robust_hint=False), _BATCH_PARAM_CODES)
    if (s02_source or {}).get("manual"):
        items.append(VerdictItem("note", "manual_s02", f"手动 S0² = {s02_source['value']:g}，没有标样依据",
                                 f"Manual S0² = {s02_source['value']:g}, no standard behind it"))
    if uncalibrated:
        items.append(_uncal_item(list(uncalibrated)))
    items += _others_note(shell, shell2)
    ws = list((windows or {}).items())
    if ws and any((w["dk"], w["window"]) != (ws[0][1]["dk"], ws[0][1]["window"]) for _, w in ws):
        items.append(VerdictItem("note", "window_mismatch",
                                 f"各样品处理的 dk / 窗函数不一致，联合拟合统一用 {ws[0][0]} 的（dk {ws[0][1]['dk']:g}，{ws[0][1]['window']}）",
                                 f"The processing dk / window function differ between samples; the joint fit uses those of {ws[0][0]} "
                                 f"(dk {ws[0][1]['dk']:g}, {ws[0][1]['window']})"))
    per = {}
    for r in summ["datasets"]:
        i = r["id"]
        v = dict(fit, summ=_restrict(summ, i, own[i]))
        sit = _items(fitcheck.fit_checks(v, None, stern=True, robust_hint=False), _SAMPLE_CODES)
        rows = [p for p in summ["paths"] if p.get("dataset") == i]
        pk, at = peaks.get(i, (None, None))
        if two:
            sit += _shell_items_two(rows, P[own[i]["n"]]["value"], P[own[i]["n2"]]["value"], shell, shell2, rmax, pk, at, (r_peaks or {}).get(i))
        else:
            sit += _shell_items(rows, P[own[i]["n"]]["value"], shell, "sample", rmax, pk, at, (r_peaks or {}).get(i))
        per[i] = Verdict(not any(x.level == "fail" for x in sit), sit)
    ok = not any(x.level == "fail" for x in items) and all(v.ok for v in per.values())
    return JointVerdict(ok, items, per)


@dataclass
class JointResult:
    model: dict
    shell: FirstShell
    samples: list               # [QuickResult]，每个样品一个（其 .fit 是同一个联合拟合记录，.verdict 是该样品的 Verdict）
    e0: float
    e0_err: float | None
    s02: float
    rfactor: float              # 联合
    n_idp: float                # Σ N_idp
    nvarys: int
    window: dict                # kmin, kmax, dk, window, kweight, rmin, rmax（全批统一）
    verdict: JointVerdict
    fit: dict                   # run_model 同形（multi=True）：model, summ, result, curves, report, time；可进会话历史 / 图片导出
    r_rmin: dict = field(default_factory=dict)   # {数据集 id: 该样品自己的自动 Rmin}；公共 Rmin = 其最大值（Rmin 由用户给时仅供参考）
    shell2: FirstShell | None = None             # 混合相：第二相的第一壳层；单相为 None

    def trend(self, meta=None, processed=None):
        """趋势表（trend.trend_table；缺省读当前项目的 meta.csv 与 process_summary.csv）。"""
        from . import trend as tr
        if meta is None and processed is None:
            meta, processed = tr.load_project_tables()
        return tr.trend_table(self.fit["summ"], self.model, meta, processed)


def run_joint(model, groups=None, root=None) -> JointResult:
    """联合拟合并判定。groups：{数据集 id: 已处理的谱}（缺的现建）；不保存任何文件。"""
    from . import fit_exafs as fx, pipeline as pl
    nm = fx.normalize_model(model)
    shell, shell2 = shells_of_model(model, root)
    two = shell2 is not None
    qk = model.get("quickfit") or {}
    win = {k: model[k] for k in ("kmin", "kmax", "dk", "window")}
    groups = dict(groups or {})
    built = {}
    for d in nm["datasets"]:
        if d["id"] not in groups:
            if d["sample"] not in built:
                built[d["sample"]] = pl.build_sample(d["sample"])[0]
            groups[d["id"]] = built[d["sample"]]
    peaks, rmins, rps = {}, {}, {}
    for d in nm["datasets"]:
        r, m = _chir(groups[d["id"]], win)
        rps[d["id"]], pk, at = peak_stats(r, m, model["rmax"])
        peaks[d["id"]] = (pk, at)
        rmins[d["id"]] = auto_rmin(r, m, peak_search_rmax(model["rmax"], shell, shell2))[0]
    with _two_phase_guard(two):
        res, dsets, summ = fx.fit_multi(groups, model, root)
    fit = dict(model=model, summ=summ, result=res, curves=fx.model_curves_all(dsets, nm), report=fx.report_text(res),
               time=datetime.now().strftime("%H:%M:%S"), multi=True)
    v = verdict_joint(fit, shell, model["rmax"], peaks, model.get("s02_source"), qk.get("windows"), rps, shell2,
                      uncalibrated=[d["sample"] for d in nm["datasets"] if getattr(groups[d["id"]], "uncalibrated", False)])
    P = summ["params"]
    full = dict(win, kweight=model["kweight"], rmin=model["rmin"], rmax=model["rmax"])
    out = []
    for r in summ["datasets"]:
        i = r["id"]
        names = joint_param_names(i, two)
        rows = [p for p in summ["paths"] if p.get("dataset") == i]
        r_fit = sum(m["degen"] * p["R"] for m, p in zip(shell.members, rows)) / shell.n_ref
        ph2 = (_phase2(shell2, rows[len(shell.members):], P[names["n2"]]["value"], P[names["n2"]]["stderr"], P[names["dr2"]]["stderr"],
                       P[names["ss2"]]["value"], P[names["ss2"]]["stderr"]) if two else None)
        out.append(QuickResult(r["sample"], "sample", model, shell, P[names["n"]]["value"], P[names["n"]]["stderr"], r_fit,
                               P[names["dr"]]["stderr"], P[names["ss"]]["value"], P[names["ss"]]["stderr"],
                               P["e0"]["value"], P["e0"]["stderr"], P["s02"]["value"], None, r["rfactor"], r["n_idp"],
                               summ["nvarys"], full, v.samples[i], fit, rps[i], *peaks[i], ph2))
    return JointResult(model, shell, out, P["e0"]["value"], P["e0"]["stderr"], P["s02"]["value"], summ["rfactor"],
                       summ["n_idp"], summ["nvarys"], full, v, fit, rmins, shell2)


def format_joint_text(res: JointResult, lang="zh") -> str:
    """联合结果与两层判定（CLI 用；HTML 实体已还原）。"""
    zh = lang == "zh"
    s, w = res.shell, res.window
    ex = lambda v, e, f: (f"{v:{f}}" if e is None else f"{v:{f}} ± {e:{f}}") if v is not None else "-"    # noqa: E731
    L = [f"== 联合快速拟合：{len(res.samples)} 个样品（{', '.join(r.sample for r in res.samples)}）" if zh else
         f"== Joint quick fit: {len(res.samples)} samples ({', '.join(r.sample for r in res.samples)})",
         ("第一壳层：" if zh else "First shell: ") + f"{s.absorber}–{s.scatterer}, N_ref = {s.n_ref:g}, R_CIF = {s.r_cif:.3f} Å"]
    L += [f"    {m['label']}  Reff {m['reff']:.4f}  degen {m['degen']:g}  {Path(m['file']).name}" for m in s.members]
    if res.shell2 is not None:
        s2_ = res.shell2
        L.append(("第二相第一壳层：" if zh else "Second-phase first shell: ") + f"{s2_.absorber}–{s2_.scatterer}, N_ref = {s2_.n_ref:g}, "
                 f"R_CIF = {s2_.r_cif:.3f} Å")
        L += [f"    {m['label']}  Reff {m['reff']:.4f}  degen {m['degen']:g}  {Path(m['file']).name}" for m in s2_.members]
    rm = ", ".join(f"{i} {v:.2f}" for i, v in res.r_rmin.items())
    L.append(("公共窗口：" if zh else "Common window: ") + f"k {w['kmin']:g}–{w['kmax']:g} (dk {w['dk']:g}, {w['window']}), "
             f"kweight {w['kweight']}, R {w['rmin']:.2f}–{w['rmax']:.2f} Å"
             + (f"（各样品自动 Rmin：{rm}，取最大）" if zh else f" (per-sample automatic Rmin: {rm}; the largest is used)"))
    L.append(f"ΔE0 {'（共享）' if zh else '(shared) '}{ex(res.e0, res.e0_err, '.2f')} eV | S0² {res.s02:.3f}{'（固定）' if zh else ' (fixed)'} | "
             f"{'联合 ' if zh else 'joint '}R-factor {res.rfactor:.4f} | Σ N_idp {res.n_idp:.1f}, vars {res.nvarys}")
    mark = {"pass": "✓", "fail": "✗", "note": "·"}

    def lines(v, pad):
        out = []
        for i in v.items:
            out.append(f"{pad}{mark[i.level]} " + html.unescape(i.zh if zh else i.en))
            if i.level == "fail" and (i.advice_zh if zh else i.advice_en):
                out.append(f"{pad}    → " + (i.advice_zh if zh else i.advice_en))
        return out
    L.append(("整批判定：" if zh else "Batch verdict: ") + res.verdict.summary(lang))
    L += lines(res.verdict, "  ")
    for r, sv in zip(res.samples, res.verdict.samples.values()):
        L.append(f"-- {r.sample}：N {ex(r.n, r.n_err, '.2f')} | R {ex(r.r, r.r_err, '.4f')} Å | σ² {ex(r.sigma2, r.sigma2_err, '.5f')} Å² | "
                 f"R-factor {r.rfactor:.4f} | {sv.summary(lang)}")
        if r.phase2:
            p2 = r.phase2
            L.append(f"   {'相 2' if zh else 'phase 2'}：N {ex(p2['n'], p2['n_err'], '.2f')} | R {ex(p2['r'], p2['r_err'], '.4f')} Å | "
                     f"σ² {ex(p2['sigma2'], p2['sigma2_err'], '.5f')} Å²")
        L += lines(sv, "  ")
    return "\n".join(L)
