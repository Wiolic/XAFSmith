"""金丝雀：监视 `_feffit_restrained.py` 所复制/依赖的 larch 内部实现。

`src/xafsmith/_feffit_restrained.py` 复制了 larch 2026.3.x 的 `xafs/feffit.py::feffit`，并从 larch 取用下列内部名：
  - `sys.modules["larch.xafs.feffit"]` 上的：add_sigma2funcs、FEFFDAT_VALUES、propagate_uncertainties、isNamedClass、
    FeffitDataSet（另加被复制的原函数 feffit 本身，它一变，复制部分就可能不再对应）；
  - `larch.Group`、`larch.fitting.ParameterGroup`、`larch.fitting.params2group`。
对每个函数/类记录 inspect.signature 与 inspect.getsource 的 sha256（换行统一为 \n）。期望值在 larch 2026.3.1 下生成。
"""
import hashlib
import inspect
import sys

import pytest

larch = pytest.importorskip("larch")

# 名字 -> (签名字符串, 源码 sha256)
EXPECTED = {
    "larch.Group": (
        "(name=None, **kws)",
        "b19bc96b72e38b226ecef598ad9786367b57e94b423e918d9d25b0bea25b4e78"),
    "larch.fitting.ParameterGroup": (
        "(name=None, **kws)",
        "2e6a7034a1c1b6593077e53b6d4969eb0630848d592cc9afca2916476d045719"),
    "larch.fitting.params2group": (
        "(params, paramgroup)",
        "5d896172071e05c4ce12e528761c89c60b30febba4d8c44a14010b4378bb83c5"),
    "larch.xafs.feffit.feffit": (
        "(paramgroup, datasets, rmax_out=10, path_outputs=True, fix_unused_variables=True, _larch=None, **kws)",
        "d33ae1934c6cc77d4078d7a6edcd091247022740e1f6c14037c909e528989dfa"),
    "larch.xafs.feffit.add_sigma2funcs": (
        "(params)",
        "47dc3eb9679024bfe72fe708709855712ac1dd336abacc9714c6b8a9a38faec0"),
    "larch.xafs.feffit.propagate_uncertainties": (
        "(result, datasets, _larch=None)",
        "e22ec55d9534949aa5ae0e9156c595c52a0cc097ec290e3251455d83c729f2b1"),
    "larch.xafs.feffit.isNamedClass": (
        "(obj, cls)",
        "c05fb6042b108d2d6aa6708088141c248f8520de787f146de1df3b34c2c7d114"),
    "larch.xafs.feffit.FeffitDataSet": (
        "(data=None, paths=None, transform=None, epsilon_k=None, refine_bkg=False, model=None, pathlist=None, _larch=None, **kws)",
        "f4fa394dad9773aa4c986b169d0b32658beb3482e858707b31676bef955b0c42"),
}
EXPECTED_FEFFDAT_VALUES = ('reff', 'nleg', 'degen', 'rmass', 'rnorman', 'gam_ch', 'rs_int', 'vint', 'vmu', 'vfermi')

HINT = "larch 内部实现变了：先核对 `_feffit_restrained.py` 的复制部分是否仍对应，再更新本测试的期望值"


def _objects():
    import larch.xafs  # noqa: F401  确保 larch.xafs.feffit 已导入
    from larch import Group
    from larch.fitting import ParameterGroup, params2group
    lf = sys.modules["larch.xafs.feffit"]
    out = {"larch.Group": Group, "larch.fitting.ParameterGroup": ParameterGroup, "larch.fitting.params2group": params2group}
    for n in ("feffit", "add_sigma2funcs", "propagate_uncertainties", "isNamedClass", "FeffitDataSet"):
        out["larch.xafs.feffit." + n] = getattr(lf, n)
    return out


def _fingerprint(obj):
    try:
        sig = str(inspect.signature(obj))
    except (TypeError, ValueError):
        sig = None
    src = inspect.getsource(obj).replace("\r\n", "\n").replace("\r", "\n")
    return sig, hashlib.sha256(src.encode("utf-8")).hexdigest()


def test_larch_version_window():
    ver = tuple(int(x) for x in larch.__version__.split(".")[:2])
    assert (2026, 3) <= ver < (2026, 4), f"larch {larch.__version__} 不在 [2026.3, 2026.4)：{HINT}；并检查 pyproject.toml 的上界"


def test_larch_internals_unchanged():
    objs = _objects()
    assert set(objs) == set(EXPECTED)
    changed = []
    for name, obj in objs.items():
        got = _fingerprint(obj)
        if got != EXPECTED[name]:
            what = "签名" if got[0] != EXPECTED[name][0] else "源码哈希"
            changed.append(f"{name}（{what}变了：期望 {EXPECTED[name]}，实际 {got}）")
    assert not changed, HINT + "。变化的名字：\n" + "\n".join(changed)


def test_feffdat_values_unchanged():
    _objects()
    lf = sys.modules["larch.xafs.feffit"]
    assert tuple(lf.FEFFDAT_VALUES) == EXPECTED_FEFFDAT_VALUES, f"larch.xafs.feffit.FEFFDAT_VALUES 变了：{HINT}"
