"""mut_planner 单元测试。参考值来自 xraydb 表值或解析关系。"""
import numpy as np
import pytest
import xraydb

from xafsmith import mut_planner as mp
from xafsmith.common import e2k


def test_mass_atten():
    """直接调用 xraydb.material_mu(density=1, kind='total')。"""
    for f, e in (("Fe2O3", 7200.0), ("IrO2", 11300.0)):
        np.testing.assert_allclose(mp.mass_atten(f, e), xraydb.material_mu(f, e, density=1.0, kind="total"),
                                   rtol=0, atol=1e-12)


def test_mut_for_mass():
    """线性：质量加倍 → mut 与边跳加倍；手算 Fe2O3 10 mg / 1.33 cm²。"""
    a = mp.mut_for_mass("Fe2O3", 10, 1.33, "Fe", "K")
    b = mp.mut_for_mass("Fe2O3", 20, 1.33, "Fe", "K")
    for k in ("mut_below", "mut_above", "edge_step"):
        np.testing.assert_allclose(b[k], 2 * a[k], rtol=1e-12)
    want = xraydb.material_mu("Fe2O3", a["E0"] + 50, density=1.0, kind="total") * 0.01 / 1.33
    np.testing.assert_allclose(a["mut_above"], want, rtol=1e-12)


@pytest.mark.parametrize("dil,md", [(None, 0.0), ("BN", 100.0)])
def test_recommend_mass_roundtrip(dil, md):
    r = mp.recommend_mass("Fe2O3", 1.33, "Fe", "K", target_mut=2.0, diluent=dil, mass_dil_mg=md)
    r2 = mp.mut_for_mass("Fe2O3", r["mass_mg"], 1.33, "Fe", "K", dil, md)
    np.testing.assert_allclose(r2["mut_above"], 2.0, rtol=1e-9)


def test_recommend_mass_diluent_exceeds():
    r = mp.recommend_mass("Fe2O3", 1.33, "Fe", "K", target_mut=0.1, diluent="BN", mass_dil_mg=1000.0)
    assert r["mass_mg"] == 0


def test_interfering_edges():
    """xraydb 表值：Ir L3 之后、13500 eV 前出现 Ir L2。"""
    df = mp.interfering_edges(["Ir", "Ta", "O"], "Ir", "L3", emax=13500)
    row = df[(df.element == "Ir") & (df.edge == "L2")]
    assert len(row) == 1
    assert row.energy.iloc[0] == pytest.approx(xraydb.xray_edge("Ir", "L2").energy, abs=1e-9)
    assert not ((df.element == "Ir") & (df.edge == "L3")).any()
    # k 换算须与 larch 的 k 网格同一常数：参考 = larch.xafs.xafsutils.etok（2m_e/ħ²，scipy CODATA）。
    # 设计稿原写 √(0.2625·dE)，0.2625 只是近似写法（k=24 Å⁻¹ 处差 1.5e-3），由 Opus 改为 larch 常数，容差不变。
    from larch.xafs.xafsutils import etok
    kref = np.array([etok(d) for d in df.dE])          # larch 的 etok 只接受标量
    print("interfering_edges k vs larch etok max diff:", np.max(np.abs(df.k - kref)))
    np.testing.assert_allclose(df.k, kref, rtol=0, atol=1e-6)
    assert list(df.energy) == sorted(df.energy)
    print("interfering:", df.to_dict("records"))


def test_pre_edge_edges():
    """xraydb 表值：Ta L2 落在 Ir L3 前 150…30 eV。"""
    df = mp.pre_edge_edges(["Ir", "Ta"], "Ir", "L3", -150, -30)
    assert ((df.element == "Ta") & (df.edge == "L2")).any()
    print("pre_edge_edges:", df.to_dict("records"))


def test_k_limit():
    kdata, df = mp.k_limit(["Fe"], "Fe", "K", mp.edge_energy("Fe", "K") + 500)
    assert len(df) == 0
    np.testing.assert_allclose(kdata, e2k(500.0), atol=1e-12)     # 数据末端 = E0 + 500 eV
    k2, df2 = mp.k_limit(["Ir", "Ta", "O"], "Ir", "L3", 13500)
    assert len(df2) and k2 == pytest.approx(df2.k.iloc[0] - 0.3, abs=1e-12)


def test_fluor_filter_fe():
    r = mp.fluor_filter("Fe", "K")
    t = r["table"]
    print("fluor_filter:", r["line"], r["line_energy"], t[["filter", "edge", "edge_energy"]].values.tolist())
    assert t["filter"].iloc[0] == "Mn" and t["edge"].iloc[0] == "K"
    ka1 = xraydb.xray_lines("Fe")["Ka1"].energy
    fk = xraydb.xray_edge("Fe", "K").energy
    assert ((t.edge_energy > ka1 + 30) & (t.edge_energy < fk - 10)).all()


def test_edge_table():
    t = mp.edge_table("Fe")
    assert t.set_index("edge").loc["K", "energy"] == pytest.approx(xraydb.xray_edge("Fe", "K").energy, abs=1e-9)
