"""后台任务：run_task（QThread + 进度 + 可取消）与 wait_cursor（短任务同步）。

线程规则见 xafsmith/tasks.py 的模块说明：任务函数不碰控件、不改 State；结果在 on_done（界面线程）写回。
取消只在 progress() 调用处（步骤之间）生效；一次 larch feffit / 一次 FEFF 运行不能中途停止。
"""

from __future__ import annotations

from xafsmith import logs
import traceback
import atexit

from PySide6.QtCore import QObject, Qt, QThread, Signal, Slot
from PySide6.QtWidgets import QApplication, QMessageBox

from xafsmith.tasks import Cancelled, TaskHandle
from .core import ERRORS, QUIET, T
from .system import toast


class _Worker(QObject):
    done = Signal(object)
    failed = Signal(str)
    cancelled = Signal()
    progress = Signal(float, str)

    def __init__(self, fn, handle, with_progress):
        super().__init__()
        self.fn = fn
        self.handle = handle
        self.wp = with_progress

    def run(self):
        try:
            r = self.fn(self.handle.progress) if self.wp else self.fn()
            self.done.emit(r)
        except Cancelled:
            self.cancelled.emit()
        except Exception as ex:          # noqa: BLE001
            logs.log.warning("qt.widgets.run 出错（已忽略或已提示）", exc_info=True)
            self.failed.emit(f"{type(ex).__name__}: {ex}\n\n{traceback.format_exc()}")


class _Relay(QObject):
    """在界面线程中接收后台线程的信号（回调里会新建控件，必须在界面线程执行）"""
    def __init__(self, ok, bad, prog, cancelled=None):
        super().__init__()
        self._ok, self._bad, self._prog, self._cancelled = ok, bad, prog, cancelled

    @Slot(object)
    def ok(self, r):
        self._ok(r)

    @Slot(str)
    def bad(self, m):
        self._bad(m)

    @Slot(float, str)
    def prog(self, f, n):
        self._prog(f, n)

    @Slot()
    def cancelled(self):
        if self._cancelled:
            self._cancelled()


_RUNNING = []     # (线程, worker, relay, handle)：线程真正结束后才移除（测试等待它清空）
_ACTIVE = []      # 界面线程里尚未收到结果的任务（状态栏据此显示）


def _show_status(status):
    """按当前所有活动任务刷新状态栏：0 个 → 隐藏；1 个 → 进度与取消；多个 → 只显示个数"""
    if status is None:
        return
    if not _ACTIVE:
        status(False)
        return
    if len(_ACTIVE) == 1:
        j = _ACTIVE[0]
        h = j["handle"]
        if h.cancelled:
            status(True, T("正在取消…将在当前步骤结束后停止", "Cancelling… will stop after the current step"), None, None)
            return
        txt = j["text"]
        if j["frac"] is not None:
            txt = f"{txt} {j['ptext']} {j['frac'] * 100:.0f}%"
        status(True, txt, j["frac"], h.cancel_and_refresh if j["cancellable"] else None)
        return
    live = [j for j in _ACTIVE if j["cancellable"] and not j["handle"].cancelled]

    def cancel_all():
        for j in live:
            j["handle"].cancel()
        _show_status(status)
    status(True, T(f"{len(_ACTIVE)} 个任务运行中", f"{len(_ACTIVE)} tasks running"), None, cancel_all if live else None)


