# ai-delivery-hook：AI 代码交付留存围栏

## 问题

AI 参与代码修改后，如果只靠最终回复说明“改好了”，后续开发者和下一次 AI 很难判断：为什么改、改了哪些模块、如何验证、是否影响其他逻辑。最初可以粗暴地要求“所有 commit 都必须写交付文档”，但这会阻断用户自己的紧急修复和人工提交。

因此本 skill 的目标不是通用 commit 文档强制器，而是：**只强制 AI 对 AI 参与的代码交付负责，同时让下一次 AI 记住用户临时做过的人工变更。**

## 设计理念

核心边界：

```text
人工提交不阻断。
AI session 下强制留存。
AI 下次接手必须发现人工未记录提交。
```

判断是否强制不看 Git author，也不看是否有源码变更，而看本地 `session.local.json` 是否处于 active AI session。没有 active session 时，hook 必须放行；有 active session 时，hook 才校验 `current.local.json`、`prepared.local.json` 和 repo-local 文档。

## 文件结构

```text
ai-delivery-hook/
├── SKILL.md
├── DESIGN.md
├── references/
│   ├── delivery_schema.md
│   ├── state_files.md
│   ├── generated_docs.md
│   ├── hook_policy.md
│   ├── doc_levels.md
│   └── orchestrator_integration.md
└── scripts/
    ├── ai_delivery_common.py
    ├── activate_project.py
    ├── doctor.py
    ├── ai_delivery_search.py
    ├── ai_delivery_start.py
    ├── ai_delivery_prepare.py
    ├── check_ai_delivery.py
    ├── ai_delivery_finish.py
    └── test_ai_delivery.py
```

## 核心实现

### 1. active session

`ai_delivery_start.py` 写入 `session.local.json`：

```json
{
  "actor": "ai",
  "status": "active",
  "session_id": "20260713-143000-ai",
  "base_commit": "<commit>"
}
```

hook 只在该状态存在时强制。用户自己提交时没有 active session，直接放行。

### 2. 人工变更补录

`checkpoint.local.json` 记录上次 AI 看过的 commit。下一次 start 时比较：

```text
git log <last_ai_seen_commit>..HEAD
```

若存在提交，脚本输出 `requires_manual_backfill=true`，要求 AI 先生成 `manual-backfill` 记录，或把人工提交纳入本次交付说明。

### 3. prepared 防过期

`ai_delivery_prepare.py` 在生成文档后写 `prepared.local.json`，保存：

- `current_sha256`
- changed files
- delivery/workflow 文档路径
- session_id

`check_ai_delivery.py` 不只检查文档存在，还检查 current hash 和 staged files 是否仍然匹配。prepare 后继续改代码会被要求重新 prepare。

### 4. repo-local docs

交付文档默认写入真实 Git 仓库：

```text
<repo_root>/docs/delivery/YYYY-MM-DD/<slug>-delivery.md
<repo_root>/docs/ai-workflow/YYYY-MM-DD/<slug>-ai-workflow.md
```

workspace 根目录只适合放可选索引，不能作为首版强制主文档，否则在多仓目录中可能不被提交。

### 5. 增量 hook 接入

`activate_project.py` 默认只在已有 `pre-commit` / `pre-push` 中追加 managed block。重复执行时只替换 managed block，不修改区块外内容。检测到 Husky、lint-staged、pre-commit framework 等复杂 hook 管理器时返回 `requires_user_action=true` 和 snippet。

## 什么被刻意删掉了

- 不创建 `agents/openai.yaml`。
- 不创建 skill 内 README / CHANGELOG / INSTALLATION_GUIDE。
- 不在 hook 中自动生成或暂存文档。
- 不用 Git author 判断 AI / 人工。
- 不默认设置 `core.hooksPath` 接管项目 hook。
- 不做远端 CI 强校验；如需以后只针对 AI 标记提交扩展。

## 与总编排的关系

本 skill 不替代 `work-orchestrator`，也不替代 `git-trunk-workflow`。

推荐接入点：

1. Intake/Evidence：`ai_delivery_search.py` 检索历史留存。
2. Execute 前：`ai_delivery_start.py` 开启 active session。
3. Git 交付前：`ai_delivery_prepare.py` 生成文档。
4. commit/push：Git hook 调 `check_ai_delivery.py`。
5. Handoff 后：`ai_delivery_finish.py` 更新 checkpoint。

Git 分支、显式暂存、commit 和 push 仍交给 `git-trunk-workflow`。

## 风险与取舍

- AI 忘记 start：首版靠总编排显式调用和 `doctor.py` 检查；不尝试猜测所有提交。
- `--no-verify` 绕过 hook：首版只做本地围栏，CI 校验留到后续。
- 文档噪音：通过 `doc_level=full|compact|skip` 分级，skip 仍需最小记录。
- 多机器 checkpoint 不一致：默认 local，后续可增加 tracked mode。
- 人工变更目的不明确：补录文档必须标注 AI 判断依据和不确定部分。
