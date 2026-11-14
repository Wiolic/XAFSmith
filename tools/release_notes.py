"""从 CHANGELOG.md 取出某个版本的一节，作为 GitHub Release 的说明（release.yml 发布时用；也用于补写旧版本）。

  python tools/release_notes.py 1.3.1            # 打印到标准输出
  python tools/release_notes.py v1.3.1 -o notes.md
找不到该版本的一节时非零退出：发布前必须先写 CHANGELOG。
"""
import argparse
import re
import sys
from pathlib import Path

CHANGELOG = Path(__file__).resolve().parent.parent / "CHANGELOG.md"
REPO = "https://github.com/Wiolic/XAFSmith"


def section(version, text=None):
    """CHANGELOG 中 `## [version]` 一节的正文（不含标题行）；没有则返回 None。"""
    version = version.lstrip("v")
    text = CHANGELOG.read_text(encoding="utf-8") if text is None else text
    m = re.search(rf"^## \[{re.escape(version)}\][^\n]*\n(.*?)(?=^## \[|\Z)", text, re.M | re.S)
    return m.group(1).strip() if m else None


def previous(version, text=None):
    """CHANGELOG 中紧接在 version 之后（即更早）的一个版本号；没有则 None。"""
    version = version.lstrip("v")
    text = CHANGELOG.read_text(encoding="utf-8") if text is None else text
    vs = re.findall(r"^## \[(\d+\.\d+\.\d+)\]", text, re.M)
    return vs[vs.index(version) + 1] if version in vs and vs.index(version) + 1 < len(vs) else None


def _has_tag(tag):
    """本地仓库里有这个 tag（发布工作流须 fetch-depth: 0 才有全部 tag）；查不了就当没有。"""
    import subprocess
    try:
        out = subprocess.run(["git", "tag", "-l", tag], capture_output=True, text=True, cwd=CHANGELOG.parent, check=True)
    except (OSError, subprocess.CalledProcessError):
        return False
    return out.stdout.strip() == tag


def notes(version, text=None, has_tag=_has_tag):
    body = section(version, text)
    if body is None:
        return None
    v, prev = version.lstrip("v"), previous(version, text)
    tail = f"\n\n**Full Changelog**: {REPO}/compare/v{prev}...v{v}" if prev and has_tag(f"v{prev}") else ""
    return f"{body}\n\n完整的版本历史见 / Full history: [CHANGELOG.md]({REPO}/blob/v{v}/CHANGELOG.md){tail}\n"


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("version")
    ap.add_argument("-o", "--out")
    a = ap.parse_args(argv)
    n = notes(a.version)
    if n is None:
        print(f"CHANGELOG.md 中没有 [{a.version.lstrip('v')}] 一节 / no CHANGELOG section for {a.version}", file=sys.stderr)
        return 1
    if a.out:
        Path(a.out).write_text(n, encoding="utf-8")
    else:
        sys.stdout.reconfigure(encoding="utf-8")
        print(n)
    return 0


if __name__ == "__main__":
    sys.exit(main())
