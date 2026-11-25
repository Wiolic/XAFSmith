"""E14：异常层级——继承关系；原有的 except ValueError / RuntimeError 仍能捕获新类。"""
import pytest

from xafsmith.errors import ConfigError, DataError, FeffError, ModelError, XafsmithError


@pytest.mark.parametrize("cls", [ConfigError, DataError, ModelError])
def test_value_error_family(cls):
    assert issubclass(cls, XafsmithError) and issubclass(cls, ValueError)
    with pytest.raises(ValueError):
        raise cls("消息 / message")


def test_feff_error_is_runtime_error():
    assert issubclass(FeffError, XafsmithError) and issubclass(FeffError, RuntimeError)
    assert not issubclass(FeffError, ValueError)
    with pytest.raises(RuntimeError):
        raise FeffError("FEFF 未生成路径")


def test_root_is_plain_exception_and_not_value_error():
    assert issubclass(XafsmithError, Exception)
    assert not issubclass(XafsmithError, (ValueError, RuntimeError))


def test_quickfit_error_is_model_error():
    from xafsmith.quickfit import QuickFitError
    assert issubclass(QuickFitError, ModelError) and issubclass(QuickFitError, ValueError)
