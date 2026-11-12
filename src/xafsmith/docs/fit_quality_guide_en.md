# Improving fit quality: getting the best EXAFS fit XAFSmith (and your data) allow

> For users who can already run a fit (see the *Beginner fitting tutorial*) but whose fit does **not** match the data closely.
> Everything here is done in the GUI; page names refer to the sidebar.

---

## 0. What “perfect” should mean

A fit that matches **every wiggle** is usually **neither achievable nor desirable**:

1. **Data contain noise and systematic errors**: single scans, glitches, background removal, sample inhomogeneity. Fitting below that level means fitting noise.
2. **Real structures are distributions; the model is a few Gaussian shells.** Disordered, multiphase or nanoscale samples can only be approximated.
3. **Information is limited**: N_idp = 2ΔkΔR/π is about 15 for k 3–11 Å⁻¹ and R 1–4 Å. More parameters mean less reliable parameters.
4. **The R-factor can always be pushed down** by adding paths and freeing N and σ² — at the cost of meaningless parameters.

“As good as possible” therefore means all four of:

| Goal | How to judge | Where |
|---|---|---|
| ① Residual near the data limit | in-window residual ÷ noise ≈ 1–2, or at least comparable to a standard measured in the same session | EXAFS fitting result → **Fit diagnosis** |
| ② No removable *structure* left in the residual | no local spikes in the k residual; no single k segment or R region dominating | k / R segment tables in Fit diagnosis |
| ③ Every parameter physical and robust | σ² > 0, |ΔE0| < 10 eV, nothing at a bound; robustness check “stable” | parameter table, **Robustness check** |
| ④ Every path earns its place | F-test p < 0.05 when it is added | Fit history |

**Satisfy ③ and ④ first, then pursue ① and ②.** A “good-looking” fit with unstable parameters is worse than a robust fit with a slightly higher R-factor.

---

## 1. Always diagnose first — do not start by adding paths

After a fit on EXAFS fitting, open **“Fit diagnosis: where the residual is and why”** below the result.

### 1.1 Three numbers

| Number | Meaning | Reading |
|---|---|---|
| In-window residual RMS | RMS of \|χ(R)data − χ(R)fit\| inside the fit window | smaller is better, but compare with the next |
| White-noise estimate | \|χ(R)\| of the data at R 15–25 Å (no structural signal there) | random noise level |
| **Residual / noise** | ratio | **≈ 1–2**: at the limit, stop; **2–5**: systematic error worth checking; **> 5**: clear systematic problem |

> The white-noise estimate **underestimates** the true error (it does not see background, glitches or inhomogeneity), so a ratio > 1 is almost always found.
> A more practical yardstick: the ratio obtained with **the same model on a known standard from the same beamtime**. If the sample is comparable to the standard, the residual comes from theory and processing, not from a wrong sample model.

### 1.2 The k-space residual

Black = data, blue = residual k^w·(data − fit), magenta dotted lines = detected spikes.

| What you see | Most likely cause | Section |
|---|---|---|
| A sharp up–down feature 1–3 points wide | **leftover glitch** | 2.1 |
| The first (low-k) segment much larger | background, near-edge effects, E0, theory | 2.3, 2.4 |
| Large, saw-tooth residual at high k | noise | 2.2 |
| Smooth, regular oscillation over a whole range | missing path / wrong distance or σ² | 3 |

### 1.3 Segment tables

- **k segments**: “relative to median” > 1.5 marks a problem segment.
- **R segments**: local misfit = Σ\|Δχ(R)\|² / Σ\|χ(R)\|².
  - First shell < 0.05; outer shells 0.1–0.3 are common; > 0.3 means the model or the data need attention there.
  - **Valleys** between peaks have little data intensity, so their local misfit is naturally high — do not add paths because of it (check the “data intensity” column).
  - Misfit **outside the window** is expected; it is not fitted.

### 1.4 A glitch shows up as an evenly spaced ripple in R

A sharp spike at k₀ becomes an **oscillation with period ≈ π/k₀** across the whole R range (also outside the window).
If the R residual looks like an evenly spaced ripple (≈ 0.6 Å for k₀ ≈ 5 Å⁻¹) and \|χ(R)\| does not decay outside the window, **check for glitches before adding shells**.

---

