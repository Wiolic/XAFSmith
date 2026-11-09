"""xafs.py —— 统一命令行入口（任何 AI / 人都按这个用；详见 AGENTS.md）。

  python scripts/xafs.py init                 扫描 data/raw → data/meta.csv、config.json（不覆盖已有修改）
  python scripts/xafs.py list                 列出样品（meta.csv 汇总）
  python scripts/xafs.py qc [--edge Ir_L3]    质量检查 → results/qc_report.csv
  python scripts/xafs.py calib                参比箔校准 → results/calib.json
  python scripts/xafs.py process [--edge K]   校准+归一化+合并+χ(k)+FT → results/processed/, figs/
  python scripts/xafs.py kcheck --edge Ir_L3  干扰边与可用 k 上限
  python scripts/xafs.py feff --builtin IrO2 --absorber Ir --edge L3 [--rmax 6]
  python scripts/xafs.py fit <model.json>     EXAFS 拟合（model.json 含 "sample"）→ results/exafs_fits.csv
  python scripts/xafs.py ftest <small.json> <large.json>   嵌套模型 F 检验
  python scripts/xafs.py lcf --sample S --standards A B C [--emin -20 --emax 30 --space norm]
  python scripts/xafs.py plan --formula IrO2 --element Ir --edge L3 [--diluent BN --mass-diluent 100]
  python scripts/xafs.py gui                  启动图形界面

所有命令都从 data/raw 原始数据重新计算；原始文件只读。
"""
import argparse
import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import numpy as np            # noqa: E402
import pandas as pd           # noqa: E402

from xafstool.common import PROJECT_ROOT, write_params   # noqa: E402
from xafstool import pipeline as pl                      # noqa: E402

pd.set_option("display.width", 250)
pd.set_option("display.max_columns", 40)
pd.set_option("display.max_colwidth", 60)


def cmd_init(a):
    meta, n = pl.scan_raw()
    cfg = pl.init_config(meta)
    for d in ("results", "figs", "feff", "notes"):
        (PROJECT_ROOT / d).mkdir(exist_ok=True)
    print(f"meta.csv：新增 {n} 行，共 {len(meta)} 行 → data/meta.csv")
    print(f"config.json：吸收边 {list(cfg['edges'])}")
    print("请检查 meta.csv 的 sample/role/use 列，以及 config.json 的 reference 与 elements_in_sample。")


def cmd_list(a):
    m = pl.load_meta()
    g = m.groupby("sample", sort=False).agg(edge=("edge_key", "first"), mode=("mode", "first"),
                                            role=("role", "first"), nscans=("file", "size"),
                                            used=("use", lambda s: int((s != "0").sum())))
    print(g.to_string())


def cmd_qc(a):
    from xafstool import qc, io as xio
    cfg, meta = pl.load_config(), pl.load_meta()
    calib = pl.load_calib()
    rows = []
    for _, r in meta.iterrows():
        if a.edge and r.edge_key != a.edge:
            continue
        try:
            g = pl.load_scan(r, cfg, calib)
            g.label = r.file
            row = qc.check(g)
        except Exception as ex:
            row = dict(label=r.file, error=str(ex))
        row["sample"] = r["sample"]
        rows.append(row)
    df = pd.DataFrame(rows)
    out = PROJECT_ROOT / "results" / "qc_report.csv"
    df.to_csv(out, index=False, encoding="utf-8-sig")
    cols = [c for c in ["label", "mode", "e0", "edge_step_mu", "delta_mut", "delta_mut_from_I1",
                        "self_abs_risk", "n_glitches", "i0_drops", "kmax_data", "k_snr3",
                        "epsilon_k", "error"] if c in df]
    print(df[cols].to_string())
    print(f"→ {out}")


def cmd_calib(a):
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
    print("→ results/calib.json")


def cmd_process(a):
    df, _ = pl.process_all(edge_keys=[a.edge] if a.edge else None, make_figs=not a.nofig)
    print(df.drop(columns=[c for c in ("scans_used",) if c in df]).to_string())
    print("→ results/processed/（.nor .chik .chir、process_summary.csv）, figs/")


