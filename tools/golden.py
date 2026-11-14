"""golden —— 黄金基线回归：冻结当前数值结果，之后每次重构都与它比对（E1）。

快照 = 演示项目全流程（校准 → 处理全部边）的 .nor/.chik/.chir 全列全点 + process_summary.csv
       + Cu 箔 EXAFS 拟合 + Fe LCF（二元、三元）。写成 JSON（tests/golden/demo.json）。
比较：每列容差 = rtol × max|gold 列|（按列尺度的绝对容差）；标量容差 = rtol × max(|gold|, 1e-300)。

用法（在 XAFSmith 仓库根目录）：
    python tools/golden.py demo --write     重写 tests/golden/demo.json
    python tools/golden.py demo --check     与 demo.json 比较，打印差异，有差异则退出码 1
    python tools/golden.py local --write / --check    本机私有快照（tests/local/golden_local，见该目录）
不写演示项目自己的 output/：全部在临时目录里重跑。
"""
from __future__ import annotations

import argparse
import json
import platform
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
TESTS = ROOT / "tests"
DEMO = TESTS / "data" / "demo_project"
GOLDEN = TESTS / "golden" / "demo.json"
LOCAL_DIR = TESTS / "local" / "golden_local"

# 易变列：绝对路径、日期时间、软件版本。目前 process_summary.csv 里没有，保留机制以便需要时列入 excluded。
VOLATILE_COLUMNS: tuple[str, ...] = ()


# ------------------------------------------------------------------ 读文件
def _num(x):
    return None if x != x else float(x)          # NaN -> None


def read_table(path) -> dict:
    """.nor/.chik/.chir：列名取自文件头（'# a b c'），全列全点。"""
    path = Path(path)
    with path.open(encoding="utf-8") as f:
        head = f.readline().lstrip("#").split()
    arr = np.atleast_2d(np.loadtxt(path, encoding="utf-8"))
    if arr.shape[1] != len(head):
        raise ValueError(f"{path.name}: 文件头 {head} 与数据列数 {arr.shape[1]} 不符")
    return {h: [_num(v) for v in arr[:, i]] for i, h in enumerate(head)}


def read_summary(path) -> tuple[dict, list]:
    import pandas as pd
    df = pd.read_csv(path, encoding="utf-8-sig", keep_default_na=True)
    excluded = [c for c in df.columns if c in VOLATILE_COLUMNS]
    cols = {}
    for c in df.columns:
        if c in excluded:
            continue
        if pd.api.types.is_numeric_dtype(df[c]):
            cols[c] = [_num(v) for v in df[c].astype(float)]
        else:
            cols[c] = [None if v != v else str(v) for v in df[c]]
    return cols, excluded


def processed_snapshot(proc: Path) -> dict:
    out = {}
    for ext in (".nor", ".chik", ".chir"):
        for p in sorted(proc.glob(f"*{ext}"), key=lambda q: q.name):
            out[p.name] = read_table(p)
    summ, excluded = read_summary(proc / "process_summary.csv")
    out["process_summary.csv"] = summ
    return out, excluded


# ------------------------------------------------------------------ 运行
def _git_commit() -> str:
    try:
        return subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True,
                              check=True).stdout.strip()
    except Exception:
        return "unknown"


def _meta() -> dict:
    import larch
    import lmfit
    import scipy
    return dict(git_commit=_git_commit(), python=platform.python_version(), numpy=np.__version__,
                scipy=scipy.__version__, xraylarch=getattr(larch, "__version__", "?"), lmfit=lmfit.__version__,
                platform=platform.platform())


