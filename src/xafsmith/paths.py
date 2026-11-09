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
from pathlib import Path

MARKER = "xafsmith.json"
SCHEMA_VERSION = "1.0"


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


def set_root(root):
    """设定项目根目录并重算全部标准路径（图形界面切换项目时调用）。"""
    g = globals()
    root = Path(root).expanduser().resolve()
    out = root / "output"
    g.update(ROOT=root, CONFIG=root / MARKER, PROJECT_MD=root / "project.md", DATA=root / "data",
             RAW=root / "data" / "raw", META=root / "data" / "meta.csv", STRUCT=root / "structures",
             MODELS=root / "models", NOTES=root / "notes", SCRIPTS=root / "scripts", OUT=out,
             QC=out / "qc", CALIB=out / "calib", PROC=out / "processed", FEFF=out / "feff", FITS=out / "fits",
             LCF=out / "lcf", FIGS=out / "figs", REPORTS=out / "reports", GUI=out / "gui")
    g.update(CALIB_JSON=g["CALIB"] / "calib.json", QC_CSV=g["QC"] / "qc_report.csv",
             FITS_CSV=g["FITS"] / "exafs_fits.csv", LCF_CSV=g["LCF"] / "lcf_results.csv",
             INPUT_DIRS=(g["RAW"], g["STRUCT"], g["MODELS"], g["NOTES"]),
             OUTPUT_DIRS=(g["QC"], g["CALIB"], g["PROC"], g["FEFF"], g["FITS"], g["LCF"], g["FIGS"],
                          g["REPORTS"], g["GUI"]))
    os.environ["XAFSMITH_PROJECT"] = str(root)
    return root


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
