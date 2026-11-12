"""统一日志与诊断包。

- 日志文件：~/.xafsmith/xafsmith.log（滚动，最多 3×1 MB）；GUI、CLI 共用。
- `log` 是包级 logger；`except Exception` 处用 `log.exception("…")` 记录，而不是静默 pass。
- `install_excepthook()` 把未捕获异常写入日志（GUI 另行弹出可复制的错误框）。
- `diagnostics_zip()` 打包 日志 + 版本/环境 + xafsmith.json + data/meta.csv 摘要，
  **不含原始数据、不含谱图数值**，可直接发给开发者。
"""
import json
import logging
import logging.handlers
import os
import platform
import sys
import traceback
import zipfile
from datetime import datetime
from pathlib import Path

LOG_DIR = Path.home() / ".xafsmith"
LOG_FILE = LOG_DIR / "xafsmith.log"

log = logging.getLogger("xafsmith")
_configured = False


def setup(level=None):
    """配置滚动文件日志（幂等）。无法写文件时只丢弃日志，不抛异常。
    默认记录 INFO 及以上；设环境变量 XAFSMITH_DEBUG=1 则连探测/回退类的 debug 一并记录。"""
    global _configured
    if _configured:
        return log
    _configured = True
    level = level or (logging.DEBUG if os.environ.get("XAFSMITH_DEBUG") else logging.INFO)
    log.setLevel(level)
    fmt = logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s")
    try:
        LOG_DIR.mkdir(parents=True, exist_ok=True)
        h = logging.handlers.RotatingFileHandler(LOG_FILE, maxBytes=1_000_000, backupCount=3, encoding="utf-8")
        h.setFormatter(fmt)
        log.addHandler(h)
    except OSError:
        pass
    log.propagate = False
    return log


def format_exc(exc_info=None):
    et, ev, tb = exc_info or sys.exc_info()
    return "".join(traceback.format_exception(et, ev, tb))


def install_excepthook(on_error=None):
    """未捕获异常 → 写日志；on_error(text) 可用于界面提示。"""
    setup()
    old = sys.excepthook

    def hook(et, ev, tb):
        text = "".join(traceback.format_exception(et, ev, tb))
        log.error("未捕获异常\n%s", text)
        if on_error:
            try:
                on_error(text)
            except Exception:
                log.exception("错误提示框本身出错")
        if old is not sys.__excepthook__:
            old(et, ev, tb)
    sys.excepthook = hook


def environment_info():
    from . import __version__
    info = {"xafsmith": __version__, "python": sys.version.split()[0], "platform": platform.platform(),
            "time": datetime.now().isoformat(timespec="seconds")}
    for mod in ("numpy", "scipy", "lmfit", "larch", "xraydb", "PySide6", "matplotlib", "pandas"):
        try:
            m = __import__(mod)
            info[mod] = getattr(m, "__version__", None) or getattr(getattr(m, "version", None), "__version__", "?")
        except Exception:
            info[mod] = "未安装"
    return info


def diagnostics_zip(dest=None, root=None):
    """生成诊断包，返回路径。root 缺省取当前项目。"""
    from . import paths
    root = Path(root or paths.ROOT)
    dest = Path(dest or (LOG_DIR / f"xafsmith_diag_{datetime.now():%Y%m%d_%H%M%S}.zip"))
    dest.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(dest, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("environment.json", json.dumps(environment_info(), ensure_ascii=False, indent=2))
        for f in sorted(LOG_DIR.glob("xafsmith.log*")):
            z.write(f, f"logs/{f.name}")
        cfg = root / paths.MARKER
        if cfg.exists():
            z.write(cfg, paths.MARKER)
        meta = root / "data" / "meta.csv"
        if meta.exists():                      # 登记表只有文件名与样品信息，不含谱数据
            z.write(meta, "data/meta.csv")
        try:
            from . import schema
            rep = schema.Report()
            schema.check_layout(rep)
            z.writestr("validate.txt", str(rep.table()) if hasattr(rep, "table") else "")
        except Exception:
            z.writestr("validate.txt", "校验失败：\n" + format_exc())
    return dest


setup()          # 导入即配置：避免未配置时 Python 把 warning 打到控制台
