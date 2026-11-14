"""带软约束（restraint）的 feffit 驱动（B3）。

复制自 larch 2026.3.1 `xafs/feffit.py::feffit`（785–934 行），只改标 `# B3` 的地方；
`tests/benchmark/test_restraints.py::test_restrained_empty_bitwise` 保证 restraints=[] 时与 larch 逐位相同，
larch 升级若改了 feffit 该测试会失败。

来源与许可：本文件改编自 xraylarch（Larch）的 feffit 代码，Larch 以 MIT 许可发布，版权声明（取自 xraylarch 2026.3.1 的 LICENSE）：
Copyright (c) 2010-2025 Matthew Newville, The University of Chicago; Mauro Rovezzi, University Grenoble Alpes, CNRS;
Bruce Ravel, National Institute of Science and Technology; Margaret Koker, Lawrence University;
Ryuichi Shimogawa, Stony Brook University. MIT 许可全文见 xraylarch 发行包；larch 部分按 MIT 许可（声明见上），XAFSmith 整体按 GPL-3.0-only。

约束项：c0·((expr − value)/sigma)²，c0 = 同一模型无约束拟合的 χ²_ν（由调用方给出）。
larch 内部名从 sys.modules["larch.xafs.feffit"] 取（`larch.xafs.feffit` 被同名函数遮住）。
"""
import ast
import sys

import numpy as np


def _larch_feffit_module():
    import larch.xafs  # noqa: F401  确保 larch.xafs.feffit 已导入
    return sys.modules["larch.xafs.feffit"]


def _eval_terms(prm, restraints):
    """每项软约束的 pull t = (expr − value)/sigma；求值出错或非有限 → ValueError（双语，指名该项）。"""
    out = []
    for r in restraints:
        ev = prm._asteval
        ev.error = []
        try:
            val = ev.eval(r["expr"])
        finally:
            err = list(getattr(ev, "error", []) or [])
            ev.error = []
        if err or val is None:
            raise ValueError(f"软约束 {r['name']} 的表达式 “{r['expr']}” 求值出错 / "
                             f"restraint {r['name']}: cannot evaluate “{r['expr']}”")
        try:
            val = float(val)
        except (TypeError, ValueError):
            val = float("nan")
        if not np.isfinite(val):
            raise ValueError(f"软约束 {r['name']} 的表达式 “{r['expr']}” 结果不是有限数 / "
                             f"restraint {r['name']}: “{r['expr']}” is not a finite number")
        out.append((val - r["value"]) / r["sigma"])
    return np.array(out, dtype=float)


