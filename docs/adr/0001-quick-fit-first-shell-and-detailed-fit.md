# Quick fit fits only the first shell; the Artemis-style page stays as Detailed fit

The EXAFS fitting page has two modes: Quick fit, which builds and fits a first-shell-only model automatically and gives a plain-language verdict, and Detailed fit, which is the v1.3.1 path table + parameter table unchanged except for column order. A full redesign that replaced both tables with a single table of shells (one row per shell, fix / fit / same-as states) was built and abandoned before release: people who know Artemis had no reason to switch, and people who do not still could not fit with it. Quick fit covers the beginner's case by asking only for decisions a beginner can make, and the rest stays expression-level for those who need it.

## Considered options

- **One table of shells replacing both tables** — abandoned for the reason above.
- **Automatic multi-shell fitting with F-test shell addition** — rejected: shell choice beyond the first shell (and multiple scattering) needs judgement the automatic rules cannot make for arbitrary compounds.

## Consequences

- Quick fit writes ordinary `models/*.json`; "continue in Detailed fit" loads that model, so there is one model format.
- All quick-fit rules depend only on scatterer element and distance, so they hold for any absorber.
