"""项目目录标准（XAFSmith 项目 = 一个包含 xafsmith.json 的文件夹）。

    <项目>/
    ├── xafsmith.json        项目标识与处理参数（原 config.json）
    ├── project.md           体系信息与结论
    ├── data/
    │   ├── raw/<批次>/…     原始数据（只读；也可以在 meta.csv 中引用项目内任意位置的原始文件）
    │   └── meta.csv         数据登记表（每个原始文件一行）
    ├── structures/          结构文件：CIF / POSCAR / XYZ / feff.inp
    ├── models/              EXAFS 拟合模型 JSON
    ├── notes/               分析记录（日期_主题.md）
    ├── scripts/             项目专用分析脚本（可选）
    └── output/              全部生成结果（可随时删除后重新生成）
        ├── qc/  calib/  processed/  feff/  fits/  lcf/  figs/  reports/  gui/

项目根目录的确定顺序：环境变量 XAFSMITH_PROJECT → 当前目录向上查找 xafsmith.json → 当前目录。
"""
import os
from dataclasses import dataclass
from pathlib import Path

from . import defaults

MARKER = "xafsmith.json"
SCHEMA_VERSION = "1.1"
USER_DIR = defaults.USER_DIR      # 用户级目录：日志、最近项目、设置（定义在 defaults，见那里的说明）

# 下面这些名字由 set_root() 在导入时与每次切换项目时写入模块（只声明类型，供 mypy 与编辑器识别；声明本身不产生任何值）
ROOT: Path
CONFIG: Path
PROJECT_MD: Path
DATA: Path
RAW: Path
META: Path
STRUCT: Path
MODELS: Path
NOTES: Path
SCRIPTS: Path
OUT: Path
QC: Path
CALIB: Path
PROC: Path
FEFF: Path
FITS: Path
LCF: Path
XANES: Path
FIGS: Path
PUBFIGS: Path
REPORTS: Path
GUI: Path
CALIB_JSON: Path
QC_CSV: Path
FITS_CSV: Path
LCF_CSV: Path
XANES_CSV: Path
INPUT_DIRS: tuple[Path, ...]
OUTPUT_DIRS: tuple[Path, ...]


def find_root(start=None):
    env = os.environ.get("XAFSMITH_PROJECT")
    if env:
        return Path(env).expanduser().resolve()
    p = Path(start or Path.cwd()).resolve()
    for d in (p, *p.parents):
        if (d / MARKER).exists():
            return d
    return p


STRUCT_EXT = (".cif", ".vasp", ".poscar", ".json")     # 另支持文件名 POSCAR / CONTCAR


