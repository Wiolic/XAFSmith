"""后台任务：run_task（QThread + 进度 + 可取消）与 wait_cursor（短任务同步）。

线程规则见 xafsmith/tasks.py 的模块说明：任务函数不碰控件、不改 State；结果在 on_done（界面线程）写回。
取消只在 progress() 调用处（步骤之间）生效；一次 larch feffit / 一次 FEFF 运行不能中途停止。

生命周期（都在界面线程里执行）：
  工作线程 done/failed/cancelled → _Relay（排队连接）→ finish()：移出 _ACTIVE、刷新状态栏、th.quit()、恢复按钮
  线程 finished → _Relay.cleanup（排队连接）：th.wait() 后才移出 _RUNNING，释放 QThread 的最后一个引用。
  不能用 lambda 直接连 finished：lambda 会在工作线程里执行，QThread 在自己的 finished 信号中途被销毁 → 崩溃（CI 退出码 134）。
"""

from __future__ import annotations

from xafsmith import logs
import traceback
import atexit
import time

import shiboken6
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
            # 装进元组再发：不让 None 直接经过跨线程的 Signal(object)（Python 3.11 的 None 不是永生对象，
            # CI 在 Ubuntu/3.11 上出现过 “none_dealloc: deallocating None” 崩溃）
            self.done.emit((r,))
        except Cancelled:
            self.cancelled.emit()
        except Exception as ex:          # noqa: BLE001
            logs.log.warning("qt.widgets.run 出错（已忽略或已提示）", exc_info=True)
            self.failed.emit(f"{type(ex).__name__}: {ex}\n\n{traceback.format_exc()}")


class _Relay(QObject):
    """在界面线程中接收后台线程的信号（回调里会新建控件，必须在界面线程执行）"""
    def __init__(self, ok, bad, prog, cancelled=None, cleanup=None):
        super().__init__()
        self._ok, self._bad, self._prog, self._cancelled, self._cleanup = ok, bad, prog, cancelled, cleanup

    @Slot(object)
    def ok(self, boxed):
        self._ok(boxed[0])

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

    @Slot()
    def cleanup(self):
        if self._cleanup:
            self._cleanup()


_RUNNING = []     # (线程, worker, relay, handle)：线程真正结束后才移除（测试等待它清空）
_ACTIVE = []      # 界面线程里尚未收到结果的任务（状态栏据此显示）


def _alive(obj):
    """控件是否仍存在（页面重建后旧按钮、旧页面的 C++ 对象已删除）"""
    return obj is not None and shiboken6.isValid(obj)


_BOUND = []       # [(按钮, key, excl, 原文字)]：页面重建出的新按钮也按运行中的任务禁用


def _matches(job, key, excl):
    return bool((key and job.get("key") == key) or (excl and job.get("excl") == excl))


def task_running(key=None, excl=None):
    """key / excl 对应的任务是否在运行；都不给 = 是否有任何任务在运行"""
    if key is None and excl is None:
        return bool(_ACTIVE)
    return any(_matches(j, key, excl) for j in _ACTIVE)


def running_count():
    return len(_ACTIVE)


def cancel_all_tasks():
    """只发取消信号（任务在下一个取消点停止）；返回被通知的任务数"""
    n = 0
    for j in list(_ACTIVE):
        if not j["handle"].cancelled:
            j["handle"].cancel()
            n += 1
    return n


def _sync():
    """按运行中的任务刷新已登记的按钮：在跑 → 禁用并显示忙碌文字；否则恢复"""
    _BOUND[:] = [e for e in _BOUND if _alive(e[0])]
    for btn, key, excl, orig in _BOUND:
        job = next((j for j in _ACTIVE if _matches(j, key, excl)), None)
        if job is not None:
            btn.setEnabled(False)
            btn.setText(job["text"])
        else:
            btn.setEnabled(True)
            btn.setText(orig)


def bind_task(btn, key, excl=None):
    """页面 build() 里给按钮登记：该任务（或互斥组）在运行时按钮禁用；重建出的新按钮同样适用"""
    _BOUND[:] = [e for e in _BOUND if _alive(e[0]) and e[0] is not btn]
    _BOUND.append((btn, key, excl, btn.text()))
    _sync()


def _elapsed(j):
    n = int(time.monotonic() - j["t0"])
    return f"{n // 60}:{n % 60:02d}" if n >= 60 else f"{n} s"


def refresh_status(status):
    """状态栏随时间刷新已用时间（主窗口每秒调用一次，只在有任务运行时）"""
    if _ACTIVE:
        _show_status(status)


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
        txt += f" · {_elapsed(j)}"
        if not j["cancellable"]:
            txt += T("（不可中断）", " (cannot be interrupted)")
        status(True, txt, j["frac"], j["cancel"] if j["cancellable"] else None)
        return
    live = [j for j in _ACTIVE if j["cancellable"] and not j["handle"].cancelled]

    def cancel_all():
        for j in live:
            j["handle"].cancel()
        _show_status(status)
    status(True, T(f"{len(_ACTIVE)} 个任务运行中", f"{len(_ACTIVE)} tasks running"), None, cancel_all if live else None)


