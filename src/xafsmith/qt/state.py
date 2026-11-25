"""会话状态与公共处理函数（原始数据只读，处理都在副本上）。"""
from __future__ import annotations

from xafsmith import logs
import json
import re
from pathlib import Path

import numpy as np
from PySide6.QtCore import QObject, Signal

from xafsmith import defaults, paths

FUNCS = {"sqrt", "exp", "log", "abs", "min", "max", "pi", "sin", "cos", "tan", "reff", "degen", "e", "log10",
         "sigma2_debye", "sigma2_eins", "tempK"}      # B6：σ² 温度模型的函数与保留符号不是参数名
RECENT = paths.USER_DIR / "recent.json"


VER = {"data": 0}          # 数据版本号：save_cfg 等不带 S 的函数也能 bump


def bump():
    VER["data"] += 1


def _mtime(p):
    try:
        return Path(p).stat().st_mtime_ns
    except OSError:
        return 0


class State(QObject):
    """一个项目的会话：已载入的谱、校准记录、拟合、当前处理参数"""
    changed = Signal(str)          # "groups" / "fits" / "calib" / "project"

    def __init__(self):
        super().__init__()
        self.reset()

    def reset(self):
        from xafsmith import autobk as xbkg, ft as xft, normalize as xnorm, pipeline as pl
        self.groups = {}
        self.calib = pl.load_calib() if paths.is_project(paths.ROOT) else {}
        self.fits = []
        self.norm_par = dict(xnorm.DEFAULT_NORM)
        self.bkg_par = dict(xbkg.DEFAULT_BKG)
        self.ft_par = dict(xft.DEFAULT_FT)
        self.qc = None
        self.extra = {}

    def emit(self, what):
        bump()
        self.changed.emit(what)

    def data_key(self):
        """页面是否需要重建的指纹：谱（含就地改动）、拟合、QC、校准、磁盘上的配置与结果。
        不依赖各处记得 emit；emit 只是补充。"""
        files = [paths.CONFIG, paths.META, paths.FEFF, paths.FITS, paths.LCF, paths.XANES, paths.FIGS,
                 paths.REPORTS, paths.MODELS, paths.FITS_CSV, paths.LCF_CSV, paths.XANES_CSV, paths.QC_CSV,
                 paths.CALIB_JSON]
        return (VER["data"],
                tuple((n, id(g), has_chi(g)) for n, g in self.groups.items()),
                len(self.fits), id(self.qc), tuple(sorted(self.calib)),
                tuple(sorted(k for k in self.extra if k != "page")),
                tuple(_mtime(f) for f in files))

    def cfg_defaults(self, sec, names=None):
        """xafsmith.json 里的处理参数（sec = norm / bkg / ft）：取 names（谱名列表）中第一条谱所属吸收边的一套，
        没有谱或配置里没有该边就取全项目第一个边；都没有则用软件默认值。返回 (参数字典, 来源说明)"""
        from xafsmith import autobk as xbkg, ft as xft, normalize as xnorm
        dflt = dict(norm=xnorm.DEFAULT_NORM, bkg=xbkg.DEFAULT_BKG, ft=xft.DEFAULT_FT)[sec]
        cfg = load_cfg()
        edges = cfg.get("edges", {})
        ek = None
        for n in (names or list(self.groups)):
            if n in self.groups:
                ek = edge_key(self.groups[n])
                break
        if ek not in edges:
            ek = next(iter(edges), None)
        if ek is None:
            return dict(dflt), "default"
        return {**dflt, **edges[ek].get(sec, {})}, ek

    def par_key(self):
        """当前处理参数的指纹：只有它变了时页面只需重画。"""
        return json.dumps([self.norm_par, self.bkg_par, self.ft_par], sort_keys=True, default=str)


# ----------------------------------------------------------------------------- 项目
def is_project():
    return paths.is_project(paths.ROOT)


def recent_projects():
    try:
        return [p for p in json.loads(RECENT.read_text(encoding="utf-8-sig")) if paths.is_project(p)]
    except Exception:
        logs.log.debug("qt.state.recent_projects 出错（已忽略或已提示）：%s", RECENT, exc_info=True)
        return []


