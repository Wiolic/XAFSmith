"""哪些第三方包真被用到：在源码环境里跑 pytest（unit + benchmark）和 test_qt --quick（演示项目），
退出时把 sys.modules 的顶层包名写到 build/used_modules.txt。体积排除列表只能据此决定。

用法（在 XAFSmith/ 目录下）：
    ..\.venv\Scripts\python packaging/used_modules.py [--no-qt] [--no-pytest]
并列出“已安装但这次没被导入”的包（候选排除项；仍需再确认 larch/pymatgen 里是否为运行时按需导入）。
注意：只覆盖测试走到的路径；没走到的功能（如 SSRF 读入）若用到某包，需另补测试再下结论。
"""
import argparse, atexit, os, runpy, sys
from importlib import metadata
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "build" / "used_modules.txt"
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


def dump():
    stdlib = set(getattr(sys, "stdlib_module_names", ()))
    used = sorted({m.split(".")[0] for m in sys.modules if not m.startswith("_")} - stdlib)
    OUT.parent.mkdir(exist_ok=True)
    OUT.write_text("\n".join(used) + "\n", encoding="utf-8")
    # 已安装发行版 → 顶层包名
    top = {}
    for d in metadata.distributions():
        tl = (d.read_text("top_level.txt") or "").split()
        for t in tl or [d.metadata["Name"].replace("-", "_")]:
            top[t] = d.metadata["Name"]
    unused = sorted(t for t in top if t not in used and not t.startswith("_") and "." not in t)
    (OUT.parent / "unused_installed.txt").write_text("\n".join(f"{t}\t{top[t]}" for t in unused) + "\n", encoding="utf-8")
    print(f"\n已用顶层包 {len(used)} 个 → {OUT}\n已安装未用 {len(unused)} 个 → {OUT.parent / 'unused_installed.txt'}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-qt", action="store_true")
    ap.add_argument("--no-pytest", action="store_true")
    a = ap.parse_args()
    atexit.register(dump)
    sys.path.insert(0, str(ROOT / "src"))
    rc = 0
    if not a.no_pytest:
        import pytest
        rc |= int(pytest.main(["-q", "-x", str(ROOT / "tests" / "unit"), str(ROOT / "tests" / "benchmark")]))
    if not a.no_qt:
        sys.argv = [str(ROOT / "tests" / "test_qt.py"), "--quick"]
        try:
            runpy.run_path(sys.argv[0], run_name="__main__")
        except SystemExit as e:
            rc |= int(e.code or 0)
    sys.exit(rc)


if __name__ == "__main__":
    main()
