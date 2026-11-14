# 更新日志 / Changelog

本项目的重要变化都记录在这里。格式参考 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.1.0/)，版本号遵循
[语义化版本](https://semver.org/lang/zh-CN/)。
All notable changes are recorded here (format: Keep a Changelog; versioning: SemVer).

## [未发布 / Unreleased]

### 新增 / Added
- **清空工作区**（“载入谱”页“已载入”卡片右上角，和左上角流程弹窗“本项目”一栏）：确认后移出全部已载入的谱、本次拟合与各页设置，并删除上次的会话快照，回到“载入谱”页，便于在同一项目里换一批样品从头处理；原始数据、meta.csv、xafsmith.json、output/ 与拟合草稿都不动。恢复上次状态的提示里也指向这个按钮。
  **Clear workspace** (Load spectra page and the flow pop-up): removes all loaded spectra, fits of this session and page settings, and deletes the saved session snapshot, to start over with other samples in the same project; files, output/ and fit drafts are kept.
- **关闭时询问是否保存进度**：有载入的谱或拟合时关闭窗口，弹框选择“保存”（下次打开自动恢复）/“不保存”（删除快照，下次从空白开始）/“取消”；可勾选“记住选择”，在“项目”页“关闭窗口时保存当前进度”改回（每次询问 / 总是保存 / 不保存）。设置键 `close_action`。
  **Ask to save progress on close** (Save / Don't save / Cancel, with “remember”; Project-page setting `close_action`: ask / save / discard).
- **启动画面**：从桌面或开始菜单打开时先显示 XAFSmith 启动画面，再载入 pandas / SciPy / Larch 等大库，冷启动时不再像“没反应”。
  **Splash screen** shown before the heavy imports.

### 改进 / Changed
- **许可证改为 GPL-3.0-only**（自 v1.3.1 起；作者另提供商业授权；v0.5.1–v1.3.0 仍为 PolyForm Noncommercial，已发出的版本不变）：LICENSE、NOTICE、README、关于对话框、安装程序同步更新；“论文中引用”改为引用请求，不再是许可条件。
  **License changed to GPL-3.0-only** (from v1.3.1; commercial licenses also offered by the author; v0.5.1–v1.3.0 remain PolyForm Noncommercial, released versions are unchanged): LICENSE, NOTICE, READMEs, About dialog and installer updated; citing in publications is now a request, not a license condition.
- `normalize` 模块不在导入时载入 Larch / SciPy（只在函数里用到时导入），图形界面窗口出现前少等约 0.3 s。
  `normalize` imports Larch / SciPy lazily, so the main window appears sooner.

## [1.3.0] — 2026-11-14

### 新增 / Added
- 多重散射绑定向导：`msbind` 模块、`xafsmith msbind 模型名 [--dataset ID] [--out 新模型]`、拟合页 **多重散射绑定…** 按钮与对话框：按 FEFF 路径几何给已勾选的多重散射路径建议 `deltar` / `sigma2` 表达式并写明依据（ΔR 按腿：共线精确 / 等价键 / 键角不变；σ² 独立键近似），点“应用”才改表；`--out` 另存新模型、不覆盖。路径新增可选字段 `note`。
  Multiple-scattering binding wizard (`msbind`, `xafsmith msbind`, fit-page dialog): suggests deltar / sigma2 expressions for multiple-scattering paths from the FEFF geometry, with the basis; nothing changes until Apply. Optional path field `note`.
- σ² 的 Debye / Einstein 温度模型：路径 σ² 可写 `sigma2_debye(tempK, θ)` / `sigma2_eins(tempK, θ)`，数据集字段 `temperature`（数据标准 4.3）；`xafsmith sigma2`（σ²(T) 表、由 σ² 反算 θ）；拟合页“使用 σ² 温度模型”勾选、每个数据集的温度与 **σ² 模型…** 对话框；结果区 **σ²(T)** 图；7 条校验与 Einstein 用于多重散射时的警告。
  Debye / Einstein σ² temperature models (`sigma2_debye` / `sigma2_eins`, dataset `temperature`, `xafsmith sigma2`, fit-page switch and dialog, σ²(T) plot, validation).
- 序列趋势与联合拟合序列工具：`trend` 模块与 `xafsmith trend 联合模型 [--seq-label] [--panels] [--nosave]`；联合拟合结果区 **趋势** 页与图片导出页 **趋势图**（N、R、σ²、ΔE0 与实测边位置随序列变量变化，1σ 误差棒，固定 N 不画误差棒，共享参数在页面与图注中标明）；Origin 工程导出误差棒（X / Y / yErr 列，线 + 符号）；`output/fits/<模型>_trend.csv`（保存联合拟合时也写）；meta.csv 可选列 `seq`（横轴：seq → 测量时间 → 数据集顺序，不混用）；拟合页 **勾选同步到所有数据集** 开关与 **σ² 各数据集独立** 按钮（`ss1` → `ss1_<数据集 id>`）。
  Series trends for joint fits: `trend` module and `xafsmith trend`; a Trend tab and a Trend figure (N, R, σ², ΔE0 and edge position vs. the series variable with 1σ error bars; fixed N without bars; shared parameters marked); error bars in the Origin export; `<model>_trend.csv`; optional meta.csv column `seq`; fit-page switch to sync ticked paths and a one-click “Independent σ² per dataset”.
- 文档：《多样品联合拟合指南》/ “Joint fitting of a series”（帮助页可达）；基础讲义 7.1 讲解 σ²；图形界面使用指南、数据标准、命令行速查、ARCHITECTURE 同步更新。
  Docs: a step-by-step guide to joint fitting of a sample series (on the help page); σ² section in the XAFS basics; GUI guides, data standard, CLI cheat sheet and ARCHITECTURE updated.

### 修复 / Fixed
- larch 的 σ² 函数在一个拟合里有几条路径时共用一条路径的几何（悄悄算错）：`build_paths` 现按每条路径的几何展开 `sigma2_debye/eins`，与 larch 对单条路径的直接计算逐位相同。
  larch's σ² functions shared one path's geometry when several paths used them (silently wrong); they are now expanded per path geometry, bit-identical to larch's single-path result.
- `msbind.equivalent` 对含 `sqrt` 等函数的表达式误判；建议值的 `:.4g` 取整不再改写用户原有的等价表达式。
  `msbind.equivalent` misjudged expressions with `sqrt`; the user's exact equivalent expression is kept.

### 说明 / Notes
- 已有模型的拟合数值与 `exafs_fits.csv` 的列不变（IrO2 回归 S0² 0.816、ΔE0 8.93）。
  Existing fit results and `exafs_fits.csv` columns are unchanged.
- Origin 工程中误差棒的线宽与端帽宽尚未按统一样式设置（使用 Origin 缺省）；打包版未做冒烟测试。
  Error-bar line and cap widths in the Origin project still use Origin's defaults; the frozen build was not smoke-tested.

## [1.2.0] — 2026-11-13

### 新增 / Added
- 多模型比较：`xafsmith compare M1 M2 […]` 与拟合历史页“模型比较表”卡片，按变量数升序列出 R 因子、χ²_ν、χ²、变量数、N_idp、软约束个数与相邻模型的 F 检验（调用原 Hamilton 检验，数值不变）；数据或拟合范围不同、软约束不同、变量数相同时不做 F 检验并写明原因；`ftest` 的两条提示抽成 `ftest_blockers`，输出逐字不变，F 检验卡片也显示同样的警告。F 检验只对嵌套模型有效，软件不检查嵌套关系。
  Model comparison: `xafsmith compare M1 M2 […]` and a “Model comparison” card on the Fit history page list R-factor, χ²_ν, χ², variables, N_idp, restraints and the F-test against the previous model (existing Hamilton test, numbers unchanged); no F-test when data/ranges or restraints differ or the variable count is equal, with the reason shown; `ftest` output is unchanged and its card now shows the same warnings. The F-test is valid only for nested models; nesting is not checked.
- 拟合软约束（restraint）：模型 JSON 顶层 `restraints`（`expr`、`value`、`sigma`），在 χ² 中加入 c₀·((expr − value)/σ)²，c₀ = 无约束预拟合的 χ²_ν，使 σ 与报告的参数误差同一尺度；不计入 N_idp，R 因子只计数据；摘要、CSV、报告、方法与 SI 文本、`xafsmith validate` 与 `ftest` 都已适配；图形界面在拟合页参数表下加软约束表。没有 `restraints` 的模型与以前逐位相同（自带 feffit 驱动 `_feffit_restrained.py`，由测试保证空约束时与 larch 逐位一致）。
  EXAFS fit restraints: a top-level `restraints` list in the model JSON adds c0·((expr − value)/σ)² to χ², with c0 = χ²_ν of the unrestrained pre-fit so that σ is on the scale of the reported errors; not counted in N_idp, R-factor over data only; summaries, CSV, reports, methods/SI text, `validate`, `ftest` and a restraint table on the GUI fit page are updated. Models without `restraints` are bit-identical to before.
- 图形界面：拟合页支持多数据集联合拟合——单个 / 多个数据集开关，路径表按数据集分标签页（可覆盖各自的 k/R 范围），参数表共享，右栏显示联合指标并可按数据集切换图、路径、质量检查与诊断；保存时每个数据集一张图；多数据集模型可在“运行已保存的模型”里运行；草稿与自动恢复含多数据集设置。多数据集模型的稳健性检查暂不支持。
  GUI: the fit page supports joint multi-dataset fitting (single / joint switch, per-dataset path tabs with range overrides, shared parameter table, joint metrics with a per-dataset view, one figure per dataset on save, saved multi-dataset models runnable, drafts keep the settings). Robustness checks for multi-dataset models are not yet supported.
- 多数据集同时拟合：模型 JSON 新增 `datasets`（各自样品、路径、k/R 范围，共享 `params`），`xafsmith fit` / `diagnose` / `figure --dataset` 支持；逐数据集报告 N_idp、R 因子、χ² 占比，失配主导误差缩放与同一数据重复使用时警告；`xafsmith validate` 增加对应校验。旧模型原样可跑，结果与 v1.1 逐位一致。
  Multi-dataset (joint) EXAFS fitting via a `datasets` list in the model JSON; old models run unchanged and bit-identical to v1.1.
- 单元测试：normalize、autobk、ft、calib、fit_lcf、xanes、mut_planner 各一个文件（与直接调用 Larch / xraydb 逐位一致、合成真值、物理不变量）。
  Unit tests for normalize, autobk, ft, calib, fit_lcf, xanes and mut_planner.
- 基准测试：Fe K 边 LCF（公开 FeO / Fe2O3 / Fe3C 端点合成混合物还原比例）与边位置–价态标定。
  Benchmarks: Fe K-edge LCF recovery on synthetic mixtures and edge-position valence calibration.
- XAFS处理规范：混合物报告价态用半高点 E_half，不用一阶导数最大值。Processing rules: use E_half, not E0_deriv, for mixed-valence samples.
- 拟合注意事项窗口改为三个标签页：拟合前（新增数据检查、k 上限、荧光自吸收、同一模型比较、换 FEFF 版本重定 ΔE0 等）、拟合得好的标准（新增 F 检验报告规则、误差来源、模型无关指标、三类陈述）、多数据集联合拟合（何时用、怎么设、共享什么、统计与三类 F 检验）。
  The fit guide window now has three tabs: before fitting, what is a good fit, and joint fits (updated and extended content).

### 修复 / Fixed
- 下拉多选（拟合页的数据与 FEFF 目录、方法导出的拟合选择）勾一项就关闭，现在关闭列表后才更新页面；多数据集拟合的“稳健性”页把上方拟合图挤扁；多数据集拟合的质量检查把共享变量数与单个数据集的 N_idp 比较（现与合计 N_idp 比较）。
  Multi-select lists no longer close after each tick; the joint-fit Robustness tab no longer squeezes the plot; joint-fit quality checks compare variables with the summed N_idp.
- `methods_text` 判断 FEFF 版本时兼容多数据集模型（否则会静默回退成 feff6）。
  methods_text now finds the FEFF code for multi-dataset models.
- k–E 换算常数统一为与 Larch 相同的 2mₑ/ħ²（scipy CODATA）；原 `common.ETOK` 与 Larch 差 5×10⁻⁷，另有三处写死 0.2625（.prj 导出的 kmax、毛刺能量显示、干扰边默认范围）。影响 ≤ 0.03%。
  The k–E constant now matches Larch exactly (it differed by 5e-7, and three places hard-coded 0.2625).
- 旧格式（单数据集）模型的路径 N 改用与多数据集相同的参考 S0²：路径的 `s02` 字段若就是一个参数名，N = 振幅 / 该参数；否则仍用全局 S0²（参数 s02 / amp / s0_2 / S02）。此前旧格式总用全局 S0²，同一模型两种格式的 N 不同；只影响给路径单独写了振幅参数名（且不是 s02）的模型。
  Old-format models now use the same S0² reference for path N as multi-dataset models (the path's own amplitude parameter when its `s02` is a parameter name).
- 拟合历史页“模型比较”保存 CSV 时同时写 `model_compare.params.json`（与 `xafsmith compare` 相同）。
  Saving the GUI model comparison also writes model_compare.params.json.

## [1.1.0] — 2026-11-12

界面美化与交互改进。UI polish and interaction fixes.

### 新增 / Added
- 图片导出：“作图顺序”列表，可拖动或用 ↑ / ↓ / 倒序调整图中样品的顺序（图例、导出文件与 Origin 工程同步）。
  Figure export: reorder the spectra in the figure (drag, up/down, reverse).
- 帮助窗口：后退 / 前进、查找条（Ctrl+F）、右侧标题目录；讲义内的 `#锚点` 目录链接可跳转；文档首次点开时才渲染。
  Help window: back/forward, find bar, heading outline, working in-page anchor links, lazy document rendering.
- 未保存修改的询问（保存 / 放弃 / 取消）与“撤销修改”（meta.csv 表格、批处理参数）；移除谱、合并覆盖同名谱前确认。
  Save/Discard/Cancel prompt and "Undo edits" for the meta table and batch parameters; confirmations before removing or overwriting spectra.
- 归一化、背景、FT 参数卡的“恢复为 xafsmith.json 的值”。"Restore xafsmith.json values" on the parameter cards.
- 快捷键：F1、Ctrl+O、Ctrl+1…9、Esc、项目路径框回车。Keyboard shortcuts.
- 窗口位置与大小记忆（限制在屏幕可用区域内）。Window geometry is remembered and kept on screen.
- 导航按钮在缺前置数据时变灰并提示缺哪一步。Sidebar hints for missing prerequisites.

### 变更 / Changed
- 切页不再重建页面：只有数据变了才重建，只改了处理参数时只重画；输入、内页标签、滚动位置保留。
  Pages rebuild only when data changed; inputs, tabs and scroll position survive page switches.
- 后台任务按名字登记：同一任务不能重复启动，①②③ 批处理互斥；任务运行时不能切换项目或语言。
  Tasks are registered by key: no duplicate runs, batch steps are mutually exclusive, project/language switches wait for tasks.
- 提示方式统一：持续性错误显示为页顶可关闭的提示条，轻提示排队显示（不再互相覆盖）；帮助窗口也能显示提示。
  Persistent errors go to a dismissable page banner; toasts are queued; the help window shows toasts too.
- 参数即时重画加 250 ms 防抖；数值框未获得焦点时忽略滚轮；kmin/kmax、Rmin/Rmax、pre1/pre2、norm1/norm2 范围联动；E0 非法时红框提示。
  Debounced redraws, no accidental wheel edits, linked range limits, E0 validation.
- 状态栏进度条带百分比与已用时间，不可中断的步骤会注明；载入与 LCF 显示进度。
  Status-bar progress with percentage and elapsed time; load and LCF report progress.
- 只保留一套浅色主题（系统深色模式下也保持浅色）；颜色、字号（5 级）、间距、宽度统一收进 `theme.py`。
  Single light theme, locked even under Windows dark mode; colours, font sizes, spacing and widths as tokens in `theme.py`.
- 小波图改用 viridis；系列配色在白底上对比度均 ≥ 3:1；下拉框与菜单的圆角不再露方角；表格行高、列宽随字体。
  Wavelet map uses viridis; series colours ≥ 3:1 contrast; rounded popups; font-based table metrics.

### 修复 / Fixed
- 基础讲义插图模糊、有锯齿：插图改为 300 dpi，按窗口宽度平滑缩放成圆角卡片；公式改回 `$$…$$` 并按屏幕缩放渲染；图标与 logo 在高分屏上清晰。
  Sharp figures, formulas and icons in the basics notes and on high-DPI screens.
- 双语缺口：归一化页“flattened”、成图页尺寸判断与语言无关。Bilingual gaps in the normalization and figure pages.

## [1.0.1] — 2026-11-11

### 修复 / Fixed
- 新建项目不再生成“打开图形界面.bat”：它只认源码安装的 `.venv` / `location.txt`，用安装包安装时双击只会报错。
  请从开始菜单启动 XAFSmith，在“最近的项目”里打开项目。
  New projects no longer get the "打开图形界面.bat" launcher, which did not work with the Windows installer.

### 删除 / Removed
- 未使用的代码：`io.read_bsrf`、`io.read_columns`（按列号读，可能静默算错 μ）、`io.is_bsrf` 等旧兼容接口，
  `ft.backward`、`normalize.copy_group`、`mut_planner.layers_for_film`、`wavelet.ridge`、`report.plot_wavelet` 等无调用的函数，
  以及界面里的死分支。读入请用 `io.read_scan(columns={...})`（按列名映射）。

### 文档 / Docs
- `XAFS处理规范.md` 更新为 XAFSmith 的实际目录、环境与启动步骤（不再提 `scripts/`）。

## [1.0.0] — 2026-11-11

首个正式版（Windows）。First stable release (Windows).

### 新增 / Added
- **Windows 安装包**：自带 Python、Larch、FEFF6L/FEFF8L 与界面库，离线安装、无需管理员权限；另提供免安装的便携 zip 与
  `SHA256SUMS.txt`。安装目录带公开数据的演示项目（`examples\demo_project`）。
  Windows installer and portable zip bundling Python, Larch, FEFF6L/8L; offline, per-user; ships a public demo project.
- **恢复上次状态**：关闭时把当前页面、处理参数、已载入的谱（只记名字，重新打开时按当时的处理参数重新计算）和各页设置写入
  `output/gui/session.json`，下次打开项目自动恢复；首页可关闭此功能。
  Session restore on project open (can be switched off on the home page).
- **拟合草稿**：拟合页可把数据选择、FEFF 目录、拟合范围、路径表、参数表存成命名草稿（`output/gui/drafts/`），随时打开继续。
  Named fit drafts on the fit page.
- 开发文档：`ARCHITECTURE.md`（软件结构）、`CONTRIBUTING.md`（参与开发）、`docs/dev/RELEASING.md`（发布流程）。

### 变更 / Changed
- 安装包版本的“检查更新”查询 GitHub Release，不自动更新，提示下载新安装包；源码安装仍走 pip。
  The installed build checks GitHub Releases for updates and never self-updates.
- 安装包体积：去掉未用到的 MKL、pyarrow、scikit-learn、scikit-image、plotly、pyFAI、botocore 等，Qt 翻译只留中英文。
  没有 MKL 时 Larch 自动改用 scipy 的 FFT；单元测试与数值基准（Cu 箔拟合）结果不变。
  构建候选实测：解压后 1223 MB → **471 MB**，安装程序 **126 MB**，便携 zip 224 MB。
- 文档：README 增加系统要求、安装 / 升级 / 卸载、问题反馈；AI 助手可用任何语言交流（不再限定中文）。

### 修复 / Fixed
- 恢复上次状态时，后台重新载入完成前切换页面或关闭软件会用不完整的状态覆盖快照。
- 安装包中带入了构建环境的“开发安装”标记，导致“检查更新”提示用 git pull。
- 删除 / 覆盖同名拟合草稿前没有确认。

### 已知限制 / Known limitations
- 安装包只提供 Windows 10 / 11 64 位版；macOS / Linux 需从源码安装。
- 安装包未做代码签名：首次运行可能出现 SmartScreen 提示，个别杀毒软件可能误报。

## [0.5.1]

### 新增 / Added
- 公开数据演示项目、单元测试与数值基准（Cu 箔第一壳层与 Larch 示例逐位一致）、GitHub Actions CI（Windows + Ubuntu）。
- 数据读入改为格式插件：BSRF、XDI、Athena `.xmu`、XDAC、Athena `.prj`、通用列文本（按列名映射）；图形界面“列映射向导”可把映射存为项目格式模板。
- 日志文件（`~/.xafsmith/xafsmith.log`）与“导出诊断包”；`xafsmith validate` 的报错指向具体文件与行列。
- 后台任务显示进度并可取消。

### 变更 / Changed
- 图形界面代码按页面拆分（不改行为）；ruff 静态检查进 CI。

### 许可 / License
- 自 0.5.1 起按 PolyForm Noncommercial License 1.0.0 发布；0.5.0 及更早版本按当时附带的 MIT 许可发布。
