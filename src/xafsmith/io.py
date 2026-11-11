"""io —— 读入束线数据，统一成 larch Group（门面）。

具体格式由 readers/ 下的 reader 实现（见 docs/dev/io_readers.md）：
  bsrf · xdi · athena_xmu · xdac · prj（Athena 工程）· columns（通用列文本，按列名映射）

新代码请用 read_scan / read_file / detect_format；下面的 read_bsrf、read_columns、read_prj、read_any
是为兼容旧调用保留的薄封装。

统一后的 Group 属性：
  energy, mu, i0, i1, ifl, mode('trans'|'fluo'|None), element, edge, e_nominal,
  filename, label, timestamp, source,
  format（reader 名）, mu_from('channels'|'file'), columns（实际使用的列映射）,
  meta_guessed（哪些字段是猜的）, read_warnings（读入时的警告）
透射 μ = ln(I0/It)；荧光 μ = If/I0；文件里同时有通道与 μ 列时一律由通道计算。

用法（单独运行）：
  python -m xafsmith.io <文件> [<文件> ...]      # 打印识别结果
"""
import re
import sys
from pathlib import Path

import numpy as np

from .readers import (BY_NAME, ReadError, detect_format, list_formats, read_file,   # noqa: F401
                      read_scan)
from .readers.base import compute_mu, make_group as _make_group_new                  # noqa: F401


def _make_group(energy, i0=None, i1=None, ifl=None, mu=None, mode="trans", element=None, edge=None,
                e_nominal=None, filename="", label=None, timestamp="", source=""):
    """旧接口（mode="mu" 表示直接给了 μ）；新代码请用 readers.base.make_group。"""
    if mode == "mu":
        mode = None
    return _make_group_new(energy, i0=i0, i1=i1, ifl=ifl, mu=mu, mode=mode, element=element,
                           edge=edge, e_nominal=e_nominal, filename=filename, label=label,
                           timestamp=timestamp, source=source)


def is_bsrf(path):
    try:
        return detect_format(path)[0] == "bsrf"
    except ReadError:
        return False


def read_bsrf(path, mode=None, label=None):
    """兼容旧调用：按 BSRF 格式读入。"""
    g = read_scan(path, fmt="bsrf", mode=mode)
    if label:
        g.label = label
    return g


def read_columns(path, ecol=0, i0col=None, i1col=None, ifcol=None, mucol=None, mode="trans",
                 element=None, edge=None, label=None, skiprows=None):
    """兼容旧调用：按列号读通用列文本（列号从 0 开始）。新代码请用 read_scan(columns={...})。"""
    cols = {"energy": ecol}
    for k, v in (("i0", i0col), ("it", i1col), ("if", ifcol), ("mu", mucol)):
        if v is not None:
            cols[k] = v
    from .readers.base import split_table, read_text, table_to_group
    text = read_text(path)
    if skiprows:
        text = "\n".join(text.splitlines()[skiprows:])
    pre, data = split_table(text)
    g = table_to_group(Path(path), "columns", pre, data, None, None, columns=cols,
                       mode=None if mucol is not None else mode, element=element, edge=edge,
                       label=label)
    if mucol is not None and mode in ("trans", "fluo"):
        g.mode = mode
    return g


def read_prj(path):
    """读 Athena 工程，返回 {组名: Group}。"""
    return {getattr(g, "group_name", g.label): g for g in read_file(path, fmt="prj")}


def read_any(path, **kws):
    """兼容旧调用：自动识别格式并读入；.prj 返回 {组名: Group}，其他返回 Group。"""
    path = Path(path)
    if path.suffix.lower() == ".prj":
        return read_prj(path)
    return read_scan(path, **kws)


def write_prj(groups, path, norm=None, bkg=None, ft=None):
    """把已校准的谱导出为 Athena 工程（.prj），用于在 Athena / Artemis 中对照。

    写入能量（已加校准 ΔE）与 μ(E)，并把本软件使用的 E0、边前/边后范围、rbkg、k 范围、窗函数
    写成 Athena 的处理参数，使 Athena 打开后的处理条件与 XAFSmith 相同（Athena 会按这些参数重新计算）。
    groups: Group 列表；返回写出的路径。
    """
    from larch import Group
    from larch.io import AthenaProject
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    prj = AthenaProject(str(path))
    for g in groups:
        e0 = getattr(g, "e0", None)
        np_ = dict(getattr(g, "norm_params", {}) or {}, **(norm or {}))
        bp = dict(getattr(g, "bkg_params", {}) or {}, **(bkg or {}))
        fp = dict(getattr(g, "ft_params", {}) or {}, **(ft or {}))
        x = Group(energy=np.asarray(g.energy, float), mu=np.asarray(g.mu, float),
                  filename=str(getattr(g, "label", "")), datatype="xas")
        x.groupname = re.sub(r"\W+", "_", str(getattr(g, "label", "group")))
        if e0 is not None:
            x.e0 = float(e0)
            x.edge_step = float(getattr(g, "edge_step", 1.0))   # 有 e0 + edge_step 时 larch 不会用默认参数重算
        x.pre_edge_details = Group(pre1=np_.get("pre1", -150), pre2=np_.get("pre2", -30),
                                   norm1=np_.get("norm1", 100),
                                   norm2=(np_.get("norm2") if (np_.get("norm2") or 0) > 0
                                          else float(g.energy[-1] - (e0 or g.energy[0]) + (np_.get("norm2") or 0))),
                                   nnorm=np_.get("nnorm", 2), e0=e0)
        kmax_data = float(np.sqrt(0.2625 * max(g.energy[-1] - (e0 or g.energy[0]), 0)))
        x.autobk_details = Group(call_args=dict(rbkg=bp.get("rbkg", 1.0), kmin=0, kmax=kmax_data,
                                                kweight=bp.get("kweight", 2), dk=0.1, win="hanning",
                                                nclamp=3, clamp_lo=0, clamp_hi=1))
        x.xftf_details = Group(call_args=dict(kmin=fp.get("kmin", 3), kmax=fp.get("kmax", 12),
                                              kweight=fp.get("kweight", 2), dk=fp.get("dk", 1),
                                              window=fp.get("window", "hanning")))
        prj.add_group(x)
    prj.save(str(path))
    return path


def write_group_columns(g, path, cols=("energy", "mu", "norm", "flat", "dmude")):
    """导出处理后数据为列文本。"""
    arrs, names = [], []
    for c in cols:
        a = getattr(g, c, None)
        if a is not None and len(a) == len(g.energy):
            arrs.append(a)
            names.append(c)
    np.savetxt(path, np.column_stack(arrs), header=" ".join(names), fmt="%.7g", encoding="utf-8")
    return path


if __name__ == "__main__":
    for p in sys.argv[1:]:
        g = read_any(p)
        if isinstance(g, dict):
            print(p, "-> Athena 工程:", list(g))
            continue
        print(f"{p}: {g.element} {g.edge} mode={g.mode} n={len(g.energy)} "
              f"E={g.energy[0]:.1f}..{g.energy[-1]:.1f} {g.timestamp}")
