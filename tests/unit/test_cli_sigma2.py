"""B6 ⑥：xafsmith sigma2（只打印；不需要项目目录）。"""
import os
import subprocess
import sys
from pathlib import Path

import pytest

from xafsmith import sigma2 as s2

FEFF = Path(__file__).resolve().parents[1] / "data" / "benchmark" / "feffcu01.dat"


def _run(tmp_path, *args):
    env = dict(os.environ, PYTHONIOENCODING="utf-8")
    env.pop("XAFSMITH_PROJECT", None)
    return subprocess.run([sys.executable, "-m", "xafsmith.cli", "sigma2", str(FEFF), *args], cwd=tmp_path,
                          capture_output=True, text=True, encoding="utf-8", env=env)


def test_parse_temps():
    assert s2.parse_temps("10,100, 300") == [10.0, 100.0, 300.0]
    assert s2.parse_temps(trange="10:50:20") == [10.0, 30.0, 50.0]
    assert s2.parse_temps(trange="10:300:10")[-1] == 300.0 and len(s2.parse_temps(trange="10:300:10")) == 30
    for bad in (dict(), dict(temps="a,b"), dict(temps="0,5"), dict(trange="5:1:1"), dict(trange="1:5:0"), dict(trange="x")):
        with pytest.raises(ValueError):
            s2.parse_temps(**bad)


def test_cli_table_matches_function(tmp_path):
    r = _run(tmp_path, "--model", "debye", "--theta", "300", "--temps", "10,300", "--static", "0.001")
    assert r.returncode == 0, r.stderr
    rows = [ln.split("\t") for ln in r.stdout.splitlines() if ln and ln[0].isdigit()]
    ref = s2.sigma2_curve(FEFF, "debye", 300.0, [10, 300], static=0.001)
    assert [float(x[0]) for x in rows] == [10.0, 300.0]
    assert [float(x[1]) for x in rows] == pytest.approx([round(v, 8) for v in ref], abs=1e-12)
    assert list(tmp_path.iterdir()) == []                       # 只打印，不写文件


def test_cli_from_sigma2_roundtrip(tmp_path):
    v = float(s2.sigma2_curve(FEFF, "einstein", 280.0, [150.0])[0])
    r = _run(tmp_path, "--model", "einstein", "--from-sigma2", repr(v), "--T", "150")
    assert r.returncode == 0, r.stderr
    th = float(r.stdout.split("θ =")[1].split("K")[0])
    assert abs(th - 280.0) < 1e-3


def test_cli_errors(tmp_path):
    assert _run(tmp_path, "--model", "debye", "--theta", "300").returncode != 0              # 没给温度
    assert _run(tmp_path, "--model", "debye", "--temps", "100").returncode != 0              # 没给 theta
    assert _run(tmp_path, "--model", "debye", "--from-sigma2", "0.004").returncode != 0      # 缺 --T
    assert _run(tmp_path, "--model", "debye", "--from-sigma2", "100", "--T", "300").returncode != 0   # 无解
