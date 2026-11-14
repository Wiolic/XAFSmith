"""agent —— 把 XAFSmith 项目接入 AI 助手（Claude Code、Codex、Cursor 等）。

写入项目根目录：
  AGENTS.md  —— 只更新 <!-- XAFSmith:BEGIN --> … <!-- XAFSmith:END --> 之间的部分，用户自己写的内容保留；
                块中写明本机 xafsmith 命令的绝对路径、工作流程、拟合与导出命令、规则（中英文）。
  CLAUDE.md  —— 不存在时新建（引用 AGENTS.md）；已存在且未提到 AGENTS.md 时在开头加一行引用。
Codex、Cursor 等读取 AGENTS.md；Claude Code 读取 CLAUDE.md（其中 @AGENTS.md 会被展开）。

命令行：xafsmith agent            显示接入信息
        xafsmith agent --write    写入 / 更新 AGENTS.md 与 CLAUDE.md
"""
import os
import re
import shutil
import sys
from pathlib import Path

from . import __version__

BEGIN, END = "<!-- XAFSmith:BEGIN -->", "<!-- XAFSmith:END -->"


def exe_path():
    """本机 xafsmith 命令的绝对路径（与当前运行的 Python 同一环境）。"""
    d = Path(sys.executable).resolve().parent
    for name in ("xafsmith-cli.exe", "xafsmith-cli", "xafsmith.exe", "xafsmith"):
        if (d / name).exists():
            return d / name
        if (d / "Scripts" / name).exists():
            return d / "Scripts" / name
    w = shutil.which("xafsmith")
    return Path(w) if w else None


def command():
    """写进文档的命令：优先 xafsmith 可执行文件，否则 python -m xafsmith。"""
    e = exe_path()
    if e:
        return f'"{e}"' if " " in str(e) else str(e)
    py = Path(sys.executable)
    if py.name.lower() == "pythonw.exe":
        py = py.with_name("python.exe")
    return f'"{py}" -m xafsmith' if " " in str(py) else f"{py} -m xafsmith"


def block(root=None):
    x = command()
    return f"""{BEGIN}
## XAFSmith（v{__version__}）—— 给 AI 助手的说明 / Instructions for AI assistants

本文件夹是一个 **XAFSmith 项目**：同步辐射 XAFS（XANES + EXAFS）数据处理与拟合。用户可能不懂编程，请用用户的语言交流。
This folder is an **XAFSmith project** for synchrotron XAFS (XANES + EXAFS) analysis. The user may not program; reply in the user's language.

**命令 / Command**（本机绝对路径 / absolute path on this computer）：

```
{x}
```

下文 `xafsmith` 均指上面这个命令 / `xafsmith` below means the command above. 先运行 / First run:
`xafsmith --help`、`xafsmith validate`、`xafsmith docs`（手册 手册.md、数据标准 数据标准.md、规范 XAFS处理规范.md）。

### 工作流程 / Workflow
| 步骤 Step | 命令 Command | 结果 Output |
|---|---|---|
| 登记数据 Register raw data | `xafsmith init` → 检查 `data/meta.csv` | sample / role / ref_file |
| 质量检查 QC | `xafsmith qc`；`xafsmith kcheck --edge Cu_K` | `output/qc/` |
| 校准 + 处理 Calibrate + process | `xafsmith calib`；`xafsmith process` | `output/processed/`、`output/figs/` |
| FEFF | `xafsmith feff --structure X.cif --absorber Cu --edge K [--code feff8]` | `output/feff/` |
| 拟合 Fit | 写 `models/<名>.json`（见 `models/_模板.json`）→ `xafsmith fit <名>` | `output/fits/` |
| 诊断 Diagnose | `xafsmith diagnose <名>` | 残差/噪声、毛刺、建议 residual vs noise, glitches, hints |
| 显著性 Significance | `xafsmith ftest <小模型> <大模型>`（p < 0.05） | |
| 多模型比较 Model comparison | `xafsmith compare M1 M2 [M3 …]` | `output/fits/model_compare.csv` |
| 稳健性 Robustness | `xafsmith robust <名>` | `output/fits/*_robustness*.csv` |
| LCF / XANES | `xafsmith lcf --sample S --standards A B`；`xafsmith xanes --samples …` | `output/lcf/`、`output/xanes/` |
| **导出 Export** | `xafsmith figure …`（期刊图 journal figures）；`xafsmith summary`（Excel + HTML）；`xafsmith methods`（方法段落 methods text）；`xafsmith si`（SI 拟合方法文本 + 参数表 SI fitting text + table）；`xafsmith export-prj --samples …`（Athena） | `output/figs/journal/`、`output/reports/` |

### 规则 / Rules
1. 原始数据只读；结果写入 `output/`；模型放 `models/`；每次分析写 `notes/YYYY-MM-DD_主题.md`。 Raw data are read-only; results go to `output/`, models to `models/`, notes to `notes/`.
2. 处理参数只改 `xafsmith.json`（同一吸收边所有样品共用；例外写 `overrides` + 理由；去毛刺写 `deglitch` + `deglitch_reason`）。 One parameter set per edge in `xafsmith.json`; exceptions need a reason.
3. S0² 先在结构已知的标样上确定，样品中固定。 Determine S0² on a known standard, fix it for samples.
4. 变量数 ≤ N_idp/2；加壳层必须 F 检验；结论要通过稳健性检查。 Variables ≤ N_idp/2; F-test every added shell; check robustness.
5. 结论分“实测 / 拟合 / 推测”；不编造数据、误差或文献值。 Label conclusions as measured / fitted / inferred; never invent data.
6. 用户可以在图形界面（`xafsmith gui`）中打开你建立的模型与结果检查。 The user can inspect everything you produce in the GUI.
7. XAFSmith 按 MIT 许可授权；论文中请求引用 Eggy & Claude, XAFSmith, https://github.com/Wiolic/XAFSmith（以及 Larch 与 FEFF）。生成的方法段落与报告中保留这条引用。 XAFSmith is MIT-licensed; publications are asked to cite it (and Larch and FEFF) — a request, not a license condition — keep this citation in generated methods text and reports.
{END}
"""


