# XAFSmith GUI guide

This guide walks through every page of the XAFSmith window in the order you use them: **what it does, how to use it, what to look at**.

- New to XAFS: read **XAFS basics** first.
- First EXAFS fit: follow the **Fitting for beginners** once.
- Fit does not match, or you want a better one: read **Improving fit quality**.

Help opens in its own window; keep it next to the main window while you work.

**Contents**

| Part | Sections |
|---|---|
| 1. Getting started | 1 Install and start　2 The window　3 Create a project |
| 2. Prepare the data | 4 Register data　5 Calibrate & process |
| 3. Look at the data | 6 Load & check　7 Normalization　8 χ(k) & FT　9 Wavelet transform |
| 4. Analysis | 10 FEFF paths　11 EXAFS fitting　12 Fit history　13 LCF　14 XANES quantification |
| 5. Export | 15 Report export　16 Figure export　17 Methods export　18 Export to Athena |
| 6. Tools and help | 19 Sample preparation　20 Edge lookup　21 AI assistant　22 Help, language and updates |
| Appendix | A Where the results are　B Reminders　C Troubleshooting |

---

## 1. Getting started

### 1　Install and start

**Option 1 (recommended): installer** (Windows 10 / 11 64-bit; offline, no administrator rights)

1. Download `XAFSmith-<version>-Setup.exe` from https://github.com/Wiolic/XAFSmith/releases/latest, run it and follow the wizard.
   The installer is not code-signed: if “Windows protected your PC” appears, click **More info → Run anyway**.
