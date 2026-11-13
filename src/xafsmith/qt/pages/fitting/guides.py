"""拟合注意事项（中英文，三个标签页：拟合前 / 拟合得好的标准 / 多数据集联合拟合）与弹窗。"""

from __future__ import annotations

from ... import widgets as W
from ...widgets import T


BEFORE_ZH = """
<h3>数据先过关</h3>
<ul>
<li><b>先看数据，再拟合</b>：逐条检查扫描（毛刺、能量漂移、首次扫描异常）再平均；去毛刺区间要盖住整个尖峰（尖峰两侧偏高/偏低的点也要去掉），
否则 χ(k) 上会留下一上一下的尖峰，R 空间出现周期性波纹，拟合永远“对不齐”。</li>
<li><b>可用的 k 上限</b>：先用“吸收边查询”或 <code>xafsmith kcheck</code> 列出扫描范围内的其他吸收边（同元素 L₂/L₁、共存元素），换算成 k；
这个上限之后的数据不能用。没有这一步不要选 k 范围。</li>
<li><b>荧光数据</b>：总 μt 不远小于 0.2 时有自吸收，会压低振幅（N 偏小、σ² 偏大）；与透射数据不能直接比较 N。</li>
</ul>
<h3>拟合前</h3>
<ul>
<li><b>先标样、后样品</b>：在结构已知的标样上拟合得到 S0²（通常 0.7–1.0），样品中固定为这个值（在“校准与处理 → 处理参数”中记录来源）。
S0² 与配位数 N 完全相关，两者不能同时自由。标样本身要结构良好：纳米晶或部分无序的标样给出的 S0² 偏低。</li>
<li><b>数据范围</b>：k 范围按全组最差样品的信噪比定，全组相同；R 窗口只包含要拟合的壳层。先看独立点数 N_idp = 2ΔkΔR/π。</li>
<li><b>变量数</b> ≤ N_idp/2（最好 ≤ N_idp − 3）。参数不够时用约束：相近壳层共用 ΔE0，多重散射路径的 σ²、ΔR 与对应单散射绑定（共线 M–O–M 路径与单散射壳层共用 σ²）。</li>
<li><b>同时用 k¹、k²、k³ 拟合</b>（k 权重多选），可降低 N–σ²、ΔE0–ΔR 的相关性。</li>
<li><b>从简单到复杂</b>：先第一壳层，再逐条加路径；每加一条都与前一个模型做 F 检验（“拟合历史”页）。</li>
<li><b>同一组样品用同一模型比较</b>：加入或去掉一条路径会改变其他参数的绝对值（例如外壳层 σ² 会随邻近的轻散射体路径一起变）；
样品之间的趋势只在同一模型、同一范围内比较。</li>
<li><b>换 FEFF 版本（FEFF6 ↔ FEFF8）要重新确定 ΔE0</b>：两者能量零点不同（可差几 eV）；沿用另一版本下固定的 ΔE0 会使 ΔR 偏移。</li>
<li><b>软约束只在有独立先验时用</b>：例如 S0² 取标样拟合的值 ± 误差；σ 填先验的报告误差（与本软件的参数误差同一尺度）；结果里偏离超过 2σ 要查先验来源或模型。软约束不同的模型不能用 F 检验比较。</li>
<li><b>FT 峰位不是键长</b>：未相移校正的峰位比真实距离短约 0.3–0.5 Å；一个小峰不等于一个壳层（可能是噪声、背景残余、窗函数旁瓣或多重散射）。</li>
</ul>
<h3>别追求严丝合缝</h3>
<p>“严丝合缝”不是目标：残差已接近噪声时，再加参数只是在拟合噪声。若标样与样品的窗口内残差相近，剩下的是理论/处理的下限，不是样品模型缺路径。
详见“使用指南 → 拟合质量提升教程”。</p>
"""

