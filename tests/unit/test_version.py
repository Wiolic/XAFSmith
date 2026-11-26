"""版本号单一来源：唯一来源是 xafsmith.__version__；pyproject 动态读取它；CITATION.cff（手写）必须与之相同。"""
import re
import tomllib
from pathlib import Path

import xafsmith

ROOT = Path(__file__).resolve().parents[2]


def _pyproject():
    return tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))


def test_pyproject_reads_version_from_package():
    d = _pyproject()
    assert "version" in d["project"].get("dynamic", [])
    assert "version" not in d["project"]
    assert d["tool"]["setuptools"]["dynamic"]["version"] == {"attr": "xafsmith.__version__"}


def test_citation_matches_package_version():
    cff = re.search(r"^version:\s*['\"]?([^\s'\"]+)", (ROOT / "CITATION.cff").read_text(encoding="utf-8"), re.M).group(1)
    assert xafsmith.__version__ == cff, (xafsmith.__version__, cff)


def test_version_format():
    assert re.fullmatch(r"\d+\.\d+\.\d+", xafsmith.__version__), xafsmith.__version__
