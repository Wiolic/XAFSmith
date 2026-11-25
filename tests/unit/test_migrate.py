"""配置版本迁移（E12）：只在内存升级，不写回文件。"""
import json
import os

import pytest

from xafsmith import migrate, paths


def _cfg(schema="1.0"):
    return {"xafsmith": {"schema": schema}, "edges": {"Ir_L3": {"element": "Ir"}}, "extra": [1, 2]}


def test_1_0_to_current():
    old = _cfg("1.0")
    new, notes = migrate.upgrade(old)
    assert new["xafsmith"]["schema"] == paths.SCHEMA_VERSION == "1.1"
    assert new["edges"] == old["edges"] and new["extra"] == [1, 2]
    assert old["xafsmith"]["schema"] == "1.0"          # 传入对象不被改
    assert len(notes) == 1 and "1.0" in notes[0][0] and "1.1" in notes[0][1]


def test_missing_schema_is_1_0():
    new, notes = migrate.upgrade({"edges": {}})
    assert new == {"edges": {}, "xafsmith": {"schema": "1.1"}}
    assert len(notes) == 2


def test_current_unchanged():
    cfg = _cfg(paths.SCHEMA_VERSION)
    new, notes = migrate.upgrade(cfg)
    assert new == cfg and new is not cfg and notes == []


def test_newer_raises():
    with pytest.raises(ValueError, match="newer"):
        migrate.upgrade(_cfg("1.2"))
    with pytest.raises(ValueError, match="升级软件"):
        migrate.upgrade(_cfg("2.0"))


def test_version_compare_is_numeric():
    assert migrate.parse_version("1.10") > migrate.parse_version("1.9")
    with pytest.raises(ValueError):
        migrate.upgrade(_cfg("1.10"))


@pytest.mark.parametrize("bad", ["abc", "1.x", "", "1..1", "-1.0", "1.1.", [1]])
def test_bad_version_raises(bad):
    with pytest.raises(ValueError):
        migrate.upgrade(_cfg(bad))


def test_load_config_does_not_write_back(tmp_path):
    from xafsmith import pipeline as pl
    f = tmp_path / "xafsmith.json"
    f.write_text(json.dumps(_cfg("1.0"), indent=2), encoding="utf-8")
    os.utime(f, (1_000_000_000, 1_000_000_000))
    before, st = f.read_bytes(), f.stat().st_mtime_ns
    cfg = pl.load_config(f)
    assert cfg["xafsmith"]["schema"] == "1.1"
    assert f.read_bytes() == before and f.stat().st_mtime_ns == st
    assert migrate.take_pending(f) and not migrate.take_pending(f)


def test_load_config_newer_raises(tmp_path):
    from xafsmith import pipeline as pl
    f = tmp_path / "xafsmith.json"
    f.write_text(json.dumps(_cfg("9.0")), encoding="utf-8")
    with pytest.raises(ValueError):
        pl.load_config(f)


def test_check_config_newer_is_error():
    from xafsmith import schema
    rep = schema.Report()
    schema.check_config(rep, _cfg("1.2"))
    assert any(lv == "错误" and "1.2" in m for lv, _w, m in rep.items)
    rep = schema.Report()
    schema.check_config(rep, _cfg("1.0"))
    assert not [i for i in rep.items if i[0] == "错误" and "schema" in i[2]]


def test_model_schema_field_newer_warns():
    from xafsmith import schema
    rep = schema.Report()
    schema._check_model_schema(rep, "models/a.json", {"schema": "9.0"})
    assert [lv for lv, *_ in rep.items] == ["警告"]
    rep = schema.Report()
    schema._check_model_schema(rep, "models/a.json", {"schema": "1.1"})
    schema._check_model_schema(rep, "models/a.json", {})
    assert rep.items == []


def test_write_params_versions(tmp_path):
    from xafsmith import __version__, common
    p = common.write_params(tmp_path / "x.params.json", {"a": 1}, "t")
    d = json.loads(p.read_text(encoding="utf-8"))
    assert d["xafsmith_version"] == __version__ and d["schema_version"] == paths.SCHEMA_VERSION
    assert d["params"] == {"a": 1}


def test_check_config_rejects_unparseable_version():
    """validate 与读入一致：无法识别的版本串在 check_config 也是错误（读入时 upgrade 会拒绝）。"""
    from xafsmith import schema
    rep = schema.Report()
    schema.check_config(rep, {"xafsmith": {"schema": "abc"}, "edges": {}})
    assert any(lv == "错误" and "无法识别" in m for lv, _w, m in rep.items)
