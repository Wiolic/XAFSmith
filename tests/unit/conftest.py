"""pytest 配置：保证测试不碰用户的项目文件夹与界面设置。"""
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ["XAFSMITH_NO_RECENT"] = "1"

from pathlib import Path

import pytest

_PUBLIC = Path(__file__).resolve().parents[1] / "data" / "demo_project" / "data" / "raw" / "public"


def demo_raw():
    """公开数据目录（tests/data/demo_project/data/raw/public）。"""
    return _PUBLIC


@pytest.fixture
def cu():
    """读入 Cu 箔（cu_metal_rt.xdi），每次新读，避免测试间互相改动 Group。"""
    from xafsmith.readers import read_scan
    return read_scan(_PUBLIC / "cu_metal_rt.xdi")


@pytest.fixture
def fe_std():
    """读入并用默认参数归一化的 FeO / Fe2O3 / Fe3C（dict，键为标样名）。"""
    from xafsmith.normalize import normalize
    from xafsmith.readers import read_scan
    return {n: normalize(read_scan(_PUBLIC / f))
            for n, f in (("FeO", "feo_rt1.xdi"), ("Fe2O3", "fe2o3_rt1.xmu"), ("Fe3C", "fe3c_rt.xdi"))}


# ---- E18：处理 + 保存过一次 Cu 拟合的演示项目（methods_text / si_text / summary 的测试用）
_DEMO_PROJECT = Path(__file__).resolve().parents[1] / "data" / "demo_project"
_FEFF_CU = Path(__file__).resolve().parents[1] / "data" / "benchmark" / "feffcu01.dat"
CU_MODEL = {"name": "cu_one", "sample": "cu_metal_rt", "kmin": 3, "kmax": 17, "dk": 4, "window": "kaiser",
            "kweight": 2, "rmin": 1.4, "rmax": 3.0, "fitspace": "r",
            "params": {"amp": 1.0, "del_e0": 0.0, "sig2": 0.0, "del_r": 0.0},
            "paths": [{"file": str(_FEFF_CU), "label": "Cu-Cu", "s02": "amp", "e0": "del_e0",
                       "sigma2": "sig2", "deltar": "del_r"}]}


@pytest.fixture(scope="session")
def _fitted_template(tmp_path_factory):
    """演示项目的 xafsmith.json 与 data/ 复制到临时目录，校准 + 处理全部边，再对 cu_metal_rt 拟合 cu_one 并用 services.save_fit 保存（一次，供各测试复制）"""
    import json
    import shutil
    from xafsmith import paths, pipeline as pl, services
    d = tmp_path_factory.mktemp("e18_template") / "proj"
    d.mkdir()
    shutil.copy2(_DEMO_PROJECT / "xafsmith.json", d / "xafsmith.json")        # 只复制入库的输入（models/、output/ 被 .gitignore，本机可能有别的内容）
    shutil.copytree(_DEMO_PROJECT / "data", d / "data")
    (d / "models").mkdir()
    (d / "models" / "cu_one.json").write_text(json.dumps(CU_MODEL, ensure_ascii=False), encoding="utf-8")
    old = paths.ROOT
    paths.set_root(d)
    try:
        cfg, meta = pl.load_config(), pl.load_meta()
        pl.run_calib(cfg, meta)
        pl.process_all(cfg, meta, make_figs=False)
        services.save_fit(services.run_model(services.load_model("cu_one")), "E18 test")
    finally:
        paths.set_root(old)
    return d


@pytest.fixture
def fitted_proj(_fitted_template, tmp_path):
    """上面那个项目的一份新副本，并把项目根切换到它（测试结束后切回）"""
    import shutil
    from xafsmith import paths
    d = tmp_path / "proj"
    shutil.copytree(_fitted_template, d)
    old = paths.ROOT
    paths.set_root(d)
    try:
        yield d
    finally:
        paths.set_root(old)
