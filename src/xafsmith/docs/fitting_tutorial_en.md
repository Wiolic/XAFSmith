# Beginner EXAFS fitting tutorial

This tutorial is for people doing **their first EXAFS fit**, from raw data to written conclusions. No programming and no commands are needed.

**Every chapter has three parts**

| Part | Content |
|---|---|
| **Principle** | Why the step is needed |
| **Operation** | Where to click in the software |
| **Check** | How to tell it was done right |

**Running example**: IrO₂ (Ir L₃ edge, transmission). Its structure is known (rutile, 6 O around each Ir), which makes it suitable for determining S0². The IrO₂ numbers come from an actual fit in the author's project; yours will differ.

Where each button is and how it works is in the **GUI guide**; this tutorial focuses on principles and criteria.

**Contents**

| Part | Chapters |
|---|---|
| 1. The big picture | 0.1 What XAFS measures　0.2 The EXAFS equation　0.3 The workflow |
| 2. Prepare the data | 1 Project and registration　2 Quality check　3 Energy calibration　4 Normalization　5 Background and χ(k)　6 Fourier transform |
| 3. Fitting | 7 How many parameters　8 FEFF paths　9 S0² from a standard　10 Fitting samples　11 Is the fit good?　12 Robustness and F-test |
| 4. Other analyses and reporting | 13 LCF　14 Export and conclusions　15 Common beginner mistakes |

---

## 1. The big picture

### 0.1　What XAFS measures

When the X-ray energy crosses an absorption edge of an element (e.g. Ir L₃ ≈ 11215 eV), the absorption coefficient μ(E) jumps: a core electron is ejected as a **photoelectron**. The spectrum near the edge has two parts:

| Region | Energy range | Tells you | What to look at |
|---|---|---|---|
| **XANES** | Pre-edge to about 50 eV above | Oxidation state, coordination symmetry | Edge position, white line, pre-edge peaks |
| **EXAFS** | About 50–1000 eV above | Type, number, distance and disorder of neighbours | Frequency, amplitude, shape of the oscillations |

Where the oscillations come from: the outgoing photoelectron wave is scattered back by neighbouring atoms and interferes with itself, so μ(E) oscillates slightly.

- **frequency** ← **distance R** to the neighbours;
- **amplitude** ← **number N** and **disorder σ²** of the neighbours;
- **shape** (how amplitude and phase change with k) ← **which element** the neighbours are.

So EXAFS fitting answers: **within a few Å of the absorber, how many atoms of which kind, how far, and how disordered.**

### 0.2　The EXAFS equation

This is the equation the fit uses:

$$\chi(k)=\sum_j S_0^2\,N_j\,\frac{|f_j(k)|}{k R_j^2}\,e^{-2k^2\sigma_j^2}\,e^{-2R_j/\lambda(k)}\,\sin\left[2kR_j+\delta_j(k)\right]$$

| Symbol | Meaning | Comes from |
|---|---|---|
| $k$ | Photoelectron wave number, $k=\sqrt{0.2625\,(E-E_0)}$ in Å⁻¹ (E in eV) | Converted from the data |
| $N_j$ | Coordination number of path (shell) j | **Fitted** or fixed |
| $R_j$ | Distance, $R_j = R_{\mathrm{FEFF}} + \Delta R$ | **ΔR fitted** |
| $\sigma_j^2$ | Variance of the distance distribution (thermal + structural), the Debye–Waller factor | **Fitted** |
| $S_0^2$ | Passive-electron amplitude reduction, usually 0.7–1.0 | **From a standard**, fixed for samples |
| $\Delta E_0$ | Energy-zero difference between theory and experiment | **Fitted**, usually shared by the paths of one sample |
| $f_j(k)$, $\delta_j(k)$, $\lambda(k)$ | Scattering amplitude, phase shift, mean free path | Computed by **FEFF** from the structure |

