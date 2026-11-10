# Beginner EXAFS fitting tutorial: what each step does and why

> ⚠️ **Disclaimer**: XAFSmith is provided "as is", without warranty. The authors accept no responsibility for results obtained with it. Please validate your results; **we recommend cross-checking key results against Athena / Artemis**.
> 📖 **Citation**: if you use XAFSmith in a publication, please cite Eggy & Claude, XAFSmith, https://github.com/Wiolic/XAFSmith, together with Larch and FEFF.

This tutorial is for people doing **their first EXAFS fit**. No programming or command line is needed — only mouse clicks.
Every step has three parts: **Principle** (why) → **Operation** (where to click) → **How to tell it is right**.

The running example is **IrO₂ (Ir L₃-edge)**: its structure is known (rutile; every Ir has 6 O neighbours), so it is suitable for determining S0².
The IrO₂ numbers quoted here come from real fits in the authors' project; your data will differ.

The **GUI guide** describes where to click in detail; this tutorial focuses on the principles and the criteria for judging results.

---

## 0. The big picture

### 0.1 What XAFS measures
When the X-ray energy crosses an absorption edge of an element (e.g. Ir L₃ ≈ 11215 eV), the absorption coefficient μ(E) rises sharply: a core electron is ejected as a **photoelectron**.

- **XANES** (from the pre-edge to ~50 eV above the edge) reflects **oxidation state and coordination symmetry**: edge position, white-line intensity, pre-edge peaks.
- **EXAFS** (~50–1000 eV above the edge): the outgoing photoelectron wave is **backscattered** by neighbouring atoms and interferes with itself, causing small oscillations in μ(E).
  The oscillation **frequency** depends on the **distance R** to the neighbours, the **amplitude** on their **number N** and **disorder σ²**, and the **shape** (k-dependence of amplitude and phase) on **which element** they are.

An EXAFS fit therefore answers: **within a few Å of the absorber, how many atoms of which kind sit at what distance, and how disordered are they?**

### 0.2 The EXAFS equation (this is what is fitted)

$$\chi(k)=\sum_j S_0^2\,N_j\,\frac{|f_j(k)|}{k R_j^2}\,e^{-2k^2\sigma_j^2}\,e^{-2R_j/\lambda(k)}\,\sin\!\left[2kR_j+\delta_j(k)\right]$$

| Symbol | Meaning | Provided by |
|---|---|---|
| $k$ | photoelectron wave number, $k=\sqrt{0.2625\,(E-E_0)}$ (Å⁻¹, E in eV) | converted from the data |
| $N_j$ | coordination number of path (shell) j | **fitted** or fixed |
| $R_j$ | distance, $R_j = R_{\text{FEFF}} + \Delta R$ | **fit ΔR** |
| $\sigma_j^2$ | variance of the distance distribution (thermal + structural disorder), the Debye–Waller factor | **fitted** |
| $S_0^2$ | passive-electron amplitude reduction factor, usually 0.7–1.0 | **from a standard**, fixed for samples |
| $\Delta E_0$ | energy-origin difference between theory and experiment | **fitted**, usually shared by all paths of a sample |
| $f_j(k)$, $\delta_j(k)$, $\lambda(k)$ | scattering amplitude, phase shift, mean free path | **calculated by FEFF from a structure** |

Fitting means: FEFF tells what each kind of scatterer “looks like”, and the data determine **N, ΔR, σ², ΔE₀, S0²**.

### 0.3 Workflow overview

```
raw data → ① register → ② quality check → ③ energy calibration → ④ normalization → ⑤ background χ(k) → ⑥ Fourier transform χ(R)
        → FEFF paths → ⑧ S0² from a standard → ⑨ fit samples → ⑩ significance test → ⑪ interpretation → ⑫ summary report
```

---

## 1. Create a project and register data

**Principle**: reproducibility requires **read-only** raw data, with every result regenerable from them. The table `meta.csv` records what each file is (sample, edge, transmission or fluorescence, which reference calibrates it, whether it is used); every later step follows it.

**Operation**:
1. **Project** → “Open / create project” → **📁 Browse…** (an empty folder) → **Create project**.
2. **Register data**: enter a batch name (e.g. `2026-11-05_Ir`), drag in the files of that beamtime and click **Upload**. **Include the metal foil or powder measured in the same session** (the reference).
3. Click **Scan data/raw and register new files** and check the table:
   - `sample`: rows with the same name are scans of one sample and will be merged;
   - `role`: `reference` for references, `standard` for standards of known structure, `sample` for unknowns;
   - `use`: `0` for unused scans, with the reason in `note`.
