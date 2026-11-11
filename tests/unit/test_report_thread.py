"""report 作图只用面向对象 API：不导入 pyplot、不切换后端，可在后台线程里运行。"""
import threading
from types import SimpleNamespace

import numpy as np


def _group(label):
    e = np.linspace(-50, 150, 400) + 9000
    k = np.linspace(0, 14, 300)
    r = np.linspace(0, 8, 200)
    return SimpleNamespace(label=label, element="Cu", edge="K", mode="trans", nscans=1, e0=9000.0, e_shift=0.0,
                           energy=e, flat=1 / (1 + np.exp(-(e - 9000) / 3)), norm=1 / (1 + np.exp(-(e - 9000) / 3)),
                           k=k, chi=0.1 * np.sin(2 * k * 2.5) * np.exp(-0.01 * k ** 2), r=r,
                           chir_mag=np.exp(-(r - 2) ** 2), chir_re=np.zeros_like(r), chir_im=np.zeros_like(r),
                           dmude=np.exp(-((e - 9000) / 3) ** 2), edge_step=1.0, bkg_params=None, ft_params=None)


def test_report_does_not_touch_pyplot_backend():
    import matplotlib
    before = matplotlib.get_backend()
    from xafsmith import report  # noqa: F401
    assert matplotlib.get_backend() == before
    assert "plt" not in vars(report)


def test_plot_norm_in_worker_thread(tmp_path):
    from xafsmith import report
    out = tmp_path / "n.png"
    err = []

    def work():
        try:
            report.plot_norm([_group("a"), _group("b")], out=out, title="t")
            report.plot_k_r([_group("a")], out=tmp_path / "kr.png", title="t")
        except BaseException as ex:          # noqa: BLE001
            err.append(ex)
    t = threading.Thread(target=work)
    t.start()
    t.join(60)
    assert not err, err
    assert out.exists() and out.stat().st_size > 1000
    assert (tmp_path / "kr.png").exists()
