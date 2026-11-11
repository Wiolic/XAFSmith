"""拟合注意事项（中英文）与弹窗。"""

from __future__ import annotations

from ... import widgets as W
from ...widgets import T


FIT_GUIDE_ZH = """
<h3>拟合前</h3>
<ul>
<li><b>先标样、后样品</b>：在结构已知的标样上拟合得到 S0²（通常 0.7–1.0），样品中固定为这个值（在“校准与处理 → 处理参数”中记录来源）。
S0² 与配位数 N 完全相关，两者不能同时自由。</li>
<li><b>数据范围</b>：k 范围按全组最差样品的信噪比定，全组相同；R 窗口只包含要拟合的壳层。先看独立点数 N_idp = 2ΔkΔR/π。</li>
<li><b>变量数</b> ≤ N_idp/2（最好 ≤ N_idp − 3）。参数不够时用约束：相近壳层共用 ΔE0，多重散射路径的 σ²、ΔR 与对应单散射绑定。</li>
<li><b>同时用 k¹、k²、k³ 拟合</b>（k 权重多选），可降低 N–σ²、ΔE0–ΔR 的相关性。</li>
<li><b>从简单到复杂</b>：先第一壳层，再逐条加路径；每加一条都与前一个模型做 F 检验。</li>
</ul>
<h3>怎样算拟合得好</h3>
<p>拟合后，右侧结果的“质量检查”标签页会逐条判断下面各项。</p>
<ul>
<li><b>R 因子</b>：&lt; 0.02 很好；0.02–0.05 对第一壳层可接受；&gt; 0.05 说明模型或数据有问题。R 因子随窗口变宽而变大，只在相同范围之间比较。</li>
<li><b>残差 / 噪声</b>（拟合诊断）：≈ 1–2 表示已到数据极限；明显大于 2 说明还有系统偏差。</li>
<li><b>χ²_ν</b>：绝对值依赖噪声估计，常远大于 1；用来比较<b>同一数据、同一范围</b>下的不同模型（明显下降才有意义）。</li>
<li><b>参数物理合理</b>：|ΔE0| ≤ 10 eV；σ² &gt; 0，一般 0.001–0.02 Å²（室温第一壳层多为 0.002–0.010）；ΔR 不应偏离 FEFF 结构超过约 0.2 Å；
N 在合理范围内且误差明显小于数值。</li>
<li><b>误差可估</b>：每个变量都有误差；误差大于数值本身，说明数据不能确定这个参数，应固定或约束。</li>
<li><b>不卡边界</b>：参数停在设定的上下限上，说明是限制在起作用，结果不可信。</li>
<li><b>相关系数</b> |r| &gt; 0.9 的参数对要在结论中说明（典型：N–σ²、S0²–N、ΔE0–ΔR）。</li>
<li><b>图上</b>：窗口内 |χ(R)| 与 Re χ(R) 都要对上，Re 对上比 |χ(R)| 对上更严格；k 空间残差不集中在某一段。</li>
<li><b>稳健</b>：改变 kmin、kmax、Rmax 与 k 权重后结论不变（稳健性检查）。</li>
</ul>
<h3>别追求严丝合缝</h3>
<p>“严丝合缝”不是目标：残差已接近噪声时，再加参数只是在拟合噪声。详见“使用指南 → 拟合质量提升教程”。</p>
"""


FIT_GUIDE_EN = """
<h3>Before fitting</h3>
<ul>
<li><b>Standard first, then samples</b>: fit S0² on a standard of known structure (usually 0.7–1.0) and fix it for the samples
(record the source under “Calibrate &amp; process → Processing parameters”). S0² and N are fully correlated; never vary both.</li>
<li><b>Ranges</b>: choose the k range from the worst sample of the series and use it for all; the R window should contain only the
shells you fit. Check N_idp = 2ΔkΔR/π first.</li>
<li><b>Variables</b> ≤ N_idp/2 (preferably ≤ N_idp − 3). When information is short, constrain: a shared ΔE0 for close shells,
σ² and ΔR of multiple-scattering paths tied to the matching single-scattering path.</li>
<li><b>Fit k¹, k² and k³ together</b> (select several k-weights) to reduce N–σ² and ΔE0–ΔR correlations.</li>
<li><b>Simple to complex</b>: first shell first, then add paths one at a time, F-testing each against the previous model.</li>
</ul>
<h3>What counts as a good fit</h3>
<p>After a fit, the “Quality” tab of the result on the right checks each point.</p>
<ul>
<li><b>R-factor</b>: &lt; 0.02 very good; 0.02–0.05 acceptable for a first shell; &gt; 0.05 points to a problem with the model or
the data. It grows with the window, so compare only fits over the same ranges.</li>
<li><b>Residual / noise</b> (fit diagnosis): ≈ 1–2 means the data limit is reached; well above 2 means a systematic residual.</li>
<li><b>χ²_ν</b>: its absolute value depends on the noise estimate and is often ≫ 1; use it to compare models on <b>the same data and
ranges</b> (only a clear drop matters).</li>
<li><b>Physical parameters</b>: |ΔE0| ≤ 10 eV; σ² &gt; 0, typically 0.001–0.02 Å² (first shells at room temperature mostly
0.002–0.010); ΔR within about 0.2 Å of the FEFF structure; N plausible, with an error clearly smaller than its value.</li>
<li><b>Errors defined</b>: every variable has an error; an error larger than the value means the data cannot determine that
parameter — fix or constrain it.</li>
<li><b>Not at a bound</b>: a parameter sitting on its min / max is held by the limit, not by the data.</li>
<li><b>Correlations</b> with |r| &gt; 0.9 should be reported (typical: N–σ², S0²–N, ΔE0–ΔR).</li>
<li><b>Plots</b>: both |χ(R)| and Re χ(R) match inside the window — matching Re is stricter; the k-space residual is not
concentrated in one region.</li>
<li><b>Robust</b>: conclusions survive changes of kmin, kmax, Rmax and k-weight (robustness check).</li>
</ul>
<h3>Do not chase a perfect match</h3>
<p>A “perfect” match is not the goal: once the residual is near the noise, extra parameters only fit noise. See
“Help → Improving fit quality”.</p>
"""


def show_fit_guide(parent):
    W.info_window(parent, "fit_guide", T("拟合注意事项与“拟合得好”的标准", "Before you fit, and what counts as a good fit"),
                  FIT_GUIDE_EN if W.en() else FIT_GUIDE_ZH)
