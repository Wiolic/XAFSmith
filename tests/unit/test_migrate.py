"""配置版本迁移（E12）：只在内存升级，不写回文件。"""
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
