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
            ├────────────────────────────────────────────────────────┤
            │ paths │ schema │ logs │ tasks │ update │ about           │  ← infrastructure
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

A project is a folder containing `xafsmith.json` (schema 1.0). The full specification is
[`src/xafsmith/docs/数据标准.md`](src/xafsmith/docs/数据标准.md); `xafsmith validate` (module `schema`) checks it.

| Path | Content |
|---|---|
| `data/raw/` | raw data, **read-only** |
| `data/meta.csv` | one row per file: sample, edge, mode, role, reference file, `use` flag |
| `xafsmith.json` | processing parameters per edge, per-sample overrides (with reasons), deglitch list, S0² |
| `models/*.json` | EXAFS fit models (paths, parameters, constraints, k/R ranges) |
| `structures/` | CIF / structure files for FEFF |
| `output/` | everything generated: `processed/`, `feff/`, `fits/`, `figs/`, `reports/`, `gui/` (session, drafts) |
| `notes/` | analysis notes |

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
   │      feff_wrap (FEFF6L/8L) ─► fit_exafs (feffit; N_idp, χ²_ν, R-factor, F-test, robustness)
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

> Changing column-name recognition can silently change μ. Such changes need a test with a real sample file.

## 4. GUI / 图形界面 (`xafsmith.qt`)

| Module | Role |
|---|---|
| `app.py` | main window, navigation, status bar (progress + cancel), update check, session save/restore |
| `state.py` | `State`: loaded groups, calibration, fits, current processing parameters; emits `changed(str)` |
| `session.py` | session snapshot (`output/gui/session.json`) and named fit drafts (`output/gui/drafts/`) |
| `pages/project.py` | home / project page |
| `pages/process/` | load, QC, calibration, normalization, χ(k)/FT, wavelet |
| `pages/fitting/` | FEFF, fit page, fit view (quality / diagnostics / robustness), history, LCF, XANES |
| `pages/output.py` | figures, Origin, reports, methods text |
| `widgets/` | shared widgets (`T()` bilingual text, tables, plots, prose/help, background tasks) |
| `help.py` | help window (guides, about, diagnostics, updates) |

Conventions / 约定

- Every user-visible string is bilingual: `T("中文", "English")`.
- Every feature must be reachable from the GUI and documented in both GUI guides.
- Old import paths (`from xafsmith.qt import widgets as W`, `pages.process.NormPage`, …) are kept by
  re-exports in the package `__init__` files. Mutable globals (`LANG`, `ERRORS`, `QUIET`, …) are defined in
  exactly one module.

### Background tasks and threads / 后台任务

Long work runs through `widgets.run_task(parent, fn, on_done, …)` (one `QThread` per task). With
`progress=True`, `fn` receives `handle.progress(fraction, text)`, which is also the cancellation point
(`xafsmith.tasks.TaskHandle`). `Cancelled` derives from `BaseException`, so `except Exception` blocks cannot
swallow it. Cancellation takes effect between steps; a single `feffit` or FEFF run cannot be interrupted.

Thread rules (see the header of `xafsmith/tasks.py`):
- a worker never creates or touches widgets and never mutates `State`;
- inputs are copied before the task starts; results are written back in `on_done` (GUI thread);
- matplotlib in workers uses the object API (`Figure` + Agg canvas), never `pyplot`.

## 5. Errors and logging / 错误与日志

`logs.py` configures a rotating log at `~/.xafsmith/xafsmith.log` on import and installs an exception hook.
Recoverable failures are logged (probing/fallback at `debug`, everything else at `warning`) and, in the GUI,
shown as a copyable error card. *About → Export diagnostics* bundles log, versions, environment and project
configuration — never raw data or spectra. Set `XAFSMITH_DEBUG=1` to record debug messages.

## 6. Tests / 测试

| Suite | Content | Runs in CI |
|---|---|---|
| `tests/unit/` | one file per module (readers, schema, calib, normalize, tasks, session, update, …) | yes |
| `tests/benchmark/` | Cu-foil first shell vs Larch's `doc_feffit1` example, bit-identical to a direct Larch call, full-pipeline invariants | yes |
| `tests/test_qt.py` | page-by-page GUI test (offscreen) on the public demo project, both languages | yes |
| `tests/local/` | tests that need the author's own data (git-ignored) | no |

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
| fitting | `fit_exafs.py`, `qt/pages/fitting/fit_page.py`, `docs/XAFS处理规范.md` |
| a GUI page | `qt/app.py` (navigation), the page module, `qt/widgets/` |
| release | `packaging/`, `.github/workflows/release.yml`, `docs/dev/RELEASING.md` |
