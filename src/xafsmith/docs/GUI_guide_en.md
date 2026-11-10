# XAFSmith GUI guide (mouse only)

> ⚠️ **Disclaimer**: XAFSmith is provided "as is", without warranty of any kind. The authors accept no responsibility for results obtained with it. Please validate your results; **we recommend cross-checking key results against Athena / Artemis**.
> 📖 **Citation**: if you use XAFSmith in a publication, please cite Eggy & Claude, XAFSmith, https://github.com/Wiolic/XAFSmith, together with Larch and FEFF (“Disclaimer & citation” at the bottom of the window copies the references).

This guide is for users who do not program or type commands. With a working knowledge of XAFS you can complete the whole workflow by clicking:
**register data → calibrate & process → FEFF → EXAFS fitting → LCF / XANES → summary, journal figures, SI**.
New to XAFS? Read **XAFS basics** on the Help page first; for your first fit, read the **Beginner fitting tutorial**.

---

## 1. Installation (once)

1. Install Python 3.11 or 3.12 from https://www.python.org/downloads/windows/ and **tick “Add python.exe to PATH”** during installation.
2. On https://github.com/Wiolic/XAFSmith click **Code → Download ZIP** and unzip it anywhere.
3. Double-click **`installer.py`** in the unzipped folder. The bilingual installer wizard asks for:
   - **Install location** (default `C:\Users\<you>\AppData\Local\Programs\XAFSmith`; “浏览…” = Browse);
   - desktop shortcut, Start-menu shortcut (with uninstaller), launch after installation;
   - tick **“I have read and agree”** and click **Install**. Internet is required; it takes 5–15 minutes.
   - If double-clicking `installer.py` does nothing or opens it in a text editor: right-click → Open with → Python, or reinstall Python making sure “Add python.exe to PATH” and the “py launcher” are ticked.
4. The unzipped folder can be deleted afterwards.

To use XAFSmith: **double-click XAFSmith on the desktop (or in the Start menu)**. It is a native desktop program that opens in a few seconds — no web browser. Close the window to quit.
Uninstall: Start menu → XAFSmith → uninstall (your projects and data are not touched).

---

## 2. The window

- **Sidebar**:
  - top: name and credit (Developed by Eggy & Claude Opus 5.5) and the **Open / new project** button;
  - middle: the pages, grouped by workflow (groups separated by space):
    1. **Project, Register data, Calibrate & process** — preparation;
    2. **Load spectra, Quality check, Energy calibration, Normalization, χ(k) & FT, Wavelet transform** — inspecting data;
    3. **FEFF paths, EXAFS fitting, Fit history, LCF, XANES quantification** — analysis;
    4. **Summary report, Journal figures, SI methods** — export;
    5. **Sample design, AI assistant, Help** — tools and help.
  - bottom: the current project (hover for the full path) and the **中文 / English** switch (remembered). A notice appears above the project when an update is available.
- **Bottom of the window**: a disclaimer line, always visible; **Disclaimer & citation** opens the full text and copies the citation.
- **Plots**: the four buttons at the top right are pan, zoom to box, reset and save image; the cursor position is shown at the top left.
- **Tables**: double-click a cell to edit; click tick boxes; some columns offer a drop-down.
- **Multi-selects**: open, search, tick; “All / None” for bulk changes.
- **Long calculations** (process all, FEFF, fits, robustness, summary) run in the background: the window stays responsive, a thin progress bar appears at the top and progress at the bottom left.
- Light / dark follows the Windows setting.

---

## 3. Create a project (once per study)

A “project” is a folder in which raw data, structures and all results are kept in a fixed layout.

1. Click **Open / new project** at the top left; under “Open or create a project” click **Browse…**, choose an empty folder and click **Create project**.
2. To reopen it later, **double-click** it under “Recent projects”, or double-click **打开图形界面.bat** in the project folder.

The project folder contains `data/raw` (raw data), `structures`, `models` (fit models), `notes` and `output` (all results).

