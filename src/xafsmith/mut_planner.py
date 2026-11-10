"""mut_planner —— 样品设计：总 μt、边跳、推荐质量/叠层数、邻近吸收边干扰。

数据来源：xraydb（Elam 表）质量吸收系数与边能量。

用法：
  python -m xafsmith.mut_planner --formula IrO2 --element Ir --edge L3 --area 1.33 \
         [--diluent BN --mass-diluent 100] [--mass 10]     # mass 单位 mg，area 单位 cm²
  python -m xafsmith.mut_planner --interfere Ir,Ta,O --element Ir --edge L3 --emax 12000
"""
import argparse

import numpy as np
import pandas as pd

from .common import e2k, edge_energy


class _LazyXraydb:
    """xraydb 导入约 0.7 秒：第一次用到时才导入，加快图形界面启动"""
    def __getattr__(self, name):
        import xraydb as _x
        return getattr(_x, name)


xraydb = _LazyXraydb()


def mass_atten(formula, energy):
    """质量衰减系数 μ/ρ (cm²/g)，光电+散射总和"""
    return float(xraydb.material_mu(formula, energy, density=1.0, kind="total"))


def mut_for_mass(formula, mass_mg, area_cm2, element, edge, diluent=None, mass_dil_mg=0.0,
                 de=50.0):
    """给定质量，计算边前/边后总 μt 与边跳。"""
    e0 = edge_energy(element, edge)
    rho_a = mass_mg / 1000.0 / area_cm2          # g/cm²
    rho_d = mass_dil_mg / 1000.0 / area_cm2 if diluent else 0.0
    below = mass_atten(formula, e0 - de) * rho_a + (mass_atten(diluent, e0 - de) * rho_d if diluent else 0)
    above = mass_atten(formula, e0 + de) * rho_a + (mass_atten(diluent, e0 + de) * rho_d if diluent else 0)
    return dict(E0=e0, mut_below=below, mut_above=above, edge_step=above - below,
                areal_density_mg_cm2=mass_mg / area_cm2)


def recommend_mass(formula, area_cm2, element, edge, target_mut=2.0, diluent=None,
                   mass_dil_mg=0.0, de=50.0):
    """在稀释剂质量固定时，求使边后总 μt = target 的样品质量。"""
    e0 = edge_energy(element, edge)
    mu_s = mass_atten(formula, e0 + de)
    mu_d = mass_atten(diluent, e0 + de) if diluent else 0.0
    rho_d = mass_dil_mg / 1000.0 / area_cm2 if diluent else 0.0
    rho_s = max(target_mut - mu_d * rho_d, 0) / mu_s
    m = rho_s * area_cm2 * 1000.0
    r = mut_for_mass(formula, m, area_cm2, element, edge, diluent, mass_dil_mg, de)
    r["mass_mg"] = m
    r["ok_step"] = r["edge_step"] >= 0.2
    r["advice"] = ("边跳 ≥ 0.2，可行" if r["ok_step"] else
                   "边跳 < 0.2：目标元素太稀，考虑减少稀释剂/基体，或改用荧光")
    return r


def layers_for_film(formula, density, thickness_um, element, edge, target_mut=2.0, de=50.0):
    """薄膜/箔：每层厚度已知，计算推荐叠层数"""
    e0 = edge_energy(element, edge)
    mu_b = xraydb.material_mu(formula, e0 - de, density=density) * thickness_um * 1e-4
    mu_a = xraydb.material_mu(formula, e0 + de, density=density) * thickness_um * 1e-4
    n = max(1, int(round(target_mut / mu_a)))
    return dict(E0=e0, mut_per_layer=mu_a, step_per_layer=mu_a - mu_b, n_layers=n,
                mut_total=n * mu_a, step_total=n * (mu_a - mu_b))


def interfering_edges(elements, element, edge, emax=None, kmax_report=20.0):
    """列出目标边之后、扫描范围内出现的所有吸收边，换算成 k。没有这个检查不得选 k 范围。"""
    e0 = edge_energy(element, edge)
    if emax is None:
        emax = e0 + (kmax_report ** 2) / 0.2625
    rows = []
    for el in elements:
        for name, ed in xraydb.xray_edges(el).items():
            if e0 < ed.energy <= emax and not (el == element and name == edge):
                rows.append(dict(element=el, edge=name, energy=ed.energy,
                                 dE=ed.energy - e0, k=float(e2k(ed.energy - e0))))
    df = pd.DataFrame(rows, columns=["element", "edge", "energy", "dE", "k"])
    return df.sort_values("energy").reset_index(drop=True)


def k_limit(elements, element, edge, emax_data, margin_k=0.3):
    """可用 k 上限 = min(数据末端 k, 第一个干扰边 k − margin)"""
    e0 = edge_energy(element, edge)
    kdata = float(e2k(emax_data - e0))
    df = interfering_edges(elements, element, edge, emax=emax_data + 50)
    if len(df):
        return min(kdata, float(df.k.iloc[0]) - margin_k), df
    return kdata, df


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--formula")
    ap.add_argument("--element", required=True)
    ap.add_argument("--edge", required=True)
    ap.add_argument("--area", type=float, default=1.327, help="cm²（默认 φ13 mm）")
    ap.add_argument("--mass", type=float)
    ap.add_argument("--diluent")
    ap.add_argument("--mass-diluent", type=float, default=0.0)
    ap.add_argument("--target", type=float, default=2.0)
    ap.add_argument("--interfere")
    ap.add_argument("--emax", type=float)
    a = ap.parse_args()
    if a.formula:
        if a.mass:
            print(mut_for_mass(a.formula, a.mass, a.area, a.element, a.edge, a.diluent,
                               a.mass_diluent))
        print(recommend_mass(a.formula, a.area, a.element, a.edge, a.target, a.diluent,
                             a.mass_diluent))
    if a.interfere:
        print(interfering_edges(a.interfere.split(","), a.element, a.edge, a.emax).to_string())


if __name__ == "__main__":
    main()
