"""B5 多重散射绑定向导（msbind）：手写几何，不依赖项目数据。核对值见设计 6.2 / 6.3。"""
import math

from xafsmith import msbind as mb

D = "output/feff/X"


def single(el, r, deltar, sigma2, use=True, d=D, label=None):
    return dict(file=f"{d}/f_{el}_{r}.dat", nleg=2, reff=r, label=label or f"A-{el}", use=use, deltar=deltar,
                sigma2=sigma2, geom=[("Ta", (0, 0, 0)), (el, (0, 0, r))])


def ms(geom, reff, d=D, **kw):
    return dict(file=f"{d}/ms.dat", nleg=len(geom), reff=reff, label="ms", use=True, deltar="0", sigma2="0.003",
                geom=geom, **kw)


# KTaO3 型：A = Ta，Ta–O 1.995，Ta–Ta 3.99
O1, TA1 = 1.995, 3.99
KT = [single("O", O1, "dr1", "ss1"), single("Ta", TA1, "2*dr1", "ssT")]


def run(rows, root="."):
    out = mb.suggest(rows, root)
    assert len(out) == 1
    return out[0]


def test_collinear_same_side_ta_ta_o_ta():
    g = [("Ta", (0, 0, 0)), ("Ta", (0, 0, TA1)), ("O", (0, 0, O1))]            # A, Ta(远), O(近)，A–Ta 方向共线
    s = run(KT + [ms(g, TA1)])
    assert s["deltar"] == "2*dr1" and s["sigma2"] == "ssT"
    assert s["exact"] and s["exact_sigma2"] and not s["problem"]


def test_collinear_opposite_sides_o_ta_o():
    g = [("Ta", (0, 0, 0)), ("O", (0, 0, O1)), ("O", (0, 0, -O1))]
    s = run(KT + [ms(g, 2 * O1)])
    assert s["deltar"] == "2*dr1"
    assert s["sigma2"] == "2*ss1"           # 两根独立键各 c = 1
    assert s["exact"] and not s["exact_sigma2"]


def test_triangle_90deg_ta_o_o_ta():
    g = [("Ta", (0, 0, 0)), ("O", (O1, 0, 0)), ("O", (0, O1, 0))]
    s = run(KT + [ms(g, (2 + math.sqrt(2)) * O1 / 2)])
    assert s["deltar"] == "1.707*dr1"
    assert s["sigma2"] == "1.457*ss1"
    assert not s["exact"] and not s["exact_sigma2"]


def test_equivalent_bond_ir_o_ir():
    """IrO2 型：A–O 1.98、A–Ir 3.55，O–Ir 腿 1.98（规则 3）。"""
    ro, rir = 1.98, 3.55
    cos = (ro ** 2 + rir ** 2 - ro ** 2) / (2 * ro * rir)           # |O–Ir| = ro
    ir = (rir * math.sqrt(1 - cos ** 2), 0, rir * cos)
    rows = [single("O", ro, "dr1", "ss1"), single("Ir", rir, "dr3", "ss2")]
    g = [("Ir", (0, 0, 0)), ("O", (0, 0, ro)), ("Ir", ir)]
    assert abs(math.dist(g[1][1], ir) - ro) < 1e-9
    s = run(rows + [ms(g, (2 * ro + rir) / 2)])
    assert s["deltar"] == "dr1 + 0.5*dr3"
    assert s["sigma2"] == "0.5*ss1 + 0.25*ss2"
    assert not s["exact"]


def test_same_bond_twice_a_b_a_b_a():
    g = [("Ta", (0, 0, 0)), ("O", (O1, 0, 0)), ("Ta", (0, 0, 0)), ("O", (O1, 0, 0))]
    s = run(KT + [ms(g, 2 * O1)])
    assert s["deltar"] == "2*dr1"
    assert s["sigma2"] == "4*ss1"           # 同一根键走两遍：c = 2
    assert s["exact_sigma2"]


def test_missing_single_row():
    g = [("Ta", (0, 0, 0)), ("Ta", (0, 0, TA1)), ("O", (0, 0, O1))]
    s = run([KT[0]] + [ms(g, TA1)])                                    # 没有 Ta–Ta 行
    assert s["deltar"] is None and s["sigma2"] is None
    assert "缺少 Ta@3.990" in s["problem"] and "先勾选" in s["problem"]


def test_unticked_single_row_not_used():
    g = [("Ta", (0, 0, 0)), ("O", (O1, 0, 0)), ("O", (0, O1, 0))]
    rows = [single("O", O1, "dr1", "ss1", use=False), ms(g, 3.4)]
    assert run(rows)["problem"]


def test_other_directory_not_used():
    g = [("Ta", (0, 0, 0)), ("O", (O1, 0, 0)), ("O", (0, O1, 0))]
    rows = [single("O", O1, "dr1", "ss1", d="output/feff/Y"), ms(g, 3.4)]
    assert run(rows)["problem"]