def cmd_kcheck(a):
    from xafstool import mut_planner as mp
    cfg, meta = pl.load_config(), pl.load_meta()
    c = cfg["edges"][a.edge]
    emax = meta[meta.edge_key == a.edge].emax.astype(float)
    emax = float(emax.median())
    kl, df = mp.k_limit(c["elements_in_sample"], c["element"], c["edge"], emax)
    print(f"{a.edge}: 元素 {c['elements_in_sample']}，数据末端（中位）{emax:.0f} eV")
    print(df.to_string() if len(df) else "扫描范围内无干扰边")
    print(f"可用 k 上限 ≈ {kl:.2f} Å⁻¹（还需结合 qc 的 k_snr3 决定 kmax）")


def cmd_feff(a):
    from xafstool import structures, feff_wrap
    s = structures.builtin(a.builtin) if a.builtin else structures.read_cif(a.cif)
    name = a.builtin or Path(a.cif).stem
    sites = feff_wrap.inequivalent_sites(s, a.absorber)
    print("不等价吸收位点 (index, 多重度):", sites)
    todo = sites if a.site is None else [x for x in sites if x[0] == a.site]
    for idx, mult in todo:
        out = PROJECT_ROOT / "feff" / f"{name}_{a.absorber}{a.edge}" / f"site{idx}"
        df = feff_wrap.build(s, a.absorber, a.edge, out, site_index=idx, rmax=a.rmax, title=name)
        print(f"\n== {out.relative_to(PROJECT_ROOT)}  (多重度 {mult})")
        print(df[["name", "label", "reff", "degen", "nleg", "amp_ratio"]].to_string(index=False))


def _run_model(path):
    from xafstool import fit_exafs as fx
    model = json.loads(Path(path).read_text(encoding="utf-8"))
    g, _ = pl.build_sample(model["sample"])
    res, dset, summ = fx.run_fit(g, model, root=PROJECT_ROOT)
    return model, g, res, dset, summ


def cmd_fit(a):
    from xafstool import fit_exafs as fx, report as xrep
    model, g, res, dset, summ = _run_model(a.model)
    rep = fx.report_text(res)
    print(rep)
    for w in summ["warnings"]:
        print("警告:", w)
    base = pl.safe(model.get("name", Path(a.model).stem))
    out = PROJECT_ROOT / "results"
    (out / f"{base}.fit_report.txt").write_text(rep, encoding="utf-8")
    if not a.nosave:
        fx.write_result_row(summ, out / "exafs_fits.csv")
    kw = model["kweight"][-1] if isinstance(model["kweight"], list) else model["kweight"]
    xrep.plot_fit(fx.model_curves(dset), summ, kweight=kw,
                  out=PROJECT_ROOT / "figs" / f"{base}_fit.png")
    write_params(out / f"{base}.params.json", model, "xafs.py fit")
    print(f"\n摘要: R={summ['rfactor']:.4f}  χ²_ν={summ['chi2_reduced']:.2f}  "
          f"N_idp={summ['n_idp']:.1f}  nvarys={summ['nvarys']}")
    print(f"→ results/{base}.fit_report.txt, results/exafs_fits.csv, figs/{base}_fit.png")


def cmd_ftest(a):
    from xafstool import fit_exafs as fx
    r1 = _run_model(a.small)[2]
    r2 = _run_model(a.large)[2]
    print(json.dumps(fx.hamilton_test(r1, r2), ensure_ascii=False, indent=2))


