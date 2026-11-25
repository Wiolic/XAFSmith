"""内置结构：手写的 8 个优先；structures_builtin/index.csv（COD）的条目并入 BUILTIN_NAMES / SOURCES / builtin_for。"""
import csv
import re

import pytest

from xafsmith import structures as st

INDEX = list(csv.DictReader(open(st._DIR / "index.csv", encoding="utf-8-sig", newline="")))


def test_hand_written_first_and_unchanged():
    assert st.BUILTIN_NAMES[:8] == ["Ir", "Ta", "Co_hcp", "Co_fcc", "IrO2", "CoO", "Co3O4", "KTaO3"]
    assert "Wyckoff" in st.SOURCES["Ir"] and abs(st.builtin("Ir").lattice.a - 3.8390) < 1e-6


def test_index_merged():
    assert len(INDEX) >= 55
    for r in INDEX:
        n = r["name"]
        assert n in st.BUILTIN_NAMES
        assert st.SOURCES[n] == f"{r['phase']} {r['space_group']}, COD {r['cod_id']}: {r['reference']}"
        assert (st._DIR / f"{n}.cif").is_file()


@pytest.mark.parametrize("r", INDEX, ids=[r["name"] for r in INDEX])
def test_entry_matches_index(r):
    s = st.builtin(r["name"])
    assert s.is_ordered
    assert s.get_space_group_info(symprec=1e-2)[0].replace(" ", "") == r["space_group"].replace(" ", ""), s.get_space_group_info()
    m = re.match(r"(\w+)-(\w+) x(\d+) ([\d.]+)", r["first_shell"])
    ab, _sc, n, d = m.group(1), m.group(2), int(m.group(3)), float(m.group(4))
    assert ab in r["absorbers"].split()
    i = next(k for k, x in enumerate(s) if x.specie.symbol == ab)
    nn = sorted(s.get_neighbors(s[i], 4.5), key=lambda x: x.nn_distance)
    assert nn[0].nn_distance == pytest.approx(d, abs=0.005)
    sc = nn[0].specie.symbol                         # 同元素、距离与最近一条相差 < 0.1 Å 的算同一壳层
    assert sum(1 for x in nn if x.specie.symbol == sc and x.nn_distance - nn[0].nn_distance < 0.1) == n


def test_builtin_for():
    assert {"Fe", "Fe2O3", "Fe3O4", "FeO", "FeS2", "LiFePO4", "ZnFe2O4"} <= set(st.builtin_for("Fe"))
    assert "Ir" in st.builtin_for("Ir") and "IrO2" in st.builtin_for("Ir")
    assert "KTaO3" in st.builtin_for("Ta") and "Ta" in st.builtin_for("Ta")
    assert st.builtin_for("Xe") == []


def test_export_covers_new_entries(tmp_path):
    files = st.export_builtin(tmp_path)
    assert {f.stem for f in files} == set(st.BUILTIN_NAMES)
