"""新建项目只生成数据标准规定的文件，不生成依赖某种安装方式的启动脚本。

1.0 之前新建项目会写一个“打开图形界面.bat”，它只认项目里的 .venv 或源码安装向导留下的 location.txt；
用 Windows 安装包装的 XAFSmith 两者都没有，双击只会提示“请先运行 installer.py”。
"""
from xafsmith import paths
from xafsmith.cli import create_project


def test_new_project_files(tmp_path):
    old = paths.ROOT
    try:
        made = {p.relative_to(tmp_path).as_posix() for p in create_project(tmp_path)}
    finally:
        paths.set_root(old)
    assert {"xafsmith.json", "project.md", "data/meta.csv", "structures/README.md", "models/_模板.json",
            "AGENTS.md", "CLAUDE.md"} <= made
    assert not list(tmp_path.glob("*.bat")) and not list(tmp_path.glob("*.cmd"))
    for d in ("data/raw", "structures", "models", "notes", "output"):
        assert (tmp_path / d).is_dir(), d


def test_new_project_keeps_existing_files(tmp_path):
    (tmp_path / "project.md").write_text("我的项目说明", encoding="utf-8")
    old = paths.ROOT
    try:
        made = {p.name for p in create_project(tmp_path)}
    finally:
        paths.set_root(old)
    assert "project.md" not in made
    assert (tmp_path / "project.md").read_text(encoding="utf-8") == "我的项目说明"
