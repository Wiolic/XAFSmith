"""数值基准：Cu 箔（K 边）第一壳层 EXAFS 拟合。

参考答案来自 xraylarch 自己的回归测试（不是凭记忆）：
  tests/test_larchexamples_xafs.py::test13_feffit1，运行 examples/feffit/doc_feffit1.lar
  （https://github.com/xraypy/xraylarch，MIT 许可；本文件写入时该测试文件的最新提交 3c781f4b18，2026-09-11）
  断言值：amp = 0.93、del_e0 = 4.364 eV、del_r = −0.006 Å、sig2 = 0.0087 Å²
  larch 用的容差：isNear(places=1) → |差| < 0.05；places=3 → |差| < 0.0005。
输入：cu_metal_rt.xdi（tests/data/demo_project/data/raw/public/）、feffcu01.dat（tests/data/benchmark/，同一仓库
examples/feffit/），autobk(rbkg=1, kw=2)，k 3–17 Å⁻¹，kw=2，dk=4，Kaiser 窗，R 1.4–3.0 Å。

两层检查：
  A. 拟合引擎：同一 χ(k)、同一模型，经 XAFSmith 的模型 JSON → fit_exafs.run_fit 得到的结果
     1) 与 larch 回归测试断言值一致（用 larch 自己的容差）；
     2) 与在本测试里直接调用 larch feffit 的结果一致（|差| < 1e-6，检查参数/路径/变换的传递没有走样）。
  B. 完整流程：XAFSmith 读入 → 按参比校准 → XAFSmith 的归一化与背景参数 → 同一模型拟合。
     处理约定不同（E0 定义、归一化范围、能量校准），所以不要求与 A 逐位相同，只检查物理上应当不变的量：
       S0² 与 σ² 用 larch 的容差（0.05、0.0005）——同一谱、同一 rbkg/k 范围，归一化差异只有百分之几；
       ΔR 容差 0.003 Å——ΔR 与 ΔE0 相关，E0 定义不同会带动 ΔR 改变约千分之几 Å；
       拟合得到的边能量 E0+ΔE0 换回原始能量标尺后应与 A 一致，容差 1 eV
       （E0 换了定义，ΔE0 会随之补偿，两者之和才是可比的量）。
运行：python -m pytest tests/benchmark -q
"""
from pathlib import Path

import numpy as np
import pytest

TESTS = Path(__file__).resolve().parents[1]
DEMO = TESTS / "data" / "demo_project"
CU = DEMO / "data" / "raw" / "public" / "cu_metal_rt.xdi"
FEFF = TESTS / "data" / "benchmark" / "feffcu01.dat"

LARCH_REF = dict(amp=0.93, del_e0=4.364, del_r=-0.006, sig2=0.0087)     # test13_feffit1 的断言值
LARCH_TOL = dict(amp=0.05, del_e0=0.05, del_r=0.0005, sig2=0.0005)     # places=1 / places=3

MODEL = {
    "name": "Cu_benchmark_1shell", "sample": "cu_metal_rt",
    "kmin": 3, "kmax": 17, "dk": 4, "window": "kaiser", "kweight": 2,
    "rmin": 1.4, "rmax": 3.0, "fitspace": "r",
    "params": {"amp": {"value": 1.0, "vary": True}, "del_e0": {"value": 0.0, "vary": True},
               "sig2": {"value": 0.0, "vary": True}, "del_r": 0.0},
    "paths": [{"file": str(FEFF), "label": "Cu-Cu", "s02": "amp", "e0": "del_e0",
               "sigma2": "sig2", "deltar": "del_r"}],
}


def _vals(res):
    return {k: float(res.params[k].value) for k in LARCH_REF}


@pytest.fixture(scope="module")
def chi_tutorial():
    """与 larch 示例相同的 χ(k)：XAFSmith 读入 μ（与文件 mutrans 列一致），larch autobk(rbkg=1, kw=2)。"""
    from larch import Group
    from larch.xafs import autobk
    from xafsmith.readers import read_scan
    g0 = read_scan(CU)
    g = Group(energy=g0.energy, mu=g0.mu)
    autobk(g.energy, g.mu, group=g, rbkg=1.0, kw=2)
    return g


