# AGENTS.md —— XAFS 工具操作手册（给任何 AI 助手：Claude Sonnet/Opus、GPT、Gemini 等）

> 规则与规范见 `CLAUDE.md`（通用 XAFS 处理规范），体系信息见 `project.md`。
> 本文件只讲**怎么用这套工具**。一律用中文回答用户。
> 不需要读懂全部源码；按下面的步骤调用命令即可。每一步的输出文件都列出来了。

## 0. 环境

- Python 环境：项目根目录 `.venv`（Windows）。所有命令都用：
  `.venv\Scripts\python scripts\xafs.py <子命令>`（在 Git Bash 中写作 `.venv/Scripts/python scripts/xafs.py ...`）
- 若 `.venv` 不存在：`python -m venv .venv` 然后 `.venv\Scripts\python -m pip install -r requirements.txt`
- 图形界面：双击 `run_gui.bat`，或 `.venv\Scripts\python scripts\xafs.py gui`，浏览器打开 http://localhost:8501
- FEFF：使用 xraylarch 自带 FEFF6L，无需另装。

## 1. 目录与文件

| 路径 | 内容 | 谁改 |
|---|---|---|
| `data/raw/` | 原始数据（只读，不得修改/删除） | 用户放入 |
| `data/meta.csv` | 每个原始文件一行：`file, sample, edge_key, mode, role, use, time, npts, emax, note, batch, ref_file` | `init` 生成，AI/用户修订 |
| `config.json` | 每个吸收边（如 `Ir_L3`）的统一参数：参比文件、表值能量、样品元素、norm/bkg/ft 参数 | `init` 生成，AI/用户修订 |
| `feff/<结构>_<吸收原子><边>/site<i>/` | feff.inp 与 feffNNNN.dat | `feff` 命令 |
| `notes/*.json` | EXAFS 拟合模型（先写模型再拟合） | AI 编写 |
| `results/` | `qc_report.csv`、`calib.json`、`processed/`、`exafs_fits.csv`、`lcf_results.csv`、`*.fit_report.txt` | 命令输出 |
| `figs/` | 图（16:9，2666×1500，带处理参数图注） | 命令输出 |

`meta.csv` 字段含义：
- `sample`：样品名；**同名多行 = 同一样品多次扫描，处理时合并**（自动剔除异常/不完整扫描并记录理由）
- `role`：`reference`（校准用金属箔/粉）| `standard`（标样）| `sample`
- `use`：`0` 表示不用，必须在 `note` 写理由
- `mode`：`trans`（μ=ln(I0/I1)）或 `fluo`（μ=If/I0）
- `batch`：`data/raw/` 下第一级文件夹 = 一次测量批次（如 `Ta`、`20261105_Ta`）
- `ref_file`：校准这条谱用的参比文件。`init` 自动填**同批次、同吸收边**的 role=reference 文件；
  批次里没有参比时留空并在 note 提示——**ref_file 为空的谱不能处理**，必须补上参比。
- 新批次的样品名与旧批次重名时，`init` 自动加批次后缀（如 `Ta2O5_20261105_Ta`），避免误合并。

## 2. 标准流程（新数据到手后，按顺序执行）

```
1. 用户把原始文件放进 data/raw/<批次>/（每个批次文件夹里应有该批次测的单质参比箔/粉）
   原始数据若在别处，复制进来（不移动、不改原文件）
2. xafs.py init        → 更新 meta.csv / config.json（已有行不会被覆盖）
3. 检查并修订 meta.csv：sample 名是否正确合并、role 是否正确（金属箔=reference）、
   每行 ref_file 是否为同批次参比（xafs.py calib 会列出没有参比的谱）
   检查 config.json："elements_in_sample"（样品中全部元素）
4. xafs.py qc          → results/qc_report.csv；向用户报告：毛刺、I0 掉束、边跳、
                          荧光自吸收风险、k_snr3（信噪比可用 k 上限）
5. xafs.py kcheck --edge Ir_L3   → 干扰边与 k 上限；据此和 k_snr3 修改 config.json 的 ft.kmax
6. xafs.py calib       → results/calib.json（ΔE，参比与样品的测量时间差）
7. xafs.py process     → results/processed/process_summary.csv，figs/<edge>_<role>_*_norm.png / _k_R.png
8. 标样定 S0²：xafs.py feff ... ；写 notes/<标样>_model.json；xafs.py fit notes/<...>.json
   本项目已完成且用户已确认：Ir_L3 0.80、Ta_L3 0.68（2026-11-05 批次 KTaO3 多壳层）、Co_K 0.78，见 config.json 各边的
   "s02_recommended"（来源见 notes/2026-11-02_标样验证.md）。不要自行更改，除非用户要求重新定标。
9. 样品拟合：S0² 固定为 s02_recommended；写模型 → fit；增加壳层时用 ftest 做显著性检验
10. XANES：xafs.py lcf --sample X --standards A B C
11. 汇报：1–2 句结论 + 一个下一步；把用到的模型 JSON、命令与结论写入 notes/
```

