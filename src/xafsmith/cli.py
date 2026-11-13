"""xafsmith —— XAFS 处理与拟合命令行（任何 AI / 人都按这个用；文档：xafsmith docs）。

项目（一个含 xafsmith.json 的文件夹）：
  xafsmith new <目录>                    新建标准项目
  xafsmith init                          扫描 data/raw → data/meta.csv、xafsmith.json（不覆盖已有修改）
  xafsmith validate                      按数据标准检查项目
  xafsmith paths                         显示项目各目录
  xafsmith formats                       列出支持的数据格式与项目里保存的列映射模板
  xafsmith inspect <文件> [--format 名 --mode trans|fluo]   显示识别出的格式、列映射、元素与吸收边（哪些是猜的）

数据处理：
  xafsmith list                          样品汇总
  xafsmith qc [--edge Ta_L3]             质量检查 → output/qc/
  xafsmith calib                         按参比校准 → output/calib/calib.json
  xafsmith process [--edge Ta_L3]        校准→归一化→合并→χ(k)→FT → output/processed/、output/figs/
  xafsmith kcheck --edge Ta_L3           干扰吸收边与可用 k 上限

结构与拟合：
  xafsmith structures [--export]         列出 structures/ 中的结构（--export 导出内置结构为 CIF）
  xafsmith feff --structure Ta2O5.cif --absorber Ta --edge L3     （或 --builtin KTaO3；--code feff8 用自洽势）→ output/feff/
  xafsmith fit <模型名或路径>             EXAFS 拟合（models/ 中查找）→ output/fits/、output/figs/
  xafsmith ftest <小模型> <大模型>        嵌套模型 F 检验
  xafsmith lcf --sample S --standards A B [--emin -20 --emax 30 --space norm]
  xafsmith plan --formula IrO2 --element Ir --edge L3              样品设计
  xafsmith robust <模型名>                稳健性检查（改变 k/R 范围与 k 权重重复拟合）→ output/fits/
  xafsmith xanes --samples A B [--valence 标样=价态 ...]          边位置/白线/价态估算 → output/xanes/
  xafsmith export-prj --samples A B [--out 文件.prj]               导出 Athena 工程 → output/gui/athena/
  xafsmith methods [--samples A B]       自动生成“方法”段落草稿 → output/reports/方法段落.md
  xafsmith diagnose <模型名>              拟合诊断：残差/噪声、毛刺定位、分段失配与建议

导出：
  xafsmith figure --kind chir --samples A B [--size double --kweight 2]   期刊图（xanes/deriv/chik/chir/fit）→ output/figs/journal/
  xafsmith summary                       一键汇总报告（Excel + HTML）→ output/reports/
  xafsmith si [--fits "样品|模型" ...] [--lang en]   SI 用拟合方法文本 + 参数表 → output/reports/

AI 助手：
  xafsmith agent [--write]               显示接入信息；--write 写入 AGENTS.md、CLAUDE.md（含本机命令路径）
  xafsmith update [--check]              检查 / 安装 GitHub 上的新版本

  xafsmith gui                           图形界面（独立桌面窗口）
  xafsmith docs                          文档位置
  xafsmith cite                          引用方式与免责声明（论文中使用请引用本仓库）

所有命令都可加 --project <目录>；不加时从当前目录向上查找 xafsmith.json。原始数据只读。
"""
from xafsmith import logs
import argparse
import json
import os
import shutil
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
    copies = {"xafsmith.json": paths.CONFIG, "project.md": paths.PROJECT_MD,
              "meta.csv": paths.META, "structures_README.md": paths.STRUCT / "README.md",
              "model_example.json": paths.MODELS / "_模板.json"}
    made = []
    for src, dst in copies.items():
        if not dst.exists():
            shutil.copy(TEMPLATES / src, dst)
            made.append(dst)
    from . import agent
    made += agent.write(paths.ROOT)          # AGENTS.md / CLAUDE.md（含本机 xafsmith 命令路径）
    return made