4. Click **Save meta.csv**, then **2 Check → Run check** until there are no errors.

**Right when**: every sample has a non-empty `ref_file` and the check reports no errors.

---

## 2. Quality check: what can these data answer?

**Principle**: judge data quality before fitting. Bad data give equally “nice-looking” numbers that mean nothing. Common problems:
- **Glitches**: multiple diffraction in the monochromator crystal at certain energies, or sudden beam drops (I0 dips), create spikes in μ(E). In k-space they become sharp spikes that contaminate the whole R-space after the Fourier transform.
- **Noise**: EXAFS oscillations decay as $e^{-2k^2\sigma^2}$ and are eventually buried in noise at high k. Noise sets the usable **upper k limit**.
- **Edge step**: in transmission, Δμt ≈ 0.2–1 is ideal. Too small gives poor signal-to-noise; a total μt that is too large (> 3) causes non-linearity and lower amplitudes.
- **Fluorescence self-absorption**: concentrated samples measured in fluorescence have damped amplitudes and white lines (by up to ~25% in practice). Fluorescence and transmission **amplitudes cannot be compared directly**.
- **Interfering edges**: if another element (or the L₂ edge of the same element) lies inside the scan range, the k range must stop before it.

**Operation**: **Calibrate & process → ① Quality check**, or the **Quality check** page.

**Columns to look at**:
- `glitch_E`: glitch positions;
- `i0_drops`: beam drops;
- `edge_step_mu`: edge step;
- `k_snr3`: k where the signal falls to 3× noise — a guide for kmax;
- `self_abs_risk`: fluorescence self-absorption risk.

Also check the k limit set by interfering edges in **χ(k) & FT → k-range check**.

**Right when**: you know how far in k each spectrum is usable, and scans with glitches or beam drops are excluded (`use=0`) or deglitched.

---

## 3. Energy calibration

**Principle**: the monochromator angle–energy relation drifts by tenths of an eV to a few eV between beamtimes and even within one.
The edge position of a metal foil is a known constant (table value $E_{\text{table}}$, from xraydb). The reference edge $E_{0,\text{meas}}$ is measured (**maximum of the first derivative**),
the correction is $\Delta E = E_{\text{table}} - E_{0,\text{meas}}$, and **the same** ΔE is applied to **all spectra measured in that session**.

Why not calibrate each sample on its own? Because the sample's edge position carries chemical information (higher oxidation states shift the edge to higher energy). “Calibrating” every sample to the table value would erase it.

**Operation**: **Calibrate & process → ② Calibrate with references**. Results appear on the **Energy calibration** page, one ΔE per reference.

**Right when**: ΔE is within a few eV, and several references from the same beamtime give similar ΔE.

---

## 4. Normalization

**Principle**: the absolute μ(E) depends on sample thickness, concentration and detector gain and cannot be compared between samples. Normalization scales spectra to “pre-edge = 0, edge step = 1”:
1. fit a line to the pre-edge region (e.g. E₀−150 to E₀−30 eV), representing absorption by other elements and other shells, and subtract it;
2. fit a quadratic polynomial to the post-edge region (e.g. E₀+100 eV to the end); its value at E₀ is the **edge step**;
3. divide by the edge step.

**E₀** is the maximum of the first derivative, used consistently across the project.

Only after normalization can XANES of different samples and modes be compared.

**Operation**: parameters are in **Calibrate & process → Processing parameters** (one set per edge, shared by all samples of that edge). View them on **Normalization**, tab “μ(E) + pre/post-edge”.

**Right when**: the pre-edge line follows the pre-edge data and the post-edge curve passes through the middle of the oscillations without systematic deviation; after normalization the post-edge oscillates around 1.
**Use one parameter set for all samples of an edge** — never tune one sample to make it “look nicer”.

---

## 5. Background removal: χ(k)

**Principle**: the EXAFS signal is defined as

$$\chi(E)=\frac{\mu(E)-\mu_0(E)}{\Delta\mu_0(E_0)}$$

where $\mu_0(E)$ is the smooth absorption of an “isolated atom”. It cannot be measured and is approximated by a smooth spline.

