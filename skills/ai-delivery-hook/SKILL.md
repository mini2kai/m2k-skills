---
name: ai-delivery-hook
description: AI 交付历史的只读检索与人工变更检测。Use when AI takes over a repository and needs prior delivery/design context, wants to list commits made since the last known point, or needs to inspect Worker Author Story logs. Delivery story logs are maintained by orchestration on request or handoff triggers, not enforced by Git hooks.
---

# AI Delivery Hook

## 定位

本 skill 只做两件事：**查历史留存**、**列出指定版本之后的提交**。

它不安装 Git hook，不阻断提交，不维护 session 状态，不强制文档等级。交付故事日志由 `work-orchestrator` 在 Handoff 阶段按触发规则维护；日常改动仍可由 `git-trunk-workflow` 的中文详细 commit 承担留痕。

## 围栏（代码强制，不可绕过）

- **纯只读**：脚本只执行 `git rev-parse`、`git log` 和文件读取，不写仓库、不写状态文件、不装 hook。
- **必须是 Git 仓库**：`resolve_repo_root` 解析失败即 `not_git_repo` 退出，不猜测路径。
- **子目录归一**：任意子目录传入都解析到仓库根，避免多仓 workspace 下算错目标。
- **参数硬上限**：`--limit` 检索 ≤ 50 条，提交列表 ≤ 200 条。
- **JSON 输出**：成功和失败都通过 `ok`、`stage`、`message`、`next_action` 表达。

## 脚本入口

```bash
python scripts/ai_delivery_search.py --repo-root <repo> --query "..." [--limit 10]
python scripts/ai_delivery_since.py  --repo-root <repo> --since <commit|tag|origin/main> [--limit 50]
```

检索范围：`docs/delivery/`、`docs/ai-workflow/`、`docs/thoughts/`、`.worker_author_story/`；其中 `.worker_author_story/` 支持 Markdown 和 CSV。

## 围栏以内（AI 自由发挥）

- 用什么关键词检索历史，检索结果哪些值得作为上下文。
- `--since` 传什么基线：上次交付 commit、`origin/main`、tag 或日期 ref。
- 提交列表里哪些是人工变更、是否影响本次任务、要不要向使用者确认。
- 本次改动是否值得维护 Worker Author Story，写多详细，放哪个项目/仓库目录。
- Worker Author Story 写完后是否交给 `git-trunk-workflow` 显式暂存。

## 文档格式

需要维护交付故事日志时，格式参考 `references/generated_docs.md`；不强制章节齐全。