def cmd_init(a):
    from . import paths, pipeline as pl
    paths.ensure()
    meta, n = pl.scan_raw()
    cfg = pl.init_config(meta)
    print(f"meta.csv：新增 {n} 行，共 {len(meta)} 行 → {paths.rel(paths.META)}")
    print(f"{paths.MARKER}：吸收边 {list(cfg['edges'])}")
    for f_, why in getattr(pl.scan_raw, "skipped", []):
        print(f"未登记 {f_}：{why}")
    print("请检查 meta.csv 的 sample / role / use / ref_file 列，以及 elements_in_sample；然后 xafsmith validate")


def cmd_formats(a):
    from . import io as xio, paths
    print("支持的数据格式（meta.csv 的 format 列；留空 = 自动识别）：")
    for n, zh, en in xio.list_formats():
        print(f"  {n:11s} {zh}  /  {en}")
    try:
        from . import pipeline as pl
        tpl = (pl.load_config().get("formats") or {}) if paths.CONFIG.exists() else {}
    except Exception:                      # noqa: BLE001
        logs.log.debug("cli.cmd_formats 出错（已忽略或已提示）", exc_info=True)
        tpl = {}
    if tpl:
        print(f"{paths.MARKER} 中保存的列映射模板：")
        for k, v in tpl.items():
            print(f"  {k}: {v}")


def cmd_inspect(a):
    from . import io as xio, paths
    tpl = {}
    if paths.CONFIG.exists():                 # 项目里保存的列映射模板也能用作 --format
        try:
            from . import pipeline as pl
            tpl = pl.load_config().get("formats") or {}
        except Exception:                      # noqa: BLE001
            logs.log.warning("cli.cmd_inspect 读取 formats 模板失败", exc_info=True)
    for f in a.files:
        try:
            fmt, score = xio.detect_format(f)
            if a.format is None:
                print(f"{f}")
                print(f"  识别格式：{fmt}（置信度 {score}）")
            else:
                print(f"{f}")
                print(f"  指定格式：{a.format}")
            gs = xio.read_file(f, fmt=a.format, mode=a.mode, templates=tpl)
        except xio.ReadError as ex:
            print(f"  读入失败：{ex}")
            continue
        for g in gs:
            print(f"  [{getattr(g, 'group_name', g.label)}] 元素/边：{g.element} {g.edge}  模式：{g.mode}  μ 来源：{g.mu_from}"
                  f"  点数：{len(g.energy)}  能量：{g.energy[0]:.1f}–{g.energy[-1]:.1f} eV")
            print(f"    列映射：{g.columns}")
            if g.meta_guessed:
                print(f"    猜测的字段（请核对）：{', '.join(g.meta_guessed)}")
            for w in g.read_warnings:
                print(f"    警告：{w}")


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
        sfx = "_feff8" if a.code == "feff8" else ""
        out = paths.FEFF / f"{name}_{a.absorber}{a.edge}{sfx}" / f"site{idx}"
        df = feff_wrap.build(s, a.absorber, a.edge, out, site_index=idx, rmax=a.rmax, title=name,
                             code=a.code, scf=a.scf, exchange=a.exchange)
        print(f"\n== {paths.rel(out)}  (多重度 {mult})")
        print(df[["name", "label", "reff", "degen", "nleg", "amp_ratio"]].to_string(index=False))


def _load_model(name):
    from . import paths
    f = paths.model_file(name)
    model = json.loads(f.read_text(encoding="utf-8-sig"))
    model.setdefault("name", f.stem)
    return model


def _run_model(name):
    """旧格式：(model, Group, res, dset, summ)；多数据集：(model, {id: Group}, res, [dset…], summ)。"""
    from . import pipeline as pl, fit_exafs as fx
    model = _load_model(name)
    if fx.is_multi(model):
        groups = pl.build_model_groups(model)
        res, dsets, summ = fx.fit_multi(groups, model)
        return model, groups, res, dsets, summ
    g, _ = pl.build_sample(model["sample"])
    res, dset, summ = fx.run_fit(g, model)
    return model, g, res, dset, summ


