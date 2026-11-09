# XAFSmith

通用 XAFS（XANES + EXAFS）数据处理与拟合软件：桌面图形界面（类似 Athena / Artemis，独立窗口）+ 命令行 `xafsmith`，
基于 [xraylarch](https://xraypy.github.io/xraylarch/)（FEFF6L、feffit）、xraydb、lmfit、pymatgen 与 Streamlit。

- **可复现**：所有处理参数写在项目的 `xafsmith.json`，原始数据只读，结果统一写入 `output/`，随时可以重新生成。
- **标准化**：固定的项目目录、数据登记表、拟合模型格式（[数据标准](src/xafsmith/docs/数据标准.md)），`xafsmith validate` 自动检查。
- **AI 友好**：任何 AI 助手按[操作手册](src/xafsmith/docs/手册.md)调用命令即可接手分析。

> [!WARNING]
> **免责声明 / Disclaimer** —— 本软件按“现状”提供，不附带任何形式的保证；作者不对使用本软件得到的任何结果负责。
> 请自行核验结果，**建议将关键结果与 Athena / Artemis（Demeter）的结果对比**。
> XAFSmith is provided "as is", without warranty of any kind; the authors accept no responsibility for results
> obtained with it. Please cross-check key results against Athena / Artemis.

> [!NOTE]
> **引用 / Citation** —— 如果在论文中使用了本软件，请引用本仓库（GitHub 页面右侧 “Cite this repository”）：
> *Eggy & Claude. XAFSmith: XAFS processing and fitting software, version 0.1.0. https://github.com/Wiolic/XAFSmith*
> 同时请引用其依赖的 Larch（M. Newville, J. Phys.: Conf. Ser. 430, 012007 (2013)）与 FEFF6
> （S. I. Zabinsky et al., Phys. Rev. B 52, 2995 (1995)）。
> If you use XAFSmith in a publication, please cite this repository, as well as Larch and FEFF.

## 不会编程？只用鼠标就能完成全流程

1. 安装 [Python 3.11/3.12](https://www.python.org/downloads/windows/)（安装时勾选 **Add python.exe to PATH**）。
2. 本页点绿色 **Code → Download ZIP**，解压。
3. 双击 **`安装XAFSmith.bat`** → 安装向导中选择安装位置、是否创建桌面/开始菜单快捷方式 → 安装（5–15 分钟）。
4. 双击桌面图标 → 软件在独立窗口中打开 → 左侧 **⓪ 项目** 新建项目 → 上传数据 → 一键处理 → FEFF → 拟合 → **⑫ 汇总报告**（Excel + HTML）。

逐步图文说明：**[图形界面使用指南](src/xafsmith/docs/图形界面使用指南.md)**；第一次做拟合请看 **[零基础拟合教程](src/xafsmith/docs/零基础拟合教程.md)**（每一步的原理与判断标准）。两者在软件左侧“❓ 使用指南”中都能看到。

## 命令行安装（开发者 / 批处理）

```
python -m venv .venv
.venv\Scripts\python -m pip install git+https://github.com/Wiolic/XAFSmith.git
```

或 `git clone` 后 `pip install -e .`。需要 Python ≥ 3.10。FEFF6L 随 xraylarch 安装。命令行用法见 [QUICKSTART.md](QUICKSTART.md)。

## 一个项目长这样

```
my_project/
├── xafsmith.json      处理参数（每个吸收边一套）
├── project.md         体系信息
├── data/raw/<批次>/   原始数据（只读，每个批次带单质参比）
├── data/meta.csv      数据登记表
├── structures/        CIF / POSCAR 等结构文件
├── models/            拟合模型 JSON
├── notes/             分析记录
└── output/            全部结果：qc/ calib/ processed/ feff/ fits/ lcf/ figs/ reports/
```

`xafsmith new my_project` 一步生成。

## 功能

| 环节 | 内容 |
|---|---|
| 读入 | BSRF 文本、通用列文本、Athena `.prj`；透射 / 荧光 |
| 质量检查 | 毛刺、I0 掉束、边跳、荧光自吸收风险、信噪比可用 k 上限 |
| 能量校准 | 每条谱用**同批次单质参比**的一阶导数最大值校准，ΔE 按参比文件记录 |
| 归一化 / 合并 | 统一参数；多次扫描合并并自动剔除异常扫描（记录理由） |
| χ(k) / FT / 小波 | AUTOBK、Hanning/Kaiser 窗 FT（标注“未相移校正”）、Morlet/Cauchy 小波 |
| FEFF | `structures/` 中的 CIF/POSCAR 或内置结构 → FEFF6L 路径（按不等价位点） |
| EXAFS 拟合 | JSON 模型：路径、参数固定/约束、多 k 权重同时拟合；N_idp 检查、F 检验 |
| LCF | XANES / 导数 / χ(k)，含单一标样比较与组合枚举 |
| 样品设计 | μt、边跳、推荐压片质量、干扰吸收边与 k 上限 |
| XANES 定量 | 边位置（导数最大值 / 半高点）、白线峰位·峰高·面积、按实测标样做价态标定、边前峰拟合 |
| 稳健性检查 | 改变 k/R 范围与 k 权重重复拟合，标出随条件变化超过统计误差的参数 |
| 报告 | 16:9 汇报图；期刊风格出图（单栏/双栏，600 dpi TIFF、SVG、PDF，自动英文图注）；一键汇总为 Excel + 带图 HTML |
| 方法段落 | 按项目实际参数自动生成中英文“实验方法”草稿（仪器信息占位，需人工核对） |
| 与 Athena 对照 | 导出 Athena 工程 `.prj`（带本软件的 E0、归一化、rbkg、k 范围），可直接在 Athena / Artemis 中对比 |
| 界面 | 中文 / English 一键切换；启动时可检查 GitHub 新版本并一键更新 |

## 命令

```
xafsmith new <目录> | init | validate | paths | list
xafsmith qc | kcheck --edge E | calib | process
xafsmith structures [--export] | feff --structure X.cif --absorber Ta --edge L3
xafsmith fit <模型> | ftest <小> <大> | robust <模型> | lcf --sample S --standards A B | plan ...
xafsmith xanes --samples A B [--valence A=2 B=3] | export-prj --samples A B | methods
xafsmith gui | docs | cite | update [--check]
```

## 仓库结构

```
XAFSmith/
├── pyproject.toml
├── README.md  QUICKSTART.md  AGENTS.md
├── 安装XAFSmith.bat  installer.py          双击打开安装向导（安装位置、快捷方式、卸载）
├── 启动XAFSmith.bat                       双击启动（桌面窗口）
├── src/xafsmith/
│   ├── cli.py  gui.py  desktop.py  paths.py  schema.py  pipeline.py  summary.py
│   ├── io.py qc.py calib.py normalize.py autobk.py ft.py wavelet.py
│   ├── structures.py feff_wrap.py fit_exafs.py fit_lcf.py mut_planner.py report.py common.py
│   ├── templates/     新项目模板
│   └── docs/          图形界面使用指南.md  零基础拟合教程.md  数据标准.md  手册.md  XAFS处理规范.md
└── tests/test_gui.py  图形界面逐页测试（需要一个有数据的项目）
```

## 验证

- 与 Artemis 对照（IrO2，同一 k/R 范围与 k 权重）：S0² 0.80 ± 0.11 vs 0.86 ± 0.09，ΔE0 9.2 vs 10.2 eV，ΔR −0.012 vs −0.010 Å，误差内一致。
- 标样多壳层拟合（金红石 IrO2、立方钙钛矿 KTaO3）给出与晶体学一致的配位与键长。

## 作者

Developed by **Eggy** & **Claude** (Anthropic).

## 许可

[MIT License](LICENSE)：可以自由使用、复制、修改、分发（含商业用途），只需保留版权与许可声明。
软件按“现状”提供，不附带任何保证；作者不对使用结果负责（见上方免责声明）。
