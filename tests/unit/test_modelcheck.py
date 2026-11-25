"""E11：模型结构检查单一实现（modelcheck）的对照测试。

对每个人造模型（每条结构规则至少一个），记录两件事：
  validate 的模型条目（schema.check_models：级别、位置、消息，保持顺序），
  fit_exafs.normalize_model 是否抛错及消息（或成功时规范化结果的 JSON）。
基线 modelcheck_baseline.json 在改代码之前由当时的实现生成；改代码后必须逐条相同。
重写基线（只在行为有意改变时）：python tests/unit/test_modelcheck.py --write
"""
import copy
import json
import shutil
import sys
from pathlib import Path

import pytest

from xafsmith import fit_exafs as fx
from xafsmith import paths, schema

HERE = Path(__file__).resolve().parent
DEMO = HERE.parent / "data" / "demo_project"
BASELINE = HERE / "modelcheck_baseline.json"

P = [{"file": "output/feff/x/feff0001.dat", "label": "a"}]


def legacy(**kw):
    m = dict(name="m", sample="s1", kmin=3, kmax=12, rmin=1, rmax=3, kweight=2, params={"s02": 0.8}, paths=P)
    m.update(kw)
    return m


def multi(**kw):
    m = dict(name="j", kmin=3, kmax=17, rmin=1, rmax=3, kweight=2, params={"s02": 0.8},
             datasets=[dict(id="A", sample="s1", paths=P), dict(id="B", sample="s2", kmax=14, paths=P)])
    m.update(kw)
    return m


def _without(m, k):
    return copy.deepcopy({a: b for a, b in m.items() if a != k})


def _ds(m, i, **kw):
    """替换第 i 个数据集的字段（值为 DEL 表示删掉该键）。"""
    m = copy.deepcopy(m)
    for k, v in kw.items():
        if v is DEL:
            m["datasets"][i].pop(k, None)
        else:
            m["datasets"][i][k] = v
    return m


DEL = object()


