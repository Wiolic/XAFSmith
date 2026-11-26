# XAFSmith architecture / 软件结构

This document is for developers and for AI assistants that change the code. For *using* XAFSmith see the
[README](README_en.md) and the guides in `src/xafsmith/docs/`.
本文面向开发者与修改代码的 AI 助手；使用说明见 README 与 `src/xafsmith/docs/`。

## 1. Layers / 分层

```
            ┌───────────────────────────┐   ┌───────────────────────┐
  users →   │ GUI  (xafsmith.qt, PySide6)│   │ CLI  (xafsmith.cli)    │  ← humans, AI assistants
            └─────────────┬─────────────┘   └───────────┬───────────┘
                          │ calls only public functions │
            ┌─────────────▼─────────────────────────────▼───────────┐
            │ pipeline.py  (project-level orchestration)             │
            ├────────────────────────────────────────────────────────┤
            │ io + readers/ │ qc │ calib │ normalize │ autobk │ ft │   │
            │ wavelet │ feff_wrap │ fit_exafs │ fit_lcf │ xanes │      │  ← computation, no Qt
            │ mut_planner │ report / pubfig / summary / methods_text  │
            │ trend │ seqtools │ msbind │ sigma2 │ origin_export      │
            │ quickfit │ fitcheck │ s02_source                         │
            ├────────────────────────────────────────────────────────┤
            │ paths │ defaults │ schema │ modelcheck │ migrate         │  ← infrastructure
            │ logs │ tasks │ update │ about │ errors │ typedefs        │
            └─────────────┬──────────────────────────────────────────┘
                          │
                 Larch (xraylarch), FEFF6L / FEFF8L, numpy / scipy / lmfit, xraydb
```

Rules / 规则

1. **Computation never imports Qt.** Everything below the GUI can be unit-tested and is shared by the CLI and
   the GUI. 计算层不导入 Qt。
2. **Modules exchange data through files** (CSV / JSON / Larch groups written to `output/`), as the project
   convention requires; every run writes its parameters next to the results.
3. **All project paths come from `xafsmith.paths`**; no module hard-codes a directory name.
4. Larch does the numerical heavy lifting (normalization, `autobk`, FT, `feffit`). XAFSmith adds data
   handling, consistency rules, quality checks and reporting; it does not re-implement Larch's algorithms.

## 2. Project on disk / 项目目录

A project is a folder containing `xafsmith.json`. The directory layout and every file format are specified in one
place only: [`src/xafsmith/docs/数据标准.md`](src/xafsmith/docs/数据标准.md) (section 1); `xafsmith validate`
(module `schema`) checks it. 项目目录结构只在数据标准.md 中描述，此处不重复。

## 3. Data flow / 数据流

```
raw file ──readers.read_any──► Larch Group (energy, μ, mode, edge, provenance)
   │                               │
   │                  calib: ΔE from the reference foil (1st-derivative max), same ΔE for all
   │                         spectra sharing that reference
   │                               ▼
   │                  normalize: pre/post-edge, E0, edge step; merge_scans (per-scan checks)
   │                               ▼
   │                  autobk → χ(k);  ft → |χ(R)|, Re/Im  (parameters from xafsmith.json)
   │                               ▼
   │      feff_wrap (FEFF6L/8L) ─► fit_exafs (feffit; joint multi-dataset fits, restraints via _feffit_restrained;
   │                              N_idp, χ²_ν, R-factor, F-test, model comparison, robustness)
   │                           └─► fit_lcf / xanes (LCF, edge position, white line, valence)
   ▼
output/  ──► report / pubfig / summary / methods_text / si_text / origin_export
```

`pipeline.build_sample()` is the single entry for "raw → processed group" and is used by the CLI, the GUI and
the tests.

### Readers / 读入插件

