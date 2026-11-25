"""E10：默认值与常量只有一个来源。"""
from xafsmith import autobk, defaults, ft, logs, normalize, paths, pipeline, schema, update


def test_dsp_defaults_are_the_same_objects():
    assert normalize.DEFAULT_NORM is defaults.NORM
    assert autobk.DEFAULT_BKG is defaults.BKG
    assert ft.DEFAULT_FT is defaults.FT


def test_meta_cols_single_source():
    assert schema.META_COLS is pipeline.META_COLS is defaults.META_COLS


def test_new_config_keeps_norm2_minus_10():
    # 写进用户 xafsmith.json 的是 -10；normalize.DEFAULT_NORM 的 None 与它不合并
    c = pipeline.default_edge_config("Cu", "K")
    assert c["norm"]["norm2"] == -10 and defaults.NORM["norm2"] is None
    assert c["norm"] == defaults.CONFIG_EDGE_DEFAULTS["norm"]
    assert c["norm"] is not defaults.CONFIG_EDGE_DEFAULTS["norm"]      # 每次新建，不共享可变字典


def test_suffix_sets_stay_distinct():
    assert pipeline._DATA_SUFFIX is defaults.DATA_SUFFIX
    assert ".nor" in defaults.RAW_LIST_SUFFIX and ".nor" not in defaults.DATA_SUFFIX
    assert ".csv" in defaults.DATA_SUFFIX and ".csv" not in defaults.RAW_LIST_SUFFIX


def test_user_dir_single_source():
    assert paths.USER_DIR is defaults.USER_DIR
    assert logs.LOG_DIR == paths.USER_DIR and update.SETTINGS.parent == paths.USER_DIR
    assert paths.USER_DIR.name == ".xafsmith"