@pytest.fixture(scope="module")
def fit_a(chi_tutorial):
    from xafsmith import fit_exafs as fx
    res, _dset, summ = fx.run_fit(chi_tutorial, MODEL, root=None)
    return res, summ


# ------------------------------------------------------------------ A. 拟合引擎
def test_a_matches_larch_regression_values(fit_a):
    v = _vals(fit_a[0])
    for k, ref in LARCH_REF.items():
        assert abs(v[k] - ref) < LARCH_TOL[k], f"{k} = {v[k]:.5f}，larch 回归值 {ref}（容差 {LARCH_TOL[k]}）"


def test_a_identical_to_direct_larch_call(chi_tutorial, fit_a):
    from larch.fitting import guess, param, param_group
    from larch.xafs import feffit, feffit_dataset, feffit_transform, feffpath
    pars = param_group(amp=param(1.0, vary=True), del_e0=param(0.0, vary=True),
                       sig2=param(0.0, vary=True), del_r=guess(0.0, vary=True))
    path = feffpath(str(FEFF), s02="amp", e0="del_e0", sigma2="sig2", deltar="del_r")
    trans = feffit_transform(kmin=3, kmax=17, kw=2, dk=4, window="kaiser", rmin=1.4, rmax=3.0)
    out = feffit(pars, feffit_dataset(data=chi_tutorial, pathlist=[path], transform=trans))
    a, b = _vals(fit_a[0]), {k: float(out.params[k].value) for k in LARCH_REF}
    for k in LARCH_REF:
        assert abs(a[k] - b[k]) < 1e-6, f"{k}: XAFSmith {a[k]} vs larch {b[k]}"
    assert abs(fit_a[0].rfactor - out.rfactor) < 1e-8


def test_a_summary_is_sane(fit_a):
    res, summ = fit_a
    assert summ["nvarys"] == 4
    assert abs(summ["n_idp_formula"] - 2 * 14 * 1.6 / np.pi) < 1e-9        # N_idp = 2ΔkΔR/π
    assert summ["rfactor"] < 0.02                                         # 金属箔第一壳层应拟合得很好
    p = summ["paths"][0]
    assert abs(p["N"] - 12) < 1e-6                                         # fcc 第一壳层 12 个 Cu
    assert abs(p["R"] - (2.5478 + p["deltar"])) < 1e-9                     # reff 来自 feffcu01.dat
    assert not [w for w in summ["warnings"] if "eV" in w]                  # ΔE0 未超出 ±10 eV


# ------------------------------------------------------------------ B. 完整流程
@pytest.fixture(scope="module")
def fit_b():
    from xafsmith import fit_exafs as fx, paths, pipeline as pl
    old = paths.ROOT
    paths.set_root(DEMO)
    try:
        g, _ = pl.build_sample("cu_metal_rt", calib={})        # 不读旧的 calib.json：当场按参比校准
        res, _dset, summ = fx.run_fit(g, MODEL, root=None)
    finally:
        paths.set_root(old)
    return g, res


def test_b_pipeline_consistent_with_reference(fit_b, fit_a, chi_tutorial):
    g, res = fit_b
    a, b = _vals(fit_a[0]), _vals(res)
    assert g.mu_from == "channels" and g.format == "xdi"
    assert abs(b["amp"] - LARCH_REF["amp"]) < 0.05, b
    assert abs(b["sig2"] - LARCH_REF["sig2"]) < 0.0005, b
    assert abs(b["del_r"] - a["del_r"]) < 0.003, (a, b)
    edge_a = chi_tutorial.e0 + a["del_e0"]                      # 原始能量标尺
    edge_b = g.e0 + b["del_e0"] - g.e_shift                     # XAFSmith 能量已加校准 ΔE，换回原始标尺
    assert abs(edge_a - edge_b) < 1.0, (edge_a, edge_b, g.e0, g.e_shift)
    assert abs(b["del_e0"]) < 10                                # CLAUDE.md 第 5 节：超过 ±10 eV 要怀疑 E0 定义
