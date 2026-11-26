"""演示项目：已保存模型、B2 多数据集 / F2-1 容器 / B3 软约束 / B6 σ² / B5 多重散射绑定检查（原 demo_suite 中段）。"""
import json

import pytest

from checks import (container_checks, msbind_checks, multi_fit_checks, restraint_checks, sigma2_checks,
                    sigma2_dialog_checks)
from helpers import W, click, go_fit, need, say, step, texts, wait


@pytest.fixture(scope="module")
def b2_dir(gui_project):
    """B2：演示项目没有 FEFF 目录：用基准测试的 Cu 路径文件临时建一个（只在项目临时副本里）"""
    PROJ = gui_project
    fd = PROJ / "output" / "feff" / "_b2test_Cu_CuK"
    fd.mkdir(parents=True, exist_ok=True)
    import shutil
    shutil.copy(PROJ.parent / "benchmark" / "feffcu01.dat", fd / "feff0001.dat")
    yield "output/feff/_b2test_Cu_CuK"
    (fd / "feff0001.dat").unlink(missing_ok=True)
    fd.rmdir()


def test_saved_model(app, w, ctx, proj):
    """已保存模型：Cu 箔第一壳层（FEFF 路径文件见 tests/data/benchmark），结果与基准测试同一范围"""
    need(ctx, "loaded")
    S, P = w.S, w.pages
    PROJ = proj
    model = {"name": "test_cu_demo", "sample": "cu_metal_rt", "kmin": 3, "kmax": 17, "dk": 4, "window": "kaiser",
             "kweight": 2, "rmin": 1.4, "rmax": 3.0, "fitspace": "r",
             "params": {"amp": {"value": 1.0, "vary": True}, "del_e0": {"value": 0.0, "vary": True},
                        "sig2": {"value": 0.0, "vary": True}, "del_r": 0.0},
             "paths": [{"file": "../benchmark/feffcu01.dat", "label": "Cu-Cu", "s02": "amp", "e0": "del_e0",
                        "sigma2": "sig2", "deltar": "del_r"}]}
    mf = PROJ / "models" / "test_cu_demo.json"
    mf.parent.mkdir(exist_ok=True)
    mf.write_text(json.dumps(model, ensure_ascii=False, indent=2), encoding="utf-8")
    try:
        go_fit(w)
        pg = P["fit"].detailed_page
        pg.state["mf"] = mf.name
        pg.refresh()
        n0, n = len(S.fits), len(W.ERRORS)
        click(pg, "运行")
        wait(app)
        step("运行已保存模型（Cu 箔）", n)
        s = S.fits[-1]["summ"] if len(S.fits) == n0 + 1 else None
        say(s is not None and 0.88 < s["params"]["amp"]["value"] < 0.96 and abs(s["params"]["del_e0"]["value"]) < 10
            and s["rfactor"] < 0.02,
            "Cu 箔拟合：" + ("无结果" if s is None else f"S0²={s['params']['amp']['value']:.3f}，R={s['rfactor']:.4f}"))
        say("残差 / 噪声" in texts(pg), "拟合诊断显示残差/噪声")
    finally:
        mf.unlink(missing_ok=True)
        (PROJ / "output" / "fits" / "test_cu_demo.params.json").unlink(missing_ok=True)


def test_multi_fit(app, w, ctx, proj, b2_dir):
    need(ctx, "loaded")
    S, P = w.S, w.pages
    multi_fit_checks(app, w, S, P, "cu_metal_rt", "cu_b2copy", b2_dir,
                     rng=dict(kmin=3, kmax=17, dk=4, win="kaiser", kws=[2], rmin=1.4, rmax=3.0, space="r"), alias=True)


def test_container(app, w, ctx, proj, b2_dir):
    need(ctx, "loaded")
    S, P = w.S, w.pages
    container_checks(app, w, S, P, "cu_metal_rt", b2_dir)


def test_restraint(app, w, ctx, proj, b2_dir):
    need(ctx, "loaded")
    S, P = w.S, w.pages
    restraint_checks(app, w, S, P, "cu_metal_rt", b2_dir)


def test_sigma2(app, w, ctx, proj, b2_dir):
    need(ctx, "loaded")
    S, P = w.S, w.pages
    sigma2_checks(app, w, S, P, "cu_metal_rt", b2_dir)


def test_sigma2_dialog(app, w, ctx, proj, b2_dir):
    need(ctx, "loaded")
    S, P = w.S, w.pages
    sigma2_dialog_checks(app, w, S, P, "cu_metal_rt", "cu_b6copy", b2_dir)


def test_msbind(app, w, ctx, proj, b2_dir):
    need(ctx, "loaded")
    S, P = w.S, w.pages
    msbind_checks(app, w, S, P, "cu_metal_rt", b2_dir)