With a project open, the **Project** page shows the six-step **Workflow** (register data, calibrate & process, inspect spectra, FEFF paths, fit, export): finished steps are ticked, the next one has a blue frame, and **Open →** goes to the page. Below are **Output** (file counts per result folder, with buttons to open them) and **This session** (spectra loaded, fits; **Save session parameters**).

## 4. Add and register raw data (Register data)

1. Use one “batch” per beamtime: enter a **Batch folder** (e.g. `2026-11-05_Ta`) and click **Choose files and copy to batch…** to copy all raw files of that beamtime into `data/raw/<batch>/` (originals untouched, existing files never overwritten).
   **Each batch must contain the elemental reference measured in that beamtime** (metal foil or powder; file name containing foil / powder / metal).
   You can also copy files into `data\raw\<batch>\` with Windows Explorer.
2. Click **Scan data/raw and register new files**. The `data/meta.csv` table shows one row per raw file.
3. Check and edit the table (double-click cells), then **Save meta.csv**:
   - **sample**: rows with the same name are repeated scans and are merged;
   - **role**: `reference` for foils, `standard` for standards, `sample` for samples;
   - **use**: `0` excludes a scan (write the reason in **note**);
   - **ref_file**: the reference used to calibrate the spectrum (defaults to the reference of the same batch). Spectra without one cannot be processed.
4. At the bottom, **Validate against the data standard → Run check** until there are no errors.

## 5. Calibrate & process

**Processing parameters** (choose the edge at the top right; one set per edge, shared by all samples of that edge):
- **All elements in the sample**: used to check interfering edges and the usable k limit (e.g. `Ta, Ir, O, K`).
- **Normalization** (pre1, pre2, norm1, norm2, nnorm, E0 smoothing) and **background removal & Fourier transform** (rbkg, k-weights, kmin, kmax, dk, window).
- **S0²** (value, error, source): leave it for now; fill it in after fitting the standard (section 8).

Click **Save parameters**, then under **Batch run**:
1. **① Quality check**: glitches (glitch_E), I0 drop-outs, edge step, k_snr3 (usable k), fluorescence self-absorption risk.
2. **② Calibrate with references**: one ΔE per reference; every spectrum of the batch gets the same ΔE.
3. **③ Process all samples**: calibrate → normalize → merge → χ(k) → FT. Results go to `output/processed` and `output/figs`.

## 6. Inspect the spectra

**Load spectra**: tick samples (or choose **a whole edge**) and click **Load**; references are loaded too. Loaded spectra are calibrated, normalized and merged, with χ(k) and FT computed. The table lists them with their calibration status; you can view raw μ(E) and the I0 / I1 / If channels, or remove spectra from the session (files are kept). “Read files directly” (BSRF / Athena .prj / column text) is for files not in meta.csv and requires a reference from the same batch.

**Quality check**: runs the check on loaded spectra (written to `output/qc/qc_report.csv`).

**Deglitch** (bottom of Quality check): choose samples (the same ranges apply to all selected) and inspect μ(E) and I0 (dotted grey = suspected glitches from QC, red = removed ranges; zoom with the box tool).
A glitch spans 1–3 points, is far narrower than an EXAFS oscillation, often appears at the same energy in several samples, and coincides with a dip in I0.
Enter **Ranges to remove** (calibrated energy, e.g. `9984.5-9990; 10321-10327.5`) and a **Reason** (required), then **Save and reload**: the ranges are stored under `deglitch` in `xafsmith.json`, raw files are untouched, and command-line processing uses them too.
**Clear deglitch for selected** undoes it. Never remove real structure.

**Energy calibration**: the reference calibrations, the status of loaded spectra (with the time gap to their reference), **Change reference / calibrate**, and “Determine / redetermine a reference ΔE” (change the tabulated energy or derivative smoothing).

**Normalization**: the shared normalization parameters at the top (changes recompute immediately) and four tabs: μ(E) with pre/post-edge lines, normalized overlay (flattened, E − E0 axis), derivative, merge scans (scans deviating from the median are rejected automatically; manual rejection possible). **Export** at the bottom: normalized data (`output/gui/norm/`) and the **Athena .prj** (section 13).

**χ(k) & FT**: rbkg, k range, window and k-weights (changes recompute immediately); tabs χ(k) (with window), |χ(R)| / Re (R not phase-corrected), background μ0(E), and **k-range check** (interfering edges → usable k limit, ΔR resolution and N_idp). χ(k) and χ(R) can be exported.

**Wavelet transform**:
1. Choose spectrum, mother wavelet (Morlet / Cauchy), k-weight, η, σ and display Rmax. The page shows the current resolution (blur along k and R at given R).
2. **Maxima in R windows**: enter R windows (e.g. `1.0-2.0; 2.0-3.6`); the table gives the k and R of the |W| maximum in each window, marked with a white “+” on the map. Compare the k of the same window across samples to judge light vs heavy scatterers in that shell.
3. **Export data and figure** writes to `output/gui/wavelet/`:
   - the |W| matrix `.csv` (first row k, first column R);
   - the maxima table `_maxima.csv`;
   - 600 dpi `.png` and `.svg`;
   - the parameters `.params.json`.
4. **How the parameters change the map, and what it is good for** (bottom of the page):
   - in this software's Morlet definition the map depends only on ησ: the blur is about ησ/(2R) along k and R/(ησ) along R, one trading against the other;
   - higher k-weights move maxima to higher k and emphasize heavy scatterers;
   - good for telling M–M from M–O second shells and single atoms from clusters; not for coordination numbers or distances.

## 7. FEFF paths

1. Structure source: **structures/ folder** (**Add structure files…** copies CIF / POSCAR in) or **Built-in**; **Export built-ins as CIF** writes them to `structures/builtin/`.
2. Choose absorber (defaults to the heaviest element), edge, inequivalent site, RMAX and NLEG.
3. **FEFF version**:
   - **FEFF6L** (default): non-self-consistent, seconds.
   - **FEFF8L**: self-consistent (SCF), 1–3 minutes. Set the **SCF radius** (usually 4–5 Å, 2–3 shells) and **exchange** (default 0 = Hedin-Lundqvist). The output folder gets `_feff8` and never overwrites FEFF6 results.
   - Path numbering is usually the same, so swapping the folder in a model compares them; but **the ΔE0 origin differs** (Ta L3 of KTaO3: about 6.6 eV with FEFF6, 1.2 eV with FEFF8) — re-determine e0 for models that fix it.
4. Click **Run FEFF**. **Existing calculations** lists all paths (distance, degeneracy, amplitude ratio); FEFF8 runs also show SCF radius, exchange and Fermi level; feff.inp can be expanded.

## 8. EXAFS fitting

At the top, **Before you fit, and what counts as a good fit** (expanded before the first fit): what to do before fitting, and what makes R-factor, residual/noise, parameter ranges, errors, bounds, correlations and robustness acceptable.

1. **Data and FEFF**: choose the sample (loaded, with χ(k)) and FEFF folders (several allowed: phases / sites).
2. **Fit range**: kmin, kmax, dk, window, k-weights (1, 2, 3 together recommended), Rmin, Rmax, fit space. N_idp and the variable limit are shown.
3. **Paths**: tick the paths to use. In `N` a number fixes the coordination number and a name (e.g. `n1`) lets it vary; in `deltar` and `sigma2` the same name means a shared parameter; all accept expressions (e.g. `ss1*1.5`).
4. **Parameters**: ticked `vary` = free, unticked = fixed at `value`; a non-empty `expr` = constrained. The variable count is shown live and turns orange above N_idp/2.
5. Enter a model name and click **Fit**. The result card shows R-factor, χ²_ν, N_idp, variables, parameters with errors, N, R, σ², ΔE0 per path, and k-space and R-space plots (|χ(R)| and Re χ(R); the fit window in grey).
6. When satisfied, **Save result**: the model goes to `models/` and the result into the summary and SI.

**Fit quality check** (automatic, below the result card) ticks or flags:
- R-factor (< 0.02 very good, 0.02–0.05 acceptable for a first shell);
- variables ≤ N_idp/2; residual / noise (≤ about 2 means the data limit);
- whether each variable has an error and whether it exceeds the value; parameters sitting on a bound;
- |ΔE0| ≤ 10 eV; positive and not excessive σ²; |ΔR| ≤ 0.2 Å;
- correlations with |r| > 0.9; a single k-weight; whether the robustness check has been run.

These are necessary conditions: an added shell must also pass the F-test (Fit history) and stay stable in the robustness check.

**Fit diagnosis**: expand **Fit diagnosis: where is the residual and why**. It shows:
- the residual in the window, a white-noise estimate and their ratio (≈ 1–2 is the data limit; ≫ 2 is systematic);
- the k-space residual (purple dotted lines mark detected spikes, mostly residual glitches);
- k-segment and R-segment mismatch tables, and suggestions based on where the residual sits.

See Help → Improving fit quality for the full method.

**Robustness check**: expand **Robustness check: refit under varied conditions** → **Run robustness check**. kmin ±0.5, kmax ±1, Rmax ±0.2 Å and k¹/k²/k³ alone are fitted in turn; each variable's spread is listed and marked **unstable** if it exceeds its statistical error.

**One model for a series** (time, potential): expand **Run a saved model** at the top, choose the model and several samples, click **Run**: the model is applied to each sample (renamed accordingly) and the results go to **Fit history**. Validate the model on a standard of known structure first.

**S0² from a standard**: let S0² vary on a standard of known structure and enter the result under “Calibrate & process → Processing parameters → S0²”. For samples, untick vary for S0² and set its value.

## 9. Compare models (Fit history)

All fits of the session are listed; **Save all to output/fits/** saves them at once.
**F-test (Hamilton)**: choose a simpler and a more complex model (with an extra shell or parameters) and click **Compare**: only **p < 0.05** makes the extra shell significant.
**View fit** switches to any fit and shows the same result card, quality check, diagnosis and robustness check as the EXAFS fitting page.

## 10. Linear combination fitting (LCF)

Choose the sample and end-member standards (must be measured), space (normalized μ / derivative / χ(k)), range and constraints (Σw = 1, 0 ≤ w ≤ 1, energy shift), then **LCF**. Single-standard fits and (with 3+ standards) all combinations are compared. Results are appended to `output/lcf/lcf_results.csv`. If an end-member is not measured, state the assumption in **Note**.

## 11. XANES quantification

Load samples and standards first.
- **Edge & white line**: E0 (derivative max), E_half (normalized μ = 0.5), white-line position, height and area (above 1 from E0 to E0 + 30 eV, adjustable). **Save** writes `output/xanes/xanes_features.csv`.
- **Valence calibration**: choose **measured standards of known valence**, enter the valences, choose the edge definition (E_half recommended); the fit “edge position = slope × valence + intercept” then estimates sample valences with errors. Only valid for standards with the same ligands and similar structures; results outside the standards' range are marked “extrapolated”.
- **Pre-edge fitting**: spectrum, range (relative to E0), number of peaks, edge baseline (erf / arctan), **Fit pre-edge**. Check the components for a sensible baseline; peaks at the range bounds or with ≈ 0 area are flagged.

## 12. Journal figures

Choose figure type (normalized XANES, XANES derivative, kⁿχ(k), |χ(R)|, fit), spectra, offset, size (single 85 mm / 1.5 column / double 178 mm / slide 16:9) and formats (TIFF, PNG, SVG, PDF); the preview is shown at actual size. **Save to output/figs/journal/**. Arial, colour-blind-safe palette, 600 dpi TIFF / PNG; the `.txt` with the same name is an English caption with processing parameters.

## 13. Export to Athena (bottom of Normalization)

Under **Export**, enter a file name and click **Export .prj** (`output/gui/athena/`). The .prj holds calibrated energy and μ(E) with this software's E0, normalization ranges, rbkg, k range and window, so Athena reproduces the processing for a direct comparison.

## 14. Summary report and methods paragraph

Click **Build summary** (if the session has unsaved fits, **Save this session's fits first**):
- **汇总.xlsx**: samples, calibration, QC, processing results, fit overview (one row per model), parameters per path, LCF, processing parameters;
- **汇总报告.html**: the tables plus all figures (**Open report in browser**; “Print → Save as PDF” works).

**Open summary folder** or **Save 汇总.xlsx as…**; **Preview** shows each table.

**Methods paragraph** at the bottom: fill in light source, beamline, monochromator and detection (**Save facility info**), optionally limit to some samples, then **Generate**: a Chinese and an English paragraph (each with **Copy**), also saved as `output/reports/方法段落.md`. It states only facts recorded in the project; missing facility details stay as [placeholders]. **It is a draft — check every sentence before submission.**

## 15. SI fitting text (SI methods)

1. Fit under EXAFS fitting and click **Save result** (only saved fits appear here).
2. Choose the fits for the Supporting Information (several allowed; a model applied to several samples is described once) and pick English or 中文.
3. **Methods** tab: **Copy** and paste into the SI. The text states only recorded facts: data and edge, FEFF version and structure, k / R ranges, k-weights, window, independent points and variables, S0² and its source, ΔE0, path constraints and how uncertainties were estimated.
4. **Table S[n]** tab: N, R, σ², ΔE0 per path (uncertainty in the last digits in parentheses), R-factor, χ²_ν and N_idp / variables. **Copy (paste into Excel / Word)** pastes as a table in Excel; in Word use “Convert Text to Table”. **Save .md / .csv** are available.
5. Adjust the table number “S[n]” and structure sources to your paper.

## 16. Sample design

From formula, element and edge, pellet area, diluent and target total μt, the page recommends the sample mass (total μt above the edge and edge step Δμt); with a given mass it computes the actual μt. **Interfering edges** lists other edges within the scan for all elements of the system. Data from xraydb (Elam).

## 17. AI assistant

An XAFSmith project can be handed to an AI assistant (Claude Code, Codex, Cursor, …) for processing, fitting and export.

1. **AI assistant** page → **Write / update AI instruction files**. This writes `AGENTS.md` (full path of the xafsmith command on this computer, workflow, commands, rules) and `CLAUDE.md` into the project folder. Your own text in these files is kept.
2. Open the AI assistant in the project folder (the page shows how for each tool) and say what you want in your own words (copyable examples are on the page).
3. The AI's results stay in the project: models in `models/` (rerun at the top of EXAFS fitting with quality check and diagnosis), numbers in `output/`, notes in `notes/`, figures in `output/figs/journal/`, reports in `output/reports/`.

After updating XAFSmith (the command path may change), click “Write / update” again.

## 18. Help, English interface and updates

- **Help** page: software information and disclaimer, updates, and four documents: **XAFS basics** (from absorption to fitting, with figures and formulas), this guide, the Beginner fitting tutorial and Improving fit quality.
- Choose **English** with **中文 / English** at the bottom of the sidebar; the whole interface and the documents switch; the choice is remembered.
- **Updates**: tick “Check for updates at start-up” (contacts github.com only, sends nothing) or click **Check now**. When a new version is available the sidebar says so; **Update now** downloads and installs it — then close and reopen the window.

---

## Reminders

- R-space peaks are **not phase-corrected** and appear ~0.3–0.5 Å shorter than bond lengths; take distances from fits.
- Variables ≤ N_idp/2; |ΔE0| > 10 eV, σ² ≤ 0 or parameters at a bound are flagged by the fit quality check — revisit the model.
- An added shell needs an F-test; a shell with p ≥ 0.05 is not “observed”.
- Fluorescence and transmission white lines / amplitudes cannot be compared directly (self-absorption, thickness).
- Keep **measured** (visible in the data) / **fitted** (model-dependent) / **inferred** (needs other experiments) apart.

## Troubleshooting

| Symptom | What to do |
|---|---|
| Double-clicking the icon opens no window | Double-click `installer.py` again to repair the installation (projects and data are not affected) |
| “Not installed yet” | Double-click `installer.py` again |
| ref_file is empty in the table | The batch has no reference: add the foil measured in that beamtime and scan again |
| A spectrum has glitches | “Deglitch” at the bottom of Quality check, or set use = 0 for that scan (with a reason) |
| A red error box appears on a page | Send its text to the maintainers; other pages keep working |
| Start over | Delete the project's `output` folder and run ① ② ③ under “Calibrate & process” again; raw data are never changed |