Larch's AUTOBK uses **rbkg** to control how flexible the background is: the spline fits the low-frequency components with R < rbkg while leaving the structural signal at R > rbkg untouched.
- rbkg is typically about half the first-shell FT peak position; **1.0 Å** is common;
- too large an rbkg lets the spline eat the first shell (amplitude drops);
- too small leaves background in the low-R region (spurious peaks below 1 Å).

Energy is then converted to $k=\sqrt{0.2625\,(E-E_0)}$. Because the oscillations decay at high k, they are usually multiplied by $k^2$ or $k^3$ for viewing and fitting.

**Operation**: **Calibrate & process → ③ Process all samples**. To look at the spectra, load samples on **Load spectra** (**Load samples**), then use the “χ(k)” and “Background μ0(E)” tabs of **χ(k) & FT**.

**Right when**: $k^2\chi(k)$ oscillates around 0 without overall tilt or slow undulations; where noise starts to dominate at high k is your candidate kmax.

---

## 6. Fourier transform: from χ(k) to χ(R)

**Principle**: χ(k) is a sum of sine waves, one per shell, with frequency $2R_j$. The Fourier transform separates them by distance, giving a “radial-distribution-like” $|\chi(R)|$.
- **k range (kmin–kmax)**: kmin usually 2–3 Å⁻¹ to avoid the XANES region; kmax set by noise and interfering edges.
- **Window** (Hanning, taper width dk): brings the data smoothly to zero at both ends, reducing truncation side-lobes.
- **Resolution**: two shells can only be separated if their distance difference exceeds $\Delta R \approx \pi/(2\Delta k)$; e.g. for k = 3–12, ΔR ≈ 0.17 Å. **Resolution depends only on Δk.**
- **Peak position ≠ bond length**: each scatterer has a phase shift δ(k), so $|\chi(R)|$ peaks appear **~0.3–0.5 Å shorter** than the true distance (the software labels the R axis “not phase-corrected”). True bond lengths come only from fitting.
- **One peak ≠ one shell**: a peak can come from noise, background residue, window side-lobes or multiple scattering.

**Operation**: on **χ(k) & FT**, tab “|χ(R)| / Re”, look at both $|\chi(R)|$ and the real part Re χ(R), with k-weights 1, 2 and 3.
Light scatterers (O) are stronger at low k, heavy ones (Ir, Ta) at high k, so the relative peak heights change with k-weight — itself a clue to the scatterer type.
If needed, **Wavelet transform** shows k and R together: heavy atoms have their intensity centre at higher k.

**Right when**: kmin and kmax are chosen and recorded, and samples of one edge use the same k range.

---

## 7. How many parameters can be fitted: independent points N_idp

**Principle**: the information content of the data is limited (Nyquist theorem):

$$N_{\text{idp}}=\frac{2\,\Delta k\,\Delta R}{\pi}$$

where Δk is the k range and ΔR the R fitting window. Example: k = 3–12.5, R = 1.0–2.5 Å gives N_idp = 2×9.5×1.5/π ≈ 9.1.

**Rule**: variables ≤ N_idp/2 (at most N_idp − 3). With more parameters than information, any model “fits well” and the result means nothing.

**Operation**: after setting the ranges on **EXAFS fitting**, the page shows N_idp and the variable limit, with a yellow warning when it is exceeded.

---

## 8. FEFF: scattering paths from a structure

**Principle**: $f(k)$, $\delta(k)$ and $\lambda(k)$ in the EXAFS equation cannot be obtained from the data; they are calculated by FEFF with multiple-scattering theory, starting from a **structural model**.
FEFF reads atomic coordinates and lists all **paths** in which the photoelectron leaves the absorber, scatters off one or more atoms and returns:
- **single-scattering paths**: absorber → neighbour → back. Path length = 2R; degeneracy = number of atoms at that distance.
- **multiple-scattering paths**: via two or more atoms, e.g. collinear M–O–M. These can be strong in outer shells.

The FEFF R is a **starting point**; ΔR is allowed to adjust slightly in the fit, and the coordination number can be fixed to the degeneracy or fitted.
The structure need not be identical to the sample — a similar local environment is enough, e.g. Ta–O paths from KTaO₃ for the first shell of amorphous TaOx.

**Operation**: **FEFF paths**:
1. Structure source **Built-in structure** → `IrO2` (for your own structures, put CIFs in **FEFF paths**);
2. absorber `Ir`, edge `L3`, RMAX 6 Å;
3. click **Run FEFF6L**.

