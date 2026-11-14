"""Release 说明取自 CHANGELOG：当前版本必须已有一节（发布前写好），取节边界正确。"""
import importlib.util
from pathlib import Path

import xafsmith

_p = Path(__file__).resolve().parents[2] / "tools" / "release_notes.py"
_spec = importlib.util.spec_from_file_location("release_notes", _p)
rn = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(rn)

TXT = """# Changelog

## [Unreleased]
- x

## [2.0.0] — 2026-01-02
### Fixed
- a

## [1.9.0] — 2026-01-01
- b
"""


def test_section_bounds():
    assert rn.section("2.0.0", TXT) == "### Fixed\n- a"
    assert rn.section("v1.9.0", TXT) == "- b"
    assert rn.section("3.0.0", TXT) is None
    assert rn.previous("2.0.0", TXT) == "1.9.0" and rn.previous("1.9.0", TXT) is None


def test_notes_links():
    n = rn.notes("2.0.0", TXT, has_tag=lambda t: True)
    assert n.startswith("### Fixed\n- a") and "compare/v1.9.0...v2.0.0" in n and "blob/v2.0.0/CHANGELOG.md" in n
    assert "compare/" not in rn.notes("2.0.0", TXT, has_tag=lambda t: False)     # 上一版没有 tag：不给坏链接


def test_current_version_has_changelog_section():
    assert rn.section(xafsmith.__version__), f"CHANGELOG.md 缺少 [{xafsmith.__version__}] 一节"
