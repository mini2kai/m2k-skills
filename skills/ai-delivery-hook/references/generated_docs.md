# 交付文档格式参考

交付文档**按需生成**，不由脚本强制，也没有文档等级枚举。日常改动用 `git-trunk-workflow` 的中文详细 commit 即可。

## 什么时候值得写

- 高风险变更、hotfix、跨仓改动。
- 复杂重构，后续开发者需要知道"为什么这样改"。
- 影响范围超出改动文件本身（数据库、外部系统、异步任务）。
- 使用者明确要求。

日常小改、文档订正、配置微调不需要。

## Delivery 文档

路径建议：

```text
<repo_root>/docs/delivery/YYYY-MM-DD/<slug>-delivery.md
```

可选章节，按需取用，不要求齐全：

- 变更背景与根因
- 变更范围（文件、模块、配置）
- 影响范围（接口、数据、外部系统）
- 风险与注意事项
- 验证记录与未执行项
- 后续事项
- AI 接手前的人工变更（如有）

## 设计思路留存

架构判断、方案取舍这类内容放：

```text
<repo_root>/docs/thoughts/YYYY-MM-DD-<topic>.md
```

`ai_delivery_search.py` 会同时检索 `docs/delivery/`、`docs/ai-workflow/` 和 `docs/thoughts/`。

## 写完之后

把文档路径交给 `git-trunk-workflow` 显式暂存；如果 `docs/` 被 `.gitignore` 忽略，走 `stage_ignored_paths.ps1`，不要手写 `git add -f`。