`readers/formats.py` holds one reader per format (`detect(path)` + `read(path)`): BSRF text, XDI, Athena
`.xmu`, XDAC, Athena `.prj`, generic column text. Columns are mapped **by name, never by position**; anything
guessed is recorded on the group and shown by `xafsmith inspect`. User-defined column templates (GUI column
wizard, `readers/wizard.py`) are stored in `xafsmith.json` → `formats`. Design notes: [docs/dev/io_readers.md](docs/dev/io_readers.md).
Separately installed packages can add readers through the entry-point group `xafsmith.readers`
(`readers.load_plugins`, run once on import): they come after the built-in `REGISTRY`, so detection of existing files
is unchanged; a plugin that fails to load, is not a `Reader` or reuses a name is logged and skipped.

> Changing column-name recognition can silently change μ. Such changes need a test with a real sample file.

## 4. GUI / 图形界面 (`xafsmith.qt`)

| Module | Role |
|---|---|
| `app.py` | main window, navigation, status bar (progress + cancel), update check, session save/restore |
| `state.py` | `State`: loaded groups, calibration, fits, current processing parameters; emits `changed(str)` |
| `session.py` | session snapshot (`output/gui/session.json`) and named fit drafts (`output/gui/drafts/`) |
| `pages/project.py` | home / project page |
| `pages/process/` | load, QC, calibration, normalization, χ(k)/FT, wavelet |
| `pages/fitting/` | FEFF; the “EXAFS fitting” container `fit_container.py` with Quick fit (`quick_fit.py`) and Detailed fit (`fit_page.py`); fit view (quality / diagnostics / robustness), trend view, history, LCF, XANES |
| `pages/output.py` | figures, Origin, reports, methods text |
| `widgets/` | shared widgets (`T()` bilingual text, tables, plots, prose/help, background tasks) |
| `help.py` | help window (guides, about, diagnostics, updates) |

Conventions / 约定

- Pages declare themselves: class attributes `key`, `title_zh`, `title_en`, `icon_name`, `needs`, `no_project`,
  `hidden` (defaults on `Page` in `widgets/layout.py`). `qt/app.py` keeps only the navigation order (`_NAV`) and
  derives `NEEDS`, `NO_PROJECT`, `HIDDEN`, `TABBED` and `PARENT` from the classes; the tabs of “Load & check” are
  `SpectraTabs.sub_pages`.
- Every user-visible string is bilingual: `T("中文", "English")`.
- Every feature must be reachable from the GUI and documented in both GUI guides.
- Old import paths (`from xafsmith.qt import widgets as W`, `pages.process.NormPage`, …) are kept by
  re-exports in the package `__init__` files. Mutable globals (`LANG`, `ERRORS`, `QUIET`, …) are defined in
  exactly one module.

### Feedback conventions / 反馈约定

- **Persistent or aggregated errors** (a failed load, spectra that failed to normalize) → in-page banner:
  `Page.notice(kind, title, lines, key=...)` (updates in place, with ×, survives a rebuild; `clear_notice(key)`
  removes it). Never one toast per item inside a loop.
  持续性 / 汇总的错误：页内 Banner。
- **Success and light hints** ("Saved …", "Exported …") → `W.toast(self, text, kind)`. The main window and the help
  window both implement `toast()` (shared `W.Toaster`).
  成功与轻提示：toast。
- **Blocking errors only** (the page cannot continue, unsaved-changes questions) → a dialog.
  只有阻断性错误才用对话框。
- Parameter widgets that redraw on every change use `W.debounced(fn)` (250 ms); spin boxes ignore the mouse wheel
  until focused (set by the global `NoWheelSpin` filter, see `widgets/inputs.py`).

### Background tasks and threads / 后台任务

Long work runs through `widgets.run_task(parent, fn, on_done, …)` (one `QThread` per task). With
`progress=True`, `fn` receives `handle.progress(fraction, text)`, which is also the cancellation point
(`xafsmith.tasks.TaskHandle`). `Cancelled` derives from `BaseException`, so `except Exception` blocks cannot
swallow it. Cancellation takes effect between steps; a single `feffit` or FEFF run cannot be interrupted.

