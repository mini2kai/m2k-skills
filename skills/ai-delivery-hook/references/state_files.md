# State Files

本 skill 的运行态默认位于已安装 skill 根目录，文件名使用 `.local.json`，不进入 Git。

| 文件 | 生成者 | 用途 | 默认提交 |
|---|---|---|---|
| `activation.local.json` | `activate_project.py` | 记录激活过的 repo 和模式 | 否 |
| `workspace.local.json` | `activate_project.py` 或用户 | workspace/repo 映射 | 否 |
| `current.local.json` | AI / 总编排 | 本次交付输入 | 否 |
| `prepared.local.json` | `ai_delivery_prepare.py` | prepare 产物清单 | 否 |
| `session.local.json` | `ai_delivery_start.py` | active session 状态 | 否 |
| `checkpoint.local.json` | `ai_delivery_start.py` / `finish.py` | AI 接手基线 | 否 |
| `logs/*.jsonl` | 所有脚本 | 本地审计 | 否 |
| `backups/` | `activate_project.py` | hook 修改前备份 | 否 |

`.gitignore` 应忽略：

```text
*.local.json
*.local.jsonc
*.local.jsonl
logs/
backups/
```

生成后的项目知识资产不在 skill 目录，而在真实 Git 仓库：

```text
<repo_root>/docs/delivery/**/*.md
<repo_root>/docs/ai-workflow/**/*.md
```
