"""readers（数据读入）单元测试：格式识别、列按名称映射、μ 计算、猜测与报错。

公开数据在 tests/data/demo_project/data/raw/public/（来源与许可见 SOURCES.md）；
合成数据只用于测解析规则，不当作测量数据。
运行：python -m pytest tests/unit/test_readers.py
"""
from pathlib import Path

import numpy as np
import pytest

from xafsmith import io as xio
from xafsmith.readers import ReadError, detect_format, read_file, read_scan, resolve_format

PUB = Path(__file__).resolve().parents[1] / "data" / "demo_project" / "data" / "raw" / "public"


# ------------------------------------------------------------------ 合成数据
def _edge(n=120, e0=8979.0):
    e = np.linspace(e0 - 60, e0 + 200, n)
    mu = 0.3 + 0.8 / (1 + np.exp(-(e - e0) / 2.0))
    i0 = np.full(n, 1.0e5)
    return e, i0, i0 * np.exp(-mu), mu


def _write(path, header, names, cols):
    lines = list(header) + ["# " + " ".join(names)]
    for row in zip(*cols):
        lines.append(" ".join(f"{v:.8g}" for v in row))
    Path(path).write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


# ------------------------------------------------------------------ 公开数据：格式识别与元信息
EXPECT = [
    # 文件, 格式, 元素, 边, 模式, μ 来源
    ("cu_metal_rt.xdi", "xdi", "Cu", "K", "trans", "channels"),
    ("cu_rt01.xmu", "athena_xmu", "Cu", "K", None, "file"),
    ("feo_rt1.xdi", "xdi", "Fe", "K", "trans", "file"),
    ("fe2o3_rt1.xmu", "athena_xmu", "Fe", "K", None, "file"),
    ("fe3c_rt.xdi", "xdi", "Fe", "K", "trans", "file"),
    ("ni_metal_rt.xdi", "xdi", "Ni", "K", "trans", "file"),
    ("pt_metal_rt.xdi", "xdi", "Pt", "L3", "trans", "channels"),
    ("fe.060", "xdac", "Fe", "K", "trans", "channels"),
]


@pytest.mark.parametrize("name,fmt,el,ed,mode,mu_from", EXPECT)
def test_public_files(name, fmt, el, ed, mode, mu_from):
    p = PUB / name
    assert detect_format(p)[0] == fmt
    g = read_scan(p)
    assert (g.element, g.edge, g.mode, g.mu_from, g.format) == (el, ed, mode, mu_from, fmt)
    assert len(g.energy) > 100 and np.all(np.diff(g.energy) > 0)
    assert np.all(np.isfinite(g.mu))
    assert g.energy[0] < g.e_nominal if g.e_nominal else True


def test_guessed_fields_are_reported():
    g = read_scan(PUB / "fe.060")                 # XDAC 头里只有 E0：元素与边按表值猜
    assert set(g.meta_guessed) >= {"element", "edge"}
    assert not read_scan(PUB / "cu_metal_rt.xdi").meta_guessed   # XDI 头里写明了元素与边


# ------------------------------------------------------------------ μ 的定义与一致性
def test_cu_mu_from_channels_matches_file_column():
    g = read_scan(PUB / "cu_metal_rt.xdi")
    raw = np.loadtxt(PUB / "cu_metal_rt.xdi", comments="#")          # energy i0 itrans mutrans
    assert np.allclose(g.energy, raw[:, 0])
    assert np.allclose(g.mu, raw[:, 3], atol=1e-6)                   # 由通道算出的 μ 与文件 μ 列一致
    assert np.allclose(g.mu, np.log(raw[:, 1] / raw[:, 2]))
    assert not g.read_warnings


def test_cu_xdi_and_xmu_are_the_same_scan():
    a, b = read_scan(PUB / "cu_metal_rt.xdi"), read_scan(PUB / "cu_rt01.xmu")
    assert np.allclose(a.energy, b.energy)
    assert np.allclose(a.mu, b.mu, atol=1e-6)


def test_pt_columns_mapped_by_name_not_position():
    """pt_metal_rt.xdi 的列顺序是 energy time itrans i0（和 Cu 的 i0 在前相反）。"""
    g = read_scan(PUB / "pt_metal_rt.xdi")
    raw = np.loadtxt(PUB / "pt_metal_rt.xdi", comments="#")
    assert np.allclose(g.mu, np.log(raw[:, 3] / raw[:, 2]))
    assert g.mu[-1] > g.mu[0]                                         # L3 边：μ 随能量上升