Thread rules (see the header of `xafsmith/tasks.py`):
- a worker never creates or touches widgets and never mutates `State`;
- inputs are copied before the task starts; results are written back in `on_done` (GUI thread);
- matplotlib in workers uses the object API (`Figure` + Agg canvas), never `pyplot`.

What runs where: fits, FEFF, loading, report building and the wavelet transform run in tasks. The wavelet page tags
each request with a sequence number: one computation at a time, a request made while one runs is queued as a single
rerun with the latest settings, and a result that is no longer the latest is dropped. Short work stays on the GUI
thread under `wait_cursor`: χ(k)/FT redraws (about 0.1 s for ten spectra) and the journal-figure preview, which draws
on the page's Qt canvas and so must stay on the GUI thread.

## 5. Errors and logging / 错误与日志

`logs.py` configures a rotating log at `~/.xafsmith/xafsmith.log` on import and installs an exception hook.
Recoverable failures are logged (probing/fallback at `debug`, everything else at `warning`) and, in the GUI,
shown as a copyable error card. *About → Export diagnostics* bundles log, versions, environment and project
configuration — never raw data or spectra. Set `XAFSMITH_DEBUG=1` to record debug messages.

Exception classes (`errors.py`): `XafsmithError` → `ConfigError` (xafsmith.json / meta.csv), `DataError` (data files;
`readers.ReadError` is one), `ModelError` (model JSON; `quickfit.QuickFitError` is one) — all three also `ValueError` —
and `FeffError` (also `RuntimeError`). Each subclass keeps the builtin base its call sites raised before, so existing
`except` clauses are unaffected. Where a class name is shown to users (CLI top level, error banner and dialog, task
failures, `errors.explain`), `errors.shown_name` maps these classes back to that builtin name, so messages read as
before. `errors.explain(exc, lang)` turns an exception into “what happened / what you can do”.

## 6. Tests / 测试

| Suite | Content | Runs in CI |
|---|---|---|
| `tests/unit/` | one file per module (readers, schema, calib, normalize, tasks, session, update, …) | yes |
| `tests/benchmark/` | Cu-foil first shell vs Larch's `doc_feffit1` example, bit-identical to a direct Larch call, full-pipeline invariants; multi-dataset and restraint fits bit-identical to a frozen v1.1 copy (`_legacy_fit_v11.py`) in the single-dataset, unrestrained case, error calibration on synthetic spectra | yes |
| `tests/gui/` | page-by-page GUI test (pytest, offscreen) on a temporary copy of the public demo project, both languages. One session-scoped window; files run in the order of their two-digit prefix and share state (`ctx`); `say()` records each check and a test fails listing all its `[FAIL]` lines. `tests/test_qt.py` is a thin entry over it | yes |
| `tests/local/` | tests that need the author's own data (git-ignored), including `tests/local/gui/` (GUI checks specific to that project, on a temporary copy of it) | no |

Test data are public only (`tests/data/demo_project/SOURCES.md` records source and license of every file).

## 7. Packaging / 打包

`packaging/` builds the Windows release; see [docs/dev/RELEASING.md](docs/dev/RELEASING.md).

- `xafsmith.spec` (PyInstaller, one-folder): `XAFSmith.exe` (windowed) and `xafsmith-cli.exe` (console) share
  one `_internal/`. MKL, pyarrow, scikit-learn and other unused packages are excluded (evidence:
  `packaging/used_modules.py`); Larch falls back to `scipy.fftpack` without `mkl_fft`.
- `build.ps1`: isolated build environment → tests → PyInstaller → size guard (`size_report.py`) → smoke test
  of the packaged program (including a Cu-foil fit checked against the benchmark) → Inno Setup installer,
  portable zip and `SHA256SUMS.txt`.
- The frozen build's update check (`update.py`) queries the latest GitHub Release and never self-updates.

## 8. Where to start / 从哪里读起