In one sentence: **FEFF says what the scatterers look like; the data determine N, ΔR, σ², ΔE₀ and S0².**

Two terms explain much of what follows:

- $e^{-2k^2\sigma^2}$: the oscillations decay with k, faster for larger σ². At high k the signal sinks into the noise, which sets the usable k range.
- $S_0^2 N_j$: the two multiply and cannot be separated from one data set. S0² must first be determined on a standard of known N (chapter 9).

### 0.3　The workflow

| Step | Page | Chapter |
|---|---|---|
| Register raw data | Register data | 1 |
| Quality check, energy calibration, normalization, background, Fourier transform | Calibrate & process (one click); Load & check, Normalization, χ(k) & FT (to inspect) | 2–6 |
| Compute scattering paths | FEFF paths | 8 |
| S0² from a standard | EXAFS fitting | 9 |
| Fit samples, judge the fit, test significance | EXAFS fitting, Fit history | 10–12 |
| Export and conclusions | Report, Figure and Methods export | 14 |

---

## 2. Prepare the data

### 1　Project and registration

**Principle**

Raw data are **read-only**, and every result can be regenerated from them, which makes the analysis reproducible. The register `meta.csv` records what each file is: sample, edge, transmission or fluorescence, which reference calibrates it, whether it is used. Every later step follows it.

**Operation**

1. **Open / new project** at the top left → **Browse…** to an empty folder → **Create project**.
2. On **Register data**:
   - enter a batch name, e.g. `2026-11-05_Ir`;
   - click **Choose files, copy to batch and register…** and select all files of the beamtime. **Include the metal foil or powder measured in the same beamtime** (the reference).
3. Check the register:

| Column | What to enter |
|---|---|
| sample | Rows with the same name are scans of one sample and are merged |
| role | `reference` for the reference, `standard` for standards of known structure, `sample` for unknowns |
| use | `0` for scans you do not use, with the reason in note |

4. Click **Save meta.csv**, then **Run check** until there are no errors.

**Check**: every sample has a non-empty `ref_file`; the check reports no errors.

### 2　Quality check: what can these data answer?

**Principle**

Judge the data before fitting. Bad data give equally “nice” numbers that mean nothing. Common problems:

| Problem | Cause | Consequence |
|---|---|---|
| Glitches | Multiple diffraction in the monochromator, or a beam drop (I0 falls) | Spikes in k space that contaminate all of R space after the FT |
| Noise | Oscillations decay as $e^{-2k^2\sigma^2}$ and sink into the noise at high k | Sets the usable **kmax** |
| Wrong edge step | Transmission sample too thin or too thick | Small Δμt gives poor signal-to-noise; total μt > 3 is non-linear and damps the amplitude |
| Fluorescence self-absorption | Concentrated samples measured in fluorescence | White line and amplitude damped (about 25% observed); not comparable with transmission |
| Interfering edges | Another element (or the L₂ edge) inside the scan | The k range must stop before it |

**Operation**

1. **Calibrate & process → ① Quality check** (or the **Quality check** tab of **Load & check**).
2. Look at:

| Column | Meaning |
|---|---|
| glitch_E | Glitch positions |
| i0_drops | Beam drops |
| edge_step_mu | Edge step |
| k_snr3 | k where the signal falls to 3× the noise — a guide for kmax |
| self_abs_risk | Fluorescence self-absorption risk |

3. On **χ(k) & FT → k-range check**, read the kmax allowed by interfering edges.
4. Glitches: **Deglitch** at the bottom of the Quality check tab, or set `use = 0` for that scan.

**Check**: you know how far in k each spectrum is usable; scans with glitches or beam drops are removed or deglitched.

### 3　Energy calibration

**Principle**

The angle–energy relation of the monochromator drifts by tenths of an eV to a few eV. The edge position of a metal foil is a known constant (table value, from xraydb). So:

