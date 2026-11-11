"""readers —— 数据读入的格式插件。入口：detect_format / read_file / read_scan。

pipeline 与图形界面统一只调用 read_scan（见 docs/dev/io_readers.md）。
"""
from pathlib import Path

from .base import ReadError, Reader, guess_element_edge     # noqa: F401
from .formats import (AthenaXmuReader, BsrfReader, ColumnsReader, PrjReader, XdacReader,  # noqa: F401
                      XdiReader)

REGISTRY = [BsrfReader(), XdiReader(), AthenaXmuReader(), XdacReader(), PrjReader(), ColumnsReader()]
BY_NAME = {r.name: r for r in REGISTRY}


def list_formats():
    """[(名称, 中文说明, English)]，用于 `xafsmith formats` 与界面。"""
    return [(r.name, r.label[0], r.label[1]) for r in REGISTRY]


def _head(path, n=4096):
    with open(path, "r", encoding="utf-8", errors="ignore") as f:
        return f.read(n)


def detect_format(path):
    """→ (reader 名, 置信度)；置信度 < 30 视为未知格式（返回 (None, score)）。"""
    path = Path(path)
    try:
        head = _head(path)
    except OSError as ex:
        raise ReadError(f"无法打开 {path.name}：{ex}", f"Cannot open {path.name}: {ex}")
    best, score = None, 0
    for r in REGISTRY:
        s = r.detect(path, head)
        if s > score:
            best, score = r.name, s
    return (best, score) if score >= 30 else (None, score)


def resolve_format(fmt, templates=None, columns=None, mode=None):
    """fmt 可以是 reader 名，也可以是 xafsmith.json "formats" 中的模板名 → (reader 名, 列映射, 模式)。"""
    templates = templates or {}
    if fmt in templates:
        tpl = dict(templates[fmt])
        base = tpl.pop("base", "columns")
        tmode = tpl.pop("mode", None)
        columns = {**tpl, **(columns or {})}
        return base, columns, mode or tmode
    return fmt, columns, mode


def read_file(path, fmt=None, mode=None, columns=None, group=None, templates=None):
    """读入一个文件，返回 Group 列表（.prj 可含多组）。fmt 为空时自动识别。"""
    path = Path(path)
    fmt, columns, mode = resolve_format(fmt or None, templates, columns, mode)
    if not fmt:
        fmt, score = detect_format(path)
        if not fmt:
            raise ReadError(f"{path.name}：无法识别文件格式（置信度 {score}）。可在“格式”中指定，或保存列映射模板",
                            f"{path.name}: unknown file format (score {score}); choose a format or save a column template")
    if fmt not in BY_NAME:
        raise ReadError(f"未知的格式名“{fmt}”，可用：{', '.join(BY_NAME)}",
                        f"Unknown format '{fmt}'; available: {', '.join(BY_NAME)}")
    return BY_NAME[fmt].read(path, mode=mode, columns=columns, group=group)


def read_scan(path, fmt=None, mode=None, columns=None, group=None, templates=None):
    """读入一条谱 → 单个 Group。多组文件（.prj）必须用 group 指定组名。"""
    gs = read_file(path, fmt=fmt, mode=mode, columns=columns, group=group, templates=templates)
    if len(gs) == 1:
        return gs[0]
    names = [getattr(g, "group_name", g.label) for g in gs]
    raise ReadError(f"{Path(path).name} 含 {len(gs)} 组谱，请指定 group：{names}",
                    f"{Path(path).name} has {len(gs)} groups; specify one: {names}")
