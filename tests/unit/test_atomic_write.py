"""原子写入（E7）：写到一半失败不动原文件、留 .bak、写前校验配置、字节与旧写法一致。"""
import json
import os

import pandas as pd
import pytest

from xafsmith import common, paths, pipeline as pl


def test_failure_keeps_original(tmp_path, monkeypatch):
    f = tmp_path / "a.json"
    f.write_bytes(b'{"old": 1}')
    monkeypatch.setattr(os, "replace", lambda *a: (_ for _ in ()).throw(OSError("boom")))
    with pytest.raises(OSError):
        common.write_text_atomic(f, '{"new": 2}')
    assert f.read_bytes() == b'{"old": 1}'
    assert not (tmp_path / "a.json.tmp").exists()


def test_exception_inside_block(tmp_path):
    f = tmp_path / "a.csv"
    f.write_bytes(b"x\n")
    with pytest.raises(RuntimeError):
        with common.atomic_path(f) as tmp:
            tmp.write_text("partial")
            raise RuntimeError("crash")
    assert f.read_bytes() == b"x\n" and not (tmp_path / "a.csv.tmp").exists()


def test_success_makes_bak(tmp_path):
    f = tmp_path / "a.json"
    common.write_text_atomic(f, "one")
    assert not (tmp_path / "a.json.bak").exists()      # 首次写入无旧版本
    common.write_text_atomic(f, "two")
    common.write_text_atomic(f, "three")
    assert f.read_text() == "three" and (tmp_path / "a.json.bak").read_text() == "two"
    assert not (tmp_path / "a.json.tmp").exists()


def test_save_config_refuses_errors(tmp_path):
    f = tmp_path / "xafsmith.json"
    good = {"xafsmith": {"schema": paths.SCHEMA_VERSION}, "edges": {}}
    pl.save_config(good, f)
    before = f.read_bytes()
    bad = pl.default_edge_config("Ir", "L3")
    bad["ft"]["window"] = "nonsense"
    with pytest.raises(ValueError, match="window"):
        pl.save_config({"edges": {"Ir_L3": bad}}, f)
    assert f.read_bytes() == before and not (tmp_path / "xafsmith.json.bak").exists()


def test_save_config_warning_not_blocking(tmp_path):
    f = tmp_path / "xafsmith.json"
    pl.save_config({"edges": {}}, f)                  # 缺 schema、edges 为空只是警告
    assert f.exists()


def test_byte_identity_json(tmp_path):
    cfg = {"edges": {}, "中文": "值", "a": [1, 2.5]}
    text = json.dumps(cfg, ensure_ascii=False, indent=2)
    old, new = tmp_path / "old.json", tmp_path / "new.json"
    old.write_text(text, encoding="utf-8")
    common.write_text_atomic(new, text, encoding="utf-8")
    assert old.read_bytes() == new.read_bytes()
    if os.linesep == "\r\n":
        assert b"\r\n" in new.read_bytes()


def test_byte_identity_csv(tmp_path):
    df = pd.DataFrame({"file": ["a.dat"], "note": ["中文；备注"]})
    old, new = tmp_path / "old.csv", tmp_path / "new.csv"
    df.to_csv(old, index=False, encoding="utf-8-sig")
    with common.atomic_path(new) as tmp:
        df.to_csv(tmp, index=False, encoding="utf-8-sig")
    assert old.read_bytes() == new.read_bytes()
    assert new.read_bytes().startswith(b"\xef\xbb\xbf")