1. measure the reference edge $E_{0,\mathrm{meas}}$ (maximum of the first derivative);
2. the correction is $\Delta E = E_{\mathrm{table}} - E_{0,\mathrm{meas}}$;
3. apply the **same** ΔE to **every spectrum of that beamtime**.

Why not calibrate each sample on its own? Its edge position carries chemical information (higher oxidation states shift it up). “Calibrating” every sample to the table value would erase it.

**Operation**: **Calibrate & process → ② Calibrate with references**. See the result on the **Energy calibration** tab of **Load & check**, one ΔE per reference.

**Check**: ΔE is usually within a few eV; references from one beamtime give similar ΔE.

### 4　Normalization

**Principle**

The raw μ(E) depends on thickness, concentration and detector gain, so spectra cannot be compared directly. Normalization scales them to “pre-edge = 0, edge step = 1”:

1. fit a line to the pre-edge region (e.g. E₀−150 to E₀−30 eV) and subtract it;
2. fit a quadratic to the post-edge region (e.g. E₀+100 eV to the end); its value at E₀ is the **edge step**;
3. divide by the edge step.

E₀ is the maximum of the first derivative, the same definition for the whole project.

**Operation**: parameters are under **Calibrate & process → Processing parameters** (one set per edge, shared by all its samples); inspect them on the “μ(E) with pre- / post-edge lines” tab of **Normalization**.

**Check**

- the pre-edge line follows the pre-edge data, the post-edge line passes through the middle of the data;
- after normalization the post-edge region oscillates around 1;
- **use one parameter set for all samples of an edge**; never tune one sample to look nicer.

### 5　Background and χ(k)

**Principle**

The EXAFS signal is defined as

$$\chi(E)=\frac{\mu(E)-\mu_0(E)}{\Delta\mu_0(E_0)}$$

$\mu_0(E)$ is the smooth absorption of an “isolated atom”. It cannot be measured, only approximated by a smooth spline. Larch's AUTOBK controls how “soft” the background is with **rbkg**:

| rbkg | Result |
|---|---|
| About half the first-shell FT peak position, typically **1.0 Å** | Suitable |
| Too large | The spline eats the first shell; amplitude drops |
| Too small | Background left at low R; false peaks below 1 Å |

Energy is then converted to $k=\sqrt{0.2625\,(E-E_0)}$. The oscillations decay at high k, so they are usually multiplied by $k^2$ or $k^3$.

**Operation**

1. **Calibrate & process → ③ Process all samples**.
2. **Load & check → Load spectra**: tick samples and click **Load**.
3. On **χ(k) & FT**, look at the “χ(k)” and “Background μ0(E)” tabs.

**Check**: $k^2\chi(k)$ oscillates around 0 without a slope or slow undulation; where the noise starts to dominate at high k is a candidate kmax.

### 6　Fourier transform: from χ(k) to χ(R)

**Principle**

χ(k) is a sum of sine waves, one frequency $2R_j$ per shell. The Fourier transform separates them by distance into a radial-distribution-like |χ(R)|.

| Point | Explanation |
|---|---|
| k range | kmin usually 2–3 Å⁻¹ (away from XANES); kmax set by noise and interfering edges |
| Window | Hanning with width dk: the data fall smoothly to 0 at both ends, fewer truncation ripples |
| Resolution | Two shells separate only if they differ by more than $\Delta R \approx \pi/(2\Delta k)$; about 0.17 Å for k = 3–12. **Resolution depends only on Δk** |
| Peak ≠ bond length | Scattering phase shifts put the peaks **0.3–0.5 Å below** the true distance (R axis “not phase-corrected”); distances come only from the fit |
| One peak ≠ one shell | A peak may come from noise, residual background, window ripples or multiple scattering |

**Operation**

