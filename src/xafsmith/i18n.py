"""i18n —— 图形界面中英文切换。

做法：界面代码仍用中文书写；选择 English 时，把 Streamlit 显示函数（标题、按钮、标签、提示、表头、
选项显示、图表坐标轴等）的文字按下面的对照表翻译后再显示。只改“显示”，不改控件的取值和数据，
因此程序逻辑与中文界面完全相同。对照表按“长短语优先”做子串替换，最后替换中文标点。
没有收录的文字保持中文（新增界面文字时请在 EN 中补充）。

语言保存在 ~/.xafsmith/settings.json 的 "lang"（"zh" / "en"）。
"""
import re

LANG = "zh"
CJK = re.compile(r"[　-〿一-鿿＀-￯【】]")

EN = {
    # ---- 页面
    "⓪ 项目": "⓪ Project", "① 数据导入": "① Import data", "② 质量检查": "② Quality check",
    "③ 能量校准": "③ Energy calibration", "④ 归一化 (Athena)": "④ Normalization (Athena)",
    "⑤ χ(k) 与 FT": "⑤ χ(k) & FT", "⑥ 小波变换": "⑥ Wavelet transform", "⑦ FEFF 路径": "⑦ FEFF paths",
    "⑧ EXAFS 拟合 (Artemis)": "⑧ EXAFS fitting (Artemis)", "⑨ 拟合历史/F检验": "⑨ Fit history / F-test",
    "⑪ 样品设计": "⑪ Sample design", "⑫ 汇总报告": "⑫ Summary report", "⑬ XANES 定量": "⑬ XANES quantification",
    "⑭ 期刊出图": "⑭ Journal figures", "❓ 使用指南": "❓ Help",
    "② 数据质量检查 (QC)": "② Data quality check (QC)", "④ 归一化（Athena）": "④ Normalization (Athena)",
    "⑤ 背景扣除 χ(k) 与傅里叶变换": "⑤ Background removal χ(k) and Fourier transform",
    "⑦ FEFF 路径计算": "⑦ FEFF path calculation", "⑧ EXAFS 拟合（Artemis）": "⑧ EXAFS fitting (Artemis)",
    "⑨ 拟合历史与 F 检验": "⑨ Fit history and F-test", "⑩ 线性组合拟合 (LCF)": "⑩ Linear combination fitting (LCF)",
    "⑪ 样品设计（透射 μt / 边跳 / 干扰边）": "⑪ Sample design (transmission μt / edge step / interfering edges)",
    "R (Å) — 未相移校正": "R (Å) — not phase-corrected",
    # ---- 侧栏
    "功能": "Pages", "先打开或新建项目": "Open or create a project first", "已载入 ": "Loaded ",
    " 条谱 · 拟合 ": " spectra · fits: ", "项目：": "Project: ", "保存会话参数": "Save session parameters",
    "已保存 output/gui/gui_session.params.json": "Saved output/gui/gui_session.params.json",
    "**不对结果负责 / No warranty.** 请核验结果，建议与 Athena / Artemis 对比。Please cross-check key results with Athena / Artemis.":
        "**No warranty.** Please validate your results and cross-check key results with Athena / Artemis.",
    "**论文中使用请引用 / Please cite:**  \n": "**If you use XAFSmith in a publication, please cite:**  \n",
    "图形界面使用指南（点哪里）": "GUI guide (where to click)", "零基础拟合教程（原理 + 每一步）": "Beginner fitting tutorial (principles + every step)",
    # ---- ⓪ 项目
    "打开 / 新建项目": "Open / create project", "📁 浏览…": "📁 Browse…",
    "项目文件夹（点“浏览…”选择，或粘贴路径）": "Project folder (click “Browse…” or paste a path)",
    "打开此文件夹": "Open this folder", "新建项目（已有文件不会被覆盖）": "Create project (existing files are not overwritten)",
    "1 数据登记": "1 Register data", "2 检查": "2 Check", "3 一键处理": "3 One-click processing",
    "4 处理参数": "4 Processing parameters", "5 结构文件": "5 Structure files", "6 输出": "6 Output",
    "原始数据放在 **data/raw/<批次>/**，每个批次带该批次测的单质参比（文件名含 foil / powder / metal）。":
        "Put raw data in **data/raw/<batch>/**; each batch must include the elemental reference measured in that session (file name containing foil / powder / metal).",
    "扫描 data/raw，登记新文件": "Scan data/raw and register new files",
    "按数据标准检查：文件是否存在、每条谱是否有参比、参数是否完整、模型路径是否存在。":
        "Check against the data standard: files exist, every spectrum has a reference, parameters are complete, model paths exist.",
    "运行检查": "Run check", "按 xafsmith.json 与 meta.csv 批量处理全部样品；结果写入 output/。":
        "Process all samples according to xafsmith.json and meta.csv; results go to output/.",
    "① 质量检查": "① Quality check", "② 按参比校准": "② Calibrate with references", "③ 处理全部样品": "③ Process all samples",
    "上传结构文件（CIF / POSCAR / .vasp）到 structures/": "Upload structure files (CIF / POSCAR / .vasp) to structures/",
    "把内置结构导出为 CIF（structures/builtin/）": "Export built-in structures as CIF (structures/builtin/)",
    "全部结果都在 **output/**（可以删除后重新生成）：": "All results are in **output/** (can be deleted and regenerated):",
    "打开 output 文件夹": "Open output folder", "打开项目文件夹": "Open project folder", "选择项目文件夹": "Select project folder",
    "引用格式 / How to cite": "How to cite", "当前项目：**": "Current project: **",
    "当前目录不是 XAFSmith 项目：": "The current folder is not an XAFSmith project: ",
    "。请在下面打开或新建一个项目。": ". Open or create a project below.", "最近的项目": "Recent projects", "打开": "Open",
    "批次文件夹名": "Batch folder name", "批次1": "batch1", "上传原始数据文件到 data/raw/<批次>/": "Upload raw data files to data/raw/<batch>/",
    "还没有吸收边：先在“1 数据登记”中扫描 data/raw。": "No absorption edges yet: scan data/raw in “1 Register data” first.",
    "保存结构文件": "Save structure files", "已保存；在 ⑦ FEFF 路径 中选择“structures/ 文件夹”使用。":
        "Saved; choose “structures/ folder” in ⑦ FEFF paths to use them.",
    "无法打开文件夹对话框（": "Cannot open the folder dialog (", "），请直接粘贴路径。": "); please paste the path.",
    "上传": "Upload", "新增 ": "Added ", " 行；吸收边 ": " rows; edges ",
    "可以直接改：sample（同名 = 合并）、role、use（0 = 不用，须写 note）、ref_file（校准参比）、note。改完点保存。":
        "Editable: sample (same name = merged), role, use (0 = not used, note required), ref_file (calibration reference), note. Click save when done.",
    "保存 meta.csv": "Save meta.csv", "meta.csv 还是空的：放入数据后点“扫描 data/raw”。":
        "meta.csv is empty: add data, then click “Scan data/raw”.",
    " 个错误，": " errors, ", " 个警告": " warnings", "检查中…": "Checking…",
    "校准 → 归一化 → 合并 → χ(k) → FT …": "Calibrate → normalize → merge → χ(k) → FT …",
    "/；之后在“① 数据导入”中按样品载入查看": "/; then load samples in “① Import data” to view them",
    "，表值 E0 = ": ", tabulated E0 = ", "）。同一吸收边的所有样品使用这一套参数。": "). All samples of this edge use these parameters.",
    "样品中的全部元素（逗号分隔，用于干扰边检查）": "All elements in the sample (comma-separated, for interfering-edge check)",
    "**归一化**": "**Normalization**", "norm2（≤0 距末端）": "norm2 (≤0: from end)", "E0 平滑 σ": "E0 smoothing σ",
    "**背景扣除 / 傅里叶变换**": "**Background removal / Fourier transform**", "背景 k 权重": "Background k-weight",
    "FT k 权重": "FT k-weight", "**S0²（标样上拟合得到，样品拟合时固定）**": "**S0² (from a standard; fixed for samples)**",
    "误差": "error", "来源": "source", "保存参数": "Save parameters", "**structures/** 中有 ": "**structures/** contains ",
    " 个结构文件": " structure files", " 中没有 xafsmith.json，不是项目；可以点“新建项目”。":
        " has no xafsmith.json and is not a project; click “Create project”.",
    " 个文件到 ": " files to ", "（已存在的同名文件未覆盖）": " (existing files were not overwritten)",
    "已保存。改了 ref_file 或 role 后请到“3 一键处理”重新校准。": "Saved. After changing ref_file or role, recalibrate in “3 One-click processing”.",
    "已保存到 xafsmith.json；改动后请重新“③ 处理全部样品”。": "Saved to xafsmith.json; rerun “③ Process all samples”.",
    # ---- ① 导入
    "**按 data/meta.csv + config.json 载入**（与命令行 `xafs.py process` 完全相同：已校准、已归一化、重复扫描已合并、χ(k)/FT 已算）":
        "**Load from data/meta.csv + xafsmith.json** (same as the command line: calibrated, normalized, repeated scans merged, χ(k)/FT computed)",
    "或整条边": "or a whole edge", "载入样品": "Load samples",
    "校准参比（同批次单质箔/粉，会一起载入）：": "Calibration references (elemental foil/powder of the same batch, loaded together): ",
    "⚠ 无": "⚠ none",
    "**或直接读入文件**——必须同时选择**参比**（与这些谱同一批测量的单质箔/粉）：参比会一起读入，并用它的 ΔE 校准所有谱。.prj 中的谱保持原样。":
        "**Or read files directly** — you must also choose a **reference** (elemental foil/powder measured in the same session): it is read together and its ΔE calibrates all spectra. Spectra from .prj files are kept as they are.",
    "从项目中选择文件（BSRF 文本 / Athena .prj / 列文本）": "Select files in the project (BSRF text / Athena .prj / column text)",
    "或上传文件（保存到 data/raw/uploads/，只读）": "Or upload files (saved to data/raw/uploads/, read-only)",
    "参比（必选，同批次单质箔/粉）": "Reference (required; elemental foil/powder of the same batch)",
    "— 请选择参比 —": "— choose a reference —", "模式": "Mode", "自动(按文件头)": "auto (from header)",
    "透射 μ=ln(I0/I1)；荧光 μ=If/I0": "transmission μ = ln(I0/I1); fluorescence μ = If/I0",
    "通用列文本设置": "Column-text settings", "能量列": "Energy column", "I0 列(-1 无)": "I0 column (-1 none)",
    "I1 列(-1 无)": "I1 column (-1 none)", "If 列(-1 无)": "If column (-1 none)", "μ 列(-1 由 I 计算)": "μ column (-1: from I)",
    "元素": "Element", "请先选择参比，再读入。": "Choose a reference first, then read.", "读入": "Read",
    "参比来自批次 ": "Reference is from batch ", "，所选谱来自 ": ", selected spectra are from ",
    "：不同批次之间单色器状态可能不同。": ": the monochromator state may differ between batches.",
    "：吸收边 ": ": edge ", " 与参比 ": " differs from reference ", " 不同，未读入（请为它选择同边的参比，分开读入）":
        "; not read (choose a reference of the same edge and read it separately)",
    "删除": "Delete", "删除所选": "Delete selected", "查看原始 μ(E) 和通道": "View raw μ(E) and channels",
    # ---- ② QC / ③ 校准
    "选择谱": "Select spectra", "运行 QC": "Run QC",
    "已保存 output/qc/qc_report.csv。delta_mut：透射边跳（与增益无关）；self_abs_risk：荧光谱由 I1 通道估计的样品(+电解池) Δμt；k_snr3：k²χ 包络降到 3×噪声的位置，可作 kmax 的参考。":
        "Saved output/qc/qc_report.csv. delta_mut: transmission edge step (gain-independent); self_abs_risk: sample (+cell) Δμt estimated from the I1 channel of fluorescence data; k_snr3: where the k²χ envelope drops to 3× noise, a guide for kmax.",
    "**规则**：每条谱都用**与它同一批测量的单质参比**（金属箔/粉）校准：ΔE = E_table − E0_meas（E0 取一阶导数最大值）。同一参比下的所有谱加同一个 ΔE，不对单个样品各自校准。读入时必须选参比（① 页），meta.csv 的 ref_file 列记录每条谱用的参比。":
        "**Rule**: every spectrum is calibrated with **the elemental reference measured in the same session** (metal foil/powder): ΔE = E_table − E0_meas (E0 = maximum of the first derivative). All spectra of one reference get the same ΔE; samples are never calibrated individually. A reference must be chosen when reading (page ①); the ref_file column of meta.csv records it.",
    "1. 参比校准值（每个参比文件一个 ΔE）": "1. Reference calibration (one ΔE per reference file)",
    "还没有校准值：在 ① 读入时选参比，或在下方第 3 步测定，或命令行运行 `xafs.py calib`。":
        "No calibration yet: choose a reference when reading in ①, or determine it in step 3 below.",
    "2. 已载入谱的校准状态": "2. Calibration status of loaded spectra", "尚未载入谱（① 数据导入）。": "No spectra loaded yet (① Import data).",
    "无第三电离室同步参比时，ΔE 只代表测参比时的单色器状态；与参比时间差大的谱可能有 ~0.x eV 漂移。":
        "Without a simultaneous reference (third ion chamber), ΔE reflects the monochromator at the time the reference was measured; spectra measured long after may drift by ~0.x eV.",
    "**换参比 / 补校准**": "**Change reference / calibrate**", "参比": "Reference",
    "应用到（只能选同一吸收边的谱）": "Apply to (spectra of the same edge only)", "用此参比校准所选谱": "Calibrate selected spectra with this reference",
    "已校准 ": "Calibrated ", "3. 测定 / 重新测定参比 ΔE（新参比、参比重测或换表值时）":
        "3. Determine / redetermine reference ΔE (new reference, remeasured reference or different table value)",
    "没有单质参比文件：在 meta.csv 中把金属箔/粉标为 role=reference。": "No elemental reference file: mark the metal foil/powder as role=reference in meta.csv.",
    "单质参比文件": "Elemental reference file", " 单质的标准边能量 E_table (eV)": " tabulated edge energy E_table (eV)",
    "默认 config.json / xraydb (Elam) 表值；可改为 Bearden 或文献值": "Default: xafsmith.json / xraydb (Elam); can be changed to Bearden or literature values",
    "导数平滑 σ (eV)": "Derivative smoothing σ (eV)", "dμ/dE (平滑)": "dμ/dE (smoothed)", "E (eV, 未校准) — ": "E (eV, uncalibrated) — ",
    " vs 已保存": " vs saved", "已保存的值": "Saved value", "保存此参比的 ΔE（并重新校准用它的 ": "Save this reference's ΔE (and recalibrate the ",
    " 条已载入谱）": " loaded spectra using it)", "已保存到 output/calib/calib.json，重新校准 ": "Saved to output/calib/calib.json; recalibrated ",
    " 条谱。注意：命令行 `xafs.py calib` 会用 config.json 的表值重新计算并覆盖此文件。": " spectra. Note: `xafsmith calib` recomputes with the table values in xafsmith.json and overwrites this file.",
    "✘ 未按参比校准": "✘ not calibrated with a reference", "⚠ 平移 ": "⚠ shift ", " eV，来源不明": " eV, unknown origin",
    "⚠ 参比 ": "⚠ reference ", " 无校准记录": " has no calibration record", " 与参比的 ": " differs from the reference's ", " 不一致": "",
    # ---- ④ 归一化 / ⑤ χ / ⑥
    "先导入数据": "Import data first", "所有样品使用同一套归一化参数（相对 E0 的 eV）。E0 = 平滑后一阶导数最大值。":
        "All samples use the same normalization parameters (eV relative to E0). E0 = maximum of the smoothed first derivative.",
    "E0 固定(空=导数最大)": "Fixed E0 (empty = derivative max.)", "norm2 (≤0: 距末端)": "norm2 (≤0: from end)", "E0 平滑σ": "E0 smoothing σ",
    "当前谱（显示边前/边后线）": "Current spectrum (show pre/post-edge lines)", "μ(E) + 边前/边后": "μ(E) + pre/post-edge",
    "归一化叠加": "Normalized overlay", "导数": "Derivative", "合并扫描": "Merge scans", "横轴 E−E0": "x axis E−E0",
    "归一化 μ(E)": "Normalized μ(E)", "（透射：= Δμt）": " (transmission: = Δμt)", " eV**，edge step = **": " eV**, edge step = **",
    "先逐条检查再平均：与中位谱 RMS 偏差超过阈值的扫描自动剔除，也可手动剔除。":
        "Check scans before averaging: scans deviating from the median by more than the threshold (RMS) are rejected automatically; you can also reject manually.",
    "要合并的扫描（同一样品同一条件）": "Scans to merge (same sample, same conditions)", "手动剔除": "Reject manually",
    "自动剔除阈值 (×中位 RMS)": "Auto-reject threshold (× median RMS)", "合并后名称": "Merged name", "合并": "Merge",
    "已生成 ": "Created ", " 条扫描）": " scans)", "导出所选归一化数据到 output/gui/norm/": "Export selected normalized data to output/gui/norm/",
    "已导出 ": "Exported ", " 条到 ": " to ", "窗函数": "Window", "作图 Rmax": "Plot Rmax", "背景 μ0(E)": "Background μ0(E)",
    "k 范围检查": "k-range check", "显示 Re χ(R)": "Show Re χ(R)", "R 轴未相移校正：峰位比真实键长短约 0.3–0.5 Å。":
        "R axis not phase-corrected: peaks appear ~0.3–0.5 Å shorter than the true bond lengths.",
    "μ0(E) 背景": "μ0(E) background", "样品中所有元素（逗号分隔，用于干扰边检查）": "All elements in the sample (comma-separated, for interfering-edge check)",
    "数据末端 k = ": "End of data k = ", " Å⁻¹；考虑干扰边后可用 k 上限 ≈ **": " Å⁻¹; usable k limit considering interfering edges ≈ **",
    "拟合 Rmin": "Fit Rmin", "拟合 Rmax": "Fit Rmax", "ΔR 分辨率 = π/(2Δk) = **": "ΔR resolution = π/(2Δk) = **",
    " Å**；N_idp = 2ΔkΔR/π = **": " Å**; N_idp = 2ΔkΔR/π = **", "导出 χ(k) 与 χ(R) 到 output/gui/chi/": "Export χ(k) and χ(R) to output/gui/chi/",
    "已导出到 ": "Exported to ", "先在 ⑤ 中计算 χ(k)": "Compute χ(k) in ⑤ first", "谱": "Spectrum", "母小波": "Mother wavelet",
    "k 权重": "k-weight", "重散射体的最大值出现在较高 k，轻散射体（O 等）在较低 k。":
        "Heavy scatterers peak at higher k, light scatterers (O etc.) at lower k.",
    # ---- ⑦ FEFF
    "结构来源": "Structure source", "structures/ 文件夹": "structures/ folder", "内置结构": "Built-in structure",
    "上传（保存到 structures/）": "Upload (saved to structures/)", "结构": "Structure", "结构文件": "Structure file",
    "structures/ 中还没有结构文件：把 CIF / POSCAR 放进去，或选“上传”。": "No structure files in structures/: put CIF / POSCAR files there or choose “Upload”.",
    "   空间群: ": "   space group: ", "吸收原子": "Absorber", "吸收边": "Edge", "不等价位点 (index, 多重度)": "Inequivalent site (index, multiplicity)",
    "输出目录": "Output folder", "运行 FEFF6L": "Run FEFF6L", "FEFF 运行中…": "Running FEFF…", "完成：": "Done: ",
    " 条路径 → ": " paths → ", "已有 FEFF 计算": "Existing FEFF calculations", "目录": "Folder",
    "拟合质量提升教程（对不严时怎么办）": "Improving fit quality (when the fit does not match)",
    # ---- 侧栏 / sidebar
    "开始": "Start", "数据处理": "Processing", "结构与拟合": "Structure & fitting", "结果与导出": "Results & export",
    "帮助": "Help", "同步辐射 XAFS 分析": "Synchrotron XAFS analysis", "可连接 AI 助手": "Agent-ready",
    "拟合数": "Fits",
    "⚠️ 不对结果负责，请与 Athena / Artemis 对照；论文中使用请引用本仓库（见 ⓪ 项目）":
        "⚠️ No warranty — cross-check with Athena / Artemis; please cite the repository in publications (see ⓪ Project)",
    # ---- ⓪ 项目 → AI 助手 / agent
    "🤖 7 AI 助手": "🤖 7 AI assistant",
    "XAFSmith 项目是标准化的文件夹，AI 助手可以直接读懂并替你处理、拟合、导出。它做的每一步都写进项目文件，你可以随时在本界面中打开、检查、修改。":
        "An XAFSmith project is a standardized folder, so an AI assistant can read it directly and process, fit and export for you. Every step it takes is written into the project files, which you can open, check and change here at any time.",
    "已接入": "connected", "需更新": "outdated", "未接入": "not connected", "命令路径": "Command path",
    "已写入": "written", "本机 xafsmith 命令（AI 用它运行所有步骤）：": "xafsmith command on this computer (the AI runs every step with it):",
    "写入 / 更新 AI 说明文件（AGENTS.md、CLAUDE.md）": "Write / update AI instruction files (AGENTS.md, CLAUDE.md)",
    "已更新：": "Updated: ", "已是最新，无需改动": "Already up to date",
    "只更新 AGENTS.md 中 XAFSmith 标记之间的部分；你自己写在 AGENTS.md / CLAUDE.md 里的内容会保留。":
        "Only the part between the XAFSmith markers in AGENTS.md is updated; anything you wrote in AGENTS.md / CLAUDE.md is kept.",
    "#### 第 1 步：在项目文件夹里打开 AI 助手": "#### Step 1: open the AI assistant in the project folder",
    "AI 助手": "AI assistant", "怎么打开": "How to open",
    "Claude Code 桌面版": "Claude Code desktop app", "新建会话 → 选择本项目文件夹": "New session → choose this project folder",
    "Claude Code 命令行": "Claude Code CLI", "在本项目文件夹中打开终端，输入 `claude`": "Open a terminal in this project folder and type `claude`",
    "在本项目文件夹中打开终端，输入 `codex`，或在 Codex 应用中打开该文件夹":
        "Open a terminal in this project folder and type `codex`, or open the folder in the Codex app",
    "文件 → 打开文件夹 → 本项目文件夹，打开 AI 对话面板": "File → Open Folder → this project folder, then open the AI chat panel",
    "#### 第 2 步：用自己的话告诉它要做什么（可以直接复制）": "#### Step 2: tell it what to do in your own words (copy an example)",
    "#### 第 3 步：检查 AI 的结果": "#### Step 3: check the AI's results",
    "拟合模型在 models/：⑧ 页顶部“运行已保存的模型”可以重跑、查看拟合诊断与稳健性检查":
        "Fit models are in models/: rerun them with “Run a saved model” at the top of ⑧ and inspect the fit diagnosis and robustness check",
    "全部数值结果在 output/；分析记录在 notes/": "All numerical results are in output/; analysis notes in notes/",
    "期刊图在 output/figs/journal/，汇总报告在 output/reports/（⑫、⑭ 页也能直接看）":
        "Journal figures are in output/figs/journal/, summary reports in output/reports/ (also viewable on ⑫ and ⑭)",
    # ---- 拟合诊断
    "拟合诊断：残差在哪里、为什么对不上": "Fit diagnosis: where the residual is and why",
    "窗口内残差 RMS": "In-window residual RMS", "白噪声估计 (R 15–25 Å)": "White-noise estimate (R 15–25 Å)",
    "残差 / 噪声": "Residual / noise", "残差": "Residual",
    "k 分段残差（相对中位数 > 1.5 为偏大）": "Residual by k segment (relative to median > 1.5 = large)",
    "R 分段局部失配 = Σ|数据−拟合|² / Σ|数据|²（未相移校正）": "Local misfit by R segment = Σ|data−fit|² / Σ|data|² (not phase-corrected)",
    "说明：残差/噪声 ≈ 1–2 时已到数据极限；≫ 2 说明残差是系统性的。系统偏差不一定能、也不一定应该用加参数消除——每加一条路径都要通过 F 检验与稳健性检查。":
        "Note: residual/noise ≈ 1–2 means the data limit is reached; ≫ 2 means the residual is systematic. Systematic misfit cannot always, and should not always, be removed by adding parameters — every added path must pass the F-test and the robustness check.",
    "k段": "k segment", "残差RMS": "residual RMS", "相对中位数": "relative to median", "R段": "R segment",
    "局部失配": "local misfit", "数据强度": "data intensity", "（窗口外）": " (outside window)",
    "窗口内残差约为噪声的 ": "In-window residual is about ", " 倍：已接近噪声水平，继续加路径/参数只会过拟合。":
        "× the noise: close to the noise level; more paths/parameters would only overfit.",
    "窗口内残差约为白噪声估计的 ": "In-window residual is about ",
    " 倍：残差主要是系统性的（模型、理论或数据处理），不是随机噪声。按下面各条逐一排查。":
        "× the white-noise estimate: the residual is mainly systematic (model, theory or processing), not random noise. Check the items below one by one.",
    "低 k 段（": "Low-k segment (", " Å⁻¹）残差是中位数的 ": " Å⁻¹) residual is ",
    " 倍：低 k 受背景扣除与近边效应影响最大。试：kmin 提高 0.5（看稳健性检查）、调 rbkg、或换 FEFF8L 自洽势。":
        "× the median: low k is most affected by background removal and near-edge effects. Try: kmin +0.5 (see robustness check), adjust rbkg, or use the FEFF8L self-consistent potential.",
    "高 k 段残差偏大：多为噪声。考虑降低 kmax（看 ② 质量检查的 k_snr3）或多次扫描合并。":
        "Large high-k residual: mostly noise. Consider lowering kmax (see k_snr3 in ② Quality check) or merging more scans.",
    " 处残差尖峰（": " residual spike (", "× 局部噪声）": "× local noise)",
    "，约对应 E = ": ", about E = ",
    " eV：到 ② 质量检查 → 去毛刺，与平滑趋势比较其前后各点，区间要包含所有偏离点。":
        " eV: go to ② Quality check → Deglitch, compare the neighbouring points with the smooth trend, and include every deviating point in the range.",
    "：检查是否为毛刺。": ": check whether it is a glitch.",
    " Å 局部失配 ": " Å local misfit ",
    "：该处可能缺路径或无序分布不是高斯型。加路径前先在已知结构的标样上验证，加入后用 F 检验（⑨ 页），p < 0.05 才保留。":
        ": a path may be missing there or the disorder is not Gaussian. Validate any new path on a known standard first, then F-test it (page ⑨); keep it only if p < 0.05.",
    "窗口外失配大是正常的（那里不参与拟合）；若想拟合更远的壳层，扩大 Rmax 并加入相应路径，N_idp 也随之增加。":
        "Large misfit outside the window is normal (it is not fitted); to fit farther shells, increase Rmax and add the corresponding paths (N_idp increases too).",
    "FEFF 版本": "FEFF version", "运行 FEFF8L": "Run FEFF8L", "SCF 自洽半径 (Å)": "SCF radius (Å)",
    "交换势 EXCHANGE": "Exchange potential (EXCHANGE)", "Hedin-Lundqvist（默认）": "Hedin-Lundqvist (default)",
    "部分非局域": "partially non-local", "FEFF6L（非自洽势）": "FEFF6L (non-self-consistent potential)",
    "FEFF 运行中…（FEFF8L 自洽计算约 1–3 分钟）": "Running FEFF… (FEFF8L self-consistency takes about 1–3 min)",
    "FEFF8L 自洽势：SCF 半径 ": "FEFF8L self-consistent potential: SCF radius ", " Å，交换势 ": " Å, exchange ",
    "，费米能 ": ", Fermi level ",
    "一般取包含 2–3 个壳层（约 30–60 个原子）；越大越慢": "Usually 2–3 shells (about 30–60 atoms); larger is slower",
    "FEFF6L：非自洽势，几秒。FEFF8L：自洽势（SCF），约 1–3 分钟，ΔE0 通常更接近 0。两者路径编号一般相同，但 ΔE0 零点不同：换版本后固定 e0 的模型要重新确定 e0。":
        "FEFF6L: non-self-consistent potential, seconds. FEFF8L: self-consistent potential (SCF), about 1–3 min, ΔE0 usually closer to 0. Path numbering is normally the same, but the ΔE0 zero differs: after switching, re-determine e0 in models that fix it.",
    # ---- ⑧ 拟合
    "运行已保存的模型（models/ 中 ": "Run a saved model (", " 个）": " in models/)", "运行": "Run", "拟合中…": "Fitting…",
    "完成，结果见下方与“⑨ 拟合历史”": "Done; see below and “⑨ Fit history”",
    "在下方建立模型并点“保存结果”后，模型会存入 models/，以后可在这里一键重跑。":
        "Build a model below and click “Save results”; it is stored in models/ and can be rerun here with one click.",
    "需要：⑤ 中已计算 χ(k) 的数据 + ⑦ 中的 FEFF 计算": "Requires data with χ(k) (⑤) and a FEFF calculation (⑦)",
    "数据": "Data", "FEFF 目录（可多选，多物相/多位点）": "FEFF folders (multiple allowed: phases / sites)", "1. 拟合范围": "1. Fit range",
    "窗": "Window", "拟合空间": "Fit space", "**；参数上限建议 ≤ N_idp/2 = **": "**; recommended max. variables ≤ N_idp/2 = **",
    "2. 路径（勾选使用；N 留空=FEFF 简并度；均可写表达式）": "2. Paths (tick to use; empty N = FEFF degeneracy; expressions allowed)",
    "3. 参数（vary=否 即固定；expr 非空 即约束）": "3. Parameters (vary unticked = fixed; expr not empty = constraint)",
    "变量数 = ": "Variables = ", "（N_idp/2 = ": " (N_idp/2 = ", "模型名": "Model name", "拟合": "Fit", "R 因子": "R-factor",
    "变量数": "Variables", "模型": "Model", "显示 k 权重": "Displayed k-weight", "χ(R)（未相移校正）": "χ(R) (not phase-corrected)",
    "|χ(R)| 数据": "|χ(R)| data", "|χ(R)| 拟合": "|χ(R)| fit", "Re 数据": "Re data", "Re 拟合": "Re fit",
    "完整拟合报告 (feffit_report)": "Full fit report (feffit_report)", "保存结果到 output/fits/exafs_fits.csv": "Save results to output/fits/exafs_fits.csv",
    "已保存：output/fits/exafs_fits.csv、output/fits/*.fit_report.txt、models/*.json、output/figs/*_fit.png":
        "Saved: output/fits/exafs_fits.csv, output/fits/*.fit_report.txt, models/*.json, output/figs/*_fit.png",
    "稳健性检查：改变拟合条件重复拟合": "Robustness check: refit with changed fit conditions",
    "依次改变 kmin ±0.5、kmax ±1、Rmax ±0.2 Å，以及（多 k 权重时）单独用 k¹/k²/k³，看各变量的变化是否超过其统计误差（离散度/误差 > 1 记为“不稳”）。":
        "Changes kmin ±0.5, kmax ±1, Rmax ±0.2 Å and (for multiple k-weights) k¹/k²/k³ alone, and checks whether each variable changes more than its statistical error (spread/error > 1 = “unstable”).",
    "运行稳健性检查": "Run robustness check", "不稳的参数：": "Unstable parameters: ",
    "。结论应以多种条件下的范围报告，或检查模型。": ". Report the range over conditions, or revise the model.",
    "所有变量随拟合条件的变化都在统计误差以内。": "All variables stay within their statistical errors when the fit conditions change.",
    "保存到 output/fits/": "Save to output/fits/", "已保存 output/fits/": "Saved output/fits/",
    "基准": "baseline", "条件": "condition", "参数": "parameter", "基准值": "baseline value", "基准误差": "baseline error",
    "最小": "min", "最大": "max", "离散度_误差比": "spread/error", "离散度": "spread", "判断": "verdict", "不稳": "unstable", "稳定": "stable",
    "错误": "error",
    # ---- ⑨ 历史 / ⑩ LCF / ⑪
    "暂无拟合": "No fits yet", "把以上全部拟合保存到 output/fits/（汇总报告会用到）": "Save all fits above to output/fits/ (used by the summary report)",
    "已保存 ": "Saved ", " 个拟合": " fits", "查看拟合": "View fit", "F 检验（Hamilton）：嵌套模型比较": "F-test (Hamilton): nested model comparison",
    "简单模型": "Simpler model", "复杂模型": "More complex model", "比较": "Compare", "至少需要两条谱": "At least two spectra are needed",
    "样品": "Sample", "端点标样（必须是实测标样）": "End members (must be measured standards)", "空间": "Space",
    "下限 (eV 相对E0 或 k)": "Lower limit (eV rel. E0, or k)", "上限": "Upper limit", "权重和=1": "Weights sum to 1",
    "拟合能量平移": "Fit energy shift", "备注（如使用非实测端点，必须在此注明为假设）": "Note (non-measured end members must be declared as assumptions here)",
    "单一标样拟合比较：": "Comparison with single-standard fits:", "所有组合（按 R 因子排序）：": "All combinations (sorted by R-factor):",
    "结果追加到 output/lcf/lcf_results.csv": "Results appended to output/lcf/lcf_results.csv",
    "样品化学式": "Sample formula", "目标元素": "Target element", "压片面积 (cm²)": "Pellet area (cm²)", "稀释剂（空=无）": "Diluent (empty = none)",
    "稀释剂质量 (mg)": "Diluent mass (mg)", "目标总 μt": "Target total μt", "样品质量 (mg，0=只推荐)": "Sample mass (mg; 0 = recommend only)",
    "体系中全部元素（干扰边检查）": "All elements in the system (interfering-edge check)", "扫描上限 (eV)": "Scan upper limit (eV)",
    "数据：xraydb (Elam 表)。总 μt 1.5–2.6 最佳，Δμt ≥ 0.2；均匀性比 Δμt 精确匹配更重要。":
        "Data: xraydb (Elam tables). Total μt 1.5–2.6 is best, Δμt ≥ 0.2; homogeneity matters more than matching Δμt exactly.",
    "推荐样品质量 **": "Recommended sample mass **", " mg** → 边后总 μt=": " mg** → total μt above edge = ", "，边跳 Δμt=": ", edge step Δμt = ",
    # ---- ⑫ 汇总
    "把项目中**已保存**的全部结果整理成一个 **Excel 工作簿** 和一份 **带图的 HTML 报告**：样品清单、能量校准、质量检查、处理结果、EXAFS 拟合（每个模型一行的概要 + 每条路径的参数）、LCF、处理参数。":
        "Collects all **saved** results of the project into an **Excel workbook** and an **HTML report with figures**: samples, energy calibration, quality check, processing results, EXAFS fits (one summary row per model + per-path parameters), LCF and processing parameters.",
    "本次会话有 ": "This session has ", " 个拟合。只有保存过的拟合会进入汇总。": " fits. Only saved fits enter the summary.",
    "先把本次会话的全部拟合保存": "Save all fits of this session first", "已保存": "Saved", "生成汇总": "Generate summary",
    "整理中…": "Collecting…", "已生成：": "Created: ", "下载 汇总.xlsx": "Download summary .xlsx", "下载 汇总报告.html": "Download report .html",
    "打开汇总文件夹": "Open summary folder", "HTML 报告与 figs/ 文件夹放在一起才能显示图；用“打开汇总文件夹”后双击 汇总报告.html。":
        "The HTML report shows figures only next to its figs/ folder: use “Open summary folder” and double-click the .html file.",
    "预览": "Preview", "表": "Table", "项目中还没有结果：先在“⓪ 项目 → 一键处理”中处理，再做拟合。":
        "No results yet: process data in “⓪ Project → One-click processing”, then fit.",
    "自动生成“方法”段落": "Generate a “Methods” paragraph",
    "只写项目文件中有记录的事实（校准参比、ΔE、归一化/背景/FT 参数、拟合范围、N_idp、S0² 来源、软件版本）。光源、线站等信息在下面填写（保存到 xafsmith.json）；没填的用【方括号】占位。生成的是草稿，投稿前请逐句核对。":
        "Only facts recorded in the project are written (calibration references, ΔE, normalization/background/FT parameters, fit ranges, N_idp, S0² source, software versions). Fill in facility and beamline below (saved to xafsmith.json); missing items appear as [placeholders]. This is a draft: check every sentence before submission.",
    "光源": "Facility", "线站": "Beamline", "单色器": "Monochromator", "探测方式 / 探测器": "Detection / detectors",
    "保存仪器信息": "Save instrument information", "已保存到 xafsmith.json": "Saved to xafsmith.json",
    "范围：只写这些样品（空 = 全部使用中的样品）": "Scope: only these samples (empty = all samples in use)", "生成方法段落": "Generate methods paragraph",
    "**中文**": "**Chinese**",
    # ---- 更新
    "有新版本 ": "New version ", "（当前 ": " available (current ", "开发安装：请在源码目录用 git pull 更新。":
        "Development install: update with git pull in the source folder.", "更新到最新版": "Update to latest version",
    "正在从 GitHub 下载并安装（约 1–5 分钟）…": "Downloading and installing from GitHub (1–5 min)…",
    "更新完成：请关闭 XAFSmith 窗口并重新打开。": "Update finished: close the XAFSmith window and open it again.",
    "更新失败（可能没有联网）。": "Update failed (no internet connection?).", "检查更新": "Check for updates",
    "启动时自动检查新版本（只访问 github.com，不发送任何数据）": "Check for new versions at start-up (contacts github.com only; no data is sent)",
    "现在检查": "Check now", "无法连接 GitHub（离线或被网络阻止）。": "Cannot reach GitHub (offline or blocked).", "已是最新版本 ": "Up to date: version ",
    # ---- ⑬ XANES
    "先在 ① 数据导入 中载入样品（归一化参数与 ④ 页相同）": "Load samples in ① Import data first (normalization as on page ④)",
    "边位置同时受价态、配位数和配体影响：价态标定只适用于配体相同、结构相近的标样与样品。":
        "Edge positions depend on oxidation state, coordination and ligands: valence calibration is only valid for standards and samples with the same ligands and similar structures.",
    "边位置与白线": "Edge position & white line", "价态标定": "Valence calibration", "边前峰拟合": "Pre-edge peak fitting",
    "白线积分区间：E0 至 E0 + (eV)": "White-line integration: E0 to E0 + (eV)",
    "E0_deriv：导数最大值；E_half：归一化 μ = 0.5 处；WL_E / WL_height：白线峰位与峰高；WL_area：E0 至 E0+区间内归一化 μ 超过 1 部分的面积（eV）。":
        "E0_deriv: derivative maximum; E_half: where normalized μ = 0.5; WL_E / WL_height: white-line position and height; WL_area: area of normalized μ above 1 between E0 and E0+window (eV).",
    "保存到 output/xanes/xanes_features.csv": "Save to output/xanes/xanes_features.csv", " 条（同名样品覆盖）": " rows (same sample names overwritten)",
    "1. 选**已知价态的实测标样**并填写价态；2. 选边位置的定义；3. 选要估算的样品。":
        "1. Select **measured standards of known valence** and enter the valence; 2. choose the edge-position definition; 3. select samples to estimate.",
    "标样": "Standards", "边位置定义": "Edge-position definition", "E_half（半高点）": "E_half (half height)",
    "E0_deriv（导数最大值）": "E0_deriv (derivative max.)", "WL_E（白线峰位）": "WL_E (white-line peak)", "价态": "valence",
    "**·价态 + **": "**·valence + **", "** eV；R² = ": "** eV; R² = ", "；斜率误差 ": "; slope error ", " eV/价（": " eV per valence unit (",
    " 个标样）": " standards)", "只有 2 个标样：直线没有统计误差，估算的价态误差未知。":
        "Only 2 standards: the line has no statistical error, so the valence uncertainty is unknown.",
    "要估算价态的样品": "Samples to estimate", "边位置": "edge position", "外推": "extrapolated", "是": "yes", "标定直线": "calibration line",
    "误差只来自标定直线的统计误差，不含标样与样品化学环境的差异；超出标样价态范围的为外推。":
        "Errors include only the statistical error of the calibration line, not differences in chemical environment; values outside the standards' range are extrapolations.",
    "保存价态估算到 output/xanes/": "Save valence estimates to output/xanes/", "已保存 output/xanes/valence_": "Saved output/xanes/valence_",
    "区间下限 E−E0 (eV)": "Range start E−E0 (eV)", "区间上限 E−E0 (eV)": "Range end E−E0 (eV)", "峰数": "Peaks", "主边基线": "Edge baseline",
    "模型：n 个高斯峰（σ ≤ 2.5 eV）+ 台阶（代表主边上升沿，中心限制在半高点 ±6 eV）+ 常数。看分量图判断基线是否合理；峰位贴边或面积≈0 时会提示。":
        "Model: n Gaussians (σ ≤ 2.5 eV) + step (rising main edge, centre within ±6 eV of the half-height point) + constant. Check the components; warnings appear when a peak sits at the range limit or has ≈0 area.",
    "拟合边前峰": "Fit pre-edge peaks", "总面积 **": "Total area **", "** eV；面积加权质心 **": "** eV; area-weighted centroid **",
    "** eV；R 因子 ": "** eV; R-factor ", "残差": "residual", "保存边前峰结果到 output/xanes/": "Save pre-edge results to output/xanes/",
    # ---- ⑭ 出图
    "统一字体（Arial）、线宽、色盲友好配色；导出 600 dpi TIFF（LZW）/ PNG 与矢量 SVG / PDF，并写一个英文图注 .txt（样品、边、模式、处理参数）。R 空间横轴注明 not phase-corrected。":
        "Consistent font (Arial), line widths and colour-blind-safe colours; exports 600 dpi TIFF (LZW) / PNG and vector SVG / PDF plus an English caption .txt (sample, edge, mode, processing parameters). R axes are labelled “not phase-corrected”.",
    "图类型": "Figure type", "尺寸": "Size", "格式": "Formats", "文件名": "File name", "归一化 XANES": "Normalized XANES",
    "XANES 导数": "XANES derivative", "拟合（k + R）": "Fit (k + R)", "单栏 85 mm": "single column 85 mm",
    "1.5 栏 120 mm": "1.5 column 120 mm", "双栏 178 mm": "double column 178 mm", "汇报 16:9": "slide 16:9",
    "本次会话还没有拟合：在 ⑧ 中拟合，或在 ⑧ 顶部运行已保存的模型。": "No fits in this session: fit in ⑧, or run a saved model at the top of ⑧.",
    "R 上限": "R max", "先在 ① 中载入样品": "Load samples in ① first", "，并在 ⑤ 中计算 χ(k)": " and compute χ(k) in ⑤",
    "谱（按顺序作图）": "Spectra (plotted in this order)", "错开量": "Offset", "化学式下标（IrO2→IrO₂）": "Formula subscripts (IrO2→IrO₂)",
    "E−E0 下限": "E−E0 min", "E−E0 上限": "E−E0 max", "同时画 Re χ(R)（虚线）": "Also plot Re χ(R) (dashed)", "图注：": "Caption: ",
    "保存到 output/figs/journal/": "Save to output/figs/journal/", "已保存：": "Saved: ", "下载 ": "Download ",
    # ---- .prj
    "导出为 Athena 项目（.prj），在 Athena / Artemis 中对照": "Export as Athena project (.prj) for cross-checking in Athena / Artemis",
    "写入已校准的能量与 μ(E)，以及本软件用的 E0、边前/边后范围、rbkg、k 范围、窗函数；Athena 打开后按这些参数重新计算，可直接与本软件的结果对比。":
        "Writes calibrated energy and μ(E) together with the E0, pre/post-edge ranges, rbkg, k range and window used here; Athena recomputes with these parameters, so results can be compared directly.",
    "导出 .prj": "Export .prj", "下载 .prj": "Download .prj", " 条谱）": " spectra)", " 条谱": " spectra",
    # ---- 其他模块的提示
    " eV 超出 ±10 eV，检查 E0 定义或模型": " eV is outside ±10 eV: check the E0 definition or the model", " < 0，非物理": " < 0, unphysical",
    "p<0.05 时加入的参数/路径显著": "added parameters/paths are significant if p < 0.05", "自由度不足": "not enough degrees of freedom",
    "至少需要两个不同价态的标样": "At least two standards of different valence are needed", "拟合区间内数据点太少": "Too few data points in the fit range",
    "峰 ": "Peak ", " 的位置贴近拟合区间边界（": " sits at the edge of the fit range (", " eV）：调整区间或减少峰数": " eV): adjust the range or use fewer peaks",
    " 面积≈0：该峰不需要": " has ≈0 area: this peak is not needed", "台阶中心贴近下限：主边基线可能没有拟合好": "Step centre at its lower bound: the edge baseline may be poor",
    ": 需要先归一化": ": normalize first",
    "缺少项目标识文件（用 xafsmith new 创建项目，或 xafsmith init 生成）": "Project marker file missing (create with xafsmith new, or run xafsmith init)",
    "edges 为空（xafsmith init 会按 meta.csv 生成）": "edges is empty (xafsmith init generates it from meta.csv)",
    "尚无 meta.csv（把原始数据放进 data/raw/<批次>/ 后运行 xafsmith init）": "No meta.csv yet (put raw data in data/raw/<batch>/ and register it)",
    "警告": "warning", "目录不存在（xafsmith init 会创建）": "folder missing (will be created)",
    "缺少 elements_in_sample（干扰边检查需要）": "elements_in_sample missing (needed for the interfering-edge check)",
    "个别样品改参数必须在 overrides_reason 写理由": "per-sample parameter changes need a reason in overrides_reason",
    "去毛刺必须在 deglitch_reason 写理由": "deglitching needs a reason in deglitch_reason", "原始文件不存在": "raw file missing",
    "mode 应为 trans / fluo": "mode must be trans / fluo", "use 应为 0 或 1": "use must be 0 or 1", "use=0 必须在 note 写理由": "use=0 needs a reason in note",
    "没有参比 ref_file：不能校准（数据标准要求每条谱与同批参比一起处理）": "no reference ref_file: cannot calibrate (each spectrum must be processed with a same-batch reference)",
    "同名样品跨吸收边（同名多行会被合并）": "same sample name across edges (rows with the same name are merged)",
    "同名样品混合透射与荧光": "same sample name mixes transmission and fluorescence", "级别": "level", "位置": "location", "说明": "message",
    "缺少列 ": "missing column ", "role 应为 ": "role must be ", " 中没有吸收边 ": " has no edge ", " 样品 ": " sample ", "样品 ": "sample ",
    " 不在 meta.csv 中": " is not in meta.csv", " 个 FEFF 路径文件不存在（先运行 xafsmith feff），如 ": " FEFF path files missing (run FEFF first), e.g. ",
    "缺少字段 ": "missing field ", " 在 meta.csv 中不是 role=reference": " is not role=reference in meta.csv", "JSON 解析失败：": "JSON parse error: ",
    "无法读入：": "cannot read: ", " 缺少 ": " missing ", " 第 ": " row ", " 行（": " (",
    "本批次无同边参比：请在 ref_file 填参比文件": "no same-edge reference in this batch: fill in ref_file",
    "：meta.csv 未指定参比 ref_file，不能校准（必须与参比一起处理）": ": no reference ref_file in meta.csv, cannot calibrate (must be processed with a reference)",
    "meta.csv 中没有可用的样品 ": "meta.csv has no usable sample ", " 条谱没有参比，不能处理：": " spectra have no reference and cannot be processed: ",
    # ---- 表头 / 工作表 / 其他
    " 次": "", "校准": "Calibration", "质量检查": "Quality check", "处理结果": "Processing results",
    "拟合概要": "Fit overview", "EXAFS拟合": "EXAFS fits", "处理参数": "Processing parameters", "说明与引用": "Notes & citation",
    "角色": "Role", "批次": "Batch", "扫描数": "Scans", "使用": "Used", "备注": "Note", "表值来源": "Table source",
    "参比测量时间": "Reference time", "谱数": "Spectra", "与样品最大时间差_h": "Max. time gap (h)", "样品元素": "Elements",
    "当前ΔE": "Current ΔE", "状态": "Status", "与参比时间差_h": "Time gap to reference (h)",
    "边跳 ≥ 0.2，可行": "edge step ≥ 0.2: feasible",
    "边跳 < 0.2：目标元素太稀，考虑减少稀释剂/基体，或改用荧光":
        "edge step < 0.2: target element too dilute — reduce diluent/matrix or use fluorescence",
    "边跳 Δμt=": "edge step Δμt = ", "条件": "condition", "R因子": "R-factor", "定义": "definition", "斜率": "slope",
    "截距": "intercept",
    # ---- 去毛刺 / 批量运行模型
    "去毛刺（删除单色器毛刺等假象点）": "Deglitch (remove monochromator glitches and other artefacts)",
    "判断标准：毛刺只占 1–3 个点、宽度远小于 EXAFS 振荡（k≈5 Å⁻¹ 时一个振荡约 30 eV），":
        "A glitch spans 1–3 points and is much narrower than an EXAFS oscillation (~30 eV at k≈5 Å⁻¹), ",
    "且常在多个样品的同一能量出现、I0 在该处也有凹陷。真实结构不要删。":
        "often appears at the same energy in several samples and coincides with a dip in I0. Never remove real structure. ",
    "区间用**校准后**能量；写进 xafsmith.json 的 deglitch，原始文件不动，命令行与图形界面都按它处理。":
        "Ranges use **calibrated** energy and are stored under deglitch in xafsmith.json; raw files are untouched and both GUI and command line use them.",
    "需要项目的 meta.csv 与 xafsmith.json": "Requires the project's meta.csv and xafsmith.json",
    "先在 ① 页“按 meta 载入”样品。": "First load samples from meta on page ①.",
    "样品（同一区间用于所选全部样品）": "Samples (the same ranges apply to all selected)",
    "归一化 μ(E)（依次上移 0.1）": "Normalized μ(E) (offset 0.1 each)",
    "I0 / 中位数": "I0 / median",
    "灰色虚线 = QC 标出的疑似毛刺；红色区域 = 已删除的区间。可用鼠标框选放大。":
        "Grey dotted = glitches flagged by QC; red = removed ranges. Drag to zoom.",
    "删除区间（eV，校准后；多个用 ; 分隔）": "Ranges to remove (eV, calibrated; separate with ;)",
    "理由（必填）": "Reason (required)",
    "保存并重新载入": "Save and reload",
    "清除所选样品的去毛刺": "Clear deglitching of selected samples",
    "请填写理由": "Please give a reason",
    "已写入 xafsmith.json 并重新载入 ": "Saved to xafsmith.json and reloaded ",
    " 个样品；请重新运行 QC 确认": " sample(s); rerun QC to confirm",
    "样品（可多选：同一模型依次用于每个样品）": "Samples (multiple: the model is applied to each in turn)",
    "完成 ": "Done: ",
    " 个拟合，结果见下方与“⑨ 拟合历史”": " fit(s); see below and “⑨ Fit history”",
    "无法识别": "Cannot parse",
    "，格式为 起始-结束，如 9984.5-9990": "; use start-end, e.g. 9984.5-9990",
}
# 最后替换的中文标点
PUNCT = [("（", " ("), ("）", ")"), ("，", ", "), ("。", ". "), ("：", ": "), ("；", "; "), ("、", ", "),
         ("“", "“"), ("”", "”"), ("【", "["), ("】", "]"), ("！", "! "), ("？", "? ")]