def _last_kw(kw):
    return kw[-1] if isinstance(kw, list) else kw


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
    if summ.get("multi"):
        figs = []
        for d, ds in zip(fx.normalize_model(model)["datasets"], dset):
            f = paths.FIGS / f"{base}_{pl.safe(d['id'])}_fit.png"
            xrep.plot_fit(fx.model_curves(ds), fx.dataset_view(summ, d["id"]), kweight=_last_kw(d["kweight"]), out=f)
            figs.append(paths.rel(f))
        fig_txt = ", ".join(str(f) for f in figs)
    else:
        xrep.plot_fit(fx.model_curves(dset), summ, kweight=_last_kw(model["kweight"]),
                      out=paths.FIGS / f"{base}_fit.png")
        fig_txt = f"{paths.rel(paths.FIGS)}/{base}_fit.png"
    write_params(paths.FITS / f"{base}.params.json", model, "xafsmith fit")
    print(f"\n摘要: R={summ['rfactor']:.4f}  χ²_ν={summ['chi2_reduced']:.2f}  "
          f"N_idp={summ['n_idp']:.1f}  nvarys={summ['nvarys']}")
    if summ.get("multi"):
        print(f"联合拟合 {summ['n_datasets']} 个数据集（上一行为合计值）：")
        for d in summ["datasets"]:
            print(f"  {d['id']}: 样品 {d['sample']}  N_idp={d['n_idp']:.1f}  R={d['rfactor']:.4f}  "
                  f"χ² 占比={d['chi2_share']:.2f}")
    print(f"→ {paths.rel(paths.FITS)}/{base}.fit_report.txt, {paths.rel(paths.FITS_CSV)}, {fig_txt}")


def _fit_ranges(model):
    from . import fit_exafs as fx
    return [tuple(str(d[k]) for k in ("sample", "kmin", "kmax", "rmin", "rmax", "kweight", "fitspace"))
            for d in fx.normalize_model(model)["datasets"]]


def cmd_ftest(a):
    from . import fit_exafs as fx
    if _fit_ranges(_load_model(a.small)) != _fit_ranges(_load_model(a.large)):
        print("两个模型的数据或拟合范围不同，F 检验不适用 / the two models use different data or fit ranges: "
              "the F-test does not apply")
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
    from .common import append_csv
    append_csv(pd.DataFrame([lc.result_row(r, a.note)]), paths.LCF_CSV)
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


def cmd_robust(a):
    from . import paths, fit_exafs as fx
    if fx.is_multi(_load_model(a.model)):
        sys.exit("多数据集模型暂不支持稳健性检查（计划在 B2 之后） / "
                 "robustness checks are not yet supported for multi-dataset models (planned after B2)")
    model, g, res, dset, summ = _run_model(a.model)
    tab, ver = fx.robustness(g, model, progress=lambda f, n: print(f"  {n}"))
    base = summ["model"].replace("/", "_")
    tab.to_csv(paths.FITS / f"{base}_robustness.csv", index=False, encoding="utf-8-sig")
    ver.to_csv(paths.FITS / f"{base}_robustness_summary.csv", index=False, encoding="utf-8-sig")
    print(ver.to_string(index=False))
    print(f"→ output/fits/{base}_robustness*.csv")


