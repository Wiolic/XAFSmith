"""GUI 测试的 fixture（pytest，无窗口 offscreen）。

- session 级 qapp_window：把项目复制到临时目录再打开（演示项目照原样复制），测试从不写源项目。
  项目目录来源：环境变量 XAFSMITH_GUI_PROJECT（缺省 = tests/data/demo_project）。
- 流水线式：原脚本是一条有状态的流程（先载入再拟合……），文件名两位序号前缀，pytest 按文件名、文件内按定义顺序执行；
  段间共享的状态放 ctx 字典，缺前置时 helpers.need() 跳过。
- 每个测试结束时若 say() 记下了 [FAIL]（含 step() 检查到的 W.ERRORS），该测试判失败并列出全部 FAIL 行。
- 英文界面逐页一段必须是最后一个文件（test_99_english.py）。
"""
import os
import sys
from pathlib import Path

import pytest

pytest.importorskip("PySide6")
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ["XAFSMITH_NO_RECENT"] = "1"          # 不写入用户的“最近的项目”
sys.path.insert(0, str(Path(__file__).resolve().parent))

import checks      # noqa: E402
import helpers     # noqa: E402

DEMO = Path(__file__).resolve().parents[1] / "data" / "demo_project"


@pytest.fixture(scope="session")
def gui_project(tmp_path_factory):
    """项目临时副本（路径）"""
    src = Path(os.environ.get("XAFSMITH_GUI_PROJECT") or DEMO)
    return helpers.copy_project(src, tmp_path_factory.mktemp("gui") / src.name)


@pytest.fixture(scope="session")
def qapp_window(gui_project):
    from xafsmith import paths
    from xafsmith.qt.app import make_window
    old_root, old_env = paths.ROOT, os.environ.get("XAFSMITH_PROJECT")
    helpers.W.QUIET["v"] = True
    app, w = make_window(str(gui_project), lang="zh")
    w.resize(1440, 920)
    w.show()
    checks.PROJ = gui_project
    yield app, w
    helpers.W.shutdown_tasks()          # 后台线程全部结束后再退出（线程对象在运行中被销毁会 abort）
    w.close()
    app.processEvents()
    paths.set_root(old_root)
    if old_env is None:
        os.environ.pop("XAFSMITH_PROJECT", None)
    else:
        os.environ["XAFSMITH_PROJECT"] = old_env


@pytest.fixture(scope="session")
def ctx():
    """各测试之间共享的状态（如 "loaded"：样品已载入）"""
    return {}


@pytest.fixture
def app(qapp_window):
    return qapp_window[0]


@pytest.fixture
def w(qapp_window):
    return qapp_window[1]


@pytest.fixture
def proj(gui_project):
    return gui_project


@pytest.hookimpl(wrapper=True)
def pytest_runtest_call(item):
    n0 = len(helpers.FAILS)
    try:
        return (yield)
    finally:
        helpers.fail_if_new(n0)
