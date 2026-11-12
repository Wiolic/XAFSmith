import json
import zipfile

from xafsmith import logs


def test_diagnostics_zip_contents(tmp_path):
    logs.setup()
    logs.log.info("unit-test marker")
    z = logs.diagnostics_zip(tmp_path / "d.zip")
    names = zipfile.ZipFile(z).namelist()
    assert "environment.json" in names and "validate.txt" in names
    info = json.loads(zipfile.ZipFile(z).read("environment.json"))
    assert "xafsmith" in info and "python" in info
    assert not any(n.startswith("data/raw") for n in names)      # 不含原始数据


def test_excepthook_logs(tmp_path):
    import sys
    got = []
    old = sys.excepthook
    try:
        logs.install_excepthook(got.append)
        try:
            raise ValueError("boom")
        except ValueError:
            sys.excepthook(*sys.exc_info())
    finally:
        sys.excepthook = old
    assert got and "boom" in got[0]