**Right when**: the first two IrO₂ paths are Ir–O: 2 at 1.958 Å and 4 at 1.996 Å, consistent with the rutile structure.

---

## 9. Determine S0² with a standard

**Principle**: S0² and the coordination number N **multiply** each other in the equation and cannot be separated from one data set.
The solution is to fit S0² on a **standard of known structure** (known N), then **fix** this value for unknown samples so that N can be fitted.
S0² depends mainly on the absorbing element and edge, little on the chemical environment, so it is transferable within the same element and edge —
provided measurements are comparable: both transmission, with suitable thickness.

**Operation (IrO₂ example)**: **EXAFS fitting**:
1. **Data**: IrO₂; **FEFF folders**: the `IrO2_IrL3` calculation.
2. **Fit range**: kmin 3, kmax 12.5, dk 1, k-weights **1, 2, 3 together**, Rmin 1.0, Rmax 2.5, space `r`.
3. **Paths**: tick both Ir–O paths. Keep `N` at the FEFF degeneracies (2 and 4, fixed at the structural values).
   Put `dr1` in `deltar` and `ss1` in `sigma2` for both: the two distances are close, so they are treated as one shell sharing parameters — fewer variables.
4. **Parameters**: tick `vary` for `s02`, `e0`, `dr1`, `ss1`. That is 4 variables with N_idp ≈ 9.1, within N_idp/2.
5. Click **Fit**.

Actual result in the authors' project: **S0² ≈ 0.82, ΔE₀ ≈ 8.9 eV** (Ir L₃, transmission).
Enter the S0² in **Calibrate & process → Processing parameters → S0²** and click **Save parameters**.

**Why k¹, k² and k³ together**: different weights emphasize low k (light atoms, ΔE₀) and high k (σ², heavy atoms) differently; fitting them together reduces the S0²–σ² and ΔE₀–ΔR correlations.

---

## 10. Fitting unknown samples

**Principle**: go from simple to complex, adding shells one at a time.

1. **First shell** (nearest neighbours, e.g. M–O): S0² fixed to the standard's value; N, ΔR, σ², ΔE₀ free — 4 variables.
2. Look at the residual: if a second peak (e.g. M–M) is not reproduced, add a shell. It usually adds N, ΔR, σ² (3 variables); ΔE₀ is normally shared.
3. Check N_idp after every added shell and run the F-test (section 11).

**Operation**:
1. **EXAFS fitting**: choose the sample data and the matching FEFF folder.
2. **Paths**: to fit a coordination number, replace the `N` value with a parameter name such as `n1`. Paths of one shell sharing `n1` share it; if one path's N must be a fixed multiple of another, write e.g. `n1*2`.
3. **Parameters**:
   - **Fix S0²**: untick `vary` in the `s02` row and set `value` to the standard's value, e.g. 0.82.
   - **Share / constrain**: text in the `expr` column makes the parameter a function of others instead of an independent variable.
     - Example 1: set `expr` of `ss2` to `ss1` — both shells have the same σ².
     - Example 2: for the collinear multiple-scattering path M–O–M, use `dr2` for `deltar` and `ss2` for `sigma2`, tying it to the corresponding M–M single-scattering path.
   - **min / max**: physical bounds, e.g. σ² ≥ 0.
4. Click **Fit**; when satisfied click **Save results to output/fits/exafs_fits.csv**. The model is also stored in `models/` for one-click reruns.

**Judging the fit**:

| Indicator | Meaning | Guide |
|---|---|---|
| R-factor | relative misfit between fit and data | < 0.02 very good, < 0.05 acceptable |
| reduced χ² | depends on the noise estimate | compare **models on the same data**, not absolute values |
| ΔE₀ | energy-origin difference | \|ΔE₀\| < 10 eV; otherwise check E₀ or the model |
| σ² | disorder | positive; first shell typically 0.002–0.015 Å² |
| S0² (standard) | | 0.6–1.1 |
| N | coordination number | uncertainty often ±10–25%; always report the error |
| errors | from the covariance matrix (scaled by reduced χ²) | an error larger than the value means the parameter is not determined |

**Also look at the plots**: both $|\chi(R)|$ and **Re χ(R)** must match — matching the magnitude alone is not enough; in k-space the fit must be in phase with the data. The software warns for |ΔE₀| > 10 eV, σ² < 0 and S0² out of range.

