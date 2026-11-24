# 内置结构（COD）/ Built-in structures (COD)

These CIF files come from the Crystallography Open Database (https://www.crystallography.net/cod/),
whose data are placed in the public domain (CC0). Each row of `index.csv` gives the COD id and the
original publication; cite the original paper when you use a structure.

Selection (2026-11-25): COD entries of the target formula and space group at ambient temperature and
pressure; partially occupied (disordered) entries rejected; Wyckoff, *Crystal Structures* (1963)
preferred; otherwise temperature / pressure series reduced to their first member and the median
volume per atom taken. Every structure was checked by its absorber's first shell (`first_shell`).
Manual choices: Ni 2100646, Fe 9006587, ZnO 9004178, MoS2 1531960, Fe2O3 9000139 (the automatic
pick had a non-ambient cell or a wrong oxygen position). Hydroxides carry no H positions.

Not included (no ordered ambient entry, or wrong geometry in COD): Rh2O3, PtO2, Ta2O5, Nb2O5,
Ga2O3, NiFe2O4, CoFe2O4, CuFe2O4, NiCo2O4 — supply your own CIF in the project's `structures/`.