_KEYS = sorted((k for k in EN if len(k) >= 3 or k.startswith(" ")), key=len, reverse=True)
_SHORT = {k: v for k, v in EN.items() if len(k) < 3 and not k.startswith(" ")}


def tr(s):
    """把界面文字翻译为当前语言（中文时原样返回）"""
    if LANG != "en" or not isinstance(s, str) or not CJK.search(s):
        return s
    if s in EN:
        return EN[s]
    if s.strip() in _SHORT:
        return s.replace(s.strip(), _SHORT[s.strip()])
    out = s
    for k in _KEYS:
        if k in out:
            out = out.replace(k, EN[k])
            if not CJK.search(out):
                break
    for a, b in PUNCT:
        out = out.replace(a, b)
    return re.sub(r" {2,}(?=\S)", " ", out) if "  \n" not in out else out


def _tr_options(kw, args, pos):
    """为选项列表中含中文的控件加上 format_func=tr（只改显示，不改取值）"""
    opts = kw.get("options", args[pos] if len(args) > pos else None)
    if "format_func" not in kw and opts is not None:
        try:
            if any(isinstance(o, str) and CJK.search(o) for o in opts):
                kw["format_func"] = tr
        except TypeError:
            pass


_TEXT_FIRST = ["title", "header", "subheader", "markdown", "caption", "text", "info", "warning", "error", "success",
               "toast", "button", "download_button", "checkbox", "toggle", "number_input", "text_input", "text_area",
               "file_uploader", "expander", "metric", "slider", "select_slider", "date_input", "color_picker",
               "form_submit_button", "link_button", "popover", "status"]
