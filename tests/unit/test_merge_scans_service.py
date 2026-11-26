"""E17：services.merge_scans——结果与 E17 前页面里的内联写法（下面的 _old_merge）逐字节相同。"""
import copy

import numpy as np
import pandas as pd
import pytest

from xafsmith import normalize as xnorm, paths, services


@pytest.fixture
def scans(cu):
    xnorm.normalize(cu)
    out = []
    rng = np.random.default_rng(0)
    for i in range(4):
        g = copy.deepcopy(cu)
        g.label = f"cu_scan{i}"
        g.mu = g.mu * (1 + 0.002 * i) + (30.0 * rng.standard_normal(len(g.mu)) if i == 3 else 0.0)
        xnorm.normalize(g)
        out.append(g)
    return out


def _old_merge(groups, label, reject, tol, outdir):
    m, rep = xnorm.merge_scans(groups, label=label, reject=reject, tol_sigma=tol)
    pd.DataFrame(rep).to_csv(outdir / f"merge_{services.safe(label)}.csv", index=False, encoding="utf-8-sig")
    return m, rep


@pytest.mark.parametrize("label,reject,tol", [("merge", [], 4.0), ("a/b: c", ["cu_scan1"], 2.0)])
def test_merge_scans_csv_bytes_equal(scans, tmp_path, monkeypatch, label, reject, tol):
    old_dir, new_dir = tmp_path / "old", tmp_path / "new"
    old_dir.mkdir()
    new_dir.mkdir()
    m0, rep0 = _old_merge(copy.deepcopy(scans), label, reject, tol, old_dir)
    monkeypatch.setattr(paths, "GUI", new_dir)
    m1, df, out = services.merge_scans(copy.deepcopy(scans), label=label, reject=reject, tol_sigma=tol, tool="test")
    assert out == new_dir / f"merge_{services.safe(label)}.csv"
    assert out.read_bytes() == (old_dir / out.name).read_bytes() and out.read_bytes().startswith(b"\xef\xbb\xbf")
    assert df.equals(pd.DataFrame(rep0)) and list(df.columns)[:2] == ["label", "rms_vs_median"]
    assert m1.nscans == m0.nscans and m1.merged_from == m0.merged_from and np.array_equal(m1.mu, m0.mu)
    assert m1.label == label
