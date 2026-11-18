"""S0² 标样来源候选（s02_source.py）：临时项目造 meta.csv / exafs_fits.csv / models，不碰真实项目。"""
import json
import os
import time

import pandas as pd

from xafsmith import s02_source as src

META = """file,sample,edge_key,mode,role,use
d/IrO2,IrO2,Ir_L3,trans,standard,1
d/IrCl3,IrCl3,Ir_L3,trans,standard,1
d/CoO,CoO,Co_K,trans,standard,1
d/IrCo,IrCo,Ir_L3,fluo,sample,1
d/IrCo2,IrCo,Co_K,fluo,sample,1
"""


def params(s02, err):
    return json.dumps({"s02": [s02, err], "e0": [8.9, 0.5]})


def row(model, sample, s02, err, rf=0.02, path="Ir-O(6)", ds=None):
    return dict(sample=sample, model=model, path=path, S02=s02, rfactor=rf, params=params(s02, err), dataset=ds or "")


def project(tmp_path, rows, models=None):
    (tmp_path / "data").mkdir()
    (tmp_path / "data" / "meta.csv").write_text(META, encoding="utf-8")
    (tmp_path / "output" / "fits").mkdir(parents=True)
    pd.DataFrame(rows).to_csv(tmp_path / "output" / "fits" / "exafs_fits.csv", index=False, encoding="utf-8-sig")
    (tmp_path / "models").mkdir()
    for name, md in (models or {}).items():
        (tmp_path / "models" / f"{name}.json").write_text(json.dumps(md), encoding="utf-8")
    return tmp_path


def session_fit(model, sample, vary=True, expr=None, stderr=0.05, multi=False):
    summ = dict(model=model, sample=sample, rfactor=0.03, params={"s02": dict(value=0.8, vary=vary, expr=expr, stderr=stderr)})
    if multi:
        summ.update(multi=True, datasets=[dict(id=s, sample=s) for s in sample.split("+")])
    return dict(model=model, summ=summ, time="2026-11-18T10:00:00")


def test_saved_same_edge_only(tmp_path):
    root = project(tmp_path, [row("A", "IrO2", 0.8, 0.05), row("B", "CoO", 0.9, 0.04), row("C", "NoMeta", 0.9, 0.04)])
    c = src.list_candidates("Ir_L3", root=root)
    assert [(x.model, x.value, x.stderr, x.origin) for x in c] == [("A", 0.8, 0.05, "saved")]
    assert [x.model for x in src.list_candidates("Co_K", root=root)] == ["B"]


def test_saved_requires_fitted_s02(tmp_path):
    rows = [row("fixed", "IrO2", 0.8, None), row("noerr", "IrO2", 0.8, "null"), row("expr", "IrO2", 0.8, 0.05),
            row("ok", "IrO2", 0.81, 0.05)]
    rows[0]["params"] = json.dumps({"s02": [0.8, None]})
    rows[1]["params"] = json.dumps({"s02": [0.8, None]})
    models = {"expr": {"params": {"s02": {"expr": "0.8*x"}}}, "ok": {"params": {"s02": {"value": 0.8, "vary": True}}}}
    root = project(tmp_path, rows, models)
    assert [x.model for x in src.list_candidates("Ir_L3", root=root)] == ["ok"]


def test_saved_json_says_fixed(tmp_path):
    root = project(tmp_path, [row("A", "IrO2", 0.8, 0.05)], {"A": {"params": {"s02": {"value": 0.8, "vary": False}}}})
    assert src.list_candidates("Ir_L3", root=root) == []


def test_resaved_model_uses_last_and_time_from_model_file(tmp_path):
    root = project(tmp_path, [row("A", "IrO2", 0.70, 0.05), row("A", "IrO2", 0.82, 0.06, rf=0.01)],
                   {"A": {"params": {"s02": {"value": 0.8, "vary": True}}}})
    os.utime(root / "models" / "A.json", (1_700_000_000, 1_700_000_000))
    (c,) = src.list_candidates("Ir_L3", root=root)
    assert (c.value, c.stderr, c.rfactor) == (0.82, 0.06, 0.01)
    assert c.time == time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(1_700_000_000))


def test_multi_dataset_all_samples_must_match_edge(tmp_path):
    rows = [row("J", "IrO2", 0.8, 0.05, ds="a"), row("J", "IrCl3", 0.8, 0.05, ds="b"),
            row("K", "IrO2", 0.8, 0.05, ds="a"), row("K", "CoO", 0.8, 0.05, ds="b")]
    root = project(tmp_path, rows)
    (c,) = src.list_candidates("Ir_L3", root=root)
    assert c.model == "J" and c.samples == ("IrO2", "IrCl3") and c.sample_text == "IrO2 + IrCl3"


def test_sample_on_two_edges_is_not_guessed(tmp_path):
    root = project(tmp_path, [row("A", "IrCo", 0.8, 0.05)])
    assert src.list_candidates("Ir_L3", root=root) == [] and src.list_candidates("Co_K", root=root) == []


def test_session_fits_and_dedup(tmp_path):
    root = project(tmp_path, [row("A", "IrO2", 0.8, 0.05)])
    fits = [session_fit("A", "IrO2", stderr=0.05), session_fit("S_fixed", "IrO2", vary=False), session_fit("S_expr", "IrO2", expr="x"),
            session_fit("S_noerr", "IrO2", stderr=None), session_fit("S_co", "CoO"), session_fit("S_multi", "IrO2+IrCl3", multi=True)]
    c = src.list_candidates("Ir_L3", fits, root=root)
    assert sorted((x.model, x.origin) for x in c) == [("A", "session"), ("S_multi", "session")]   # A 的已保存版本同值，只留会话的
    assert c[0].source() == {"model": c[0].model, "value": 0.8, "stderr": 0.05}


def test_no_files_gives_empty(tmp_path):
    assert src.list_candidates("Ir_L3", root=tmp_path) == []
    (tmp_path / "data").mkdir()
    (tmp_path / "data" / "meta.csv").write_text(META, encoding="utf-8")
    assert src.list_candidates("Ir_L3", root=tmp_path) == []
    assert src.edge_of_samples(["IrO2", "IrCl3"], root=tmp_path) == "Ir_L3"
    assert src.edge_of_samples(["IrO2", "CoO"], root=tmp_path) is None
    assert src.edge_of_samples(["IrCo"], root=tmp_path) is None