def run_pipeline(workdir: Path, src: Path) -> tuple[dict, list]:
    """把 src 中的 xafsmith.json 与 data/ 复制到 workdir，校准并处理全部边，返回 processed 快照。"""
    from xafsmith import paths, pipeline as pl
    workdir = Path(workdir)
    shutil.copy2(src / "xafsmith.json", workdir / "xafsmith.json")
    shutil.copytree(src / "data", workdir / "data", dirs_exist_ok=True)
    old = paths.ROOT
    paths.set_root(workdir)
    try:
        cfg, meta = pl.load_config(), pl.load_meta()
        pl.run_calib(cfg, meta)
        pl.process_all(cfg, meta, make_figs=False)
        snap, excluded = processed_snapshot(paths.PROC)
    finally:
        paths.set_root(old)
    return snap, excluded


def fit_summary(summ: dict) -> dict:
    """拟合摘要（run_fit 返回的 summary dict）转纯 JSON：保留全部数值与参数，去掉本机相关的文件路径。"""
    return json.loads(json.dumps(summ, default=float, allow_nan=True))


def run_demo(workdir) -> dict:
    """演示项目全流程 + Cu 拟合 + Fe LCF 的快照。workdir 须为空的临时目录。"""
    sys.path.insert(0, str(TESTS / "benchmark"))
    try:
        from _fe_synth import load_standards, mix
        from test_cu_feffit import MODEL
    finally:
        sys.path.pop(0)
    from xafsmith import fit_exafs as fx, paths, pipeline as pl
    from xafsmith.fit_lcf import lcf

    workdir = Path(workdir)
    processed, excluded = run_pipeline(workdir, DEMO)

    # 拟合 1：Cu（对流程产出的 cu_metal_rt χ(k)；与 test_cu_feffit "B. 完整流程" 同写法）
    old = paths.ROOT
    paths.set_root(workdir)
    try:
        g, _ = pl.build_sample("cu_metal_rt", calib={})
        _res, _dset, summ = fx.run_fit(g, MODEL, root=None)
    finally:
        paths.set_root(old)
    cu = fit_summary(summ)

    # 拟合 2：Fe LCF（参数同 test_fe_lcf.RNG）
    std = load_standards()
    rng = dict(xmin=-20, xmax=30, space="norm", sum_to_one=True, bounds=True)
    cases = {
        "binary_FeO0.3_Fe2O30.7": ({"FeO": 0.3, "Fe2O3": 0.7}, ["FeO", "Fe2O3"]),
        "ternary_FeO0.5_Fe2O30.2_Fe3C0.3": ({"FeO": 0.5, "Fe2O3": 0.2, "Fe3C": 0.3}, ["FeO", "Fe2O3", "Fe3C"]),
    }
    lcf_out = {}
    for name, (truth, comps) in cases.items():
        r = lcf(mix(truth, 0.005, seed=0, std=std), [std[c] for c in comps], **rng)
        lcf_out[name] = dict(weights=r["weights"], weights_err=r["weights_err"], sum_weights=r["sum_weights"],
                             rfactor=r["rfactor"], chi2=r["chi2"], chi2_reduced=r["chi2_reduced"],
                             nvarys=r["nvarys"], npts=r["npts"], de=r["de"])
    return dict(meta=_meta(), excluded=excluded, processed=processed, cu_fit=cu, fe_lcf=lcf_out)


def run_demo_tmp() -> dict:
    with tempfile.TemporaryDirectory(prefix="xafsmith_golden_") as d:
        return run_demo(d)


