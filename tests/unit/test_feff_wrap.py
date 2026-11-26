"""E18：feff_wrap.py 中其余公开函数的单元测试（build_builtin / 失败不毁旧结果 / default_edge 已在 test_feff_builtin、
test_feff_safe 里）：不等价位点、feff.inp 文本（FEFF6 / FEFF8）、feff_info、list_paths（files.dat / list.dat）、
run_feff 成功路径（真实 FEFF6L 小团簇）、build 的缩小团簇重试、内置结构目录与位点数。数值期望为结构 / 物理性质或快照（E18 时代码的输出）。"""
import shutil
from pathlib import Path

import pandas as pd
import pytest

from xafsmith import feff_wrap, paths, structures
from xafsmith.errors import FeffError

CU_DAT = Path(__file__).resolve().parents[1] / "data" / "benchmark" / "feffcu01.dat"
A_CU = 3.6149                                        # fcc Cu 晶格常数（Å）：最近邻 a/√2


def test_inequivalent_sites():
    cu = structures.builtin("Cu")
    assert feff_wrap.inequivalent_sites(cu, "Cu") == [(0, 4)] and feff_wrap.inequivalent_sites(cu, "O") == []
    wo3 = structures.builtin("WO3")
    sites = feff_wrap.inequivalent_sites(wo3, "W")
    assert len(sites) == 2 and sum(m for _, m in sites) == 8                        # 快照：WO3 有两个不等价 W 位点
    assert feff_wrap.n_absorber_sites("WO3", "W") == 2 and feff_wrap.n_absorber_sites("Cu", "Cu") == 1


def test_feffinp_feff6_text():
    cu = structures.builtin("Cu")
    t = feff_wrap.make_feffinp(cu, "Cu", "K", rmax=3.0, rcluster=3.0)
    lines = t.splitlines()
    assert lines[0] == "TITLE Cu Cu K site 0" and lines[-1] == "END"
    assert "HOLE 1 1.0" in lines and "CONTROL 1 1 1 1" in lines and "PRINT 1 0 0 0" in lines and "RMAX 3.00" in lines and "NLEG 4" in lines
    assert not any(ln.startswith(("EDGE", "SCF", "EXCHANGE")) for ln in lines)
    assert "  0  29 Cu" in lines and "  1  29 Cu" in lines                           # 吸收原子 ipot 0；Cu 的 Z = 29
    atoms = lines[lines.index("ATOMS") + 1:-1]
    assert len(atoms) == 13                                                        # 吸收原子 + 12 个最近邻（rcluster 3 Å）
    d = [float(a.split()[-1]) for a in atoms]
    assert d[0] == 0.0 and d == sorted(d) and all(abs(x - A_CU / 2 ** 0.5) < 2e-3 for x in d[1:])
    assert atoms[0].split()[3] == "0" and all(a.split()[3] == "1" for a in atoms[1:])
    assert t.endswith("\n")


def test_feffinp_feff8_text_and_edges():
    cu = structures.builtin("Cu")
    t = feff_wrap.make_feffinp(cu, "Cu", "L3", rmax=3.0, rcluster=3.0, code="feff8", scf=3.5, exchange=2, s02=0.9, title="demo")
    lines = t.splitlines()
    assert lines[0] == "TITLE demo Cu L3 site 0"
    assert "EDGE L3" in lines and "S02 0.9" in lines and "CONTROL 1 1 1 1 1 1" in lines
    assert "PRINT 1 0 0 0 0 3" in lines                                           # FEFF8 的 PRINT 最后一位必须是 3
    assert "SCF 3.50 0 30 0.2 1" in lines and "EXCHANGE 2 0 0" in lines
    assert not any(ln.startswith("HOLE") for ln in lines)
    assert "HOLE 4 1.0" in feff_wrap.make_feffinp(cu, "Cu", "L3", rmax=3.0, rcluster=3.0).splitlines()      # L3 → 空穴编号 4
    assert feff_wrap.HOLE["K"] == 1 and feff_wrap.HOLE["L3"] == 4


def test_feffinp_site_index_and_max_atoms():
    wo3 = structures.builtin("WO3")
    s0, s1 = (feff_wrap.make_feffinp(wo3, "W", "L3", site_index=i, rmax=4.0, rcluster=4.0) for i, _ in feff_wrap.inequivalent_sites(wo3, "W"))
    assert s0.splitlines()[0].endswith("site 0") and s1.splitlines()[0].endswith("site 4") and s0 != s1
    cu = structures.builtin("Cu")
    many = feff_wrap.make_feffinp(cu, "Cu", "K", rmax=6.0, rcluster=8.0, max_atoms=20)
    assert len(many.splitlines()[many.splitlines().index("ATOMS") + 1:-1]) == 20


