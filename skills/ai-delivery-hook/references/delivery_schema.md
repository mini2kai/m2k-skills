# Delivery Schema

## current.local.json

AI 本次交付输入，写在 skill 根目录。

必填字段：

| 字段 | 说明 |
|---|---|
| `type` | `feature | bugfix | refactor | docs | config | test | hotfix | manual-backfill` |
| `title` | 交付标题 |
| `summary` | 一句话摘要 |
| `changed_modules` | 非空数组 |
| `risk_level` | `low | medium | high` |
| `doc_level` | `full | compact | skip` |
| `validation` | 非空数组 |
| `files` | 仓库内相对路径数组 |

可选字段：`reason`、`affected_modules`、`risk_notes`、`follow_up`、`ai_notes`、`context`、`skip_reason`、`manual_backfill`、`cross_repo`、`repositories`。

规则：

- `files` 必须是 repo 内相对路径。
- JSON 文件最大 256KB。
- `doc_level=skip` 必须提供 `skip_reason`。
- `bugfix`、`hotfix`、高风险和跨仓任务禁止 `skip`。

## prepared.local.json

由 `ai_delivery_prepare.py` 生成，供 hook 校验。

关键字段：

| 字段 | 说明 |
|---|---|
| `session_id` | 本次 AI session |
| `repo_id` | 仓库标识 |
| `repo_root` | 真实 Git 仓库 |
| `doc_level` | 文档等级 |
| `current_sha256` | 当前 `current.local.json` hash |
| `changed_files` | prepare 时覆盖的文件 |
| `delivery_doc` | repo-local delivery 文档路径 |
| `workflow_doc` | repo-local workflow 文档路径，可为空 |

## session.local.json

active AI session 状态。

必须满足：

```json
{
  "actor": "ai",
  "status": "active"
}
```

只有 active session 下 hook 才强制。

## checkpoint.local.json

AI 接手基线：

```json
{
  "last_ai_seen_commit": "<commit>",
  "last_ai_delivery_commit": "<commit>",
  "updated_at": "2026-07-13T15:00:00+08:00"
}
```

`ai_delivery_start.py` 用它检测人工未记录提交。
