"""fitcheck / quality_checks：精细拟合的质量检查文字与顺序逐字锁定（快照在 quality_snapshot.json）。
快照由 F2-2 拆分前的 quality_checks 生成；改动文字须同时有意识地更新快照。"""
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

SNAP = Path(__file__).with_name("quality_snapshot.json")


def _res(P, correl=None):
    pars = {}
    for k, v in P.items():
        pars[k] = SimpleNamespace(vary=v["vary"], correl=(correl or {}).get(k))
    return SimpleNamespace(params=pars)


def _p(value, stderr, vary=True, expr=None):
    return dict(value=value, stderr=stderr, vary=vary, expr=expr)


def _path(name, sigma2=0.004, deltar=0.01):
    return dict(path=name, sigma2=sigma2, deltar=deltar)


def scenarios():
    """名字 → (fit, dg)；覆盖每个检查项的触发与不触发。"""
    out = {}
    P = {"s02": _p(0.85, 0.05), "e0": _p(3.0, 1.0), "dr1": _p(0.01, 0.01), "ss1": _p(0.004, 0.001)}
    base = dict(rfactor=0.012, nvarys=4, n_idp=9.0, params=P, paths=[_path("Ir-O")], sample="s")
    md = dict(kweight=[1, 2, 3], params={"s02": dict(min=0.3, max=1.5), "ss1": dict(min=0, max=0.05)})
    out["good"] = (dict(summ=dict(base), model=md, result=_res(P), robust=object()), dict(ratio=1.8))
    out["rf_mid"] = (dict(summ=dict(base, rfactor=0.03), model=md, result=_res(P), robust=None), None)
    out["rf_bad_noise_bad"] = (dict(summ=dict(base, rfactor=0.09), model=md, result=_res(P), robust=None), dict(ratio=6.0))
    P2 = {"s02": _p(1.5, None), "e0": _p(14.0, 3.0), "dr1": _p(0.3, 0.5), "ss1": _p(0.0, 0.002),
          "n1": _p(0.2, 0.5), "ssx": _p(-0.001, 0.0005)}
    s2 = dict(base, params=P2, nvarys=6, n_idp=8.0, rfactor=0.01,
              paths=[_path("a", -0.001, 0.25), _path("b", 0.05, -0.3)])
    md2 = dict(kweight=[2], params={"s02": dict(min=0.3, max=1.5), "ss1": dict(min=0, max=0.05), "n1": dict(min=0, max=12)})
    corr = {"s02": {"ss1": 0.95, "e0": 0.3}, "ss1": {"s02": 0.95}}
    out["many_problems"] = (dict(summ=s2, model=md2, result=_res(P2, corr), robust=None), None)
    out["joint"] = (dict(summ=dict(base, joint=dict(n_idp=30.0), nvarys=12, dataset="d1"), model=md,
                         result=_res(P), robust=None), None)
    out["no_result_params"] = (dict(summ=dict(base), model=md, result=None, robust=None), None)
    return out


def _run(lang):
    from xafsmith.qt import widgets as W
    from xafsmith.qt.pages.fitting.quality import quality_checks
    old = W.LANG["v"]
    W.LANG["v"] = lang
    try:
        return {k: [[ok, txt] for ok, txt in quality_checks(f, dg)] for k, (f, dg) in scenarios().items()}
    finally:
        W.LANG["v"] = old


@pytest.mark.parametrize("lang", ["zh", "en"])
def test_quality_checks_text_locked(lang):
    assert _run(lang) == json.loads(SNAP.read_text(encoding="utf-8"))[lang]


def _stern(nv, ni):
    from xafsmith.fitcheck import fit_checks
    f, _ = scenarios()["good"]
    f = dict(f, summ=dict(f["summ"], nvarys=nv, n_idp=ni))
    return {c.code: c for c in fit_checks(f, stern=True, robust_hint=False)}


def test_stern_pass_note_fail():
    assert _stern(4, 12.0)["nvarys"].ok is True and "nvarys_low_info" not in _stern(4, 12.0)
    c = _stern(4, 6.0)                        # 6/2 < 4 ≤ 6：通过，另有提示
    assert c["nvarys"].ok is True and c["nvarys_low_info"].ok is None
    assert _stern(7, 6.0)["nvarys"].ok is False and "nvarys_low_info" not in _stern(7, 6.0)


def test_robust_hint_off():
    from xafsmith.fitcheck import fit_checks
    f, _ = scenarios()["rf_mid"]
    assert "robust" in {c.code for c in fit_checks(f)}
    assert "robust" not in {c.code for c in fit_checks(f, robust_hint=False)}
