"""体积审计：列出打包产物 _internal 下各项大小，写 build/size_report.csv，并与上一次比较。

用法（在 XAFSmith/ 目录下）：
    python packaging/size_report.py [dist/XAFSmith] [--limit-mb 550] [--forbid mkl pyarrow ...]
退出码：解压总大小超过 --limit-mb 或出现 --forbid 中的名字 → 1（供 build.ps1 / CI 作体积护栏）。
不是软件的一部分，不进安装包。
"""
import argparse, csv, re, sys
from pathlib import Path

DEFAULT_FORBID = ["mkl", "mkl_fft", "pyarrow", "botocore", "boto3", "sklearn", "skimage", "plotly", "pyFAI", "mypy", "mp_api", "emmet"]   # 与 xafsmith.spec 的 excludes 保持一致


def tree_size(p: Path) -> int:
    if p.is_file():
        return p.stat().st_size
    return sum(f.stat().st_size for f in p.rglob("*") if f.is_file())


def collect(root: Path):
    """返回 {条目名: 字节}；mkl*.dll 合并成一项 'mkl_*.dll'。"""
    internal = root / "_internal"
    base = internal if internal.is_dir() else root
    rows, mkl = {}, 0
    for e in base.iterdir():
        s = tree_size(e)
        if re.match(r"mkl_.*\.dll$", e.name, re.I):
            mkl += s
        else:
            rows[e.name] = s
    if mkl:
        rows["mkl_*.dll"] = mkl
    return rows, base


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("dist", nargs="?", default="dist/XAFSmith")
    ap.add_argument("--limit-mb", type=float, default=None, help="解压总大小上限（MB），超过则失败")
    ap.add_argument("--forbid", nargs="*", default=DEFAULT_FORBID, help="不应出现的包/文件名前缀")
    ap.add_argument("--out", default="build/size_report.csv")
    ap.add_argument("--top", type=int, default=25)
    a = ap.parse_args()

    root = Path(a.dist)
    if not root.is_dir():
        print(f"找不到 {root}"); return 2
    rows, base = collect(root)
    total_mb = sum(tree_size(f) for f in root.iterdir()) / 1e6

    out = Path(a.out); out.parent.mkdir(parents=True, exist_ok=True)
    prev = {}
    if out.exists():
        with open(out, encoding="utf-8-sig", newline="") as f:
            prev = {r["name"]: float(r["mb"]) for r in csv.DictReader(f) if r["name"] != "TOTAL"}
        prev_total = float(next((r["mb"] for r in csv.DictReader(open(out, encoding="utf-8-sig", newline="")) if r["name"] == "TOTAL"), 0))
    else:
        prev_total = 0.0

    items = sorted(rows.items(), key=lambda kv: -kv[1])
    print(f"{root}  合计 {total_mb:.0f} MB" + (f"（上次 {prev_total:.0f} MB，{total_mb - prev_total:+.0f}）" if prev_total else ""))
    for name, s in items[:a.top]:
        mb = s / 1e6
        d = f"  ({mb - prev[name]:+.1f})" if name in prev else ""
        print(f"  {mb:8.1f} MB  {name}{d}")

    with open(out, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f); w.writerow(["name", "mb"])
        w.writerow(["TOTAL", f"{total_mb:.1f}"])
        for name, s in items:
            w.writerow([name, f"{s / 1e6:.2f}"])
    print(f"已写 {out}")

    bad = []
    for e in base.iterdir():
        stem = e.name.lower().split(".")[0]
        for fb in a.forbid:
            if stem == fb.lower() or stem.startswith(fb.lower() + "_") or (fb.lower() == "mkl" and stem.startswith("mkl")):
                bad.append(e.name); break
    code = 0
    leaked = [str(f.relative_to(root)) for f in root.rglob("direct_url.json")]
    if leaked:                                    # pip -e 的标记文件含构建机本地路径，且会让程序以为是开发安装
        print("失败：安装包里有 direct_url.json：" + ", ".join(leaked)); code = 1
    if bad:
        print("失败：出现禁用项 " + ", ".join(sorted(set(bad)))); code = 1
    if a.limit_mb and total_mb > a.limit_mb:
        print(f"失败：{total_mb:.0f} MB 超过上限 {a.limit_mb:.0f} MB"); code = 1
    return code


if __name__ == "__main__":
    sys.exit(main())
