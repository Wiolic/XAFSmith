"""structures —— 内置标准结构（pymatgen Structure），以及 CIF 读入。

内置结构的晶胞参数来源均写在 SOURCES 中，均为常见文献/ICSD 室温值；
需要更高精度时把 CIF / POSCAR 放进项目的 structures/ 文件夹（read_structure）。

用法：
  python -m xafsmith.structures            # 列出内置结构
  python -m xafsmith.structures IrO2       # 打印结构
"""
import sys
from pathlib import Path

from pymatgen.core import Lattice, Structure

SOURCES = {
    "Ir": "fcc Fm-3m, a=3.8390 Å (Wyckoff, Crystal Structures 1963)",
    "Ta": "bcc Im-3m, a=3.3058 Å (Wyckoff 1963)",
    "Co_hcp": "hcp P6_3/mmc, a=2.5071, c=4.0695 Å (Wyckoff 1963)",
    "Co_fcc": "fcc Fm-3m, a=3.5447 Å (β-Co)",
    "IrO2": "rutile P4_2/mnm, a=4.4983, c=3.1544 Å, O x=0.3077 (Bolzan et al. 1997)",
    "CoO": "rocksalt Fm-3m, a=4.2615 Å",
    "Co3O4": "spinel Fd-3m (origin 2), a=8.0837 Å, O 32e u=0.2633 (Liu & Prewitt 1990 近似值)",
    "KTaO3": "cubic perovskite Pm-3m, a=3.9885 Å",
    "Ta2O5_approx": "未内置：Ta2O5 多晶型、结构复杂，请提供 CIF",
}


def builtin(name):
    if name == "Ir":
        return Structure.from_spacegroup("Fm-3m", Lattice.cubic(3.8390), ["Ir"], [[0, 0, 0]])
    if name == "Ta":
        return Structure.from_spacegroup("Im-3m", Lattice.cubic(3.3058), ["Ta"], [[0, 0, 0]])
    if name == "Co_hcp":
        return Structure.from_spacegroup("P6_3/mmc", Lattice.hexagonal(2.5071, 4.0695), ["Co"],
                                         [[1 / 3, 2 / 3, 1 / 4]])
    if name == "Co_fcc":
        return Structure.from_spacegroup("Fm-3m", Lattice.cubic(3.5447), ["Co"], [[0, 0, 0]])
    if name == "IrO2":
        return Structure.from_spacegroup("P4_2/mnm", Lattice.tetragonal(4.4983, 3.1544),
                                         ["Ir", "O"], [[0, 0, 0], [0.3077, 0.3077, 0]])
    if name == "CoO":
        return Structure.from_spacegroup("Fm-3m", Lattice.cubic(4.2615), ["Co", "O"],
                                         [[0, 0, 0], [0.5, 0.5, 0.5]])
    if name == "Co3O4":
        # origin choice 2: Co(tet) 8a (1/8,1/8,1/8), Co(oct) 16d (1/2,1/2,1/2), O 32e (u,u,u)
        return Structure.from_spacegroup(227, Lattice.cubic(8.0837), ["Co", "Co", "O"],
                                         [[0.125, 0.125, 0.125], [0.5, 0.5, 0.5],
                                          [0.2633, 0.2633, 0.2633]])
    if name == "KTaO3":
        return Structure.from_spacegroup("Pm-3m", Lattice.cubic(3.9885), ["Ta", "K", "O"],
                                         [[0, 0, 0], [0.5, 0.5, 0.5], [0.5, 0, 0]])
    raise KeyError(f"无内置结构 {name}；可用：{[k for k in SOURCES if 'approx' not in k]}")


BUILTIN_NAMES = [k for k in SOURCES if "approx" not in k]


def read_cif(path_or_text):
    """CIF 文件路径、structures/ 中的文件名，或 CIF 文本"""
    import io
    from pymatgen.io.cif import CifParser
    s = str(path_or_text)
    if len(s) < 500 and chr(10) not in s:
        return read_structure(s)
    return CifParser(io.StringIO(s)).parse_structures(primitive=False)[0]


def read_structure(name):
    """读结构文件（structures/ 中的文件名或任意路径）：CIF、POSCAR/CONTCAR/.vasp、pymatgen JSON"""
    from pymatgen.core import Structure
    from pymatgen.io.cif import CifParser
    from .paths import structure_file
    p = structure_file(name)
    if p.suffix.lower() == ".cif":
        return CifParser(str(p)).parse_structures(primitive=False)[0]
    return Structure.from_file(str(p))


def list_structures():
    """structures/ 中可用的结构文件（相对 structures/ 的路径）"""
    from .paths import STRUCT, STRUCT_EXT
    if not STRUCT.exists():
        return []
    return sorted(p.relative_to(STRUCT).as_posix() for p in STRUCT.rglob("*")
                  if p.is_file() and (p.suffix.lower() in STRUCT_EXT or p.name in ("POSCAR", "CONTCAR")))


def export_builtin(dest=None):
    """把内置结构导出为 CIF（默认到 structures/builtin/），便于查看与复用"""
    from pymatgen.io.cif import CifWriter
    from .paths import STRUCT
    dest = Path(dest or STRUCT / "builtin")
    dest.mkdir(parents=True, exist_ok=True)
    out = []
    for n in BUILTIN_NAMES:
        f = dest / f"{n}.cif"
        CifWriter(builtin(n)).write_file(str(f))
        out.append(f)
    return out


if __name__ == "__main__":
    if len(sys.argv) == 1:
        for k, v in SOURCES.items():
            print(f"{k:14s} {v}")
    else:
        print(builtin(sys.argv[1]))