1. On **χ(k) & FT**, look at |χ(R)| and the real part Re χ(R) on the “|χ(R)| / Re” tab.
2. Look at k-weights 1, 2 and 3: light scatterers (O) are stronger at low k, heavy ones (Ir, Ta) at high k, so relative peak heights change with the weight — itself a clue to the scatterer.
3. If needed, use **Wavelet transform** to see k and R together: heavy atoms peak at higher k; two spectra can be compared side by side.

**Check**: kmin and kmax are chosen and recorded; samples of one edge use the same k range.

---

## 3. Fitting

### 7　How many parameters: independent points N_idp

**Principle**

The information a data set can determine is limited (Nyquist):

$$N_{\mathrm{idp}}=\frac{2\,\Delta k\,\Delta R}{\pi}$$

Δk is the k range and ΔR the R window of the fit.

**Example**: k = 3–12.5 Å⁻¹, R = 1.0–2.5 Å gives N_idp = 2 × 9.5 × 1.5 / π ≈ 9.1.

**Rule**: variables ≤ N_idp/2 (at most N_idp − 3). With more parameters than information, any model fits “very well”, and the result means nothing.

**Operation**: after setting the fit range in the left column of **EXAFS fitting**, N_idp and the variable limit are shown; the variable count turns orange above the limit.

### 8　FEFF: scattering paths from a structure

**Principle**

$f(k)$, $\delta(k)$ and $\lambda(k)$ cannot be taken from the data; they are computed with FEFF (multiple-scattering theory) from a **structural model**. FEFF lists every **path** the photoelectron can take from the absorber back to it:

| Path | Explanation |
|---|---|
| Single scattering | Absorber → neighbour → back. Path length = 2R, degeneracy = number of atoms at that distance |
| Multiple scattering | Via two or more atoms, e.g. collinear M–O–M; can be strong in outer shells |

The FEFF R is a **starting point**: the fit adjusts it by a small ΔR; N may stay at the degeneracy or be fitted. The structure need not match the sample exactly, only the local environment — e.g. Ta–O paths of KTaO₃ for the first shell of amorphous TaOx.

**Operation** (**FEFF paths** page)

1. Structure source **Built-in** → `IrO2` (your own: choose the structures/ folder and **Add structure files…**).
2. Absorber `Ir`, edge `L3`, RMAX 6 Å.
3. Start with **FEFF6L** and click **Run FEFF**.

**Check**: the first two IrO₂ paths are Ir–O: 2 at 1.958 Å and 4 at 1.996 Å, as in rutile.

> FEFF8L (self-consistent) usually gives ΔE₀ closer to 0, but its zero differs from FEFF6L. Use one FEFF version for a whole series.

### 9　S0² from a standard

**Principle**

S0² and N multiply and cannot be separated from one data set. So:

1. fit S0² on a **standard of known structure** (N known);
2. **fix** it for the unknowns and fit N.

S0² depends mainly on the absorbing element and edge, hardly on the chemistry, so one value serves an element and edge — provided the measurements are comparable (both transmission, suitable thickness).

**Operation** (**EXAFS fitting**, IrO₂)

In the left column:

1. **Data and FEFF**: data IrO₂, FEFF folder `IrO2_IrL3` from the previous chapter.
2. **Fit range**: kmin 3, kmax 12.5, dk 1, k-weights **1, 2 and 3 together**, Rmin 1.0, Rmax 2.5, fit space `r`.
3. **Paths**: tick the two Ir–O paths.
   - keep `N` at the FEFF degeneracy (2 and 4, fixed to the structure);
   - write `dr1` in `deltar` and `ss1` in `sigma2` for both: the distances are close, so they share parameters as “one shell”, saving variables.
4. **Parameters**: tick vary for `s02`, `e0`, `dr1`, `ss1`. Four variables, N_idp ≈ 9.1, so ≤ N_idp/2 holds.
5. Click **Fit** at the bottom left (or Ctrl+Enter); the result appears on the right.

Result in the author's project: **S0² ≈ 0.82, ΔE₀ ≈ 8.9 eV** (Ir L₃, transmission).