| Task | Read first |
|---|---|
| new data format | `readers/base.py`, `readers/formats.py`, `docs/dev/io_readers.md` |
| processing parameters / validation | `pipeline.py`, `schema.py`, `docs/数据标准.md` |
| default values and shared constants | `defaults.py` (no Qt, no larch: processing defaults `NORM` / `BKG` / `FT` behind `normalize.DEFAULT_NORM`, `autobk.DEFAULT_BKG`, `ft.DEFAULT_FT`; the norm / bkg / ft written into a new `xafsmith.json` (`norm2 = -10`, not `None`: see the comment there); `META_COLS`; the two data-suffix sets, which differ on purpose; `USER_DIR` = `~/.xafsmith`, also `paths.USER_DIR`, kept here because `logs` is imported before `--project` is parsed); `tests/unit/test_defaults.py` |
| project paths | `paths.py`: `paths.current()` is the active `Project` (frozen; the root and every standard path as properties); `set_root` builds it and copies its `module_vars()` into the module-level names (`paths.ROOT`, `paths.FITS`, …), which existing code keeps using; `tests/unit/test_paths_project.py` |
| version number | only `__version__` in `src/xafsmith/__init__.py`; `pyproject.toml` reads it (`dynamic = ["version"]`); `CITATION.cff` is written by hand and `tests/unit/test_version.py` checks it matches |
| model JSON structure checks | `modelcheck.py`: one set of structure rules used two ways, like `sigma2.model_issues`: `schema` reports every issue (`strict=True`), `fit_exafs.normalize_model` raises on the first (`strict=False`). The two modes keep the rules each side had before v1.4.2 (listed in the module); `tests/unit/test_modelcheck.py` pins both outputs for 97 synthetic models |
| config version and migration | `migrate.py`: `pipeline.load_config` upgrades an older `xafsmith.json` in memory, step by step through `MIGRATIONS`, and never writes the file back; a version newer than `paths.SCHEMA_VERSION` or one that cannot be parsed is refused. `schema.validate` reads the file as it is. To change the data standard: raise `SCHEMA_VERSION`, register a step from the previous version, update `docs/数据标准.md`; `tests/unit/test_migrate.py` |
| fitting (Detailed fit) | `fit_exafs.py`, `qt/pages/fitting/fit_page.py`, `docs/XAFS处理规范.md` |
| Quick fit (first shell, joint, mixed phase, verdict) | `quickfit.py` (no Qt: first shell, automatic Rmin, model building, verdict thresholds as module constants), `fitcheck.py` (quality checks shared with Detailed fit), `s02_source.py` (standard-fit S0² candidates), `qt/pages/fitting/quick_fit.py`, `GLOSSARY.md`, `docs/adr/0001-*` |
| joint-fit series (trend table, trend figure, user trend order, σ² independence, tick sync) | `trend.py` (no Qt: seq variable, N_err rule, shared flags, quick-fit first-shell rows, user order), `seqtools.py`, `pubfig.trend`, `origin_export._errorbar_parts`, `qt/pages/fitting/trend_view.py`, `docs/数据标准.md` |
| run a model / save a result (fit, robustness, comparison, LCF, XANES, QC, calibration, merged scans) | `services.py` (no Qt, no print: the single implementation both the CLI and the GUI call; every save also writes `*.params.json`, except the merge report, which never had one; file names use `pipeline.safe`; `tests/unit/test_services.py`) |
| the model the Detailed-fit page builds | `services.build_fit_model`, `params_from_table`, `paths_from_table`, `default_param_row` (pure functions; starting values of new parameters in `defaults.FIT_PARAM_DEFAULTS`); `fit_page.py` only collects the tables, and its card builders share one `_CardCtx`; `tests/unit/test_fit_model_build.py` |
| reading files picked in the GUI | `io.read_direct` (auto-detect, a reader, a template, or column numbers given by the user, which become a temporary template and take the same path as saved templates; `.prj` returns every group) |
| wavelet maxima | `wavelet.compute` / `wavelet.maxima` (the page only formats the table and draws) |
| a GUI page | `qt/app.py` (navigation), the page module, `qt/widgets/` |
| release | `packaging/`, `.github/workflows/release.yml`, `docs/dev/RELEASING.md` |
| adding a format, an analysis or a page | the three checklists in [CONTRIBUTING.md](CONTRIBUTING.md) |