def test_ss_tolerance_boundary():
    g = [("Ta", (0, 0, 0)), ("O", (O1, 0, 0)), ("O", (0, O1, 0))]
    near = single("O", O1 + mb.SS_TOL - 1e-6, "dr1", "ss1")
    far = single("O", O1 + mb.SS_TOL + 1e-3, "dr1", "ss1")
    assert run([near, ms(g, 3.4)])["deltar"] == "1.707*dr1"
    assert run([far, ms(g, 3.4)])["problem"]


def test_constants_fixed():
    assert (mb.SS_TOL, mb.BOND_TOL, mb.COLLINEAR_DEG) == (0.05, 0.05, 5.0)


def test_collinear_angle_threshold():
    """A 处夹角 4° 仍按共线（规则 2），6° 走规则 4。"""
    def trial(deg):
        a = math.radians(deg)
        g = [("Ta", (0, 0, 0)), ("O", (0, 0, O1)), ("O", (O1 * math.sin(a), 0, O1 * math.cos(a)))]
        return run(KT + [ms(g, 2 * O1)])
    s4, s6 = trial(4.0), trial(6.0)
    assert s4["exact"] and not s6["exact"]


def test_temperature_model_same_call():
    call = "sigma2_debye(tempK, thD)"
    rows = [single("O", O1, "dr1", call), single("Ta", TA1, "2*dr1", call)]
    g = [("Ta", (0, 0, 0)), ("O", (O1, 0, 0)), ("O", (0, O1, 0))]
    s = run(rows + [ms(g, 3.4)])
    assert s["deltar"] == "1.707*dr1" and s["sigma2"] == call and not s["sigma2_problem"]


def test_temperature_model_different_theta_or_mixed():
    # 同时用 O 与 Ta 两根键的三角路径
    g = [("Ta", (0, 0, 0)), ("O", (O1, 0, 0)), ("Ta", (0, TA1, 0))]
    rows = [single("O", O1, "dr1", "sigma2_debye(tempK, thA)"), single("Ta", TA1, "2*dr1", "sigma2_debye(tempK, thB)")]
    s = run(rows + [ms(g, 5.0)])
    assert s["deltar"] and s["sigma2"] is None and "温度模型" in s["sigma2_problem"]
    rows2 = [single("O", O1, "dr1", "sigma2_debye(tempK, thA)"), single("Ta", TA1, "2*dr1", "ssT")]
    assert run(rows2 + [ms(g, 5.0)])["sigma2"] is None


def test_einstein_warning_in_basis():
    call = "sigma2_eins(tempK, thE)"
    rows = [single("O", O1, "dr1", call), single("Ta", TA1, "2*dr1", call)]
    g = [("Ta", (0, 0, 0)), ("O", (O1, 0, 0)), ("O", (0, O1, 0))]
    assert "sigma2_eins" in run(rows + [ms(g, 3.4)])["basis_sigma2"]


def test_no_change_to_inputs_and_filters():
    g = [("Ta", (0, 0, 0)), ("O", (O1, 0, 0)), ("O", (0, O1, 0))]
    rows = KT + [ms(g, 3.4), dict(ms(g, 3.4), use=False)]
    before = [dict(r) for r in rows]
    out = mb.suggest(rows, ".")
    assert rows == before and [o["index"] for o in out] == [2]        # 只给已勾选的 nleg > 2 行


def test_combine_format():
    assert mb._combine([(1.0, "dr1")]) == "dr1"
    assert mb._combine([(1.0, "2*dr1")]) == "2*dr1"
    assert mb._combine([(1.0, "a+b"), (0.5, "c")]) == "(a+b) + 0.5*c"
    assert mb._combine([(2.0, "a+b")]) == "2*(a+b)"
    assert mb._combine([(1.0, "a"), (-0.5, "b")]) == "a - 0.5*b"
    assert mb._combine([(5e-5, "a"), (1.0, "b")]) == "b"
    assert mb._combine([(1.70711, "dr1")]) == "1.707*dr1"


def test_equivalent():
    assert mb.equivalent("dr1 + dr3/2", "dr1 + 0.5*dr3")
    assert mb.equivalent("2*dr1", "dr1*2")
    assert not mb.equivalent("ss1 + ss2/2", "0.5*ss1 + 0.25*ss2")
    assert mb.equivalent(" ssT", "ssT")


def test_path_atoms_reads_feff():
    from pathlib import Path
    cu = Path(__file__).resolve().parents[1] / "data" / "benchmark" / "feffcu01.dat"
    g = mb.path_atoms(cu, root="")
    assert g[0][0] == "Cu" and len(g) == 2 and abs(math.dist(g[0][1], g[1][1]) - 2.5527) < 0.01