GOOD_ZH = """
<p>拟合后，右侧结果的“质量检查”标签页会逐条判断下面各项（多数据集时按当前选中的数据集判断，变量数与全部数据集的 N_idp 之和比较）。</p>
<h3>数字</h3>
<ul>
<li><b>R 因子</b>：&lt; 0.02 很好；0.02–0.05 对第一壳层可接受；含外壳层（到 3–4 Å）、荧光或原位数据时 0.03–0.06 常见；&gt; 0.05 时先查模型、R 窗口与数据。
R 因子随窗口变宽而变大，只在相同范围之间比较。</li>
<li><b>残差 / 噪声</b>（“诊断”标签）：≈ 1–2 表示已到数据极限；明显大于 2 说明还有系统偏差（看诊断给出的 k 段与 R 段）。</li>
<li><b>χ²_ν</b>：绝对值依赖噪声估计，常远大于 1；参数误差已按 √χ²_ν 放大。用来比较<b>同一数据、同一范围</b>下的不同模型（明显下降才有意义）。</li>
<li><b>F 检验</b>：新加的壳层 / 参数 p &lt; 0.05 才能报告为“观察到”；p 在 0.05–0.1 之间只能说“可能”，并需要独立证据（小波、不同 k 权重、其他表征）。</li>
</ul>
<h3>参数</h3>
<ul>
<li><b>物理合理</b>：|ΔE0| ≤ 10 eV；σ² &gt; 0，一般 0.001–0.02 Å²（室温第一壳层多为 0.002–0.010；外壳层与无序样品可到 0.02–0.03）；
ΔR 不应偏离 FEFF 结构超过约 0.2 Å；N 在合理范围内且误差明显小于数值。</li>
<li><b>误差可估</b>：每个变量都有误差；误差大于数值本身，说明数据不能确定这个参数，应固定或约束。</li>
<li><b>不卡边界</b>：参数停在设定的上下限上，说明是限制在起作用，结果不可信。</li>
<li><b>相关系数</b> |r| &gt; 0.9 的参数对要在结论中说明（典型：N–σ²、S0²–N、ΔE0–ΔR）；ΔE0 与 ΔR 相关时键长结论要谨慎。</li>
<li><b>误差的来源</b>：报告的误差只来自拟合（协方差 × χ²_ν）；只有 1 次扫描时没有独立的误差估计，要在结论中写明。</li>
</ul>
<h3>图与稳健性</h3>
<ul>
<li><b>图上</b>：窗口内 |χ(R)| 与 Re χ(R) 都要对上，Re 对上比 |χ(R)| 对上更严格；k 空间残差不集中在某一段。</li>
<li><b>稳健</b>：改变 kmin、kmax、Rmax 与 k 权重后结论不变（“稳健性”标签）。σ² 等趋势对 kmin 敏感时，不能作为结论。</li>
<li><b>与模型无关的指标</b>：样品间的定性变化（如外壳层变弱）最好同时用模型无关的量支撑（R 空间峰高比、χ(k) LCF、小波），不只靠一个拟合参数。</li>
</ul>
<h3>陈述分三类</h3>
<p><b>实测</b>（数据直接可见）、<b>拟合结果</b>（依赖模型与假设）、<b>推测</b>（需进一步实验）——写结论时分开。</p>
"""

