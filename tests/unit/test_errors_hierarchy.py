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


# ---- shown_name：直接显示类名的地方（CLI 顶层、界面横幅 / 对话框）与换类前相同
@pytest.mark.parametrize("new,old", _PAIRS)
def test_shown_name_is_builtin_name(new, old):
    from xafsmith.errors import shown_name
    assert shown_name(new("m")) == old.__name__ == shown_name(old("m"))
    assert shown_name(new) == old.__name__ and shown_name(new.__name__) == old.__name__


def test_shown_name_keeps_other_names():
    from xafsmith.errors import shown_name
    from xafsmith.quickfit import QuickFitError
    from xafsmith.readers import ReadError
    assert shown_name(ReadError("x")) == "ReadError" and shown_name(QuickFitError("x")) == "QuickFitError"
    assert shown_name(KeyError("x")) == "KeyError"


@pytest.mark.parametrize("new,old", _PAIRS)
def test_cli_top_level_line_same_as_builtin(monkeypatch, capsys, tmp_path, new, old):
    from xafsmith import cli

    def run(exc):
        def f(a):
            raise exc
        monkeypatch.setattr(cli, "cmd_qc", f)
        with pytest.raises(SystemExit):
            cli.main(["--project", str(tmp_path), "qc"])
        return capsys.readouterr().err.splitlines()[0]
    assert run(new("boom")) == run(old("boom")) == f"错误 / Error: {old.__name__}: boom"


# ---- 换过的 raise：新类，且仍是原来的内置类
def test_replaced_raises_use_new_classes():
    from xafsmith import migrate, modelcheck
    with pytest.raises(ConfigError):
        migrate.parse_version("abc")
    with pytest.raises(ConfigError):
        migrate.check_not_newer("99.0")
    with pytest.raises(ConfigError):
        migrate.upgrade({"xafsmith": {"schema": "0.1"}})
    with pytest.raises(ModelError):
        modelcheck.raise_on_errors({"name": "x"})
    with pytest.raises(ValueError):                      # 仍可被 except ValueError 捕获
        modelcheck.raise_on_errors({"name": "x"})