def feffit_restrained(paramgroup, datasets, restraints, c0, rmax_out=10, path_outputs=True,
                      fix_unused_variables=True, **kws):
    from lmfit import Minimizer, Parameter, Parameters
    from larch import Group
    from larch.fitting import ParameterGroup, params2group
    LF = _larch_feffit_module()
    add_sigma2funcs, FEFFDAT_VALUES = LF.add_sigma2funcs, LF.FEFFDAT_VALUES
    propagate_uncertainties, isNamedClass = LF.propagate_uncertainties, LF.isNamedClass
    FeffitDataSet = LF.FeffitDataSet

    fit_kws = dict(gtol=1.e-6, ftol=1.e-6, xtol=1.e-6, epsfcn=1.e-10)
    if 'tol' in kws:
        tol = kws.pop('tol')
        fit_kws['gtol'] = fit_kws['ftol'] = fit_kws['xtol'] = tol
    fit_kws.update(kws)

    work_paramgroup = ParameterGroup()
    if isinstance(paramgroup, ParameterGroup):
        __params = paramgroup._params
        for pname in paramgroup:
            if pname == '_params':
                continue
            if pname in __params:
                par = __params[pname]
                par._delay_asteval = True
                setattr(work_paramgroup, pname, par)
    elif isinstance(paramgroup, Group):
        for pname, par in paramgroup.items():
            par._delay_asteval = True
            setattr(work_paramgroup, pname, par)

    params = Parameters()
    add_sigma2funcs(params)
    for attr in FEFFDAT_VALUES:
        params._asteval.symtable[attr] = 1.0
    for pname, par in work_paramgroup._params.items():
        par._delay_asteval = True
        params.add(par)
    for pname, parval in paramgroup.items():  # explicitly copy 'skip'!
        if pname == '_params':
            continue
        if pname in params and isinstance(params[pname], Parameter):
            params[pname].skip = getattr(parval, 'skip', False)

    if isNamedClass(datasets, FeffitDataSet):
        datasets = [datasets]

    dset_hashkeys = []
    for ds in datasets:
        if not isNamedClass(ds, FeffitDataSet):
            raise ValueError("feffit needs a list of FeffitDataSets")
        ds.prepare_fit(params=params, other_hashkeys=dset_hashkeys)
        dset_hashkeys.append(ds.hashkey)
    vars, exprs = [], []
    for p in params.values():
        if p.vary:
            nam = p.name
            if not any([nam.startswith('bkg') and nam.endswith(ds.hashkey) for ds in datasets]):
                vars.append(nam)
        elif p.expr is not None:
            exprs.append(p.expr)
    for expr in exprs:
        for node in ast.walk(ast.parse(expr)):
            if isinstance(node, ast.Name):
                if node.id in vars:
                    vars.remove(node.id)
    if len(vars) > 0:
        if fix_unused_variables:
            for v in vars:
                params[v].vary = False

    # B3: 总 N_idp 在 prepare_fit 之后算；残差 = 数据残差 + 软约束项
    nidp = sum(ds.n_idp for ds in datasets)
    restraints = list(restraints or [])
    if restraints:
        _eval_terms(params, restraints)       # 拟合前用初值先求一次，出错在 leastsq 之前报
    c0 = float(c0)

    def _resid(prm, datasets=None, **kwargs):
        d = np.concatenate([x._residual(prm) for x in datasets])
        if not restraints:
            return d
        return np.concatenate((d, _eval_terms(prm, restraints) * np.sqrt(c0 * len(d) / nidp)))

    fit = Minimizer(_resid, params, fcn_kws=dict(datasets=datasets), scale_covar=False, **fit_kws)
    result = fit.leastsq()
    dat = np.concatenate([d._residual(result.params, data_only=True) for d in datasets])

    n_idp = 0
    for ds in datasets:
        n_idp += ds.n_idp

    # B3: 统计只用数据部分；约束项单独计
    npts_data = len(dat)
    rdat = np.asarray(result.residual)[:npts_data]
    t = _eval_terms(result.params, restraints) if restraints else np.zeros(0)
    if restraints:
        chi2_data = float((rdat ** 2).sum()) * n_idp * 1.0 / npts_data
        restraint_chi2 = float(c0 * (t ** 2).sum())
        chi_square = chi2_data + restraint_chi2
    else:
        chi_square = result.chisqr * n_idp * 1.0 / npts_data
        chi2_data, restraint_chi2 = chi_square, 0.0
    chi2_reduced = chi_square / (n_idp * 1.0 - result.nvarys)
    rfactor = (rdat ** 2).sum() / (dat ** 2).sum()
    neg2_loglikel = n_idp * np.log(chi_square / n_idp)
    aic = neg2_loglikel + 2 * result.nvarys
    bic = neg2_loglikel + np.log(n_idp) * result.nvarys

    propagate_uncertainties(result, datasets)
    params2group(result.params, work_paramgroup)
    for ds in datasets:
        ds.save_outputs(rmax_out=rmax_out, path_outputs=path_outputs)

    out = Group(name='feffit results', params=result.params,
                paramgroup=work_paramgroup, fit_kws=fit_kws,
                datasets=datasets, fit_details=result,
                chi_square=chi_square, n_independent=n_idp,
                chi2_reduced=chi2_reduced, redchi=chi2_reduced,
                rfactor=rfactor, aic=aic, bic=bic, covar=result.covar)
    for attr in ('params', 'nvarys', 'nfree', 'ndata', 'var_names', 'nfev',
                 'success', 'errorbars', 'message', 'lmdif_message'):
        setattr(out, attr, getattr(result, attr, None))

    # B3: 额外属性
    out.chi2_data = chi2_data
    out.restraint_chi2 = restraint_chi2
    out.restraint_c0 = c0
    rows = []
    for r, ti in zip(restraints, t):
        rows.append(dict(name=r["name"], expr=r["expr"], value=r["value"], sigma=r["sigma"],
                         note=r.get("note", ""), fitted=float(ti * r["sigma"] + r["value"]),
                         pull=float(ti), chi2=float(c0 * ti ** 2)))
    out.restraints = rows
    return out
