"""独立安装包（sys.frozen）的更新检查：改查 GitHub Release，不走 pip。"""
import sys

from xafsmith import update as xup


def test_frozen_uses_release_and_cannot_self_update(monkeypatch):
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(xup, "latest_release", lambda timeout=4.0: "9.9.9")
    u = xup.check()
    assert u["latest"] == "9.9.9" and u["newer"] is True
    ok, msg = xup.upgrade()
    assert not ok and xup.RELEASES_PAGE in msg


def test_not_frozen_keeps_pip_route(monkeypatch):
    monkeypatch.delattr(sys, "frozen", raising=False)
    assert not xup.is_frozen()


def test_frozen_is_never_editable(monkeypatch):
    """打包时构建环境是 pip install -e；即便 dist-info 标记为 editable，安装包也不能提示 git pull。"""
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    assert xup.is_editable() is False
    monkeypatch.setattr(xup, "latest_release", lambda timeout=4.0: "9.9.9")
    assert xup.check()["editable"] is False
