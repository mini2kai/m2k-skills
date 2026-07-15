---
name: ai-delivery-hook
description: AI 代码交付留存和本地 Git hook 围栏。Use when AI is about to modify code, prepare delivery notes, activate/check AI delivery hooks, backfill unrecorded manual commits, or let work-orchestrator integrate delivery memory with Git handoff. Human/manual commits must not be blocked when no active AI session exists.
---

# AI Delivery Hook

## 围栏（代码强制，不可绕过）

以下限制由 `scripts/` 中的 Python 脚本执行：

- **active session 才强制**：只有 `session.local.json` 中 `actor=ai` 且 `status=active` 时，hook 才校验交付留存；无 active session 必须放行人工提交。
- **current schema 校验**：`current.local.json` 必须包含任务类型、标题、摘要、变更模块、风险等级、文档等级、验证项和文件列表，且标题不能为空。
- **prepared 防过期**：`ai_delivery_prepare.py` 生成 `prepared.local.json`，记录 `current_sha256`、changed files 和 repo-local 文档路径；hash、session 标题/类型、repo_root 或文件范围不匹配时 hook 必须阻断。
- **repo-local 文档**：AI 交付文档默认写入真实 Git 仓库的 `docs/delivery/` 和 `docs/ai-workflow/`，不写入未版本化 workspace 根目录作为主文档。
- **文档分级**：`doc_level` 只能是 `full|compact|skip`；`skip` 必须有 `skip_reason`，且 bugfix、hotfix、跨仓和高风险任务禁止 skip。
- **hook 增量接入**：`activate_project.py` 只追加或替换 ai-delivery managed block；检测到复杂 hook 管理器时输出 snippet，不覆盖原 hook。
- **人工变更补录**：`ai_delivery_start.py` 检测 `last_ai_seen_commit..HEAD`，发现未记录人工提交时输出 `requires_manual_backfill=true`。
- **多仓 workspace**：prepare 前必须显式确认 repo root，不允许靠 cwd 推断目标仓；如果 docs/ 被 `.gitignore` 忽略，必须走受控 ignored-docs 流程，不能临时手写 `git add -f`。
- **所有脚本 JSON 输出**：成功、阻断和用户动作都通过 JSON 的 `ok`、`stage`、`message`、`next_action` 表达，并写本地审计日志。

## 脚本入口

```bash
python scripts/activate_project.py --repo-root <repo> [--skill-root <skill>]
python scripts/doctor.py --repo-root <repo> [--skill-root <skill>]
python scripts/ai_delivery_search.py --repo-root <repo> --query "..."
python scripts/ai_delivery_start.py --repo-root <repo> --title "..." --type bugfix
python scripts/ai_delivery_prepare.py --repo-root <repo>
python scripts/check_ai_delivery.py --repo-root <repo> --mode pre-commit|pre-push
python scripts/ai_delivery_finish.py --repo-root <repo> --status completed|abandoned|no-code
```

多仓 workspace 激活：

```bash
python scripts/activate_project.py --workspace-root <workspace> --discover-repos
python scripts/doctor.py --workspace-root <workspace>
```

## 围栏以内（AI 自由发挥）

在脚本围栏内，AI 自行判断：

- 如何总结变更背景、影响范围和风险说明。
- 使用 `full`、`compact` 还是允许的 `skip` 文档等级。
- 人工提交是单独补录，还是纳入本次交付记录。
- 历史 delivery / workflow 文档中哪些结论值得参考。
- 如何把生成文档路径交给 `git-trunk-workflow` 做显式暂存和提交。
