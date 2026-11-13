# Joint fitting of a sample series (step by step)

> For: a series of samples of the same system at the same absorption edge (time, potential, temperature or composition series) when you want to know
> how the structural parameters change along the series.
> The workflow is split into 9 steps. Each step says **which page, what to click, what to look at, and when you may move on**.
> Interface details: GUI guide, sections 11, 12 and 16; model file format: data standard 4.1.

---

## 0　First decide what question you are asking

A joint fit is not a "better fit". It is a fit **under one explicit assumption**: **parameters with the same name are the same number in every sample**.
Pick the route that matches your question:

| Your question | Suitable approach | Note |
|---|---|---|
| What is the structure of each sample, independently | **Fit each sample separately** (run one model on all samples) | That is step 3; no joint fit needed |
| Some quantities (ΔE0, a bond length) should physically be the same across the series, and you want the **changing quantities** (σ², N) more reliably | **Joint fit** | The main line of this guide |
| A weak outer shell cannot be determined in single fits | **Joint fit** (shared distance and ΔE0) | The conclusion must state the "shared distance" assumption |
| The samples are mixtures of known phases and you want fractions | **LCF** (linear combination) | Not a shell fit |
| The samples have completely different structures | Separate fits | A joint fit only puts separate fits side by side; no gain |

> In one sentence: **joint fit = separate fits + the assumption of which parameters are equal**. If the assumption is right you get fewer parameters,
> smaller errors and clearer trends; if it is wrong, real differences are flattened away.
> So the order is always: **separate first, joint second, then test the assumptions with F-tests**.

---

## 1　Preparation: checklist before fitting

Tick everything before going on.

| ☐ | Check | Where |
|---|---|---|
| ☐ | All samples at **the same edge and the same measurement mode** (do not compare amplitudes of transmission and fluorescence in one series) | Data registry (`edge_key`, `mode` in `meta.csv`) |
| ☐ | Every sample calibrated with a reference foil; ΔE reasonable | Calibration & processing → calibration results |
| ☐ | Scans inspected before merging; bad scans rejected with a reason | Load & inspect; `output/qc/qc_report.csv` |
| ☐ | **One set of processing parameters for all samples**: E0 definition, normalization ranges, rbkg, k-weight, FT k-range and window | Calibration & processing → processing parameters |
| ☐ | χ(k) computed for every sample | χ(k) & FT |
| ☐ | FEFF paths available (from a CIF or a hand-written structure) | FEFF paths |
| ☐ | **S0² determined on a standard of known structure** (step 2 below) | EXAFS fitting |
| ☐ | Neighbouring edges checked; k upper limit chosen | Edge lookup; XAFS processing rules |
| ☐ | (For the trend plot) a numeric **`seq`** filled in `meta.csv` for every sample (e.g. reduction time 50 / 100 / 200 / 300) | Open `data/meta.csv` in Excel or a text editor; repeated scans of one sample (several rows) get the same number |

Without `seq` the fit still works; the trend plot's x-axis then falls back to measurement time (hours since the first sample), or to sample order.

---

## 2　Step 1: determine S0² on a standard

S0² and the coordination number N are fully correlated (amplitude = N × S0²). **Determine S0² on a standard with known N**, then fix it for the samples.

1. **EXAFS fitting** page, mode **Single dataset**; data = the standard (a metal foil or a well-known oxide), FEFF folder = its calculation.
2. Tick only the first shell; N = crystallographic coordination number (fixed); tick vary for `s02`.
3. Fit → quality checks all green, R-factor around < 0.02.
4. Note S0² ± error (e.g. 0.82 ± 0.05); enter it under **Calibration & processing → processing parameters → S0²**, or in `notes/`.

**Move on when**: S0² is between about 0.7 and 1.0 with a reasonable error; otherwise check the standard first (nanocrystalline or disordered standards have larger σ²).

---

## 3　Step 2: fit one representative sample alone and settle the model

Before the joint fit, **the model (which paths, which shells) must be settled on one sample**.

1. Choose the best and most representative sample (usually the longest usable k-range and the lowest noise).
2. In **Single dataset** mode:
   - Fit range: kmin, kmax from signal-to-noise and neighbouring edges; k-weights 1, 2, 3; Rmin, Rmax around the peaks to fit.
   - Paths: start with the first shell only; untick vary for `s02` and enter the value from step 1.
   - Parameters: usually `e0`, `dr1`, `ss1` free; N fixed at the structural value, or a parameter (e.g. `n1`) if it should vary (N and σ² are strongly correlated; do not free both for many shells).
3. For each added shell:
   - check whether the R-factor and χ²_ν improve clearly;
   - compare before / after under **Fit history → F-test / model comparison table**: **only p < 0.05 is significant**;
   - run the **robustness check** to confirm the parameters are stable when kmin / kmax / Rmax change.