def write(root):
    """写入 / 更新 AGENTS.md 中的 XAFSmith 块，并确保 CLAUDE.md 引用 AGENTS.md。返回改动的文件列表。"""
    root = Path(root)
    changed = []
    a = root / "AGENTS.md"
    blk = block(root).strip() + "\n"
    if a.exists():
        old = a.read_text(encoding="utf-8")
        if BEGIN in old and END in old:
            new = re.sub(re.escape(BEGIN) + r".*?" + re.escape(END) + r"\n?", lambda _: blk, old, flags=re.S)
        else:
            new = blk + "\n" + old
    else:
        new = "# AGENTS.md\n\n" + blk + "\n## 本项目 / This project\n\n（在这里写体系、约定与已有结论 / project notes here）\n"
        old = None
    if new != old:
        a.write_text(new, encoding="utf-8")
        changed.append(a)
    c = root / "CLAUDE.md"
    line = "@AGENTS.md\n\n（XAFSmith 项目：说明见 AGENTS.md / XAFSmith project: see AGENTS.md）\n"
    if not c.exists():
        c.write_text(line, encoding="utf-8")
        changed.append(c)
    else:
        t = c.read_text(encoding="utf-8")
        if "AGENTS.md" not in t:
            c.write_text(line + "\n" + t, encoding="utf-8")
            changed.append(c)
    return changed


def status(root):
    root = Path(root)
    a = root / "AGENTS.md"
    has = a.exists() and BEGIN in a.read_text(encoding="utf-8")
    cur = has and command() in a.read_text(encoding="utf-8")
    return dict(agents_md=a.exists(), block=has, current=cur, claude_md=(root / "CLAUDE.md").exists(),
                command=command())


EXAMPLES_ZH = [
    "读 AGENTS.md，然后检查这批数据的质量，告诉我哪些扫描或毛刺有问题。",
    "用 Cu 箔标样确定 Cu K 边的 S0²，并判断拟合质量。",
    "把同一个模型用于时间序列样品 A、B、C，比较第二壳层，做 F 检验和稳健性检查，结论分实测/拟合/推测。",
    "把这个序列的 |χ(R)| 和最终拟合导出成双栏期刊图，再生成汇总报告和方法段落。",
]
EXAMPLES_EN = [
    "Read AGENTS.md, then check the data quality and tell me which scans or glitches are a problem.",
    "Determine S0² for the Cu K edge from the Cu foil standard and judge the fit quality.",
    "Apply the same model to time-series samples A, B and C, compare the second shell, run F-tests and robustness checks, "
    "and label conclusions as measured / fitted / inferred.",
    "Export |χ(R)| and the final fits of the series as double-column journal figures, then build the summary "
    "report and the methods paragraph.",
]


def main_text(root):
    s = status(root)
    lines = [f"xafsmith 命令 / command: {s['command']}", f"项目 / project: {root}",
             f"AGENTS.md: {'已接入 / connected' if s['current'] else ('需要更新 / outdated' if s['block'] else '未接入 / not connected')}",
             f"CLAUDE.md: {'有 / present' if s['claude_md'] else '无 / missing'}"]
    if not s["current"]:
        lines.append("运行 `xafsmith agent --write` 写入 / run `xafsmith agent --write` to connect")
    return "\n".join(lines)


if __name__ == "__main__":
    print(main_text(Path(os.getcwd())))
