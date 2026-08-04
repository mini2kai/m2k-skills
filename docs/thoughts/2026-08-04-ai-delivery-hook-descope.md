# 2026-08-04 ai-delivery-hook 从强制围栏收缩为只读能力

## 起因

讨论多 AI 并发开发流程时，使用者提出一个观察：`ai-delivery-hook` 这个 hook "我用下来也不太会去关注"。

一个由代码强制、会阻断 commit 的机制，如果使用者完全没有感知，只有两种可能：它完美隐形（好），或者它压根没在运行（该处理）。

核查结果是后者。

## 核查发现

```text
.git/hooks/          只有 .sample，没有 pre-commit
*.local.json         不存在（activation / session / current / prepared 全无）
C:/Users/lzsj/all    maxdepth 3 内没有任何已安装该 hook 的项目
```

`activate_project.py` 从未对任何项目执行过。这个 skill 从 2026-07-13 设计至今，实际交付价值为 0，而它是仓库里最复杂的一个：7 个脚本，`ai_delivery_common.py` 16KB。

## 两个结构性问题

### 1. 状态全局单份，与并发 AI 对立

`ai_delivery_common.py` 的 `state_path()` 把状态写在 skill 目录下，不按 repo、不按 worktree 分片：

```python
return skill_root / STATE_NAMES[name]    # session.local.json 全局唯一
```

配合 `ai_delivery_start.py` 的 `session_already_active` 拒绝，多 AI 并行时：

| 顺序 | 结果 |
|---|---|
| AI-1 start | 成功 |
| AI-2 start | 直接失败 |
| AI-2 `--force` | 顶掉 AI-1 的 session，AI-1 提交时被 hook 阻断 |

而使用者的真实模式正是多个 AI 在各自 `.wt/` worktree 里并行处理不同任务。首版隐含假设了单 AI 串行。

### 2. 强制的对象是模型本来就能做的事

复核首版四个目标：

| 目标 | 是否需要 hook |
|---|---|
| AI 改代码要留痕 | 不需要——`commit_cn.ps1` 已强制中文详细 commit + 13 类前缀 |
| 人工提交不被阻断 | 不需要——这是引入 hook 后才产生的问题 |
| AI 接手时发现人工变更 | 需要保留，但一条 `git log <since>..HEAD` 就够 |
| 后续能判断影响 | 部分由 PR、commit、`docs/thoughts/` 承担 |

四条里只有一条是 git 和现有 skill 给不了的，而它不需要 hook、不需要 session 状态机。

hook 的复杂度代价却很实在：session 生命周期、prepared hash 防过期、doc_level 分级与 skip 禁令、多仓 workspace 确认、ignored-docs 流程——全部为"强制"而生。

## 判断依据

`skill-dev/references/design_philosophy.md` 的核心判断：

> 如果删掉后模型能自己完成，就删。

写交付文档恰好是模型能自己完成的事。用 `raise` 逼模型写文档，是把提示词层面的要求错误地升级成了代码围栏。

围栏应该守**不变量**（只读、路径白名单、禁 force push、凭据脱敏），而不是守**判断**（这次改动该不该写文档、写多详细）。

## 本次改动

保留两个只读能力：

```text
ai_delivery_search.py   检索 docs/delivery、docs/ai-workflow、docs/thoughts
ai_delivery_since.py    列出指定基线之后的提交（新增，替代 checkpoint 状态机）
```

删除：

```text
check_ai_delivery.py     pre-commit/pre-push 阻断
activate_project.py      hook 安装
ai_delivery_start.py     session 开启
ai_delivery_prepare.py   文档生成 + prepared hash
ai_delivery_finish.py    session 收口 + checkpoint
doctor.py                激活状态诊断
references/              hook_policy、state_files、doc_levels、delivery_schema、orchestrator_integration
```

`ai_delivery_common.py` 从 16KB 收缩到约 3KB。围栏从"强制文档齐全"改为"只读边界"：不写仓库、不写状态、不装 hook、必须是 Git 仓库、参数硬上限、JSON 输出。

同步更新 `work-orchestrator`（SKILL.md 与 DESIGN.md 大段编排引用）、`manifest.json`、README、INSTALLATION 和 `docs/README`。

测试从"跑脚本比对 JSON"改为直接测函数，17 项覆盖非 Git 目录拒绝、子目录归一、提交范围检索、非法 ref、limit 生效、检索打分与摘要截断。

## 保留的风险

- **没有强制留痕**：AI 可以完全不写交付文档。这是有意取舍——用 commit 质量替代文档强制。
- **人工变更检测需要显式基线**：`--since` 要手动给。首版用 `checkpoint.local.json` 自动记录，但那份状态同样全局单份，显式传参更适合并发。

如果将来变成团队多人协作、需要不可绕过的 AI 变更证据链，应该在 CI 层做，而不是回到本地 hook。

## 一般化的经验

这次的教训不只关于一个 skill：

1. **未被激活的围栏等于不存在。** 复杂度是真实的，收益是零。设计完成 ≠ 交付完成。
2. **围栏守不变量，不守判断。** 能被合理判断为"这次不需要"的事，就不该用 `raise` 强制。
3. **全局单份状态是并发的天敌。** 任何 `*.local.json` 写在 skill 目录而非按 repo/worktree 分片的设计，都要先问"N 个实例同时跑会怎样"。
4. **使用者说"我不关注这个"是重要信号。** 它往往意味着该机制没在工作，或者没有产生价值。