4. Then **Save result** (the model goes to `models/`) with a clear name, e.g. `TaO_2shell`.

**Move on when**: this sample's fit passes the quality checks, every shell passes the F-test, and the number of variables ≤ N_idp/2.

---

## 4　Step 3: the same model on every sample, separately (evidence for what to share)

This step answers the key question of a joint fit: **which parameters are really equal across the samples?**

1. On the EXAFS fitting page, expand **Run a saved model** at the top of the left column → choose the model from step 2 → select all samples → **Run**.
   The model is applied to each sample in turn; all results appear in **Fit history**.
2. Look at each fit in the history and copy **value ± error** of every parameter into a table (or save and read `output/fits/exafs_fits.csv`):

| Parameter | Sample A | Sample B | Sample C | Sample D | Decision |
|---|---|---|---|---|---|
| ΔE0 (eV) | 3.1 ± 0.9 | 2.7 ± 1.0 | 3.4 ± 0.8 | 2.9 ± 1.1 | consistent within errors → **can share** |
| R₁ (Å) | 1.94 ± 0.01 | 1.94 ± 0.01 | 1.95 ± 0.01 | 1.94 ± 0.01 | consistent → **can share** |
| σ²₁ (Å²) | 0.0060 ± 0.0008 | 0.0071 ± 0.0009 | 0.0089 ± 0.0010 | 0.0098 ± 0.0011 | trend → **independent** |

(The numbers are only an illustration, not results of any real sample.)

3. **Rules**:
   - difference between two samples > about 2 × combined error (√(σ_A² + σ_B²)) → **do not share**;
   - all consistent within errors → **may share** (an assumption; confirm it with an F-test in step 6);
   - the quantity you are studying (e.g. σ² or N in a time series) **must not be shared** — sharing leaves one value and removes the trend yourself.

**Move on when**: you have written down "shared: …; independent: …" with the reasons in `notes/`.

---

## 5　Step 4: set up the joint fit (left column of the fitting page, card by card)

### 5.1　Card 1 Data and FEFF

1. Switch **Mode** to **Joint fit of several datasets**.
2. Select all samples under **Datasets** (at least 2). Each sample gets a **dataset id** (from the file name, e.g. `IrTa-100`); parameter-name suffixes use it.
3. **FEFF folder**: one selection shared by all datasets (one structural model).

### 5.2　Card 2 Fit range

1. This is the **common range of all datasets**; normally the values from step 2.
2. Below it, **Σ N_idp** (sum over datasets) is shown. **Variable limit = Σ N_idp / 2**.
3. If one sample is noisy and needs a shorter k-range: on that dataset's tab in card 3, enter its own kmax under **Override the fit range** (empty = common value).

### 5.3　Card 3 Paths (one tab per dataset)

1. **Set up the path table of the first dataset**: tick paths, enter parameter names for N, s02, e0, deltar, sigma2 (as in the step 2 model).
2. Click **Copy this path table to the other datasets**: all path tables become identical — **every parameter is now shared** (same names).
3. Optionally switch on **Sync ticked paths to all datasets**: ticking / unticking a path on any tab does the same on the other tabs; only the tick is synced, never expressions.
4. **Rename the parameters that must be independent** (the "independent" list from step 3):
   - **σ²**: click **Independent σ² per dataset**; shared σ² names become `ss1_<dataset id>` (one per dataset), the parameter table is filled in, start value / vary / bounds copied from the original. Clicking again adds nothing. A σ² name referenced by another parameter's expression is left unchanged (renaming would break that expression); rename it by hand if needed.
   - **N, ΔR, ΔE0**: no one-click button; rename by hand on each tab. Naming suggestions below.
5. With a **σ² temperature model** (Debye / Einstein, multi-temperature data) σ² follows one shared θ and the "Independent σ²" button is greyed out — the two are opposite intentions; choose one.

**Naming conventions (recommended)**

| Intent | How | Example |
|---|---|---|
| Shared by all | the same name | every dataset uses `e0`, `dr1` |
| Independent per sample | name + `_` + dataset id | `ss1_IrTa_50`, `ss1_IrTa_100`, … |
| Shared within a subgroup | your own group name | first two `dr1_early`, last two `dr1_late` |
| Determined by another parameter | an expression | `ss2` = `ss1_IrTa_50*1.5` |

### 5.4　Card 4 Parameters (one shared table)

1. The names are the union of the parameters used by the ticked paths of all datasets.
2. `s02`: **untick vary**, value = the standard's value from step 1 (or a restraint: value = standard's value, sigma = its error).
3. Give other parameters sensible start values and bounds: ΔE0 −15 to 15 eV, ΔR −0.5 to 0.5 Å, σ² 0 to 0.05 Å².
4. Watch **Variables**: it turns orange above Σ N_idp/2 — reduce the independent parameters or the model.

