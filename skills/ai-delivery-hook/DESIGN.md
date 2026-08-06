# ai-delivery-hook：从强制围栏收缩为只读上下文能力

## 首版设计与实际结果

首版目标是用 Git hook 强制 AI 交付留存：`session.local.json` 标记 active AI session，hook 在 pre-commit/pre-push 校验 `current.local.json`、`prepared.local.json` 和 repo-local 文档，人工提交在无 active session 时放行。设计文档见 `docs/thoughts/2026-07-13-ai-delivery-hook-design.md`。

2026-08-04 复核时发现：**这套机制从未被激活过。**

- 本仓库 `.git/hooks/` 下只有 `.sample`，没有 `pre-commit`。
- 没有任何 `activation.local.json`、`session.local.json`、`current.local.json`。
- 在 `C:/Users/lzsj/all` 下也没找到已安装该 hook 的项目。

也就是说它交付的实际价值是 0，而它是仓库里最复杂的 skill：7 个脚本，`ai_delivery_common.py` 16KB。使用者本人也表示"不太会去关注这个 hook"。

## 两个致命问题

### 1. 状态全局单份，和并发 AI 冲突

`state_path()` 把状态写在 **skill 目录**下，不按 repo、更不按 worktree 分片：

```python
return skill_root / STATE_NAMES[name]   # session.local.json 全局唯一
```

配合 `ai_delivery_start.py` 的 `session_already_active` 拒绝，多个 AI 并行时第二个必然失败，用 `--force` 则顶掉第一个的 session，导致其 commit 被 hook 阻断。

而使用者的真实工作模式正是**多个 AI 在各自 `.wt/` worktree 里并行处理不同任务**。首版隐含假设了单 AI 串行，与实际场景对立。

### 2. 强制的对象是模型本来就能做的事

复核首版四个目标：

| 目标 | 是否需要 hook |
|---|---|
| AI 改代码要留痕 | 不需要——`commit_cn.ps1` 已强制中文详细 commit + 13 类前缀，git history 就是留痕 |
| 人工提交不被阻断 | 不需要——这是引入 hook 后才产生的问题，去掉 hook 即消失 |
| AI 接手时发现人工变更 | **需要保留**，但一条 `git log <since>..HEAD` 就够，不需要 session 状态机 |
| 后续能判断影响 | 部分由 PR、commit、`.worker_author_story/`、`docs/thoughts/` 承担 |

四条里只有一条是 git 和现有 skill 给不了的，且它不需要 hook。

而 hook 的复杂度代价很实在：session 生命周期、prepared hash 防过期、doc_level 分级与 skip 禁令、多仓 workspace 确认、ignored-docs 流程。全部是为了"强制"而生。

按 `skill-dev` 的核心判断——**如果删掉后模型能自己完成，就删**——写交付文档恰好是模型能自己完成的事，不需要 `raise` 来逼。

## 本版设计

只保留两个只读能力：

```text
ai_delivery_search.py   查历史留存（含 .worker_author_story/），给后续任务提供上下文
ai_delivery_since.py    列出指定版本之后的提交，判断人工变更
```

围栏从"强制文档齐全"收缩为"只读边界"：不写仓库、不写状态、不装 hook、必须是 Git 仓库、参数硬上限、JSON 输出。

删掉：

```text
check_ai_delivery.py     pre-commit/pre-push 阻断
activate_project.py      hook 安装
ai_delivery_start.py     session 开启
ai_delivery_prepare.py   文档生成 + prepared hash
ai_delivery_finish.py    session 收口 + checkpoint
doctor.py                激活状态诊断
references/hook_policy.md、state_files.md、doc_levels.md、delivery_schema.md、orchestrator_integration.md
```

`ai_delivery_common.py` 从 16KB 收缩到约 3KB：只留 `DeliveryError`、JSON 输出、`git()`、`resolve_repo_root()`、`read_doc_summary()`。

## 刻意删掉了什么

- **doc_level 分级和 skip 禁令**：该不该写文档、写多详细由使用者和模型判断，不由脚本枚举校验。
- **session 状态机**：并发下必然冲突，且它解决的是"AI 是否在工作"这个模型自己知道的问题。
- **prepared hash 防过期**：为 hook 阻断服务，hook 去掉后失去意义。
- **多仓 workspace 强制确认**：`--repo-root` 必传且解析到仓库根，已经够。
- **审计日志**：只读操作不需要留痕，git history 本身就是审计。

## 并发适配

改造后天然支持多 AI 并行：脚本无状态、无写入，N 个进程同时调用互不干扰。`--repo-root` 可以是主工作区或任意 `.wt/` worktree。

## 与其他 skill 的关系

- `git-trunk-workflow`：分支、暂存、commit、push 仍全部由它负责，留痕靠中文详细 commit。
- `work-orchestrator`：Intake/Evidence 阶段可调 `ai_delivery_search.py` 取历史上下文，接手时可调 `ai_delivery_since.py` 检测人工变更；Handoff 阶段自行维护项目级 `.worker_author_story/`，本 skill 不再编排 start/prepare/finish，也不写日志。

## 保留的风险

- **没有代码强制留痕**：本 skill 不用 hook 阻断来强制写文档。需要长期追溯时，由 `work-orchestrator` 在 Handoff 阶段维护 `.worker_author_story/`；如果将来变成团队多人协作、需要不可绕过的 AI 变更证据链，应该在 CI 层做，而不是回到本地 hook。
- **人工变更检测需要显式基线**：`--since` 要手动给。首版用 `checkpoint.local.json` 自动记录，但那份状态同样是全局单份。显式传参更适合并发。
