"""io —— 读入束线数据，统一成 larch Group。

支持：
  * BSRF 1W1B 格式（# Element: Ir, 11215 eV, Transmission/Fluorescence Mode；
    列 Energy I0 I1 If ln(I0/I1) If/I0 mu）
  * Athena .prj（larch.io.read_athena）
  * 通用列文本（需指定能量列及 I0/I1/If 或 mu 列）

统一后的 Group 属性：
  energy, mu, i0, i1, ifl, mode('trans'|'fluo'|'mu'), element, edge, e_nominal,
  filename, label, timestamp, source
透射 μ = ln(I0/I1)；荧光 μ = If/I0。

用法（单独运行）：
  python -m xafsmith.io <文件> [<文件> ...]      # 打印识别结果
"""
import re
import sys
from pathlib import Path

import numpy as np
from larch import Group

from .common import guess_edge

_BSRF_ELEM = re.compile(r"Element:\s*([A-Z][a-z]?)\s*,\s*([\d.]+)\s*eV\s*,\s*(.*)$")


def _make_group(energy, i0=None, i1=None, ifl=None, mu=None, mode="trans",
                element=None, edge=None, e_nominal=None, filename="", label=None,
                timestamp="", source=""):
    order = np.argsort(energy)
    energy = np.asarray(energy, float)[order]

    def _o(a):
        return None if a is None else np.asarray(a, float)[order]

    i0, i1, ifl, mu = _o(i0), _o(i1), _o(ifl), _o(mu)
    # 去掉重复能量点
    keep = np.concatenate([[True], np.diff(energy) > 1e-6])
    energy = energy[keep]
    i0, i1, ifl, mu = [None if a is None else a[keep] for a in (i0, i1, ifl, mu)]
    if mu is None:
        mu = compute_mu(i0, i1, ifl, mode)
    if element and not edge and e_nominal:
        edge = guess_edge(element, e_nominal)
    g = Group(energy=energy, mu=mu, i0=i0, i1=i1, ifl=ifl, mode=mode, element=element,
              edge=edge, e_nominal=e_nominal, filename=str(filename),
              label=label or Path(filename).name, timestamp=timestamp, source=source,
              e_shift=0.0)
    return g


def compute_mu(i0, i1=None, ifl=None, mode="trans"):
    if mode == "trans":
        return np.log(np.abs(i0) / np.abs(i1))
    if mode == "fluo":
        return ifl / i0
    raise ValueError(f"未知模式 {mode}")


def is_bsrf(path):
    try:
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            head = "".join(f.readline() for _ in range(5))
        return "BSRF" in head or "Element:" in head
    except Exception:
        return False


def read_bsrf(path, mode=None, label=None):
    """读入 BSRF（1W1B 等）文本。mode=None 时按文件头自动判断。"""
    path = Path(path)
    header, rows = [], []
    with open(path, "r", encoding="utf-8", errors="ignore") as f:
        for line in f:
            s = line.strip()
            if not s:
                continue
            if s.startswith("#"):
                header.append(s.lstrip("#").strip())
                continue
            try:
                rows.append([float(x) for x in s.split()])
            except ValueError:
                continue
    data = np.array([r for r in rows if len(r) == len(rows[0])])
    element, e_nom, mode_hdr, timestamp = None, None, None, ""
    for h in header:
        m = _BSRF_ELEM.search(h)
        if m:
            element, e_nom = m.group(1), float(m.group(2))
            txt = m.group(3).lower()
            mode_hdr = "fluo" if "fluor" in txt else ("trans" if "trans" in txt else None)
        elif re.match(r"\d{4}/\d+/\d+", h):
            timestamp = h
    mode = mode or mode_hdr or "trans"
    g = _make_group(data[:, 0], i0=data[:, 1], i1=data[:, 2], ifl=data[:, 3], mode=mode,
                    element=element, e_nominal=e_nom, filename=path, label=label,
                    timestamp=timestamp, source="BSRF")
    g.header = header
    return g


def read_columns(path, ecol=0, i0col=None, i1col=None, ifcol=None, mucol=None, mode="trans",
                 element=None, edge=None, label=None, skiprows=None):
    """通用列文本。列号从 0 开始。给 mucol 则直接用该列作为 μ。"""
    path = Path(path)
    rows = []
    with open(path, "r", encoding="utf-8", errors="ignore") as f:
        for i, line in enumerate(f):
            if skiprows and i < skiprows:
                continue
            s = line.strip()
            if not s or s[0] in "#;!%":
                continue
            try:
                rows.append([float(x) for x in re.split(r"[\s,]+", s)])
            except ValueError:
                continue
    n = max(set(len(r) for r in rows), key=[len(r) for r in rows].count)
    d = np.array([r for r in rows if len(r) == n])
    col = lambda c: None if c is None else d[:, c]
    if mucol is not None:
        mode_ = "mu"
        g = _make_group(d[:, ecol], i0=col(i0col), i1=col(i1col), ifl=col(ifcol), mu=d[:, mucol],
                        mode=mode_, element=element, edge=edge, filename=path, label=label,
                        source="columns")
    else:
        g = _make_group(d[:, ecol], i0=col(i0col), i1=col(i1col), ifl=col(ifcol), mode=mode,
                        element=element, edge=edge, filename=path, label=label, source="columns")
    if element and not edge:
        g.edge = guess_edge(element, float(np.median(g.energy)))
    return g


def read_prj(path):
    """读 Athena 工程，返回 {label: Group}（只取 energy、mu，以及 Athena 的参数备查）。"""
    from larch.io import read_athena
    prj = read_athena(str(path), do_preedge=False, do_bkg=False, do_fft=False)
    out = {}
    for name, grp in prj.groups.items() if hasattr(prj, "groups") else prj._athena_groups.items():
        g = _make_group(grp.energy, mu=grp.mu, mode="mu", filename=path, label=name,
                        source="athena_prj")
        g.athena_params = getattr(grp, "athena_params", None)
        el = getattr(getattr(grp, "athena_params", None), "bkg", None)
        out[name] = g
    return out


def read_any(path, **kws):
    path = Path(path)
    if path.suffix.lower() == ".prj":
        return read_prj(path)
    if is_bsrf(path):
        return read_bsrf(path, **kws)
    return read_columns(path, **kws)


def write_group_columns(g, path, cols=("energy", "mu", "norm", "flat", "dmude")):
    """导出处理后数据为列文本。"""
    arrs, names = [], []
    for c in cols:
        a = getattr(g, c, None)
        if a is not None and len(a) == len(g.energy):
            arrs.append(a)
            names.append(c)
    np.savetxt(path, np.column_stack(arrs), header=" ".join(names), fmt="%.7g")
    return path


if __name__ == "__main__":
    for p in sys.argv[1:]:
        g = read_any(p)
        if isinstance(g, dict):
            print(p, "-> Athena 工程:", list(g))
            continue
        print(f"{p}: {g.element} {g.edge} mode={g.mode} n={len(g.energy)} "
              f"E={g.energy[0]:.1f}..{g.energy[-1]:.1f} {g.timestamp}")
