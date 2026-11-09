"""update —— 检查 GitHub 上是否有新版本，并在用户确认后更新。

检查：读取 GitHub 仓库 main 分支的 pyproject.toml 中的 version，与本机已安装版本比较（只访问 github.com，
不发送任何用户数据；超时 4 秒，离线时安静失败）。
更新：pip install --upgrade https://github.com/Wiolic/XAFSmith/archive/refs/heads/main.zip
      （不需要安装 git）。开发安装（pip install -e）不自动更新，提示用 git pull。
设置保存在 ~/.xafsmith/settings.json（check_updates: true/false）。
"""
import json
import re
import subprocess
import sys
import urllib.request
from pathlib import Path

from . import __version__

REPO = "Wiolic/XAFSmith"
RAW_URL = f"https://raw.githubusercontent.com/{REPO}/main/pyproject.toml"
ZIP_URL = f"https://github.com/{REPO}/archive/refs/heads/main.zip"
SETTINGS = Path.home() / ".xafsmith" / "settings.json"


def load_settings():
    try:
        return json.loads(SETTINGS.read_text(encoding="utf-8"))
    except Exception:
        return {}


def save_settings(**kw):
    s = load_settings()
    s.update(kw)
    SETTINGS.parent.mkdir(parents=True, exist_ok=True)
    SETTINGS.write_text(json.dumps(s, ensure_ascii=False, indent=2), encoding="utf-8")
    return s


def _vtuple(v):
    return tuple(int(x) for x in re.findall(r"\d+", str(v))[:3]) or (0,)


def latest_version(timeout=4.0):
    """返回 GitHub main 分支上的版本号；失败返回 None"""
    try:
        req = urllib.request.Request(RAW_URL, headers={"User-Agent": "XAFSmith-update-check"})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            txt = r.read().decode("utf-8", "replace")
        m = re.search(r'^version\s*=\s*"([^"]+)"', txt, re.M)
        return m.group(1) if m else None
    except Exception:
        return None


def is_editable():
    """是否为开发安装（pip install -e）"""
    try:
        from importlib.metadata import distribution
        d = distribution("xafsmith")
        info = json.loads(d.read_text("direct_url.json") or "{}")
        return bool(info.get("dir_info", {}).get("editable"))
    except Exception:
        return False


def check(timeout=4.0):
    """dict(current, latest, newer: bool|None, editable)"""
    lat = latest_version(timeout)
    return dict(current=__version__, latest=lat,
                newer=None if lat is None else _vtuple(lat) > _vtuple(__version__), editable=is_editable())


def upgrade():
    """用当前 Python 环境的 pip 从 GitHub 安装最新版；返回 (成功, 输出文本)"""
    if is_editable():
        return False, "开发安装（pip install -e）：请在源码目录运行 git pull 更新。"
    py = Path(sys.executable)
    if py.name.lower() == "pythonw.exe" and (py.parent / "python.exe").exists():
        py = py.parent / "python.exe"
    flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    r = subprocess.run([str(py), "-m", "pip", "install", "--upgrade", ZIP_URL], capture_output=True, text=True,
                       creationflags=flags)
    return r.returncode == 0, (r.stdout or "")[-3000:] + (r.stderr or "")[-3000:]
