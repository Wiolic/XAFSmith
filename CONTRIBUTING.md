# Contributing / 参与开发

Thank you for helping improve XAFSmith. Issues and pull requests may be written in English or Chinese.
欢迎提交问题和改进；Issue 与 PR 用中文或英文均可。

XAFSmith is licensed under the [MIT License](LICENSE). By contributing you agree that
your contribution is distributed under the same license. 贡献的代码按同一许可发布。

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

## Before you open a pull request / 提交前检查

```bash
python -m ruff check src tests tools
python -m pytest tests/unit tests/benchmark
python tests/test_qt.py            # page-by-page GUI test on the public demo project (offscreen)
```

All three must pass. CI runs them on Windows and Ubuntu with Python 3.11 and 3.12.

## Rules / 规则

1. **Numerical changes need evidence.** Changes to `calib`, `normalize`, `autobk`, `ft`, `fit_exafs`,
   `fit_lcf` or `xanes` must keep the benchmarks green; if a reference value changes, explain why in the PR and
   cite the source of the new value. Never adjust a tolerance just to make a test pass.
   涉及数值的改动必须保持基准测试通过；参考值变化须说明原因与出处。
2. **Data formats need a real sample file**, not a format written from memory. Column recognition is by name,
   never by position.
3. **GUI**: every feature must be reachable with the mouse; all text bilingual via `T("中文", "English")`;
   update both `docs/图形界面使用指南.md` and `docs/GUI_guide_en.md`.
4. **Data standard**: changes to project files update `docs/数据标准.md`, `schema.py` (validate) and
   `templates/` together.
5. **Paths** only through `xafsmith.paths`; raw data are read-only; outputs go under `output/`.
6. **Threads**: follow the rules in `xafsmith/tasks.py` (no widgets or `State` changes in workers).
7. **Test data must be public** and recorded in `tests/data/demo_project/SOURCES.md` with source and license.
   Do not commit your own measurements.
8. Keep `LICENSE`, `NOTICE`, `CITATION.cff` and the citation text in `src/xafsmith/about.py` intact.
9. Add an entry under *Unreleased* in [CHANGELOG.md](CHANGELOG.md).

## AI assistants / AI 助手

AI assistants working on this repository should read [AGENTS.md](AGENTS.md). Results must be labelled
*measured / fitted / inferred*; things that could not be verified locally (CI, installers on a clean machine,
macOS) must be reported as **not verified**.
