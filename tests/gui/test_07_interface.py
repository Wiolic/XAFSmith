"""U1 / U3 界面行为、制样指导与吸收边查询、流程悬浮窗与导航提示、署名与使用指南窗口、清空工作区、关闭询问
（原 main() 后段，在 demo_suite 之后；检查逐字不变）。"""
from checks import (clear_workspace_check, close_splash_check, flow_nav_check, planner_elements_check,
                    signature_help_checks, u1_u3_checks)


def test_u1_u3(app, w):
    u1_u3_checks(app, w)


def test_planner_elements(app, w):
    planner_elements_check(app, w)


def test_flow_nav(app, w):
    flow_nav_check(app, w)


def test_signature_help(app, w):
    signature_help_checks(app, w)


def test_clear_workspace(app, w):
    clear_workspace_check(app, w)


def test_close_splash(app, w):
    close_splash_check(app, w)
