"""errors —— 把异常翻译成“发生了什么 / 你可以怎么做”两句人话（中 / 英），界面的错误框与后台任务的默认报错共用。

`explain(exc, lang)` 接受异常对象，或后台任务带回来的文字（"类型名: 消息\\n\\n堆栈…"）。英文堆栈不在这里，
由界面放进“详细信息”。不依赖 Qt，可单元测试。
Turn an exception into two plain sentences (what happened / what you can do), in Chinese or English.
"""

from __future__ import annotations

import re

ISSUES_URL = "https://github.com/Wiolic/XAFSmith/issues"

_CONV = re.compile(r"singular|converge|ill-conditioned|too many function calls|could not estimate|covariance|cannot be inverted", re.I)


def _names(exc):
    """(异常类名列表（含父类）, 消息)；文字形式只有类名一个"""
    if isinstance(exc, BaseException):
        return [c.__name__ for c in type(exc).__mro__], str(exc)
    text = str(exc).strip()
    if text.startswith("Traceback (most recent call last)"):          # 未捕获异常的完整堆栈：取最后一行 “类型: 消息”
        first = next((ln for ln in reversed(text.splitlines()) if ln.strip() and not ln.startswith((" ", "\t"))), text)
    else:
        first = text.split("\n\n")[0].split("\n")[0]
    name, sep, msg = first.partition(": ")
    name = name.rsplit(".", 1)[-1]                                    # numpy.linalg.LinAlgError → LinAlgError
    return ([name.strip()] if sep else ["Exception"]), (msg if sep else first)


def _bi(msg, lang):
    """软件里的双语消息（"中文 / English" 或 "中文（English）"）取一种语言；不是双语就原样返回"""
    msg = str(msg)
    if " / " in msg:
        zh, en = msg.split(" / ", 1)
        return zh.strip() if lang == "zh" else en.strip()
    m = re.match(r"^(.*?)（(.*)）$", msg, re.S)
    if m and re.search(r"[A-Za-z]{3}", m.group(2)) and re.search(r"[一-鿿]", m.group(1)):
        return m.group(1).strip() if lang == "zh" else m.group(2).strip()
    return msg.strip()


def _file(exc, msg):
    fn = getattr(exc, "filename", None) if isinstance(exc, BaseException) else None
    if fn:
        return str(fn)
    m = re.search(r"['\"]([^'\"]+)['\"]\s*$", msg)
    return m.group(1) if m else ""


def explain(exc, lang="zh"):
    """(发生了什么, 你可以怎么做)，lang = "zh" | "en"。"""
    zh = lang == "zh"
    names, msg = _names(exc)
    if "FileNotFoundError" in names:
        f = _file(exc, msg)
        return ((f"找不到文件：{f}" if f else "找不到文件。") if zh else (f"File not found: {f}" if f else "File not found."),
                "检查文件是否被移动、改名或删除；在“数据登记”里重新扫描，或重新选择文件。" if zh else
                "Check whether the file was moved, renamed or deleted; rescan on the Data page or choose the file again.")
    if "PermissionError" in names:
        f = _file(exc, msg)
        return ((f"没有权限读写文件：{f}" if f else "没有权限读写文件。") if zh else
                (f"No permission to read or write the file: {f}" if f else "No permission to read or write the file."),
                "多半是这个文件正在 Excel 等程序里打开：先把它关掉再重试；也可能是文件夹只读或在受保护的位置。" if zh else
                "Most often the file is open in Excel or another program: close it and retry; the folder may also be read-only or protected.")
    if "ReadError" in names:
        what = (getattr(exc, "zh", None) if zh else getattr(exc, "en", None)) if isinstance(exc, BaseException) else None
        return (what or _bi(msg, lang),
                "文件格式或列没有被识别：到“载入谱”页用“列映射向导…”指定能量 / I0 / It / If 列，或换用正确的格式。" if zh else
                "The format or columns were not recognised: use the column mapping wizard on the Load page to set the energy / I0 / It / If "
                "columns, or choose the correct format.")
    if "QuickFitError" in names:
        return (_bi(msg, lang),
                "照上面的提示调整；或看判定里的建议，也可以到“精细拟合”里手动设置路径与参数。" if zh else
                "Adjust as the message says; see the advice in the verdict, or set paths and parameters yourself in Detailed fit.")
    if "MemoryError" in names:
        return ("内存不足。" if zh else "Out of memory.",
                "关闭其他程序，减少同时处理的谱数，或缩小 k / R 范围后重试。" if zh else
                "Close other programs, process fewer spectra at once, or narrow the k / R range, then retry.")
    if "LinAlgError" in names or _CONV.search(msg):
        return ("拟合没有收敛，或参数之间无法分开（协方差矩阵奇异）。" if zh else
                "The fit did not converge, or the parameters cannot be told apart (singular covariance matrix).",
                "减少变量（固定 S0²、σ² 等）、放宽 k / R 窗口，或给更接近的初值；快速拟合可先看判定里的建议。" if zh else
                "Reduce the variables (fix S0², σ² …), widen the k / R window or give closer starting values; in Quick fit read the "
                "advice in the verdict first.")
    if "FEFF" in msg and "RuntimeError" in names:
        return ("FEFF 没有算出路径。" if zh else "FEFF produced no paths.",
                "检查结构（CIF 是否完整、吸收元素和吸收边是否对）；失败现场在该 FEFF 文件夹的 _feff_failed 里，原有结果没有改动。" if zh else
                "Check the structure (is the CIF complete; are absorber and edge right?); the failed run is kept in _feff_failed inside the "
                "FEFF folder and the previous results are untouched.")
    t = names[0]
    return (f"未预料的错误：{t}: {msg}".strip() if zh else f"Unexpected error: {t}: {msg}".strip(),
            "请点“导出诊断包…”，连同这条信息一起发到 GitHub Issues，开发者会处理；保存好当前工作后可重启软件。" if zh else
            "Please click “Export diagnostics…” and send the bundle with this message to GitHub Issues; save your work and restart if needed.")