6. Enter S0² under **Calibrate & process → Processing parameters → S0²** and **Save parameters**; on EXAFS fitting click **Save result**.

**Why k¹, k² and k³ together**: the weights differ in sensitivity to low k (light atoms, ΔE₀) and high k (σ², heavy atoms). Fitting them together weakens the S0²–σ² and ΔE₀–ΔR correlations.

**Tip while tuning**: after a fit, **Use fitted values as start** on the right copies the result into the parameter table as the next start values; change parameters and click **Fit** again — no scrolling up and down.

### 10　Fitting samples

**Principle**: from simple to complex, one shell at a time.

1. **First shell** (nearest neighbours, e.g. M–O): S0² fixed at the standard's value; N, ΔR, σ², ΔE₀ free — four variables.
2. Look at the residual: if a second peak (e.g. M–M) is not fitted, add a shell. A new shell usually adds N, ΔR and σ² (three variables); ΔE₀ is usually shared.
3. With every shell, check N_idp and run the F-test (chapter 12).

**Operation**

1. Left column of **EXAFS fitting**: choose the sample data and the matching FEFF folder.
2. **Paths**: for paths whose coordination number is fitted, write a parameter name in `N`, e.g. `n1`.
   - all paths of one shell with `n1` = shared;
   - a path whose N is a fixed multiple of another: `n1*2`.
3. **Parameters**:

| To do | Enter |
|---|---|
| Fix S0² | untick vary for `s02`, value = the standard's value (e.g. 0.82) |
| Same σ² for two shells | expr of `ss2` = `ss1` |
| Tie multiple scattering to single scattering | for the collinear M–O–M path write `dr2` in `deltar` and `ss2` in `sigma2`, as for the matching M–M path |
| Physical limits | min / max, e.g. σ² ≥ 0 |

4. Click **Fit**; when satisfied, **Save result**: the result goes to `output/fits/exafs_fits.csv` and the model to `models/` for one-click reruns.
5. A series (time, potential): **Run a saved model** at the top of the left column → choose the model → select several samples → **Run**.

### 11　Is the fit good?

**Principle**: a curve that “looks close” is not enough; numbers, plots and physical sense must all agree.

**Operation**: read the **Quality** tab on the right (automatic ✓ / ⚠ per point) and **Before you fit · what is a good fit** at the top right.

**Numbers**

| Quantity | Meaning | Reference |
|---|---|---|
| R-factor | Relative misfit | < 0.02 very good; 0.02–0.05 acceptable for a first shell |
| Residual / noise | On the Diagnosis tab | ≈ 1–2 = data limit; well above 2 = systematic residual |
| χ²_ν | Reduced chi-square, depends on the noise estimate | Only for comparing models on **the same data** |
| ΔE₀ | Energy-zero difference | \|ΔE₀\| ≤ 10 eV; otherwise check E₀ or the model |
| σ² | Disorder | Positive; first shells at room temperature mostly 0.002–0.010 Å² |
| S0² (standard) | | 0.6–1.1 |
| N | Coordination number | Errors of ±10–25% are common; report them |
| Errors | From the covariance matrix (scaled by χ²_ν) | Error larger than the value = parameter not determined |

**Plots**

- both |χ(R)| and **Re χ(R)** must match; a fit with the wrong phase can still match the magnitude;
- in k space the fit must be in phase with the data, and the residual not concentrated in one region.

**Correlations**

- ΔE₀ with ΔR (both shift the phase), N with σ² (both change the amplitude);
- correlations are listed at the end of the Full report tab; report pairs with |r| > 0.9;
- so be careful with distance differences below 0.02 Å, and compare N between samples only with the same k range and S0².

### 12　Robustness and F-test

**Robustness**

- **Principle**: a sound conclusion must not depend on one particular fit range.
- **Operation**: **Robustness** tab on the right → **Run robustness check**: kmin ±0.5, kmax ±1, Rmax ±0.2 Å and k¹ / k² / k³ alone are fitted in turn.
- **Reading**: parameters that move more than their error are marked unstable; report a range or simplify the model.

