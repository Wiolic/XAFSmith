"""混合相快速拟合的项目对照（只在有 IrTaOx 项目时跑）：IrTa 原位 Ir L3 序列，Ir–O（IrO2 路径）+ Ir–Ir（fcc 金属）两相，
与项目里的 models/JIr_insitu_OM.json（E0、ΔR、σ² 全序列共用，N 逐样品，S0² = 0.8）重拟合的结果比。

JIr_insitu_OM 的 R 窗是 1.2–3.0 Å；快速拟合自动 Rmin 取第一峰（金属 Ir–Ir，≈ 2.3 Å）− 0.6 = 1.7 Å，把 1.6 Å 处的 Ir–O 峰切掉了，
所以 Ir–O 的 N 在自动 Rmin 下与参考不同（见报告）；给同一个 Rmin = 1.2 时两者逐位相同。"""
import json
from pathlib import Path

import pytest

from xafsmith import fit_exafs as fx, paths, pipeline as pl, quickfit as qf

PROJECT = Path(__file__).resolve().parents[3]
REF = PROJECT / "models" / "JIr_insitu_OM.json"
FEFF_O, FEFF_M = "output/feff/IrO2_IrL3", "output/feff/Ir_IrL3"

pytestmark = pytest.mark.skipif(
    not (REF.exists() and (PROJECT / FEFF_O).exists() and (PROJECT / FEFF_M).exists()),
    reason="需要 IrTaOx 项目（JIr_insitu_OM 与 IrO2 / Ir 的 FEFF）")


@pytest.fixture(scope="module")
def compare():
    old = paths.ROOT
    paths.set_root(PROJECT)
    try:
        ref = json.loads(REF.read_text(encoding="utf-8-sig"))
        nm = fx.normalize_model(ref)
        groups = {d["id"]: pl.build_sample(d["sample"])[0] for d in nm["datasets"]}
        P = fx.fit_multi(groups, ref)[2]["params"]
        samples = [d["sample"] for d in nm["datasets"]]
        out = {}
        for tag, rmin in (("same_rmin", 1.2), ("auto", None)):
            m = qf.build_joint_model(samples, FEFF_O, None, s02=0.8, rmin=rmin, feff_dir2=FEFF_M)
            out[tag] = qf.run(m, {pl.safe(s): groups[d["id"]] for s, d in zip(samples, nm["datasets"])})
        yield nm, P, out
    finally:
        paths.set_root(old)


def test_same_window_reproduces_jir_insitu_om(compare):
    """同一个 R 窗：各样品 N(Ir–O)、N(Ir–Ir) 与项目模型重拟合相差远小于 1σ，共享参数一致。"""
    nm, P, out = compare
    r = out["same_rmin"]
    assert r.shell2 is not None and r.window["rmin"] == 1.2 and r.window["rmax"] == 3.0
    for d, s in zip(nm["datasets"], r.samples):
        a, b = P["nO_" + d["id"]], P["nM_" + d["id"]]
        assert abs(s.n - a["value"]) < 0.05 and abs(s.n - a["value"]) < a["stderr"], d["sample"]
        assert abs(s.phase2["n"] - b["value"]) < 0.05 and abs(s.phase2["n"] - b["value"]) < b["stderr"], d["sample"]
    Q = r.fit["summ"]["params"]
    assert abs(Q["e0"]["value"] - P["e0"]["value"]) < 0.1 and abs(Q["ss2"]["value"] - P["ssM"]["value"]) < 2e-4


def test_auto_rmin_ir_ir_agrees_and_ir_o_is_cut(compare):
    """自动 Rmin（= 1.70 Å）：Ir–Ir 的 N 仍在 1σ 内；Ir–O 峰（1.6 Å）落在窗外，N 偏低——判定里的信息，记入报告。"""
    nm, P, out = compare
    r = out["auto"]
    assert r.window["rmin"] > 1.6
    for d, s in zip(nm["datasets"], r.samples):
        b = P["nM_" + d["id"]]
        assert abs(s.phase2["n"] - b["value"]) < b["stderr"], d["sample"]