## 3. 命令速查

| 命令 | 作用 | 输出 |
|---|---|---|
| `init` | 扫描 data/raw | data/meta.csv, config.json |
| `list` | 样品汇总（扫描数/可用数） | 屏幕 |
| `qc [--edge E]` | 质量检查（逐条扫描） | results/qc_report.csv |
| `kcheck --edge E` | 干扰吸收边 → k 上限 | 屏幕 |
| `calib` | 参比箔一阶导数最大值校准 | results/calib.json |
| `process [--edge E]` | 校准→归一化→合并→χ(k)→FT | results/processed/, figs/ |
| `feff --builtin NAME --absorber X --edge L3 [--rmax 6]` | 内置结构算路径（每个不等价位点一个目录） | feff/... |
| `feff --cif file.cif --absorber X --edge K` | CIF 算路径 | feff/... |
| `fit notes/model.json` | EXAFS 拟合 | results/exafs_fits.csv, *.fit_report.txt, figs/*_fit.png |
| `ftest small.json large.json` | 嵌套模型 F 检验（p<0.05 才算显著） | 屏幕 |
| `lcf --sample S --standards A B [--emin -20 --emax 30 --space norm/dmude/chik]` | LCF + 单一标样比较 + 组合枚举 | results/lcf_results.csv, figs/lcf_*.png |
| `plan --formula IrO2 --element Ir --edge L3 [--diluent BN --mass-diluent 100]` | 样品设计（μt、边跳、推荐质量） | 屏幕 |
| `gui` | 图形界面 | — |

内置结构（在 scripts 目录下运行 `..\.venv\Scripts\python -m xafstool.structures` 列出）：
`Ir, Ta, Co_hcp, Co_fcc, IrO2, CoO, Co3O4, KTaO3`。其他物相（Ta2O5、IrCl3 等）需用户提供 CIF。

## 4. 拟合模型 JSON 模板（notes/xxx.json）

```json
{
  "name": "Irfoil_1shell",
  "sample": "Ir foil",
  "kmin": 3.0, "kmax": 14.0, "dk": 1.0, "window": "hanning",
  "kweight": [1, 2, 3],
  "rmin": 1.8, "rmax": 3.0, "fitspace": "r",
  "params": {
    "s02": {"value": 0.85, "vary": true, "min": 0.4, "max": 1.3},
    "e0":  {"value": 0.0,  "vary": true, "min": -15, "max": 15},
    "dr1": {"value": 0.0,  "vary": true, "min": -0.3, "max": 0.3},
    "ss1": {"value": 0.003, "vary": true, "min": 0.0, "max": 0.03}
  },
  "paths": [
    {"file": "feff/Ir_IrL3/site0/feff0001.dat", "label": "Ir-Ir",
     "s02": "s02", "e0": "e0", "deltar": "dr1", "sigma2": "ss1"}
  ]
}
```
- `sample` 必须与 meta.csv 的 sample 名一致（处理参数自动取 config.json 中该边的设置）。
- 路径加 `"N": "6"` 或 `"N": "n1"`（参数名）表示配位数，此时 FEFF 简并度被替换；不写则用 FEFF 简并度。
- 参数：数字 = 可变初值；`{"value":..,"vary":false}` = 固定；`{"expr":"ss1*1.2"}` 或直接写字符串 = 约束。
- 样品拟合时 S0² 固定：`"s02": {"value": 0.85, "vary": false}`（数值取标样拟合结果）。
- 多重散射路径与单散射共线时，σ² 用表达式绑定并在 note 中说明。
- 同一 label 可用于多条路径（工具自动加文件号区分）。
- 键长分散大的低对称氧化物（如 Ta2O5）：先试"单条有效路径 + N 固定"（见 notes/Ta2O5_eff_Nfix.json），
  再与 CIF 全部路径模型比较；σ² 落在下限 0 说明结构模型内含的分散过大。

## 5. 判读规则（必须遵守，详见 CLAUDE.md 第 5–7 节）

1. 拟合前看 N_idp（命令会打印）；变量数 ≤ N_idp/2，最好 ≤ N_idp − 3。
2. |ΔE0| > 10 eV、σ² < 0、S0² 超出 0.6–1.1 → 警告，需检查模型/E0 定义，不能直接报告。
3. 加壳层必须 `ftest`，p ≥ 0.05 的路径不得说"观察到"。
4. R 空间峰位未相移校正，比真实键长短约 0.3–0.5 Å；不要把峰位当键长。
5. 荧光 vs 透射不能直接比较白线强度（自吸收）；看 qc 的 `self_abs_risk`。
6. **校准规则（用户指定）**：每条谱都必须和**同批次的单质参比**（金属箔/粉）一起载入，并用该参比的
   ΔE 校准；同一参比下的所有谱（标样、样品、原位谱）加同一个 ΔE，不得逐谱或逐样品各自校准。
   `calib` 对每个参比文件算一个 ΔE（results/calib.json 按参比文件索引），`process` 按 meta.csv 的
   ref_file 加 ΔE（process_summary.csv 的 ref_file / dE_cal 列）。
   图形界面：① 按 meta 载入时参比自动一起载入；直接读入文件时**必须选参比**（默认同批次），
   参比一起读入；③ 页列出各参比的 ΔE 与每条谱的校准状态。不同批次不要共用参比。
   无同步参比通道（BSRF 1W1B 本批数据只有 I0/I1/If）时，校准 ΔE 来自单独测量的参比箔；
   参比与样品测量时间相差数小时时，样品能量可能有 ~0.x eV 级漂移，E0 比较要说明这一点。
7. 结论分三类陈述：实测 / 拟合结果 / 推测。不编造数据、误差或文献值。

## 6. 个别样品改参数（overrides）

处理参数原则上同一边所有样品相同。确有理由（如干扰边落在边前范围、数据末端 k 较短）时，
在 config.json 中加：
```json
"overrides": {"样品名": {"norm": {"pre1": -70}, "ft": {"kmax": 10.5}}},
"overrides_reason": {"样品名": "Ta L2 边位于 Ir L3 边前 −79 eV"}
```
必须写理由；汇报时说明该样品参数与其他样品不同。

去毛刺（删去处理副本中的数据点，原始文件不动）：
```json
"deglitch": {"IrO2": [[11355.5, 11368.5], [11395.0, 11403.0]]},
"deglitch_reason": {"IrO2": "11357 单色器毛刺；11400 I0 掉束"}
```
能量为校准后能量；先看 qc 的 glitch_E 和 I0，确认是仪器问题（多个样品同一能量 / I0 凹陷）再删，并比较删前删后的拟合结果。

## 7. 已有的示例（可直接照抄）

- 拟合模型：`notes/Irfoil_1shell.json`、`Tapowder_2shell.json`、`Cofoil_1shell.json`、
  `IrO2_1shell_ArtemisCompare.json`、`KTaO3_1shell.json`、`CoO_2shell.json`、`Tapowder_1shell.json`（ftest 用）
- FEFF：`feff/Ir_IrL3`、`IrO2_IrL3`、`Ta_TaL3`、`KTaO3_TaL3`、`Co_hcp_CoK`、`CoO_CoK`
- 验证记录：`notes/2026-11-02_标样验证.md`

## 8. 自检

- 改了代码后运行 `.venv\Scripts\python scripts\test_gui.py`（逐页测试图形界面，应输出“全部通过”）。
- 命令行回归：`xafs.py fit notes/IrO2_1shell_ArtemisCompare.json --nosave` 应得 S0²≈0.82、ΔE0≈8.9 eV（2026-11-03 起 IrO2 已去毛刺；去毛刺前为 0.80 / 9.2）。

## 9. 常见问题

- `KeyError: meta.csv 中没有可用的样品 X`：sample 名拼写与 meta.csv 不一致（`xafs.py list` 查看）。
- 合并时某扫描被剔除：见 `process_summary.csv` 的 `scans_rejected` 列（RMS 异常或能量范围不完整）。
- FEFF 报错：检查结构是否含吸收原子，RMAX 不宜 > 8 Å。
- Python 模块直接调用：`sys.path.insert(0, "scripts")` 后 `from xafstool import pipeline`；
  `pipeline.build_sample("样品名")` 返回处理好的 larch Group（energy, mu, norm, flat, k, chi, r, chir_mag ...）。