## 9. Module index / 模块一览

Every module under `src/xafsmith/` (package `__init__.py` / `__main__.py` and the data folders `assets/`, `docs/`,
`templates/`, `structures_builtin/` aside). `tests/unit/test_consistency.py` fails when a module is missing here.
`src/xafsmith/` 下每个模块都列在这里；漏列时一致性测试失败。

### Computation and infrastructure (no Qt) / 计算与基础设施

| Module | Role |
|---|---|
| `cli.py` | the `xafsmith` command line; each subcommand calls `services` / the computation modules |
| `services.py` | single service layer shared by CLI and GUI: run a model, save fits, robustness, comparison, LCF, XANES, QC, calibration, merged scans; build the Detailed-fit model dict |
| `pipeline.py` | configuration-driven batch processing: meta.csv + xafsmith.json → calibration → normalization → merge → χ(k) → FT |
| `paths.py` | project directory standard; every project path |
| `defaults.py` | default values and shared constants (no Qt, no larch) |
| `schema.py` | data standard checks for meta.csv, xafsmith.json and model JSON (`xafsmith validate`) |
| `modelcheck.py` | model JSON structure rules, collecting (`schema`) or raising (`fit_exafs`) |
| `migrate.py` | xafsmith.json version migration, in memory only |
| `common.py` | shared helpers: parameter records, atomic writes, k/E conversion, edge energies |
| `errors.py` | exception classes and plain-language error explanations |
| `typedefs.py` | `TypedDict` declarations for configuration, models and fit records (mypy only) |
| `logs.py` | logging and the diagnostics bundle |
| `tasks.py` | cancellable task handle with progress, shared by GUI and CLI |
| `update.py` | update check against GitHub Releases |
| `about.py` | author, disclaimer and citation text used everywhere |
| `agent.py` | connects a project to AI assistants (`xafsmith agent`) |
| `io.py` | facade: read beamline data into a Larch Group; `read_direct` for files picked in the GUI |
| `readers/base.py` | `Reader` base class, `ReadError`, column-name mapping, text-table parsing |
| `readers/formats.py` | one reader per built-in format |
| `readers/wizard.py` | column-mapping wizard back end (preview, template, trial read) |
| `qc.py` | data quality checks → `qc_report.csv` |
| `calib.py` | energy calibration from the reference foil |
| `normalize.py` | scan merging, pre/post-edge, normalization, E0 |
| `autobk.py` | background removal (Larch `autobk`) → χ(k) |
| `ft.py` | k-space windows and Fourier transform (Larch `xftf`) |
| `wavelet.py` | wavelet transform of χ(k); `compute` and `maxima` used by the wavelet page |
| `structures.py` | built-in reference structures and CIF reading |
| `feff_wrap.py` | structure → feff.inp → FEFF6L / FEFF8L → path list |
| `fit_exafs.py` | EXAFS path fitting (Larch `feffit` wrapper), multi-dataset, F-test, comparison |
| `_feffit_restrained.py` | `feffit` driver with soft restraints (adapted from Larch) |
| `fitcheck.py` | fit quality checks shared by Quick and Detailed fit |
| `quickfit.py` | Quick fit: first shell only, with a plain-language verdict |
| `quickfit_report.py` | Quick fit report bundle (figures, tables, verdict, methods, HTML) |
| `s02_source.py` | S0² candidates from standard fits |
| `msbind.py` | ΔR / σ² binding suggestions for multiple-scattering paths |
| `sigma2.py` | Debye / Einstein σ² temperature models |
| `trend.py` | trend table of a joint-fit series |
| `seqtools.py` | joint-fit series tools (independent σ², tick sync) |
| `fit_lcf.py` | linear combination fitting (XANES / EXAFS) |
| `xanes.py` | XANES: edge position, white line, valence calibration, pre-edge peaks |
| `mut_planner.py` | sample design: total μt, edge step, mass / layers, nearby edges |
| `report.py` | figures with automatic captions and result tables |
| `pubfig.py` | journal-style figures (TIFF / PNG / SVG / PDF) |
| `summary.py` | project summary workbook and HTML report |
| `methods_text.py` | methods paragraph (Chinese + English) from the parameters actually used |
| `si_text.py` | Supporting Information tables from saved fits |
| `origin_export.py` | figures as an Origin project (.opju) |
| `origin_builder.py` | stand-alone Origin project builder (needs only `originpro` and pandas) |

