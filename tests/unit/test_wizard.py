"""列映射向导后台：预览、模板生成、试读、保存。合成数据只测规则，不当作测量数据。"""
import numpy as np
import pytest

from xafsmith.readers import ReadError, resolve_format
from xafsmith.readers import wizard as wz


def _file(tmp_path, names, header=True, n=60, e0=8979.0):
    e = np.linspace(e0 - 60, e0 + 200, n)
    mu = 0.3 + 0.8 / (1 + np.exp(-(e - e0) / 2.0))
    i0 = np.full(n, 1e5)
    cols = {"Energy": e, "Mon": i0, "Det": i0 * np.exp(-mu), "Ch1": 1e3 * (1 + mu), "Ch2": 1e3 * (1 + mu)}
    lines = ["# some beamline", "# " + " ".join(names)] if header else ["some beamline"]
    for k in range(n):
        lines.append(" ".join(f"{cols[nm][k]:.8g}" for nm in names))
    p = tmp_path / "scan.dat"
    p.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return p


def test_inspect_gives_names_rows_and_auto_roles(tmp_path):
    p = _file(tmp_path, ["Energy", "Mon", "Det"])
    info = wz.inspect_file(p, nrows=5)
    assert info["names"] == ["Energy", "Mon", "Det"] and info["ncols"] == 3 and info["ntotal"] == 60
    assert len(info["rows"]) == 5
    assert info["auto"].get("energy") == [0] and info["auto"].get("i0") == [1]


def test_template_uses_names_when_unique_else_index(tmp_path):
    t = wz.build_template(["Energy", "Mon", "Det"], {"energy": 0, "i0": 1, "it": 2}, mode="trans")
    assert t == {"base": "columns", "energy": "Energy", "i0": "Mon", "it": "Det", "mode": "trans"}
    dup = wz.build_template(["E", "x", "x"], {"energy": 0, "i0": 1, "it": 2})
    assert dup["i0"] == 1 and dup["it"] == 2                       # 重名的列退回列号
    noname = wz.build_template(None, {"energy": 0, "i0": 1, "if": [3, 4]})
    assert noname["if"] == [3, 4]


def test_template_requires_energy_and_signal():
    with pytest.raises(ReadError):
        wz.build_template(["a", "b"], {"i0": 1, "it": 0})
    with pytest.raises(ReadError):
        wz.build_template(["a", "b"], {"energy": 0})


def test_try_read_with_nonstandard_names(tmp_path):
    p = _file(tmp_path, ["Energy", "Mon", "Det"])
    t = wz.build_template(["Energy", "Mon", "Det"], {"energy": 0, "i0": 1, "it": 2}, mode="trans")
    s = wz.try_read(p, t)
    assert s["mode"] == "trans" and s["npts"] == 60 and abs(s["e_min"] - 8919) < 1 and s["element"] == "Cu"
    assert 0.2 < s["mu_min"] < s["mu_max"] < 1.3                    # ln(I0/It) 算出的 μ


def test_try_read_fluo_sums_channels(tmp_path):
    p = _file(tmp_path, ["Energy", "Mon", "Ch1", "Ch2"])
    t = wz.build_template(["Energy", "Mon", "Ch1", "Ch2"], {"energy": 0, "i0": 1, "if": [2, 3]}, mode="fluo")
    s = wz.try_read(p, t)
    assert s["mode"] == "fluo"
    s1 = wz.try_read(p, wz.build_template(["Energy", "Mon", "Ch1", "Ch2"], {"energy": 0, "i0": 1, "if": 2}, mode="fluo"))
    assert abs(s["mu_max"] / s1["mu_max"] - 2.0) < 1e-6              # 两个通道求和


def test_headerless_file_needs_index_mapping(tmp_path):
    p = _file(tmp_path, ["Energy", "Mon", "Det"], header=False)
    info = wz.inspect_file(p)
    assert info["names"] is None and info["auto"] == {}
    s = wz.try_read(p, wz.build_template(None, {"energy": 0, "i0": 1, "it": 2}, mode="trans"))
    assert s["npts"] == 60


def test_saved_template_is_resolved_by_reader(tmp_path):
    cfg = wz.add_template({"edges": {}}, "MyBL", wz.build_template(["Energy", "Mon", "Det"], {"energy": 0, "i0": 1, "it": 2}, "trans"))
    base, cols, mode = resolve_format("MyBL", cfg["formats"])
    assert base == "columns" and cols["i0"] == "Mon" and mode == "trans"


@pytest.mark.parametrize("bad", ["", "  ", "bsrf", "xdi", "auto", "columns_by_index"])
def test_template_name_rules(bad):
    with pytest.raises(ReadError):
        wz.add_template({}, bad, {"base": "columns", "energy": 0, "i0": 1, "it": 2})