## 2. Work through the sources — data first, model last

### 2.1 Data: glitches (most common, easiest to fix)

**Where**: Quality check → **Deglitch** at the bottom.

1. Select samples and look at μ(E) and I0/median. QC-detected glitch energies are grey dotted lines.
2. Remove only if all three hold: 1–3 points wide; **at the same energy in several samples**; **a matching dip in I0** (monochromator glitch).
3. **The range must include every point that deviates from the smooth trend**, not just the sharpest one. Glitches often appear as a high/low pair; removing only the middle leaves an up–down spike in χ(k).
4. Enter the range (e.g. `9983-9991`; several separated by semicolons) and a **reason (required)** → **Save and reload**.
5. Refit on EXAFS fitting and re-check the diagnosis: the spike hint should disappear and the k residual should be flat there.

**Don’t**: remove more than ~10 eV; remove points near the white line or pre-edge; remove a glitch from one sample but not from other samples of the same batch; remove “ugly” oscillations to lower the R-factor.

> The R-factor does **not** necessarily drop after removing a spike: most of its power lies at high R outside the window, and the fit re-converges. Judge by the flattened k residual, not by the R-factor.

### 2.2 Data: noise and k max

- **k_snr3** in the QC table is where signal-to-noise falls to 3. Do not set kmax much above the k_snr3 of the **worst sample** of a series.
- All samples of a series **must use the same k range**, otherwise σ² values are not comparable.
- The real cure for noise is **merging more scans** (same sample name in ① → merged automatically).

### 2.3 Processing: background, E0, kmin

| Symptom | What to adjust (where) | Note |
|---|---|---|
| Residual peak below 1 Å | rbkg on ⑤ (typ. 1.0; try 0.9–1.2) | same rbkg for the whole series, saved in `xafsmith.json` |
| Large low-k residual | run the **Robustness check** (kmin ±0.5) first | parameters stable within errors → keep kmin; otherwise raise kmin **for all samples** |
| |ΔE0| > 10 eV | E0 definition on ④ | one E0 definition for the whole project |
| ΔE0 very different between samples | energy calibration (③) | be careful without a simultaneous reference |

Raising kmin usually lowers the R-factor but costs N_idp and light-scatterer signal. If the robustness check shows your conclusion does not depend on kmin, there is no need to raise it; state the kmin used.

### 2.4 Theory: FEFF6L vs FEFF8L

FEFF paths → **FEFF version**: **FEFF6L** (non-self-consistent, seconds) or **FEFF8L** (self-consistent SCF potential, 1–3 min; usually better at low k and for ΔE0).

1. Compute both for the same structure (FEFF8L output folder gets `_feff8`).
2. Fit the same model with each path set on the standard and on the samples.
3. Parameters agree within errors → the conclusion is independent of the theory (itself a robustness argument); report the lower R-factor and state the FEFF version. They disagree → treat the difference as a systematic error.
4. **The ΔE0 zero changes between versions** (often by several eV). Models with a fixed e0 must re-determine it.

SCF radius: usually 4–5 Å (2–3 shells, 30–60 atoms). Make sure the structure (polymorph, site) is right — no parameter can fix a wrong structure. Compute every inequivalent site.

### 2.5 Amplitude: S0² and sample homogeneity

- S0² must come from a **known standard at the same edge** (`s02_recommended` in `xafsmith.json`) and be fixed for samples.
- If all shells are uniformly too weak while σ² looks normal, suspect inhomogeneity (pinholes, thickness variation) or fluorescence self-absorption. For medium-range order comparisons, use ratios such as outer-shell peak ÷ first-shell peak.

---

## 3. Model: when and how to add paths

Only after section 2, and only if the diagnosis still shows a **smooth, regular** residual concentrated in an R region.

### 3.1 Candidate paths
“Existing FEFF calculations” on ⑦ lists every path with its **amp_ratio**. Consider every path in the window with amp_ratio > ~10 % (and have a reason to use or omit it). Do not ignore multiple scattering (collinear M–O–M MS often exceeds single scattering). Paths on the same geometry share ΔR and σ².

### 3.2 Constrain instead of adding variables