def cases():
    c = {}
    # ---- 旧格式
    c["L_ok"] = legacy()
    c["L_ok_nokweight_window"] = _without(legacy(window="hanning"), "kweight")
    for k in ("name", "sample", "kmin", "kmax", "rmin", "rmax", "kweight", "params", "paths"):
        c[f"L_missing_{k}"] = _without(legacy(), k)
    c["L_missing_two_ranges"] = _without(_without(legacy(), "kmin"), "rmax")
    c["L_missing_all_but_name"] = dict(name="m")
    c["L_kweight_null"] = legacy(kweight=None)
    c["L_kmin_null"] = legacy(kmin=None)
    c["L_params_list"] = legacy(params=[1, 2])
    c["L_params_list_and_missing_kmin"] = _without(legacy(params=[1]), "kmin")
    c["L_params_null"] = legacy(params=None)
    c["L_paths_empty"] = legacy(paths=[])
    c["L_paths_notlist"] = legacy(paths="x")
    c["L_paths_bad_item"] = legacy(paths=[{}, 3])
    c["L_sample_empty"] = legacy(sample="")
    c["L_range_text"] = legacy(kmin="3")
    c["L_range_reversed"] = legacy(kmin=12, kmax=3)
    c["L_restraints_bad"] = legacy(restraints="x")
    c["L_restraints_bad_and_missing_rmax"] = _without(legacy(restraints="x"), "rmax")
    c["L_temp_bad"] = legacy(temperature="hot")
    c["L_temp_bad_and_missing_rmax"] = _without(legacy(temperature="hot"), "rmax")
    c["L_tempK_no_temperature"] = legacy(paths=[{"file": "f", "sigma2": "tempK*0.001"}])
    c["L_extra_keys_ok"] = legacy(epsilon_k=0.1, dk=2, window="kaiser", fitspace="k")
    c["L_not_dict_list"] = [1, 2]
    c["L_not_dict_str"] = "x"
    # ---- 多数据集：顶层
    c["M_ok"] = multi()
    c["M_ok_top_ranges_in_ds"] = dict(name="j", params={}, datasets=[
        dict(sample="s1", paths=P, kmin=3, kmax=12, rmin=1, rmax=3, kweight=2),
        dict(sample="s2", paths=P, kmin=3, kmax=12, rmin=1, rmax=3, kweight=[1, 2])])
    c["M_missing_name"] = _without(multi(), "name")
    c["M_missing_params"] = _without(multi(), "params")
    c["M_missing_name_params"] = _without(_without(multi(), "name"), "params")
    c["M_datasets_empty"] = multi(datasets=[])
    c["M_datasets_null"] = multi(datasets=None)
    c["M_datasets_str"] = multi(datasets="x")
    c["M_datasets_dict"] = multi(datasets={"a": 1})
    c["M_top_sample"] = multi(sample="s1")
    c["M_top_paths"] = multi(paths=P)
    c["M_top_sample_paths"] = multi(sample="s1", paths=P)
    c["M_params_list"] = multi(params=[1])
    c["M_params_null"] = multi(params=None)
    c["M_top_sample_and_datasets_empty"] = multi(sample="s1", datasets=[])
    c["M_params_list_and_top_sample"] = multi(params=[1], sample="s1")
    c["M_missing_name_and_datasets_empty"] = _without(multi(datasets=[]), "name")
    c["M_restraints_bad_and_datasets_empty"] = multi(restraints="x", datasets=[])
    c["M_restraints_bad_and_top_sample"] = multi(restraints="x", sample="s1")
    c["M_temp_bad_and_datasets_empty"] = multi(temperature="hot", datasets=[])
    # ---- 多数据集：数据集
    b = multi()
    c["M_ds_not_dict"] = _ds(b, 1, **{})
    c["M_ds_not_dict"]["datasets"][1] = 5
    c["M_ds_not_dict_first"] = copy.deepcopy(b)
    c["M_ds_not_dict_first"]["datasets"][0] = "x"
    c["M_ds_not_dict_and_later_bad"] = copy.deepcopy(b)
    c["M_ds_not_dict_and_later_bad"]["datasets"][0] = None
    c["M_ds_not_dict_and_later_bad"]["datasets"][1].pop("paths")
    c["M_ds_missing_sample"] = _ds(b, 0, sample=DEL)
    c["M_ds_missing_paths"] = _ds(b, 1, paths=DEL)
    c["M_ds_missing_sample_paths"] = _ds(_ds(b, 0, sample=DEL), 0, paths=DEL)
    c["M_ds_paths_empty"] = _ds(b, 0, paths=[])
    c["M_ds_paths_null"] = _ds(b, 0, paths=None)
    c["M_ds_paths_notlist"] = _ds(b, 0, paths="x")
    c["M_ds_sample_empty"] = _ds(b, 0, sample="")
    c["M_ds_sample_null"] = _ds(b, 0, sample=None)
    c["M_ds_sample_missing_no_id"] = _ds(_ds(b, 0, sample=DEL), 0, id=DEL)
    c["M_ds_id_empty"] = _ds(b, 0, id="")
    c["M_ds_id_blank"] = _ds(b, 0, id="  ")
    c["M_ds_id_int"] = _ds(b, 0, id=5)
    c["M_ds_id_null"] = _ds(b, 0, id=None)
    c["M_ds_id_dup"] = _ds(b, 1, id="A")
    c["M_ds_id_dup_via_sample"] = _ds(_ds(_ds(b, 0, id=DEL), 1, id=DEL), 1, sample="s1")
    c["M_ds_id_default_ok"] = _ds(_ds(b, 0, id=DEL), 1, id=DEL)
    c["M_ds_id_dup_three"] = _ds(b, 1, id="A")
    c["M_ds_id_dup_three"]["datasets"].append(dict(id="A", sample="s3", paths=P))
    c["M_ds_sample_unhashable_no_id"] = _ds(_ds(b, 0, id=DEL), 0, sample=["s1"])
    c["M_ds_id_unhashable"] = _ds(b, 0, id=["A"])
    c["M_ds_range_missing"] = _ds(_without(b, "rmax"), 0)
    c["M_ds_range_missing_both_ds"] = _without(b, "rmax")
    c["M_ds_range_missing_two"] = _without(_without(b, "rmax"), "kmin")
    c["M_ds_range_in_ds_only"] = _ds(_without(_without(b, "rmax"), "kmin"), 0, rmax=3, kmin=3)
    c["M_ds_kweight_missing"] = _without(b, "kweight")
    c["M_ds_kweight_missing_ds_has"] = _ds(_without(b, "kweight"), 0, kweight=2)
    c["M_ds_kweight_null"] = _ds(b, 0, kweight=None)
    c["M_ds_kmin_null"] = _ds(b, 1, kmin=None)
    c["M_ds_range_null_top"] = multi(rmax=None)
    c["M_ds_epsilon_bad_and_id_blank"] = _ds(_ds(b, 0, id=" "), 0, epsilon_k=-1)
    c["M_ds_epsilon_bad_and_range_missing"] = _ds(_without(b, "rmax"), 0, epsilon_k=0)
    c["M_ds_epsilon_bad"] = _ds(b, 0, epsilon_k="a")
    c["M_ds_id_blank_and_missing_range_and_bad_window"] = _ds(_ds(_without(b, "rmax"), 0, id=""), 0, window="zzz")
    c["M_two_ds_each_bad"] = _ds(_ds(b, 0, sample=DEL), 1, id="")
    c["M_ds_missing_range_then_second_not_dict"] = _without(b, "rmax")
    c["M_ds_missing_range_then_second_not_dict"]["datasets"][1] = 7
    c["M_ds_missing_range_then_dup_id"] = _ds(_without(b, "rmax"), 1, id="A")
    c["M_ds_temp_bad"] = _ds(b, 0, temperature="hot")
    c["M_ds_temp_bad_and_missing_sample"] = _ds(_ds(b, 0, temperature="hot"), 1, sample=DEL)
    c["M_top_temp_bad"] = multi(temperature="hot")
    c["M_ds_params_list_range_and_ds"] = _ds(multi(params=[1], sample="s", name=None), 0, sample=DEL)
    c["M_ds_range_missing_and_restraints_bad"] = _without(multi(restraints=[3]), "rmax")
    c["M_sigma2_reserved_and_struct"] = multi(params={"tempK": 1}, datasets=[])
    c["M_all_structure_wrong"] = dict(sample="s", paths=P, params=[1], datasets=[3, dict(id=" "), dict(sample="x")])
    return c


