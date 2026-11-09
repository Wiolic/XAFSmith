# XAFSmith GUI guide (mouse only)

> ⚠️ **Disclaimer**: XAFSmith is provided "as is", without warranty of any kind. The authors accept no responsibility for results obtained with it. Please validate your results; **we recommend cross-checking key results against Athena / Artemis**.
> 📖 **Citation**: if you use XAFSmith in a publication, please cite Eggy & Claude, XAFSmith, https://github.com/Wiolic/XAFSmith, together with Larch and FEFF (copy the formatted references from “How to cite” on the ⓪ Project page).

This guide is for users who do not program or type commands. With a working knowledge of XAFS you can complete the whole workflow by clicking:
**register data → calibrate → process → FEFF → EXAFS fitting → LCF / XANES → summary report**.
If this is your first EXAFS fit, read the **Beginner fitting tutorial** next to this guide first.

---

## 1. Installation (once)

1. Install Python 3.11 or 3.12 from https://www.python.org/downloads/windows/ and **tick “Add python.exe to PATH”** during installation.
2. On https://github.com/Wiolic/XAFSmith click **Code → Download ZIP** and unzip it anywhere.
3. Double-click **`安装XAFSmith.bat`** (“Install XAFSmith”) in the unzipped folder. The installer wizard asks for:
   - **Install location** (default `C:\Users\<you>\AppData\Local\Programs\XAFSmith`; “浏览…” = Browse);
   - desktop shortcut, Start-menu shortcut (with uninstaller), launch after installation;
   - tick **“I have read and agree”** and click **安装 (Install)**. Internet is required; it takes 5–15 minutes.
4. The unzipped folder can be deleted afterwards.

To use XAFSmith: **double-click XAFSmith on the desktop (or in the Start menu)**. It opens in its own window (no web browser). Close the window to quit.
Uninstall: Start menu → XAFSmith → uninstall (your projects and data are not touched).

At the top of the sidebar, **Language / 语言** switches between 中文 and English; the choice is remembered.

---

## 2. Create a project (once per study)

A project is a folder with a fixed layout for raw data, structures and all results.

1. Click **⓪ Project** → expand “Open / create project”.
2. Click **📁 Browse…**, choose an empty folder and click **Create project**.
3. To reopen it later, pick it in “Recent projects” and click **Open**, or double-click **打开图形界面.bat** in the project folder.

The project contains `data/raw` (raw data), `structures`, `models` (fit models), `notes` and `output` (all results).

## 3. Add and register raw data (⓪ Project → 1 Register data)

