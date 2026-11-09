# XAFSmith

**给化学、材料研究者的 XAFS 数据处理与拟合软件：不写代码、不敲命令，用鼠标完成从原始数据到论文图表的全流程。**

XANES 与 EXAFS 都能做：能量校准、归一化、χ(k)、傅里叶变换、小波变换、FEFF 计算、EXAFS 拟合、线性组合拟合、价态估算、期刊出图、汇总报告。
计算核心是同步辐射领域广泛使用的 [Larch](https://xraypy.github.io/xraylarch/)（xraylarch）与 FEFF，结果可以导出到 Athena / Artemis 中对照。

> [!WARNING]
> **免责声明** —— 本软件按“现状”提供，不附带任何保证；作者不对使用本软件得到的结果负责。
> 请自行核验结果，**关键结果建议与 Athena / Artemis 对比**（软件可一键导出 Athena 工程文件，见下文）。

---

## 为什么用 XAFSmith

如果你用过 Athena 和 Artemis，下面这些事在 XAFSmith 里会省很多时间：

| 你要做的事 | Athena / Artemis 中通常 | XAFSmith 中 |
|---|---|---|
| 一个机时测了几十条谱，要校准、归一化、合并 | 导入后逐组标记参比、对齐、设置参数、合并，再保存工程 | 文件放进文件夹 → 点 **扫描登记** → 点 **一键处理**：所有谱按同批次参比自动校准、同一套参数归一化、多次扫描自动合并（异常扫描自动剔除并记录理由） |
| 保证一组样品用的是**同一套**处理参数 | 靠自己逐个检查 | 每个吸收边一套参数存在项目文件里，所有样品自动共用；个别例外必须写明理由 |
| 同一个拟合模型用于一组样品（时间、电位、温度序列） | 通常逐个样品复制、调整拟合 | 拟合页 **运行已保存的模型** → 多选样品 → 一次跑完 |
| FEFF 计算 | Atoms 由 CIF 生成输入，再运行 FEFF | 选 CIF 或内置结构 → 选吸收原子和吸收边 → 一键计算；**内置 FEFF6L（几秒）和 FEFF8L（自洽势）两种**，可直接比较，无需另装 FEFF |
| 小波变换（区分轻 / 重散射体、重叠壳层） | 需借助其他程序 | ⑥ 页直接计算（Morlet / Cauchy 母小波） |
| 判断拟合好不好、为什么对不上 | 主要看 R 因子与经验 | **拟合诊断**：残差与噪声之比、k 空间残差图（自动定位毛刺并换算成能量）、分段失配表、改进建议；**稳健性检查**：自动改变 k/R 范围重复拟合，标出不可靠的参数；F 检验一键完成 |
| 出论文图、写方法部分 | 导出数据再用 Origin 等重新画；方法自己写 | **一键期刊出图**（单栏 / 双栏，600 dpi TIFF、SVG、PDF，自动英文图注）；**一键生成中英文“实验方法”段落**（按实际参数填写） |
| 整理全部结果 | 手工抄表 | **一键汇总报告**：Excel + 带图 HTML，所有拟合参数、误差、R 因子、N_idp 一张表 |
| 和 Athena / Artemis 对照 | — | **一键导出 Athena 工程（.prj）**，带上本软件的 E0、归一化、背景、k 范围参数 |
| 半年后重现结果 | 找当时的工程文件、回忆参数 | 原始数据只读，所有参数写在项目文件里，结果随时可以从原始数据重新生成 |

此外：
- **XANES 定量**：边位置（一阶导数最大值 / 半高点）、白线位置·高度·面积、用实测标样标定价态、边前峰拟合、XANES / 导数 / χ(k) 线性组合拟合（含所有标样组合的自动枚举）。
- **样品设计**：输入成分和质量，计算总 μt、边跳、推荐压片质量，检查邻近吸收边对 k 范围的限制。
- **质量检查**：自动检测毛刺、I0 掉束、边跳、信噪比可用的 k 上限、荧光自吸收风险；图形界面中可视化**去毛刺**（区间与理由写入项目，原始文件不动）。
- **中文 / English 界面**一键切换；软件内**检查更新、一键升级**。

## AI 助手可以直接帮你分析

XAFSmith 的项目是**标准化的文件夹**：数据登记表、处理参数、拟合模型都是普通文本文件，并附带写给 AI 的说明（`AGENTS.md`）。
因此 Claude Code、Codex、Cursor 等 AI 编程助手可以直接读懂你的项目，替你：

- 检查数据质量、发现异常扫描和毛刺；
- 搭建并比较拟合模型、做 F 检验和稳健性检查；
- 批量处理一个序列、汇总趋势、出图；
- 用“实测 / 拟合 / 推测”三类分清结论，写分析记录。

AI 做的每一步都落在项目文件里，你可以随时**在图形界面中打开、检查、修改、重跑**，不会变成看不见的黑箱。
不用 AI 也完全可以：所有功能都能在图形界面里用鼠标完成。

---

## 安装（Windows，约 15 分钟，只需一次）

1. **安装 Python**（XAFSmith 运行所需的免费环境）：打开 <https://www.python.org/downloads/windows/>，下载 Python 3.11 或 3.12 安装包。
   安装第一屏**一定要勾选 “Add python.exe to PATH”**，然后点 Install Now。
2. **下载 XAFSmith**：本页上方绿色按钮 **Code → Download ZIP**，解压到任意位置。
3. **双击解压文件夹里的 `安装XAFSmith.bat`**，出现安装向导：选择安装位置和快捷方式 → 阅读并同意免责声明 → **安装**（需要联网，5–15 分钟）。
4. 装好后，**双击桌面上的 XAFSmith 图标**，软件在独立窗口中打开。解压的文件夹可以删除。

卸载：开始菜单 → XAFSmith → 卸载 XAFSmith（只删软件，不删你的数据）。

> macOS / Linux 目前没有安装向导，需要用命令行安装，见 [命令行速查](src/xafsmith/docs/命令行速查.md)。

## 第一次使用

**→ [快速上手（QUICKSTART）](QUICKSTART.md)**：用一个标样和一个样品，从建项目走到第一次拟合，约 30 分钟。

然后按需要阅读（这些文档在软件左侧 **❓ 使用指南** 里也都能看到）：

| 文档 | 适合 |
|---|---|
| [图形界面使用指南](src/xafsmith/docs/图形界面使用指南.md) | 每一页、每个按钮的用法 |
| [零基础拟合教程](src/xafsmith/docs/零基础拟合教程.md) | 第一次做 EXAFS 拟合：每一步的原理、参数怎么取、怎么判断做对了 |
| [拟合质量提升教程](src/xafsmith/docs/拟合质量提升教程.md) | 拟合曲线和数据对不严时：诊断残差、去毛刺、FEFF6/FEFF8、什么时候加路径、什么时候停 |
| [数据标准](src/xafsmith/docs/数据标准.md) | 项目文件夹里每个文件的含义 |
| [命令行速查](src/xafsmith/docs/命令行速查.md) | 会用命令行、想批处理的人 |

## 支持的数据

- 北京同步辐射装置（BSRF）等束线输出的文本文件（自动识别透射 / 荧光）；
- 通用列文本（能量 + I0 + I1 / If，或直接 μ）；
- Athena 工程文件 `.prj`。

每次测量请**同时测对应的单质参比**（金属箔或粉末），软件用它做能量校准。

## 验证

- 与 Artemis 对照（IrO2，相同 k/R 范围与 k 权重）：S0² 0.80 ± 0.11 vs 0.86 ± 0.09，ΔE0 9.2 vs 10.2 eV，ΔR −0.012 vs −0.010 Å，误差范围内一致。
- 标样多壳层拟合（金红石 IrO2、立方钙钛矿 KTaO3）给出与晶体学一致的配位数与键长。
- 每次发布前运行图形界面逐页自动测试（中文与英文界面）。

## 引用

论文中使用本软件，请引用本仓库（GitHub 页面右侧 **Cite this repository**）：

*Eggy & Claude. XAFSmith: XAFS processing and fitting software, version 0.3.0. https://github.com/Wiolic/XAFSmith*

并引用所依赖的程序：
- Larch：M. Newville, *J. Phys.: Conf. Ser.* **430**, 012007 (2013).
- FEFF6：S. I. Zabinsky, J. J. Rehr, A. Ankudinov, R. C. Albers, M. J. Eller, *Phys. Rev. B* **52**, 2995 (1995).
- 使用 FEFF8L 时另引 FEFF8：A. L. Ankudinov, B. Ravel, J. J. Rehr, S. D. Conradson, *Phys. Rev. B* **58**, 7565 (1998).

软件内 **⓪ 项目** 页的“引用格式”可以直接复制。

## 作者与许可

Developed by **Eggy** & **Claude** (Anthropic). [MIT License](LICENSE)：可以自由使用、修改、分发（含商业用途），保留版权与许可声明即可。

---

### English summary

XAFSmith is a point-and-click XAFS (XANES + EXAFS) package for chemists and materials scientists, built on Larch and FEFF.
Compared with a typical Athena/Artemis workflow it offers one-click batch calibration, normalization and merging with a single parameter set per edge;
FEFF6L **or FEFF8L** (self-consistent) path calculations without a separate FEFF install; wavelet transforms; one model applied to a whole sample series;
fit diagnosis, robustness checks and F-tests; journal-style figures, a methods paragraph and an Excel/HTML summary in one click; and export to Athena `.prj` for cross-checking.
Projects are plain, standardized folders, so AI coding assistants (Claude Code, Codex, Cursor, …) can work on them alongside you.
Windows installer: download the ZIP, double-click `安装XAFSmith.bat`. The interface switches between Chinese and English (sidebar, top).
Guides: [GUI guide](src/xafsmith/docs/GUI_guide_en.md), [fitting tutorial](src/xafsmith/docs/fitting_tutorial_en.md), [improving fit quality](src/xafsmith/docs/fit_quality_guide_en.md).
