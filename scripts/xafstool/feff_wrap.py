"""feff_wrap —— 结构（CIF 或内置）→ feff.inp → 运行 FEFF6L（xraylarch 自带）→ 路径列表。

用法：
  python -m xafstool.feff_wrap --builtin IrO2 --absorber Ir --edge L3 --out feff/IrO2
  python -m xafstool.feff_wrap --cif my.cif --absorber Ta --edge L3 --out feff/Ta2O5 --rmax 6
"""
import argparse
import re
from pathlib import Path

import numpy as np
import pandas as pd

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
                 nleg=4, title="", max_atoms=500, s02=1.0):
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
    lines = [f"TITLE {title or structure.composition.reduced_formula} {absorber} {edge} "
             f"site {site_index}",
             f"HOLE {HOLE[edge]} {s02:.1f}",
             "CONTROL 1 1 1 1", "PRINT 1 0 0 0",
             f"RMAX {rmax:.2f}", f"NLEG {nleg}", "", "POTENTIALS",
             f"  0 {Element(absorber).Z:3d} {absorber}"]
    for sym, i in ipot.items():
        lines.append(f"  {i} {Element(sym).Z:3d} {sym}")
    lines += ["", "ATOMS"]
    for j, (d, sym, xyz) in enumerate(atoms):
        ip = 0 if j == 0 else ipot[sym]
        lines.append(f"  {xyz[0]:10.5f} {xyz[1]:10.5f} {xyz[2]:10.5f} {ip:3d} {sym:3s} {d:8.4f}")
    lines.append("END")
    return "\n".join(lines) + "\n"


def run_feff(folder, feffinp_text=None, verbose=False):
    from larch.xafs import feff6l
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    if feffinp_text is not None:
        (folder / "feff.inp").write_text(feffinp_text)
    for old in folder.glob("feff*.dat"):
        old.unlink()
    feff6l(folder=str(folder), feffinp="feff.inp", verbose=verbose)
    return list_paths(folder)


def list_paths(folder):
    """读取 FEFF 输出目录，返回 DataFrame：file, reff, degen, nleg, amp_ratio, label"""
    from larch.xafs import feffpath
    folder = Path(folder)
    amp = {}
    fd = folder / "files.dat"
    if fd.exists():
        for line in fd.read_text(errors="ignore").splitlines():
            m = re.match(r"\s*(feff\d+\.dat)\s+([\d.Ee+-]+)\s+([\d.Ee+-]+)\s+([\d.]+)\s+(\d+)\s+([\d.]+)",
                         line)
            if m:
                amp[m.group(1)] = float(m.group(3))
    rows = []
    for f in sorted(folder.glob("feff[0-9]*.dat")):
        p = feffpath(str(f))
        geom = [a[0] for a in p.geom]  # 元素符号
        label = "-".join(geom) + ("-" + geom[0] if p.nleg > 2 else "")
        rows.append(dict(file=str(f), name=f.name, reff=round(p.reff, 4), degen=p.degen,
                         nleg=p.nleg, amp_ratio=amp.get(f.name, np.nan), label=label))
    return pd.DataFrame(rows)


def build(structure, absorber, edge, out, site_index=None, rmax=6.0, rcluster=8.0, nleg=4,
          title=""):
    # FEFF6L 在团簇过大时会在 istprm 处异常退出（无输出路径）；逐步减小团簇半径重试
    for rc in sorted({rcluster, 7.0, 6.5, rmax + 1.0}, reverse=True):
        if rc > rcluster or rc < rmax + 0.5:
            continue
        txt = make_feffinp(structure, absorber, edge, site_index=site_index, rmax=rmax,
                           rcluster=rc, nleg=nleg, title=title)
        df = run_feff(out, txt)
        if len(df):
            return df
    raise RuntimeError(f"FEFF 未生成路径，见 {out}/feffrun_feff.log")


def main():
    from .structures import builtin, read_cif
    from .common import PROJECT_ROOT
    ap = argparse.ArgumentParser()
    ap.add_argument("--builtin")
    ap.add_argument("--cif")
    ap.add_argument("--absorber", required=True)
    ap.add_argument("--edge", default="K")
    ap.add_argument("--rmax", type=float, default=6.0)
    ap.add_argument("--site", type=int, default=None)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    s = builtin(a.builtin) if a.builtin else read_cif(a.cif)
    print("不等价吸收位点:", inequivalent_sites(s, a.absorber))
    df = build(s, a.absorber, a.edge, a.out, site_index=a.site, rmax=a.rmax,
               title=a.builtin or Path(a.cif).stem)
    print(df[["name", "label", "reff", "degen", "nleg", "amp_ratio"]].to_string(index=False))


if __name__ == "__main__":
    main()
