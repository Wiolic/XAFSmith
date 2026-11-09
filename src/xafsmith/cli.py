"""xafsmith —— XAFS 处理与拟合命令行（任何 AI / 人都按这个用；文档：xafsmith docs）。

项目（一个含 xafsmith.json 的文件夹）：
  xafsmith new <目录>                    新建标准项目
  xafsmith init                          扫描 data/raw → data/meta.csv、xafsmith.json（不覆盖已有修改）
  xafsmith validate                      按数据标准检查项目
  xafsmith paths                         显示项目各目录

数据处理：
  xafsmith list                          样品汇总
  xafsmith qc [--edge Ta_L3]             质量检查 → output/qc/
  xafsmith calib                         按参比校准 → output/calib/calib.json
  xafsmith process [--edge Ta_L3]        校准→归一化→合并→χ(k)→FT → output/processed/、output/figs/
  xafsmith kcheck --edge Ta_L3           干扰吸收边与可用 k 上限

结构与拟合：
  xafsmith structures [--export]         列出 structures/ 中的结构（--export 导出内置结构为 CIF）
  xafsmith feff --structure Ta2O5.cif --absorber Ta --edge L3     （或 --builtin KTaO3）→ output/feff/
  xafsmith fit <模型名或路径>             EXAFS 拟合（models/ 中查找）→ output/fits/、output/figs/
  xafsmith ftest <小模型> <大模型>        嵌套模型 F 检验
  xafsmith lcf --sample S --standards A B [--emin -20 --emax 30 --space norm]
  xafsmith plan --formula IrO2 --element Ir --edge L3              样品设计

  xafsmith gui                           图形界面（独立桌面窗口；--browser 改用浏览器）
  xafsmith docs                          文档位置
  xafsmith cite                          引用方式与免责声明（论文中使用请引用本仓库）

所有命令都可加 --project <目录>；不加时从当前目录向上查找 xafsmith.json。原始数据只读。
"""
import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
TEMPLATES = HERE / "templates"
DOCS = HERE / "docs"


def _pd():
    import pandas as pd
    pd.set_option("display.width", 250)
    pd.set_option("display.max_columns", 40)
    pd.set_option("display.max_colwidth", 60)
    return pd


# ---------------------------------------------------------------- 项目
def cmd_new(a):
    from . import paths
    for f in create_project(paths.ROOT):
        print("创建", paths.rel(f))
    print(f"\n项目已就绪：{paths.ROOT}\n"
          "下一步：把原始数据放进 data/raw/<批次>/（每个批次带单质参比），然后 xafsmith init，或用图形界面 xafsmith gui")


def create_project(root):
    """按数据标准新建（或补全）项目；已有文件不覆盖。返回新建的文件列表。"""
    from . import paths
    paths.set_root(root)
    paths.ensure()
    copies = {"xafsmith.json": paths.CONFIG, "project.md": paths.PROJECT_MD, "AGENTS.md": paths.ROOT / "AGENTS.md",
              "meta.csv": paths.META, "structures_README.md": paths.STRUCT / "README.md",
              "model_example.json": paths.MODELS / "_模板.json", "run_gui.bat": paths.ROOT / "打开图形界面.bat"}
    made = []
    for src, dst in copies.items():
        if not dst.exists():
            shutil.copy(TEMPLATES / src, dst)
            made.append(dst)
    return made


def cmd_init(a):
    from . import paths, pipeline as pl
    paths.ensure()
    meta, n = pl.scan_raw()
    cfg = pl.init_config(meta)
    print(f"meta.csv：新增 {n} 行，共 {len(meta)} 行 → {paths.rel(paths.META)}")
    print(f"{paths.MARKER}：吸收边 {list(cfg['edges'])}")
    print("请检查 meta.csv 的 sample / role / use / ref_file 列，以及 elements_in_sample；然后 xafsmith validate")


def cmd_validate(a):
    from . import schema
    rep = schema.validate(structures=not a.quick)
    t = rep.table()
    if len(t):
        print(t.to_string(index=False))
    print(f"\n{rep.n_err} 个错误，{len(t) - rep.n_err} 个警告")
    sys.exit(1 if rep.n_err else 0)


def cmd_paths(a):
    from . import paths
    for k in ("ROOT", "CONFIG", "META", "RAW", "STRUCT", "MODELS", "NOTES", "SCRIPTS", "OUT", "QC", "CALIB",
              "PROC", "FEFF", "FITS", "LCF", "FIGS", "REPORTS", "GUI"):
        p = getattr(paths, k)
        print(f"{k:8s} {'✔' if p.exists() else '·'} {p}")


def cmd_cite(a):
    from . import about
    print(about.text_block())