def cmd_lcf(a):
    from xafstool import fit_lcf as lc, report as xrep
    smp, _ = pl.build_sample(a.sample, do_chi=a.space == "chik")
    stds = [pl.build_sample(s, do_chi=a.space == "chik")[0] for s in a.standards]
    kws = dict(xmin=a.emin, xmax=a.emax, space=a.space)
    r = lc.lcf(smp, stds, sum_to_one=not a.free, **kws)
    print(f"LCF {a.sample}  {a.space} [{a.emin}, {a.emax}]  R因子={r['rfactor']:.5f}  "
          f"Σw={r['sum_weights']:.3f}")
    for k in r["weights"]:
        print(f"  {k:30s} {r['weights'][k]:.3f} ± {r['weights_err'][k]:.3f}")
    print("\n单一标样比较：")
    print(lc.single_standard_compare(smp, stds, **kws).to_string(index=False))
    if len(stds) > 2:
        print("\n全部组合（前 10）：")
        print(lc.fit_all_combinations(smp, stds, **kws).head(10).to_string())
    csv = PROJECT_ROOT / "results" / "lcf_results.csv"
    pd.DataFrame([lc.result_row(r, a.note)]).to_csv(csv, mode="a", header=not csv.exists(),
                                                    index=False, encoding="utf-8-sig")
    xrep.plot_lcf(r, out=PROJECT_ROOT / "figs" / f"lcf_{pl.safe(a.sample)}.png")
    print(f"→ {csv.relative_to(PROJECT_ROOT)}, figs/lcf_{pl.safe(a.sample)}.png")


def cmd_plan(a):
    from xafstool import mut_planner as mp
    r = mp.recommend_mass(a.formula, a.area, a.element, a.edge, a.target, a.diluent, a.mass_diluent)
    print(json.dumps(r, ensure_ascii=False, indent=2, default=float))
    if a.mass:
        print(json.dumps(mp.mut_for_mass(a.formula, a.mass, a.area, a.element, a.edge, a.diluent,
                                         a.mass_diluent), ensure_ascii=False, indent=2, default=float))


def cmd_gui(a):
    app = Path(__file__).resolve().parent / "gui_app.py"
    subprocess.call([sys.executable, "-m", "streamlit", "run", str(app)])


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sp = ap.add_subparsers(dest="cmd", required=True)
    sp.add_parser("init").set_defaults(f=cmd_init)
    sp.add_parser("list").set_defaults(f=cmd_list)
    p = sp.add_parser("qc"); p.add_argument("--edge"); p.set_defaults(f=cmd_qc)
    sp.add_parser("calib").set_defaults(f=cmd_calib)
    p = sp.add_parser("process"); p.add_argument("--edge"); p.add_argument("--nofig", action="store_true")
    p.set_defaults(f=cmd_process)
    p = sp.add_parser("kcheck"); p.add_argument("--edge", required=True); p.set_defaults(f=cmd_kcheck)
    p = sp.add_parser("feff")
    p.add_argument("--builtin"); p.add_argument("--cif"); p.add_argument("--absorber", required=True)
    p.add_argument("--edge", default="K"); p.add_argument("--rmax", type=float, default=6.0)
    p.add_argument("--site", type=int); p.set_defaults(f=cmd_feff)
    p = sp.add_parser("fit"); p.add_argument("model"); p.add_argument("--nosave", action="store_true")
    p.set_defaults(f=cmd_fit)
    p = sp.add_parser("ftest"); p.add_argument("small"); p.add_argument("large"); p.set_defaults(f=cmd_ftest)
    p = sp.add_parser("lcf")
    p.add_argument("--sample", required=True); p.add_argument("--standards", nargs="+", required=True)
    p.add_argument("--emin", type=float, default=-20); p.add_argument("--emax", type=float, default=30)
    p.add_argument("--space", default="norm", choices=["norm", "dmude", "chik"])
    p.add_argument("--free", action="store_true", help="不要求权重和为 1")
    p.add_argument("--note", default=""); p.set_defaults(f=cmd_lcf)
    p = sp.add_parser("plan")
    p.add_argument("--formula", required=True); p.add_argument("--element", required=True)
    p.add_argument("--edge", required=True); p.add_argument("--area", type=float, default=1.327)
    p.add_argument("--target", type=float, default=2.0); p.add_argument("--diluent")
    p.add_argument("--mass-diluent", type=float, default=0.0); p.add_argument("--mass", type=float)
    p.set_defaults(f=cmd_plan)
    sp.add_parser("gui").set_defaults(f=cmd_gui)
    a = ap.parse_args()
    a.f(a)


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    main()
