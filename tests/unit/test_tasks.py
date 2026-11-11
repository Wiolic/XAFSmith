"""tasks：可取消任务句柄（纯逻辑）与 run_task 的取消 / 进度 / 出错行为（offscreen Qt）。"""
import threading
import time

import pytest

from xafsmith.tasks import Cancelled, TaskHandle


# ---------------------------------------------------------------- 纯逻辑
def test_progress_forwards_and_records():
    seen = []
    h = TaskHandle(lambda f, n: seen.append((f, n)))
    h.progress(0.25, "a")
    h.progress(1, "b")
    assert seen == [(0.25, "a"), (1.0, "b")]
    assert (h.fraction, h.text) == (1.0, "b")


def test_cancel_raises_at_next_progress():
    h = TaskHandle()
    h.progress(0.1)
    h.cancel()
    assert h.cancelled
    with pytest.raises(Cancelled):
        h.progress(0.2)
    with pytest.raises(Cancelled):
        h.check()


def test_cancelled_is_not_caught_by_except_exception():
    """阶段 2 里有大量 `except Exception`：取消不能被它们吞掉"""
    h = TaskHandle()
    h.cancel()
    swallowed = False
    try:
        try:
            h.check()
        except Exception:
            swallowed = True
    except Cancelled:
        pass
    assert not swallowed
    assert not issubclass(Cancelled, Exception)


def test_cancel_from_other_thread():
    h = TaskHandle()
    started = threading.Event()

    def work():
        started.set()
        try:
            while True:
                time.sleep(0.01)
                h.progress(0.5)
        except Cancelled:
            return "cancelled"

    out = []
    t = threading.Thread(target=lambda: out.append(work()))
    t.start()
    started.wait(2)
    h.cancel()
    t.join(2)
    assert out == ["cancelled"]


# ---------------------------------------------------------------- run_task（Qt）
@pytest.fixture(scope="module")
def qapp():
    pytest.importorskip("PySide6")
    from PySide6.QtWidgets import QApplication
    return QApplication.instance() or QApplication([])


def _wait(W, qapp, timeout=10):
    t0 = time.time()
    while (W._RUNNING or W._ACTIVE) and time.time() - t0 < timeout:
        qapp.processEvents()
        time.sleep(0.005)
    qapp.processEvents()
    assert not W._RUNNING and not W._ACTIVE, "任务没有在时限内结束"


class _Win:
    """假的主窗口：记录状态栏调用"""
    def __init__(self):
        self.calls = []

    def busy(self, on, text="", frac=None, cancel=None):
        self.calls.append((on, text, frac, cancel is not None))


def _parent(qapp, win):
    from PySide6.QtWidgets import QWidget

    class P(QWidget):
        def window(self):
            return win
    return P()


def test_run_task_done_and_progress(qapp):
    from xafsmith.qt import widgets as W
    win, got = _Win(), []
    p = _parent(qapp, win)
    W.run_task(p, lambda progress: [progress(i / 3, f"s{i}") for i in range(3)] and "ok", got.append,
               "busy", progress=True)
    _wait(W, qapp)
    assert got == ["ok"]
    assert win.calls[0][0] is True and win.calls[-1][0] is False
    assert any(c[2] is not None for c in win.calls), "进度应显示确定的进度条"
    assert any(c[3] for c in win.calls), "有进度的任务应显示取消按钮"


def test_run_task_cancel(qapp):
    from xafsmith.qt import widgets as W
    win, got, cancelled = _Win(), [], []
    n_err = len(W.ERRORS)
    p = _parent(qapp, win)
    gate = threading.Event()

    def work(progress):
        for i in range(1000):
            gate.set()
            time.sleep(0.01)
            progress(i / 1000, "step")
        return "never"

    h = W.run_task(p, work, got.append, "busy", progress=True, on_cancel=lambda: cancelled.append(1))
    gate.wait(2)
    h.cancel()
    _wait(W, qapp)
    assert got == [] and cancelled == [1]
    assert len(W.ERRORS) == n_err, "取消不是错误"
    assert win.calls[-1][0] is False


def test_run_task_cancel_swallowed_by_user_except_exception(qapp):
    """任务函数里有 except Exception 时，取消仍能退出"""
    from xafsmith.qt import widgets as W
    got, cancelled = [], []
    p = _parent(qapp, _Win())
    gate = threading.Event()

    def work(progress):
        for i in range(1000):
            try:
                gate.set()
                time.sleep(0.01)
                progress(i / 1000)
            except Exception:
                pass
        return "never"

    h = W.run_task(p, work, got.append, progress=True, on_cancel=lambda: cancelled.append(1))
    gate.wait(2)
    h.cancel()
    _wait(W, qapp)
    assert got == [] and cancelled == [1]


def test_run_task_error_reported(qapp):
    from xafsmith.qt import widgets as W
    got, errs = [], []
    p = _parent(qapp, _Win())

    def boom():
        raise ValueError("坏了")
    W.run_task(p, boom, got.append, on_error=errs.append)
    _wait(W, qapp)
    assert got == [] and len(errs) == 1 and "ValueError" in errs[0]
    W.ERRORS.pop()


def test_two_tasks_status_counts(qapp):
    from xafsmith.qt import widgets as W
    win = _Win()
    p = _parent(qapp, win)
    ev = threading.Event()
    got = []
    W.run_task(p, lambda: ev.wait(5), got.append, "a")
    W.run_task(p, lambda: ev.wait(5), got.append, "b")
    qapp.processEvents()
    assert "2" in win.calls[-1][1]
    ev.set()
    _wait(W, qapp)
    assert win.calls[-1][0] is False and len(got) == 2