def cmd_docs(a):
    print(DOCS)
    for f in sorted(DOCS.glob("*.md")):
        print("  ", f.name)


# ---------------------------------------------------------------- 数据处理
def cmd_list(a):
    from . import pipeline as pl
    m = pl.load_meta()
    g = m.groupby("sample", sort=False).agg(edge=("edge_key", "first"), mode=("mode", "first"),
                                            role=("role", "first"), batch=("batch", "first"),
                                            nscans=("file", "size"),
                                            used=("use", lambda s: int((s != "0").sum())))
    _pd()
    print(g.to_string())


def cmd_qc(a):
    from . import paths, pipeline as pl
    _pd()
    df = pl.run_qc(a.edge)
    cols = [c for c in ["label", "mode", "e0", "edge_step_mu", "delta_mut", "delta_mut_from_I1",
                        "self_abs_risk", "n_glitches", "i0_drops", "kmax_data", "k_snr3",
                        "epsilon_k", "error"] if c in df]
    print(df[cols].to_string())
    print(f"→ {paths.rel(paths.QC_CSV)}")


def cmd_calib(a):
    from . import paths, pipeline as pl
    meta = pl.load_meta()
    res = pl.run_calib(pl.load_config(), meta)
    for ref, r in res.items():
        gaps = [v for v in r["time_gap_hours"].values() if v is not None]
        print(f"{r['edge_key']} [{r['batch']}] 参比 {ref}  E0_meas={r['e0_meas']:.2f}  "
              f"E_table={r['e_table']:.2f} ({r['table_source']})  ΔE={r['delta_e']:+.2f} eV  "
              f"{len(r['time_gap_hours'])} 条谱，与参比最大时间差 {max(gaps) if gaps else 'NA'} h")
    miss = meta[meta.ref_file == ""]
    if len(miss):
        print(f"⚠ {len(miss)} 条谱没有参比（不能处理）：", ", ".join(miss.file))
    print(f"→ {paths.rel(paths.CALIB_JSON)}")


def cmd_process(a):
    from . import paths, pipeline as pl
    _pd()
    df, _ = pl.process_all(edge_keys=[a.edge] if a.edge else None, make_figs=not a.nofig)
    print(df.drop(columns=[c for c in ("scans_used",) if c in df]).to_string())
    print(f"→ {paths.rel(paths.PROC)}/（.nor .chik .chir、process_summary.csv）, {paths.rel(paths.FIGS)}/")


def cmd_kcheck(a):
    from . import pipeline as pl, mut_planner as mp
    cfg, meta = pl.load_config(), pl.load_meta()
    c = cfg["edges"][a.edge]
    emax = float(meta[meta.edge_key == a.edge].emax.astype(float).median())
    kl, df = mp.k_limit(c["elements_in_sample"], c["element"], c["edge"], emax)
    print(f"{a.edge}: 元素 {c['elements_in_sample']}，数据末端（中位）{emax:.0f} eV")
    print(df.to_string() if len(df) else "扫描范围内无干扰边")
    print(f"可用 k 上限 ≈ {kl:.2f} Å⁻¹（还需结合 qc 的 k_snr3 决定 kmax）")


# ---------------------------------------------------------------- 结构与拟合
def cmd_structures(a):
    from . import structures as xs, paths
    if a.export:
        for f in xs.export_builtin():
            print("导出", paths.rel(f))
    print(f"{paths.rel(paths.STRUCT)}/ 中的结构文件：")
    for n in xs.list_structures():
        print("  ", n)
    print("内置结构：", ", ".join(xs.BUILTIN_NAMES))


def cmd_feff(a):
    from . import paths, structures, feff_wrap
    src = a.structure or a.cif
    if not (a.builtin or src):
        sys.exit("需要 --structure <structures/ 中的文件或路径> 或 --builtin <名称>")
    s = structures.builtin(a.builtin) if a.builtin else structures.read_structure(src)
    name = a.builtin or Path(src).stem
    sites = feff_wrap.inequivalent_sites(s, a.absorber)
    print("不等价吸收位点 (index, 多重度):", sites)
    todo = sites if a.site is None else [x for x in sites if x[0] == a.site]
    for idx, mult in todo:
        out = paths.FEFF / f"{name}_{a.absorber}{a.edge}" / f"site{idx}"
        df = feff_wrap.build(s, a.absorber, a.edge, out, site_index=idx, rmax=a.rmax, title=name)
        print(f"\n== {paths.rel(out)}  (多重度 {mult})")
        print(df[["name", "label", "reff", "degen", "nleg", "amp_ratio"]].to_string(index=False))