def run_task(parent, fn, on_done, busy_text=None, button_=None, progress=False, on_error=None,
             cancellable=True, on_cancel=None, key=None, excl=None):
    """在后台线程运行 fn（耗时计算不卡界面）；完成后在界面线程调用 on_done(result)。
    progress=True 时 fn 接收一个 progress(f, 文字) 回调：它同时是取消点（见 xafsmith/tasks.py）。
    cancellable（默认 True）仅对 progress=True 的任务有意义：状态栏出现“取消”按钮，取消后不调用 on_done，
    调用 on_cancel()（如有）并提示“已取消”。返回任务句柄 TaskHandle。
    key：任务名；excl：互斥组名。同 key 或同组的任务已在运行 → 不启动，提示“已在运行”并返回 None。
    给了 key 时 button_ 自动登记（bind_task），页面重建后新按钮仍是禁用状态。未给 key 的调用保持旧行为。
    任务运行期间页面可能重建（按钮、页面被删除）：结束时跳过已删除的控件，不影响状态栏与线程回收。"""
    if (key or excl) and task_running(key, excl):
        toast(parent, T("该任务已在运行", "This task is already running"), "info")
        return None
    app = parent.window()
    status = getattr(app, "busy", None)
    th = QThread()
    wk = None
    handle = TaskHandle(lambda f, n: wk.progress.emit(float(f), str(n)))
    job = dict(handle=handle, text=busy_text or T("运行中…", "Running…"), frac=None, ptext="",
               cancellable=bool(cancellable and progress), key=key, excl=excl, t0=time.monotonic())
    job["cancel"] = lambda: (handle.cancel(), _show_status(status))
    wk = _Worker(fn, handle, progress)
    wk.moveToThread(th)
    old_text = None
    bound = bool(key or excl) and button_ is not None
    if bound:
        bind_task(button_, key, excl)
    elif button_ is not None:
        old_text = button_.text()
        button_.setEnabled(False)
        button_.setText(busy_text or T("运行中…", "Running…"))
    _ACTIVE.append(job)
    _sync()
    _show_status(status)
    QApplication.setOverrideCursor(Qt.CursorShape.BusyCursor)
    state = {"finished": False}

    def finish():
        if state["finished"]:
            return
        state["finished"] = True
        # 先做不会失败的收尾（状态栏、线程），再碰可能已删除的控件
        if job in _ACTIVE:
            _ACTIVE.remove(job)
        _show_status(status)
        th.quit()
        QApplication.restoreOverrideCursor()
        _sync()
        if not bound and _alive(button_):
            button_.setEnabled(True)
            button_.setText(old_text)

    def call(cb, *a):
        """回调里碰到已删除的控件（页面在任务期间重建）只记日志，不让异常打断收尾"""
        try:
            cb(*a)
        except RuntimeError as ex:
            if "already deleted" not in str(ex):
                raise
            logs.log.warning("后台任务结束时界面已重建，回调中的旧控件已删除：%s", ex)

    def cancelled():
        finish()
        if _alive(parent):
            toast(parent, T("已取消", "Cancelled"), "info")
        if on_cancel:
            call(on_cancel)

    def ok(r):
        if handle.cancelled:             # 已请求取消，但任务恰好跑完：丢弃结果，与“取消”一致
            cancelled()
            return
        finish()
        call(on_done, r)

    def bad(msg):
        finish()
        ERRORS.append(msg)
        if on_error:
            call(on_error, msg)
        elif not QUIET["v"]:
            dlg = QMessageBox(parent if _alive(parent) else None)
            dlg.setIcon(QMessageBox.Icon.Warning)
            dlg.setWindowTitle(T("出错了", "Error"))
            dlg.setText(msg.split("\n\n")[0])
            dlg.setDetailedText(msg)
            dlg.exec()

    def prog(f, n):
        job["frac"], job["ptext"] = f, n
        _show_status(status)

    def cleanup():
        th.wait()                         # finished 已发出，线程只剩最后几步；等它真正退出再释放
        if entry in _RUNNING:
            _RUNNING.remove(entry)
        relay.deleteLater()

    relay = _Relay(ok, bad, prog, cancelled, cleanup)    # 创建于界面线程 → 排队连接，回调在界面线程执行
    Q = Qt.ConnectionType.QueuedConnection
    wk.done.connect(relay.ok, Q)
    wk.failed.connect(relay.bad, Q)
    wk.progress.connect(relay.prog, Q)
    wk.cancelled.connect(relay.cancelled, Q)
    th.started.connect(wk.run)
    th.finished.connect(relay.cleanup, Q)
    entry = (th, wk, relay, handle)
    _RUNNING.append(entry)
    th.start()
    return handle


def shutdown_tasks(timeout_ms=10000):
    """退出前：取消全部后台任务，在总时限内等待线程结束。
    仍在运行的线程（如一次 FEFF8L）保留引用：QThread 在线程运行时被销毁，Qt 会直接 abort（退出码 134）。"""
    entries = list(_RUNNING)
    for _th, _wk, _relay, handle in entries:
        handle.cancel()
    deadline = time.monotonic() + timeout_ms / 1000
    for entry in entries:
        th = entry[0]
        try:
            th.quit()
            if th.wait(max(0, int((deadline - time.monotonic()) * 1000))) and entry in _RUNNING:
                _RUNNING.remove(entry)
        except RuntimeError:          # C++ 对象已删除
            if entry in _RUNNING:
                _RUNNING.remove(entry)
    if _RUNNING:
        logs.log.warning("退出时仍有 %d 个后台线程未结束（不可中断的单步，如 FEFF 运行）", len(_RUNNING))


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