def _norm_obs(m):
    try:
        r = fx.normalize_model(m)
    except Exception as ex:                                  # noqa: BLE001  记录异常类型与消息
        return ["raise", type(ex).__name__, str(ex)]
    return ["ok", json.dumps(r, sort_keys=True, default=str, ensure_ascii=False)]


def _validate_obs(m, models_dir):
    for f in models_dir.glob("*.json"):
        f.unlink()
    (models_dir / "c.json").write_text(json.dumps(m, ensure_ascii=False), encoding="utf-8")
    rep = schema.Report()
    try:
        schema.check_models(rep, None, {})
    except Exception as ex:                                  # noqa: BLE001
        return [["raise", type(ex).__name__, str(ex)]]
    return [list(i) for i in rep.items]


def observe(models, models_dir):
    out = {}
    for name, m in models.items():
        out[name] = dict(validate=_validate_obs(m, models_dir), normalize=_norm_obs(copy.deepcopy(m)))
    return out


@pytest.fixture
def models_dir(tmp_path):
    dst = tmp_path / "p"
    shutil.copytree(DEMO, dst, ignore=shutil.ignore_patterns("output"))
    old = paths.ROOT
    paths.set_root(dst)
    (dst / "models").mkdir(exist_ok=True)
    yield dst / "models"
    paths.set_root(old)


def test_cases_match_baseline(models_dir):
    base = json.loads(BASELINE.read_text(encoding="utf-8"))
    now = observe(cases(), models_dir)
    assert list(now) == list(base)
    for k in base:
        assert now[k]["validate"] == base[k]["validate"], f"validate: {k}"
        assert now[k]["normalize"] == base[k]["normalize"], f"normalize: {k}"


if __name__ == "__main__":
    import tempfile
    if "--write" not in sys.argv:
        sys.exit("加 --write 才会重写基线")
    with tempfile.TemporaryDirectory() as td:
        dst = Path(td) / "p"
        shutil.copytree(DEMO, dst, ignore=shutil.ignore_patterns("output"))
        paths.set_root(dst)
        (dst / "models").mkdir(exist_ok=True)
        BASELINE.write_text(json.dumps(observe(cases(), dst / "models"), ensure_ascii=False, indent=1) + "\n",
                            encoding="utf-8")
    print("wrote", BASELINE)
