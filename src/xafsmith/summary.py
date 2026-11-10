"""汇总：把项目的处理与拟合结果整理成一个 Excel 工作簿 + 一份带图的 HTML 报告。

输出：output/reports/汇总_<日期时间>/
    汇总.xlsx      工作表：样品、校准、质量检查、处理结果、EXAFS拟合、拟合参数(每模型一行)、LCF、处理参数
    汇总报告.html  表格 + 图（双击用浏览器打开，可另存为 PDF）
    figs/          报告中用到的图（从 output/figs 复制）
"""
import datetime
import html
import json
import re
import shutil
from pathlib import Path

import pandas as pd

from . import paths


def _read_csv(p):
    p = Path(p)
    return pd.read_csv(p, encoding="utf-8-sig") if p.exists() else pd.DataFrame()


def collect():
    """读取项目中已有的全部结果，返回 {工作表名: DataFrame}"""
    from .pipeline import load_meta
    sheets = {}
    if paths.META.exists():
        m = load_meta()
        sheets["样品"] = m.groupby("sample", sort=False).agg(
            吸收边=("edge_key", "first"), 模式=("mode", "first"), 角色=("role", "first"),
            批次=("batch", "first"), 扫描数=("file", "size"),
            使用=("use", lambda s: int((s != "0").sum())), 参比=("ref_file", "first"),
            备注=("note", lambda s: "；".join(x for x in s if x))).reset_index()
    if paths.CALIB_JSON.exists():
        cal = json.loads(paths.CALIB_JSON.read_text(encoding="utf-8"))
        sheets["校准"] = pd.DataFrame([dict(参比=k, 吸收边=v.get("edge_key", ""), 批次=v.get("batch", ""),
                                            参比测量时间=v.get("ref_time", ""), E0_meas=round(v["e0_meas"], 3),
                                            E_table=v["e_table"], 表值来源=v.get("table_source", ""),
                                            ΔE=round(v["delta_e"], 3), 谱数=len(v.get("time_gap_hours", {})),
                                            与样品最大时间差_h=max([x for x in v.get("time_gap_hours", {}).values()
                                                                   if x is not None] or [None]))
                                       for k, v in cal.items()])
    qc = _read_csv(paths.QC_CSV)
    if len(qc):
        keep = [c for c in ["sample", "label", "mode", "e0", "edge_step_mu", "delta_mut", "delta_mut_from_I1",
                            "self_abs_risk", "n_glitches", "glitch_E", "i0_drops", "kmax_data", "k_snr3",
                            "epsilon_k", "error"] if c in qc]
        sheets["质量检查"] = qc[keep]
    proc = _read_csv(paths.PROC / "process_summary.csv")
    if len(proc):
        sheets["处理结果"] = proc
    fits = _read_csv(paths.FITS_CSV)
    if len(fits):
        sheets["EXAFS拟合"] = fits
        sheets["拟合概要"] = fit_overview(fits)
    lcf = _read_csv(paths.LCF_CSV)
    if len(lcf):
        sheets["LCF"] = lcf
    if paths.CONFIG.exists():
        cfg = json.loads(paths.CONFIG.read_text(encoding="utf-8"))
        rows = []
        for ek, c in cfg.get("edges", {}).items():
            row = dict(吸收边=ek, E_table=c.get("e_table"), 样品元素=",".join(c.get("elements_in_sample", [])))
            for sec in ("norm", "bkg", "ft"):
                for k, v in c.get(sec, {}).items():
                    row[f"{sec}.{k}"] = v
            s0 = c.get("s02_recommended", {})
            row.update(S02=s0.get("value"), S02_err=s0.get("err"), S02_来源=s0.get("source"))
            rows.append(row)
        sheets["处理参数"] = pd.DataFrame(rows)
    return sheets


def fit_overview(fits):
    """每个（样品, 模型）一行：R 因子、χ²_ν、N_idp、变量数，以及各路径的 N/R/σ²"""
    rows = []
    for (s, m), g in fits.groupby(["sample", "model"], sort=False):
        g = g.drop_duplicates("path", keep="last")
        row = dict(样品=s, 模型=m, R因子=g.rfactor.iloc[-1], chi2_nu=g.chi2_reduced.iloc[-1],
                   N_idp=g.n_idp.iloc[-1], 变量数=g.nvarys.iloc[-1], ΔE0=g.dE0.iloc[-1], S02=g.S02.iloc[-1])
        for _, r in g.head(6).iterrows():
            row[f"{r.path}: N"] = r.N
            row[f"{r.path}: R"] = r.R
            row[f"{r.path}: σ²"] = r.sigma2
        rows.append(row)
    return pd.DataFrame(rows)


