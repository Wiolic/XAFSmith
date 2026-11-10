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
  - at the top the name and credit (Developed by Eggy & Claude Opus 5.5), then the **Open / new project** button;
  - the pages, grouped by workflow (gaps between groups):
    1. **Register data, Calibrate & process** — preparation;
    2. **Load & check** (one page, three tabs: Load spectra, Quality check, Energy calibration), **Normalization, χ(k) & FT, Wavelet transform** — look at the data;
    3. **FEFF paths, EXAFS fitting, Fit history, LCF, XANES quantification** — analysis;
    4. **Report export, Figure export, Methods export** — export;
    5. **Sample preparation, Edge lookup, AI assistant, Help** — tools and help.
  - at the bottom the current project (hover for the full path) and **中文 / English** (remembered). An update notice appears above the project when a new version exists.
- **Workflow & project** at the top right (a blue rounded button, always in the same place): hover over it (or click) for a small pop-up below it:
  - the six-step **Workflow** (register data, calibrate & process, inspect spectra, FEFF paths, fit, export): finished steps are ticked, the next one has a blue frame, click any step to go there;
  - **This project**: project name, spectra loaded, fits, reference calibrations, and the buttons **Project folder**, **output** and **Save parameters**.
- The **window footer** always shows a one-line disclaimer; **Disclaimer & citation** opens the “About & disclaimer” page of the help window (full text, citation, copy button).
- **Help** opens in its own window, which you can place next to the main window and read while you work (section 19).
- Some pages have an explanation button at the top right (e.g. **Before you fit · what is a good fit** on EXAFS fitting, **Parameters · what it is good for** on Wavelet transform); it opens a separate window that does not block the page.
- **Plots**: the four buttons at the top right are pan, zoom to rectangle, reset and save image; the cursor coordinates are shown at the top left.
- **Tables**: double-click a cell to edit (the path and parameter tables of EXAFS fitting edit with a single click); click check boxes directly; some columns offer a drop-down. Numbers accept any number of decimals.
- **Multi-select boxes**: open them to search and tick; “All / None” for bulk changes.
- **Long calculations** (processing all samples, FEFF, fitting, robustness, report) run in the background; the window stays responsive, a thin progress bar appears at the top and the progress at the bottom left.
- Light / dark follows the Windows setting.

## 3. Create a project (once per study)

A “project” is a folder in which raw data, structures and all results are kept in a fixed layout.

1. Click **Open / new project** at the top left; under “Open or create a project” click **Browse…**, choose an empty folder and click **Create project**.
2. To reopen it later, **double-click** it under “Recent projects”, or double-click **打开图形界面.bat** in the project folder.

The project folder contains `data/raw` (raw data), `structures`, `models` (fit models), `notes` and `output` (all results).

Opening a project takes you to **Register data**. Workflow progress and project information are in the **Workflow & project** pop-up at the top right (section 2).

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

**Load & check** in the sidebar is one page with three tabs: **Load spectra**, **Quality check** and **Energy calibration** (switch tabs without going back to the sidebar). Normalization, χ(k) & FT and Wavelet transform follow as separate pages.

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
1. Choose **Spectrum (left)**; to compare, also choose **Compare with (right)**: the two maps appear side by side, square, with identical parameters (mother wavelet Morlet / Cauchy, k-weight, η, σ, display Rmax). Tick **Shared colour scale** to compare absolute |W|; otherwise each map runs from 0 to its own maximum. The page shows the current resolution (blur along k and R at a given R).
2. **Maxima in R windows**: enter R windows (e.g. `1.0-2.0; 2.0-3.6`); the table lists, per sample, the k and R of the |W| maximum in each window, marked with a white “+” on the maps. Compare the k of the same window between the two spectra to judge light vs heavy scatterers in that shell.
3. **Export data and figure** writes, for each spectrum shown, to `output/gui/wavelet/`:
   - the |W| matrix `.csv` (first row k, first column R);
   - the maxima table `_maxima.csv`;
   - 600 dpi `.png` and `.svg`;
   - the parameters `.params.json`.
4. **Parameters · what it is good for** (top right, separate window):
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

The page has two columns, so you can change parameters, fit and read the result without scrolling up and down:
- the **left column** holds ① Data and FEFF, ② Fit range, ③ Paths, ④ Parameters (it scrolls on its own); **Model name** and **Fit** stay pinned at its bottom; **Ctrl+Enter** also fits.
- the **right column** always shows the latest fit: R-factor and other numbers, k- and R-space plots, then the tabs **Parameters, Paths, Quality, Diagnosis, Robustness, Full report**.
- drag the divider between the columns to resize them.
- **Before you fit · what is a good fit** (top right) opens a separate window: what to do before fitting, and what makes R-factor, residual/noise, parameter ranges, errors, bounds, correlations and robustness acceptable.