def remember(root):
    import os
    if os.environ.get("XAFSMITH_NO_RECENT"):      # 自动测试 / 截图时不写入“最近的项目”
        return
    lst = [str(root)] + [p for p in recent_projects() if p != str(root)]
    try:
        RECENT.parent.mkdir(parents=True, exist_ok=True)
        RECENT.write_text(json.dumps(lst[:10], ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception:
        logs.log.warning("qt.state.remember 出错（已忽略或已提示）：%s", RECENT, exc_info=True)
        pass


def load_cfg():
    from xafsmith import pipeline as pl
    return pl.load_config() if pl.CONFIG.exists() else {"edges": {}}


def err_lines(ex):
    """ValueError（save_config 的多行消息）→ (标题, 明细行)，供 Page.notice 显示。"""
    from .widgets import T
    ls = str(ex).splitlines() or [str(ex)]
    if getattr(ex, "config_errors", None) is not None:      # save_config 拒写：标题按界面语言，明细为校验原文
        return T("配置有错误，未保存", "The configuration has errors; not saved"), list(ex.config_errors)
    return ls[0], ls[1:]


def save_cfg(cfg):
    from xafsmith import pipeline as pl
    pl.save_config(cfg)                                    # 校验 + 原子写入；有错误级问题抛 ValueError
    bump()


# ----------------------------------------------------------------------------- 谱
def edge_key(g):
    return f"{g.element}_{g.edge}"


def has_chi(g):
    return hasattr(g, "chi") and hasattr(g, "k")


def _known_format(xio, p):
    """能被某个 reader 自动识别的数据文件（读不了的文件当作不是数据）。"""
    try:
        return xio.detect_format(p)[0] is not None
    except Exception:                      # noqa: BLE001
        logs.log.warning("qt.state._known_format 出错（已忽略或已提示）：%s", p, exc_info=True)
        return False


def raw_files():
    from xafsmith import io as xio
    out = [p for p in paths.RAW.rglob("*") if p.is_file()
           and (p.suffix.lower() in defaults.RAW_LIST_SUFFIX or _known_format(xio, p))]
    out += [p for p in paths.ROOT.rglob("*.prj") if ".venv" not in p.parts]
    return sorted(set(out))


def ref_candidates():
    from xafsmith import io as xio, pipeline as pl
    out = list(pl.load_meta().query("role == 'reference'").file) if pl.META.exists() else []
    for p in paths.RAW.rglob("*"):
        if p.is_file() and re.search(r"foil|powder|metal", p.name, re.I) and _known_format(xio, p):
            out.append(p.relative_to(paths.ROOT).as_posix())
    return list(dict.fromkeys(out))


def ref_calib(S, ref, e_table=None, smooth_ev=1.0, force=False):
    from xafsmith import pipeline as pl, services
    if ref in S.calib and not force:
        return S.calib[ref]
    cfg = load_cfg()
    if e_table is not None:
        cfg = json.loads(json.dumps(cfg))
        g0 = pl.read_meta_row(pl.meta_row(ref) or {"file": ref}, cfg)
        e = cfg["edges"].setdefault(f"{g0.element}_{g0.edge}", {})
        e["e_table"] = e_table
        e.setdefault("norm", {})["smooth_ev"] = smooth_ev
    r = pl.calibrate_ref_file(ref, cfg)
    S.calib[ref] = r
    services.save_calib(S.calib, tool="GUI calibration",
                        params=dict(reference=ref, e_table=e_table, smooth_ev=smooth_ev, force=force, references=sorted(S.calib)))
    S.emit("calib")
    return r


def calib_status(S, g, en=False):
    """(状态文字, 是否已按参比校准)"""
    refs = [r for r in str(getattr(g, "calib_ref", "") or "").split(";") if r]
    de = getattr(g, "e_shift", 0.0) or 0.0
    if not refs:
        if de == 0:
            return ("✘ not calibrated against a reference" if en else "✘ 未按参比校准"), False
        return (f"⚠ shifted {de:+.2f} eV, unknown source" if en else f"⚠ 平移 {de:+.2f} eV，来源不明"), False
    miss = [r for r in refs if r not in S.calib]
    if miss:
        return (f"⚠ no calibration record for {Path(miss[0]).name}" if en
                else f"⚠ 参比 {Path(miss[0]).name} 无校准记录"), False
    want = float(np.mean([S.calib[r]["delta_e"] for r in refs]))
    if abs(de - want) > 1e-6:
        return (f"⚠ ΔE={de:+.2f} differs from reference {want:+.2f}" if en
                else f"⚠ ΔE={de:+.2f} 与参比的 {want:+.2f} 不一致"), False
    return "✔ " + " + ".join(Path(r).name for r in refs), True


def apply_ref(S, keys, ref):
    from xafsmith import calib as xcal
    r = S.calib[ref]
    done, skipped = [], []
    for k in keys:
        g = S.groups[k]
        if edge_key(g) != r["edge_key"]:
            skipped.append(k)
            continue
        xcal.apply_shift([g], r["delta_e"])
        g.calib_ref = ref
        for a in ("e0", "norm", "norm_params", "chi", "k", "chir_mag"):
            if hasattr(g, a):
                delattr(g, a)
        done.append(k)
    return done, skipped


def ensure_norm(S, g):
    from xafsmith import normalize as xnorm
    if not hasattr(g, "flat"):
        xnorm.normalize(g, **S.norm_par)
    return g


def process(S, g, norm=True, bkg=True, ft=True):
    from xafsmith import autobk as xbkg, ft as xft, normalize as xnorm
    if norm:
        xnorm.normalize(g, **S.norm_par)
    if bkg:
        xbkg.autobk(g, **S.bkg_par)
    if ft:
        xft.forward(g, **S.ft_par)
    return g


def idents(expr):
    if expr is None:
        return []
    s = str(expr)
    if re.fullmatch(r"\s*[-+]?[\d.]+([eE][-+]?\d+)?\s*", s):
        return []
    return [t for t in re.findall(r"[A-Za-z_]\w*", s) if t not in FUNCS]


def feff_dirs():
    if not paths.FEFF.exists():
        return []
    from xafsmith import feff_wrap as xfeff
    return sorted([d for d in paths.FEFF.rglob("*") if d.is_dir() and list(d.glob("feff0001.dat"))
                   and not {xfeff.RUN_DIR, xfeff.FAILED_DIR} & set(d.parts)])      # E6 的运行中 / 失败现场目录不算


def saved_models():
    return sorted(f.name for f in paths.MODELS.glob("*.json") if not f.name.startswith("_")) \
        if paths.MODELS.exists() else []


# ----------------------------------------------------------------------------- 拟合
def group_snapshot(S, names):
    """后台线程用的会话快照：只含 S.groups 中 names 里已有的谱，且是深拷贝（须在界面线程调用）。
    返回只有 .groups 的对象；其 .groups 作 services.run_model 的 fallback。"""
    import copy
    from types import SimpleNamespace
    return SimpleNamespace(groups={k: copy.deepcopy(S.groups[k]) for k in dict.fromkeys(names) if k in S.groups})


def fit_ds_ids(fit):
    """多数据集拟合的数据集 id 列表；单数据集拟合返回空列表"""
    return [r["id"] for r in fit["summ"]["datasets"]] if fit["summ"].get("multi") else []


def fit_dataset(fit, ds_id):
    """多数据集拟合记录 → 某个数据集的单数据集形状记录（model 为旧格式模型，summ 为 dataset_view，curves 为该数据集的曲线），
    供作图、诊断、质量检查复用；联合量（参数、χ²、变量数）取联合值。单数据集拟合原样返回。"""
    from xafsmith import fit_exafs as xfit
    if not fit["summ"].get("multi"):
        return fit
    d = xfit.dataset_of(fit["model"], ds_id)
    mdl = {k: v for k, v in d.items() if k not in ("id", "epsilon_k")}
    mdl.update(name=fit["summ"]["model"], params=fit["model"].get("params", {}))
    return dict(model=mdl, summ=xfit.dataset_view(fit["summ"], ds_id), curves=fit["curves"][ds_id],
                result=fit["result"], report=fit["report"], time=fit["time"], robust=None, dataset=ds_id)


def fit_label(f):
    return f"{f['time']}  {f['summ']['sample']} — {f['summ']['model']}"


def parse_ranges(txt):
    """'9984.5-9990; 10321-10327.5' → [[9984.5, 9990.0], [10321.0, 10327.5]]"""
    out = []
    for part in re.split(r"[;；,，\n]+", txt or ""):
        part = part.strip()
        if not part:
            continue
        m = re.match(r"^\s*([0-9.]+)\s*[-–~～]\s*([0-9.]+)\s*$", part)
        if not m:
            raise ValueError(f"无法识别“{part}”，格式为 起始-结束，如 9984.5-9990 / cannot parse “{part}”; use start-end")
        lo, hi = sorted((float(m.group(1)), float(m.group(2))))
        out.append([lo, hi])
    return out
