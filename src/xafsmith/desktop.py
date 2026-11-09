"""桌面窗口版：不打开浏览器，在独立的应用窗口中运行 XAFSmith 图形界面。

实现：后台启动本机 Streamlit 服务（随机空闲端口、无控制台窗口），用 pywebview
（Windows 上为系统自带的 Edge WebView2）打开一个原生窗口显示界面；关闭窗口即退出软件。

用法：
    xafsmith app [--project <项目目录>]
    pythonw -m xafsmith app            （桌面快捷方式使用，不显示黑色控制台窗口）
"""
import os
import socket
import subprocess
import sys
import threading
import time
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
TITLE = "XAFSmith — XAFS analysis"
CREDIT = "Developed by Eggy & Claude Opus 5.5"

SPLASH = f"""<!doctype html><html><head><meta charset="utf-8"><style>
body{{margin:0;height:100vh;display:flex;align-items:center;justify-content:center;
font-family:'Segoe UI','Microsoft YaHei',sans-serif;background:#f7f8fa;color:#333}}
.b{{text-align:center}}h1{{font-weight:600;margin:0 0 8px}}p{{color:#777;margin:4px}}
.s{{width:36px;height:36px;border:4px solid #ddd;border-top-color:#ff4b4b;border-radius:50%;
margin:24px auto;animation:r 1s linear infinite}}@keyframes r{{to{{transform:rotate(360deg)}}}}
</style></head><body><div class="b"><img src="data:image/png;base64,{{ICON}}" width="96" style="border-radius:18px"><h1>XAFSmith</h1><p>正在启动，请稍候… / Starting…</p>
<div class="s"></div><p style="font-size:12px">{CREDIT}</p>
<p style="font-size:11px;max-width:560px">No warranty — please cross-check key results with Athena / Artemis.
If you use XAFSmith in a publication, please cite https://github.com/Wiolic/XAFSmith</p></div></body></html>"""


def _splash():
    import base64
    try:
        ico = base64.b64encode((HERE / "assets" / "xafsmith.png").read_bytes()).decode()
    except Exception:
        ico = ""
    return SPLASH.replace("{ICON}", ico)


def _free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _log_file():
    d = Path.home() / ".xafsmith"
    d.mkdir(parents=True, exist_ok=True)
    return d / "app.log"


def start_server(port, project=None):
    env = dict(os.environ)
    if project:
        env["XAFSMITH_PROJECT"] = str(Path(project).resolve())
    py = Path(sys.executable)
    if py.name.lower() == "pythonw.exe" and (py.parent / "python.exe").exists():
        py = py.parent / "python.exe"        # 服务用 python.exe，但不显示窗口（CREATE_NO_WINDOW）
    cmd = [str(py), "-m", "streamlit", "run", str(HERE / "gui.py"),
           "--server.headless", "true", "--server.address", "127.0.0.1", "--server.port", str(port),
           "--browser.gatherUsageStats", "false", "--client.toolbarMode", "minimal",
           "--theme.primaryColor", "#2563eb",
           "--server.fileWatcherType", "none"]
    flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    log = open(_log_file(), "w", encoding="utf-8")
    return subprocess.Popen(cmd, env=env, stdout=log, stderr=subprocess.STDOUT, creationflags=flags)


def wait_ready(port, proc, timeout=120):
    url = f"http://127.0.0.1:{port}/_stcore/health"
    t0 = time.time()
    while time.time() - t0 < timeout:
        if proc.poll() is not None:
            return False
        try:
            with urllib.request.urlopen(url, timeout=2) as r:
                if r.status == 200:
                    return True
        except Exception:
            time.sleep(0.5)
    return False


def run(project=None):
    import webview
    try:
        webview.settings["ALLOW_DOWNLOADS"] = True       # 汇总报告的“下载”按钮
    except Exception:
        pass
    port = _free_port()
    proc = start_server(port, project)
    win = webview.create_window(TITLE, html=_splash(), width=1400, height=900, min_size=(1000, 650))

    def load():
        if wait_ready(port, proc):
            win.load_url(f"http://127.0.0.1:{port}/")
        else:
            win.load_html(f"<h2 style='font-family:sans-serif'>XAFSmith 启动失败</h2>"
                          f"<p style='font-family:sans-serif'>日志：{_log_file()}</p>")

    threading.Thread(target=load, daemon=True).start()
    try:
        store = Path.home() / ".xafsmith" / "webview"
        store.mkdir(parents=True, exist_ok=True)
        webview.start(private_mode=False, storage_path=str(store))
    finally:
        proc.terminate()
        try:
            proc.wait(10)
        except Exception:
            proc.kill()
