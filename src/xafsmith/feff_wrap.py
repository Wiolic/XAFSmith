"""feff_wrap —— 结构（CIF 或内置）→ feff.inp → 运行 FEFF6L 或 FEFF8L（均为 xraylarch 自带）→ 路径列表。

FEFF6L：非自洽 muffin-tin 势，几秒；FEFF8L：自洽势（SCF），约 1–3 分钟，ΔE0 通常更接近 0。
两者路径编号一般相同；换用时 ΔE0 的零点会变（Ta L3 KTaO3：约 6.6 → 1.2 eV），固定 e0 的模型要重新确定。
（推荐用 xafsmith feff，输出目录自动按标准命名）
"""
import os
import re
from pathlib import Path

import numpy as np
import pandas as pd

from .errors import FeffError

CODES = ("feff6", "feff8")
EXCHANGE = {0: "Hedin-Lundqvist（默认）", 2: "Dirac-Hara", 5: "部分非局域"}
HOLE = {"K": 1, "L1": 2, "L2": 3, "L3": 4, "M1": 5, "M2": 6, "M3": 7, "M4": 8, "M5": 9}


def inequivalent_sites(structure, absorber):
    """返回吸收原子的不等价位点 (index, multiplicity)"""
    from pymatgen.symmetry.analyzer import SpacegroupAnalyzer
    sym = SpacegroupAnalyzer(structure, symprec=1e-3).get_symmetrized_structure()
    out = []
    for grp in sym.equivalent_indices:
        if structure[grp[0]].specie.symbol == absorber:
            out.append((grp[0], len(grp)))
    return out


def make_feffinp(structure, absorber, edge="K", site_index=None, rcluster=8.0, rmax=6.0,
                 nleg=4, title="", max_atoms=500, s02=1.0, code="feff6", scf=4.5, exchange=0):
    """code='feff6'：HOLE/CONTROL 4 项；code='feff8'：EDGE/S02/CONTROL 6 项 + SCF（自洽半径 scf Å）+ EXCHANGE。
    FEFF8 的 PRINT 最后一位必须为 3 才会写出 feffNNNN.dat。"""
    from pymatgen.core.periodic_table import Element
    if site_index is None:
        site_index = inequivalent_sites(structure, absorber)[0][0]
    center = structure[site_index].coords
    nbrs = structure.get_sites_in_sphere(center, rcluster, include_index=False)
    atoms = sorted([(np.linalg.norm(n.coords - center), n.specie.symbol, n.coords - center)
                    for n in nbrs], key=lambda a: a[0])
    if len(atoms) > max_atoms:
        atoms = atoms[:max_atoms]
    elems = []
    for _, sym, _ in atoms[1:]:
        if sym not in elems:
            elems.append(sym)
    ipot = {sym: i + 1 for i, sym in enumerate(elems)}
    lines = [(f"TITLE {title or structure.composition.reduced_formula} {absorber} {edge} "
              f"site {site_index}"),
             ]
    if code == "feff8":
        lines += [f"EDGE {edge}", f"S02 {s02:.1f}", "CONTROL 1 1 1 1 1 1", "PRINT 1 0 0 0 0 3",
                  f"SCF {scf:.2f} 0 30 0.2 1", f"EXCHANGE {int(exchange)} 0 0"]
    else:
        lines += [f"HOLE {HOLE[edge]} {s02:.1f}", "CONTROL 1 1 1 1", "PRINT 1 0 0 0"]
    lines += [f"RMAX {rmax:.2f}", f"NLEG {nleg}", "", "POTENTIALS",
             f"  0 {Element(absorber).Z:3d} {absorber}"]
    for sym, i in ipot.items():
        lines.append(f"  {i} {Element(sym).Z:3d} {sym}")
    lines += ["", "ATOMS"]
    for j, (d, sym, xyz) in enumerate(atoms):
        ip = 0 if j == 0 else ipot[sym]
        lines.append(f"  {xyz[0]:10.5f} {xyz[1]:10.5f} {xyz[2]:10.5f} {ip:3d} {sym:3s} {d:8.4f}")
    lines.append("END")
    return "\n".join(lines) + "\n"