def _run_model(name):
    from . import paths, pipeline as pl, fit_exafs as fx
    f = paths.model_file(name)
    model = json.loads(f.read_text(encoding="utf-8"))
    model.setdefault("name", f.stem)
    g, _ = pl.build_sample(model["sample"])
    res, dset, summ = fx.run_fit(g, model)
    return model, g, res, dset, summ


def cmd_fit(a):
    from . import paths, pipeline as pl, fit_exafs as fx, report as xrep
    from .common import write_params
    model, g, res, dset, summ = _run_model(a.model)
    rep = fx.report_text(res)
    print(rep)
    for w in summ["warnings"]:
        print("警告:", w)
    base = pl.safe(model["name"])
    for d in (paths.FITS, paths.FIGS):
        d.mkdir(parents=True, exist_ok=True)
    (paths.FITS / f"{base}.fit_report.txt").write_text(rep, encoding="utf-8")
    if not a.nosave:
        fx.write_result_row(summ, paths.FITS_CSV)
    kw = model["kweight"][-1] if isinstance(model["kweight"], list) else model["kweight"]
    xrep.plot_fit(fx.model_curves(dset), summ, kweight=kw, out=paths.FIGS / f"{base}_fit.png")
    write_params(paths.FITS / f"{base}.params.json", model, "xafsmith fit")
    print(f"\n摘要: R={summ['rfactor']:.4f}  χ²_ν={summ['chi2_reduced']:.2f}  "
          f"N_idp={summ['n_idp']:.1f}  nvarys={summ['nvarys']}")
    print(f"→ {paths.rel(paths.FITS)}/{base}.fit_report.txt, {paths.rel(paths.FITS_CSV)}, "
          f"{paths.rel(paths.FIGS)}/{base}_fit.png")


def cmd_ftest(a):
    from . import fit_exafs as fx
    r1 = _run_model(a.small)[2]
    r2 = _run_model(a.large)[2]
    print(json.dumps(fx.hamilton_test(r1, r2), ensure_ascii=False, indent=2))


def cmd_lcf(a):
    from . import paths, pipeline as pl, fit_lcf as lc, report as xrep
    pd = _pd()
    smp, _ = pl.build_sample(a.sample, do_chi=a.space == "chik")
    stds = [pl.build_sample(s, do_chi=a.space == "chik")[0] for s in a.standards]
    kws = dict(xmin=a.emin, xmax=a.emax, space=a.space)
    r = lc.lcf(smp, stds, sum_to_one=not a.free, **kws)
    print(f"LCF {a.sample}  {a.space} [{a.emin}, {a.emax}]  R因子={r['rfactor']:.5f}  Σw={r['sum_weights']:.3f}")
    for k in r["weights"]:
        print(f"  {k:30s} {r['weights'][k]:.3f} ± {r['weights_err'][k]:.3f}")
    print("\n单一标样比较：")
    print(lc.single_standard_compare(smp, stds, **kws).to_string(index=False))
    if len(stds) > 2:
        print("\n全部组合（前 10）：")
        print(lc.fit_all_combinations(smp, stds, **kws).head(10).to_string())
    for d in (paths.LCF, paths.FIGS):
        d.mkdir(parents=True, exist_ok=True)
    pd.DataFrame([lc.result_row(r, a.note)]).to_csv(paths.LCF_CSV, mode="a", header=not paths.LCF_CSV.exists(),
                                                    index=False, encoding="utf-8-sig")
    fig = paths.FIGS / f"lcf_{pl.safe(a.sample)}.png"
    xrep.plot_lcf(r, out=fig)
    print(f"→ {paths.rel(paths.LCF_CSV)}, {paths.rel(fig)}")


def cmd_plan(a):
    from . import mut_planner as mp
    r = mp.recommend_mass(a.formula, a.area, a.element, a.edge, a.target, a.diluent, a.mass_diluent)
    print(json.dumps(r, ensure_ascii=False, indent=2, default=float))
    if a.mass:
        print(json.dumps(mp.mut_for_mass(a.formula, a.mass, a.area, a.element, a.edge, a.diluent,
                                         a.mass_diluent), ensure_ascii=False, indent=2, default=float))


def cmd_gui(a):
    from . import paths
    if not a.browser:                         # 默认：独立桌面窗口（不打开浏览器）
        from . import desktop
        desktop.run(paths.ROOT if paths.is_project(paths.ROOT) else None)
        return
    env = dict(os.environ, XAFSMITH_PROJECT=str(paths.ROOT))
    args = [sys.executable, "-m", "streamlit", "run", str(HERE / "gui.py")]
    if a.port:
        args += ["--server.port", str(a.port)]
    sys.exit(subprocess.call(args, env=env))


