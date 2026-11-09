# project.md —— 体系特定信息

> 以下“已知”部分仅根据数据文件头整理（实测信息）；标 **【待用户填写】** 的项目请用户补充，AI 不要猜。

# 体系与目标
- 体系：IrTaOx、IrCoOx（电催化，原位电位依赖 XAFS：OCP、1.0/1.3/1.6/1.8/1.9 V 及回到 OCP 的 `_r`）
- 目标：**【待用户填写】**（如：Ir 价态随电位变化、Ta/Co 是否参与重构、第一壳层 CN/σ² 变化）

# 测量（BSRF 1W1B，2026-04-30 至 2026-05-02）
| 边 | 参比（role=reference） | 透射标样 | 原位/样品（荧光，Lytle） |
|---|---|---|---|
| Ir L3 (11215 eV) | Ir foil（5/1 17:41） | IrO2、IrCl3 | IrCoOx_insitu（5/1 08:13–10:26）；IrTa（5/1 17:05–17:13） |
| Ta L3 (9881 eV) | Ta powder（5/1 23:36） | Ta2O5、KTaO3 | IrTaOx insitu（5/2 00:13–01:28）；Ta2O5_insitu（5/2 01:50–03:14） |
| Co K (7709 eV) | Co foil（4/30 20:50） | CoO、Co3O4、Co2O3 | IrCo_insitu（5/1 01:12–02:24）；CoOx_NS、IrCoOx_p（透射） |

- 文件列：Energy, I0, I1, If, ln(I0/I1), If/I0, mu。**无第三电离室参比通道**，参比箔与样品不同时测量。
- 截断/中断扫描：IrCoOx_1_8v_2、_3（只到 ~11270/11230 eV，仅 XANES）；IrCoOx_1_0v（至 11792 eV）；
  IrTaOx_1V（至 10507 eV）；Ta2O5_OCP（至 10111 eV）。
- IrTa 两条 Ir L3 谱只测到 11664/11698 eV。

# 参比与标样
- 能量校准表值：xraydb（Elam）边能量；可在 config.json 中改为其他来源并注明。
- 标样结构质量 **【待用户填写】**（来源、纯度、是否纳米晶）。

# 结构模型来源
- 内置：Ir(fcc)、IrO2(rutile)、Ta(bcc)、KTaO3(perovskite)、Co(hcp)、CoO、Co3O4（参数见 scripts/xafstool/structures.py）
- Ta2O5：用户提供 CIF（C2/c，单一 Ta 位点），见 feff/Ta2O5_TaL3/；拟合见 notes/2026-11-02_Ta2O5拟合.md
- IrCl3、Co2O3：**需 CIF**【待用户提供】

# 已知干扰边 / 已知问题
- Ir L3 + Ta 共存（IrTa 样品）：Ta L1 = 11682 eV，距 Ir L3 467 eV → **k ≈ 11.1 Å⁻¹ 以上不可用**；
  Ta L2（11136 eV）在 Ir L3 边前，影响边前拟合范围。
- 荧光原位数据：自吸收程度 **【待用户填写：载量/膜厚】**。

# 与本体系相关的结论与教训
- 2026-11-02 标样验证（详见 notes/2026-11-02_标样验证.md）：
  - 校准 ΔE：Ir L3 +3.40 eV，Ta L3 −0.72 eV，Co K +0.23 eV（xraydb 表值）
  - S0²（**用户已确认**）：Ir L3 0.80（IrO2），Ta L3 **0.68**（2026-11-05 批次 KTaO3 多壳层；用户指示以新批次为准，取代 0.75），Co K 0.78（Co foil）；见 config.json 的 s02_recommended，样品拟合固定为此值
  - 2026-05 批次 Ta 标样（KTaO3、Ta2O5）已停用（use=0）
  - Ta powder、Ir foil 的 S0² 均为 0.57，不作 S0² 来源；**2026-11-05 更正**：薄 Ta_foil 也给 0.57，
    "Ta powder 过厚"不是主因，金属参比普遍偏低（原因未明）
  - "Co2O3" 标样谱与 Co3O4 几乎相同（推测试剂为 Co3O4）
  - IrO2 已去毛刺（config.json deglitch）；多壳层拟合 Ir–Ir 3.54 Å 显著，S0² 浮动 0.86±0.12 与 0.80 一致
    （notes/2026-11-03_IrO2分析.md）
  - IrTa 两条 Ir L3 荧光谱受 Ta L2/L1 与探测器尖峰影响，EXAFS 不可用
- 2026-11-05 Ta 新批次（data/raw/20261105_Ta：Ta_foil、Ta2O5、KTaO3，透射）：
  用同批 Ta_foil 校准 ΔE=+0.14 eV；详见 notes/2026-11-05_Ta新批次.md
- 2026-11-07 Ta_Time_resolved（Ir/KTaO3；IrTa-50=新样品仅通水，100–300 约化时间）：新样品已较 KTaO3 无序；运行中共角链信号
  逐步减弱（主要 100→200），八面体与共角拓扑保留、无边共享；IrTa-300 XANES 变化待重测确认；
  报告 Ta_Time_resolved/analysis/报告_Ta时间分辨XAFS.md
- 2026-11-07 Ta_raw（编号混乱的 7+1 条荧光谱）：剔除 200_0（掉束）；按共角链比分组 A{IrTa-mem-200,100-2,25,50-long}→B{100-1}→C{IrTa-mem-50,200}；
  报告 Ta_raw/analysis/报告_Ta_raw排序.md
- 2026-11-07 IrTa_series：从 Ta_raw 选 4 条趋势一致的谱重命名为 IrTa_0–3（100-2, 50-long, 100-1, 200）+ 同机时标样；
  报告 IrTa_series/analysis/报告_IrTa序列.md
- 校准方式（2026-11-05 起）：每条谱用同批次参比校准，meta.csv 的 ref_file 列记录