RUN_DIR, FAILED_DIR = "_feffrun", "_feff_failed"    # run_feff 的运行中 / 失败现场子目录（不是 FEFF 结果目录）


def run_feff(folder, feffinp_text=None, verbose=False, code=None):
    """在 folder 下的临时子目录 _feffrun 里运行 FEFF；成功（至少一条 feff[0-9]*.dat）才替换 folder 里的旧结果，
    失败则 folder 原样不动，失败现场保留在 folder/_feff_failed（含 feffrun_feff.log、feff.err）。"""
    import shutil
    from larch.xafs import feff6l, feff8l
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    tmp, failed = folder / RUN_DIR, folder / FAILED_DIR
    shutil.rmtree(tmp, ignore_errors=True)
    tmp.mkdir()
    if feffinp_text is not None:
        (tmp / "feff.inp").write_text(feffinp_text, encoding="utf-8")
    else:
        shutil.copyfile(folder / "feff.inp", tmp / "feff.inp")
    if code is None:                       # 由 feff.inp 判断
        code = "feff8" if re.search(r"^\s*(EDGE|SCF)\b", (tmp / "feff.inp").read_text(encoding="utf-8", errors="ignore"),
                                    re.M | re.I) else "feff6"
    err = None
    try:
        (feff8l if code == "feff8" else feff6l)(folder=str(tmp), feffinp="feff.inp", verbose=verbose)
    except Exception as e:                 # noqa: BLE001  先保留失败现场再原样抛出
        err = e
    if err is None and any(tmp.glob("feff[0-9]*.dat")):
        new = {f.name for f in tmp.iterdir()}
        for f in list(tmp.iterdir()):          # 先换入新文件（同名覆盖），再删多余的旧路径：中途出错也不会一条路径都没有
            os.replace(f, folder / f.name)
        for old in folder.glob("feff*.dat"):
            if old.name not in new:
                old.unlink()
        tmp.rmdir()
        shutil.rmtree(failed, ignore_errors=True)     # 旧的失败现场已过时
        return list_paths(folder)
    shutil.rmtree(failed, ignore_errors=True)
    os.replace(tmp, failed)
    if err is not None:
        raise err
    return pd.DataFrame()


def feff_info(folder):
    """FEFF 版本与自洽信息：{'code','scf','exchange','fermi_ev'}"""
    folder = Path(folder)
    inp = (folder / "feff.inp").read_text(errors="ignore", encoding="utf-8") if (folder / "feff.inp").exists() else ""
    info = dict(code="feff8" if re.search(r"^\s*(EDGE|SCF)\b", inp, re.M | re.I) else "feff6")
    m = re.search(r"^\s*SCF\s+([\d.]+)", inp, re.M | re.I)
    info["scf"] = float(m.group(1)) if m else None
    m = re.search(r"^\s*EXCHANGE\s+(\d+)", inp, re.M | re.I)
    info["exchange"] = int(m.group(1)) if m else 0
    log1 = folder / "log1.dat"
    mu = re.findall(r"mu_new=\s*([-\d.]+)", log1.read_text(errors="ignore", encoding="utf-8")) if log1.exists() else []
    info["fermi_ev"] = float(mu[-1]) if mu else None
    return info


