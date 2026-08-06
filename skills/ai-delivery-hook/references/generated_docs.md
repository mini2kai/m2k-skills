# 交付故事日志格式参考

交付故事日志**按需维护**，不由脚本强制，也没有文档等级枚举。日常小改可用 `git-trunk-workflow` 的中文详细 commit 承担留痕；需要长期追溯时，由 `work-orchestrator` 维护项目级 Worker Author Story。

## 什么时候值得写

- 用户明确要求“记录一下”“写交付日志”“需求收口”“长期留存”。
- 完成一个明确需求或较大任务，并产生 Git commit。
- 创建 AI 临时分支、push 临时分支，或需要记录分支是否合回。
- 高风险变更、hotfix、跨仓改动。
- 复杂重构，后续开发者需要知道“为什么这样改”。
- 影响范围超出改动文件本身（数据库、外部系统、异步任务）。

纯咨询、只读查询、日常小改、文档订正、配置微调不需要。

## Worker Author Story

默认项目结构：

```text
.worker_author_story/
  INDEX.md
  branch-flow.csv
  logs/
    YYYY-MM.md
```

- `INDEX.md`：轻量索引，只放日期、需求、仓库、分支、状态和日志链接。
- `branch-flow.csv`：分支流程，记录来源分支、AI 工作分支、commit、push、合回状态，便于 Excel 打开。
- `logs/YYYY-MM.md`：按月追加详细交付故事。

可选章节，按需取用，不要求齐全：

- 交付结论：状态、push、合回、更新时间。
- 分支流程：来源分支、AI 工作分支、baseline、commit、合回目标。
- 变更背景与根因。
- 变更范围：文件、模块、配置、SQL。
- 上游/下游影响：接口、数据、外部系统、模型/跑批、页面。
- SQL / 配置 / 回退。
- 风险与注意事项。
- 验证记录与未执行项。
- 后续事项。
- AI 接手前的人工变更（如有）。

## 设计思路留存

架构判断、方案取舍这类内容放：

```text
<repo_root>/docs/thoughts/YYYY-MM-DD-<topic>.md
```

`ai_delivery_search.py` 会同时检索 `docs/delivery/`、`docs/ai-workflow/`、`docs/thoughts/` 和 `.worker_author_story/`。

## 写完之后

把 `.worker_author_story/` 相关路径交给 `git-trunk-workflow` 显式暂存；如果该目录被 `.gitignore` 忽略，走受控 ignored-docs 暂存流程，不要手写 `git add -f`。