1. **Data and FEFF**: choose the sample (loaded, with χ(k)) and FEFF folders (several allowed: phases / sites).
2. **Fit range**: kmin, kmax, dk, window, k-weights (1, 2, 3 together recommended), Rmin, Rmax, fit space. N_idp and the variable limit are shown.
3. **Paths**: tick the paths to use (a single click edits a cell). In `N` a number fixes the coordination number and a name (e.g. `n1`) lets it vary; in `deltar` and `sigma2` the same name means a shared parameter; all accept expressions (e.g. `ss1*1.5`).
4. **Parameters**: ticked `vary` = free, unticked = fixed at `value`; a non-empty `expr` = constrained. `value` takes any number of decimals (e.g. 0.00412 for σ²). The variable count is shown live and turns orange above N_idp/2.
5. Enter a model name and click **Fit** (or Ctrl+Enter). The right column shows R-factor, χ²_ν, N_idp, variables and the k- and R-space plots (|χ(R)| and Re χ(R); the fit window in grey); parameters with errors and N, R, σ², ΔE0 per path are in the **Parameters** and **Paths** tabs. Only the right column changes: the left column keeps its settings and scroll position.
6. **Use fitted values as start** (above the result) copies the fitted values into the `value` column of the parameter table as start values for the next fit (fixed and constrained parameters are left alone).
7. When satisfied, **Save result**: the model goes to `models/` and the result into the report and methods export.

**Quality** (tab on the right, automatic; the tab shows how many ⚠ there are) ticks or flags:
- R-factor (< 0.02 very good, 0.02–0.05 acceptable for a first shell);
- variables ≤ N_idp/2; residual / noise (≤ about 2 means the data limit);
- whether each variable has an error and whether it exceeds the value; parameters sitting on a bound;
- |ΔE0| ≤ 10 eV; positive and not excessive σ²; |ΔR| ≤ 0.2 Å;
- correlations with |r| > 0.9; a single k-weight; whether the robustness check has been run.

These are necessary conditions: an added shell must also pass the F-test (Fit history) and stay stable in the robustness check.

**Diagnosis** (tab on the right): where the residual is and why. It shows:
- the residual in the window, a white-noise estimate and their ratio (≈ 1–2 is the data limit; ≫ 2 is systematic);
- the k-space residual (purple dotted lines mark detected spikes, mostly residual glitches);
- k-segment and R-segment mismatch tables, and suggestions based on where the residual sits.

See Help → Improving fit quality for the full method.

**Robustness** (tab on the right) → **Run robustness check**. kmin ±0.5, kmax ±1, Rmax ±0.2 Å and k¹/k²/k³ alone are fitted in turn; each variable's spread is listed and marked **unstable** if it exceeds its statistical error.

**One model for a series** (time, potential): expand **Run a saved model** at the top of the left column, choose the model and several samples, click **Run**: the model is applied to each sample (renamed accordingly) and the results go to **Fit history**. Validate the model on a standard of known structure first.

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

## 12. Figure export

