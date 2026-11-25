"""一致性测试（E16）：代码与文档、中英文、模块表之间的对应关系。
失败信息一次列出全部缺项。"""
import ast
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
PKG = ROOT / "src" / "xafsmith"
DOCS = PKG / "docs"
CJK = re.compile(r"[㐀-䶿一-鿿　-〿＀-￯]")
FILENAME = re.compile(r"\S+\.[A-Za-z0-9]{2,5}\b")      # 文件名（带扩展名）：其中的中文是文件的真实名字


def _fail(title, items):
    if items:
        pytest.fail(f"{title}（{len(items)} 项）:\n  " + "\n  ".join(items), pytrace=False)


# 1. CLI 子命令 <-> 命令行速查 ------------------------------------------------

def cli_command_names():
    """子命令主名。别名 = 指向同一个 parser 对象（add_parser(aliases=...)），或像 gui / app 那样
    登记了多个 parser 却共用同一个处理函数（set_defaults 的 f）。登记时主名在先，
    所以按“处理函数（无则 parser 对象）”去重，取 choices 中最先出现的名字即主名。"""
    import argparse
    from xafsmith.cli import build_parser
    sub = next(a for a in build_parser()._actions if isinstance(a, argparse._SubParsersAction))
    seen, names = set(), []
    for name, parser in sub.choices.items():
        ident = parser.get_default("f") or id(parser)
        if ident in seen:
            continue
        seen.add(ident)
        names.append(name)
    return names


def test_cli_commands_in_reference():
    text = (DOCS / "命令行速查.md").read_text(encoding="utf-8")
    names = cli_command_names()
    assert names
    missing = [f"缺子命令: xafsmith {n}" for n in names
               if not re.search(rf"xafsmith {re.escape(n)}(?![\w-])", text)]
    _fail("命令行速查.md 缺少以下子命令", missing)


# 2. 页面标题 <-> 两份 GUI 指南 -------------------------------------------------

def gui_pages():
    pytest.importorskip("PySide6")
    from xafsmith.qt.app import SpectraTabs, page_specs
    classes = [spec[1] for spec in page_specs() if spec is not None]
    classes += list(SpectraTabs.sub_pages)
    seen, out = set(), []
    for c in classes:
        if c.key in seen:
            continue
        seen.add(c.key)
        if not c.hidden:
            out.append(c)
    return out


def test_page_titles_in_gui_guides():
    pages = gui_pages()
    zh = (DOCS / "图形界面使用指南.md").read_text(encoding="utf-8")
    en = (DOCS / "GUI_guide_en.md").read_text(encoding="utf-8")
    missing = []
    for c in pages:
        if c.title_zh not in zh:
            missing.append(f"图形界面使用指南.md 缺页面标题「{c.title_zh}」（key={c.key}）")
        if c.title_en not in en:
            missing.append(f"GUI_guide_en.md 缺页面标题 “{c.title_en}”（key={c.key}）")
    _fail("GUI 指南缺少以下页面标题", missing)


# 3. T() 双语 ----------------------------------------------------------------

def scan_T_calls():
    calls = []
    for f in sorted(PKG.rglob("*.py")):
        if "__pycache__" in f.parts:
            continue
        tree = ast.parse(f.read_text(encoding="utf-8"), filename=str(f))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            fn = node.func
            if (isinstance(fn, ast.Name) and fn.id == "T") or (isinstance(fn, ast.Attribute) and fn.attr == "T"):
                calls.append((f.relative_to(ROOT).as_posix(), node))
    return calls


def test_T_calls_bilingual():
    calls = scan_T_calls()
    assert calls
    bad = []
    for rel, node in calls:
        where = f"{rel}:{node.lineno}"
        if any(isinstance(a, ast.Starred) for a in node.args):
            continue   # T(*表[键])：参数来自变量，与 f-string 一样不查
        if len(node.args) != 2 or node.keywords:
            bad.append(f"{where}: T() 须恰好 2 个位置参数且无关键字参数（现为 {len(node.args)} 个位置、{len(node.keywords)} 个关键字）")
            continue
        a, b = node.args
        if not (isinstance(a, ast.Constant) and isinstance(a.value, str)
                and isinstance(b, ast.Constant) and isinstance(b.value, str)):
            continue   # f-string / 变量：只查常量
        if not b.value.strip():
            bad.append(f"{where}: 英文为空 T({a.value!r}, {b.value!r})")
        elif CJK.search(a.value) and CJK.search(FILENAME.sub("", b.value)):   # 中文文件名（如 汇总.xlsx）在英文里原样出现
            bad.append(f"{where}: 英文参数含中日韩字符 T({a.value!r}, {b.value!r})")
    _fail("T() 调用有问题", bad)


# 4. ARCHITECTURE.md <-> src ---------------------------------------------------

EXCLUDE_NAMES = {"__init__.py", "__main__.py"}
EXCLUDE_DIRS = {"__pycache__", "structures_builtin", "assets", "docs", "templates"}


def src_modules():
    out = []
    for f in sorted(PKG.rglob("*.py")):
        rel = f.relative_to(PKG)
        if f.name in EXCLUDE_NAMES or EXCLUDE_DIRS & set(rel.parts):
            continue
        out.append(rel.as_posix())
    return out


def _mentioned(rel, text):
    """相对路径（自 src/xafsmith 起）或文件名出现在文本中；文件名前不能紧接字母数字下划线，
    以免 `io.py` 误中 `fit_io.py`。"""
    if rel in text:
        return True
    name = rel.rsplit("/", 1)[-1]
    return re.search(rf"(?<![\w]){re.escape(name)}(?![\w])", text) is not None


def test_architecture_matches_src():
    text = (ROOT / "ARCHITECTURE.md").read_text(encoding="utf-8")
    mods = src_modules()
    assert mods
    problems = [f"ARCHITECTURE.md 缺模块文件: {m}" for m in mods if not _mentioned(m, text)]
    # 文档里反引号中的 xxx.py 必须对应存在的文件（仓库内任意位置，如 tests/、packaging/）
    existing = [p.relative_to(ROOT).as_posix() for p in ROOT.rglob("*.py")
                if not ({".venv", "dist", "build", "__pycache__", ".git"} & set(p.relative_to(ROOT).parts))]
    for m in sorted(set(re.findall(r"`([\w./-]+\.py)`", text))):
        if not any(e == m or e.endswith("/" + m) for e in existing):
            problems.append(f"ARCHITECTURE.md 写了不存在的文件: {m}")
    _fail("ARCHITECTURE.md 与 src 不一致", problems)