# ---------------------------------------------------------------- 入口
def build_parser():
    ap = argparse.ArgumentParser(prog="xafsmith", description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--project", help="项目目录（默认：从当前目录向上查找 xafsmith.json）")
    ap.add_argument("--version", action="store_true")
    sp = ap.add_subparsers(dest="cmd")
    p = sp.add_parser("new", help="新建标准项目"); p.add_argument("dir"); p.set_defaults(f=cmd_new)
    sp.add_parser("init", help="登记 data/raw").set_defaults(f=cmd_init)
    p = sp.add_parser("validate", help="按数据标准检查"); p.add_argument("--quick", action="store_true", help="不读结构文件")
    p.set_defaults(f=cmd_validate)
    sp.add_parser("paths", help="显示项目目录").set_defaults(f=cmd_paths)
    sp.add_parser("docs", help="文档位置").set_defaults(f=cmd_docs)
    sp.add_parser("cite", help="引用方式与免责声明").set_defaults(f=cmd_cite)
    sp.add_parser("list", help="样品汇总").set_defaults(f=cmd_list)
    p = sp.add_parser("qc", help="质量检查"); p.add_argument("--edge"); p.set_defaults(f=cmd_qc)
    sp.add_parser("calib", help="按参比校准").set_defaults(f=cmd_calib)
    p = sp.add_parser("process", help="处理"); p.add_argument("--edge"); p.add_argument("--nofig", action="store_true")
    p.set_defaults(f=cmd_process)
    p = sp.add_parser("kcheck", help="干扰边与 k 上限"); p.add_argument("--edge", required=True)
    p.set_defaults(f=cmd_kcheck)
    p = sp.add_parser("structures", help="结构文件"); p.add_argument("--export", action="store_true")
    p.set_defaults(f=cmd_structures)
    p = sp.add_parser("feff", help="FEFF 路径")
    p.add_argument("--structure", help="structures/ 中的文件名或任意路径（CIF/POSCAR/…）")
    p.add_argument("--cif", help="同 --structure（兼容）"); p.add_argument("--builtin")
    p.add_argument("--absorber", required=True); p.add_argument("--edge", default="K")
    p.add_argument("--rmax", type=float, default=6.0); p.add_argument("--site", type=int)
    p.set_defaults(f=cmd_feff)
    p = sp.add_parser("fit", help="EXAFS 拟合"); p.add_argument("model"); p.add_argument("--nosave", action="store_true")
    p.set_defaults(f=cmd_fit)
    p = sp.add_parser("ftest", help="F 检验"); p.add_argument("small"); p.add_argument("large")
    p.set_defaults(f=cmd_ftest)
    p = sp.add_parser("lcf", help="线性组合拟合")
    p.add_argument("--sample", required=True); p.add_argument("--standards", nargs="+", required=True)
    p.add_argument("--emin", type=float, default=-20); p.add_argument("--emax", type=float, default=30)
    p.add_argument("--space", default="norm", choices=["norm", "dmude", "chik"])
    p.add_argument("--free", action="store_true", help="不要求权重和为 1")
    p.add_argument("--note", default=""); p.set_defaults(f=cmd_lcf)
    p = sp.add_parser("plan", help="样品设计")
    p.add_argument("--formula", required=True); p.add_argument("--element", required=True)
    p.add_argument("--edge", required=True); p.add_argument("--area", type=float, default=1.327)
    p.add_argument("--target", type=float, default=2.0); p.add_argument("--diluent")
    p.add_argument("--mass-diluent", type=float, default=0.0); p.add_argument("--mass", type=float)
    p.set_defaults(f=cmd_plan)
    for name in ("gui", "app"):
        p = sp.add_parser(name, help="图形界面（桌面窗口；--browser 用浏览器）")
        p.add_argument("--browser", action="store_true", help="在浏览器中打开（http://localhost:8501）")
        p.add_argument("--port", type=int); p.set_defaults(f=cmd_gui)
    return ap


def main(argv=None):
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    ap = build_parser()
    a = ap.parse_args(argv)
    if a.version:
        from . import __version__
        from .about import CREDIT, DISCLAIMER_EN, CITATION_TEXT
        print("xafsmith", __version__, "—", CREDIT)
        print(DISCLAIMER_EN)
        print("Cite:", CITATION_TEXT)
        return
    if a.cmd is None:
        ap.print_help()
        return
    project = a.dir if a.cmd == "new" else a.project
    if project:                              # 必须在导入 paths 之前设置
        Path(project).mkdir(parents=True, exist_ok=True) if a.cmd == "new" else None
        os.environ["XAFSMITH_PROJECT"] = str(Path(project).resolve())
    a.f(a)


if __name__ == "__main__":
    main()
