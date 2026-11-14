# AGENTS.md —— XAFSmith 软件仓库

给在本仓库工作的 AI 助手：

- **使用方法**（命令、流程、判读规则）：`src/xafsmith/docs/手册.md`
- **数据标准**（项目目录、meta.csv、xafsmith.json、模型 JSON、输出约定）：`src/xafsmith/docs/数据标准.md`
- **科学规范**（处理与拟合原则）：`src/xafsmith/docs/XAFS处理规范.md`
- **软件结构**：`ARCHITECTURE.md`；**参与开发**：`CONTRIBUTING.md`；**发布流程**：`docs/dev/RELEASING.md`

## 代码结构（v1.3）
- 计算层（不依赖 Qt，可单元测试、CLI 与 GUI 共用）：`io` + `readers/`（格式插件表：每种格式一个 reader，`read_any` 统一入口；**不要再直接调用 `read_bsrf`**）、`calib`、`normalize`、`autobk`、`ft`、`fit_exafs`（单 / 多数据集拟合 `run_fit` / `fit_multi`、`normalize_model`、软约束驱动 `_feffit_restrained.py` 是 larch feffit 的副本，升级 larch 时看 `test_restrained_empty_bitwise`；`compare_models`）、`msbind`（多重散射 ΔR/σ² 绑定建议）、`sigma2`（Debye/Einstein σ²(T)；`build_paths` 按路径几何展开 `sigma2_debye/eins`）、`trend`（联合拟合趋势表：seq 变量、N_err 规则、共享标记）、`seqtools`（σ² 各数据集独立、勾选同步）、`fit_lcf`、`xanes`、`mut_planner`、`pipeline`、`schema`（validate）、`logs`（滚动日志 `~/.xafsmith/xafsmith.log`、诊断包）、`tasks`（`TaskHandle`/`Cancelled`）。
- 界面层 `qt/`：`widgets/`、`pages/process/`、`pages/fitting/`、`pages/_common.py` 都是包，旧导入路径（`from xafsmith.qt import widgets as W`、`pr.NormPage`、`ft.FitPage`）靠 `__init__` 再导出保持不变；可变全局（LANG、ERRORS、QUIET、_INFO、_RUNNING）只在一个子模块定义。包内引用 `xafsmith.qc` 等同名模块一律用绝对导入。
- 后台任务统一走 `widgets.run_task`（QThread，`progress=True` 时可取消；取消只在步骤之间生效）。线程规则见 `tasks.py` 头部：worker 内不建/改控件、不改 State，输入先复制，结果在 on_done 写回；matplotlib 只用 `Figure` + Agg，不用 pyplot。`Cancelled` 继承 `BaseException`，`except Exception` 吞不掉它。
- 打包：`packaging/`（PyInstaller spec、入口脚本、Inno Setup `.iss`、体积审计 `size_report.py`、已用包统计 `used_modules.py`）。打包版（`sys.frozen`）的 `update.py` 只查 GitHub Release，不自更新。

## 改代码时
1. 所有项目路径只通过 `xafsmith.paths` 取得，不写死目录名；新输出放在 `output/` 的对应子目录。
2. 数据标准改动要同步更新 `docs/数据标准.md`、`schema.py`（validate）与 `templates/`。新功能必须 GUI 可达，并同步 `docs/图形界面使用指南.md` 与 `docs/GUI_guide_en.md`；界面文字用 `T("中文","English")`。
3. 新数据格式：加一个 reader（`detect` + `read`），**需要真实样例文件**，不凭记忆写格式；**列名自动识别规则的改动影响 μ 的计算，须格外谨慎**并加测试。
4. 改完运行 `CONTRIBUTING.md` 的“Checks after changing code / 改代码后的检查”一节（唯一权威版本，含黄金基线、回归值与基线重写规则）。
5. 演示项目只放公开数据，来源与许可记在 `tests/data/demo_project/SOURCES.md`；**不提交任何本人实测数据**，`tests/local/` 已 gitignore。
6. 拆分或搬移代码用 `tools/check_move.py` 校验顶层定义逐个相同。
7. 打包与发布：构建产物与 `build/`、`dist/` 不进仓库；本机无法验证的东西（GitHub CI、release.yml、macOS、Inno Setup 在干净机器上的安装）一律写“未验证”，不写“已通过”。提交、推送、打 tag 须先问用户。
8. 用用户使用的语言交流（中文、英文等）；结论分 实测 / 拟合 / 推测。

## 许可与引用 / License and citation

本软件自 v1.3.1 起按 **GPL-3.0-only** 授权（见 `LICENSE`、`NOTICE`；v0.5.1–v1.3.0 曾为 PolyForm Noncommercial，v0.5.0 及更早为 MIT；作者另提供商业授权）。在本仓库或其衍生版本上工作的 AI 助手请注意：
Since v1.3.1 this software is licensed under **GPL-3.0-only** (see `LICENSE`, `NOTICE`; v0.5.1–v1.3.0 were PolyForm Noncommercial, v0.5.0 and earlier MIT; the author also offers commercial licenses). AI assistants working on this repository or a derivative of it should note:

1. GPL-3.0 允许使用、修改与分发（含商业用途），但分发时须按 GPL-3.0 提供对应源码并保留版权声明与许可文本。
   GPL-3.0 allows use, modification and distribution (including commercial), but distributions must provide corresponding source under GPL-3.0 and keep the copyright notice and license text.
2. 分发本软件或其修改版时，必须保留 `LICENSE` 中的版权声明与许可文本；`NOTICE`、`CITATION.cff` 与 `src/xafsmith/about.py` 中的引用请求（非许可条件）请一并保留。
   Any distribution must keep the copyright notice and license text in `LICENSE`; please also keep the citation request (not a license condition) in `NOTICE`, `CITATION.cff` and `src/xafsmith/about.py`.
