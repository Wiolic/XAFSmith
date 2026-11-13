"""B3 restraint 软约束：驱动与 larch 逐位一致、权重极限、高斯合并、误差校准、逐数据集统计、警告。

设计与容差见路线图“B3 设计”第 5 节（执行时不得改容差）。
运行：python -m pytest tests/benchmark/test_restraints.py -q
"""
import numpy as np
import pytest

import test_cu_feffit as cu
from test_cu_feffit import MODEL

from xafsmith import fit_exafs as fx

chi_tutorial = cu.chi_tutorial          # fixture 复用


def _cu_parts(g, sig2=0.0):
    from larch.fitting import guess, param_group
    from larch.xafs import feffit_dataset, feffit_transform, feffpath
    pars = param_group(amp=guess(1.0), del_e0=guess(0.0), sig2=guess(sig2), del_r=guess(0.0))
    p = feffpath(str(cu.FEFF), label="Cu-Cu", s02="amp", e0="del_e0", sigma2="sig2", deltar="del_r")
    tr = feffit_transform(kmin=3, kmax=17, dk=4, window="kaiser", kweight=2, rmin=1.4, rmax=3.0, fitspace="r")
    return pars, feffit_dataset(data=g, pathlist=[p], transform=tr)


# ------------------------------------------------------------------ R0
def test_restrained_empty_bitwise(chi_tutorial):
    from larch.xafs import feffit, feffit_report
    from xafsmith._feffit_restrained import feffit_restrained
    pa, da = _cu_parts(chi_tutorial)
    ref = feffit(pa, [da])
    pb, db = _cu_parts(chi_tutorial)
    new = feffit_restrained(pb, [db], [], 1.0)
    for k in ("amp", "del_e0", "sig2", "del_r"):
        assert ref.params[k].value == new.params[k].value, k
        assert ref.params[k].stderr == new.params[k].stderr, k
    for k in ("chi_square", "chi2_reduced", "rfactor", "n_independent"):
        assert getattr(ref, k) == getattr(new, k), k
    assert np.array_equal(ref.covar, new.covar)
    assert feffit_report(ref) == feffit_report(new)
