# Quickstart

从零开始，大约 15 分钟：装环境 → 放数据 → 校准与处理 → 拟合一个标样 → 打开图形界面。

## 1. 安装（Windows，Python 3.11–3.13）

```
git clone https://github.com/Wiolic/XAFSmith.git
cd XAFSmith
python -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt
```

xraylarch 自带 FEFF6L，无需另装。macOS / Linux 把 `.venv\Scripts\python` 换成 `.venv/bin/python`。

以下命令都在项目根目录运行，`py` 代表 `.venv\Scripts\python`。

## 2. 放入原始数据

每次测量（一个机时 / 一个批次）一个文件夹，**里面要有该批次测的单质参比**（金属箔或粉，文件名含 `foil` / `powder` / `metal`）：

```
data/raw/
└── 20261105_Ta/
    ├── Ta_foil        ← 参比
    ├── KTaO3          ← 标样
    └── sample_1 ...
```

原始文件只读，工具不会修改它们。

## 3. 登记、检查、校准、处理

```
py scripts\xafs.py init       # 生成/更新 data/meta.csv 与 config.json
py scripts\xafs.py list       # 看样品汇总
```

打开 `data/meta.csv` 检查：
- `sample`：同名多行 = 同一样品多次扫描，会被合并；
- `role`：参比为 `reference`，标样 `standard`，样品 `sample`；
- `ref_file`：每条谱用来校准的参比（默认同批次参比；为空的谱不能处理）。

打开 `config.json` 检查该吸收边的 `elements_in_sample`（样品中全部元素，用于干扰边检查）。

```
py scripts\xafs.py qc                  # → results/qc_report.csv（毛刺、掉束、边跳、k 上限）
py scripts\xafs.py kcheck --edge Ta_L3 # 干扰吸收边 → k 上限
py scripts\xafs.py calib               # → results/calib.json（每个参比一个 ΔE）
py scripts\xafs.py process             # → results/processed/、figs/
```

## 4. 拟合一个标样

```
py scripts\xafs.py feff --builtin KTaO3 --absorber Ta --edge L3     # 或 --cif 你的结构.cif
```

复制一个模型模板（例如 `notes/KTaO3_1shell.json`），把 `"sample"` 改成 meta.csv 中的样品名，然后：

```
py scripts\xafs.py fit notes\我的模型.json
```

输出：`results/exafs_fits.csv`（一行一个拟合）、`results/<模型名>.fit_report.txt`、`figs/<模型名>_fit.png`。

模型写法（参数固定 / 约束 / 配位数）见 `AGENTS.md` 第 4 节。要点：
- 参数写数字 = 自由变化；`{"value": 0.68, "vary": false}` = 固定；写字符串（如 `"dr1"`、`"ss1*1.5"`）= 约束；
- 路径加 `"N": "6"` 固定配位数，`"N": "n1"` 让配位数变化；
- 变量数 ≤ N_idp/2；加壳层后用 `py scripts\xafs.py ftest 小模型.json 大模型.json`，p < 0.05 才算显著。

S0² 先在结构已知的标样上定（S0² 自由），之后样品拟合固定为该值（写入 `config.json` 的 `s02_recommended`）。

## 5. 图形界面

```
py scripts\xafs.py gui
```

浏览器打开 http://localhost:8501。左侧 11 页：
数据导入（必须同时选参比）→ 质量检查 → 能量校准 → 归一化 → χ(k)/FT → 小波 → FEFF → EXAFS 拟合 → 拟合历史/F 检验 → LCF → 样品设计。

按 meta.csv 载入的样品与命令行处理结果完全相同。

## 6. 让 AI 助手接手

把项目文件夹交给 AI（Claude Code、Codex、Cursor 等），告诉它“先读 AGENTS.md”。
`AGENTS.md` 写明了流程、命令、文件约定与判读规则（例如 R 空间峰位未相移校正、加壳层要做 F 检验、实测/拟合/推测分开陈述）。

## 7. 自检

```
py scripts\test_gui.py          # 应输出“全部通过”（需要本项目的 data/raw 与 feff/）
```

## 常见问题

| 现象 | 处理 |
|---|---|
| `meta.csv 未指定参比 ref_file，不能校准` | 该批次没有参比文件：放入同批参比后重新 `init`，或在 meta.csv 的 `ref_file` 填参比路径 |
| `KeyError: meta.csv 中没有可用的样品 X` | 样品名与 meta.csv 不一致（`xafs.py list` 查看） |
| 新批次样品与旧批次重名 | `init` 会自动加批次后缀（如 `KTaO3_20261105_Ta`），避免误合并 |
| 某条谱有毛刺 | 在 `config.json` 的 `deglitch` 中写能量区间与理由，见 AGENTS.md 第 6 节 |
| FEFF 无路径 / 报错 | 检查结构是否含吸收原子；RMAX 不宜 > 8 Å |
