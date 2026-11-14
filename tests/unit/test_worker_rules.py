"""E5：后台线程规则。拟合页的三个后台任务（已保存模型、自定义拟合、稳健性）：
闭包里不得有 Qt 对象，也不得持有与 S.groups 同一个（is）的谱对象。离屏 Qt；用小型假 State，不需要项目。"""
import types

import pytest

pytest.importorskip("PySide6")
from PySide6.QtCore import QObject

from xafsmith import paths
from xafsmith.qt.pages.fitting import fit_page as fp, fit_view as fv


class Grp:
    def __init__(self, name):
        self.name = name
        self.k = [1.0, 2.0]


def _S():
    return types.SimpleNamespace(groups={"a": Grp("a"), "b": Grp("b")})


def _reach(obj, seen=None, depth=0):
    """闭包（含其直接捕获的函数、容器、对象属性）里可达的全部对象"""
    seen = {} if seen is None else seen
    if id(obj) in seen or depth > 6:
        return seen
    seen[id(obj)] = obj
    kids = []
    if isinstance(obj, types.FunctionType) and obj.__closure__:
        kids += [c.cell_contents for c in obj.__closure__ if _filled(c)]
    if isinstance(obj, dict):
        kids += list(obj.values())
    elif isinstance(obj, (list, tuple, set)):
        kids += list(obj)
    elif hasattr(obj, "__dict__") and not isinstance(obj, type) and not callable(obj) and not isinstance(obj, types.ModuleType):
        kids += list(vars(obj).values())
    for k in kids:
        _reach(k, seen, depth + 1)
    return seen


def _filled(c):
    try:
        c.cell_contents
        return True
    except ValueError:
        return False


def _check(work, S):
    objs = list(_reach(work).values())
    assert not [o for o in objs if isinstance(o, QObject)], "后台任务的闭包里有 Qt 对象"
    live = {id(g) for g in S.groups.values()}
    assert not [o for o in objs if id(o) in live], "后台任务持有会话里活的谱对象"
    return objs


def test_saved_model_job(tmp_path, monkeypatch):
    (tmp_path / "m.json").write_text('{"name": "m", "sample": "a"}', encoding="utf-8")
    monkeypatch.setattr(paths, "MODELS", tmp_path)
    S = _S()
    work = fp.saved_model_job(S, "m.json", [None, "b"])
    objs = _check(work, S)
    copies = [o for o in objs if isinstance(o, Grp)]
    assert {g.name for g in copies} == {"a", "b"}          # 回退需要的谱已深拷贝


def test_custom_fit_job():
    S = _S()
    for src in ("a", {"d1": "a", "d2": "b"}):
        job = fp.custom_fit_job(S, {"name": "x"}, src)
        objs = _check(job, S)
        assert any(isinstance(o, Grp) for o in objs)


def test_robust_job():
    S = _S()
    work = fv.robust_job(S, {"summ": {"sample": "a"}, "model": {"name": "x"}})
    objs = _check(work, S)
    assert any(isinstance(o, Grp) and o.name == "a" for o in objs)
    none = fv.robust_job(S, {"summ": {"sample": "zz"}, "model": {}})     # 会话里没有 → 后台重建
    _check(none, S)
