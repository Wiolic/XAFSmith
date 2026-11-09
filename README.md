# XAFSmith

通用 XAFS（XANES + EXAFS）数据处理与拟合工具：命令行 + 图形界面（类似 Athena / Artemis），
基于 [xraylarch](https://xraypy.github.io/xraylarch/)（FEFF6L、feffit）、xraydb、lmfit、pymatgen 与 Streamlit。

设计目标：**可复现、可比较、可追溯**——所有处理参数写在配置文件里，原始数据只读，
每次分析的模型、参数与结论都留在 `notes/`；任何 AI 助手（Claude、GPT、Gemini 等）按 `AGENTS.md` 即可接手。

新手请先看 **[QUICKSTART.md](QUICKSTART.md)**。

## 功能

| 环节 | 内容 |
|---|---|
| 读入 | BSRF 文本、通用列文本、Athena `.prj`；透射 μ=ln(I0/I1)、荧光 μ=If/I0 |
| 质量检查 | 毛刺、I0 掉束、边跳、荧光自吸收风险、信噪比可用 k 上限 |
| 能量校准 | 每条谱用**同批次单质参比**（金属箔/粉）一阶导数最大值校准，ΔE 按参比文件记录 |
| 归一化 / 合并 | 统一的边前/边后参数；多次扫描合并并自动剔除异常扫描（记录理由） |
| χ(k) / FT / 小波 | AUTOBK 背景扣除、Hanning/Kaiser 窗 FT（R 空间标注“未相移校正”）、Morlet/Cauchy 小波 |
| FEFF | 内置结构或 CIF → FEFF6L 路径（按不等价位点） |
| EXAFS 拟合 | JSON 模型：路径、参数约束（固定 / 表达式）、多 k 权重同时拟合；N_idp 检查、F 检验 |
| LCF | XANES / 导数 / χ(k) 线性组合，含单一标样比较与组合枚举 |
| 样品设计 | μt、边跳、推荐压片质量、干扰吸收边与 k 上限 |
| 报告 | 16:9 汇报图（2666×1500），图注自动写明样品、模式、处理参数 |

## 目录

```
.
├── README.md / QUICKSTART.md
├── AGENTS.md          # 工具操作手册（给任何 AI 或人）：命令、文件约定、模型模板、判读规则
├── CLAUDE.md          # 通用 XAFS 处理与拟合规范
├── project.md         # 本项目（IrTaOx / IrCoOx 电催化）的体系信息与结论
├── config.json        # 每个吸收边的处理参数、S0² 推荐值、个别样品 overrides、去毛刺
├── requirements.txt
├── data/meta.csv      # 每个原始文件一行：样品名、边、模式、角色、批次、校准参比 ref_file …
├── notes/             # 拟合模型 JSON 与每次分析的记录（日期_主题.md）
└── scripts/
    ├── xafs.py        # 统一命令行入口
    ├── gui_app.py     # 图形界面（Streamlit）
    ├── test_gui.py    # 图形界面自动测试
    ├── analysis_*.py  # 本项目的专题分析脚本
    └── xafstool/      # 模块：io, qc, calib, normalize, autobk, ft, wavelet, structures,
                       #       feff_wrap, fit_exafs, fit_lcf, mut_planner, report, pipeline
```

**不在仓库中**（本地生成或自行放入）：`data/raw/`（原始数据，只读）、`feff/`（FEFF 计算，可用 `xafs.py feff` 重新生成）、
`results/`、`figs/`、各数据文件夹下的 `analysis/`、`.venv/`。

## 常用命令

```
python scripts/xafs.py init        # 扫描 data/raw → meta.csv / config.json
python scripts/xafs.py qc          # 质量检查
python scripts/xafs.py calib       # 按参比校准
python scripts/xafs.py process     # 校准→归一化→合并→χ(k)→FT
python scripts/xafs.py feff --builtin IrO2 --absorber Ir --edge L3
python scripts/xafs.py fit notes/IrO2_1shell_ArtemisCompare.json
python scripts/xafs.py ftest notes/A.json notes/B.json
python scripts/xafs.py lcf --sample S --standards A B
python scripts/xafs.py gui         # 图形界面 http://localhost:8501
```

完整说明见 [AGENTS.md](AGENTS.md)。

## 验证

- 与 Artemis 对照（IrO2，同一 k/R 范围与 k 权重）：S0² 0.80 ± 0.11 vs 0.86 ± 0.09，ΔE0 9.2 vs 10.2 eV，ΔR −0.012 vs −0.010 Å，误差内一致。
- 标样多壳层拟合（金红石 IrO2、立方钙钛矿 KTaO3）给出与晶体学一致的配位与键长。
- `python scripts/test_gui.py` 逐页测试图形界面（应输出“全部通过”）。

详见 `notes/2026-11-02_标样验证.md`。

## 约定

- 原始数据只读；所有结果从 `data/raw/` 重新生成。
- 结论分三类：**实测 / 拟合 / 推测**；加壳层必须做 F 检验（p < 0.05）。
- 理论值注明来源（xraydb Elam 表、FEFF6L）。