_OPTION_WIDGETS = {"radio": 1, "selectbox": 1, "multiselect": 1, "pills": 1, "segmented_control": 1}


def _wrap(fn, name):
    def w(self, *args, **kw):
        if LANG == "en":
            if args and isinstance(args[0], str):
                args = (tr(args[0]),) + tuple(args[1:])
            for k in ("label", "body", "help", "placeholder", "text"):
                if isinstance(kw.get(k), str):
                    kw[k] = tr(kw[k])
            if name in _OPTION_WIDGETS:
                _tr_options(kw, args, _OPTION_WIDGETS[name])
            if name == "tabs" and args and isinstance(args[0], (list, tuple)):
                args = ([tr(x) for x in args[0]],) + tuple(args[1:])
            if name in ("dataframe", "table") and args and hasattr(args[0], "rename"):
                df = args[0]
                args = (df.rename(columns=lambda c: tr(c) if isinstance(c, str) else c),) + tuple(args[1:])
            if name == "plotly_chart" and args:
                translate_figure(args[0])
            if name == "write" and args:
                args = tuple(tr(a) if isinstance(a, str) else a for a in args)
        return fn(self, *args, **kw)
    w.__wrapped__ = fn
    w.__name__ = getattr(fn, "__name__", name)
    return w


def install(st):
    """给 Streamlit 的显示函数加翻译（每个进程只装一次；语言由 LANG 决定）"""
    from streamlit.delta_generator import DeltaGenerator as DG
    if getattr(DG, "_xafsmith_i18n", False):
        return
    names = _TEXT_FIRST + list(_OPTION_WIDGETS) + ["tabs", "dataframe", "table", "write", "plotly_chart"]
    for n in names:
        f = getattr(DG, n, None)
        if f is not None:
            setattr(DG, n, _wrap(f, n))
    main = getattr(st, "_main", None)
    for n in names:                     # st.button 等是模块导入时绑定好的方法，需重新绑定
        if main is not None and hasattr(main, n):
            setattr(st, n, getattr(main, n))
    _spin = st.spinner

    def spinner(text="", *a, **k):
        return _spin(tr(text), *a, **k)
    st.spinner = spinner
    DG._xafsmith_i18n = True


def translate_figure(fig):
    """plotly 图：坐标轴标题、图例名、子图标题"""
    if LANG != "en":
        return fig
    for tr_ in fig.data:
        if isinstance(getattr(tr_, "name", None), str):
            tr_.name = tr(tr_.name)
    lay = fig.layout
    for ax in [k for k in lay if k.startswith("xaxis") or k.startswith("yaxis")]:
        t = lay[ax].title.text
        if isinstance(t, str):
            lay[ax].title.text = tr(t)
    for a in lay.annotations or []:
        if isinstance(a.text, str):
            a.text = tr(a.text)
    return fig
