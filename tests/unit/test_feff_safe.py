"""E6：FEFF 失败不毁旧结果；path_atoms 缓存随文件变化失效。真实 FEFF6L 小团簇约 2 s。"""
import hashlib
import os

import pytest

from xafsmith import feff_wrap, msbind, structures


def _inp():
    s = structures.builtin("IrO2")
    return feff_wrap.make_feffinp(s, "Ir", "L3", rmax=3.0, rcluster=6.0)


def _snapshot(folder):
    return {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in folder.iterdir() if p.is_file()}


def _leftover(folder):
    return (folder / "_feffrun").exists()


def test_failure_keeps_old_results(tmp_path):
    (tmp_path / "feff.inp").write_text("OLD INP\n", encoding="utf-8")
    (tmp_path / "feff0001.dat").write_text("old path 1\n", encoding="utf-8")
    (tmp_path / "files.dat").write_text("old files\n", encoding="utf-8")
    before = _snapshot(tmp_path)
    df = feff_wrap.run_feff(tmp_path, "garbage\nEND\n")        # 真实 FEFF 对垃圾输入不产出路径
    assert len(df) == 0
    assert _snapshot(tmp_path) == before
    assert (tmp_path / "_feff_failed" / "feff.inp").read_text(encoding="utf-8") == "garbage\nEND\n"
    assert not _leftover(tmp_path)
    feff_wrap.run_feff(tmp_path, "garbage2\nEND\n")            # 再次失败：替换上一次的失败现场
    assert (tmp_path / "_feff_failed" / "feff.inp").read_text(encoding="utf-8") == "garbage2\nEND\n"
    assert _snapshot(tmp_path) == before


def test_exception_preserves_folder_and_reraises(tmp_path, monkeypatch):
    import larch.xafs as lx
    (tmp_path / "feff.inp").write_text("OLD\n", encoding="utf-8")
    (tmp_path / "feff0001.dat").write_text("old\n", encoding="utf-8")
    before = _snapshot(tmp_path)

    def boom(**kw):
        raise OSError("fake crash")
    monkeypatch.setattr(lx, "feff6l", boom)
    with pytest.raises(OSError):
        feff_wrap.run_feff(tmp_path, "TITLE x\nEND\n")
    assert _snapshot(tmp_path) == before
    assert (tmp_path / "_feff_failed").is_dir() and not _leftover(tmp_path)


def test_success_replaces_old(tmp_path):
    (tmp_path / "feff.inp").write_text("OLD\n", encoding="utf-8")
    (tmp_path / "feff0099.dat").write_text("stale extra\n", encoding="utf-8")
    df = feff_wrap.run_feff(tmp_path, _inp())
    assert len(df) >= 2
    assert not (tmp_path / "feff0099.dat").exists()
    assert (tmp_path / "feff0001.dat").stat().st_size > 100
    assert (tmp_path / "feff.inp").read_text(encoding="utf-8") == _inp()
    assert not _leftover(tmp_path)
    assert all(str(tmp_path) in f for f in df["file"])
    df2 = feff_wrap.run_feff(tmp_path)                          # 不给文本：沿用目录里的 feff.inp
    assert len(df2) == len(df)


def test_path_atoms_cache_follows_file(tmp_path):
    feff_wrap.run_feff(tmp_path, _inp())
    a, b = tmp_path / "feff0001.dat", tmp_path / "feff0002.dat"
    g_a, g_b = msbind.path_atoms(a, root=None), msbind.path_atoms(b, root=None)
    assert g_a != g_b
    target = tmp_path / "target.dat"
    target.write_bytes(a.read_bytes())
    os.utime(target, ns=(10**18, 10**18))
    assert msbind.path_atoms(target, root=None) == g_a
    target.write_bytes(b.read_bytes())
    os.utime(target, ns=(2 * 10**18, 2 * 10**18))
    assert msbind.path_atoms(target, root=None) == g_b
