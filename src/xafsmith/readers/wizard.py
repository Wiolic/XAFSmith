"""列映射向导的后台（不依赖界面，可单独测试）：预览文件的列、把用户的选择变成 xafsmith.json "formats" 模板、试读。

模板格式见 docs/数据标准.md：{"base": "columns", "energy": 列名或列号, "i0": …, "it": …, "if": 列名/列号或列表, "mu": …, "mode": "trans|fluo"}
"""
from pathlib import Path

import numpy as np

from .base import ReadError, auto_roles, header_names, read_text, split_table

ROLES = ("energy", "i0", "it", "if", "mu")


def inspect_file(path, nrows=8):
    """预览：{names, ncols, ntotal, rows(前 nrows 行), auto{角色: [列号]}, auto_warnings, header}。
    names 为 None 表示文件没有可识别的列名行（只能按列号映射）。"""
    pre, data = split_table(read_text(path))
    names, _units = header_names(pre, data.shape[1])
    auto, warns = {}, []
    if names:
        auto, warns, _hint = auto_roles(names)
    return dict(names=names, ncols=int(data.shape[1]), ntotal=int(data.shape[0]), rows=data[:nrows].tolist(),
                auto=auto, auto_warnings=warns, header=pre[-5:])


def build_template(names, assignment, mode=None):
    """assignment: {角色: 列号 | [列号, …]}（空/None 的角色忽略）→ 模板字典。
    有列名且列名在文件中唯一时写列名（换文件列顺序也能用），否则写列号。"""
    tpl = {"base": "columns"}
    for role in ROLES:
        idx = assignment.get(role)
        if idx is None or idx == [] or idx == "":
            continue
        idx = [int(i) for i in (idx if isinstance(idx, (list, tuple)) else [idx])]
        vals = []
        for i in idx:
            nm = names[i] if names and 0 <= i < len(names) else None
            vals.append(nm if nm and sum(1 for x in names if x == nm) == 1 else i)
        tpl[role] = vals if role == "if" and len(vals) > 1 else vals[0]
    if "energy" not in tpl:
        raise ReadError("必须指定能量列", "The energy column is required")
    if "mu" not in tpl and "i0" not in tpl:
        raise ReadError("至少要指定 I0 与 It / If，或直接指定 μ 列", "Give I0 with It / If, or a μ column")
    if mode in ("trans", "fluo"):
        tpl["mode"] = mode
    return tpl


def try_read(path, template):
    """用模板试读一个文件 → 摘要字典（出错抛 ReadError，消息可直接显示）。"""
    from . import read_scan
    g = read_scan(path, fmt="columns", templates=None, columns={k: v for k, v in template.items() if k not in ("base",)},
                  mode=template.get("mode"))
    e = np.asarray(g.energy)
    return dict(mode=g.mode, npts=int(len(e)), e_min=float(e[0]), e_max=float(e[-1]), element=g.element, edge=g.edge,
                mu_min=float(np.nanmin(g.mu)), mu_max=float(np.nanmax(g.mu)),
                warnings=[w.split(" / ")[0] for w in getattr(g, "read_warnings", [])])


def add_template(cfg, name, template):
    """把模板写进 cfg["formats"][name]（返回 cfg）。名字不能为空，也不能和内置 reader 同名。"""
    from . import BY_NAME
    name = (name or "").strip()
    if not name:
        raise ReadError("请给模板起个名字", "Give the template a name")
    if name in BY_NAME or name == "columns_by_index" or name == "auto":
        raise ReadError(f"“{name}”是内置格式名，请换一个名字", f"'{name}' is a built-in format name")
    cfg.setdefault("formats", {})[name] = template
    return cfg
