# structures/ —— 结构文件

放 FEFF 计算用的结构：CIF（推荐）、POSCAR / CONTCAR / *.vasp、pymatgen JSON。

- 文件名就是结构名：`xafsmith feff --structure Ta2O5.cif --absorber Ta --edge L3` → `output/feff/Ta2O5_TaL3/site*/`
- 在 project.md 的“结构模型来源”中写明每个文件的来源（数据库编号、文献）。
- 内置结构可导出到 `structures/builtin/` 查看：`xafsmith structures --export`