def cmd_xanes(a):
    from . import paths, pipeline as pl, xanes as xx
    gs = [pl.build_sample(s)[0] for s in a.samples]
    tab = xx.features_table(gs, a.wl_window)
    paths.XANES.mkdir(parents=True, exist_ok=True)
    tab.to_csv(paths.XANES_CSV, index=False, encoding="utf-8-sig")
    print(tab.round(4).to_string(index=False))
    if a.valence:
        std = dict(x.split("=", 1) for x in a.valence)
        t = tab.set_index("sample")
        cal = xx.valence_calibration([t.loc[s, a.position] for s in std], [float(v) for v in std.values()])
        print(f"\n{a.position} = {cal['a']:.3f}·价态 + {cal['b']:.2f}  (R²={cal['r2']:.4f}, n={cal['n']})")
        for s in t.index:
            if s not in std:
                v, err = xx.predict_valence(cal, float(t.loc[s, a.position]))
                print(f"  {s}: 价态 {v:.2f} ± {err:.2f}")
    print(f"→ {paths.rel(paths.XANES_CSV)}")


def cmd_export_prj(a):
    from . import paths, pipeline as pl, io as xio
    gs = [pl.build_sample(s)[0] for s in a.samples]
    out = Path(a.out) if a.out else paths.GUI / "athena" / f"{paths.ROOT.name}_xafsmith.prj"
    xio.write_prj(gs, out)
    print(f"→ {out}（{len(gs)} 条谱）")


def cmd_methods(a):
    from . import methods_text as mt
    p, r = mt.save(a.samples or None)
    print(r["zh"], "\n\n", r["en"], f"\n\n→ {p}")


def cmd_update(a):
    from . import update as xup
    u = xup.check()
    if u["latest"] is None:
        print("无法连接 GitHub")
        return
    print(f"当前 {u['current']}，GitHub 上 {u['latest']}" + ("（有新版本）" if u["newer"] else "（已是最新）"))
    if u["newer"] and not a.check:
        ok, log = xup.upgrade()
        print(log[-1500:])
        print("更新完成" if ok else "更新失败")


def cmd_diagnose(a):
    from . import fit_exafs as fx
    model, g, res, dset, summ = _run_model(a.model)
    print(f"R 因子 {summ['rfactor']:.4f}  χ²_ν {summ['chi2_reduced']:.2f}  变量 {summ['nvarys']} / N_idp {summ['n_idp']:.1f}")
    if summ.get("multi"):
        for d, ds in zip(fx.normalize_model(model)["datasets"], dset):
            print(f"\n===== 数据集 {d['id']}（样品 {d['sample']}） =====")
            _print_diag(fx.diagnose(fx.model_curves(ds), d, e0=getattr(g[d["id"]], "e0", None),
                                    kweight=_last_kw(d["kweight"])))
        return
    _print_diag(fx.diagnose(fx.model_curves(dset), model, e0=getattr(g, "e0", None),
                            kweight=_last_kw(model["kweight"])))


def _print_diag(dg):
    print(f"窗口内残差 RMS {dg['resid_R']:.4f}   白噪声估计 {dg['noise_R']:.4f}   残差/噪声 {dg['ratio']:.1f}")
    print("\nk 分段残差：\n" + dg["k_segments"].round(3).to_string(index=False))
    print("\nR 分段局部失配：\n" + dg["r_segments"].round(3).to_string(index=False))
    print("\n建议：")
    for h in dg["hints"]:
        print(" -", h)


def cmd_summary(a):
    from . import paths, summary
    out = summary.build(title=a.title)
    print(f"→ {paths.rel(out)}（汇总.xlsx、汇总报告.html）")


SIZE_ALIAS = {"single": "单栏 85 mm", "1.5": "1.5 栏 120 mm", "double": "双栏 178 mm", "slide": "汇报 16:9"}


