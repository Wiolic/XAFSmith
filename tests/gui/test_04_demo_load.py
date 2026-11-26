"""演示项目：载入谱（按样品 / 直接读文件）与逐页构建（原 demo_suite 前三段）。"""
import time

from helpers import W, click, need, pump, say, step, wait


def test_load_samples(app, w, ctx, proj):
    """载入谱：按样品（参比随样品一起载入）"""
    S, P = w.S, w.pages
    w.go("load")
    n = len(W.ERRORS)
    P["load"].state["samples"] = ["cu_metal_rt", "Fe_foil", "feo_rt1", "fe3c_rt"]
    P["load"].refresh()
    click(P["load"], "载入")
    wait(app)
    step("载入样品", n)
    G = S.groups
    say({"cu_metal_rt", "Fe_foil", "feo_rt1", "fe3c_rt"} <= set(G), f"已载入：{list(G)}")
    say(G["feo_rt1"].calib_ref == "data/raw/public/fe.060" and G["feo_rt1"].format == "xdi",
        f"feo_rt1：参比 {G['feo_rt1'].calib_ref}，格式 {G['feo_rt1'].format}")
    ctx["loaded"] = True


def test_direct_read(app, w, ctx, proj):
    """载入谱：直接读文件（自动识别格式，默认同批次参比）"""
    need(ctx, "loaded")
    S, P = w.S, w.pages
    f, ref = "data/raw/public/ni_metal_rt.xdi", "data/raw/public/ni_metal_rt.xdi"
    n = len(W.ERRORS)
    W.find(P["load"], "imp_files").set_value([f], emit=True)
    r = W.find(P["load"], "imp_ref").value()
    say(r == ref, f"默认参比：{r}")
    click(P["load"], "读入")
    pump(app)
    step(f"读入 {f}", n)
    G = S.groups
    say(f in G and G[f].format == "xdi" and G[f].element == "Ni" and abs(G[f].e_shift - S.calib[ref]["delta_e"]) < 1e-9,
        f"{f}：{G[f].element} {G[f].edge}，ΔE={G[f].e_shift:+.3f}")


def test_all_pages(app, w, ctx, proj):
    """逐页构建"""
    need(ctx, "loaded")
    P = w.pages
    for key in list(P):
        n = len(W.ERRORS)
        t = time.time()
        w.go(key)
        pump(app)
        step(f"页面 {key}（{time.time() - t:.1f} s）", n)