1. Choose the figure type (normalized XANES, XANES derivative, kⁿχ(k), |χ(R)|, fit), the spectra (plot order), offset and range.
2. **Palette**: 24 palettes (named as in PeakForge, six families — Waters, Forests, Earth, Skies, Stone, Fields — each marked monochrome, contrast, soft or colour-blind safe). Monochrome ramps suit one series of samples (oxidation state, time, potential) and are sampled evenly along the ramp. The default **Waters · Glacier** draws samples in blue and standards in grey (as in the author's Origin project).
3. **References / standards**: the spectra selected here are drawn in grey with slightly thinner lines (default: names containing foil / powder / metal). Clear it to treat all as samples.
4. Size (single column 85 mm / 1.5 column / double column 178 mm / slide 16:9), formats (TIFF, PNG, SVG, PDF), file name. The preview is at true size; below it is the English caption (saved with the figure as .txt, including processing parameters).
5. **Save to output/figs/journal/**: Arial, 600 dpi TIFF/PNG.
6. **Export Origin project (.opju)**: every curve becomes an X/Y column pair (column names = legend) and is plotted in one format — 25 × 19 cm layer, Arial 32 pt (axis titles, tick labels, legend), 2 pt axes, boxed frame (no ticks on the top and right), inward ticks, 3.5 pt data lines (3 pt for standards), frameless legend, anti-aliasing on; XANES uses the energy E (eV) on the x axis and hides the y ticks when offset; formula subscripts use Origin syntax (IrO\-(2)).
   - With Origin (2021 or later) installed, `output/figs/journal/origin/<name>/<name>.opju` is built directly in about 10–30 s (the window pauses meanwhile);
   - without Origin only the data (.csv), `spec.json` and `build_origin.py` are written: on a computer with Origin, run `run -pyf "<that folder>/build_origin.py"` in Origin's script window to get the same project (see README_Origin.txt in the folder).

## 13. Export to Athena (bottom of Normalization)

Under **Export**, enter a file name and click **Export .prj** (`output/gui/athena/`). The .prj holds calibrated energy and μ(E) with this software's E0, normalization ranges, rbkg, k range and window, so Athena reproduces the processing for a direct comparison.

## 14. Report export

Click **Build report** (with unsaved fits, **Save all open fits first**) to get `output/reports/汇总_<time>/`:
- **汇总.xlsx**: samples, calibration, quality check, processing results, fit overview (one row per model), EXAFS path parameters, LCF, processing parameters;
- **汇总报告.html**: the same tables plus every figure, grouped (spectra / fits / LCF) as a grid of thumbnails; **click a thumbnail to enlarge it**, scroll to zoom, drag to pan, double-click to reset, Esc or a click outside to close. Print → Save as PDF from the browser if needed.

**Open report folder**, **Save 汇总.xlsx as…**, **Open report in browser**. **Preview** shows each table.

## 15. Methods export

**Methods paragraph**: fill in the light source, beamline, monochromator, detection etc. (**Save facility info**), optionally limit to some samples, and click **Generate**: a Chinese and an English paragraph (each with **Copy**), also saved as `output/reports/方法段落.md`. Only facts recorded in the project are stated (references and ΔE, normalization / background / FT parameters, fit ranges, N_idp, S0² source, versions); missing facility fields stay as [placeholders]. **It is a draft: check every sentence before submission.**

**Fit-parameter table (Supporting Information, Table S[n])**:
1. Fit under EXAFS fitting and click **Save result** (only saved fits appear here).
2. Choose the fits (several allowed). The table gives N, R, σ², ΔE0 per path (error in the last digit in brackets), R-factor, χ²_ν and N_idp / variables.
3. **Copy table**: pastes as a table in Excel; in Word use “Convert Text to Table”. Or **Save .csv**, or **Save .md (with fit text)**, which adds the fitting description in English and Chinese (FEFF version and structure, k / R ranges, k-weights, window, independent points and variables, S0² source, constraints per path, error estimate).
4. Adjust the “Table S[n]” numbering and structure sources to your paper.

## 16. Sample preparation

- **Sample** (shared by both tools): enter the **formula** (e.g. IrO2, Ta2O5; non-integer as IrCo0.2O2); the **absorber** is read from the formula (default: the heaviest element); choose the **edge**. The page lists the elements and the edge energy.
- **Pellet calculator**: pellet area, diluent and its mass, target total μt → recommended sample mass (total μt above the edge, edge step Δμt); with a sample mass entered, the actual μt is computed.
- **Interfering-edge screening**: the elements screened are those of the formula + the diluent + “Other elements present” (optional, e.g. K or Cl impurities). Other edges inside the scan are listed with their k; keep kmax below the first one.

Data: xraydb (Elam tables).

## 17. Edge lookup

Like Hephaestus' periodic table: click an element to see
- **Absorption edges**: energy, fluorescence yield and jump ratio of each edge;
- **Fluorescence lines**: Siegbahn name, energy, relative intensity (normalised within one initial level), transition;
- **Fluorescence filter**: choose the edge measured and the filter thickness (absorption lengths μx, default 3); the elements whose edge lies between the main fluorescence line and the absorber edge are listed with thickness (μm) and the transmission of the main line, sorted by transmission (the first row is usually the Z−1 element, e.g. Fe K → Mn).

## 18. AI assistant

An XAFSmith project can be handed to an AI assistant (Claude Code, Codex, Cursor, …) for processing, fitting and export.

1. **AI assistant** page → **Write / update AI instruction files**. This writes `AGENTS.md` (full path of the xafsmith command on this computer, workflow, commands, rules) and `CLAUDE.md` into the project folder. Your own text in these files is kept.
2. Open the AI assistant in the project folder (the page shows how for each tool) and say what you want in your own words (copyable examples are on the page).
3. The AI's results stay in the project: models in `models/` (rerun at the top of EXAFS fitting with quality check and diagnosis), numbers in `output/`, notes in `notes/`, figures in `output/figs/journal/`, reports in `output/reports/`.

After updating XAFSmith (the command path may change), click “Write / update” again.

## 19. Help, English interface and updates

- **Help** in the sidebar opens a **separate window** (the main window stays on its page), so you can keep it next to the main window while you work. On its left: **GUI guide** (this document), **Beginner fitting tutorial**, **Improving fit quality**, **XAFS basics** (from absorption to fitting, with formulas, examples and figures); at the bottom a separate page **About & disclaimer**: version and credit, the full disclaimer, the citation (**Copy citation**) and the update check.
- **中文 / English** at the bottom of the sidebar switches the interface and documents; the choice is remembered.
- **Updates** (About & disclaimer page): tick “Check for updates at start-up” (contacts github.com only, sends nothing) or click **Check now**. When a new version exists the sidebar shows it; **Update now** downloads and installs it — close and reopen the window afterwards.

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