def test_feff_info_from_files(tmp_path):
    assert feff_wrap.feff_info(tmp_path) == dict(code="feff6", scf=None, exchange=0, fermi_ev=None)      # 空目录
    (tmp_path / "feff.inp").write_text("TITLE x\nEDGE K\nSCF 4.50 0 30 0.2 1\nEXCHANGE 2 0 0\n", encoding="utf-8")
    (tmp_path / "log1.dat").write_text("a mu_new= -5.1\n...\n mu_new= -4.25 \n", encoding="utf-8")
    assert feff_wrap.feff_info(tmp_path) == dict(code="feff8", scf=4.5, exchange=2, fermi_ev=-4.25)      # 取最后一个 mu_new
    d6 = tmp_path / "six"
    d6.mkdir()
    (d6 / "feff.inp").write_text("TITLE x\nHOLE 1 1.0\n", encoding="utf-8")
    assert feff_wrap.feff_info(d6)["code"] == "feff6"


def test_list_paths_from_feff_file(tmp_path):
    shutil.copy(CU_DAT, tmp_path / "feff0001.dat")
    df = feff_wrap.list_paths(tmp_path)
    assert list(df.columns) == ["file", "name", "reff", "degen", "nleg", "amp_ratio", "label"] and len(df) == 1
    r = df.iloc[0]
    assert r["name"] == "feff0001.dat" and r["nleg"] == 2 and r["degen"] == 12 and r["label"] == "Cu-Cu"
    assert r["reff"] == pytest.approx(2.5478, abs=1e-4) and pd.isna(r["amp_ratio"])         # 没有 files.dat：无振幅比
    assert feff_wrap.list_paths(tmp_path / "empty_none").empty


def test_list_paths_amp_ratio_from_files_dat_and_list_dat(tmp_path):
    shutil.copy(CU_DAT, tmp_path / "feff0001.dat")
    (tmp_path / "files.dat").write_text("   feff0001.dat      1.0   87.500   2.556   12   1.0\n", encoding="utf-8")
    assert feff_wrap.list_paths(tmp_path).iloc[0]["amp_ratio"] == pytest.approx(87.5)
    (tmp_path / "files.dat").unlink()
    (tmp_path / "list.dat").write_text("  1   12.000   66.250   2.556   2   4.5\n", encoding="utf-8")          # FEFF8L 的 list.dat
    assert feff_wrap.list_paths(tmp_path).iloc[0]["amp_ratio"] == pytest.approx(66.25)


def test_run_feff_success_replaces_folder_contents(tmp_path):
    cu = structures.builtin("Cu")
    inp = feff_wrap.make_feffinp(cu, "Cu", "K", rmax=3.0, rcluster=4.0)
    (tmp_path / "feff0099.dat").write_text("stale\n", encoding="utf-8")                # 旧结果：成功后被替换
    df = feff_wrap.run_feff(tmp_path, inp)
    assert len(df) >= 1 and (tmp_path / "feff0001.dat").exists() and not (tmp_path / "feff0099.dat").exists()
    assert (tmp_path / "feff.inp").read_text(encoding="utf-8") == inp
    assert not (tmp_path / feff_wrap.RUN_DIR).exists() and not (tmp_path / feff_wrap.FAILED_DIR).exists()
    first = df[df["nleg"] == 2].sort_values("reff").iloc[0]
    assert first["degen"] == 12 and first["reff"] == pytest.approx(A_CU / 2 ** 0.5, abs=2e-3)
    assert feff_wrap.feff_info(tmp_path)["code"] == "feff6"


def test_build_shrinks_cluster_radius_until_paths_found(tmp_path, monkeypatch):
    radii = []

    def fake_run(out, txt, code=None):
        radii.append(max(float(ln.split()[-1]) for ln in txt.splitlines()[txt.splitlines().index("ATOMS") + 1:-1]))
        return pd.DataFrame({"a": [1]}) if len(radii) == 2 else pd.DataFrame()
    monkeypatch.setattr(feff_wrap, "run_feff", fake_run)
    cu = structures.builtin("Cu")
    df = feff_wrap.build(cu, "Cu", "K", tmp_path, rmax=3.0, rcluster=8.0)
    assert len(df) == 1 and len(radii) == 2 and radii[1] < radii[0]                  # 第一次空 → 缩小团簇再试


def test_build_raises_feff_error_when_nothing_works(tmp_path, monkeypatch):
    calls = []
    monkeypatch.setattr(feff_wrap, "run_feff", lambda out, txt, code=None: calls.append(1) or pd.DataFrame())
    with pytest.raises(FeffError) as ei:
        feff_wrap.build(structures.builtin("Cu"), "Cu", "K", tmp_path, rmax=6.0, rcluster=8.0)
    assert len(calls) == 3 and "FEFF" in str(ei.value)                              # rcluster 8、7、6.5 各试一次


def test_builtin_feff_dir(tmp_path):
    old = paths.ROOT
    paths.set_root(tmp_path)
    try:
        assert feff_wrap.builtin_feff_dir("IrO2", "Ir", "L3") == tmp_path / "output" / "feff" / "IrO2_IrL3" / "site0"
        assert feff_wrap.builtin_feff_dir("WO3", "W", "L3", 4) == tmp_path / "output" / "feff" / "WO3_WL3" / "site4"
    finally:
        paths.set_root(old)
