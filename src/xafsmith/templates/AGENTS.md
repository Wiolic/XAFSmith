# AGENTS.md —— 本项目由 XAFSmith 管理

给任何 AI 助手（Claude、GPT、Gemini 等）：

1. 先运行 `xafsmith --help` 和 `xafsmith validate`，再读 `project.md`。
2. 工具手册（命令、数据标准、模型写法、判读规则）随软件安装：运行 `xafsmith docs` 显示文档位置。
3. 原始数据只读；所有结果写入 `output/`；拟合模型放 `models/`；分析记录写 `notes/日期_主题.md`。
4. 一律区分 实测 / 拟合 / 推测；加壳层必须做 F 检验（xafsmith ftest）。