JOINT_ZH = """
<p>多个数据集联合拟合：几条谱同时拟合，<b>同名参数在数据集之间共享</b>，名字不同就各自独立。拟合页卡片 1 选“多个数据集联合”即可。</p>
<h3>什么时候用</h3>
<ul>
<li>同一体系的一组样品（时间、电位、温度序列），某些量在物理上应当相同（同一 FEFF 计算的 ΔE0、不变的第一壳层距离、同一拓扑的外壳层距离）。</li>
<li>弱的外壳层在单独拟合中定不下来：共享距离与 ΔE0 后，全组一起约束，弱壳层的 σ² 能从相关参数里分离出来。</li>
<li>多温度数据（σ² 随温度变化、距离共享）；同一样品的两个吸收边（共享键长）。</li>
<li>不适合：样品之间结构本来就不同、找不到真正应当相同的参数——这时联合拟合只是把几个单独拟合放在一起。</li>
</ul>
<h3>怎么设</h3>
<ul>
<li><b>数据集</b>：选 ≥ 2 条谱；FEFF 目录全组共用一份。</li>
<li><b>路径</b>：每个数据集一张路径表（标签页）；“把本页路径表复制到其他数据集”后再改。<b>要共享的参数写同一个名字，要各自独立的改名</b>（如 ss2_A、ss2_B）。</li>
<li><b>范围</b>：卡片 2 是共同范围；每个数据集可单独覆盖 kmin、kmax、Rmin、Rmax（噪声大的谱可截短 k）。N_idp 按各数据集之和计。</li>
<li><b>参数</b>：一张共享参数表，变量数与 Σ N_idp/2 比较。</li>
<li>同一条谱不要放进两个数据集：同一数据计入两次，误差被低估（软件会警告）。</li>
</ul>
<h3>共享什么、不共享什么</h3>
<ul>
<li>通常共享：ΔE0（同一边、同一 FEFF、同一 E0 定义）；已知不变的距离。S0² 仍按标样固定。</li>
<li>通常各自独立：要比较的量（σ²、N）。</li>
<li><b>共享是假设，要写进结论</b>。先做单独拟合：若某参数在单独拟合中相差超过约 2σ，就不该共享；联合结果应落在单独拟合的误差范围内。</li>
</ul>
<h3>统计上要知道的</h3>
<ul>
<li>每个数据集的残差除以它自己的噪声 ε：噪声小的谱权重大，这是正确的加权，不另加权重。</li>
<li><b>误差按合计 χ²_ν 统一缩放</b>：一个失配大的数据集会放大所有参数的误差（包括只属于其他数据集的参数）。看结果中每个数据集的 <b>χ² 占比</b>；
某个数据集每点残差是另一个的 4 倍以上时软件会警告，先查这个数据集的模型、范围或 ε。</li>
<li>逐数据集只报 R 因子、N_idp 与 χ² 占比；χ²_ν 只有合计值（变量是共享的，无法分到单个数据集）。</li>
</ul>
<h3>显著性：分三个问题做 F 检验</h3>
<ol>
<li><b>这个壳层在整个系列里是否存在</b>：所有数据集都去掉该路径 vs 都加上。</li>
<li><b>某个样品自己是否需要</b>：只去掉这个数据集的路径，其他不变。在“共享距离”的假设下，单独拟合不显著的弱壳层可能在这里显著——结论要连同这个假设一起写。</li>
<li><b>某参数在样品之间是否真的不同</b>：所有数据集共用一个参数 vs 各自一个。p &gt; 0.05 时，样品间的差别（例如 σ² 的趋势）不能由拟合支撑。</li>
</ol>
<p>F 检验要求两个模型用相同的数据与范围（软件在不同时会提示）。</p>
<h3>结果与保存</h3>
<ul>
<li>右侧先显示联合指标（总 R 因子、χ²_ν、Σ N_idp、变量数）；用数据集切换看每条谱的图、路径、质量检查与诊断。</li>
<li>稳健性检查暂不支持多数据集：对关键样品另做单独拟合的稳健性检查。</li>
<li>“保存结果”：结果表每条路径一行（带 dataset 列），每个数据集一张拟合图；模型存入 models/，可在“运行已保存的模型”或命令行
<code>xafsmith fit 模型名</code>、<code>xafsmith ftest 小模型 大模型</code>、<code>xafsmith figure --kind fit --model 模型名 --dataset ID</code> 重跑。</li>
</ul>
"""


BEFORE_EN = """
<h3>Get the data right first</h3>
<ul>
<li><b>Look before fitting</b>: check every scan (glitches, energy drift, an odd first scan) before averaging. A deglitch range must
cover the whole spike, including the high/low points on either side; otherwise χ(k) keeps an up-down spike, R space shows periodic
ripples and the fit never lines up.</li>
<li><b>Usable k limit</b>: list the other edges inside the scan (same element L₂/L₁, other elements) with “Edge lookup” or
<code>xafsmith kcheck</code> and convert them to k; data beyond that limit are unusable. Do not choose a k range without this.</li>
<li><b>Fluorescence</b>: unless the total μt is well below 0.2, self-absorption damps the amplitude (N too small, σ² too large);
N from fluorescence and transmission are not directly comparable.</li>
</ul>
<h3>Before fitting</h3>
<ul>
<li><b>Standard first, then samples</b>: fit S0² on a standard of known structure (usually 0.7–1.0) and fix it for the samples
(record the source under “Calibrate &amp; process → Processing parameters”). S0² and N are fully correlated; never vary both.
The standard itself must be well crystallised: nanocrystalline or partly disordered standards give a low S0².</li>
<li><b>Ranges</b>: choose the k range from the worst sample of the series and use it for all; the R window should contain only the
shells you fit. Check N_idp = 2ΔkΔR/π first.</li>
<li><b>Variables</b> ≤ N_idp/2 (preferably ≤ N_idp − 3). When information is short, constrain: a shared ΔE0 for close shells,
σ² and ΔR of multiple-scattering paths tied to the matching single-scattering path (collinear M–O–M paths share σ² with the shell).</li>
<li><b>Fit k¹, k² and k³ together</b> (select several k-weights) to reduce N–σ² and ΔE0–ΔR correlations.</li>
<li><b>Simple to complex</b>: first shell first, then add paths one at a time, F-testing each against the previous model (Fit history).</li>
<li><b>Compare a series with one model</b>: adding or removing a path changes the absolute values of other parameters (an outer-shell
σ² moves together with a nearby light-scatterer path); compare trends between samples only within the same model and ranges.</li>
<li><b>Switching FEFF6 ↔ FEFF8 needs a new ΔE0</b>: their energy zeros differ (by several eV); keeping a ΔE0 fixed under the other
version shifts ΔR.</li>
<li><b>Use restraints only with an independent prior</b>: e.g. S0² from a standard fit ± its error; give σ as the reported error of the prior (same scale as this software's parameter errors); a pull beyond 2σ means checking the prior's source or the model. Models with different restraints cannot be compared with the F-test.</li>
<li><b>FT peak ≠ bond length</b>: peaks without phase correction sit about 0.3–0.5 Å short; a small peak is not necessarily a shell
(noise, background residue, window side lobes or multiple scattering).</li>
</ul>
<h3>Do not chase a perfect match</h3>
<p>A “perfect” match is not the goal: once the residual is near the noise, extra parameters only fit noise. If the standard and the
samples leave the same residual inside the window, that is the theory/processing floor, not a missing path in the sample model.
See “Help → Improving fit quality”.</p>
"""