**Counting variables (illustration)**: 4 datasets, each kmin 3, kmax 11, Rmin 1, Rmax 2 → N_idp ≈ 2×8×1/π ≈ 5.1 each, Σ N_idp ≈ 20, limit ≈ 10.
Shared `e0`, `dr1` (2) + one σ² per sample (4) = 6 variables → fine. Making N independent too (+4 = 10) reaches the limit and reliability drops markedly.

### 5.5　What to share and what not (a usual starting point)

| Parameter | Usually | When to separate |
|---|---|---|
| S0² | **fixed** at the standard's value (one for the series) | not shared between transmission and fluorescence (self-absorption) |
| ΔE0 | **shared** (same edge, same FEFF, same E0 definition) | single fits differ by > 2σ, or the absorber's chemistry changes strongly |
| ΔR (first shell) | **shared** if the structure does not change | independent if bond-length change is the question; ΔR and ΔE0 are correlated — be careful with bond-length conclusions |
| σ² | **independent** (usually the quantity of interest in time / potential series) | multi-temperature data: Debye / Einstein model with one shared θ |
| N | **fixed** at the structural value first | independent if coordination change is the question; N and σ² are strongly correlated |
| Distance of a weak outer shell | **shared** (this is why a joint fit can determine weak shells) | the conclusion must state "under the shared-distance assumption" |

---

## 6　Step 5: run and read the results

1. Enter a **model name** at the bottom of the left column (e.g. `TaO_joint_ssfree`) and click **Fit** (Ctrl+Enter).
2. **Top of the right column = joint metrics**: joint R-factor, χ²_ν, Σ N_idp, variables, datasets.
3. **Dataset** drop-down: switch to each dataset and look at its own k / R fit plots, R-factor, N_idp and **χ² share**.
   - If one dataset has a much larger χ² share, or the warning "residual per fit point … is N times … (mismatch)" appears: **its mismatch inflates the errors of all parameters**. Check that dataset first — range, noise, or a model that does not suit it.
4. Tabs:
   - **Parameters**: all parameters, value ± error (joint).
   - **Paths**: N, R, σ², ΔE0 of every path of the current dataset.
   - **Quality**, **Diagnosis**: for the current dataset (switch through all datasets).
   - **Trend**: see step 7.
   - The **robustness check is not available for joint fits** yet: run it on the separate fits from step 3 for the key samples.
5. To start the next fit from these results: **Use fitted values as start**.
6. When satisfied, **Save result**: result table (one row per path, with a `dataset` column), model JSON, report, one fit figure per dataset, and the trend table `output/fits/<model>_trend.csv`.

**Move on when**: every dataset's fit plot is reasonable, no serious mismatch warning, and the joint results lie within the errors of the separate fits from step 3 (if not, a sharing assumption is probably wrong).

---

## 7　Step 6: test the assumptions with F-tests (the step most often skipped)

The conclusions of a joint fit depend on what is shared. **Test each key assumption with an F-test**: fit two **nested** models (the smaller one is a special case of the larger), keep both in the fit history, and compare.

**Getting two models**: fit and save the first → change something on the left (parameter names / ticks) → a **new model name** → fit again → both appear in **Fit history**.

| Question | Smaller model | Larger model | Conclusion |
|---|---|---|---|
| ① Is this shell present in the series? | path **unticked** in all datasets | path **ticked** in all | only p < 0.05 allows "observed" |
| ② Does one sample need this shell itself? | path removed only in that dataset | present everywhere | valid under the shared-distance assumption; state it |
| ③ Does σ² (or N, ΔR) really differ between samples? | **one** `ss1` for all datasets | **one per dataset** (Independent σ²) | **with p > 0.05 the σ² "trend" is not supported by the fit** |

**Compare**: Fit history → **model comparison table**, tick the two fits → **Compare** (or the F-test above: choose the simpler and the more complex model → Compare).
Both models must use **the same data and fit ranges** and the same restraints; the software notes differences in the note column or above the result. **It does not check nesting — you must ensure it.**

---

## 8　Step 7: look at the trends

The **Trend** tab of the result area (joint fits with ≥ 2 datasets):

1. **Panels**: N, R, σ², ΔE0, edge position E0; N, R, σ² and edge position by default.
2. **Paths**: which paths to plot (all used paths by default).
3. **x-axis**: `seq` from `meta.csv` (only if every sample has one) → otherwise measurement time (hours) → otherwise sample order. The page says which samples lack `seq`. The **x-axis title** can be edited (e.g. "Reduction time (s)").
4. Below is the trend table; **Save trend table** writes `output/fits/<model>_trend.csv`.

**How to read it (important)**

