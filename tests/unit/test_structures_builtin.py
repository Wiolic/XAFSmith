"""G2：新增内置结构（fcc 金属、bcc Fe、NiO）的最近邻距离与配位数，以及 builtin_for。"""
import math

import pytest

from xafsmith import structures as st


def _first_shell(name, absorber):
    s = st.builtin(name)
    i = next(k for k, site in enumerate(s) if site.specie.symbol == absorber)
    nn = sorted(s.get_neighbors(s[i], 4.0), key=lambda n: n.nn_distance)
    r0 = nn[0].nn_distance
    n = sum(1 for x in nn if abs(x.nn_distance - r0) < 1e-4)
    return r0, n


@pytest.mark.parametrize("name,a", [("Cu", 3.6149), ("Ni", 3.5240), ("Pd", 3.8907), ("Ag", 4.0862), ("Pt", 3.9242), ("Au", 4.0782)])
def test_fcc(name, a):
    r, n = _first_shell(name, name)
    assert r == pytest.approx(a / math.sqrt(2), abs=1e-6) and n == 12


def test_bcc_fe():
    r, n = _first_shell("Fe", "Fe")
    assert r == pytest.approx(2.8665 * math.sqrt(3) / 2, abs=1e-6) and n == 8


def test_nio():
    r, n = _first_shell("NiO", "Ni")
    assert r == pytest.approx(4.1771 / 2, abs=1e-6) and n == 6


def test_sources_and_builtin_for():
    for n in ("Cu", "Ni", "Pd", "Ag", "Pt", "Au", "Fe", "NiO"):
        assert n in st.SOURCES and n in st.BUILTIN_NAMES and "Wyckoff 1963" in st.SOURCES[n]
    assert st.builtin_for("Ni") == ["Ni", "NiO"]
    assert st.builtin_for("Ir") == ["Ir", "IrO2"]
    assert "KTaO3" in st.builtin_for("Ta") and "Ta" in st.builtin_for("Ta")
    assert st.builtin_for("Xe") == []
