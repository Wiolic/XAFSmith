"""会话快照：编码往返、草稿读写、不可保存的键被跳过、不开启时不写文件。"""
import json
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest

pytest.importorskip("PySide6")
from xafsmith import paths
from xafsmith.qt import session


class FakePage:
    def __init__(self, state):
        self.state = state


def fake_S():
    return SimpleNamespace(extra={"page": "fit"}, norm_par={"pre1": -150.0}, bkg_par={"rbkg": 1.0}, ft_par={"kmin": 3.0},
                           groups={"IrO2": object(), "Ir_foil": object()})


@pytest.fixture
def proj(tmp_path, monkeypatch):
    (tmp_path / "xafsmith.json").write_text("{}", encoding="utf-8")
    monkeypatch.delenv("XAFSMITH_NO_SESSION", raising=False)
    monkeypatch.delenv("XAFSMITH_NO_RECENT", raising=False)
    monkeypatch.setattr(paths, "ROOT", tmp_path, raising=False)
    monkeypatch.setattr(paths, "GUI", tmp_path / "output" / "gui", raising=False)
    monkeypatch.setattr("xafsmith.update.load_settings", lambda: {})
    return tmp_path


def test_encode_roundtrip():
    df = pd.DataFrame({"name": ["s02", "e0"], "value": [0.8, 1.5], "vary": [True, False], "expr": ["", "a*2"]})
    st = {"partab": df, "dirs": [Path("feff/IrO2")], "n": np.int64(3), "kws": (1, 2, 3), "x": np.array([1.0, 2.0]),
          "range": {"kmin": 3.0, "win": "hanning"}}
    back = session.decode(json.loads(json.dumps(session.encode_state(st))))
    pd.testing.assert_frame_equal(back["partab"], df, check_dtype=False)
    assert back["dirs"] == [{"__path__": "feff/IrO2"}] or back["dirs"] == [Path("feff/IrO2")]
    assert back["n"] == 3 and back["kws"] == [1, 2, 3] and back["x"] == [1.0, 2.0]
    assert back["range"] == {"kmin": 3.0, "win": "hanning"}


def test_unserializable_key_is_skipped():
    out = session.encode_state({"ok": 1, "bad": object(), "split": [1, 2]})
    assert out == {"ok": 1}                       # bad 跳过；split 在不保存名单里


def test_session_roundtrip(proj):
    S = fake_S()
    pages = {"fit": FakePage({"data": "IrO2", "range": {"kmin": 3.2}}), "norm": FakePage({}), "chi": FakePage({"sel": ["IrO2"]})}
    assert session.save_session(S, pages)
    snap = session.load_session()
    assert snap["page"] == "fit" and snap["groups"] == ["IrO2", "Ir_foil"]
    assert "norm" not in snap["pages"]            # 空状态不存
    S2 = fake_S()
    S2.norm_par["pre1"] = 0.0
    p2 = {"fit": FakePage({}), "chi": FakePage({})}
    session.apply_params(S2, snap)
    session.apply_pages(snap, p2)
    assert S2.norm_par["pre1"] == -150.0
    assert p2["fit"].state == {"data": "IrO2", "range": {"kmin": 3.2}} and p2["chi"].state == {"sel": ["IrO2"]}


def test_disabled_does_not_write(proj, monkeypatch):
    monkeypatch.setenv("XAFSMITH_NO_SESSION", "1")
    assert not session.save_session(fake_S(), {"fit": FakePage({"a": 1})})
    assert not session.session_file().exists()


def test_corrupt_or_old_file_is_ignored(proj):
    f = session.session_file()
    f.parent.mkdir(parents=True)
    f.write_text("{ not json", encoding="utf-8")
    assert session.load_session() is None
    f.write_text(json.dumps({"version": 999}), encoding="utf-8")
    assert session.load_session() is None


def test_drafts(proj):
    S = fake_S()
    pages = {"fit": FakePage({"data": "IrO2", "partab": pd.DataFrame({"name": ["ss1"], "value": [0.003]})}),
             "chi": FakePage({"sel": ["x"]})}
    p = session.save_draft("1壳层 / 试一下", S, pages)
    assert p.parent == session.drafts_dir() and p.suffix == ".json" and "/" not in p.name
    lst = session.list_drafts()
    assert [d["name"] for d in lst] == ["1壳层 / 试一下"]
    snap = session.load_draft(lst[0]["file"])
    assert set(snap["pages"]) == {"fit"}          # 草稿只含拟合页
    p2 = {"fit": FakePage({}), "chi": FakePage({})}
    session.apply_pages(snap, p2, only=("fit",))
    assert p2["fit"].state["partab"]["value"].iloc[0] == 0.003 and p2["chi"].state == {}
    session.delete_draft(lst[0]["file"])
    assert session.list_drafts() == []
    # 不在草稿目录里的文件不会被删
    other = proj / "keep.json"
    other.write_text("{}", encoding="utf-8")
    session.delete_draft(other)
    assert other.exists()
