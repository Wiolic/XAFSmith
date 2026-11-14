"""黄金基线回归（E1）：演示项目全流程 + Cu 拟合 + Fe LCF 的数值与 tests/golden/demo.json 逐列比对（rtol 1e-9）。

基线由 `python tools/golden.py demo --write` 生成。数值有意改动时才重写，并在提交信息里说明原因。
运行：python -m pytest tests/benchmark/test_golden.py -q
"""
import importlib.util
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
GOLDEN = ROOT / "tests" / "golden" / "demo.json"


@pytest.fixture(scope="module")
def golden_tool():
    spec = importlib.util.spec_from_file_location("golden_tool", ROOT / "tools" / "golden.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules["golden_tool"] = mod
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def new_snapshot(golden_tool, tmp_path_factory):
    snap = golden_tool.run_demo(tmp_path_factory.mktemp("golden"))
    return json.loads(json.dumps(snap))


def test_matches_golden(golden_tool, new_snapshot):
    gold = json.loads(GOLDEN.read_text(encoding="utf-8"))
    diffs = golden_tool.compare(new_snapshot, gold, rtol=1e-9)
    assert not diffs, f"{len(diffs)} 项与黄金基线不一致（前 30 条）：\n" + "\n".join(diffs[:30])


def test_snapshot_keys_match_golden(new_snapshot):
    """防止改了 snapshot 的结构却忘了重生成 demo.json。"""
    gold = json.loads(GOLDEN.read_text(encoding="utf-8"))

    def keys(d, p=""):
        out = set()
        if isinstance(d, dict):
            for k, v in d.items():
                out.add(p + "/" + k)
                out |= keys(v, p + "/" + k)
        return out
    assert keys(new_snapshot) == keys(gold)


def test_compare_detects_perturbation(golden_tool):
    """比较器自检：改动一个 χ 值 1e-6（相对列尺度）必须被发现，1e-12 不应报错。"""
    gold = json.loads(GOLDEN.read_text(encoding="utf-8"))
    import copy
    new = copy.deepcopy(gold)
    col = new["processed"]["cu_metal_rt.chik"]["chi"]
    scale = max(abs(v) for v in col if v is not None)
    col[10] += 1e-6 * scale
    assert golden_tool.compare(new, gold, 1e-9)
    new = copy.deepcopy(gold)
    new["processed"]["cu_metal_rt.chik"]["chi"][10] += 1e-12 * scale
    assert not golden_tool.compare(new, gold, 1e-9)
