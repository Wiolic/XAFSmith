"""B5：xafsmith msbind —— 只打印；--out 另存新模型（不覆盖已有、原模型不变）并写 .params.json。手写几何，进程内调用。"""
import argparse
import json

import pytest

from xafsmith import cli, msbind as mb, paths

O1, TA1 = 1.995, 3.99
GEOM = {
    "s_o.dat": (2, O1, [("Ta", (0, 0, 0)), ("O", (0, 0, O1))]),
    "s_ta.dat": (2, TA1, [("Ta", (0, 0, 0)), ("Ta", (0, 0, TA1))]),
    "m.dat": (3, 3.4, [("Ta", (0, 0, 0)), ("O", (O1, 0, 0)), ("O", (0, O1, 0))]),
}
PATHS = [dict(file="x/s_o.dat", label="Ta-O", deltar="dr1", sigma2="ss1", s02="s02", e0="e0"),
         dict(file="x/s_ta.dat", label="Ta-Ta", deltar="2*dr1", sigma2="ssT", s02="s02", e0="e0"),
         dict(file="x/m.dat", label="tri", deltar="dr1", sigma2="ss1", s02="s02", e0="e0")]
MODEL = dict(name="m1", sample="a", kmin=3, kmax=12, rmin=1, rmax=3, params={"s02": 0.8}, paths=PATHS)


@pytest.fixture
def env(tmp_path, monkeypatch):
    monkeypatch.setattr(paths, "MODELS", tmp_path)
    monkeypatch.setattr(mb, "path_info", lambda f, root=None: GEOM[f.split("/")[-1]][:2])
    monkeypatch.setattr(mb, "path_atoms", lambda f, root=None: GEOM[str(f).replace("\\", "/").split("/")[-1]][2])
    (tmp_path / "m1.json").write_text(json.dumps(MODEL), encoding="utf-8")
    return tmp_path


def _args(**kw):
    return argparse.Namespace(**{**dict(model="m1", dataset=None, out=None), **kw})


def test_print_only(env, capsys):
    cli.cmd_msbind(_args())
    out = capsys.readouterr().out
    assert "1.707*dr1" in out and "1.457*ss1" in out
    assert sorted(p.name for p in env.iterdir()) == ["m1.json"]


def test_out_saves_new_model(env, capsys):
    before = (env / "m1.json").read_text(encoding="utf-8")
    cli.cmd_msbind(_args(out="m1_ms"))
    new = json.loads((env / "m1_ms.json").read_text(encoding="utf-8"))
    tri = new["paths"][2]
    assert (tri["deltar"], tri["sigma2"]) == ("1.707*dr1", "1.457*ss1") and tri["note"].startswith("msbind:")
    assert "note" not in new["paths"][0] and new["name"] == "m1_ms"
    assert (env / "m1.json").read_text(encoding="utf-8") == before
    p = json.loads((env / "m1_ms.params.json").read_text(encoding="utf-8"))
    assert p["tool"] == "xafsmith msbind" and p["params"]["SS_TOL"] == 0.05


def test_out_never_overwrites(env):
    (env / "taken.json").write_text("{}", encoding="utf-8")
    with pytest.raises(SystemExit, match="已存在"):
        cli.cmd_msbind(_args(out="taken"))
    assert (env / "taken.json").read_text(encoding="utf-8") == "{}"


def test_unknown_dataset(env):
    with pytest.raises(SystemExit):
        cli.cmd_msbind(_args(dataset="nope"))