1. Use one “batch” per beamtime: enter a batch folder name (e.g. `2026-11-05_Ta`), drag the raw files into the upload box and click **Upload**.
   **Every batch must contain the elemental reference measured in that session** (metal foil or powder; file name containing foil / powder / metal).
   You can also copy files into `data\raw\<batch>\` with Windows Explorer.
2. Click **Scan data/raw and register new files**. A table with one row per raw file appears.
3. Edit the table and click **Save meta.csv**:
   - **sample**: rows with the same name are scans of the same sample and are merged;
   - **role**: `reference` for foils, `standard` for standards, `sample` for samples;
   - **use**: `0` to exclude a scan (give the reason in **note**);
   - **ref_file**: the reference used for calibration (default: the reference of the same batch). Spectra without one cannot be processed.
4. Click **2 Check → Run check** and fix the reported errors until there are none.

## 4. Processing parameters (⓪ Project → 4 Processing parameters)

One parameter set per absorption edge, shared by all samples of that edge:
- **All elements in the sample** (for the interfering-edge check, e.g. `Ta, Ir, O, K`);
- normalization (pre1, pre2, norm1, norm2, nnorm), background (rbkg) and Fourier transform (kmin, kmax, window, k-weight);
- **S0²**: leave empty until it has been fitted on a standard (section 7).

Click **Save parameters**.

## 5. One-click processing (⓪ Project → 3 One-click processing)

Click in order:
1. **① Quality check**: glitches (glitch_E), I0 drops, edge step, k_snr3 (usable k range), fluorescence self-absorption risk.
2. **② Calibrate with references**: one ΔE per reference; all spectra of that batch get the same ΔE.
3. **③ Process all samples**: calibrate → normalize → merge → χ(k) → FT. Results go to `output/processed` and `output/figs`.

To view spectra: **① Import data** → select samples → **Load samples** (references are loaded with them), then use **④ Normalization**, **⑤ χ(k) & FT** and **⑥ Wavelet transform**.

## 6. FEFF paths (⑦ FEFF paths)

1. Structure source: **structures/ folder** (upload CIFs in ⓪ Project → 5 Structure files) or **Built-in structure**.
2. Choose absorber, edge, inequivalent site and RMAX, then click **Run FEFF6L**.
3. “Existing FEFF calculations” lists all paths (distance, degeneracy, amplitude ratio).

## 7. EXAFS fitting (⑧ EXAFS fitting)

1. **Data**: the sample (load it in ① first); **FEFF folders**: the matching structure.
2. **Fit range**: kmin, kmax, k-weights (1, 2, 3 together recommended), Rmin, Rmax. N_idp and the variable limit are shown.
3. **Paths**: tick the paths to use. A number in `N` fixes the coordination number; a parameter name (e.g. `n1`) fits it. Paths with the same name in `deltar` / `sigma2` share that parameter.
4. **Parameters**: ticked `vary` = free, unticked = fixed at `value`; text in `expr` = constraint (e.g. `dr1`, `ss1*1.5`).
5. Click **Fit** and check the R-factor, reduced χ², parameters with errors, the |χ(R)| and Re χ(R) plots and any warnings.
6. Click **Save results**: the model goes to `models/` and the results enter the summary. Saved models can be rerun with one click at the top of the page.

**S0² from a standard**: fit S0² freely on a standard of known structure and enter the value in ⓪ Project → 4 Processing parameters → S0². In sample fits untick `vary` for S0² and set its value.

**Robustness check**: below the fit result, expand **Robustness check** → **Run robustness check**. The fit is repeated with kmin ±0.5, kmax ±1, Rmax ±0.2 Å and with k¹/k²/k³ alone; variables that change more than their statistical error are marked **unstable**. Report such parameters as a range, or revise the model.

## 8. Comparing models (⑨ Fit history / F-test)

Choose a simpler and a more complex model (with an extra shell or parameters) and click **Compare**: the extra shell is significant only if **p < 0.05**.
**Save all fits above to output/fits/** saves every fit of the session.

## 9. XANES linear combination fitting (⑩ LCF)

Choose the sample and measured standards as end members, the energy range and the space (normalized μ / derivative / χ(k)), then click **LCF**. Single-standard fits are shown for comparison.

## 10. XANES quantification (⑬ XANES quantification)

Load samples and standards in ① first.
- **Edge position & white line**: E0 (derivative maximum), E_half (normalized μ = 0.5), white-line position and height, white-line area (above 1 between E0 and E0+30 eV; adjustable). **Save** writes `output/xanes/xanes_features.csv`.
- **Valence calibration**: select **measured standards of known valence**, enter their valences, choose the edge-position definition (E_half recommended). The line “edge position = slope × valence + intercept” is fitted and the valence of selected samples is estimated with an error. Valid only for standards with the same ligands and similar structures; values outside the standards' range are marked “extrapolated”.
- **Pre-edge peak fitting**: choose the spectrum, range (relative to E0), number of peaks and edge baseline (erf / arctan), then click **Fit pre-edge peaks**. Check the components; warnings appear for peaks at the range limits or with ≈0 area.

## 11. Journal figures (⑭ Journal figures)

Choose the figure type (normalized XANES, XANES derivative, k^n χ(k), |χ(R)|, fit), size (single column 85 mm / 1.5 column / double column 178 mm / slide 16:9), formats (TIFF, PNG, SVG, PDF) and spectra, then click **Save to output/figs/journal/**.
Figures use Arial and colour-blind-safe colours; TIFF/PNG are 600 dpi; the .txt file of the same name is an English caption with processing parameters.

## 12. Export to Athena (bottom of page ④)

Expand **Export as Athena project (.prj)**, select spectra and click **Export .prj** (saved in `output/gui/athena/`, also downloadable). The file contains the calibrated energy and μ(E) plus the E0, normalization ranges, rbkg, k range and window used in XAFSmith, so Athena reproduces the same processing for a direct comparison.

## 13. Summary report and Methods paragraph (⑫ Summary report)

**Generate summary** creates:
- **summary .xlsx**: samples, calibration, quality check, processing results, fit overview (one row per model), per-path EXAFS parameters, LCF, processing parameters;
- **report .html**: the tables and all figures (open in a browser; “Print → Save as PDF” works).

Under **Generate a “Methods” paragraph**, fill in facility, beamline, monochromator and detection (**Save instrument information**), optionally restrict to some samples and click **Generate methods paragraph**. Chinese and English paragraphs are produced and saved as `output/reports/方法段落.md`. Only facts recorded in the project are used; missing instrument details appear as [placeholders]. **It is a draft: check every sentence.**

## 14. Updates

On the ❓ Help page, **Check for updates** lets you enable the start-up check (contacts github.com only) or **Check now**. When a new version exists the sidebar shows it; **Update to latest version** downloads and installs it — then close and reopen the window.

---

## Interpretation reminders

- R-space peaks are **not phase-corrected** and appear ~0.3–0.5 Å shorter than the bond lengths; take distances from the fit.
- Keep variables ≤ N_idp/2. Warnings appear for |ΔE0| > 10 eV, σ² < 0 and S0² outside 0.6–1.1.
- Test added shells with the F-test; a shell with p ≥ 0.05 cannot be reported as “observed”.
- Fluorescence and transmission white lines / amplitudes are not directly comparable (self-absorption, thickness).
- Separate **measured** (visible in the data), **fitted** (model-dependent) and **speculative** (needs other experiments) statements.

## Troubleshooting

| Problem | Solution |
|---|---|
| The window keeps showing “Starting…” | The first start takes 10–30 s; after 2 minutes check `C:\Users\<you>\.xafsmith\app.log` |
| “Not installed” message | Run `安装XAFSmith.bat` again |
| The window does not open (old systems without WebView2) | Install the Microsoft Edge WebView2 Runtime (https://developer.microsoft.com/microsoft-edge/webview2/, Evergreen Bootstrapper) and try again |
| ref_file is empty in the table | The batch has no reference: add the foil measured in that session to the batch and scan again |
| A spectrum has a glitch | Set use = 0 for that scan (with a reason), or define a deglitch range in xafsmith.json |
| Start over | Delete the project's `output` folder and run one-click processing again; raw data are never changed |
