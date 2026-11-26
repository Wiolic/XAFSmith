# Contributing / 参与开发

Thank you for helping improve XAFSmith. Issues and pull requests may be written in English or Chinese.
欢迎提交问题和改进；Issue 与 PR 用中文或英文均可。

XAFSmith is licensed under the [GPL-3.0-only](LICENSE), and the author also offers separate commercial licenses
(dual licensing). By submitting a contribution (pull request, patch or code in an issue) you confirm that you wrote it
or have the right to submit it, and you agree that:
1. it is distributed under GPL-3.0-only, and
2. you grant the author (Eggy) a perpetual, worldwide, non-exclusive, royalty-free, irrevocable license to use,
   modify and relicense your contribution, including under commercial license terms.
You keep the copyright in your contribution. Please say so in the pull request if you do not agree; the change can then
not be merged.

XAFSmith 按 [GPL-3.0-only](LICENSE) 发布，作者另外提供商业授权（双重许可）。提交贡献（PR、补丁或 Issue 中的代码）即表示：
你是作者或有权提交；同意贡献按 GPL-3.0-only 发布；并授予作者（Eggy）永久、全球、非独占、免费、不可撤销的许可，
可使用、修改并以其他许可（包括商业许可）再授权你的贡献。贡献的版权仍归你。若不同意，请在 PR 中说明，该改动将无法合并。

## Reporting a problem / 报告问题