def cmd_figure(a):
    import datetime
    import re as _re
    from . import paths, pipeline as pl, pubfig as pf, fit_exafs as fx
    size = SIZE_ALIAS.get(a.size, a.size)
    if a.kind == "fit":
        if not a.model:
            sys.exit("--kind fit 需要 --model <模型名>")
        m0 = _load_model(a.model)
        if fx.is_multi(m0):
            dl = fx.normalize_model(m0)["datasets"]
            ids = [d["id"] for d in dl]
            if a.dataset not in ids:
                sys.exit(f"多数据集模型需要 --dataset ID，可选：{', '.join(ids)} / "
                         f"a multi-dataset model needs --dataset ID, one of: {', '.join(ids)}")
            model, g, res, dset, summ = _run_model(a.model)
            i = ids.index(a.dataset)
            fig, cap = pf.fit(fx.model_curves(dset[i]), fx.dataset_view(summ, a.dataset), size,
                              kweight=a.kweight, rmax=a.rmax, model=dl[i])
        else:
            model, g, res, dset, summ = _run_model(a.model)
            fig, cap = pf.fit(fx.model_curves(dset), summ, size, kweight=a.kweight, rmax=a.rmax, model=model)
    else:
        if not a.samples:
            sys.exit("需要 --samples 样品1 样品2 …")
        gs = [pl.build_sample(s)[0] for s in a.samples]
        if a.kind in ("xanes", "deriv"):
            fig, cap = pf.xanes(gs, size, (a.emin, a.emax), a.offset, deriv=a.kind == "deriv")
        elif a.kind == "chik":
            fig, cap = pf.chik(gs, size, a.kweight, a.offset)
        else:
            fig, cap = pf.chir(gs, size, a.kweight, a.rmax, a.offset, a.re)
    name = a.name or f"{a.kind}_{datetime.datetime.now():%Y%m%d_%H%M%S}"
    files = pf.save(fig, cap, paths.PUBFIGS / _re.sub(r"[^\w.-]+", "_", name), a.formats)
    print("图注 / caption:", cap)
    for f in files:
        print("→", paths.rel(f))


def cmd_agent(a):
    from . import paths, agent
    if a.write:
        for f in agent.write(paths.ROOT):
            print("写入", paths.rel(f))
    print(agent.main_text(paths.ROOT))
    if not a.write:
        print("\n示例提问 / example prompts:")
        for z, e in zip(agent.EXAMPLES_ZH, agent.EXAMPLES_EN):
            print(" -", z, "\n  ", e)


def cmd_si(a):
    from . import paths, si_text
    keys = a.fits or None
    if a.list:
        for k in si_text.fit_keys():
            print(k)
        return
    p, r = si_text.save(keys)
    print(r["en"] if a.lang == "en" else r["zh"])
    print()
    print(si_text.table_markdown(r["table"]))
    print(f"\n→ {paths.rel(p)}、SI_EXAFS拟合参数表.csv")


def cmd_gui(a):
    from . import paths
    from .qt.app import run                   # PySide6 原生窗口
    sys.exit(run(paths.ROOT if paths.is_project(paths.ROOT) else None))


