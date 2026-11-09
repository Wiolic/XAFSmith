# AGENTS.md —— XAFSmith 软件仓库

给在本仓库工作的 AI 助手：

- **使用方法**（命令、流程、判读规则）：`src/xafsmith/docs/手册.md`
- **数据标准**（项目目录、meta.csv、xafsmith.json、模型 JSON、输出约定）：`src/xafsmith/docs/数据标准.md`
- **科学规范**（处理与拟合原则）：`src/xafsmith/docs/XAFS处理规范.md`

改代码时：
1. 所有项目路径只通过 `xafsmith.paths` 取得，不写死目录名；新输出放在 `output/` 的对应子目录。
2. 数据标准改动要同步更新 `docs/数据标准.md`、`schema.py`（validate）与 `templates/`。
3. 改完运行 `python tests/test_gui.py --project <有数据的项目>`，应输出“全部通过”。
4. 一律用中文与用户交流；结论分 实测 / 拟合 / 推测。