**F-test: add a shell or not**

- **Principle**: extra parameters always lower the R-factor, even if they fit noise. The Hamilton F-test asks whether the drop exceeds what the extra parameters would give anyway.
- **Operation**: **Fit history** → choose the “simpler” and the “more complex” model (the latter adds parameters to the former) → **Compare**.
- **Reading**:

| p | Conclusion |
|---|---|
| p < 0.05 | The new shell is significant: “the fit includes this shell, and it is significant” |
| p ≥ 0.05 | It is not “observed”; at most “the data do not exclude it” |

Light scatterers (O, K) next to heavy-element shells are especially hard; support them independently with wavelets, different k-weights or other methods (XRD, XPS, composition).

---

## 4. Other analyses and reporting

### 13　XANES linear combination fitting (LCF, optional)

**Principle**: if a sample is a mixture of known phases, its normalized XANES is approximately a weighted sum of the standards; the weights are the phase fractions (per absorbing atom).

**Operation**: on **LCF**:

1. choose the sample and the end-members (**measured standards only**);
2. energy range typically E₀−20 to E₀+60 eV, space normalized μ;
3. click **LCF**. Single-standard fits are given for comparison.

**Check**

- weights sum to about 1;
- the multi-standard R-factor is clearly lower than the single-standard ones;
- a missing phase biases the result systematically.

Edge positions, valence calibration and pre-edge fitting are under **XANES quantification** in the GUI guide.

### 14　Export and conclusions

**Export**

| Need | Page |
|---|---|
| All results: Excel workbook + HTML report with figures | **Report export** → Build report |
| Publication figures, or Origin files (.opju) directly | **Figure export** |
| Methods paragraph (English and Chinese), fit-parameter table for the SI | **Methods export** |

**What to report in a paper**

- k range, R range, k-weights, window;
- N_idp and the number of variables;
- S0² and its source (which standard);
- N, R, σ² per shell, ΔE₀ and R-factor, all with errors.

**Keep three kinds of statements apart**

| Kind | Example | Basis |
|---|---|---|
| **Measured** | “The white line is weaker than in IrO₂”; “the FT peak at 2.8–3.5 Å decreases with time” | Directly visible (state “not phase-corrected”) |
| **Fitted** | “Ir–O coordination 5.6 ± 0.6 at 1.98 ± 0.01 Å” (illustrative) | Depends on the model, S0² and k range |
| **Inferred** | “An amorphous IrOx forms at the surface” | Needs several indicators or other experiments |

### 15　Common beginner mistakes

| Mistake | Instead |
|---|---|
| Fitting without looking at χ(k) and the noise | Do chapters 2 and 5 first |
| Different normalization or background parameters per sample | Use one set per edge |
| Taking FT peak positions as bond lengths | Peaks are not phase-corrected; take distances from the fit |
| Letting S0² and N both vary | They are fully correlated; get S0² from a standard |
| More variables than N_idp/2 | Fewer shells, or share σ² and ΔE₀ |
| Looking only at \|χ(R)\| | Re χ(R) must match too |
| Comparing fluorescence and transmission amplitudes directly | Self-absorption damps them; use a bridging standard |
| Claiming an outer shell without the F-test | See chapter 12 |
| Accepting ΔE₀ beyond ±10 eV | Check E₀, calibration and the model |
| Relying on this software alone | **Cross-check key results once with Athena / Artemis** |

---

## Further reading

- M. Newville, *Fundamentals of XAFS* (introductory notes in the Larch documentation)
- S. Calvin, *XAFS for Everyone*, CRC Press (2013)
- G. Bunker, *Introduction to XAFS*, Cambridge University Press (2010)
- B. Ravel & M. Newville, Athena / Artemis documentation (Demeter)
