"""pipeline 的 progress / 取消：回调按样品调用；取消（Cancelled）时中止且不写汇总文件。"""
import shutil
from pathlib import Path

import pytest

from xafsmith import paths
from xafsmith.tasks import Cancelled, TaskHandle

DEMO = Path(__file__).resolve().parents[1] / "data" / "demo_project"


@pytest.fixture
def proj(tmp_path):
    root = tmp_path / "p"
    shutil.copytree(DEMO, root, ignore=shutil.ignore_patterns("output"))
    old = paths.ROOT
    paths.set_root(root)
    paths.ensure()
    yield root
    paths.set_root(old)


def test_process_all_reports_progress(proj):
    from xafsmith import pipeline as pl
    seen = []
    df, _ = pl.process_all(make_figs=False, progress=lambda f, n: seen.append((f, n)))
    assert len(df) > 0
    fr = [f for f, _ in seen]
    assert fr == sorted(fr) and 0 <= fr[0] < 1 and fr[-1] < 1
    assert len({n for _, n in seen}) == len(seen), "每个样品只报告一次"


def test_process_all_cancel_writes_no_summary(proj):
    from xafsmith import pipeline as pl
    h = TaskHandle()
    n = []

    def prog(f, name):
        n.append(name)
        if len(n) == 2:
            h.cancel()
        h.progress(f, name)

    with pytest.raises(Cancelled):
        pl.process_all(make_figs=False, progress=prog)
    assert len(n) == 2
    assert not (paths.PROC / "process_summary.csv").exists()


def test_run_qc_progress_and_cancel(proj):
    from xafsmith import pipeline as pl
    seen = []
    df = pl.run_qc(progress=lambda f, n: seen.append(n))
    assert len(seen) == len(df) and len(df) > 0
    h = TaskHandle()
    h.cancel()
    with pytest.raises(Cancelled):
        pl.run_qc(progress=h.progress)