**Parameter correlations**: ΔE₀ and ΔR are strongly correlated (both change the phase), as are N and σ² (both change the amplitude). The correlation coefficients are listed at the end of the full fit report (feffit_report); be careful above 0.9.
Therefore:
- be cautious with bond-length differences < 0.02 Å;
- compare N between samples using the same k range and the same S0².

**Robustness**: below the fit result, **Run robustness check** repeats the fit with slightly different k and R ranges and k-weights. A parameter that changes more than its error is “unstable” — report it as a range or simplify the model.

---

## 11. Add a shell or not: the F-test

**Principle**: adding parameters always lowers the R-factor, even when the new shell only fits noise. The Hamilton F-test checks whether the improvement exceeds what the extra parameters alone would give.

**Operation**: **Fit history** → choose the “simpler model” and the “more complex model” (which must contain the simpler one plus extra parameters) → **Compare**.

**Interpretation**:
- **p < 0.05**: the new shell is significant and can be reported as “included and significant”;
- **p ≥ 0.05**: the shell cannot be called “observed” — only “not excluded by the data”.

Light scatterers (O, K) next to heavy-atom shells are particularly hard to determine and need independent support: wavelet transform, different k-weights or other techniques (XRD, XPS, composition analysis).

---

## 12. XANES linear combination fitting (LCF, optional)

**Principle**: if a sample is a mixture of known phases, its normalized XANES is approximately a weighted sum of the standards' spectra, the weights being the phase fractions (per absorbing atom).

**Operation**: **LCF**: choose the sample and end members (**measured standards only**), the energy range (commonly E₀−20 to E₀+60 eV) and the space (normalized μ), then click **LCF**. Single-standard fits are shown for comparison.

**Interpretation**:
- the weights should sum to about 1;
- the multi-standard fit should have a clearly lower R-factor than single-standard fits;
- a missing phase biases the result systematically.

For edge positions, valence calibration and pre-edge peaks see **XANES quantification** in the GUI guide.

---

## 13. Report export

**Operation**: **Report export** → **Build report** produces:
- the Excel file: samples, calibration, quality check, processing parameters, fit overview per model and per-path parameters, LCF;
- the HTML report: tables plus all figures, printable to PDF.

For a paper, report:
- k range, R range, k-weights, window;
- N_idp and number of variables;
- S0² and its source (which standard);
- for every shell N, R, σ², plus ΔE₀ and the R-factor, all with errors.

**Methods export** drafts this text from the project files; **Figure export** produces publication-style figures.

---

## 14. Writing conclusions: keep three kinds of statements apart

| Type | Example | Basis |
|---|---|---|
| **Measured** | “the sample's white line is lower than that of IrO₂”; “the FT peak at 2.8–3.5 Å weakens with time” | directly visible in the data (state “not phase-corrected”) |
| **Fitted** | “Ir–O coordination number 5.6 ± 0.6, bond length 1.98 ± 0.01 Å” (illustrative numbers) | depends on the model, S0² and k range |
| **Speculative** | “amorphous IrOx forms at the surface” | needs several indicators together or other experiments |

---

## 15. Common beginner mistakes

1. Fitting without looking at χ(k) and the noise → do sections 2 and 5 first.
2. Different normalization or background parameters for different samples → one set per edge.
3. Taking FT peak positions as bond lengths → peaks are not phase-corrected; use fitted distances.
4. Letting S0² and N vary together → they are fully correlated; determine S0² on a standard first.
5. More variables than N_idp/2 → fewer shells, or share σ² and ΔE₀.
6. Looking at |χ(R)| but not Re χ(R) → a fit with the wrong phase can still match the magnitude.
7. Comparing fluorescence and transmission amplitudes directly → self-absorption damps amplitudes.
8. Claiming outer shells without an F-test → section 11.
9. Accepting |ΔE₀| > 10 eV → check E₀, calibration and the model.
10. Relying on this software alone → **cross-check key results with Athena / Artemis.**

---

## Further reading

- M. Newville, *Fundamentals of XAFS* (introductory notes in the Larch documentation)
- S. Calvin, *XAFS for Everyone*, CRC Press (2013)
- G. Bunker, *Introduction to XAFS*, Cambridge University Press (2010)
- B. Ravel & M. Newville, Athena/Artemis documentation (Demeter)
