"""E14：异常层级——继承关系；原有的 except ValueError / RuntimeError 仍能捕获新类。"""
import pytest

from xafsmith.errors import ConfigError, DataError, FeffError, ModelError, XafsmithError, explain


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


# ---- explain()：新类的输出与“内置类 + 同一消息”逐字相同（对象形式与后台任务带回的文字形式）
_PAIRS = [(ConfigError, ValueError), (DataError, ValueError), (ModelError, ValueError),
          (FeffError, RuntimeError), (XafsmithError, Exception)]
_MSGS = ["中文 / English message", "FEFF 未生成路径，失败现场见 x", "plain"]


@pytest.mark.parametrize("new,old", _PAIRS)
@pytest.mark.parametrize("msg", _MSGS)
@pytest.mark.parametrize("lang", ["zh", "en"])
def test_explain_same_as_builtin(new, old, msg, lang):
    assert explain(new(msg), lang) == explain(old(msg), lang)


@pytest.mark.parametrize("new,old", _PAIRS)
@pytest.mark.parametrize("msg", _MSGS)
@pytest.mark.parametrize("lang", ["zh", "en"])
def test_explain_text_form_same_as_builtin(new, old, msg, lang):
    def tb(mod, name):
        return f"Traceback (most recent call last):\n  File \"x.py\", line 1, in f\n    g()\n{mod}{name}: {msg}\n"
    assert explain(tb("xafsmith.errors.", new.__name__), lang) == explain(tb("", old.__name__), lang)
    assert explain(f"{new.__name__}: {msg}\n\nstack", lang) == explain(f"{old.__name__}: {msg}\n\nstack", lang)


def test_read_error_is_data_error_and_keeps_signature():
    from xafsmith.readers import ReadError
    assert issubclass(ReadError, DataError) and issubclass(ReadError, XafsmithError)
    e = ReadError("中文", "English")
    assert (e.zh, e.en, str(e)) == ("中文", "English", "中文（English）")
    e = ReadError("只有中文")
    assert (e.zh, e.en, str(e)) == ("只有中文", "只有中文", "只有中文")
    assert explain(ReadError("中文", "English"), "en")[0] == "English"