GOOD_EN = """
<p>After a fit, the “Quality” tab of the result on the right checks each point (for a joint fit: for the selected dataset, with the
number of variables compared with the summed N_idp of all datasets).</p>
<h3>Numbers</h3>
<ul>
<li><b>R-factor</b>: &lt; 0.02 very good; 0.02–0.05 acceptable for a first shell; 0.03–0.06 is common with outer shells (to 3–4 Å),
fluorescence or in-situ data; above 0.05 check the model, R window and data first. It grows with the window, so compare only fits
over the same ranges.</li>
<li><b>Residual / noise</b> (Diagnosis tab): ≈ 1–2 means the data limit is reached; well above 2 means a systematic residual (see
the k and R segments the diagnosis points to).</li>
<li><b>χ²_ν</b>: its absolute value depends on the noise estimate and is often ≫ 1; the parameter errors are already scaled by
√χ²_ν. Use it to compare models on <b>the same data and ranges</b> (only a clear drop matters).</li>
<li><b>F-test</b>: report an added shell / parameter as “observed” only with p &lt; 0.05; with p between 0.05 and 0.1 say “possible”
and look for independent evidence (wavelets, other k-weights, other techniques).</li>
</ul>
<h3>Parameters</h3>
<ul>
<li><b>Physical</b>: |ΔE0| ≤ 10 eV; σ² &gt; 0, typically 0.001–0.02 Å² (first shells at room temperature mostly 0.002–0.010; outer
shells and disordered samples up to 0.02–0.03); ΔR within about 0.2 Å of the FEFF structure; N plausible, with an error clearly
smaller than its value.</li>
<li><b>Errors defined</b>: every variable has an error; an error larger than the value means the data cannot determine that
parameter — fix or constrain it.</li>
<li><b>Not at a bound</b>: a parameter sitting on its min / max is held by the limit, not by the data.</li>
<li><b>Correlations</b> with |r| &gt; 0.9 should be reported (typical: N–σ², S0²–N, ΔE0–ΔR); be careful with bond lengths when
ΔE0 and ΔR are correlated.</li>
<li><b>Where errors come from</b>: the reported errors come only from the fit (covariance × χ²_ν); with a single scan there is no
independent error estimate — say so in the conclusions.</li>
</ul>
<h3>Plots and robustness</h3>
<ul>
<li><b>Plots</b>: both |χ(R)| and Re χ(R) match inside the window — matching Re is stricter; the k-space residual is not
concentrated in one region.</li>
<li><b>Robust</b>: conclusions survive changes of kmin, kmax, Rmax and k-weight (Robustness tab). A σ² trend that flips with kmin is
not a result.</li>
<li><b>Model-independent indicators</b>: support qualitative changes between samples (e.g. a weakening outer shell) with
model-independent quantities as well (R-space peak ratios, χ(k) LCF, wavelets), not with one fit parameter alone.</li>
</ul>
<h3>Three kinds of statement</h3>
<p><b>Measured</b> (directly visible in the data), <b>fit result</b> (depends on the model and its assumptions) and
<b>inference</b> (needs further experiments) — keep them apart in the conclusions.</p>
"""

