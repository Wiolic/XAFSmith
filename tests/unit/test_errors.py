"""G6：errors.explain 逐类。"""
from xafsmith import errors, quickfit as qf
from xafsmith.readers import ReadError


def both(exc):
    return errors.explain(exc, "zh"), errors.explain(exc, "en")


def test_file_not_found():
    (zw, zt), (ew, et) = both(FileNotFoundError(2, "No such file or directory", "data/raw/a.xdi"))
    assert "找不到文件" in zw and "data/raw/a.xdi" in zw and "重新" in zt
    assert "File not found" in ew and "data/raw/a.xdi" in ew and "rescan" in et


def test_permission_mentions_excel():
    (zw, zt), (ew, et) = both(PermissionError(13, "Permission denied", "meta.csv"))
    assert "没有权限" in zw and "Excel" in zt and "meta.csv" in zw
    assert "No permission" in ew and "Excel" in et


def test_read_error_uses_own_languages_and_wizard():
    e = ReadError("无法识别能量列", "Cannot find the energy column")
    (zw, zt), (ew, et) = both(e)
    assert zw == "无法识别能量列" and ew == "Cannot find the energy column"
    assert "列映射向导" in zt and "wizard" in et


def test_quickfit_error_bilingual_message_split():
    e = qf.QuickFitError("FEFF 路径里没有单散射路径 / no single-scattering path in the FEFF output")
    (zw, zt), (ew, et) = both(e)
    assert zw == "FEFF 路径里没有单散射路径" and ew == "no single-scattering path in the FEFF output"
    assert "精细拟合" in zt and "Detailed fit" in et


def test_memory_error():
    (zw, _), (ew, _) = both(MemoryError())
    assert "内存" in zw and "memory" in ew


def test_covariance_and_convergence():
    import numpy as np
    for e in (np.linalg.LinAlgError("Singular matrix"), ValueError("fit did not converge"), RuntimeError("Could not estimate error-bars")):
        (zw, zt), (ew, et) = both(e)
        assert "没有收敛" in zw and "固定" in zt and "converge" in ew and "Reduce" in et


def test_feff_failure():
    e = RuntimeError("FEFF 未生成路径，失败现场见 x/_feff_failed（feffrun_feff.log、feff.err）；原有结果未改动")
    (zw, zt), (ew, et) = both(e)
    assert "FEFF" in zw and "_feff_failed" in zt and "FEFF" in ew and "_feff_failed" in et


def test_unexpected():
    (zw, zt), (ew, et) = both(KeyError("boom"))
    assert zw.startswith("未预料的错误：KeyError") and "诊断包" in zt
    assert ew.startswith("Unexpected error: KeyError") and "diagnostics" in et.lower()


def test_text_form_from_worker():
    msg = "FileNotFoundError: [Errno 2] No such file or directory: 'a/b.xdi'\n\nTraceback (most recent call last):\n  ..."
    w, _t = errors.explain(msg, "zh")
    assert "找不到文件" in w and "a/b.xdi" in w
    w, _t = errors.explain("MemoryError: \n\nTraceback…", "en")
    assert "memory" in w
    w, _t = errors.explain("QuickFitError: 先选样品 / choose samples first\n\nTraceback…", "en")
    assert w == "choose samples first"


def test_issues_url():
    assert errors.ISSUES_URL == "https://github.com/Wiolic/XAFSmith/issues"


def test_uncaught_traceback_text():
    tb = ("Traceback (most recent call last):\n  File \"x.py\", line 1, in <module>\n    open('m.csv')\n"
          "PermissionError: [Errno 13] Permission denied: 'm.csv'\n")
    w, t = errors.explain(tb, "zh")
    assert "没有权限" in w and "Excel" in t
    w, _t = errors.explain("Traceback (most recent call last):\n  File \"y\", line 3\nnumpy.linalg.LinAlgError: Singular matrix\n", "en")
    assert "converge" in w
