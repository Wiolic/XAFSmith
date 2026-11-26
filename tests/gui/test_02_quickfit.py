"""快速拟合端到端（含混合相 / 趋势顺序 / 叠加拟合曲线）、读入猜测的确认、错误框
（原 quickfit_checks / guess_checks / error_dialog_check）。"""
from checks import error_dialog_check, guess_checks, quickfit_checks


def test_quickfit(app, w):
    quickfit_checks(app, w)


def test_guess(app, w):
    guess_checks(app, w)


def test_error_dialog(app, w, tmp_path):
    error_dialog_check(app, w, tmp_path)