def build(title=None, include_figs=True):
    """生成汇总；返回输出文件夹"""
    sheets = collect()
    stamp = datetime.datetime.now().strftime("%Y%m%d_%H%M")
    out = paths.REPORTS / f"汇总_{stamp}"
    out.mkdir(parents=True, exist_ok=True)
    from . import about
    with pd.ExcelWriter(out / "汇总.xlsx") as xw:
        pd.DataFrame({"说明 / Notes": about.text_block().split("\n")}).to_excel(
            xw, sheet_name="说明与引用", index=False)
        if not sheets:
            pd.DataFrame({"说明": ["项目中还没有结果"]}).to_excel(xw, sheet_name="说明", index=False)
        for name, df in sheets.items():
            df.to_excel(xw, sheet_name=name[:31], index=False)
    figs = []
    if include_figs and paths.FIGS.exists():
        (out / "figs").mkdir(exist_ok=True)
        for f in sorted(paths.FIGS.glob("*.png")):
            shutil.copy(f, out / "figs" / f.name)
            figs.append(f.name)
    (out / "汇总报告.html").write_text(_html(title or paths.ROOT.name, sheets, figs), encoding="utf-8")
    return out


def _notice():
    from . import about
    up = "".join(f"<li>{html.escape(u)}</li>" for u in about.UPSTREAM)
    return ("<div class=w><b>⚠ " + html.escape(about.DISCLAIMER_CN) + "</b><br><small>"
            + html.escape(about.DISCLAIMER_EN) + "</small></div>"
            "<div class=c><b>📖 " + html.escape(about.CITE_CN) + "</b><br><small>" + html.escape(about.CITE_EN)
            + "</small><ul>" + up + "</ul></div>")


def _table(df, maxrows=300):
    return df.head(maxrows).to_html(index=False, border=0, classes="t", na_rep="",
                                    float_format=lambda x: f"{x:.4g}")


def _html(title, sheets, figs):
    order = ["样品", "校准", "质量检查", "处理结果", "拟合概要", "EXAFS拟合", "LCF", "处理参数"]
    parts = [f"<h1>{html.escape(title)} —— XAFSmith 汇总</h1>",
             f"<p class=m>生成时间 {datetime.datetime.now():%Y-%m-%d %H:%M}｜项目 {html.escape(str(paths.ROOT))}</p>",
             "<p class=m>R 空间峰位未相移校正；拟合结果依赖模型，判读时区分 实测 / 拟合 / 推测。</p>",
             _notice()]
    for name in order:
        if name in sheets:
            parts.append(f"<h2>{name}</h2>" + _table(sheets[name]))
    if figs:
        parts.append("<h2>图</h2><p class=m>点击缩略图放大查看：滚轮缩放，拖动平移，双击复位，Esc 或点击空白处关闭。</p>")
        groups = {}
        for f in figs:
            key = "拟合" if f.endswith("_fit.png") else ("LCF" if f.startswith("lcf_") else "谱图")
            groups.setdefault(key, []).append(f)
        for k in ("谱图", "拟合", "LCF"):
            if not groups.get(k):
                continue
            parts.append(f"<h3>{k}</h3><div class=g>")
            for f in groups[k]:
                parts.append(f"<figure><img src='figs/{html.escape(f)}' loading=lazy alt='{html.escape(f)}'>"
                             f"<figcaption>{html.escape(f)}</figcaption></figure>")
            parts.append("</div>")
    css = ("body{font-family:'Microsoft YaHei',sans-serif;margin:24px;color:#222}"
           "h1{font-size:22px}h2{font-size:18px;border-bottom:1px solid #ccc;padding-bottom:4px;margin-top:28px}"
           ".m{color:#666;font-size:13px}table.t{border-collapse:collapse;font-size:12px;margin:6px 0}"
           "table.t th,table.t td{border:1px solid #ddd;padding:3px 6px;text-align:right}"
           "table.t th{background:#f3f3f3}"
           ".g{display:grid;grid-template-columns:repeat(auto-fill,minmax(300px,1fr));gap:14px;margin:8px 0 18px}"
           "figure{margin:0;background:#fff;border:1px solid #e5e5e5;border-radius:8px;padding:8px}"
           "figure img{width:100%;height:auto;cursor:zoom-in;display:block}"
           "figcaption{font-size:12px;color:#666;margin-top:4px;word-break:break-all}"
           "#lb{position:fixed;inset:0;background:rgba(20,20,20,.86);display:none;overflow:hidden;z-index:9}"
           "#lb img{position:absolute;left:50%;top:50%;max-width:none;transform-origin:0 0;cursor:grab;background:#fff}"
           "#lb .bar{position:fixed;top:12px;right:16px;display:flex;gap:6px;z-index:10}"
           "#lb .bar button{font-size:15px;padding:4px 11px;border-radius:6px;border:none;background:#fff;cursor:pointer}"
           "#lb .cap{position:fixed;bottom:12px;left:16px;color:#ddd;font-size:13px}"
           ".w{background:#fff4e5;border:1px solid #f0b46a;padding:8px 12px;margin:10px 0;font-size:13px}"
           ".c{background:#eef5ff;border:1px solid #9cc0f0;padding:8px 12px;margin:10px 0;font-size:13px}"
           ".c ul{margin:4px 0 0 18px;padding:0}")
    return f"<!doctype html><html><head><meta charset='utf-8'><title>{html.escape(title)}</title>" \
           f"<style>{css}</style></head><body>{''.join(parts)}{_LIGHTBOX}</body></html>"


