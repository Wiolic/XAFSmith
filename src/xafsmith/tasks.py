"""tasks —— 可取消、带进度的任务句柄（不依赖 Qt，界面与命令行共用）。

用法：任务函数收到一个 progress(f, 文字) 回调；在两个步骤之间调用它，既报告进度，也是“取消点”：
用户请求取消后，下一次调用 progress（或 handle.check()）会抛出 Cancelled，任务从这里退出。

线程规则（界面里用 run_task 在后台线程运行任务函数时必须遵守）：
1. 任务函数里不得创建、读取或修改任何控件，也不得修改会话 State；
2. 需要的参数在启动前复制好（如 dict(S.norm_par)），结果在 on_done（界面线程）里写回 State；
3. matplotlib 只用面向对象 API（Figure + Agg 画布），不用 pyplot；
4. 一次 larch feffit、一次 FEFF 运行不能中途停止：取消只在步骤之间生效。

Cancelled 继承 BaseException：这样各处 `except Exception` 不会把“取消”当成普通错误吞掉。
"""
from __future__ import annotations

import threading
from typing import Callable, Optional


class Cancelled(BaseException):
    """用户取消了任务（刻意不继承 Exception）"""


class TaskHandle:
    """任务与调用方之间的句柄：进度、取消标志"""

    def __init__(self, on_progress: Optional[Callable[[float, str], None]] = None):
        self._event = threading.Event()
        self._on_progress = on_progress
        self.fraction = 0.0
        self.text = ""

    @property
    def cancelled(self) -> bool:
        return self._event.is_set()

    def cancel(self) -> None:
        self._event.set()

    def check(self) -> None:
        """取消点：已请求取消则抛出 Cancelled"""
        if self._event.is_set():
            raise Cancelled()

    def progress(self, f: float = 0.0, text: str = "") -> None:
        """报告进度（f 为 0–1）并检查取消"""
        self.check()
        self.fraction, self.text = float(f), str(text)
        if self._on_progress is not None:
            self._on_progress(self.fraction, self.text)


