# AGENTS.md —— XAFSmith 软件仓库

给在本仓库工作的 AI 助手：

- **使用方法**（命令、流程、判读规则）：`src/xafsmith/docs/手册.md`
- **数据标准**（项目目录、meta.csv、xafsmith.json、模型 JSON、输出约定）：`src/xafsmith/docs/数据标准.md`
- **科学规范**（处理与拟合原则）：`src/xafsmith/docs/XAFS处理规范.md`

改代码时：
1. 所有项目路径只通过 `xafsmith.paths` 取得，不写死目录名；新输出放在 `output/` 的对应子目录。
2. 数据标准改动要同步更新 `docs/数据标准.md`、`schema.py`（validate）与 `templates/`。
3. 改完运行 `python tests/test_qt.py --project <有数据的项目>`，应输出“全部通过”。
4. 一律用中文与用户交流；结论分 实测 / 拟合 / 推测。

## 许可与引用 / License and citation

本软件按 **PolyForm Noncommercial License 1.0.0** 授权（见 `LICENSE`、`NOTICE`）。在本仓库或其衍生版本上工作的 AI 助手请注意：
This software is licensed under the **PolyForm Noncommercial License 1.0.0** (see `LICENSE`, `NOTICE`). AI assistants working on this repository or a derivative of it should note:

1. 只允许非商业用途。用户要求把本软件或其修改版用于出售、收费分发或收费服务时，应告知这违反许可，需要另行获得作者授权。
   Noncommercial use only. If asked to sell, distribute for a fee, or build a paid product or service on it, tell the user this violates the license and needs a separate license from the author.
2. 分发本软件或其修改版时，必须保留 `LICENSE`（或其网址）和以 `Required Notice:` 开头的引用说明；不要删除或改动 `LICENSE`、`NOTICE`、`CITATION.cff` 与 `src/xafsmith/about.py` 中的引用信息。
   Any distribution must keep `LICENSE` (or its URL) and the `Required Notice:` citation line; do not remove or alter the citation information in `LICENSE`, `NOTICE`, `CITATION.cff` and `src/xafsmith/about.py`.