JOINT_EN = """
<p>A joint fit of several datasets fits several spectra at once: <b>parameters with the same name are shared between datasets</b>;
different names are independent. Choose “Joint fit of several datasets” in card 1 of the fit page.</p>
<h3>When to use it</h3>
<ul>
<li>A series of one system (time, potential, temperature) in which some quantities should physically be the same (ΔE0 from one
FEFF calculation, an unchanged first-shell distance, an outer-shell distance of the same topology).</li>
<li>A weak outer shell that a single fit cannot pin down: with shared distances and ΔE0 the whole series constrains them, and the
σ² of the weak shell separates from the correlated parameters.</li>
<li>Multi-temperature data (σ² varies, distances shared); two edges of one sample (shared bond length).</li>
<li>Not useful when the samples genuinely differ in structure and nothing should be shared — the joint fit is then just several
single fits side by side.</li>
</ul>
<h3>Setting it up</h3>
<ul>
<li><b>Datasets</b>: choose at least two spectra; the FEFF folders are shared by all.</li>
<li><b>Paths</b>: one path table (tab) per dataset; use “Copy this path table to the other datasets”, then edit.
<b>Give a parameter the same name to share it and different names to keep it separate</b> (e.g. ss2_A, ss2_B).</li>
<li><b>Ranges</b>: card 2 holds the common ranges; each dataset may override kmin, kmax, Rmin, Rmax (shorten k for a noisy spectrum).
N_idp is summed over the datasets.</li>
<li><b>Parameters</b>: one shared table; the number of variables is compared with Σ N_idp/2.</li>
<li>Do not put the same spectrum into two datasets: the data would count twice and the errors would be too small (the program
warns).</li>
</ul>
<h3>What to share</h3>
<ul>
<li>Usually shared: ΔE0 (same edge, same FEFF, same E0 definition); distances known not to change. S0² stays fixed from the standard.</li>
<li>Usually separate: the quantities you want to compare (σ², N).</li>
<li><b>Sharing is an assumption and belongs in the conclusions.</b> Fit each dataset alone first: a parameter that differs by more
than about 2σ between single fits should not be shared, and joint values should lie within the errors of the single fits.</li>
</ul>
<h3>Statistics you should know</h3>
<ul>
<li>Each dataset's residual is divided by its own noise ε: low-noise spectra weigh more. This is the correct weighting; no extra
weights are applied.</li>
<li><b>Errors are scaled by the combined χ²_ν</b>: one badly fitted dataset inflates the errors of all parameters (including those
that belong only to other datasets). Check each dataset's <b>χ² share</b> in the result; the program warns when one dataset's
residual per point is more than 4 times another's — check that dataset's model, ranges or ε first.</li>
<li>Per dataset only the R-factor, N_idp and χ² share are reported; χ²_ν exists only for the whole fit (shared variables cannot be
split between datasets).</li>
</ul>
<h3>Significance: three F-test questions</h3>
<ol>
<li><b>Is the shell present in the series?</b> Remove the path from all datasets vs keep it in all.</li>
<li><b>Does one sample need it?</b> Remove the path from that dataset only. Under the shared-distance assumption a weak shell that
is not significant in a single fit may become significant here — state the conclusion together with that assumption.</li>
<li><b>Does a parameter really differ between samples?</b> One common parameter for all datasets vs one each. With p &gt; 0.05 the
differences (e.g. a σ² trend) are not supported by the fit.</li>
</ol>
<p>The F-test needs both models on the same data and ranges (the program says so when they differ).</p>
<h3>Results and saving</h3>
<ul>
<li>The right side first shows the joint numbers (total R-factor, χ²_ν, Σ N_idp, variables); switch datasets to see each spectrum's
plot, paths, quality checks and diagnosis.</li>
<li>Robustness checks are not yet available for joint fits: run them on single fits of the key samples.</li>
<li>“Save result”: one row per path in the results table (with a dataset column) and one fit figure per dataset; the model goes to
models/ and can be rerun under “Run a saved model” or with <code>xafsmith fit name</code>, <code>xafsmith ftest small large</code>,
<code>xafsmith figure --kind fit --model name --dataset ID</code>.</li>
</ul>
"""

# 兼容旧名字（整页）
FIT_GUIDE_ZH = BEFORE_ZH + GOOD_ZH
FIT_GUIDE_EN = BEFORE_EN + GOOD_EN


def show_fit_guide(parent, tab=None):
    """tab：0 拟合前、1 拟合得好的标准、2 多数据集联合拟合"""
    pages = ([("Before fitting", BEFORE_EN), ("What is a good fit", GOOD_EN), ("Joint fits", JOINT_EN)] if W.en() else
             [("拟合前", BEFORE_ZH), ("拟合得好的标准", GOOD_ZH), ("多数据集联合拟合", JOINT_ZH)])
    W.info_window(parent, "fit_guide", T("拟合注意事项与“拟合得好”的标准", "Before you fit, and what counts as a good fit"),
                  pages, tab=tab)
