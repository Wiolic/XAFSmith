# 更新日志 / Changelog

本项目的重要变化都记录在这里。格式参考 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.1.0/)，版本号遵循
[语义化版本](https://semver.org/lang/zh-CN/)。
All notable changes are recorded here (format: Keep a Changelog; versioning: SemVer).

## [未发布] / Unreleased

工程改进，不加分析功能，数值与界面文字都不变。
Engineering work with no new analysis features; numbers and interface text are unchanged.

### 开发者 / For developers
- **异常分类**：`errors.py` 新增 `XafsmithError` 及子类 `ConfigError`（xafsmith.json / meta.csv）、`DataError`（数据文件，`ReadError` 现在属于它）、`ModelError`（模型 JSON，`QuickFitError` 现在属于它）、`FeffError`（FEFF 运行失败）。前三个仍是 `ValueError`、`FeffError` 仍是 `RuntimeError`，已有的 `except` 照旧捕获；配置、meta.csv、模型检查与 FEFF 的报错改抛这些类，消息不变。错误提示里显示的类名仍是原来的内置类名（`errors.shown_name`），用户看到的文字逐字不变。
  **Error classes**: `errors.py` adds `XafsmithError` with `ConfigError` (xafsmith.json / meta.csv), `DataError` (data files; `ReadError` is now one), `ModelError` (model JSON; `QuickFitError` is now one) and `FeffError` (FEFF failures). The first three are still `ValueError` and `FeffError` is still `RuntimeError`, so existing `except` clauses catch them as before; configuration, meta.csv, model-check and FEFF errors now raise them with unchanged messages. Error messages keep showing the builtin class name (`errors.shown_name`), so the text users see is identical.
- **类型声明**：新模块 `typedefs.py`（配置、模型、路径、参数、拟合记录的 `TypedDict`，运行时无作用）。CI 加 mypy（非严格），先查 `paths`、`common`、`schema`、`services`、`readers`、`typedefs`、`errors`。
  **Type declarations**: new module `typedefs.py` (`TypedDict`s for the configuration, models, paths, parameters and fit records; no runtime effect). CI runs mypy (non-strict) on `paths`, `common`, `schema`, `services`, `readers`, `typedefs` and `errors`.
- **读入格式插件**：另装的包可在 entry point 组 `xafsmith.readers` 登记读入格式，排在内置格式之后；加载失败、不是 `Reader` 或重名的插件记日志后跳过，不影响启动。内置格式的顺序与识别结果不变。
  **Reader plugins**: a separately installed package can register a data format in the entry-point group `xafsmith.readers`; plugins come after the built-in readers, and one that fails to load, is not a `Reader` or reuses a name is logged and skipped without affecting startup. The built-in readers and their detection results are unchanged.
- **页面自己声明属性**：每个页面类写明 `key`、`needs`、`no_project`、`hidden`，导航顺序只在 `qt/app.py` 的 `_NAV` 一处；`NEEDS`、`NO_PROJECT` 等表由页面类推导（与之前逐项相同，有测试锁定）。
  **Pages declare their own properties**: each page class states `key`, `needs`, `no_project` and `hidden`; the navigation order lives only in `_NAV` in `qt/app.py`, and the `NEEDS`, `NO_PROJECT` and related tables are derived from the classes (identical to before, pinned by a test).
- **一致性测试**（`tests/unit/test_consistency.py`）：每个命令行子命令都在《命令行速查》里，每个页面标题都在中英两份界面指南里，`T()` 都有英文，`ARCHITECTURE.md` 的模块表与 `src/` 一致。
  **Consistency tests** (`tests/unit/test_consistency.py`): every CLI command is in the CLI reference, every page title is in both GUI guides, every `T()` has English, and the `ARCHITECTURE.md` module table matches `src/`.
- `CONTRIBUTING.md` 新增“新增一种格式 / 一个分析 / 一个页面”三张清单；改代码后的检查加上 mypy。
  `CONTRIBUTING.md` gains three checklists (a data format, an analysis, a page); the checks after changing code include mypy.

## [1.4.2] — 2026-11-25

工程补丁版，不加分析功能。命令行与图形界面改用同一个业务层（新模块 `services`）：同一个结果无论从哪边保存，文件名与内容都相同，并且每种保存都留下参数记录。项目配置有了版本迁移：旧版本在内存中升级、文件不改，新于软件的明确拒绝。默认值、模型结构检查各只写一份。拟合、LCF、QC、校准的数值逐位不变（黄金基线 `tests/golden/demo.json` 与本机快照）。
An engineering patch release with no new analysis features. The command line and the graphical interface now share one service layer (new module `services`): a result saved from either side has the same file names and contents, and every kind of save leaves a parameter record. The project configuration gains version migration: older versions are upgraded in memory with the file left alone, newer ones are refused. Default values and model structure checks each exist once. Numbers of fits, LCF, QC and calibration are unchanged bit for bit (golden baseline `tests/golden/demo.json` and the local snapshot).

### 修复 / Fixed
- **界面保存拟合补写 `<模型>.params.json`**：以前只有命令行写，界面保存（拟合结果、拟合历史“全部保存”、输出页、快速拟合）不写，报告与方法导出追溯不到模型。
  **Saving a fit from the interface writes `<model>.params.json`**: only the command line wrote it before; saves from the fit result, “Save all” in the fit history, the Output page and Quick fit left it out.
- **文件名清洗只剩一条规则**（字母、数字、`_ . -` 以外的连续字符换成一个 `_`，去掉首尾 `_`）：以前界面逐字符替换、命令行合并连续字符，`xafsmith robust` 只替换 `/`，同一个模型名可能在两边写出不同文件名。名字里只有字母、数字、`_ . -` 的（常见情形）文件名不变；含空格、括号等的名字，稳健性 CSV 与界面导出（归一化、χ、小波、边前峰）的文件名可能与旧版不同。
  **One file-name rule**: runs of characters other than letters, digits and `_ . -` become one `_`, leading and trailing `_` are dropped. Before, the interface replaced character by character, the command line merged runs, and `xafsmith robust` replaced only `/`, so one model name could give two file names. Names made of letters, digits and `_ . -` (the usual case) are unaffected; with spaces, brackets and the like, robustness CSVs and interface exports (normalization, χ, wavelet, pre-edge) may be named differently from older versions.
- **XANES 特征表统一按样品合并**：`xafsmith xanes` 以前整表覆盖、界面按样品合并；现在两边都是新算的样品替换同名旧行，其余保留。
  **The XANES feature table is merged by sample everywhere**: `xafsmith xanes` used to overwrite the whole table while the interface merged; now both replace rows of the recomputed samples and keep the rest.
- 只给模型名时先在 `models/` 中找，项目根目录里的同名 json（如 `xafsmith.json`）不会被当作模型读入。
  A bare model name is looked up in `models/` first, so a same-named json in the project root (such as `xafsmith.json`) is never read as a model.

- `xafsmith validate` 遇到多数据集模型里没写 `id`、而 `sample` 不是字符串（如误写成列表）时整个校验崩溃（TypeError）；现在报一条错误，指明写上 `id` 或把 `sample` 改为字符串。拟合本来就拒绝这种模型，行为不变。
  `xafsmith validate` crashed (TypeError) on a multi-dataset model whose dataset has no `id` and a non-string `sample` (a list, say); it now reports an error asking for an `id` or a string `sample`. Fitting already refused such a model.
- XANES 特征表的“按样品合并”对数字样品名（如 `50`）失效：旧表读回时样品名成了数字，重算不替换旧行而是重复追加；现在按字符串比较。`xafsmith.json` 中 `xafsmith` 项不是对象时 `validate` 与保存配置崩溃，现在报错误。
  The XANES table's merge by sample failed for numeric sample names (such as `50`): read back as numbers, old rows were never replaced and recomputes appended duplicates; names are now compared as strings. A non-object `xafsmith` entry in `xafsmith.json` crashed `validate` and config saving; it is now an error.

### 配置版本 / Config version
- **旧版本项目在内存中升级，文件不改**：读 `xafsmith.json` 时按 `xafsmith.schema` 逐级升到当前数据标准（1.1），文件本身不改，下次正常保存配置时才写成新版本；图形界面打开这样的项目时在窗口底部提示一次，日志记一条。缺 `schema` 按 1.0 处理。1.0 → 1.1 只记新版本号（1.1 新增的只是 meta.csv 的可选列）。新模块 `migrate`。
  **Older projects are upgraded in memory, the file is left alone**: `xafsmith.json` is brought up to the current data standard (1.1) step by step from its `xafsmith.schema` when read; the file stays as it is until the configuration is next saved; the interface shows a one-time notice and the log gets one line. A missing `schema` counts as 1.0. 1.0 → 1.1 only records the new number (1.1 added only optional meta.csv columns). New module `migrate`.
- **新于本软件的项目明确拒绝**：`xafsmith.schema` 新于本软件，或版本串无法识别时（`1.1.0` 与 `1.1` 视为同一版本），读入报错（请升级软件或改正版本号），`xafsmith validate` 也报错误；以前照常读入，可能悄悄忽略新字段。
  **Projects from a newer version are refused**: a `xafsmith.schema` newer than the software, or one that cannot be parsed (`1.1.0` equals `1.1`), stops loading with an error (upgrade or fix the number) and is an error in `xafsmith validate`; before, such a file was read as is and new fields could be silently ignored.
- 模板 `templates/xafsmith.json` 与《数据标准》示例的版本号改为 1.1（代码自 v1.1.0 起就是 1.1）。模型 JSON 可写可选的 `schema` 字段，新于本软件时 `validate` 只警告；软件不往已有模型里补写它。
  The template `templates/xafsmith.json` and the Data standard example now say 1.1 (the code has been 1.1 since v1.1.0). A model JSON may carry an optional `schema` field; newer than the software is only a warning in `validate`; existing models are never given one.
- 每个 `*.params.json` 多记两项：`xafsmith_version`（软件版本）与 `schema_version`（数据标准版本）。
  Every `*.params.json` also records `xafsmith_version` and `schema_version`.

### 可追溯性 / Traceability
- 新增参数记录：稳健性 `<模型>_robustness.params.json`、LCF `output/lcf/lcf_<样品>.params.json`（样品、标样、全部拟合选项、备注）、XANES `xanes_features.params.json`（按样品记录白线窗口）、QC `qc_report.params.json`（所用归一化参数）、校准 `calib.params.json`（参比与所用配置）。命令行与界面写的同一结果只有 `tool` 与 `time` 两项不同。
  New parameter records: robustness `<model>_robustness.params.json`, LCF `output/lcf/lcf_<sample>.params.json` (sample, standards, every fit option, note), XANES `xanes_features.params.json` (white-line window per sample), QC `qc_report.params.json` (normalization used), calibration `calib.params.json` (references and the configuration used). The same result written from the command line or the interface differs only in `tool` and `time`.
- 界面 LCF 也写拟合图 `output/figs/lcf_<样品>.png`（以前只有命令行写）；`xafsmith fit` 遇到 ≥ 2 个数据集的联合模型也写趋势表 `<模型>_trend.csv`（以前只有界面保存与快速拟合写）。
  The interface LCF also writes the plot `output/figs/lcf_<sample>.png` (command line only before); `xafsmith fit` on a joint model of ≥ 2 datasets also writes the trend table `<model>_trend.csv` (interface saves and Quick fit only before).

### 内部 / Internal
- 新模块 `services`：读模型、运行模型、保存拟合、稳健性、模型比较、LCF、XANES、QC、校准的落盘只此一份；`cli` 与界面各页面都调用它，`qt/state.py` 只留会话状态。新增测试 `tests/unit/test_services.py`：同一模型分别走命令行与界面的保存路径，产物（含 PNG）逐字节相同，参数记录除 `tool`、`time` 外相同。
  New module `services`: loading and running models and saving fits, robustness, comparisons, LCF, XANES, QC and calibration exist once; `cli` and every interface page call it and `qt/state.py` keeps only session state. New test `tests/unit/test_services.py`: one model saved through the command-line and the interface paths gives byte-identical outputs (PNG included) and parameter records equal apart from `tool` and `time`.
- 新模块 `defaults`：处理参数默认值、新建配置写入的 norm / bkg / ft、`META_COLS`、两套数据后缀与 `~/.xafsmith` 各只定义一处（原散在 5 个模块）。`norm2` 的 `None`（计算缺省）与 `-10`（写进新配置）保持各自行为：归一化中两者等价，导出 Athena 工程时不等价。
  New module `defaults`: processing defaults, the norm / bkg / ft written into a new configuration, `META_COLS`, the two data-suffix sets and `~/.xafsmith` are each defined once (they were spread over 5 modules). `norm2 = None` (computation default) and `-10` (written into new configurations) keep their own behaviour: equivalent in normalization, not in the Athena project export.
- 新模块 `modelcheck`：模型 JSON 的结构检查只写一份，`validate`（报告全部问题）与拟合（遇第一个错误就停）共用；两边原有的规则差异、消息文字与先后顺序都不变（97 个人造模型与本机项目全部模型对照逐条相同）。
  New module `modelcheck`: model-JSON structure checks exist once, shared by `validate` (reports every issue) and fitting (stops at the first error); the rules each side had, their messages and order are unchanged (checked entry by entry on 97 synthetic models and every model of a local project).
- 去掉计算模块各自的单独运行入口（`python -m xafsmith.<模块>`，参数与 `xafsmith` 子命令不一致，有的还绕过参比校准）；`python -m xafsmith.io` 与 `python -m xafsmith.agent` 改为转到 `xafsmith inspect` / `xafsmith agent`。`origin_builder` 的入口保留（Origin 里运行导出脚本要用）。
  Computation modules no longer run on their own (`python -m xafsmith.<module>` took arguments unlike the `xafsmith` subcommands and some skipped the reference calibration); `python -m xafsmith.io` and `python -m xafsmith.agent` forward to `xafsmith inspect` / `xafsmith agent`. `origin_builder` keeps its entry (Origin runs the exported script).

## [1.4.1] — 2026-11-25

降低第一次拟合的门槛：快速拟合里直接用内置结构算 FEFF（内置结构从 8 个增加到 63 个）、判定的每条问题后面直接给操作按钮、一键导出给导师看的汇报包；没有参比时可以显式跳过校准；按能量猜出的元素与吸收边要用户确认；报错改成人话。已有模型与拟合的数值逐位不变（黄金基线 `tests/golden/demo.json`）。
Lowers the bar for a first fit: compute FEFF from a built-in structure right in Quick fit (63 built-in structures instead of 8), action buttons under every problem in the verdict, and a one-click report package for a supervisor; an explicit way to skip calibration when there is no reference; guessed element and edge must be confirmed; plain-language error messages. Numbers of existing models and fits are unchanged bit for bit (golden baseline `tests/golden/demo.json`).

### 新增 / Added
- **内置结构从 8 个增加到 63 个**：新增 55 个取自开放晶体学数据库 COD（公共领域）的结构，放在 `src/xafsmith/structures_builtin/`（CIF + `index.csv`，记录 COD 编号、原始文献、空间群、晶胞与第一壳层，`README.md` 写明挑选规则）。包括 19 种金属（fcc Ni Cu Rh Pd Ag Pt Au，bcc V Cr Fe Nb Mo W，hcp Ti Zn Zr Ru Re Os）、26 种氧化物（TiO₂ 金红石与锐钛矿、V₂O₅、Cr₂O₃、MnO、Mn₂O₃、MnO₂、Mn₃O₄、FeO、Fe₂O₃、Fe₃O₄、NiO、CuO、Cu₂O、ZnO、ZrO₂、MoO₂、MoO₃、RuO₂、PdO、Ag₂O、SnO₂、CeO₂、WO₃、In₂O₃、GeO₂）与 ZnS、MoS₂、FeS₂、SrTiO₃、BaTiO₃、LiCoO₂、LiFePO₄、ZnFe₂O₄、Co(OH)₂、Ni(OH)₂。只收室温常压、有序的条目，优先 Wyckoff《Crystal Structures》，每个都核对了吸收原子的第一壳层；Ni、Fe、ZnO、MoS₂、Fe₂O₃ 是人工挑的条目（自动挑选得到的是变温系列或错误的氧位置）。没有合格条目的（Rh₂O₃、PtO₂、Ta₂O₅、Nb₂O₅、Ga₂O₃、反尖晶石铁氧体等）不收。原有手写的 8 个（Ir、Ta、Co_hcp、Co_fcc、IrO2、CoO、Co3O4、KTaO3）不变且优先；`builtin_for(元素)` 列出含该元素的结构；FEFF 路径页的内置结构下拉、`xafsmith structures` 与“内置结构导出为 CIF”都包含新结构；安装包带上该文件夹。
  **63 built-in structures instead of 8**: 55 new ones from the Crystallography Open Database (COD, public domain) in `src/xafsmith/structures_builtin/` (CIF + `index.csv` with COD id, original paper, space group, cell and first shell; `README.md` states the selection rules). They cover 19 metals (fcc Ni Cu Rh Pd Ag Pt Au, bcc V Cr Fe Nb Mo W, hcp Ti Zn Zr Ru Re Os), 26 oxides (rutile and anatase TiO₂, V₂O₅, Cr₂O₃, MnO, Mn₂O₃, MnO₂, Mn₃O₄, FeO, Fe₂O₃, Fe₃O₄, NiO, CuO, Cu₂O, ZnO, ZrO₂, MoO₂, MoO₃, RuO₂, PdO, Ag₂O, SnO₂, CeO₂, WO₃, In₂O₃, GeO₂) and ZnS, MoS₂, FeS₂, SrTiO₃, BaTiO₃, LiCoO₂, LiFePO₄, ZnFe₂O₄, Co(OH)₂, Ni(OH)₂. Only ambient, ordered entries were taken, Wyckoff's *Crystal Structures* preferred, and each was checked by its absorber's first shell; Ni, Fe, ZnO, MoS₂ and Fe₂O₃ were chosen by hand (the automatic pick gave a temperature series or a wrong oxygen position). Phases without a usable entry (Rh₂O₃, PtO₂, Ta₂O₅, Nb₂O₅, Ga₂O₃, inverse-spinel ferrites …) are left out. The 8 hand-written ones (Ir, Ta, Co_hcp, Co_fcc, IrO2, CoO, Co3O4, KTaO3) are unchanged and take priority; `builtin_for(element)` lists the structures containing an element; the FEFF-paths built-in list, `xafsmith structures` and “Export built-ins as CIF” include the new ones; the installer ships the folder.
- **快速拟合：用内置结构计算…**（FEFF 文件夹旁）：列出含样品吸收元素的内置结构及其来源，选一个就在后台用 FEFF6L（参数同 FEFF 路径页缺省）算到 `output/feff/<结构>_<元素><边>/site<n>` 并自动选中；已算过的直接选用，勾“重新计算”才重算；吸收原子有多个不等价位点时只算第一个并提示。还没有任何 FEFF 计算时页面不再拦住，直接提供这个按钮。新函数 `feff_wrap.build_builtin`、`n_absorber_sites`。
  **Quick fit: Compute from a built-in structure…** (next to the FEFF folder): lists the built-in structures containing the samples' absorber with their sources; choosing one runs FEFF6L in the background (FEFF-paths defaults) into `output/feff/<structure>_<element><edge>/site<n>` and selects it; an existing result is reused unless “Recompute” is ticked; with several inequivalent absorber sites only the first is computed and a notice says so. With no FEFF calculation yet the page no longer blocks and offers this button. New functions `feff_wrap.build_builtin`, `n_absorber_sites`.
- **判定后面的操作按钮**：快速拟合判定里每条 ✗ 的建议下面给按钮——**Rmax 改为 X Å 并重新拟合**（Rmax 处残余过大；X = Rmax − 0.2 Å，低于第一壳层距离时不出现）、**换结构…**（第一峰位置、R 与结构之差、|ΔR|、ΔE0、R 因子）、**去能量校准**（ΔE0）、**选取标样 S0²…**（N 过大）、**在精细拟合中继续**（变量数、误差、边界、相关、σ²、系统残差）。判定的阈值与分级不变。
  **Action buttons in the verdict**: under the advice of every ✗ in the quick-fit verdict — **Set Rmax to X Å and refit** (residual at Rmax; X = Rmax − 0.2 Å, not offered below the first-shell distance), **Change structure…** (first-peak position, R vs structure, |ΔR|, ΔE0, R-factor), **Go to energy calibration** (ΔE0), **Pick a standard's S0²…** (N too large), **Continue in Detailed fit** (variables, errors, bounds, correlations, σ², systematic residual). Thresholds and levels of the verdict are unchanged.
- **导出汇报包**（快速拟合结果按钮；命令行 `xafsmith quickfit … --report`，不需要 `--save`）：写 `output/reports/<模型名>_<时间>/`，含每个样品的 |χ(R)| 与 k²χ(k) 数据和拟合图（PNG 300 dpi）、联合拟合的 N / R / σ² 趋势图、`参数表.csv`、`判定.txt`、`方法.md`（中英文方法段落）与单页 `报告.html`；判定有 ✗ 时报告顶部醒目写明“本次拟合有 n 项需注意，不建议直接用于结论”。未保存的拟合也能导出。新模块 `quickfit_report`；`methods_text.build` / `collect` 可传入拟合记录 CSV。
  **Export report package** (Quick-fit result button; command line `xafsmith quickfit … --report`, no `--save` needed): writes `output/reports/<model>_<time>/` with |χ(R)| and k²χ(k) data-and-fit plots per sample (PNG 300 dpi), N / R / σ² trend plots for a joint fit, `参数表.csv` (parameters), `判定.txt` (verdict), `方法.md` (methods in Chinese and English) and a one-page `报告.html`; with any ✗ a red box at the top says the fit should not be used directly for conclusions. Unsaved fits can be exported. New module `quickfit_report`; `methods_text.build` / `collect` accept a fit-record CSV.
- **没有参比时可以显式跳过校准**：meta.csv 的 `ref_file` 填 `none`（大小写不限）= 有意不校准：能量不平移、谱标为未校准，快速拟合判定加一条 ℹ 提示（不算失败），方法段落写“未做能量校准（无参比）”；数据登记页 `ref_file` 下拉多了 `none`，`xafsmith validate` 接受它。`ref_file` 为空仍是错误，报错文字改为说明这一出路；同一样品的扫描混用参比与 `none` 时报错。
  **Skip the calibration explicitly when there is no reference**: `ref_file = none` (any case) in meta.csv means no calibration on purpose: no energy shift, the spectra are marked uncalibrated, the quick-fit verdict gets a note (not a failure), and the methods paragraph says “no energy calibration (no reference)”; the Register-data drop-down offers `none` and `xafsmith validate` accepts it. An empty `ref_file` is still an error, whose message now points to this option; mixing a reference and `none` within one sample is an error.
- **猜测的元素 / 吸收边要确认**：载入谱页“已载入”表在按能量猜出的元素、吸收边后标“（猜测）”，表上方提示，表下方可选谱、填元素、看将得到的吸收边后 **应用**，或 **确认无误**；元素在谱的能量范围内没有吸收边时拒绝。只改本次会话。
  **Guessed element / edge must be confirmed**: the Load page marks element and edge guessed from the energy with “(guessed)”, shows a notice, and below the table lets you choose spectra, type an element, preview the edge and **Apply**, or **Confirm as is**; an element with no edge inside the spectrum's energy range is refused. Session only.
- **报错说人话**：出错窗口分三段——发生了什么 / 你可以怎么做 / 联系（GitHub Issues 链接、**导出诊断包…**、**复制详细信息**），英文堆栈收在折叠的“详细信息”里；后台任务的默认报错与未捕获异常共用。新模块 `errors.explain` 覆盖找不到文件、文件被占用（如在 Excel 中打开）、读入格式不识别、快速拟合错误、内存不足、拟合不收敛 / 协方差奇异、FEFF 失败与其它。
  **Plain-language errors**: the error window has three parts — what happened / what you can do / contact (GitHub Issues link, **Export diagnostics…**, **Copy details**) — with the stack trace in a collapsed “Details”; shared by background tasks and uncaught exceptions. New module `errors.explain` covers missing files, files locked by another program (e.g. Excel), unrecognised formats, quick-fit errors, out of memory, non-converging fits / singular covariance, FEFF failures and the rest.
- 文档：《零基础拟合教程》开头加“最短路径”五步，第 8 章列出全部内置结构与多位点说明，第 11 章列出判定按钮，第 1、3、14 章写明 `none`、猜测确认与汇报包；《图形界面使用指南》《拟合质量提升教程》《多样品联合拟合指南》《数据标准》《XAFS处理规范》（无参比的例外与必须注明）、《手册》《命令行速查》、README、QUICKSTART 中英同步。
  Docs: the Beginner tutorial opens with a five-step shortest path; chapter 8 lists all built-in structures and the multi-site caveat, chapter 11 the verdict buttons, chapters 1, 3 and 14 cover `none`, guess confirmation and the report package; the GUI guide, fit-quality and joint-fit guides, Data standard, processing rules (the no-reference exception and its required statement), Manual, CLI sheet, README and QUICKSTART follow, in Chinese and English.

### 改进 / Changed
- README、QUICKSTART（中英）按 v1.4 重写：“为什么用 XAFSmith”先讲四个亮点（快速拟合零基础友好、多谱一键归一化、直接导出 Origin 文件、写论文方法与补充材料），其余功能用文字叙述；全部截图按真实字体渲染重拍（Ir 箔与 IrO₂ 标样）。`ARCHITECTURE.md`、`AGENTS.md`、`GLOSSARY.md` 更新到 v1.4 的结构与术语。
  README and QUICKSTART (Chinese and English) rewritten for v1.4: “Why XAFSmith” leads with four highlights (Quick fit for beginners, one-click normalization of many spectra, direct Origin export, methods and SI), the rest as text; all screenshots retaken with real font rendering (Ir foil and IrO₂ standards). `ARCHITECTURE.md`, `AGENTS.md` and `GLOSSARY.md` describe the v1.4 structure and terms.
- 免责声明措辞改为“不对计算结果的正确性作任何担保，请自行核验”（关于页、安装程序、安装向导）。
  The disclaimer now reads “no warranty that the results are correct; please verify them” (About page, installer, setup wizard).
- 截图工具 `tools/shot_gui.py` 默认用 Windows 原生平台渲染（字体与真实界面一致），`--offscreen` 只用于无桌面环境；`tools/shot_docs.py` 一次生成文档配图。
  The screenshot tool `tools/shot_gui.py` renders on the native Windows platform by default (fonts as in the real GUI), `--offscreen` only for headless use; `tools/shot_docs.py` regenerates the documentation images.

### 修复 / Fixed
- 有时打开窗口看不到右上角的最小化 / 还原 / 关闭，也拖不动、缩放不了：恢复上次窗口位置时只把客户区限制在屏幕内，标题栏被推到屏幕上方之外（上次是最大化关闭时尤其如此）。现在恢复时给标题栏和边框留出位置；最大化关闭时记下还原后的大小与“最大化”状态，下次按最大化打开。帮助窗口同样处理。
  The window sometimes opened without its minimize / restore / close buttons and could not be dragged or resized: restoring the last position kept only the client area on screen, pushing the title bar above the top edge (especially after closing maximized). The title bar and frame now get room; a maximized window saves its restored size and the maximized state and reopens maximized. The help window is handled the same way.
- 右上角“流程与本项目”弹窗底部四个按钮挤在一行，“项目文件夹”“保存处理参数”的文字被挤偏，改为两行两列等宽。
  The four buttons at the bottom of the “Workflow & project” pop-up were squeezed into one row, pushing “Project folder” and “Save parameters” off-centre; they are now a 2 × 2 grid of equal width.
- 图片导出的配色名“柔和期刊”改为“柔和”。 The Chinese name of the “soft” palette is now 柔和.
- `scan_raw`（数据登记的扫描）重写 meta.csv 时不再把 `None`、`NA` 等文字当成缺失值清空（以前 `ref_file = None` 会在重扫后丢失）。
  `scan_raw` (Register-data scan) no longer blanks text such as `None` or `NA` when rewriting meta.csv (a `ref_file` of `None` used to be lost on rescan).
- 方法导出：没有记录能量平移 ΔE 时写成占位【ΔE】，不再留下空的“( eV)”。
  Methods export: a missing energy shift ΔE is written as the placeholder [ΔE] instead of an empty “( eV)”.
- 英文界面：趋势图上方的序列提示（如 seq 为空、改用时间作横轴）原来只有中文，现在按界面语言显示（`trend.seq_values` 另给 `notes_en`）；拟合结果行、快速拟合判定里的中文全角空格换成英文间隔。
  English interface: the sequence notes above trend plots (e.g. empty seq, falling back to time) were Chinese only and now follow the interface language (`trend.seq_values` also returns `notes_en`); ideographic spaces in the fit-result line and the quick-fit verdict are replaced by Latin spacing.

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
- **混合相快速拟合**（两相第一壳层，如 IrTa 原位的金属 Ir + IrO2）：样品用途可再选一个 **第二相 FEFF**（GUI“第二相 FEFF（可选）”；命令行 `--feff2`；标样用途不可用）。两相吸收原子须相同；各拟合第一壳层：相 1 的 n1、dr1、ss1，相 2 的 n2、dr2、ss2，ΔE0 共用，S0² 固定，N 初值各为 N_ref 的一半（范围 [0, 2·N_ref]）。联合拟合时每个样品只有自己的 n1_<id>、n2_<id>，dr1、ss1、dr2、ss2 **全批共享**（两相 N–σ² 强相关，与项目模型 `JIr_insitu_OM` 一致）；单样品七个变量全自由，协方差奇异时给出带建议的错误。Rmax 缺省：有第二相 3.0 Å，否则 2.5 Å（GUI 里你改过 Rmax 就不再自动换；命令行 `--rmax` 缺省改为按此决定）；Rmin 见下。判定：两相各做 R 与 CIF 之差、N / N_ref（文字带“相 1 / 相 2（Ir–O / Ir–Ir）”前缀）；数据第一峰与任一相的结构第一壳层相符即通过；Rmax 处残余只作提示；各相比例 N / N_ref 只作提示。结果表多出 N₂、R₂、σ²₂、相 2 比例，页内趋势图两条线，趋势表每数据集两行（R = R_CIF + dr，σ²、R 标记为共享），“在精细拟合中继续”载入来自两个 FEFF 文件夹的路径（精细拟合的“载入模型”支持多个 FEFF 文件夹）。模型 `quickfit` 键新增可选 `shell2`（`xafsmith validate` 检查类型）。单相模型、精细拟合与黄金基线的数值逐位不变。混合相的自动 Rmin 按距离较短的一相找第一峰（上端 = 较短的 R_CIF − 0.2 Å），不会被较长一相（如金属）的峰带偏而把低 R 的氧峰切出窗外：IrTa 原位序列自动 Rmin 1.18 Å，两相 N 与 `JIr_insitu_OM`（R 窗 1.2–3.0 Å）重拟合相差 ≤ 0.03；混合相时 Rmax 处残余只作提示（较长一相的第一峰较宽）。
  **Mixed-phase quick fit** (two-phase first shell, e.g. in-situ IrTa: metallic Ir + IrO2): in Sample mode a **second-phase FEFF** can be chosen (GUI “Second-phase FEFF (optional)”; command line `--feff2`; not available in Standard mode). Both phases need the same absorber; each fits its first shell: n1, dr1, ss1 for phase 1 and n2, dr2, ss2 for phase 2, a shared ΔE0, S0² fixed, N starting at half of N_ref (range [0, 2·N_ref]). In a joint fit each sample has only its own n1_<id>, n2_<id> while dr1, ss1, dr2, ss2 are **shared by the whole batch** (N and σ² of the two phases are strongly correlated; same as the project model `JIr_insitu_OM`); a single sample has seven free variables, and a singular covariance gives an error with advice. Default Rmax: 3.0 Å with a second phase, else 2.5 Å (in the GUI no longer changed automatically once you edit Rmax; command-line `--rmax` now defaults accordingly); Rmin see below. Verdict: each phase gets the R-vs-CIF and N / N_ref checks (texts prefixed “Phase 1 / Phase 2 (Ir–O / Ir–Ir)”); the data's first peak matching either phase's structure passes; the residual at Rmax is a note only; the phase fractions N / N_ref are notes only. The result table gains N₂, R₂, σ²₂ and the phase-2 fraction, the in-page trend plot shows two lines, the trend table has two rows per dataset (R = R_CIF + dr; σ² and R flagged shared), and “Continue in Detailed fit” loads paths from the two FEFF folders (Detailed fit's “load model” accepts several FEFF folders). The model's `quickfit` key gains the optional `shell2` (checked for types by `xafsmith validate`). Single-phase models, Detailed fit and the golden baseline are numerically unchanged bit for bit. For mixed phases the automatic Rmin looks for the first peak of the shorter-distance phase (upper end = the shorter R_CIF − 0.2 Å), so the peak of the longer phase (e.g. a metal) no longer pushes Rmin past the low-R oxygen peak: on the in-situ IrTa series the automatic Rmin is 1.18 Å and both phases' N agree with a refit of `JIr_insitu_OM` (R window 1.2–3.0 Å) within 0.03; with mixed phases the residual at Rmax is a note only (the longer phase's first peak is broad).
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
- **快速拟合的样品列表**与精细拟合一致：只列当前会话已载入并算出 χ(k) 的样品（以前列 `data/meta.csv` 里的全部样品，拟合时在后台另建一份，会话里没有那条谱，导致图片导出等页面看不到）；没有载入样品时提示去“载入谱 / χ(k) 与 FT”。
  **The Quick-fit sample list** now matches Detailed fit: only samples loaded in the session with χ(k) are listed (before, all samples of `data/meta.csv` were listed and built in the background, so the spectra were not in the session and Figure export etc. could not see them); with nothing loaded a hint points to “Load spectra / χ(k) & FT”.
- **图片导出 › χ(k) / |χ(R)| 的“叠加拟合曲线”对联合（多数据集）拟合无效**：联合拟合记录的样品名是 “a+b”，匹配不到任何谱；现在按数据集逐个对应（精细拟合与快速拟合的联合结果都适用），单数据集拟合行为不变。
  **Figure export › χ(k) / |χ(R)| “Overlay fit” did nothing for joint (multi-dataset) fits**: a joint record is named “a+b” and matched no spectrum; datasets are now matched one by one (for joint fits from Detailed fit and Quick fit alike); single-dataset fits behave as before.
- **趋势图的样品顺序可调**（快速拟合页内趋势图与 图片导出 › 趋势图）：“横轴顺序”里拖动样品或用 ↑ ↓，“恢复默认顺序”回到 seq → 测量时间 → 数据集顺序的规则；调过后横轴按该顺序等间距排列（标签为样品名）。顺序存在拟合记录上（`trend_order`，数据集 id 列表），两处共用；保存的趋势 CSV 按此顺序写行并在最后加一列 `order`，原有各列（含 `seq`）的值不变，`trend_table` 的数值不变；没调时与以前完全相同。
  **The sample order of the trend plot is adjustable** (the in-page plot of Quick fit and Figure export › Trend): drag the samples or use ↑ ↓ in “X-axis order”, “Restore default order” returns to the seq → measurement time → dataset-order rule; once changed, the axis shows the samples in that order, evenly spaced (labelled with the sample names). The order is stored on the fit record (`trend_order`, a list of dataset ids) and shared by both places; the saved trend CSV writes its rows in that order with one extra trailing column `order`, the existing columns (including `seq`) keep their values and `trend_table` numbers are unchanged; unchanged behaviour when the order is not touched.
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
