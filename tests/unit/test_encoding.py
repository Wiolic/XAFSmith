"""所有文本读写必须显式写 encoding。

没写 encoding 时 Python 用系统默认编码：中文 Windows 是 cp936（能编码中文），英文 Windows 是 cp1252（不能），
于是在开发机上正常、在别人电脑上一写中文表头就崩溃（1.0.0 试构建时 CI 上 `xafsmith-cli process` 因此失败）。
CI 设置了 PYTHONUTF8=1，运行时测不出这类问题，所以这里直接检查源码。
"""
import ast
from pathlib import Path

SRC = Path(__file__).resolve().parents[2] / "src" / "xafsmith"


def _missing_encoding():
    out = []
    for f in sorted(SRC.rglob("*.py")):
        tree = ast.parse(f.read_text(encoding="utf-8"))
        for n in ast.walk(tree):
            if not isinstance(n, ast.Call) or any(k.arg == "encoding" for k in n.keywords):
                continue
            name = n.func.attr if isinstance(n.func, ast.Attribute) else (n.func.id if isinstance(n.func, ast.Name) else "")
            if name in ("savetxt", "loadtxt", "genfromtxt", "write_text"):
                bad = True
            elif name == "read_text":
                bad = not n.args                     # importlib 的 dist.read_text("文件名") 不是文件读写
            elif name == "open" and isinstance(n.func, ast.Name):
                mode = n.args[1].value if len(n.args) > 1 and isinstance(n.args[1], ast.Constant) else None
                for k in n.keywords:
                    if k.arg == "mode" and isinstance(k.value, ast.Constant):
                        mode = k.value.value
                bad = mode is None or "b" not in str(mode)
            else:
                bad = False
            if bad:
                out.append(f"{f.relative_to(SRC.parent)}:{n.lineno} {name}()")
    return out


def test_text_io_has_explicit_encoding():
    missing = _missing_encoding()
    assert not missing, "这些文本读写没有写 encoding=\"utf-8\"：\n" + "\n".join(missing)
