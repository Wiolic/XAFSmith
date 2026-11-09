# Quickstart（命令行）

> **只用鼠标的用户请看 [图形界面使用指南](src/xafsmith/docs/图形界面使用指南.md)**：双击安装、双击启动，全流程在图形界面里点击完成。

本文是命令行版本：安装 → 建项目 → 放数据 → 校准与处理 → 拟合一个标样 → 图形界面。

## 1. 安装（Python ≥ 3.10）

```
python -m venv .venv
.venv\Scripts\python -m pip install git+https://github.com/Wiolic/XAFSmith.git
.venv\Scripts\xafsmith --help
```

macOS / Linux：`.venv/bin/...`。下文 `xafsmith` 指 venv 中的这个命令（也可以先激活 venv）。

## 2. 新建项目

```
xafsmith new D:\XAFS\my_project
cd D:\XAFS\my_project
```

生成 `xafsmith.json`、`project.md`、`data/`、`structures/`、`models/`（含 `_模板.json`）、`notes/`、`output/`，
以及双击即可打开图形界面的 `打开图形界面.bat`。之后在项目目录里运行命令即可，不必再写 `--project`。

## 3. 放入原始数据

每次测量一个文件夹，**带上该批次测的单质参比**（金属箔或粉，文件名含 `foil` / `powder` / `metal`）：

```
data/raw/2026-11-05_Ta/
    Ta_foil          ← 参比
    KTaO3            ← 标样
    sample_A  sample_A_2  ...
```

原始文件只读，XAFSmith 不会修改它们。

## 4. 登记、检查、校准、处理

```
xafsmith init         # → data/meta.csv、xafsmith.json
xafsmith validate     # 按数据标准检查
```

检查 `data/meta.csv`：
- `sample`：同名多行 = 同一样品多次扫描，会合并；不想合并就改名；
- `role`：参比 `reference`、标样 `standard`、样品 `sample`；
- `ref_file`：每条谱的校准参比（默认同批次）；为空的谱不能处理。

检查 `xafsmith.json` 中该吸收边的 `elements_in_sample`（样品里的全部元素）。

```
xafsmith qc                   # → output/qc/
xafsmith kcheck --edge Ta_L3  # 干扰吸收边 → k 上限
xafsmith calib                # → output/calib/calib.json
xafsmith process              # → output/processed/、output/figs/
```

## 5. 拟合一个标样

结构文件放进 `structures/`（或用内置结构）：

```
xafsmith feff --structure KTaO3.cif --absorber Ta --edge L3     # 或 --builtin KTaO3
```

复制 `models/_模板.json` 为 `models/KTaO3_1shell.json`，改 `sample` 和路径文件，然后：

```
xafsmith fit KTaO3_1shell
```

输出：`output/fits/exafs_fits.csv`、`output/fits/KTaO3_1shell.fit_report.txt`、`output/figs/KTaO3_1shell_fit.png`。

- 参数写数字 = 自由；`{"value": 0.68, "vary": false}` = 固定；字符串 `"dr1"`、`"ss1*1.5"` = 约束；
- 路径 `"N": "6"` 固定配位数，`"N": "n1"` 让它变化；
- 变量数 ≤ N_idp/2；加壳层用 `xafsmith ftest 小模型 大模型`，p < 0.05 才显著。

标样上定出的 S0² 写进 `xafsmith.json` 的 `s02_recommended`，样品拟合时固定为该值。

## 6. 图形界面

```
xafsmith gui
```

浏览器打开 http://localhost:8501（或双击项目中的 `打开图形界面.bat`）。数据导入时必须同时选参比。

## 7. 交给 AI 助手

在项目目录里让 AI（Claude Code、Codex、Cursor 等）先读 `AGENTS.md`，再运行 `xafsmith docs` 找到手册与数据标准。

## 8. 常见问题

| 现象 | 处理 |
|---|---|
| `未指定参比 ref_file，不能校准` | 批次缺参比：放入同批参比后 `xafsmith init`，或在 meta.csv 手填 `ref_file` |
| `meta.csv 中没有可用的样品 X` | 样品名不一致（`xafsmith list`） |
| 找不到项目 / 结果写到了别处 | `xafsmith paths` 查看；在项目目录内运行或加 `--project` |
| 有毛刺 | `xafsmith.json` 的 `deglitch` 写能量区间与理由 |
| FEFF 无路径 | 结构是否含吸收原子；RMAX 不宜 > 8 Å |