2. `examples\demo_project` in the install folder is a demo project built from public data — **copy it to your own folder before opening it**.
3. Upgrade: run the new installer (it replaces the old version). Uninstall: Windows Settings → Apps → XAFSmith → Uninstall.
   Neither removes your projects or the settings and logs in `%USERPROFILE%\.xafsmith\`.

**Option 2: install from source (once, about 15 min, internet needed)**

1. Install Python 3.11 or 3.12 from https://www.python.org/downloads/windows/ and **tick “Add python.exe to PATH”** during installation.
2. Open https://github.com/Wiolic/XAFSmith, click the green **Code → Download ZIP** and unzip it anywhere.
3. Double-click **installer.py** in the unzipped folder. In the installer:
   - **Install location**: default `C:\Users\<you>\AppData\Local\Programs\XAFSmith`; “Browse…” to change it;
   - tick as needed: **desktop shortcut**, **Start-menu shortcut (with uninstaller)**, **start after installation**;
   - tick **I have read and agree**, click **Install** and wait for the progress bar.
4. The unzipped folder can be deleted afterwards.

> If double-clicking installer.py does nothing or opens Notepad: right-click → Open with → Python. If that fails, reinstall Python with “Add python.exe to PATH” and “py launcher” ticked.

**Start and uninstall (source install)**

- Start: double-click **XAFSmith** on the desktop or in the Start menu; the window opens in a few seconds. Closing the window quits.
- Uninstall: Start menu → XAFSmith → **Uninstall XAFSmith**. Only the software is removed, never your projects or data.

### 2　The window

**Sidebar (top to bottom)**

| Place | Content |
|---|---|
| Top | Name and credit (Developed by Eggy & Claude Opus 5.5) |
| Button | **Open / new project** |
| Navigation | Five groups following the workflow (below) |
| Bottom | Current project (hover for the full path), **中文 / English**; an update notice appears above the project when a new version exists |

The five groups:

| Group | Pages |
|---|---|
| Preparation | Register data, Calibrate & process |
| Look at the data | Load & check (three tabs: Load spectra, Quality check, Energy calibration), Normalization, χ(k) & FT, Wavelet transform |
| Analysis | FEFF paths, EXAFS fitting, Fit history, LCF, XANES quantification |
| Export | Report export, Figure export, Methods export |
| Tools and help | Sample preparation, Edge lookup, AI assistant, Help |

**Top right: Workflow & project**

A blue rounded button, always in the same place. Hover over it (or click) for a pop-up below it:

- **Workflow**: register data, calibrate & process, inspect spectra, FEFF paths, fit, export. Finished steps are ticked, the next one is framed in blue; click any step to go there.
- **This project**: project name, spectra loaded, fits, reference calibrations, and the buttons **Project folder**, **output** and **Save parameters**.

**Window footer**: a one-line disclaimer. **Disclaimer & citation** opens the “About & disclaimer” page of the help window.

**Common operations**

| Item | How to use it |
|---|---|
| Plots | Four buttons at the top right: pan, zoom to rectangle, reset, save image; cursor coordinates at the top left |
| Tables | Double-click a cell to edit (path and parameter tables of EXAFS fitting edit with a single click); click check boxes directly; numbers accept any number of decimals |
| Multi-select boxes | Open to search and tick; “All / None” for bulk changes |
| Explanation buttons | Some pages have one at the top right (e.g. “Before you fit · what is a good fit”); it opens a separate window that does not block the page |
| Long calculations | Processing, QC, calibration, FEFF, fitting, robustness, LCF and reports run in the background; a thin bar at the top (with a percentage when the progress is known) and the progress at the bottom left. Tasks with progress (batch processing, QC, calibration, running saved models, robustness) show a **Cancel** button: it stops **after the current step** (a single fit or FEFF run cannot be interrupted), and a cancelled task writes no result. With several tasks running only their count is shown |
| Appearance | One light theme only; it stays light even when Windows uses dark mode |

### 3　Create a project

A “project” is a folder holding raw data, structures and every result in a fixed layout. Use one per study.

**Create**

1. Click **Open / new project** at the top left.
2. Click **Browse…** and choose an empty folder (or make one).
3. Click **Create project**. Existing files are never overwritten.

**Reopen later**: start XAFSmith and **double-click** it under “Recent projects”, or use **Open / new project → Browse…** and pick the folder.

**What the project folder contains**

| Folder | Content |
|---|---|
| `data/raw/` | Raw data (read-only, one subfolder per batch) |
| `data/meta.csv` | Data register |
| `structures/` | Structure files (CIF, POSCAR) |
| `models/` | Fit models |
| `notes/` | Analysis notes |
| `output/` | All results |

Opening a project takes you to **Register data**.

---

## 2. Prepare the data

### 4　Register data

**What it does**: puts the raw data into the project and records in `data/meta.csv` what each file is. Every later step follows this table.

**Steps**

1. One **batch** per beamtime: enter a name under **Batch folder**, e.g. `2026-11-05_Ta`.
2. Click **Choose files, copy to batch and register…** and select all raw files of that beamtime:
   - files are copied to `data/raw/<batch>/`; the originals are not touched;
   - files with the same name are skipped (you are told which);
   - the copies are **registered automatically** in `data/meta.csv` below.
3. **Each batch must contain the elemental reference measured in the same beamtime** (foil or powder; file name containing foil / powder / metal).
4. Check and edit the register (double-click a cell), then **Save meta.csv**:

| Column | What to enter |
|---|---|
| sample | Sample name. Rows with the same name are scans of one sample and are merged; rename to keep them apart |
| role | `reference` for the foil, `standard` for standards of known structure, `sample` for samples |
| use | `0` for scans you do not want, with the reason in note |
| ref_file | Reference used for calibration (default: the reference of the same batch). Spectra without one cannot be processed |

5. At the bottom, **Validate against the data standard → Run check**; fix every “error” until there are none.

> Files copied into `data\raw\<batch>\` with Explorer are registered with **Scan data/raw and register new files**.

### 5　Calibrate & process

**What it does**: sets the processing parameters, then processes every sample at once.

**First: processing parameters** (choose the edge at the top right; one set per edge, shared by all its samples)

| Parameter | Meaning |
|---|---|
| All elements in the sample | Used to check interfering edges and the usable k range, e.g. `Ta, Ir, O, K` |
| Normalization | pre1, pre2, norm1, norm2, nnorm, E0 smoothing |
| Background and Fourier transform | rbkg, k-weight, kmin, kmax, dk, window |
| S0² | Value, error, source. Leave empty; fill in after fitting a standard (section 11) |

Click **Save parameters**.

**Second: batch run**, click in turn:

1. **① Quality check**: glitches (glitch_E), I0 drops, edge step, k_snr3 (k reached at a usable signal-to-noise), fluorescence self-absorption risk.
2. **② Calibrate with references**: one ΔE per reference, the same ΔE applied to every spectrum of that batch.
3. **③ Process all samples**: calibrate → normalize → merge → χ(k) → Fourier transform.

Results are in `output/processed/` and `output/figs/`.

---

## 3. Look at the data

### 6　Load & check

**Load & check** in the sidebar is one page with three tabs: **Load spectra**, **Quality check**, **Energy calibration**. Switch tabs without going back to the sidebar.

**Tab 1: Load spectra**

1. Tick samples, or choose **or a whole edge**.
2. Click **Load**. References are loaded too.
3. Loaded spectra are calibrated, normalized and merged, with χ(k) and FT computed.

The table below lists the loaded spectra and their calibration status. You can also:

- view **Raw μ(E) and channels** (I0 / I1 / If);
- **Remove from session (files kept)**;
- **Read files directly** (auto-detects BSRF / XDI / .xmu / XDAC / Athena .prj; you can also choose the format by hand, or pick “Column text (by number)” and fill in the column numbers below) for files not in meta.csv — a reference from the same batch is required. If any field was guessed (element, edge, energy unit …) or the column mapping raised a warning, a notice is shown — please check it.
- **Column mapping wizard** (button next to “Read”; choose one file first): use it when a file is not recognised or its column names are non-standard. It previews the columns and first rows; choose which column is energy, I0, It, If (several channels are summed) and μ (recognisable names are pre-selected); choose transmission or fluorescence, or let the software decide from the mapped columns; **Test read** shows the number of points, energy range, mode, edge and μ range — check them, then enter a template name and **Save as template**. The template is written to the project's `xafsmith.json` (`formats`), appears in the “Format” list and can be used in the `format` column of meta.csv. Columns are saved by name when the name is unique (still valid if the order changes), otherwise by number. The name must not equal a built-in format name.

**Tab 2: Quality check**

- **Check loaded spectra**: written to `output/qc/qc_report.csv`.
- **Deglitch**:
  1. choose samples (several allowed; the ranges apply to all selected);
  2. look at μ(E) and I0: grey dotted lines mark suspected glitches, red marks removed ranges; zoom with a rectangle;
  3. enter **Ranges to remove** (calibrated energy, e.g. `9984.5-9990; 10321-10327.5`) and a **Reason** (required);
  4. click **Save and reload**. The ranges go to `xafsmith.json`; raw files are untouched. **Clear deglitch for selected** undoes it.

> A glitch spans 1–3 points, is much narrower than the EXAFS oscillations, often appears at the same energy in several samples and coincides with a dip in I0. Never remove real structure.

**Tab 3: Energy calibration**

- **Reference calibrations**: ΔE of each reference;
- **Calibration status of loaded spectra**: reference used and time difference to it; **change reference / calibrate**;
- **Determine / redetermine a reference ΔE** (expand): change the table value or derivative smoothing and redetermine.

### 7　Normalization

- Top: the normalization parameters shared by the group; changes recompute after ~0.25 s (continuous nudging recomputes once). **Restore xafsmith.json values** on the card resets the parameters to the project configuration for that edge (background and FT cards have it too).
- Inputs are guarded: pre1 stays below pre2, kmin below kmax, Rmin below Rmax (change one and the other follows); a non-numeric E0 turns the box red and the derivative maximum is used.
- Four tabs:
  - **μ(E) with pre- / post-edge lines**: check that both lines are sensible;
  - **Normalized overlay**: optionally flattened, x axis E − E0;
  - **Derivative**;
  - **Merge scans**: scans that deviate from the median are rejected automatically; manual rejection possible.
- **Export** at the bottom: normalized data of the selected spectra (`output/gui/norm/`) and the Athena project .prj (section 18).

**What to look at**: the pre-edge line follows the pre-edge data, the post-edge line passes through the middle of the data; after normalization the post-edge region oscillates around 1. Use one parameter set for all samples of an edge.

### 8　χ(k) & FT

- Parameters: rbkg, k range, window, k-weight; changes recompute at once.
- Four tabs:
  - **χ(k)** (with the window);
  - **|χ(R)| / Re**: R axis not phase-corrected;
  - **Background μ0(E)**;
  - **k-range check**: usable kmax from interfering edges, ΔR resolution and N_idp.
- **Export χ(k) and χ(R) to output/gui/chi/**.

**What to look at**: k²χ(k) oscillates around 0 without an overall slope; look at k¹, k² and k³; choose the k range from the worst sample of the group and use it for all.

### 9　Wavelet transform

**What it does**: shows the signal in k and R together, to tell light scatterers (O etc., maxima at low k) from heavy ones (metals, maxima at high k).

**Steps**

1. Choose **Spectrum (left)**. To compare, also choose **Compare with (right)**: the two maps appear side by side, square, with identical parameters.
2. Choose mother wavelet (Morlet / Cauchy), k-weight, η, σ and display Rmax. The current resolution is shown.
3. Tick **Shared colour scale** to compare absolute |W|; otherwise each map runs from 0 to its own maximum.
4. **Maxima in R windows**: enter R windows (e.g. `1.0-2.0; 2.0-3.6`); the table lists, per sample, the k and R of the |W| maximum in each window, marked with a white “+”.
5. **Export data and figure** writes, for each spectrum shown, to `output/gui/wavelet/`: the |W| matrix `.csv` (first row k, first column R), the maxima `_maxima.csv`, 600 dpi `.png` and `.svg`, and `.params.json`.

**Choosing parameters** (the explanation button at the top right has the full text)

- In this software's Morlet definition the map depends only on ησ: the blur is about ησ/(2R) along k and R/(ησ) along R, one trading against the other.
- Higher k-weights move every maximum to higher k and emphasize heavy scatterers. Compare k positions only at the same k-weight.
- Good for telling M–M from M–O second shells and single atoms from clusters; it gives no coordination numbers or distances.

---

## 4. Analysis

### 10　FEFF paths

**What it does**: computes scattering paths (distance, degeneracy, amplitude and phase) from a crystal structure for fitting.

**Steps**

1. Structure source:
   - **structures/ folder**: **Add structure files…** copies CIF / POSCAR files in;
   - **Built-in**: choose directly; **Export built-ins as CIF** saves them to `structures/builtin/`.
2. Choose the **absorber** (default: the heaviest element, remembered per structure), **edge**, **inequivalent site**, **RMAX** and **NLEG**.
3. Choose the **FEFF version**:

| | FEFF6L (default) | FEFF8L |
|---|---|---|
| Potential | Non-self-consistent | Self-consistent (SCF) |
| Time | Seconds | About 1–3 min |
| Extra parameters | — | SCF radius (usually 4–5 Å, 2–3 shells), exchange (default 0 = Hedin-Lundqvist) |
| Output folder | `…/<structure>_<element><edge>/site0` | ends with `_feff8`; FEFF6 results are not overwritten |

4. Click **Run FEFF**.

**Results**: **Existing calculations** lists every path (distance, degeneracy, amplitude ratio); FEFF8L runs also show SCF radius, exchange and Fermi level; feff.inp can be expanded.

> FEFF6L and FEFF8L have different ΔE0 zeros (e.g. Ta L3 of KTaO₃: about 6.6 eV with FEFF6, 1.2 eV with FEFF8). After switching, re-determine e0 for models that fix it.

### 11　EXAFS fitting

**Layout**

| Area | Content |
|---|---|
| Left column (scrolls on its own) | ① Data and FEFF ② Fit range ③ Paths ④ Parameters; “Run a saved model” at the top |
| Bottom of the left column (pinned) | **Model name** and **Fit**; **Ctrl+Enter** also fits |
| Right column | The latest fit: numbers and k- / R-space plots; tabs below: Parameters, Paths, Quality, Diagnosis, Robustness, Full report |
| Top right | **Before you fit · what is a good fit** (separate window with three tabs: before fitting, what is a good fit, joint fits; opens on the third tab in joint mode) |

Drag the divider between the columns to resize them. A fit updates only the right column; the left keeps its settings and scroll position.

**Set up the fit (left)**

1. **Data and FEFF**: choose the data (with χ(k)) and FEFF folders (several allowed: phases / sites).
2. **Fit range**: kmin, kmax, dk, window, k-weights (1, 2, 3 together recommended), Rmin, Rmax, fit space. N_idp and the variable limit N_idp/2 are shown.
3. **Paths**: tick the paths to use; a single click edits a cell:

| Column | What to write |
|---|---|
| N | A number fixes the coordination number; a name (e.g. `n1`) lets it vary; empty = FEFF degeneracy |
| s02, e0 | Parameter names, usually `s02` and `e0` shared by all paths |
| deltar, sigma2 | Parameter names; the same name means shared (e.g. `dr1`, `ss1` for two close Ir–O paths) |
| Any column | Accepts expressions, e.g. `ss1*1.5` |

4. **Parameters**:
   - ticked `vary` = free, unticked = fixed at `value`;
   - non-empty `expr` = constrained by the expression;
   - `min` / `max` = allowed range;
   - `value` takes any number of decimals (e.g. 0.00412 for σ²);
   - the variable count is shown live and turns orange above N_idp/2.

**Fit and read the result (right)**

1. Enter a model name and click **Fit** (or Ctrl+Enter).
2. The right column shows R-factor, χ²_ν, N_idp, variables and the k- and R-space plots (|χ(R)| and Re χ(R); fit window in grey).
3. Tabs:

| Tab | Content |
|---|---|
| Parameters | Value and error of each parameter |
| Paths | N, R, σ², ΔE0 of each path |
| Quality | Point-by-point ✓ / ⚠ (the tab shows the number of ⚠), see below |
| Diagnosis | Residual in the window, white-noise estimate and their ratio; k-space residual (purple dotted lines mark spikes); k- and R-segment mismatch with suggestions |
| Robustness | **Run robustness check**: kmin ±0.5, kmax ±1, Rmax ±0.2 Å and k¹/k²/k³ alone; parameters that move more than their error are marked unstable |
| Full report | Larch's feffit report (with correlations) |

4. **Use fitted values as start**: copies the fitted values into the `value` column of the parameter table for the next fit (fixed and constrained parameters are left alone).
5. When satisfied, **Save result**: the model goes to `models/` and the result into report and methods export.

**What the Quality tab checks**

- R-factor: < 0.02 very good; 0.02–0.05 acceptable for a first shell;
- variables ≤ N_idp/2;
- residual / noise ≤ about 2 (data limit reached);
- every variable has an error smaller than its value; no parameter sits on a bound;
- |ΔE0| ≤ 10 eV; σ² positive and not excessive; |ΔR| ≤ 0.2 Å;
- no pair with |r| > 0.9;
- whether a single k-weight was used; whether the robustness check has been run.

> These are necessary, not sufficient: an added shell must also pass the F-test (section 12) and stay stable in the robustness check.

**Restraints** (below the parameter table in card 4, optional)

- Pull a parameter towards an independent prior: χ² gets ((expr − value)/σ)² × χ²_ν(unrestrained) added. **Give σ on the scale of the reported errors**, e.g. S0² = 0.816 ± 0.05 from a standard fit: value = 0.816, sigma = 0.05.
- The table has 5 columns `name expr value sigma note`: `expr` is a parameter expression (e.g. `s02` or `ss1 - ss2`, names from the parameter table); **Add a row** / **Delete selected row**. An empty table = no restraints and the fit is bit-identical to before. If value or sigma is not a number, or sigma ≤ 0, a message is shown and nothing is fitted.
- Restraints do not add to N_idp and the R-factor counts data only. The “Parameters” tab of the result has a restraints table (prior, fitted value, pull in σ); a pull beyond 2σ raises a warning: the data contradict the prior, so check where the prior came from or the model. Use restraints only with an independent prior.
- Drafts, automatic restore and saved models include the restraints; two models with different restraints cannot be compared with the F-test.

**Debye / Einstein temperature model for σ²** (above the paths of card 3, optional)

- Tick “Use a σ² temperature model” first; only then are “Temperature (K)” and “σ² model…” shown. Usually leave it unticked: it is for one sample measured at several temperatures. Unticked, the model has no `temperature`; if a path σ² already uses `sigma2_debye` / `sigma2_eins` / `tempK`, the box is ticked automatically when the page opens. **Unticking switches the model off**: path σ² values that use it are changed back to plain parameters `ss<shell>` (in every dataset; a message lists them), and the θ and static parameters leave the parameter table.

- With several measurement temperatures, one θ (Debye or Einstein temperature) replaces one σ² per temperature: fewer parameters, and a check that σ² follows a simple vibrational model. Use at least 2–3 temperatures; with a single temperature θ is just another way of writing σ² and adds no information.
- **Temperature (K)**: one field per dataset (per dataset tab in a joint fit); empty = no `temperature` in the model. In `sigma2_debye(tempK, thD1)`, `tempK` takes this value, so the same expression can be copied unchanged to every temperature's dataset. A non-numeric or ≤ 0 temperature is reported and nothing is fitted.
- **σ² model…**: select a row of the path table (otherwise the first ticked path is used) and a dialog opens: model (Free / Debye / Einstein), θ parameter name (default `thD<shell number>` / `thE<shell number>`), θ start and limits (default 50–2000 K; with a temperature and a numeric current σ² the start is back-calculated from that σ², otherwise 300 K), and an optional “static disorder” term (parameter `ss0_<shell number>`, start 0, no lower limit). In a joint fit you can tick “Apply to the same shell of all datasets” (matched by path label). On OK the path's `sigma2` cell becomes `sigma2_debye(tempK, thD1) + ss0_1` and the parameter table gains θ and the static term; “Free” writes `ss<shell number>` back.
- The σ² model functions may only be used in a path's `sigma2` cell (anywhere else the value would silently be wrong; both validation and the fit report an error).
- **“σ²(T)” tab of the result**: one fitted model curve per θ parameter (with the static term, from 0 to 1.2 × the highest temperature) and the fitted σ² of each dataset as points with error bars; the caption gives θ ± error. This is a **fit result and depends on the chosen model**; the Einstein model on a multiple-scattering path is only an approximation (a warning is given), so use Debye for multiple scattering.
- Command line: `xafsmith sigma2 feff0001.dat --model debye --theta 300 --temps 10,100,300` computes σ²(T); `--from-sigma2 0.004 --T 300` back-calculates θ from a σ² at one temperature (print only). For the model JSON see the data standard, section 4.3.

**Multiple-scattering binding** (the **Multiple-scattering binding…** button under the path table of card 3)

- What it does: from the FEFF path geometry and the expressions of the ticked **single-scattering paths**, it suggests `deltar` and `sigma2` for the ticked **multiple-scattering paths** (nleg > 2). The dialog has one row per multiple-scattering path: path, Reff, nleg, deltar now / suggested, σ² now / suggested, status, basis. The “Apply” column is ticked only for rows that would change (consistent rows and rows without a suggestion are not ticked).
- **Suggestions only**: nothing changes until you click Apply; Apply edits only the `deltar`, `sigma2` and `note` (the basis) cells of the ticked rows in this dataset's path table. It creates no parameters and does not touch N / s02 / e0. In a joint fit every dataset tab has its own button and only that tab changes.
- Rules and limits: see the processing guide (XAFS处理规范, section 5, item 8): ΔR is built leg by leg (exact for collinear legs, otherwise an equivalent-bond or fixed-angle linear approximation); σ² uses an independent-bond approximation, which is only approximate for triangular paths. If a needed single-scattering path is missing the row gets no suggestion; tick it and try again.
- Command line: `xafsmith msbind MODEL [--dataset ID] [--out NEW_MODEL]` prints “now / suggested / basis”; `--out` saves a new model (an existing one is never overwritten) and writes `.params.json`.

**Joint fit of several datasets** (several samples fitted at once, parameters with the same name shared)

- At the top of card 1 switch “Mode” to **Joint fit of several datasets**; “Data” becomes a multi-select (at least 2 for a joint fit; selecting 1 equals a single-dataset fit, bit-identical). The FEFF folders are one shared choice.
- The fit range in card 2 is the common value for all datasets; below it **Σ N_idp** is shown (summed over each dataset's actual range). Keep the variables ≤ Σ N_idp/2.
- Card 3 has one tab per dataset (tab = dataset id), each with its own path table; a new dataset's table is copied from the first one, and **Copy this path table to the other datasets** syncs them. Under each table you can **override the fit range** (kmin / kmax / Rmin / Rmax; empty = common range). **Parameters with the same name are shared between datasets; rename to make them independent** (e.g. `ss1_300K`).
- Card 4 is one shared parameter table (names are the union over the ticked paths of all datasets).
- Right column: joint metrics on top (joint R-factor, χ²_ν, Σ N_idp, variables, datasets); the **Dataset** drop-down switches the plot, paths, quality check and diagnosis to that dataset (with its R-factor, N_idp and χ² share); “Parameters” and “Full report” are joint. Robustness checks are not yet supported for multi-dataset models.
- **Save result** writes one CSV (one row per path, with a `dataset` column), one model json (`datasets` format), one report, and one figure per dataset `…_<dataset>_fit.png`. A saved multi-dataset model runs directly from **Run a saved model** (the samples come from the model's `datasets`, the sample box is greyed) or from the command line `xafsmith fit <model>`.
- Drafts and automatic restore also keep the multi-dataset settings (chosen datasets, per-dataset path tables and range overrides).

**Two common recipes**

- **S0² from a standard**: let S0² vary on a standard of known structure and enter the result under “Calibrate & process → Processing parameters → S0²”. For samples, untick vary for `s02` and set its value.
- **One model for a series** (time, potential): expand **Run a saved model** at the top of the left column → choose the model → select several samples → **Run**. The model is applied to each sample and the results go to Fit history. Validate the model on a standard first.

- **A fit you are in the middle of**: at the top of the left column, **Fit drafts** → name it → **Save draft**. A draft stores the data choice, FEFF folders, fit range, path table and parameter table (including edited start values and constraints). Later pick it in the same place → **Open** to continue from those settings (the spectra it needs are reloaded automatically). A draft does not contain fit results; click “Save result” for finished fits.
- **Automatic restore**: when you close the app, the current page, processing parameters, loaded spectra and page settings are saved to `output/gui/session.json` in the project and restored the next time you open it (can be switched off on the home page). Only spectra registered in `meta.csv` can be restored; files read directly must be read again. Normalization / background / FT parameters come back as you had set them in the GUI.

### General conventions

- **Messages**: persistent errors (a failed load or normalization) appear as a dismissable banner at the top of the page; success and light hints show briefly at the bottom of the window; only blocking errors open a dialog.
- **Number boxes**: the mouse wheel changes a value only after you click into the box, so scrolling the page never alters parameters.
- **Progress**: the status bar at the bottom shows a progress bar, elapsed time and **Cancel**; a single fit / FEFF run / report build cannot be stopped midway and the status bar says "cannot be interrupted".
- **Windows**: position and size are remembered (and pulled back onto the screen if needed); the help window too.
- **Switching pages**: inputs, inner tabs and scroll position are kept when you come back; a page is rebuilt only when the data changed.
- **Unsaved edits**: with unsaved edits in the meta.csv table or the "Calibrate & process" parameters, switching page, edge, project or language, or closing the window asks "Save / Discard / Cancel"; **Undo edits** on the card reloads from disk. Removing spectra and overwriting a group by a merge also ask first.
- **Background tasks**: while a task runs its button is greyed out and cannot start twice (batch steps ①②③ exclude each other); the project or language cannot be switched while tasks run, but you can cancel them.
- **Navigation**: pages whose prerequisite is missing (e.g. no spectra loaded) are greyed in the sidebar, and the tooltip says which step is missing; the "Workflow & project" pop-up opens on click and closes when you click outside.
- **Help window**: Back / Forward and Find (Ctrl+F; Enter next, Shift+Enter previous) at the top; a heading outline on the right when the window is wide; table-of-contents links in the basics notes jump to the section.
- **Shortcuts**: F1 help; Ctrl+O open / new project; Ctrl+1…9 go to the n-th sidebar page; Esc closes the "Workflow & project" pop-up; Enter in the project path box opens the project; Ctrl+Enter fits.

### 12　Fit history

- All open fits are listed; **Save all to output/fits/** saves them at once.
- **F-test (Hamilton)**: choose the “simpler” and the “more complex” model (with an extra shell or parameters) and click **Compare**. Only **p < 0.05** makes the extra shell significant.
- **Model comparison**: tick the fits to compare (at least 2) and click **Compare**: the table is ordered by number of variables and lists R-factor, χ²_ν, χ², variables, N_idp, number of restraints and, for each model, the F-test (F, p) against the previous row. Adjacent models with different data or fit ranges, different restraints or the same number of variables get no F-test (reason in the “note” column); the F-test card's **Compare** also shows a warning in those cases. **The F-test is valid only for nested models (the smaller is a special case of the larger); the software does not check nesting.** **Save as CSV** writes `output/fits/model_compare.csv`; on the command line use `xafsmith compare model1 model2 …`.
- **View fit**: switch to any fit, shown like the right column of EXAFS fitting.

### 13　LCF (linear combination fitting)

1. Choose the sample and the end-members (**measured standards only**).
2. Choose the space (normalized μ / derivative / χ(k)), range and constraints (Σw = 1, 0 ≤ w ≤ 1, fit an energy shift).
3. Click **LCF**.

**Results**: weights with errors and the fit plot; single-standard fits for comparison and, with three or more standards, all combinations. Results are appended to `output/lcf/lcf_results.csv`. State any non-measured end-member as an assumption under “Note”.

### 14　XANES quantification

Load samples and standards first. Three tabs:

| Tab | What it does |
|---|---|
| Edge & white line | E0 (derivative maximum), E_half (normalized μ = 0.5), white-line position, height and area; **Save** writes `output/xanes/xanes_features.csv` |
| Valence calibration | Fits “edge position = slope × valence + intercept” on **measured standards of known valence**, then estimates the valence of samples with errors; values outside the standards' range are flagged “extrapolated” |
| Pre-edge fitting | Choose the range, number of peaks and edge baseline (erf / arctan) and click **Fit pre-edge**; peaks at a range limit or with area ≈ 0 are flagged |

> Valence calibration only holds for standards and samples with the same ligands and similar structures.

---

## 5. Export

### 15　Report export

1. With unsaved fits, click **Save all open fits first**.
2. Click **Build report** to get `output/reports/汇总_<time>/`:
   - **汇总.xlsx**: samples, calibration, quality check, processing results, fit overview (one row per model), path parameters, LCF, processing parameters;
   - **汇总报告.html**: the same tables plus every figure, grouped (spectra / fits / LCF) as thumbnails.
3. Buttons: **Open report folder**, **Save 汇总.xlsx as…**, **Open report in browser**. **Preview** shows each table.

**Figures in the browser**: click a thumbnail to enlarge it; scroll to zoom, drag to pan, double-click to reset; Esc or a click outside closes it. For a PDF use the browser's Print → Save as PDF.

### 16　Figure export

**Settings**

1. Figure type: normalized XANES, XANES derivative, kⁿχ(k), |χ(R)|, fit (k + R).
2. Spectra, offset, range; in the **Plot order** list drag items or use ↑ / ↓ / reverse to set the curve order (with an offset the first is at the bottom; the legend, exported files and Origin project follow this order).
3. **Palette**: 24, named as in PeakForge, in six families (Waters, Forests, Earth, Skies, Stone, Fields), each marked with its type:
   - monochrome ramps for one series of samples (oxidation state, time, potential), sampled evenly along the ramp;
   - contrast, soft (print), colour-blind safe.
   - Default **Waters · Glacier**: samples blue, standards grey.
4. **References / standards**: the selected spectra are drawn grey and slightly thinner (default: names containing foil / powder / metal); clear it to treat all as samples.
5. Size (single column 85 mm / 1.5 column / double column 178 mm / slide 16:9), formats (TIFF, PNG, SVG, PDF), file name.

The preview is at true size; below it is the English caption (saved with the figure as .txt, including processing parameters).

**Save**: **Save to output/figs/journal/**. Arial, 600 dpi TIFF / PNG.

**Export Origin project (.opju)**

Each curve becomes an X/Y column pair (column name = legend), plotted in one format:

| Item | Setting |
|---|---|
| Layer | 25 × 19 cm |
| Font | Arial 32 pt (axis titles, tick labels, legend) |
| Axes | 2 pt, boxed; no ticks on the top and right; outward ticks |
| Lines | 3.5 pt for data, 3 pt for standards; anti-aliasing on |
| Legend | No frame; formula subscripts in Origin syntax (IrO\-(2)) |
| XANES | Energy E (eV) on the x axis; y ticks hidden when offset |

- With Origin (2021 or later) installed: `output/figs/journal/origin/<name>/<name>.opju` is built directly in about 10–30 s; the window pauses meanwhile.
- Without Origin: only the data (.csv), `spec.json` and `build_origin.py` are written. On a computer with Origin, open the script window and run `run -pyf "<that folder>/build_origin.py"` to get the same project (see README_Origin.txt in the folder).

### 17　Methods export

**Methods paragraph**

1. Fill in light source, beamline, monochromator, detection etc. and click **Save facility info**.
2. Optionally limit the scope to some samples.
3. Click **Generate**: a Chinese and an English paragraph (each with **Copy**), also saved as `output/reports/方法段落.md`.

Only facts recorded in the project are stated: references and ΔE, normalization / background / FT parameters, fit ranges, N_idp, S0² source, versions. Missing facility fields stay as [placeholders]. **It is a draft: check every sentence before submission.**

**Fit-parameter table (Supporting Information, Table S[n])**

1. Only fits saved with **Save result** appear. Choose the fits for the SI (several allowed).
2. The table gives N, R, σ², ΔE0 per path (error in the last digit in brackets), R-factor, χ²_ν and N_idp / variables.
3. **Copy table**: pastes as a table in Excel; in Word use “Convert Text to Table”.
4. Or **Save .csv**, or **Save .md (with fit text)**, which adds the fitting description in English and Chinese (FEFF version and structure, k / R ranges, k-weights, window, independent points and variables, S0² source, constraints, error estimate).
5. Adjust the “Table S[n]” numbering and structure sources to your paper.

### 18　Export to Athena

Under **Export** at the bottom of **Normalization**, enter a file name and click **Export .prj**; the file goes to `output/gui/athena/`.

The .prj holds the calibrated energy and μ(E) together with this software's E0, normalization ranges, rbkg, k range and window, so Athena shows the same processing for a side-by-side check.

---

## 6. Tools and help

### 19　Sample preparation

**Sample** (shared by the two tools below)

- **Formula**: e.g. IrO2, Ta2O5; non-integer as IrCo0.2O2.
- **Absorber**: read from the formula; default the heaviest element.
- **Edge**: K / L3 / L2 / L1.

The page lists the elements and the edge energy.

**Pellet calculator**

- Input: pellet area (φ13 mm = 1.327 cm²), diluent and its mass, target total μt;
- Output: recommended sample mass, total μt above the edge, edge step Δμt;
- with a sample mass entered, the actual μt for that mass.

> Transmission: total μt 1.5–2.6 is best, Δμt ≥ 0.2; a uniform pellet without pinholes matters more than matching Δμt.

**Interfering-edge screening**

- Elements screened = those in the formula + in the diluent + “Other elements present” (optional, e.g. K or Cl impurities);
- other edges inside the scan are listed with their k; keep kmax below the first one.

Data: xraydb (Elam tables).

### 20　Edge lookup

Like Hephaestus' periodic table: click an element for three tables in one row.

| Table | Content |
|---|---|
| Absorption edges | Energy, fluorescence yield and jump ratio of each edge |
| Fluorescence lines | Siegbahn name, energy, relative intensity (normalized within one initial level), transition |
| Fluorescence filter | Choose the edge measured and the thickness (absorption lengths μx, default 3); elements whose edge lies between the main line and the absorber edge, with thickness (μm) and transmission of the main line |

Filters are sorted by transmission; the first row is usually the Z−1 element (e.g. Fe K → Mn).

### 21　AI assistant

An XAFSmith project can be handed to an AI assistant (Claude Code, Codex, Cursor, …) for processing, fitting and export.

1. Click **Write / update AI instruction files**. `AGENTS.md` (with the path of the xafsmith command, the workflow and rules) and `CLAUDE.md` are written into the project folder; your own text in them is kept.
2. Open the AI assistant in the project folder (the page shows how for each tool) and say what you want in your own words (examples on the page).
3. Check the AI's work:

| Result | Where |
|---|---|
| Fit models | `models/`; rerun them under “Run a saved model” at the top of EXAFS fitting and check quality and diagnosis |
| Numbers | `output/` |
| Analysis notes | `notes/` |
| Figures, reports | `output/figs/journal/`, `output/reports/` |

After an update (the command path may change), click **Write / update AI instruction files** again.

### 22　Help, language and updates

- **Help**: opens a separate window (the main window stays on its page). On its left: GUI guide, Fitting for beginners, Improving fit quality, XAFS basics; at the bottom a separate page **About & disclaimer** (version and credit, full disclaimer, citation with **Copy citation**, license, **Export diagnostics**, update check). The bundle holds the log (`~/.xafsmith/xafsmith.log`), versions, project config and meta.csv — no raw data; send it to the developer on errors.
- **Language**: choose **English** at the bottom of the sidebar; interface and documents switch, and the choice is remembered.
- **Updates** (About & disclaimer page):
  - tick “Check for updates at start-up” (contacts github.com only, sends nothing), or click **Check now**;
  - when a new version exists the sidebar shows it; **Update now** downloads and installs it — close and reopen the window afterwards.

---

## Appendix

### A　Where the results are

| Content | Location |
|---|---|
| Processed spectra (normalized, χ(k), FT) | `output/processed/` |
| Quality-check report | `output/qc/qc_report.csv` |
| Fit results | `output/fits/exafs_fits.csv`; models in `models/` |
| LCF results | `output/lcf/lcf_results.csv` |
| XANES features | `output/xanes/xanes_features.csv` |
| Wavelet data and figures | `output/gui/wavelet/` |
| Normalized data, Athena projects | `output/gui/norm/`, `output/gui/athena/` |
| Exported figures, Origin projects | `output/figs/journal/`, `output/figs/journal/origin/` |
| Reports, methods paragraph | `output/reports/` |

### B　Reminders

- R-space peaks are **not phase-corrected** and sit about 0.3–0.5 Å below the true distance; take distances from the fit.
- Variables ≤ N_idp/2; the quality check flags |ΔE0| > 10 eV, σ² ≤ 0 and parameters at bounds — revisit the model.
- Added shells need the F-test; a shell with p ≥ 0.05 is not “observed”.
- White lines and amplitudes from fluorescence and transmission cannot be compared directly (self-absorption, thickness).
- Separate three kinds of statements: **measured** (visible in the spectra), **fitted** (model-dependent), **inferred** (needs other experiments).

### C　Troubleshooting

| Symptom | What to do |
|---|---|
| Double-clicking the icon opens no window | Installer: run the installer again; source install: double-click installer.py again (projects and data unaffected) |
| “Not installed yet” (source install) | Double-click installer.py again |
| ref_file empty in the register | The batch has no reference: add the foil measured in that beamtime and scan again |
| Register still empty after copying files | Click **Scan data/raw and register new files** |
| A spectrum has glitches | Load & check → Quality check → Deglitch; or set use = 0 for that scan (with a reason) |
| Origin export gives only data and a script | Origin (originpro) was not found; run build_origin.py in Origin as in section 16 |
| A red error box on a page | Other pages keep working. Help → About → **Export diagnostics** (log, versions, environment, project configuration; no raw data) and post it with the message on [GitHub Issues](https://github.com/Wiolic/XAFSmith/issues) |
| Start over | Delete the project's `output` folder and run ① ② ③ under “Calibrate & process” again; raw data are never changed |