def list_paths(folder):
    """读取 FEFF 输出目录，返回 DataFrame：file, reff, degen, nleg, amp_ratio, label"""
    from larch.xafs import feffpath
    folder = Path(folder)
    amp = {}
    fd = folder / "files.dat"
    if fd.exists():
        for line in fd.read_text(errors="ignore", encoding="utf-8").splitlines():
            m = re.match(r"\s*(feff\d+\.dat)\s+([\d.Ee+-]+)\s+([\d.Ee+-]+)\s+([\d.]+)\s+(\d+)\s+([\d.]+)",
                         line)
            if m:
                amp[m.group(1)] = float(m.group(3))
    ld = folder / "list.dat"               # FEFF8L
    if not amp and ld.exists():
        for line in ld.read_text(errors="ignore", encoding="utf-8").splitlines():
            m = re.match(r"\s*(\d+)\s+[\d.]+\s+([\d.]+)\s+[\d.]+\s+\d+\s+[\d.]+\s*$", line)
            if m:
                amp[f"feff{int(m.group(1)):04d}.dat"] = float(m.group(2))
    rows = []
    for f in sorted(folder.glob("feff[0-9]*.dat")):
        p = feffpath(str(f))
        geom = [a[0] for a in p.geom]  # 元素符号
        label = "-".join(geom) + ("-" + geom[0] if p.nleg > 2 else "")
        rows.append(dict(file=str(f), name=f.name, reff=round(p.reff, 4), degen=p.degen,
                         nleg=p.nleg, amp_ratio=amp.get(f.name, np.nan), label=label))
    return pd.DataFrame(rows)


def build(structure, absorber, edge, out, site_index=None, rmax=6.0, rcluster=8.0, nleg=4,
          title="", code="feff6", scf=4.5, exchange=0):
    # FEFF6L 在团簇过大时会在 istprm 处异常退出（无输出路径）；逐步减小团簇半径重试
    for rc in sorted({rcluster, 7.0, 6.5, rmax + 1.0}, reverse=True):
        if rc > rcluster or rc < rmax + 0.5:
            continue
        txt = make_feffinp(structure, absorber, edge, site_index=site_index, rmax=rmax,
                           rcluster=rc, nleg=nleg, title=title, code=code, scf=scf,
                           exchange=exchange)
        df = run_feff(out, txt, code=code)
        if len(df):
            return df
    raise FeffError(f"FEFF 未生成路径，失败现场见 {Path(out) / FAILED_DIR}（feffrun_feff.log、feff.err）；原有结果未改动")


def default_edge(element):
    """FEFF 页的缺省吸收边：Z ≤ 40 用 K，否则 L3"""
    from pymatgen.core import Element
    return "K" if Element(element).Z <= 40 else "L3"


def builtin_feff_dir(name, absorber, edge, site_index=0):
    """内置结构的 FEFF 输出文件夹：output/feff/<结构>_<元素><边>/site<n>（与 FEFF 路径页内置结构的默认输出目录相同）"""
    from . import paths
    return paths.FEFF / f"{name}_{absorber}{edge}" / f"site{site_index}"


def n_absorber_sites(name, absorber):
    """内置结构里吸收元素的不等价位点数（> 1 时 build_builtin 只算第一个位点，第一壳层只代表该位点）"""
    from .structures import builtin
    return len(inequivalent_sites(builtin(name), absorber))


def build_builtin(name, absorber, edge, recompute=False, progress=None):
    """用内置结构跑 FEFF6L（参数同 FEFF 页缺省：RMAX 6 Å、NLEG 4、第一个不等价位点）。
    返回 (输出文件夹, 是否沿用已有结果)；已有 feff0001.dat 且 recompute=False 时不重算。"""
    from .structures import builtin
    struct = builtin(name)
    sites = inequivalent_sites(struct, absorber)
    if not sites:
        raise ValueError(f"结构 {name} 不含吸收元素 {absorber} / structure {name} has no {absorber} atom")
    out = builtin_feff_dir(name, absorber, edge, sites[0][0])
    if not recompute and (out / "feff0001.dat").exists():
        return out, True
    if progress:
        progress(0.2, "FEFF6L…")
    build(struct, absorber, edge, out, site_index=sites[0][0], title=name, code="feff6")
    return out, False
