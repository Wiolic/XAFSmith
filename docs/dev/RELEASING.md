# Release procedure / 发布流程

Releases are Windows-only for 1.x (installer + portable zip). macOS packaging is experimental
(`release.yml` → `macos` job, manual runs only) and is not published.

## 1. Prepare / 准备

1. All changes merged to `main`; CI (`ci.yml`) green on Windows and Ubuntu.
2. Version number in **both** `pyproject.toml` (`version`) and `src/xafsmith/__init__.py` (`__version__`).
   `release.yml` refuses a tag that does not match.
3. `CHANGELOG.md`: move *Unreleased* to the new version with the date; record the measured installer and
   unpacked sizes (from `build/size_report.csv` and `dist/`).
4. Version references in `README.md` / `README_en.md` (citation line) and `CITATION.cff`.

## 2. Local build / 本机构建

Requirements: Windows, Python 3.12, [Inno Setup 6](https://jrsoftware.org/isinfo.php).

```powershell
cd XAFSmith
powershell -ExecutionPolicy Bypass -File packaging\build.ps1 -Iscc "<path>\ISCC.exe"
```

`build.ps1` steps (any failure stops the build):

| Step | What it checks |
|---|---|
| 1 | creates `.venv-build` (separate from your `.venv`), installs XAFSmith, **removes MKL** |
| 2 | `pytest tests/unit tests/benchmark` in that environment (numerical results without MKL) |
| 3 | PyInstaller; `size_report.py` size guard (default limit 550 MB unpacked; forbidden packages) |
| 4 | smoke test of the packaged `xafsmith-cli.exe`: `--version`, `validate`, `process` on a copy of the demo project, Cu-foil fit compared with the benchmark (S0² 0.917, ΔE0 4.37 eV, σ² 0.00867 Å²) |
| 5 | Inno Setup installer, portable zip, `SHA256SUMS.txt` in `dist/` |

Options: `-SkipTests`, `-SkipInstaller`, `-LimitMB`, `-Python`, `-Iscc`.

Notes: `build.ps1` must stay UTF-8 **with BOM** (Windows PowerShell 5.1). Packaged sizes of v1.0 candidates:
about 470 MB unpacked, 126 MB installer.

## 3. Trial build on GitHub / 试构建

Actions → *Release* → *Run workflow* (`workflow_dispatch`). Artifacts are uploaded to the run, no Release is
created. Download the installer for acceptance testing.

## 4. Acceptance on a clean machine / 干净机器验收

Follow [`packaging/ACCEPTANCE.md`](../../packaging/ACCEPTANCE.md) on a Windows PC that has never had Python or
XAFSmith installed (offline install, Chinese/space paths, demo project six-step workflow, diagnostics bundle,
uninstall/upgrade). **Do not tag if any item fails.**

## 5. Tag and publish / 打标签发布

```bash
git tag v1.0.0
git push origin v1.0.0
```

`release.yml` builds with `build.ps1`, then publishes `XAFSmith-<ver>-Setup.exe`,
`XAFSmith-<ver>-win64-portable.zip` and `SHA256SUMS.txt` to the GitHub Release. Afterwards download the
installer from the Release page and install it once more.

## Known limitations / 已知限制

- The installer is not code-signed (SmartScreen warning; some antivirus programs may flag it).
- `opengl32sw.dll` (software OpenGL, 20 MB) is still bundled until acceptance on machines without a GPU driver
  shows it can be removed.
