"""XAFSmith 安装向导 / installer（Windows，图形界面）。

用法 / Usage：装好 Python ≥ 3.10 后，双击本文件 installer.py（或在命令行运行 `python installer.py`）。
Double-click installer.py after installing Python ≥ 3.10 (or run `python installer.py`).

选项：安装位置、桌面快捷方式、开始菜单快捷方式、安装后立即启动。
安装内容：<安装位置>\\venv（独立 Python 环境，含 XAFSmith 及依赖）、启动与卸载脚本、图标。
"""
import os
import queue
import shutil
import subprocess
import sys
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

SRC = Path(__file__).resolve().parent
APPNAME = "XAFSmith"
CREDIT = "Developed by Eggy & Claude Opus 5.5"
DEFAULT_DIR = Path(os.environ.get("LOCALAPPDATA", Path.home())) / "Programs" / APPNAME
LOCATION_FILE = Path(os.environ.get("LOCALAPPDATA", Path.home())) / APPNAME / "location.txt"
NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)


def special_folder(name):
    """Desktop / Programs（开始菜单）文件夹"""
    ps = f"[Environment]::GetFolderPath('{name}')"
    out = subprocess.run(["powershell", "-NoProfile", "-Command", ps], capture_output=True, text=True,
                         creationflags=NO_WINDOW)
    return Path(out.stdout.strip())


def make_shortcut(lnk, target, args="", workdir="", icon="", desc=""):
    ps = ("$s=(New-Object -ComObject WScript.Shell).CreateShortcut($env:LNK);"
          "$s.TargetPath=$env:TGT;$s.Arguments=$env:ARGS;$s.WorkingDirectory=$env:WD;"
          "if($env:ICO){$s.IconLocation=$env:ICO};$s.Description=$env:DESC;$s.Save()")
    env = dict(os.environ, LNK=str(lnk), TGT=str(target), ARGS=args, WD=str(workdir), ICO=str(icon), DESC=desc)
    subprocess.run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", ps], env=env,
                   check=True, creationflags=NO_WINDOW)




