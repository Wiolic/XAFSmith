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