# ------------------------------------------------------------------ 比较
def _walk(new, gold, path, rtol, out, scale=None):
    if isinstance(gold, dict):
        if not isinstance(new, dict):
            out.append(f"{path}: 类型不同（新 {type(new).__name__}，基线 dict）")
            return
        if set(new) != set(gold):
            out.append(f"{path}: 键集合不同；新多 {sorted(set(new) - set(gold))}，新缺 {sorted(set(gold) - set(new))}")
        for k in gold:
            if k in new and not (path == "" and k == "meta"):        # meta 只记录，不比较
                _walk(new[k], gold[k], f"{path}/{k}" if path else k, rtol, out)
        return
    if isinstance(gold, list):
        if not isinstance(new, list):
            out.append(f"{path}: 类型不同（新 {type(new).__name__}，基线 list）")
            return
        if len(new) != len(gold):
            out.append(f"{path}: 长度不同（新 {len(new)}，基线 {len(gold)}）")
            return
        if all(isinstance(v, (int, float)) or v is None for v in gold):
            _array(new, gold, path, rtol, out)
        else:
            for i, (a, b) in enumerate(zip(new, gold)):
                _walk(a, b, f"{path}[{i}]", rtol, out)
        return
    if isinstance(gold, bool) or isinstance(gold, str) or gold is None:
        if new != gold:
            out.append(f"{path}: 新 {new!r} ≠ 基线 {gold!r}")
        return
    if isinstance(gold, (int, float)):
        if not isinstance(new, (int, float)) or isinstance(new, bool):
            out.append(f"{path}: 新 {new!r} 不是数值（基线 {gold!r}）")
            return
        tol = rtol * max(abs(gold), 1e-300)
        if not abs(new - gold) <= tol:
            out.append(f"{path}: 新 {new!r} vs 基线 {gold!r}，差 {abs(new - gold):.3e} > 容差 {tol:.3e}")
        return
    out.append(f"{path}: 无法比较的类型 {type(gold).__name__}")


def _array(new, gold, path, rtol, out):
    nn = [i for i, (a, b) in enumerate(zip(new, gold)) if (a is None) != (b is None)]
    if nn:
        out.append(f"{path}: NaN 位置不同，首个下标 {nn[0]}（共 {len(nn)} 处）")
        return
    idx = [i for i, b in enumerate(gold) if b is not None]
    if not idx:
        return
    g = np.array([gold[i] for i in idx], float)
    n = np.array([new[i] for i in idx], float)
    scale = float(np.max(np.abs(g)))
    tol = rtol * scale
    d = np.abs(n - g)
    bad = np.flatnonzero(~(d <= tol))
    if bad.size:
        j = int(bad[np.argmax(d[bad])])
        out.append(f"{path}: {bad.size}/{len(g)} 点超差；最大差 {d[j]:.3e}（相对列尺度 {d[j] / max(scale, 1e-300):.3e}，"
                   f"容差 {tol:.3e}）位于下标 {idx[j]}：新 {n[j]!r} vs 基线 {g[j]!r}")


def compare(new: dict, gold: dict, rtol: float = 1e-9) -> list[str]:
    """返回全部不一致项（空列表 = 一致）。数组按"列尺度绝对容差" rtol × max|gold 列|。"""
    out: list[str] = []
    _walk(new, gold, "", rtol, out)
    return out


# ------------------------------------------------------------------ 命令行
def _load_json(p: Path) -> dict:
    return json.loads(p.read_text(encoding="utf-8"))


def _dump_json(p: Path, obj) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(obj, ensure_ascii=False, indent=None, separators=(",", ":"), allow_nan=False),
                 encoding="utf-8")


def _local_module():
    sys.path.insert(0, str(LOCAL_DIR))
    try:
        import golden_local
    finally:
        sys.path.pop(0)
    return golden_local


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("what", choices=["demo", "local"])
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--write", action="store_true")
    g.add_argument("--check", action="store_true")
    ap.add_argument("--rtol", type=float, default=1e-9)
    a = ap.parse_args(argv)
    if a.what == "demo":
        path, run, rtol = GOLDEN, run_demo_tmp, a.rtol
    else:
        gl = _local_module()
        path, run, rtol = gl.SNAP, gl.run_local_tmp, 1e-12
    new = run()
    if a.write:
        _dump_json(path, new)
        print(f"已写 {path}（{path.stat().st_size / 1e6:.2f} MB）")
        return 0
    diffs = compare(json.loads(json.dumps(new)), _load_json(path), rtol)
    for d in diffs:
        print(d)
    print("0 差异" if not diffs else f"{len(diffs)} 项差异")
    return 1 if diffs else 0


if __name__ == "__main__":
    sys.exit(main())