- Error bars are **1σ** (covariance matrix scaled by √χ²_ν, Larch).
- Paths with **fixed N** (N empty, a number, or depending only on fixed parameters) have **no error bar** — not zero error, but not fitted.
- **Shared parameters** are **one fitted value** for all samples and plot as a horizontal line. **A horizontal line does not mean "no change"**, only that you assumed none; the page and the caption say which values are shared.
- The **edge position E0** is a **measured** value from normalization, not a fit result — model-independent supporting evidence.
- Whether a trend is significant is decided by the F-test of question ③ in step 6, not by how the points look.

---

## 9　Step 8: export figures

1. **Figure export** page, choose **Trend** at the top.
2. Choose the joint fit (latest by default), panels, paths, x-axis title; size (single column 85 mm / 1.5 column / double column / slide 16:9), palette, formats (TIFF / PNG / SVG / PDF), file name.
3. **Save to output/figs/journal/**: the figure plus an English caption (.txt) stating the model, number of datasets, edge, x-axis source, meaning of the error bars, shared parameters and fixed N.
4. **Export Origin project (.opju)**: each curve becomes X / Y / yErr columns, line + filled circles + error bars. (Error-bar line width and cap width currently use Origin's defaults and are not yet set to the common style.)
5. k / R fit plot of each dataset: Figure export → χ(k) or |χ(R)| → tick **Overlay fit**; or the `output/figs/<model>_<dataset>_fit.png` written by Save result.

---

## 10　Step 9: record and write the conclusions

1. Write a note in `notes/`: model name, shared / independent list with reasons, source of S0², the F-test results (p for each of the three questions), the trend-table file name.
2. Separate three kinds of statements:
   - **Measured**: shift of the edge position E0, change of R-space peak heights (model-independent).
   - **Fit result**: "with ΔE0 and R₁ shared, σ²₁ increases from … to … (F-test p = …)".
   - **Inference**: structural interpretation (more disorder, local reconstruction, …) needs other characterisation.
3. **Do not claim**: a shell "observed" without passing the F-test; a "trend" in a parameter that failed question ③; "no change" in a shared parameter.

---

## 11　Troubleshooting

| Symptom | Cause | What to do |
|---|---|---|
| σ² is identical for all samples | same σ² name → shared | click **Independent σ² per dataset**, or rename by hand |
| Variables shown in orange | too many independent parameters | share parameters whose differences are not significant; fewer shells; longer k-range (more N_idp) |
| One dataset has a large χ² share / mismatch warning | this sample does not suit the model or range | check it alone: k-range, noise, does it need different paths |
| Joint results outside the separate-fit errors | sharing assumption wrong | make that parameter independent and F-test |
| ΔE0 beyond ±10 eV | E0 definition or model problem | check that the E0 definition is the same for the whole series |
| Trend x-axis is "Measurement time (h)" | a sample has no `seq` | add `seq` in `meta.csv` (the page says which) |
| Trend x-axis is "Dataset" | neither `seq` nor `time` complete | as above |
| A path has no error bar | N fixed | normal; write N as a parameter name to fit it |
| One sample used in two datasets | the same data counted twice → errors underestimated | remove one (the software warns) |
| "Independent σ²" does nothing | no σ² name shared by ≥ 2 datasets, or a σ² temperature model is used | read the message; temperature model and independent σ² are alternatives |
| Robustness check greyed out | not available for joint fits | robustness-check the separate fits of key samples |

---

## Appendix: command line and model file

```
xafsmith fit JointModel                  # run a joint fit (model with datasets)
xafsmith compare Model1 Model2 …         # model comparison table (F-test of adjacent models)
xafsmith ftest SmallModel LargeModel     # F-test of two nested models
xafsmith trend JointModel [--seq-label "Reduction time (s)"] [--panels N,R,sigma2,E0] [--nosave]
xafsmith figure --kind fit --model JointModel --dataset DatasetId
```

Structure of a joint model JSON (see data standard 4.1):

```json
{
  "name": "TaO_joint_ssfree",
  "kmin": 3, "kmax": 11, "dk": 1, "window": "hanning", "kweight": [1, 2, 3], "rmin": 1.0, "rmax": 2.0, "fitspace": "r",
  "params": {"s02": {"value": 0.82, "vary": false}, "e0": 0.0, "dr1": 0.0,
             "ss1_A": 0.005, "ss1_B": 0.005},
  "datasets": [
    {"id": "A", "sample": "sampleA",
     "paths": [{"file": "output/feff/…/feff0001.dat", "label": "Ta-O", "s02": "s02", "e0": "e0", "deltar": "dr1", "sigma2": "ss1_A"}]},
    {"id": "B", "sample": "sampleB",
     "paths": [{"file": "output/feff/…/feff0001.dat", "label": "Ta-O", "s02": "s02", "e0": "e0", "deltar": "dr1", "sigma2": "ss1_B"}]}
  ]
}
```

`e0` and `dr1` have the same name in both datasets → shared; `ss1_A` and `ss1_B` differ → independent.
