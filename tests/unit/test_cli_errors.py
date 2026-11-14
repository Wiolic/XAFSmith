"""CLI 顶层错误处理：一行错误 + 日志路径、--debug 重新抛出、Ctrl+C 退出码 130。"""
import pytest

from xafsmith import cli


def _boom(exc):
    def f(a):
        raise exc
    return f


def test_error_is_one_line(monkeypatch, capsys, tmp_path):
    monkeypatch.setattr(cli, "cmd_qc", _boom(ValueError("boom")))
    with pytest.raises(SystemExit) as e:
        cli.main(["--project", str(tmp_path), "qc"])
    assert e.value.code == 1
    err = capsys.readouterr().err
    lines = err.strip().splitlines()
    assert lines[0] == "错误 / Error: ValueError: boom"
    assert len(lines) <= 2 and (len(lines) == 1 or lines[1].startswith("日志 / Log: "))
    assert "Traceback" not in err


def test_debug_reraises(monkeypatch, tmp_path):
    monkeypatch.setattr(cli, "cmd_qc", _boom(ValueError("boom")))
    with pytest.raises(ValueError, match="boom"):
        cli.main(["--debug", "--project", str(tmp_path), "qc"])
    with pytest.raises(ValueError, match="boom"):
        cli.main(["--project", str(tmp_path), "qc", "--debug"])


def test_keyboard_interrupt_130(monkeypatch, capsys, tmp_path):
    monkeypatch.setattr(cli, "cmd_qc", _boom(KeyboardInterrupt()))
    with pytest.raises(SystemExit) as e:
        cli.main(["--project", str(tmp_path), "qc"])
    assert e.value.code == 130
    assert "Traceback" not in capsys.readouterr().err


def test_systemexit_passes_through(monkeypatch, tmp_path):
    monkeypatch.setattr(cli, "cmd_qc", _boom(SystemExit(3)))
    with pytest.raises(SystemExit) as e:
        cli.main(["--project", str(tmp_path), "qc"])
    assert e.value.code == 3
