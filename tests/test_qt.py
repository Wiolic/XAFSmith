"""图形界面自动测试的入口（薄壳）。检查本身已迁入 pytest：

  tests/gui/          公开数据演示项目上的逐页检查（CI 用这个）：python -m pytest tests/gui -q
  tests/local/gui/    本机 IrTaOx 项目专用检查（Ir/Ta 样品、已保存模型、FEFF；整个 tests/local 不入库）

运行：
  python tests/test_qt.py                       # = python -m pytest tests/gui -s -q（演示项目）
  python tests/test_qt.py --project <项目目录>   # 本机 IrTaOx 项目：跑 tests/local/gui（项目含 IrO2、Ir foil、IrCoOx_OCP 三个样品时），
                                                # 否则在该项目上跑演示项目的通用检查
  python tests/test_qt.py --quick               # 跳过 FEFF8L 与稳健性检查（较慢；只有 IrTaOx 套件有这两项）
测试在项目的临时副本里运行，不写源项目，也不改用户保存的界面语言；退出码沿用 pytest 的。
"""
import argparse
import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
DEMO = HERE / "data" / "demo_project"
IRTAOX_SAMPLES = {"IrO2", "Ir foil", "IrCoOx_OCP"}


def _is_irtaox(project):
    import pandas as pd
    meta = Path(project) / "data" / "meta.csv"
    if not meta.is_file():
        return False
    return IRTAOX_SAMPLES <= set(pd.read_csv(meta, dtype=str, encoding="utf-8-sig").fillna("")["sample"])


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--project", default=None, help="项目目录；缺省是公开数据的演示项目（不读 XAFSMITH_PROJECT，避免误测真实项目）")
    ap.add_argument("--quick", action="store_true", help="跳过 FEFF8L 与稳健性检查（较慢）")
    args = ap.parse_args(argv)
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    os.environ["XAFSMITH_NO_RECENT"] = "1"
    os.environ.pop("XAFSMITH_GUI_PROJECT", None)
    if args.quick:
        os.environ["XAFSMITH_GUI_QUICK"] = "1"
    target = HERE / "gui"
    if args.project:
        proj = Path(args.project).resolve()
        os.environ["XAFSMITH_GUI_PROJECT"] = str(proj)
        if _is_irtaox(proj):
            target = HERE / "local" / "gui"
    import pytest
    return int(pytest.main(["-q", "-s", "-p", "no:cacheprovider", str(target)]))


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(main())
