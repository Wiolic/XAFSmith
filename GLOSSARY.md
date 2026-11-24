# XAFSmith

XAFS data processing and EXAFS fitting. This glossary fixes the words used in the GUI, docs and code.

## EXAFS fitting

**Quick fit** (快速拟合):
The EXAFS fitting mode that fits only the first shell automatically and states in plain words whether the result can be trusted; the user chooses only samples, FEFF folder, purpose, Rmax and S0².
_Avoid_: simple mode, wizard, 傻瓜模式

**Detailed fit** (精细拟合):
The EXAFS fitting mode where the user writes every path and parameter by hand (path table + parameter table).
_Avoid_: expert mode, advanced mode, Artemis mode

**First shell** (第一壳层):
The nearest single-scattering neighbours of the absorber: same scatterer element, consecutive distances less than 0.3 Å apart, starting from the shortest path.
_Avoid_: first peak (that is a feature of |χ(R)|, not of the structure)

**Standard fit** (标样拟合):
A fit of a reference compound of known structure whose purpose is to determine S0²: N is fixed to the crystallographic value and S0² is fitted.
_Avoid_: calibration fit

**S0² source** (S0² 来源):
Where the fixed S0² of a sample fit comes from: a named standard fit (value ± error) or a manual entry.
_Avoid_: S0² origin, reference S0²

**Verdict** (判定):
The quick-fit conclusion for one sample: trustworthy, or has problems with each failed check and a suggested action.
_Avoid_: score, grade
