"""readers.load_plugins：entry point 组 xafsmith.readers 的加载与跳过。"""
import importlib.metadata
import logging

import pytest

from xafsmith import readers
from xafsmith.readers.base import Reader

BUILTIN = ["bsrf", "xdi", "athena_xmu", "xdac", "prj", "columns"]   # 32f8eb7 时的内置顺序


class _Plugin(Reader):
    name = "plugin_demo"
    label = ("插件演示", "Plugin demo")


class _Dup(Reader):
    name = "xdi"


class _FakeEP:
    def __init__(self, name, obj=None, exc=None):
        self.name, self._obj, self._exc = name, obj, exc

    def load(self):
        if self._exc:
            raise self._exc
        return self._obj


@pytest.fixture
def clean_registry():
    reg, by = list(readers.REGISTRY), dict(readers.BY_NAME)
    yield
    readers.REGISTRY[:] = reg
    readers.BY_NAME.clear()
    readers.BY_NAME.update(by)


def _patch(monkeypatch, eps):
    def fake(**kw):
        assert kw == {"group": "xafsmith.readers"}
        return eps
    monkeypatch.setattr(importlib.metadata, "entry_points", fake)


def test_builtin_registry_unchanged():
    # 无插件时 REGISTRY 与改前相同（按 name 与顺序）
    assert [r.name for r in readers.REGISTRY] == BUILTIN
    assert list(readers.BY_NAME) == BUILTIN


def test_plugin_class_and_instance_added(monkeypatch, clean_registry):
    n0 = len(readers.REGISTRY)
    first = [r.name for r in readers.REGISTRY]
    _patch(monkeypatch, [_FakeEP("a", _Plugin)])
    assert readers.load_plugins() == ["plugin_demo"]
    assert [r.name for r in readers.REGISTRY][:n0] == first          # 追加在内置之后
    assert readers.REGISTRY[-1].name == "plugin_demo"
    assert readers.BY_NAME["plugin_demo"] is readers.REGISTRY[-1]
    assert ("plugin_demo", "插件演示", "Plugin demo") in readers.list_formats()


def test_plugin_instance(monkeypatch, clean_registry):
    class Inst(_Plugin):
        name = "inst_demo"
    _patch(monkeypatch, [_FakeEP("b", Inst())])
    assert readers.load_plugins() == ["inst_demo"]


def test_bad_plugins_skipped(monkeypatch, clean_registry, caplog):
    before = [r.name for r in readers.REGISTRY]
    eps = [_FakeEP("dup", _Dup), _FakeEP("notreader", object()), _FakeEP("notreader2", int),
           _FakeEP("boom", exc=RuntimeError("x")), _FakeEP("imp", exc=ImportError("y"))]
    _patch(monkeypatch, eps)
    readers.logs.log.propagate = True
    try:
        with caplog.at_level(logging.WARNING, logger="xafsmith"):
            assert readers.load_plugins() == []
    finally:
        readers.logs.log.propagate = False
    assert [r.name for r in readers.REGISTRY] == before
    text = caplog.text
    for n in ("dup", "notreader", "notreader2", "boom", "imp"):          # 每个坏插件都记了一条（中英同条）
        assert f"'{n}'" in text


def test_entry_points_failure_ignored(monkeypatch, clean_registry):
    def boom(**kw):
        raise OSError("no metadata")
    monkeypatch.setattr(importlib.metadata, "entry_points", boom)
    assert readers.load_plugins() == []