Open a [GitHub issue](https://github.com/Wiolic/XAFSmith/issues) with:
- the version (*About* page or `xafsmith --version`) and how it was installed (installer / source);
- the steps, what you expected and what happened;
- the **diagnostics bundle** (*About → Export diagnostics*; it contains no raw data or spectra);
- for an unrecognised data format: one sample file (only if you are allowed to share it).

## Development setup / 开发环境

```bash
git clone https://github.com/Wiolic/XAFSmith
cd XAFSmith
python -m venv .venv
.venv/Scripts/python -m pip install -e ".[dev]"      # Linux/macOS: .venv/bin/python
```

Python 3.11 or 3.12 (the versions tested in CI). Read [ARCHITECTURE.md](ARCHITECTURE.md) first.

## Checks after changing code / 改代码后的检查

This is the only authoritative list; `AGENTS.md` files link here. Run from `XAFSmith/` with the project `.venv`.
这是唯一权威版本，其他文档只引用本节。

```bash
python -m pytest tests/unit tests/benchmark        # includes tests/benchmark/test_golden.py (golden baseline)
python -m pytest tests/gui -q                      # page-by-page GUI test on a temporary copy of the public demo project (offscreen)
python -m pytest tests/local                       # only on a machine that has the private project (git-ignored; includes tests/local/gui)
python -m ruff check src tests tools               # 0 errors; do not run `ruff format`
python -m mypy                                     # 0 errors; checks the modules listed in pyproject [tool.mypy] (non-strict)
```

- The first, second, fourth and fifth commands must pass; CI runs them on Windows and Ubuntu with Python 3.11 and 3.12.
- `python tests/test_qt.py` still works as a thin entry over `tests/gui` (`--project <dir>` runs `tests/local/gui` for the
  IrTaOx project, `--quick` skips FEFF8L and robustness). GUI tests always run on a temporary copy of the project and never
  write to it. `tests/gui` is a pipeline: files run in the order of their two-digit prefix and share state, so a file run
  alone skips the checks whose prerequisites are missing; `test_99_english.py` must stay last.
- Fitting changes, on a machine that has the private IrTaOx project only: `xafsmith fit IrO2_1shell_ArtemisCompare --nosave`
  must give S0² ≈ 0.816 and ΔE0 ≈ 8.93; `tests/local` includes the `tools/golden.py local` snapshot.
- If a number changes **on purpose**: rewrite the baseline with `python tools/golden.py demo --write` and state the reason
  in the commit message (and in the PR). Never loosen a tolerance just to make a test pass.
  数值有意改变时重写基线并在提交信息里写明原因。

## Rules / 规则

1. **Numerical changes need evidence.** Changes to `calib`, `normalize`, `autobk`, `ft`, `fit_exafs`,
   `fit_lcf` or `xanes` must keep the benchmarks green; if a reference value changes, explain why in the PR and
   cite the source of the new value. Never adjust a tolerance just to make a test pass.
   涉及数值的改动必须保持基准测试通过；参考值变化须说明原因与出处。
2. **Data formats need a real sample file**, not a format written from memory. Column recognition is by name,
   never by position.
3. **GUI**: every feature must be reachable with the mouse; all text bilingual via `T("中文", "English")`;
   update both `src/xafsmith/docs/图形界面使用指南.md` and `src/xafsmith/docs/GUI_guide_en.md`.
4. **Data standard**: changes to project files update `docs/数据标准.md`, `schema.py` (validate) and
   `templates/` together.
5. **Paths** only through `xafsmith.paths`; raw data are read-only; outputs go under `output/`.
6. **Threads**: follow the rules in `xafsmith/tasks.py` (no widgets or `State` changes in workers).
7. **Test data must be public** and recorded in `tests/data/demo_project/SOURCES.md` with source and license.
   Do not commit your own measurements.
8. Keep `LICENSE`, `NOTICE`, `CITATION.cff` and the citation text in `src/xafsmith/about.py` intact.
9. Add an entry under *Unreleased* in [CHANGELOG.md](CHANGELOG.md). At release the section is renamed to the version
   and becomes the GitHub Release notes verbatim (`tools/release_notes.py`, used by `release.yml`), so write
   **everything that changed** there; a release without its CHANGELOG section fails.
   发布时这一节就是 GitHub Release 说明的全文：改了什么都写在这里。
10. **Version number**: change it only in `src/xafsmith/__init__.py` (`__version__`; `pyproject.toml` reads it) and in
    `CITATION.cff` (`version`, `date-released`); `tests/unit/test_version.py` fails if the two differ. After changing it,
    reinstall the development install (`pip install -e . --no-deps`) so `importlib.metadata` sees the new number.
    版本号只改 `__init__.py` 与 `CITATION.cff` 两处。
11. **Lint rules**: the ruff rules switched on are listed, with the reasons for those left off, in `pyproject.toml`
    `[tool.ruff.lint]`. A `# noqa` needs a short reason on the same line. Switch on a new rule family in a commit of its own,
    and only with fixes that leave every string and number unchanged.
    新开一组 ruff 规则单独一个提交；`# noqa` 写明理由。

## Adding things / 新增一种格式、一个分析、一个页面

Three checklists. `tests/unit/test_consistency.py` fails when a CLI command, a page title or a module is missing from
the documents named below, so most forgotten steps show up in the tests.
三张清单；漏写文档时 `tests/unit/test_consistency.py` 会失败。

### A data format / 一种读入格式
1. A real sample file first (rule 2). If it may be shared, put it in `tests/data/` and record it in
   `tests/data/demo_project/SOURCES.md`.
2. Subclass `Reader` (`readers/base.py`): `name` (unique), `label = ("中文", "English")`, `suffixes`,
   `detect(path, head) -> 0–100` and `read(path, mode=None, columns=None, group=None) -> list[Group]`. Recognise columns
   by name, never by position; raise `ReadError(zh, en)` with both languages.
3. Built into XAFSmith: add the class to `readers/formats.py` and to `REGISTRY` in `readers/__init__.py`. The order of
   `REGISTRY` decides ties in detection, so new formats go **before** the catch-all `ColumnsReader` and must not change
   which reader wins for existing files (the golden baseline would show it).
   As a separate package: register it in the entry-point group `xafsmith.readers`; it is appended after the built-in
   readers, and a plugin that fails to load, is not a `Reader` or reuses a name is logged and skipped:
   ```toml
   [project.entry-points."xafsmith.readers"]
   myformat = "my_package.reader:MyReader"
   ```
4. A unit test that reads the sample file; `docs/dev/io_readers.md` and the format list in `src/xafsmith/docs/数据标准.md`.

### An analysis / 一个分析
1. The calculation goes in its own module under `src/xafsmith/`, with no Qt imports. Defaults and constants go in
   `defaults.py`, never repeated at the call site.
2. Anything that writes files goes in `services.py`, so the command line and the interface save the same files with
   the same names (`services.safe`) and a `.params.json` (`common.write_params`). Writes go through
   `common.write_text_atomic`.
3. Errors: raise `ConfigError` / `DataError` / `ModelError` / `FeffError` (`errors.py`) with a bilingual message;
   they are still `ValueError` / `RuntimeError`, so callers' `except` clauses keep working.
4. A `xafsmith <command>` in `cli.py` that calls the service, and its line in `src/xafsmith/docs/命令行速查.md`.
5. A GUI place to run it (next checklist, or a card on an existing page) — rule 3.
6. Tests: unit tests for the calculation; if it produces numbers that users report, add them to the golden snapshot
   (`tools/golden.py`) and rewrite the baseline in a commit that says why.
7. `ARCHITECTURE.md` module table and a CHANGELOG entry.

### A page / 一个页面
1. A `Page` subclass (`qt/widgets/layout.py`) with the class attributes `key` (unique), `title_zh`, `title_en`,
   `icon_name`, and when they apply `needs` (data the page requires: `"groups"`, `"feff"`), `no_project = True` (usable
   without an open project) and `hidden = True` (not in the navigation).
2. Add the class to `_NAV` in `qt/app.py` (navigation order; `None` is the gap between groups). The tables `NEEDS`,
   `NO_PROJECT`, `HIDDEN`, `TABBED` and `PARENT` are derived from the classes, do not edit them by hand. A tab inside
   "Load & check" goes in `SpectraTabs.sub_pages` instead.
3. Long work goes through `run_task` (rule 6); no calculation in the page itself — call the calculation module or
   `services`.
4. Every string via `T("中文", "English")`; a section in both GUI guides whose text contains the page title
   (`title_zh` in `图形界面使用指南.md`, `title_en` in `GUI_guide_en.md`).
5. A check in `tests/gui/` (in the file whose number matches where the page's data become available, or a new
   `test_NN_<topic>.py`; checks shared with `tests/local/gui` go in `tests/gui/checks.py`), and the `ARCHITECTURE.md` GUI table.

## AI assistants / AI 助手

AI assistants working on this repository should read [AGENTS.md](AGENTS.md). Results must be labelled
*measured / fitted / inferred*; things that could not be verified locally (CI, installers on a clean machine,
macOS) must be reported as **not verified**.
