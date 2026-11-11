"""check_move —— 校验“只搬不改”：旧单文件（取自 git HEAD）中每个顶层 def/class/赋值，
必须在新包的某个子模块里以完全相同的语法树（ast.dump）出现；并且旧文件的每个顶层名字
都能从新包（import）取到。

用法（在 XAFSmith 仓库根目录运行）：
    python tools/check_move.py src/xafsmith/qt/widgets.py src/xafsmith/qt/widgets
    python tools/check_move.py src/xafsmith/qt/pages/process.py src/xafsmith/qt/pages/process \
           --extra src/xafsmith/qt/pages/_common.py
旧文件已被删除也可以：旧内容固定从 git HEAD 读取（--rev 可改）。
"""
from __future__ import annotations

import argparse
import ast
import importlib
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class _Dots(ast.NodeTransformer):
    """新文件比旧文件深 N 层：函数体里的相对导入多 N 个点，比较前减回去"""
    def __init__(self, n):
        self.n = n

    def visit_ImportFrom(self, node):
        if self.n and node.level > self.n:
            node.level -= self.n
        return node


def _top_nodes(src: str, dots: int = 0):
    """顶层节点 → {名字: ast.dump}；顶层 import 语句不比较（搬移后导入位置必然不同）"""
    out = {}
    tree = ast.parse(src)
    if dots:
        tree = _Dots(dots).visit(tree)
    for n in tree.body:
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            out[n.name] = ast.dump(n)
        elif isinstance(n, (ast.Assign, ast.AnnAssign)):
            tg = n.targets if isinstance(n, ast.Assign) else [n.target]
            names = [t.id for t in tg if isinstance(t, ast.Name)]
            for nm in names:
                out[nm] = ast.dump(n)
    return out


def _git_show(rel: str, rev: str) -> str:
    return subprocess.run(["git", "show", f"{rev}:{rel}"], cwd=ROOT, capture_output=True, text=True,
                          encoding="utf-8", check=True).stdout


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("old")
    ap.add_argument("new_pkg")
    ap.add_argument("--extra", nargs="*", default=[], help="另外接收被搬走内容的文件")
    ap.add_argument("--rev", default="HEAD")
    ap.add_argument("--dots", type=int, default=0, help="新包比旧文件深几层（函数体内相对导入多几个点）")
    a = ap.parse_args()

    old_rel = Path(a.old).as_posix()
    old = _top_nodes(_git_show(old_rel, a.rev))
    new = {}
    files = list((ROOT / a.new_pkg).glob("*.py")) + [ROOT / e for e in a.extra]
    for f in files:
        for k, v in _top_nodes(f.read_text(encoding="utf-8"), a.dots if f.parent == ROOT / a.new_pkg else 0).items():
            if k in new and new[k] != v and f.name != "__init__.py":
                print(f"  [警告] {k} 在多个新文件中定义且不同：{f.name}")
            new.setdefault(k, v)
    bad = 0
    for k, v in old.items():
        if k not in new:
            print(f"缺失：{k}")
            bad += 1
        elif new[k] != v:
            print(f"被改动：{k}")
            bad += 1
    extra = sorted(set(new) - set(old))
    if extra:
        print("新增名字（应只有再导出/包装）：", ", ".join(extra))

    # 旧导入路径：旧文件的每个顶层名字必须能从新包取到
    sys.path.insert(0, str(ROOT / "src"))
    modname = ".".join(Path(a.new_pkg).relative_to("src").parts)
    mod = importlib.import_module(modname)
    for k in old:
        if not hasattr(mod, k):
            print(f"导入不到：{modname}.{k}")
            bad += 1
    print(f"旧顶层名字 {len(old)} 个，问题 {bad} 个")
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