| Constraint | Path table entry | Basis |
|---|---|---|
| isotropic expansion | `deltar = dr1*reff/r1`, or `alpha*reff` | cubic-like structures |
| geometry | e.g. perovskite ΔR(B–A) = √3·ΔR(B–O) → `dr1*sqrt(3)` | lattice geometry |
| MS σ² | collinear MS shares the single-scattering `ssT`; triangle `ss1*2` | state the rule |
| fixed N | `N = 6` | known coordination |
| fixed σ² for weak scatterers | value from the standard | N and σ² cannot both be fitted |

> **N and σ² are strongly correlated** (amplitude ∝ N·exp(−2k²σ²)). Free one, fix the other, and say so.

### 3.3 Every addition must pass an F-test
1. Fit the smaller and the larger model on EXAFS fitting (both go to Fit history).
2. Fit history → select both → **F-test**. Keep only if p < 0.05; a path with p ≥ 0.05 cannot be reported as “observed”.
3. If you add paths without new variables (all constrained), the F-test does not apply: check χ²_ν and robustness.
4. Try new paths on the **standard** first.

### 3.4 Advanced options and their cost

| Option | When | Cost |
|---|---|---|
| third cumulant c3 (path `third`) | asymmetric first shell | +1 variable, correlated with ΔR |
| larger Rmax + outer shells | clear peaks outside the window you want to explain | more N_idp but usually many more paths |
| two phases / sites | independent evidence of a mixture | variables double; tie N with x and (1−x) |
| several k-weights (1,2,3) at once | always | reduces N–σ² and ΔE0–ΔR correlation |
| split shells | separation > ΔR = π/(2Δk) | otherwise unstable |

---

## 4. Robustness check

EXAFS fitting → **Robustness check** varies kmin ±0.5, kmax ±1, Rmax ±0.2 Å and single k-weights. “Spread/error > 1” = **unstable**. All parameters stable is a prerequisite for reporting. For a series, a **trend must hold under every condition**.

---

## 5. When to stop

1. [ ] Glitches removed; no spike hints in the k residual
2. [ ] One set of processing parameters for the whole series
3. [ ] Model validated on a standard
4. [ ] Variables ≤ N_idp/2
5. [ ] Every added path passed an F-test (or adds no variables)
6. [ ] Robustness check all stable
7. [ ] Residual/noise comparable to the standard, or ≤ 2–3
8. [ ] \|χ(R)\| **and Re χ(R)** follow the main features in the window
9. [ ] (optional) FEFF6L and FEFF8L agree within errors

When all are met but the fit is still not “perfect”, the remaining misfit is the limit of data and theory. Report R-factor, χ²_ν and residual level honestly instead of adding parameters.

---

## 6. Common mistakes

| Mistake | Why it is wrong | Instead |
|---|---|---|
| Adding paths until R < 0.01 | parameters lose meaning; robustness fails | F-test every path; R 0.02–0.05 is normal for multi-shell fits |
| Adding a shell for every small R peak | may be noise, glitch ripple, window side lobe or valley misfit | diagnose first; check with wavelets (⑥) and k-weights |
| Different k range / rbkg per sample | σ² no longer comparable | one parameter set; exceptions in overrides with a reason |
| Looking only at \|χ(R)\| | insensitive to phase | also Re χ(R) and k space |
| Very wide deglitch ranges | removes real signal | remove only deviating points, with a reason |
| Keeping a fixed e0 after switching FEFF version | different ΔE0 zero biases distances | re-determine e0 |
| Expecting a disordered sample to fit as well as the crystal | its model is necessarily coarser | aim for residual/noise comparable to the standard |

---

## 7. Recommended order (cheat sheet)

1. ② QC → k_snr3, glitches → **Deglitch** (range + reason).
2. ④⑤ one set of processing parameters; inspect k¹/k²/k³.
3. ⑦ FEFF6L and FEFF8L for the standard structure.
4. EXAFS fitting: model on the **standard** → fit → **Fit diagnosis** → robustness → save; determine S0².
5. EXAFS fitting: “Run a saved model” on all samples.
6. Diagnose each sample: spike → step 1; low k large → robustness for kmin; smooth localized residual → section 3 with F-tests.
7. Fit history: F-tests; robustness for every conclusion.
8. ⑫ summary, ⑭ journal figures; captions state FEFF version, k/R ranges, k-weights, S0² source, number of scans.
