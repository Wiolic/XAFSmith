"""io —— 读入束线数据，统一成 larch Group（门面）。

具体格式由 readers/ 下的 reader 实现（见 docs/dev/io_readers.md）：
  bsrf · xdi · athena_xmu · xdac · prj（Athena 工程）· columns（通用列文本，按列名映射）

入口：read_scan / read_file / detect_format / list_formats；read_prj（Athena 工程 → {组名: Group}）、
read_any（自动识别，.prj 返回字典）；write_prj、write_group_columns 导出。

统一后的 Group 属性：
  energy, mu, i0, i1, ifl, mode('trans'|'fluo'|None), element, edge, e_nominal,
  filename, label, timestamp, source,
  format（reader 名）, mu_from('channels'|'file'), columns（实际使用的列映射）,
  meta_guessed（哪些字段是猜的）, read_warnings（读入时的警告）
透射 μ = ln(I0/It)；荧光 μ = If/I0；文件里同时有通道与 μ 列时一律由通道计算。
"""
import re
import sys
from pathlib import Path

import numpy as np

from . import defaults
from .readers import ReadError, detect_format, list_formats, read_file, read_scan   # noqa: F401  门面：供 xio.* 调用


def read_prj(path):
    """读 Athena 工程，返回 {组名: Group}。"""
    return {getattr(g, "group_name", g.label): g for g in read_file(path, fmt="prj")}


def read_any(path, **kws):
    """兼容旧调用：自动识别格式并读入；.prj 返回 {组名: Group}，其他返回 Group。"""
    path = Path(path)
    if path.suffix.lower() == ".prj":
        return read_prj(path)
    return read_scan(path, **kws)


_INDEX_TEMPLATE = "__columns_by_index__"     # read_direct 临时模板名（不会与用户模板重名）


def read_direct(path, *, fmt=None, columns=None, mode=None, templates=None, element=None):
    """图形界面“直接读入文件”的逐文件读入 → [(标签, Group), …]。
    fmt：None / "auto" 自动识别；reader 名；xafsmith.json "formats" 里的模板名；或 "columns_by_index"（通用列文本，
    用户明确给出的列号映射：columns = {"energy": 列号, "i0": …, "it": …, "if": …, "mu": …}，负数 = 没有这一列）——
    它被构造成一个临时模板 {"base": "columns", …}，与已保存模板走同一个读入入口。
    mode："auto" / None 按文件头，或 "trans" / "fluo"。element：非空则覆盖元素并按能量中位数重新猜吸收边（.prj 里的谱保持原样）。
    .prj（fmt 为 None / "prj"）返回多个 (“文件名主干:组名”, Group)；其他文件返回一个 (相对项目根的 posix 路径, Group)，
    并把 group.label 设为该路径。read_warnings 原样留在 group 上（提示由调用方负责）。"""
    from . import paths
    from .common import guess_edge
    path = Path(path)
    tpls = dict(templates or {})
    fmt = None if fmt in (None, "auto") else fmt
    if fmt == "columns_by_index":
        cols = {"base": "columns"}
        for key, v in (columns or {}).items():
            if v is not None and (key == "energy" or v >= 0):
                cols[key] = int(v) if key != "energy" else v
        tpls[_INDEX_TEMPLATE] = cols
        fmt, columns = _INDEX_TEMPLATE, None
    mode = None if mode in (None, "auto") else mode
    if path.suffix.lower() == ".prj" and fmt in (None, "prj"):
        return [(f"{path.stem}:{lab}", g) for lab, g in read_prj(path).items()]
    g = read_scan(path, fmt=fmt, columns=columns, templates=tpls, **({} if mode is None else {"mode": mode}))
    if element and element.strip():
        g.element = element.strip()
        g.edge = guess_edge(g.element, float(np.median(g.energy)))
    lab = path.relative_to(paths.ROOT).as_posix()
    g.label = lab
    return [(lab, g)]


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
        # norm2：None 在这里按“e_end−e0（偏移 0）”处理，与 normalize.normalize / 新建配置的 -10 不等价；不要合并（会改 .prj 内容）
        x.pre_edge_details = Group(pre1=np_.get("pre1", -150), pre2=np_.get("pre2", -30),
                                   norm1=np_.get("norm1", 100),
                                   norm2=(np_.get("norm2") if (np_.get("norm2") or 0) > 0
                                          else float(g.energy[-1] - (e0 or g.energy[0]) + (np_.get("norm2") or 0))),
                                   nnorm=np_.get("nnorm", defaults.NORM["nnorm"]), e0=e0)
        from .common import ETOK
        kmax_data = float(np.sqrt(ETOK * max(g.energy[-1] - (e0 or g.energy[0]), 0)))
        x.autobk_details = Group(call_args=dict(rbkg=bp.get("rbkg", defaults.BKG["rbkg"]), kmin=0, kmax=kmax_data,
                                                kweight=bp.get("kweight", defaults.BKG["kweight"]),
                                                dk=defaults.BKG["dk"], win=defaults.BKG["win"],
                                                nclamp=defaults.BKG["nclamp"], clamp_lo=defaults.BKG["clamp_lo"],
                                                clamp_hi=defaults.BKG["clamp_hi"]))
        x.xftf_details = Group(call_args=dict(kmin=fp.get("kmin", 3), kmax=fp.get("kmax", 12),
                                              kweight=fp.get("kweight", defaults.FT["kweight"]), dk=fp.get("dk", 1),
                                              window=fp.get("window", defaults.FT["window"])))
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
    from . import cli
    raise SystemExit(cli.main(["inspect", *sys.argv[1:]]))
