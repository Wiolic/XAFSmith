"""英文界面逐页构建（不保存语言设置）。必须是最后一个测试文件：之后界面语言保持英文。"""
from checks import english_check


def test_english(app, w):
    english_check(app, w)