# 报告中的图：缩略图网格 + 点击放大（滚轮缩放、拖动平移、双击复位、Esc 关闭）
_LIGHTBOX = """<div id=lb><div class=bar><button id=zi>＋</button><button id=zo>－</button><button id=z1>1:1</button>
<button id=zf>适应</button><button id=zx>✕</button></div><img id=lbi><div class=cap id=lbc></div></div>
<script>
(function(){var lb=document.getElementById('lb'),im=document.getElementById('lbi'),cap=document.getElementById('lbc');
var s=1,x=0,y=0,drag=null;
function ap(){im.style.transform='translate('+x+'px,'+y+'px) scale('+s+')';}
function fit(){var w=im.naturalWidth,h=im.naturalHeight,W=innerWidth-40,H=innerHeight-60;s=Math.min(W/w,H/h,1);
 x=-w*s/2;y=-h*s/2;ap();}
function zoom(f,cx,cy){var r=lb.getBoundingClientRect();cx=(cx===undefined?innerWidth/2:cx)-innerWidth/2;
 cy=(cy===undefined?innerHeight/2:cy)-innerHeight/2;x=cx-(cx-x)*f;y=cy-(cy-y)*f;s*=f;ap();}
document.querySelectorAll('figure img').forEach(function(e){e.addEventListener('click',function(){
 im.onload=fit;im.src=e.src;cap.textContent=e.alt;lb.style.display='block';if(im.complete)fit();});});
lb.addEventListener('wheel',function(e){e.preventDefault();zoom(e.deltaY<0?1.15:1/1.15,e.clientX,e.clientY);},{passive:false});
im.addEventListener('mousedown',function(e){e.preventDefault();drag=[e.clientX-x,e.clientY-y];im.style.cursor='grabbing';});
addEventListener('mousemove',function(e){if(drag){x=e.clientX-drag[0];y=e.clientY-drag[1];ap();}});
addEventListener('mouseup',function(){drag=null;im.style.cursor='grab';});
im.addEventListener('dblclick',fit);
lb.addEventListener('click',function(e){if(e.target===lb)lb.style.display='none';});
document.getElementById('zi').onclick=function(){zoom(1.25);};document.getElementById('zo').onclick=function(){zoom(0.8);};
document.getElementById('z1').onclick=function(){var w=im.naturalWidth,h=im.naturalHeight;s=1;x=-w/2;y=-h/2;ap();};
document.getElementById('zf').onclick=fit;document.getElementById('zx').onclick=function(){lb.style.display='none';};
addEventListener('keydown',function(e){if(e.key==='Escape')lb.style.display='none';});})();
</script>"""


def safe(name):
    return re.sub(r"[^\w.-]+", "_", str(name))
