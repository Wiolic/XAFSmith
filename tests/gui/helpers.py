"""GUI 测试的公共辅助（逐字取自原 tests/test_qt.py：say / pump / wait / go_fit / errors_since / step / click / texts / _none_rc）。
被 tests/gui 与 tests/local/gui 共用。say() 仍打印 [ok] / [FAIL]；失败行另记在 FAILS 里，conftest 的 autouse fixture
在每个测试结束时据此判定。"""
import os
import sys
import time

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ["XAFSMITH_NO_RECENT"] = "1"          # 不写入用户的“最近的项目”

from PySide6.QtWidgets import QLabel, QPushButton   # noqa: E402

from xafsmith.qt import widgets as W                 # noqa: E402

OK = [True]
FAILS: list[str] = []           # 本进程内所有 [FAIL] 行（say 记录；conftest 按测试取差）


def quick():
    """--quick（环境变量 XAFSMITH_GUI_QUICK=1）：跳过 FEFF8L 与稳健性检查（只有 IrTaOx 套件用到）"""
    return os.environ.get("XAFSMITH_GUI_QUICK") == "1"


def need(ctx, key):
    """流水线式测试：前置测试没有运行时（单独运行某个文件）跳过，不报误导性的失败"""
    if key not in ctx:
        pytest.skip("需先运行前面的 GUI 测试")


_NONE_RC = [sys.getrefcount(None)]


def _none_rc():
    """Python < 3.12：None 的引用计数变化。某个 C 扩展多减 None 的引用时，累积到 0 才崩（none_dealloc），
    崩溃位置与出错步骤无关；逐步打印下降量才能定位。3.12 起 None 不计引用（PEP 683），不打印。"""
    if sys.version_info >= (3, 12):
        return ""
    r = sys.getrefcount(None)
    d, _NONE_RC[0] = r - _NONE_RC[0], r
    return f"  [None 引用 {r}，{d:+d}]" if d < -200 else ""


def say(good, what):
    print(f"[{'ok' if good else 'FAIL'}] {what}{_none_rc()}", flush=True)
    if not good:
        FAILS.append(what)
    OK[0] &= bool(good)
    return good


def pump(app, t=0.05):
    end = time.time() + t
    while time.time() < end:
        app.processEvents()


def wait(app, timeout=900):
    """等后台任务结束"""
    t0 = time.time()
    pump(app)
    while W._RUNNING and time.time() - t0 < timeout:
        app.processEvents()
        time.sleep(0.02)
    pump(app, 0.2)


def go_fit(w):
    """进入“EXAFS 拟合”并切到精细拟合（进入页默认是快速拟合）"""
    w.go("fit")
    w.pages["fit"].show_detailed()


def errors_since(n):
    return W.ERRORS[n:]


def step(what, n0):
    e = errors_since(n0)
    return say(not e, what + (f": {e[0][:400]}" if e else ""))


def click(page, text):
    for b in page.findChildren(QPushButton):
        if b.text().replace("&&", "&").strip() == text and b.isEnabled():
            b.click()
            return True
    raise AssertionError(f"找不到按钮：{text}")


def texts(page):
    return " ".join(l.text() for l in page.findChildren(QLabel))



# ---- 以下为迁入 pytest 时新增（不属于原脚本）：项目临时副本、失败汇总
def copy_project(src, dst, subset_outputs=("feff",)):
    """把项目复制到临时目录 dst，使测试从不写源项目。
    演示项目（体积小）整个复制；其他项目只复制 xafsmith.json、data/、models/、structures/ 与 output/ 下 subset_outputs 里的子目录
    （不复制体积很大的整个 output）。基准测试的 FEFF 路径文件（tests/data/benchmark）复制到 dst 旁边的 benchmark/，
    检查里用 PROJ.parent / "benchmark" 引用它。"""
    import shutil
    from pathlib import Path
    src, dst = Path(src), Path(dst)
    demo = Path(__file__).resolve().parents[1] / "data" / "demo_project"
    if src.resolve() == demo.resolve():
        shutil.copytree(src, dst)
    else:
        dst.mkdir(parents=True)
        shutil.copy2(src / "xafsmith.json", dst / "xafsmith.json")
        for d in ("data", "models", "structures"):
            if (src / d).is_dir():
                shutil.copytree(src / d, dst / d)
        for d in subset_outputs:
            if (src / "output" / d).is_dir():
                shutil.copytree(src / "output" / d, dst / "output" / d)
    shutil.copytree(demo.parent / "benchmark", dst.parent / "benchmark")
    return dst


def fail_if_new(n0):
    """本测试内 say() 记下的 [FAIL] 行（FAILS[n0:]）全部列出后判失败（不在第一处就停）"""
    new = FAILS[n0:]
    if new:
        pytest.fail("本测试内有 %d 条检查失败：\n" % len(new) + "\n".join("[FAIL] " + x for x in new), pytrace=False)
