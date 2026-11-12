"""autobk 单元测试。"""
import numpy as np

from xafsmith.autobk import DEFAULT_BKG, autobk
from xafsmith.ft import forward
from xafsmith.normalize import normalize


def test_matches_larch(cu):
    """直接调用 larch.xafs.autobk（DEFAULT_BKG 全部参数 + 同一 pre_edge_kws）。"""
    from larch import Group
    from larch.xafs import autobk as lautobk
    normalize(cu)
    npar = dict(cu.norm_params)
    ref = Group(energy=cu.energy.copy(), mu=cu.mu.copy())
    # 与 XAFSmith 相同的前处理：同一 e0、edge_step
    from larch.xafs import pre_edge
    pre_edge(ref, e0=npar["e0"], pre1=npar["pre1"], pre2=npar["pre2"], norm1=npar["norm1"],
             norm2=npar["norm2"], nnorm=npar["nnorm"], nvict=npar["nvict"], make_flat=True)
    p = DEFAULT_BKG
    lautobk(ref, e0=cu.e0, edge_step=cu.edge_step, rbkg=p["rbkg"], kweight=p["kweight"], kmin=p["kmin"],
            kmax=p["kmax"], dk=p["dk"], win=p["win"], nclamp=p["nclamp"], clamp_lo=p["clamp_lo"],
            clamp_hi=p["clamp_hi"],
            pre_edge_kws=dict(pre1=npar["pre1"], pre2=npar["pre2"], norm1=npar["norm1"],
                              norm2=npar["norm2"], nnorm=npar["nnorm"]))
    autobk(cu)
    for a in ("chi", "k", "bkg"):
        d = np.max(np.abs(getattr(cu, a) - getattr(ref, a)))
        print("autobk", a, "max diff", d)
        np.testing.assert_allclose(getattr(cu, a), getattr(ref, a), rtol=0, atol=1e-12)


def test_k_grid(cu):
    """larch autobk 输出 k 网格：步长 0.05、从 0 开始。"""
    autobk(cu)
    assert cu.k[0] == 0.0
    np.testing.assert_allclose(np.diff(cu.k), 0.05, rtol=0, atol=1e-9)


def test_low_r_suppressed(cu):
    """rbkg 生效：R<0.9 Å 的 |χ(R)| 最大值 / 全局最大值 < 0.05。"""
    autobk(cu)
    forward(cu, kmin=3, kmax=14)
    ratio = cu.chir_mag[cu.r < 0.9].max() / cu.chir_mag.max()
    print("Cu low-R ratio:", ratio)
    assert ratio < 0.05


def test_auto_normalize_and_params(cu):
    """未归一化 Group 自动归一化；bkg_params 记录实际参数（None 取默认）。"""
    assert not hasattr(cu, "e0")
    autobk(cu, rbkg=1.3, kmax=None)
    assert hasattr(cu, "e0") and hasattr(cu, "norm_params")
    assert cu.bkg_params["rbkg"] == 1.3
    assert cu.bkg_params["kmax"] == DEFAULT_BKG["kmax"]
    assert set(cu.bkg_params) == set(DEFAULT_BKG)
