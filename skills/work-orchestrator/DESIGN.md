# work-orchestrator：总控编排只做路由和阶段门

## 问题

单个专业 Skill 能把某一类操作做安全，但真实研发任务往往跨越需求理解、代码定位、数据库只读验证、日志取证、Git 分支、交付收口等多个环节。

如果让 AI 一上来就修改代码，风险不是能力不足，而是证据不足、边界不清和交付动作混在一起。

## 设计理念

`work-orchestrator` 只负责三件事：

```text
先理解，再实施。
能路由到专业 Skill 的，必须路由。
写操作和对外动作必须经过授权。
```

它不是专业 Skill 的总包实现器，不复制数据库、日志、Git 或 AI delivery 的脚本规则。它只判断当前阶段需要哪些能力，并把最小充分上下文交给对应 Skill。

## 核心流程

1. Intake：归纳问题，不急着分类。
2. Evidence：收集代码、日志、数据库、Git、文档等证据。
3. Plan：输出根因、方案、影响范围、验证计划和风险。
4. Execute：用户授权后才修改代码或仓库状态。
5. Verify：按方案验证，并记录未执行项。
6. Handoff：交给 Git 交付能力收口，按触发规则维护 Worker Author Story 交付故事日志，正式对外文档仍按需生成。

## AI delivery 与 Worker Author Story 接入

`ai-delivery-hook` 在 2026-08-04 收缩为只读能力（原因见该 skill 的 `DESIGN.md`），编排方式相应简化：

- Intake/Evidence 阶段可调 `ai_delivery_search.py` 检索历史留存作为影响范围证据，检索范围包括 `docs/delivery/`、`docs/ai-workflow/`、`docs/thoughts/` 和 `.worker_author_story/`。
- 接手既有仓库时可调 `ai_delivery_since.py --since <基线>` 列出该基线之后的提交，判断是否存在需纳入上下文的人工变更。
- 多仓 workspace 下，实施前必须先输出 repo map，并显式锁定 `workspace_root`、`code_repo_root`、`git_operation_repo_root`、`current_cwd`、`source_branch`、`ai_branch`；`code_repo_root` 必须等于 `git_operation_repo_root`。创建 Git 分支后，还必须记录 `git_worktree_path`，后续代码修改、暂存、commit、push 和 handoff 都绑定该隔离 worktree。
- commit 前做跨仓 `git status` 审计，确认没有误写到其他仓。
- 如果 docs/ 或 `.worker_author_story/` 被 `.gitignore` 忽略，必须走受控 ignored-docs 暂存流程；不能临时手写 `git add -f`。

Worker Author Story 由 `work-orchestrator` 在 Handoff 阶段维护，不属于 `ai-delivery-hook` 的写入职责。默认项目结构：

```text
.worker_author_story/
  INDEX.md
  branch-flow.csv
  logs/
    YYYY-MM.md
```

- `INDEX.md` 放轻量索引。
- `branch-flow.csv` 放来源分支、AI 工作分支、commit、push、合回状态，方便 Excel 查看。
- `logs/YYYY-MM.md` 按月追加需求和提交的详细交付故事。

这套日志用于内部长期追溯；正式技术/业务文档仍只在用户明确要求时生成。不再有 session 状态机和 Git hook 阻断。

## 与专业 Skill 的关系

- Git 隔离 worktree 分支创建、暂存、commit、push、清理：交给 `git-trunk-workflow`；后续写操作必须绑定其返回的 `worktree_path`。
- GitHub/GitLab/Gitee issue、PR/MR、review、CI、release 等平台对象：优先交给对应 MCP。
- AI 交付历史检索、接手前人工变更检测：交给 `ai-delivery-hook`（只读）。
- Worker Author Story 交付故事日志：由 `work-orchestrator` 组织上下文并维护项目级 `.worker_author_story/`，如需入库则交给 `git-trunk-workflow` 显式暂存、commit、push。
- 数据库日常只读验证：优先用数据库 MCP；本地 `postgres-query` 仍作为受控脚本方案可用。
- 服务器日志读取：交给 `server-docker-logs-readonly`。

专业 Skill 返回阻断时，不能改用原生命令绕过；应停住并复述错误和下一步选项。

## 刻意不做

- 不自动触发所有普通代码任务；仍以用户明确启用总控编排为主。
- 不静默修改代码、配置、Git hook、数据库或远端分支。
- 不合并长期分支，不部署，不发布。
- 不把数据库、日志、Git、AI delivery 的领域规则复制进总控文档。