### GUI (`qt/`) / 图形界面

| Module | Role |
|---|---|
| `qt/app.py` | main window, navigation (`_NAV`), status bar, update check, session save / restore |
| `qt/state.py` | session state and shared processing helpers |
| `qt/session.py` | session snapshot and named fit drafts |
| `qt/theme.py` | colours, fonts, style sheets, icons, matplotlib style |
| `qt/help.py` | help window (guides, about, diagnostics, updates) |
| `qt/colwizard.py` | column-mapping wizard dialog |
| `qt/errdialog.py` | three-part error dialog |
| `qt/pages/_common.py` | constants and helpers shared by pages |
| `qt/pages/project.py` | home, data registration, batch processing |
| `qt/pages/output.py` | reports, figures, methods; planner, elements, AI assistant, help pages |
| `qt/pages/process/_shared.py` | helpers shared by processing pages |
| `qt/pages/process/load.py` | Load spectra |
| `qt/pages/process/qc.py` | Quality check and deglitching |
| `qt/pages/process/calib.py` | Energy calibration |
| `qt/pages/process/norm.py` | Normalization |
| `qt/pages/process/chi.py` | χ(k) and FT |
| `qt/pages/process/wavelet.py` | Wavelet transform |
| `qt/pages/fitting/feff.py` | FEFF paths |
| `qt/pages/fitting/fit_container.py` | “EXAFS fitting” container: Quick fit / Detailed fit |
| `qt/pages/fitting/quick_fit.py` | Quick fit page |
| `qt/pages/fitting/fit_page.py` | Detailed fit page (path and parameter tables) |
| `qt/pages/fitting/fit_view.py` | one fit result: quality, diagnostics, robustness |
| `qt/pages/fitting/quality.py` | interface text for fit quality checks (logic in `fitcheck`) |
| `qt/pages/fitting/trend_view.py` | trend tab of joint-fit results |
| `qt/pages/fitting/guides.py` | fitting notes (three tabs) and their dialog |
| `qt/pages/fitting/msbind_dialog.py` | multiple-scattering binding dialog |
| `qt/pages/fitting/sigma2_dialog.py` | σ² temperature-model dialog |
| `qt/pages/fitting/history.py` | Fit history |
| `qt/pages/fitting/lcf.py` | Linear combination fitting |
| `qt/pages/fitting/xanes.py` | XANES analysis |
| `qt/widgets/core.py` | global state (language, error list, quiet switch); `T()` |
| `qt/widgets/basic.py` | labels, separators, buttons, rows, form fields |
| `qt/widgets/inputs.py` | spin boxes, text fields, combos, check boxes, segmented buttons |
| `qt/widgets/layout.py` | cards, `Page` base class, banners, metrics, tabs, collapsibles |
| `qt/widgets/plot.py` | matplotlib canvas widget |
| `qt/widgets/prose.py` | code blocks, copy buttons, rich text, info windows, confirmations |
| `qt/widgets/system.py` | toasts, open folder, save-as |
| `qt/widgets/table.py` | editable DataFrame table |
| `qt/widgets/tasks.py` | `run_task` (QThread, progress, cancel) and `wait_cursor` |