def run_task(parent, fn, on_done, busy_text=None, button_=None, progress=False, on_error=None,
             cancellable=True, on_cancel=None):
    """在后台线程运行 fn（耗时计算不卡界面）；完成后在界面线程调用 on_done(result)。
    progress=True 时 fn 接收一个 progress(f, 文字) 回调：它同时是取消点（见 xafsmith/tasks.py）。
    cancellable（默认 True）仅对 progress=True 的任务有意义：状态栏出现“取消”按钮，取消后不调用 on_done，
    调用 on_cancel()（如有）并提示“已取消”。返回任务句柄 TaskHandle。"""
    app = parent.window()
    status = getattr(app, "busy", None)
    th = QThread()
    handle = TaskHandle()
    job = dict(handle=handle, text=busy_text or T("运行中…", "Running…"), frac=None, ptext="",
               cancellable=bool(cancellable and progress))
    handle.cancel_and_refresh = lambda: (handle.cancel(), _show_status(status))
    wk = _Worker(fn, handle, progress)
    wk.moveToThread(th)
    if button_ is not None:
        button_.setEnabled(False)
        button_._old = button_.text()
        button_.setText(busy_text or T("运行中…", "Running…"))
    _ACTIVE.append(job)
    _show_status(status)
    QApplication.setOverrideCursor(Qt.CursorShape.BusyCursor)

    def finish():
        QApplication.restoreOverrideCursor()
        if button_ is not None:
            button_.setEnabled(True)
            button_.setText(button_._old)
        if job in _ACTIVE:
            _ACTIVE.remove(job)
        _show_status(status)
        th.quit()

    def cancelled():
        finish()
        toast(parent, T("已取消", "Cancelled"), "info")
        if on_cancel:
            on_cancel()

    def ok(r):
        if handle.cancelled:             # 已请求取消，但任务恰好跑完：丢弃结果，与“取消”一致
            cancelled()
            return
        finish()
        on_done(r)

    def bad(msg):
        finish()
        ERRORS.append(msg)
        if on_error:
            on_error(msg)
        elif not QUIET["v"]:
            dlg = QMessageBox(parent)
            dlg.setIcon(QMessageBox.Icon.Warning)
            dlg.setWindowTitle(T("出错了", "Error"))
            dlg.setText(msg.split("\n\n")[0])
            dlg.setDetailedText(msg)
            dlg.exec()

    def prog(f, n):
        job["frac"], job["ptext"] = f, n
        _show_status(status)
    relay = _Relay(ok, bad, prog, cancelled)            # 创建于界面线程 → 排队连接，回调在界面线程执行
    Q = Qt.ConnectionType.QueuedConnection
    wk.done.connect(relay.ok, Q)
    wk.failed.connect(relay.bad, Q)
    wk.progress.connect(relay.prog, Q)
    wk.cancelled.connect(relay.cancelled, Q)
    handle._on_progress = lambda f, n: wk.progress.emit(float(f), str(n))
    th.started.connect(wk.run)
    entry = (th, wk, relay, handle)
    th.finished.connect(relay.deleteLater)
    th.finished.connect(lambda: _RUNNING.remove(entry) if entry in _RUNNING else None)
    _RUNNING.append(entry)
    th.start()
    return handle


def shutdown_tasks(timeout_ms=10000):
    """退出前：取消并等待所有后台线程结束。线程对象在线程仍运行时被销毁，Qt 会直接 abort（退出码 134）。"""
    for th, _wk, _relay, handle in list(_RUNNING):
        try:
            handle.cancel()
            th.quit()
            th.wait(timeout_ms)
        except RuntimeError:          # C++ 对象已删除
            pass
    _RUNNING.clear()


atexit.register(shutdown_tasks)


def wait_cursor(fn):
    """短任务：显示等待光标同步运行；出错时弹窗并返回 None"""
    QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
    try:
        return fn()
    except Exception as ex:        # noqa: BLE001
        logs.log.warning("qt.widgets.wait_cursor 出错（已忽略或已提示）", exc_info=True)
        QApplication.restoreOverrideCursor()
        ERRORS.append(f"{type(ex).__name__}: {ex}\n{traceback.format_exc()}")
        if QUIET["v"]:
            return None
        QMessageBox.warning(QApplication.activeWindow(), T("出错了", "Error"), f"{type(ex).__name__}: {ex}")
        return None
    finally:
        if QApplication.overrideCursor():
            QApplication.restoreOverrideCursor()