# ---------------------------------------------------------------- 入口
def build_parser():
    ap = argparse.ArgumentParser(prog="xafsmith", description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--project", help="项目目录（默认：从当前目录向上查找 xafsmith.json）")
    ap.add_argument("--version", action="store_true")
    sp = ap.add_subparsers(dest="cmd")
    # --project 既可写在子命令前（xafsmith --project D gui），也可写在后（xafsmith gui --project D）
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--project", default=argparse.SUPPRESS, help="项目目录")
    _add = sp.add_parser
    sp.add_parser = lambda *a, **k: _add(*a, parents=[common], **k)
    p = sp.add_parser("new", help="新建标准项目"); p.add_argument("dir"); p.set_defaults(f=cmd_new)
    sp.add_parser("init", help="登记 data/raw").set_defaults(f=cmd_init)
    p = sp.add_parser("validate", help="按数据标准检查"); p.add_argument("--quick", action="store_true", help="不读结构文件")
    p.set_defaults(f=cmd_validate)
    sp.add_parser("paths", help="显示项目目录").set_defaults(f=cmd_paths)
    sp.add_parser("formats", help="支持的数据格式").set_defaults(f=cmd_formats)
    p = sp.add_parser("inspect", help="显示文件的识别结果（格式、列映射、元素与吸收边）")
    p.add_argument("files", nargs="+"); p.add_argument("--format"); p.add_argument("--mode", choices=["trans", "fluo"])
    p.set_defaults(f=cmd_inspect)
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
    p.add_argument("--code", choices=["feff6", "feff8"], default="feff6",
                   help="feff6 = FEFF6L（快）；feff8 = FEFF8L 自洽势（输出目录加 _feff8）")
    p.add_argument("--scf", type=float, default=4.5, help="FEFF8 自洽团簇半径 (Å)")
    p.add_argument("--exchange", type=int, default=0, help="FEFF8 交换势：0 Hedin-Lundqvist，2 Dirac-Hara，5 部分非局域")
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
    p = sp.add_parser("robust", help="拟合稳健性检查"); p.add_argument("model"); p.set_defaults(f=cmd_robust)
    p = sp.add_parser("diagnose", help="拟合诊断：残差、噪声、毛刺、建议"); p.add_argument("model")
    p.set_defaults(f=cmd_diagnose)
    p = sp.add_parser("summary", help="一键汇总报告（Excel + HTML）"); p.add_argument("--title")
    p.set_defaults(f=cmd_summary)
    p = sp.add_parser("figure", help="期刊出图 → output/figs/journal/")
    p.add_argument("--kind", required=True, choices=["xanes", "deriv", "chik", "chir", "fit"])
    p.add_argument("--samples", nargs="+"); p.add_argument("--model", help="--kind fit 时的模型名")
    p.add_argument("--dataset", help="--kind fit 且为多数据集模型时：数据集 id")
    p.add_argument("--size", default="single", help="single / 1.5 / double / slide")
    p.add_argument("--kweight", type=int, default=2); p.add_argument("--rmax", type=float, default=6.0)
    p.add_argument("--emin", type=float, default=-20); p.add_argument("--emax", type=float, default=60)
    p.add_argument("--offset", type=float, default=0.0); p.add_argument("--re", action="store_true", help="chir 同时画 Re")
    p.add_argument("--formats", nargs="+", default=["tiff", "png", "svg"]); p.add_argument("--name")
    p.set_defaults(f=cmd_figure)
    p = sp.add_parser("si", help="SI 用 EXAFS 拟合方法文本 + 参数表（来自已保存的拟合）")
    p.add_argument("--fits", nargs="+", help="“样品|模型”，默认全部；--list 列出可选项")
    p.add_argument("--list", action="store_true"); p.add_argument("--lang", choices=["zh", "en"], default="en")
    p.set_defaults(f=cmd_si)
    p = sp.add_parser("agent", help="接入 AI 助手：显示信息 / --write 写入 AGENTS.md 与 CLAUDE.md")
    p.add_argument("--write", action="store_true"); p.set_defaults(f=cmd_agent)
    p = sp.add_parser("xanes", help="XANES 边位置/白线/价态")
    p.add_argument("--samples", nargs="+", required=True)
    p.add_argument("--valence", nargs="*", help="标样=价态，如 CoO=2 Co3O4=2.667")
    p.add_argument("--position", default="E_half", choices=["E_half", "E0_deriv", "WL_E"])
    p.add_argument("--wl-window", type=float, default=30.0); p.set_defaults(f=cmd_xanes)
    p = sp.add_parser("export-prj", help="导出 Athena 工程")
    p.add_argument("--samples", nargs="+", required=True); p.add_argument("--out"); p.set_defaults(f=cmd_export_prj)
    p = sp.add_parser("methods", help="生成方法段落"); p.add_argument("--samples", nargs="*")
    p.set_defaults(f=cmd_methods)
    p = sp.add_parser("update", help="检查/安装新版本"); p.add_argument("--check", action="store_true")
    p.set_defaults(f=cmd_update)
    for name in ("gui", "app"):
        sp.add_parser(name, help="图形界面（独立桌面窗口）").set_defaults(f=cmd_gui)
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