def test_swapped_column_order_gives_same_mu(tmp_path):
    e, i0, it, mu = _edge()
    h = ["# Cu K edge, synthetic parsing test"]
    a = _write(tmp_path / "a.dat", h, ["energy", "i0", "itrans"], [e, i0, it])
    b = _write(tmp_path / "b.dat", h, ["energy", "itrans", "i0"], [e, it, i0])
    ga, gb = read_scan(a, fmt="columns"), read_scan(b, fmt="columns")
    assert np.allclose(ga.mu, gb.mu) and np.allclose(ga.mu, mu, atol=1e-6)


def test_mu_column_mismatch_warns(tmp_path):
    e, i0, it, mu = _edge()
    rng = np.random.default_rng(0)
    p = _write(tmp_path / "m.dat", [], ["energy", "i0", "itrans", "mu"], [e, i0, it, rng.normal(size=len(e))])
    g = read_scan(p, fmt="columns", mode="trans")
    assert g.mu_from == "channels" and any("0.999" in w for w in g.read_warnings)


def test_channels_preferred_over_file_mu(tmp_path):
    e, i0, it, mu = _edge()
    p = _write(tmp_path / "m.dat", [], ["energy", "i0", "itrans", "mu"], [e, i0, it, mu + 5.0])
    g = read_scan(p, fmt="columns")
    assert g.mu_from == "channels" and np.allclose(g.mu, mu, atol=1e-6)


# ------------------------------------------------------------------ 模式
def test_mode_rules(tmp_path):
    e, i0, it, mu = _edge()
    iff = i0 * (0.02 + 0.01 * mu)
    both = _write(tmp_path / "both.dat", [], ["energy", "i0", "it", "if"], [e, i0, it, iff])
    g = read_scan(both, fmt="columns")
    assert g.mode == "trans" and "mode" in g.meta_guessed            # 两种通道都有：默认透射并标记为猜测
    g = read_scan(both, fmt="columns", mode="fluo")
    assert g.mode == "fluo" and np.allclose(g.mu, iff / i0)
    only_f = _write(tmp_path / "f.dat", [], ["energy", "i0", "if"], [e, i0, iff])
    assert read_scan(only_f, fmt="columns").mode == "fluo"
    with pytest.raises(ReadError):                                     # 要求透射，但没有 It 也没有 μ 列
        read_scan(only_f, fmt="columns", mode="trans")


def test_multichannel_fluorescence_summed(tmp_path):
    e, i0, it, mu = _edge()
    ch = [i0 * 0.01 * (1 + 0.1 * k) * (1 + mu) for k in range(3)]
    p = _write(tmp_path / "f.dat", [], ["energy", "i0", "ch1", "ch2", "ch3"], [e, i0] + ch)
    g = read_scan(p, fmt="columns")
    assert g.mode == "fluo" and np.allclose(g.mu, sum(ch) / i0)
    assert any("求和" in w for w in g.read_warnings)


# ------------------------------------------------------------------ 能量
def test_kev_converted_and_flagged(tmp_path):
    e, i0, it, mu = _edge()
    p = _write(tmp_path / "k.dat", [], ["energy", "i0", "itrans"], [e / 1000.0, i0, it])
    g = read_scan(p, fmt="columns")
    assert np.allclose(g.energy, e, rtol=1e-6) and "energy_unit" in g.meta_guessed
    p2 = _write(tmp_path / "k2.dat", [], ["energy_keV", "i0", "itrans"], [e / 1000.0, i0, it])
    assert "energy_unit" not in read_scan(p2, fmt="columns").meta_guessed      # 列名写明 keV 就不算猜


def test_angle_and_nonmonotonic_energy_rejected(tmp_path):
    e, i0, it, mu = _edge()
    ang = np.linspace(14.0, 13.0, len(e))
    with pytest.raises(ReadError):
        read_scan(_write(tmp_path / "a.dat", [], ["theta_deg", "i0", "itrans"], [ang, i0, it]), fmt="columns")
    with pytest.raises(ReadError):
        read_scan(_write(tmp_path / "t.dat", [], ["energy", "i0", "itrans"], [np.linspace(0.5, 1.0, len(e)), i0, it]), fmt="columns")
    zig = e.copy()
    zig[::2] = zig[::2][::-1]
    with pytest.raises(ReadError):
        read_scan(_write(tmp_path / "z.dat", [], ["energy", "i0", "itrans"], [zig, i0, it]), fmt="columns")