@dataclass(frozen=True)
class Project:
    """一个项目的全部标准路径（只由根目录决定）。属性即各标准路径；module_vars() 给出本模块的大写模块变量。"""
    root: Path

    @classmethod
    def from_root(cls, root):
        return cls(Path(root).expanduser().resolve())

    @property
    def config(self): return self.root / MARKER
    @property
    def project_md(self): return self.root / "project.md"
    @property
    def data(self): return self.root / "data"
    @property
    def raw(self): return self.root / "data" / "raw"
    @property
    def meta(self): return self.root / "data" / "meta.csv"
    @property
    def struct(self): return self.root / "structures"
    @property
    def models(self): return self.root / "models"
    @property
    def notes(self): return self.root / "notes"
    @property
    def scripts(self): return self.root / "scripts"
    @property
    def out(self): return self.root / "output"
    @property
    def qc(self): return self.out / "qc"
    @property
    def calib(self): return self.out / "calib"
    @property
    def proc(self): return self.out / "processed"
    @property
    def feff(self): return self.out / "feff"
    @property
    def fits(self): return self.out / "fits"
    @property
    def lcf(self): return self.out / "lcf"
    @property
    def xanes(self): return self.out / "xanes"
    @property
    def figs(self): return self.out / "figs"
    @property
    def pubfigs(self): return self.out / "figs" / "journal"
    @property
    def reports(self): return self.out / "reports"
    @property
    def gui(self): return self.out / "gui"
    @property
    def calib_json(self): return self.calib / "calib.json"
    @property
    def qc_csv(self): return self.qc / "qc_report.csv"
    @property
    def fits_csv(self): return self.fits / "exafs_fits.csv"
    @property
    def lcf_csv(self): return self.lcf / "lcf_results.csv"
    @property
    def xanes_csv(self): return self.xanes / "xanes_features.csv"
    @property
    def input_dirs(self): return (self.raw, self.struct, self.models, self.notes)
    @property
    def output_dirs(self):
        return (self.qc, self.calib, self.proc, self.feff, self.fits, self.lcf, self.xanes,
                self.figs, self.reports, self.gui)

    def module_vars(self):
        """本模块的大写模块变量（ROOT … OUTPUT_DIRS，共 29 个）→ 值。"""
        return {"ROOT": self.root, "CONFIG": self.config, "PROJECT_MD": self.project_md, "DATA": self.data,
                "RAW": self.raw, "META": self.meta, "STRUCT": self.struct, "MODELS": self.models,
                "NOTES": self.notes, "SCRIPTS": self.scripts, "OUT": self.out, "QC": self.qc,
                "CALIB": self.calib, "PROC": self.proc, "FEFF": self.feff, "FITS": self.fits, "LCF": self.lcf,
                "XANES": self.xanes, "FIGS": self.figs, "PUBFIGS": self.pubfigs, "REPORTS": self.reports,
                "GUI": self.gui, "CALIB_JSON": self.calib_json, "QC_CSV": self.qc_csv,
                "FITS_CSV": self.fits_csv, "LCF_CSV": self.lcf_csv, "XANES_CSV": self.xanes_csv,
                "INPUT_DIRS": self.input_dirs, "OUTPUT_DIRS": self.output_dirs}


_CURRENT: Project


def current():
    """当前项目（set_root 设定的那个）。"""
    return _CURRENT


def set_root(root):
    """设定项目根目录并重算全部标准路径（图形界面切换项目时调用）。"""
    global _CURRENT
    _CURRENT = Project.from_root(root)
    globals().update(_CURRENT.module_vars())
    os.environ["XAFSMITH_PROJECT"] = str(_CURRENT.root)
    return _CURRENT.root


def is_project(root):
    return (Path(root) / MARKER).exists()


set_root(find_root())


def ensure(dirs=None):
    for d in dirs or INPUT_DIRS + OUTPUT_DIRS:
        Path(d).mkdir(parents=True, exist_ok=True)


def rel(p):
    """项目内相对路径（正斜杠）；项目外的路径原样返回。"""
    p = Path(p).resolve()
    try:
        return p.relative_to(ROOT).as_posix()
    except ValueError:
        return p.as_posix()


def resolve(p, base=None):
    """相对路径按项目根目录解释。"""
    p = Path(p)
    return p if p.is_absolute() else (base or ROOT) / p


def structure_file(name):
    """结构文件：给路径就用路径；只给文件名（或不带扩展名）就在 structures/ 中查找。"""
    p = resolve(name)
    if p.exists():
        return p
    for ext in ("",) + STRUCT_EXT:
        q = STRUCT / f"{name}{ext}"
        if q.exists():
            return q
    raise FileNotFoundError(f"找不到结构文件 {name}（已在 {rel(STRUCT)}/ 中查找）")


def model_file(name):
    """拟合模型：给路径就用路径；只给模型名就在 models/ 中查找。"""
    p = resolve(name)
    if p.exists():
        return p
    q = MODELS / (name if str(name).endswith(".json") else f"{name}.json")
    if q.exists():
        return q
    raise FileNotFoundError(f"找不到模型 {name}（已在 {rel(MODELS)}/ 中查找）")
