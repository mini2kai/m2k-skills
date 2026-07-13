# Orchestrator Integration

`ai-delivery-hook` 不替代 `work-orchestrator`，也不替代 `git-trunk-workflow`。

## 推荐接入点

| 阶段 | 动作 | 脚本 |
|---|---|---|
| Intake / Evidence | 检索历史交付记忆 | `ai_delivery_search.py` |
| Plan 后、Execute 前 | 开启 active AI session | `ai_delivery_start.py` |
| Verify 后、Git 交付前 | 生成 current/prepared/docs | `ai_delivery_prepare.py` |
| commit / push | hook 被动校验 | `check_ai_delivery.py` |
| Handoff 后 | 关闭 session，更新 checkpoint | `ai_delivery_finish.py` |

## 与 git-trunk-workflow 的关系

- 分支创建、显式暂存、commit、push 仍交给 `git-trunk-workflow`。
- `ai-delivery-hook` 在 Git 交付前生成文档，并把文档路径交给 Git 交付步骤显式暂存。
- 任一 skill 阻断后，不得改用原生命令绕过。

## 最小上下文包

总编排调用本 skill 前至少提供：

- repo root
- 任务标题
- 任务类型
- 变更文件
- 验证结果
- 风险等级
- 文档等级
