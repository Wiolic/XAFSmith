# 更新日志 / Changelog

本项目的重要变化都记录在这里。格式参考 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.1.0/)，版本号遵循
[语义化版本](https://semver.org/lang/zh-CN/)。
All notable changes are recorded here (format: Keep a Changelog; versioning: SemVer).

## [1.4.0] — 2026-11-24

次版本：新增快速拟合（第一壳层、单样品与联合、人话判定、趋势），原拟合页改名精细拟合；已有模型的拟合数值逐位不变（黄金基线 `tests/golden/demo.json`）。
Minor release: Quick fit (first shell, single and joint, plain-words verdict, trends); the former fit page is now Detailed fit; fit numbers of existing models are unchanged bit for bit (golden baseline `tests/golden/demo.json`).

### 新增 / Added
- **快速拟合**（侧栏“EXAFS 拟合”顶部分段开关 **快速拟合 | 精细拟合**，进入页面默认快速拟合）：只拟合第一壳层，用人话判定结果是否可信。你只选样品（可多选）、FEFF 文件夹、用途（标样 / 样品）、Rmax（默认 2.5 Å）与 S0²；k 窗取样品的处理设置，Rmin 自动（|χ(R)| 在 0.7 Å 到第一峰之间的谷，且不低于第一峰 − 0.6 Å、不低于 0.7 Å，没有谷取 1.0 Å 与第一峰 − 0.6 Å 中较大者），k 权重 1、2、3 同时。第一壳层 = 最近的单散射路径起、并入同一散射元素且与前一条相差 < 0.3 Å 的路径（页内显示 N_ref、R_ref）。
  **Quick fit** (switch **Quick fit | Detailed fit** at the top of the sidebar page “EXAFS fitting”; the page opens on Quick fit): fits the first shell only and states in plain words whether the result is trustworthy. You choose samples (several allowed), FEFF folder, purpose (Standard / Sample), Rmax (default 2.5 Å) and S0²; the k window comes from the samples' processing settings, Rmin is automatic (the valley of |χ(R)| between 0.7 Å and the first peak, not below first peak − 0.6 Å and not below 0.7 Å, else the larger of 1.0 Å and first peak − 0.6 Å), k-weights 1, 2, 3 together. The first shell starts at the nearest single-scattering path and takes in paths of the same scatterer element less than 0.3 Å apart (N_ref and R_ref are shown on the page).
- 快速拟合的两种用途：**标样**（N 固定为结构简并度，拟合 S0²）与 **样品**（S0² 固定，拟合 N）。样品的 S0² 手填，或点 **选取标样值…** 从同吸收边、S0² 为拟合量的标样拟合取（本会话的与已保存的 `exafs_fits.csv` 的都列出），来源记入模型的 `s02_source`；标样拟合完成后即可选取，不必先保存。
  Two purposes: **Standard** (N fixed to the structure's degeneracy, S0² fitted) and **Sample** (S0² fixed, N fitted). The sample's S0² is typed or taken with **Pick standard value…** from a standard fit on the same edge with a fitted S0² (session fits and saved `exafs_fits.csv` rows are both listed); the source is recorded in the model's `s02_source`; a standard fit can be picked as soon as it is done, without saving.
- **联合快速拟合**：样品用途选 ≥ 2 个样品（同一吸收边）自动联合拟合：统一 k 窗（各样品处理 k 窗的交集，不足 6 Å⁻¹ 报错）与 R 窗、共享 ΔE0、共用 S0²，每个样品各自的 N、R、σ²；各样品 dk / 窗函数不一致时提示。标样用途只能选一个样品。
  **Joint quick fit**: ≥ 2 samples in Sample mode (one absorption edge) are fitted jointly: one common k window (the intersection of the processing windows; below 6 Å⁻¹ is an error) and R window, a shared ΔE0, one S0², and N, R, σ² per sample; differing dk / window functions are noted. Standard mode takes a single sample.
- **判定**（整批 + 逐样品两层，每项 ✓ / ✗ / ℹ，✗ 带一句建议）：R 因子（< 0.02 很好，≤ 0.05 对第一壳层可接受）；Stern 准则（变量数 ≤ N_idp，超过 N_idp/2 仅提示“信息量偏少”）；参数误差、边界、|ΔE0| ≤ 10 eV、σ² 为正且 ≤ 0.03 Å²、|ΔR| ≤ 0.2 Å、强相关；拟合 R 与 CIF 相差 ≤ 0.15 Å；N ≤ 1.5 × N_ref；Rmax 处 |χ(R)| ≤ 第一峰的 30%；数据第一峰与结构第一壳层对应（R_p − R_CIF 在 −0.8 … +0.1 Å，否则提示所选结构与样品不符，如金属相样品配了氧化物 FEFF）。手填 S0²、第一层还有别的元素只作提示。
  **Verdict** (two layers, batch + per sample; each check ✓ / ✗ / ℹ, ✗ with one line of advice): R-factor (< 0.02 very good, ≤ 0.05 acceptable for a first shell); Stern criterion (variables ≤ N_idp, only a note above N_idp/2); parameter errors, bounds, |ΔE0| ≤ 10 eV, σ² positive and ≤ 0.03 Å², |ΔR| ≤ 0.2 Å, strong correlations; fitted R within 0.15 Å of the CIF; N ≤ 1.5 × N_ref; |χ(R)| at Rmax ≤ 30% of the first peak; the data's first peak matches the structure's first shell (R_p − R_CIF within −0.8 … +0.1 Å, otherwise the structure does not match the sample, e.g. an oxide FEFF for a metallic sample). A typed S0² and other elements in the first layer are notes only.
- 快速拟合结果页：窗口、整批判定（联合）、结果表（样品、N、R、σ²、ΔE0、S0²、R 因子、判定，带 1σ 误差；点一行看该样品的 |χ(R)| 数据与拟合图和逐项判定）、页内趋势图（联合；下拉选 N / R / σ²，带误差棒）。按钮 **保存**（`models/<名>.json`、拟合记录与图、参数文件；联合另写 `output/fits/<名>_trend.csv`；与命令行 `--save` 相同）、**去图片导出**（打开 **图片导出 › 趋势图** 并选中这次拟合，那里可选导出哪些量）、**在精细拟合中继续**（把模型载入精细拟合，已有内容时先确认覆盖）。
  Quick-fit result: the window, the batch verdict (joint), a result table (Sample, N, R, σ², ΔE0, S0², R-factor, Verdict, with 1σ errors; click a row for that sample's |χ(R)| data and fit plot and its checks), an in-page trend plot (joint; a drop-down chooses N / R / σ², with error bars). Buttons: **Save** (`models/<name>.json`, fit records and figure, parameter file; a joint fit also writes `output/fits/<name>_trend.csv`; same as the command line `--save`), **Go to Figure export** (opens **Figure export › Trend** with this fit selected, where you choose which quantities to export) and **Continue in Detailed fit** (loads the model into Detailed fit, asking before overwriting existing content).
- **命令行 `xafsmith quickfit 样品… --feff 文件夹 (--standard | --s02 x | --s02-from 标样模型) [--rmax 2.5] [--rmin x] [--kweight 1,2,3] [--name N] [--save]`**：与界面同一套计算与判定；默认只打印结果表与判定、不写文件，`--save` 才写模型、拟合记录与图（联合拟合另写趋势 CSV）；模型已存在时报错、不覆盖；标样用途给多个样品是错误。
  **Command line `xafsmith quickfit …`**: the same computation and verdict as the GUI; by default it only prints the table and verdict and writes nothing; `--save` writes the model, fit records and figure (a joint fit also the trend CSV); an existing model is not overwritten; several samples in Standard mode is an error.
- 模型 JSON 新增可选键 **`s02_source`**（`{model, value, stderr}` 来自标样拟合，或 `{manual: true, value}`）与 **`quickfit`**（快速拟合的说明：模式、第一壳层、联合时各样品的处理 k 窗）：计算完全忽略，`xafsmith validate` 只检查类型，写法见《数据标准》。联合趋势表（`xafsmith trend`、图片导出的趋势图）对带 `quickfit` 键的模型按每个数据集给出一行第一壳层（N = n1、R = R_CIF + dr1、σ² = ss1、共享 ΔE0）。
  New optional model keys **`s02_source`** (`{model, value, stderr}` from a standard fit, or `{manual: true, value}`) and **`quickfit`** (mode, first shell, and for a joint model each sample's processing k window): ignored by the computation, `xafsmith validate` checks only their types; see the Data standard. The trend table (`xafsmith trend`, the Figure-export trend figure) gives one first-shell row per dataset for models with a `quickfit` key (N = n1, R = R_CIF + dr1, σ² = ss1, shared ΔE0).
- 文档：手册（快速拟合 / 精细拟合一节、命令表）、XAFS处理规范（拟合流程与判定）、图形界面使用指南、Quickstart、拟合教程与指南（中英）按新页面更新；`GLOSSARY.md` 与 `docs/adr/0001-*` 记录术语与“快速拟合只拟合第一壳层”的决定。
  Docs: the Manual (a Quick fit / Detailed fit section, the command table), the XAFS processing standard (fit flow and verdict), the GUI guide, the Quickstart and the fitting tutorials and guides (Chinese and English) follow the new pages; `GLOSSARY.md` and `docs/adr/0001-*` record the terms and the decision that Quick fit fits only the first shell.

### 改进 / Changed
- **“EXAFS 拟合”页成为容器页，原拟合页改名“精细拟合”**，功能不变；路径表的列序改为 use、label、N、deltar、sigma2、e0、s02、third、note、reff、degen、nleg、amp_ratio、dir（旧版保存的草稿与会话里的路径表打开时自动重排，模型 JSON 不变）。精细拟合新增“载入模型”功能（供快速拟合的 **在精细拟合中继续** 使用）：由模型的 FEFF 文件重建路径表，并载入参数、k / R 窗口与模型名（单数据集或联合）。
  **The “EXAFS fitting” page is now a container and the former fit page is renamed “Detailed fit”**, with unchanged functions; the path-table column order is now use, label, N, deltar, sigma2, e0, s02, third, note, reff, degen, nleg, amp_ratio, dir (path tables in older drafts and sessions are reordered on load; model JSON is unchanged). Detailed fit can now load a model (used by Quick fit's **Continue in Detailed fit**): the path table is rebuilt from the model's FEFF files, and the parameters, k / R window and model name are loaded (single or joint).
- 拟合结果的质量检查拆成独立的纯逻辑模块 `fitcheck`（精细拟合页与快速拟合判定共用；精细拟合页的文字与顺序逐字不变，有测试锁定）。
  The fit-quality checks are split out into a pure-logic module `fitcheck`, shared by the Detailed-fit page and the Quick-fit verdict; the Detailed-fit text and order are verbatim unchanged (locked by a test).
- GitHub Release 说明改为 CHANGELOG 中该版本一节的全文（`tools/release_notes.py`，`release.yml` 发布时调用；缺这一节则发布失败）；v1.0.0–v1.3.1 的 Release 说明已按 CHANGELOG 补写。
  GitHub Release notes are now the version's full CHANGELOG section (`tools/release_notes.py`, used by `release.yml`; a release without its section fails); notes for v1.0.0–v1.3.1 were backfilled.
- `.gitignore` 加入工具缓存目录。 Tool caches added to `.gitignore`.

### 修复 / Fixed
- `xafsmith fit --nosave` 现在真的不写文件：以前只是不追加 `exafs_fits.csv`，仍会写拟合报告、`params.json` 与拟合图。
  `xafsmith fit --nosave` now writes nothing; previously it only skipped `exafs_fits.csv` and still wrote the report, `params.json` and figures.

## [1.3.1] — 2026-11-14

补丁版：稳定性修复与工程护栏；已有数值结果逐位不变（黄金基线 `tests/golden/demo.json` 与本机项目快照核对）。
Patch release: stability fixes and engineering guard rails; existing numerical results are bit-identical (checked against the golden baseline and a local project snapshot).

### 修复 / Fixed
- 处理参数页：`norm2 = 0` 不再被改成 −10；窗函数下拉列出 larch 支持的全部 6 种，配置里其他写法原样保留（以前保存时被改成 hanning）；FT `kweight` 为列表时不再崩溃，原样显示并保存。
  Processing-parameter page: `norm2 = 0` is kept; all six larch windows are offered and other spellings kept (previously saved as hanning); a list-valued FT `kweight` no longer crashes and is kept.
- 后台线程不再读界面控件、不再与界面共用同一份谱对象（运行已保存模型、自定义拟合、稳健性检查、FEFF 运行）：谱在界面线程里先复制。
  Background tasks no longer read widgets or share live spectra with the UI (saved-model run, custom fit, robustness, FEFF).
- FEFF 在临时子目录运行，成功后才替换旧结果；失败时旧的 `feff*.dat` 与 `feff.inp` 原样保留，失败现场在 `_feff_failed/`（`feffrun_feff.log`、`feff.err`），报错指向它。多重散射向导的几何缓存随 FEFF 文件更新失效。
  FEFF runs in a temporary subfolder and replaces old results only on success; on failure old files are kept and the failed run is kept in `_feff_failed/`. The multiple-scattering geometry cache follows file changes.
- `xafsmith.json`、`meta.csv`、模型 JSON 改为原子写入（写到一半中断不留坏文件），旧版本保留为同名 `.bak`；配置写入前按数据标准校验，有“错误”级问题则拒绝保存并在页面上说明。
  `xafsmith.json`, `meta.csv` and model JSON are written atomically with a `.bak` of the previous version; a configuration with errors is refused before writing.

- 命令行出错时只打印一行中英文原因与日志位置，完整 traceback 写入日志；`--debug` 显示 traceback；Ctrl+C 退出码 130。日志消息补上出错对象（文件、样品、模型名），原先静默忽略的异常记入调试日志。
  CLI errors print one line plus the log location (`--debug` shows the traceback); log messages name the object; previously silent exceptions are debug-logged.
- 工程护栏：黄金基线回归测试（`tools/golden.py`、`tests/benchmark/test_golden.py`）；核心依赖设下界、`xraylarch` 设上界 <2026.4 并加 larch 内部函数金丝雀测试；`requires-python >=3.11`；`pytest` 默认只收集 `tests/unit` 与 `tests/benchmark`；CI 出覆盖率报告、每周定时运行；Windows 发布构建使用约束文件；删除过时的 `requirements.txt`；版本号一致性测试。
  Guard rails: golden-baseline regression, dependency bounds and a larch canary test, Python ≥ 3.11, pytest test paths, coverage report and weekly CI, build constraints, version consistency test.

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