class Installer(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title(f"{APPNAME} 安装向导 / Setup")
        try:
            self.iconbitmap(str(SRC / "src" / "xafsmith" / "assets" / "xafsmith.ico"))
        except Exception:
            pass
        self.geometry("720x780")
        self.minsize(600, 480)
        self.q = queue.Queue()
        pad = dict(padx=14, pady=4)

        ttk.Label(self, text=APPNAME, font=("Segoe UI", 20, "bold")).pack(anchor="w", padx=14, pady=(14, 0))
        ttk.Label(self, text="可连接 AI 助手的同步辐射 XAFS 分析软件 / Agent-ready synchrotron XAFS analysis", font=("Microsoft YaHei", 10)).pack(anchor="w", **pad)
        ttk.Label(self, text=CREDIT, foreground="#666").pack(anchor="w", padx=14)

        box = ttk.LabelFrame(self, text="安装选项 / Options")
        box.pack(fill="x", padx=14, pady=10)
        ttk.Label(box, text="安装位置 / Location：").grid(row=0, column=0, sticky="w", padx=8, pady=6)
        self.dir = tk.StringVar(value=str(DEFAULT_DIR))
        ttk.Entry(box, textvariable=self.dir, width=52).grid(row=0, column=1, sticky="we", pady=6)
        ttk.Button(box, text="浏览… / Browse…", command=self.browse).grid(row=0, column=2, padx=8)
        box.columnconfigure(1, weight=1)
        self.desktop = tk.BooleanVar(value=True)
        self.startmenu = tk.BooleanVar(value=True)
        self.launch = tk.BooleanVar(value=True)
        ttk.Checkbutton(box, text="创建桌面快捷方式 / Desktop shortcut", variable=self.desktop).grid(row=1, column=1, sticky="w")
        ttk.Checkbutton(box, text="创建开始菜单快捷方式（含卸载）/ Start-menu shortcuts (with uninstall)", variable=self.startmenu).grid(row=2, column=1, sticky="w")
        ttk.Checkbutton(box, text="安装完成后立即启动 / Launch when finished", variable=self.launch).grid(row=3, column=1, sticky="w", pady=(0, 6))
        ttk.Label(box, text=f"需要联网（约 1 GB，5–15 分钟）/ Internet needed (~1 GB, 5–15 min)。Python {sys.version.split()[0]}",
                  foreground="#666").grid(row=4, column=0, columnspan=3, sticky="w", padx=8, pady=(0, 6))

        note = ttk.LabelFrame(self, text="免责声明、引用与许可 / Disclaimer, citation & license")
        note.pack(fill="x", padx=14, pady=(0, 8))
        tk.Message(note, width=590, font=("Microsoft YaHei", 9), fg="#8a4b00", text=(
            "本软件按“现状”提供，不附带任何保证；作者不对使用本软件得到的结果负责。"
            "请自行核验结果，建议与 Athena / Artemis 的结果对比。\n"
            "Provided \"as is\", without warranty. Please cross-check key results with Athena / Artemis.")).pack(anchor="w")
        tk.Message(note, width=590, font=("Microsoft YaHei", 9), fg="#1a4f8a", text=(
            "论文中使用本软件，请引用本仓库：Eggy & Claude, XAFSmith, https://github.com/Wiolic/XAFSmith\n"
            "If you use XAFSmith in a publication, please cite the repository above.")).pack(anchor="w")
        tk.Message(note, width=590, font=("Microsoft YaHei", 9), fg="#444", text=(
            "许可：MIT（自 v1.3.1）——可自由使用、修改、分发；分发时保留版权声明与许可文本。\n"
            "License: MIT (since v1.3.1) — free to use, modify and distribute; keep the copyright notice and license text.")).pack(anchor="w")
        self.agree = tk.BooleanVar(value=False)
        ttk.Checkbutton(note, text="我已阅读并同意 / I have read and agree", variable=self.agree,
                        command=lambda: self.btn.configure(state="normal" if self.agree.get() else "disabled")
                        ).pack(anchor="w", pady=(2, 6))

        self.bar = ttk.Progressbar(self, mode="determinate", maximum=6)
        self.bar.pack(fill="x", padx=14)
        self.status = ttk.Label(self, text="准备就绪 / Ready")
        self.status.pack(anchor="w", padx=14, pady=2)
        self.log = tk.Text(self, height=8, font=("Consolas", 9), state="disabled")
        self.log.pack(fill="both", expand=True, padx=14, pady=4)

        btns = ttk.Frame(self)
        btns.pack(fill="x", padx=14, pady=10)
        self.btn = ttk.Button(btns, text="安装 / Install", command=self.start, state="disabled")
        self.btn.pack(side="right")
        ttk.Button(btns, text="取消 / Cancel", command=self.destroy).pack(side="right", padx=8)
        self.after(100, self.poll)

    # ------------------------------------------------------------------
    def browse(self):
        d = filedialog.askdirectory(title="选择安装位置 / Choose location", initialdir=str(Path(self.dir.get()).parent))
        if d:
            self.dir.set(str(Path(d) / APPNAME) if Path(d).name != APPNAME else d)

    def write(self, msg):
        self.q.put(("log", msg))

    def poll(self):
        try:
            while True:
                kind, val = self.q.get_nowait()
                if kind == "log":
                    self.log.configure(state="normal")
                    self.log.insert("end", val + "\n")
                    self.log.see("end")
                    self.log.configure(state="disabled")
                elif kind == "step":
                    self.bar["value"] = val[0]
                    self.status["text"] = val[1]
                elif kind == "done":
                    self.finish(*val)
        except queue.Empty:
            pass
        self.after(100, self.poll)

    def run(self, cmd):
        p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
                             encoding="utf-8", errors="replace", creationflags=NO_WINDOW)
        for line in p.stdout:
            line = line.rstrip()
            if line:
                self.write(line[-160:])
        if p.wait():
            raise RuntimeError(f"命令失败：{' '.join(map(str, cmd))[:200]}")

    def start(self):
        target = Path(self.dir.get()).expanduser()
        if not target.is_absolute():
            messagebox.showerror(APPNAME, "请填写完整的安装位置 / Please enter a full path（例如 e.g. D:\\Programs\\XAFSmith）")
            return
        self.btn["state"] = "disabled"
        threading.Thread(target=self.install, args=(target,), daemon=True).start()

    def install(self, target):
        try:
            venv = target / "venv"
            py = venv / "Scripts" / "python.exe"
            pyw = venv / "Scripts" / "pythonw.exe"
            self.q.put(("step", (1, f"1/6 创建独立 Python 环境 / Creating environment：{venv}")))
            target.mkdir(parents=True, exist_ok=True)
            if not py.exists():
                self.run([sys.executable, "-m", "venv", str(venv)])
            self.q.put(("step", (2, "2/6 更新 pip / Updating pip")))
            self.run([str(py), "-m", "pip", "install", "--upgrade", "pip"])
            self.q.put(("step", (3, "3/6 安装 XAFSmith 及依赖（时间较长）/ Installing XAFSmith and dependencies (takes a while)")))
            self.run([str(py), "-m", "pip", "install", "--upgrade", str(SRC)])
            self.q.put(("step", (4, "4/6 图标与卸载程序 / Icon and uninstaller")))
            icon = target / "xafsmith.ico"
            try:
                shutil.copy(SRC / "src" / "xafsmith" / "assets" / "xafsmith.ico", icon)
            except Exception as ex:
                self.write(f"（图标复制失败，使用默认图标：{ex}）")
                icon = ""
            for old in (target / "启动XAFSmith.bat",):          # 旧版本留下的启动脚本 / launcher from older versions
                old.unlink(missing_ok=True)
            LOCATION_FILE.parent.mkdir(parents=True, exist_ok=True)
            LOCATION_FILE.write_text(str(target), encoding="utf-8")
            self.q.put(("step", (5, "5/6 创建快捷方式 / Shortcuts")))
            links = []
            home = Path.home()
            # 安装目录里始终放一个快捷方式 / always a shortcut in the install folder
            make_shortcut(target / f"{APPNAME}.lnk", pyw, "-m xafsmith gui", home, icon, f"{APPNAME} — {CREDIT}")
            if self.desktop.get():
                lnk = special_folder("Desktop") / f"{APPNAME}.lnk"
                make_shortcut(lnk, pyw, "-m xafsmith gui", home, icon, f"{APPNAME} — {CREDIT}")
                links.append(lnk)
            if self.startmenu.get():
                folder = special_folder("Programs") / APPNAME
                folder.mkdir(parents=True, exist_ok=True)
                lnk = folder / f"{APPNAME}.lnk"
                make_shortcut(lnk, pyw, "-m xafsmith gui", home, icon, f"{APPNAME} — {CREDIT}")
                links += [lnk, folder / f"卸载 {APPNAME}.lnk"]
            uninstall = target / "卸载XAFSmith.bat"
            lines = ["@echo off", "chcp 65001 >nul", f"echo 将卸载 {APPNAME}（只删除软件，不删除你的项目与数据）/ Uninstalling {APPNAME} (your projects and data are kept).", "pause"]
            for l in links:
                lines.append(f'del "{l}" 2>nul')
            if self.startmenu.get():
                lines.append(f'rmdir "{special_folder("Programs") / APPNAME}" 2>nul')
            lines += [f'del "{LOCATION_FILE}" 2>nul', "echo 卸载完成 / Uninstalled.",
                      f'start "" /b cmd /c "timeout /t 2 >nul & rmdir /s /q \\"{target}\\""', "exit"]
            uninstall.write_bytes("\r\n".join(lines).encode("utf-8"))
            if self.startmenu.get():
                make_shortcut(special_folder("Programs") / APPNAME / f"卸载 {APPNAME}.lnk", uninstall,
                              workdir=target, desc=f"卸载 {APPNAME}")
            self.q.put(("step", (6, "6/6 检查安装 / Verifying")))
            self.run([str(py), "-m", "xafsmith", "--version"])
            self.q.put(("done", (True, target, pyw)))
        except Exception as ex:
            self.write(f"错误：{ex}")
            self.q.put(("done", (False, target, None)))

    def finish(self, ok, target, pyw):
        if ok:
            self.status["text"] = "安装完成 / Done"
            msg = (f"{APPNAME} 已安装到 / installed to：\n{target}\n\n"
                   + ("双击桌面上的 XAFSmith 图标打开软件。\nDouble-click the XAFSmith icon on the desktop."
                      if self.desktop.get() else
                      f"双击 {target / (APPNAME + '.lnk')} 打开软件。\nDouble-click it to open XAFSmith."))
            messagebox.showinfo(APPNAME, msg)
            if self.launch.get():
                subprocess.Popen([str(pyw), "-m", "xafsmith", "gui"], cwd=str(Path.home()), creationflags=NO_WINDOW)
            self.destroy()
        else:
            self.status["text"] = "安装失败 / Failed"
            messagebox.showerror(APPNAME, "安装失败。请检查网络后重试，或把窗口中的日志截图发给维护者。\nInstallation failed. Check the network and retry, or send a screenshot of the log to the maintainers.")
            self.btn["state"] = "normal"


if __name__ == "__main__":
    try:                                    # 高分辨率屏幕上清晰显示
        import ctypes
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except Exception:
        pass
    if sys.version_info < (3, 10):
        tk.Tk().withdraw()
        messagebox.showerror(APPNAME, "需要 Python 3.10 或更高版本 / Python ≥ 3.10 is required.")
        sys.exit(1)
    Installer().mainloop()
