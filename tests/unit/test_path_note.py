"""B5：路径可选字段 note —— schema 接受（非字符串报错）、build_paths 忽略、计算结果不变。"""
import json
import shutil
from pathlib import Path

import pytest

from xafsmith import fit_exafs as fx, paths, schema

TESTS = Path(__file__).resolve().parents[1]
CU = str(TESTS / "data" / "benchmark" / "feffcu01.dat")
PATH = dict(file=CU, label="Cu", s02="s02", e0="e0", deltar="dr", sigma2="ss")
MODEL = dict(name="n1", sample="cu_metal_rt", kmin=3, kmax=12, rmin=1, rmax=3, params={"s02": 0.8, "e0": 0, "dr": 0, "ss": 0.004},
             paths=[PATH])


def test_build_paths_ignores_note():
    a = fx.build_paths(MODEL)["p1"]
    b = fx.build_paths(dict(MODEL, paths=[dict(PATH, note="msbind: ΔR 共线（精确）")]))["p1"]
    for k in ("s02", "e0", "deltar", "sigma2", "degen", "label"):
        assert getattr(a, k) == getattr(b, k)


@pytest.fixture
def proj(tmp_path):
    dst = tmp_path / "p"
    shutil.copytree(TESTS / "data" / "demo_project", dst, ignore=shutil.ignore_patterns("output"))
    old = paths.ROOT
    paths.set_root(dst)
    yield dst
    paths.set_root(old)


def test_schema_note_must_be_string(proj):
    (proj / "models").mkdir(exist_ok=True)
    (proj / "models" / "ok.json").write_text(json.dumps(dict(MODEL, name="ok", paths=[dict(PATH, note="x")])), encoding="utf-8")
    (proj / "models" / "bad.json").write_text(json.dumps(dict(MODEL, name="bad", paths=[dict(PATH, note=3)])), encoding="utf-8")
    rep = schema.validate(structures=False)
    msgs = [f"{a} {b} {c}" for a, b, c in rep.items]
    assert any("paths[0].note" in m for m in msgs)
    assert not any("ok" in m and "note" in m for m in msgs)
