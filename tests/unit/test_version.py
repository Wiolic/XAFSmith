"""版本号一致性：pyproject.toml、xafsmith.__version__、CITATION.cff 三处必须相同。"""
import re
import tomllib
from pathlib import Path

import xafsmith

ROOT = Path(__file__).resolve().parents[2]


def test_versions_agree():
    py = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))["project"]["version"]
    cff = re.search(r"^version:\s*['\"]?([^\s'\"]+)", (ROOT / "CITATION.cff").read_text(encoding="utf-8"), re.M).group(1)
    assert py == xafsmith.__version__ == cff, (py, xafsmith.__version__, cff)