# ------------------------------------------------------------------ 列映射模板、错误信息
def test_user_mapping_and_templates(tmp_path):
    e, i0, it, mu = _edge()
    p = _write(tmp_path / "w.dat", [], ["E", "mon", "trn"], [e, i0, it])
    with pytest.raises(ReadError):                                     # 自动映射认不出 trn
        read_scan(p, fmt="columns")
    cols = {"energy": "E", "i0": "mon", "it": "trn"}
    assert np.allclose(read_scan(p, fmt="columns", columns=cols).mu, mu, atol=1e-6)
    assert np.allclose(read_scan(p, fmt="columns", columns={"energy": 0, "i0": 1, "it": 2}).mu, mu, atol=1e-6)
    tpl = {"my_beamline": {"base": "columns", "energy": "E", "i0": "mon", "it": "trn", "mode": "trans"}}
    assert resolve_format("my_beamline", tpl)[0] == "columns"
    g = read_scan(p, fmt="my_beamline", templates=tpl)
    assert g.mode == "trans" and np.allclose(g.mu, mu, atol=1e-6)
    with pytest.raises(ReadError):
        read_scan(p, fmt="columns", columns={"energy": "E", "i0": "nope", "it": "trn"})
    with pytest.raises(ReadError):
        read_scan(p, fmt="columns", columns={"energy": 0, "i0": 9, "it": 2})


def test_unknown_format_and_bad_names(tmp_path):
    f = tmp_path / "notes.txt"
    f.write_text("just some words\nand no numbers\n", encoding="utf-8")
    assert detect_format(f)[0] is None
    with pytest.raises(ReadError):
        read_scan(f)
    with pytest.raises(ReadError):
        read_scan(PUB / "cu_metal_rt.xdi", fmt="no_such_format")
    e, i0, it, mu = _edge()
    p = tmp_path / "nonames.dat"
    p.write_text("\n".join(f"{a} {b} {c}" for a, b, c in zip(e, i0, it)), encoding="utf-8")
    with pytest.raises(ReadError):
        read_scan(p, fmt="columns")                                    # 没有列名行又没给映射：不猜


# ------------------------------------------------------------------ BSRF（合成文件，只测解析）
def test_bsrf_synthetic(tmp_path):
    e, i0, it, mu = _edge(e0=11215.0)
    iff = i0 * 0.01 * (1 + mu)
    for head, mode in (("Transmission Mode", "trans"), ("Fluorescence Mode", "fluo")):
        p = tmp_path / f"s_{mode}"
        lines = ["# BSRF 1W1B synthetic", f"# Element: Ir, 11215 eV, {head}", "# 2026/4/30 20:50:51",
                 "# Energy I0 I1 If ln(I0/I1) If/I0 mu"]
        lines += [f"{a:.4f} {b:.2f} {c:.2f} {d:.2f} {np.log(b / c):.6f} {d / b:.6f} {np.log(b / c):.6f}"
                  for a, b, c, d in zip(e, i0, it, iff)]
        p.write_text("\n".join(lines) + "\n", encoding="utf-8")
        assert detect_format(p)[0] == "bsrf"
        g = read_scan(p)
        assert (g.element, g.edge, g.mode, g.timestamp) == ("Ir", "L3", mode, "2026/4/30 20:50:51")
        assert np.allclose(g.mu, np.log(i0 / it) if mode == "trans" else iff / i0, rtol=1e-4)
        assert read_scan(p, mode="fluo").mode == "fluo"                # meta.csv 的 mode 优先于文件头


# ------------------------------------------------------------------ Athena 工程
def test_prj_groups_and_element_guess():
    gs = read_file(PUB / "fe_athena.prj")
    assert len(gs) == 3 and all((g.element, g.edge) == ("Fe", "K") for g in gs)   # 不能把 Fe K 误判成 Nd L1
    assert all(g.mu_from == "file" and g.mode is None for g in gs)
    with pytest.raises(ReadError):
        read_scan(PUB / "fe_athena.prj")                               # 多组而没指定 group
    name = gs[0].group_name
    assert read_scan(PUB / "fe_athena.prj", group=name).group_name == name
    with pytest.raises(ReadError):
        read_scan(PUB / "fe_athena.prj", group="nonexistent")
    d = xio.read_prj(PUB / "fe_athena.prj")                            # 兼容旧接口：{组名: Group}
    assert set(d) == {g.group_name for g in gs}


# ------------------------------------------------------------------ 旧接口兼容
def test_legacy_wrappers():
    g = xio.read_columns(PUB / "cu_metal_rt.xdi", ecol=0, i0col=1, i1col=2, mode="trans")
    assert np.allclose(g.mu, read_scan(PUB / "cu_metal_rt.xdi").mu, atol=1e-9)
    g = xio.read_columns(PUB / "cu_metal_rt.xdi", ecol=0, mucol=3, mode="trans")
    assert g.mode == "trans" and g.mu_from == "file"
    assert xio.is_bsrf(PUB / "cu_metal_rt.xdi") is False
    assert xio.read_any(PUB / "fe.060").format == "xdac"
