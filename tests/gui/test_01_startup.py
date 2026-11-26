"""启动、无控制台载入、新项目复制登记、列映射向导（原 tests/test_qt.py main() 开头；检查逐字不变）。"""
from checks import copy_register_check, no_console_check, startup_check, wizard_check


def test_startup(app, w):
    startup_check(app, w)


def test_no_console(app, w):
    no_console_check("cu_metal_rt")


def test_copy_register(app, w):
    copy_register_check(app, w)


def test_column_wizard(app, w):
    wizard_check(app)
