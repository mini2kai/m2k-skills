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
6. Handoff：交给 Git / AI delivery 能力收口。

## AI delivery 接入

当 `ai-delivery-hook` 可用，且任务进入代码修改或 Git 交付路径时，`work-orchestrator` 必须把它纳入编排：

- 执行前查历史留存并开启 active AI session。
- 当前 repo 未激活 hook 时，先询问用户是否允许增量写入 Git hook；用户同意后由 AI 自动执行激活命令。
- 多仓 workspace 下，实施前必须先输出 repo map，并显式锁定 `workspace_root`、`code_repo_root`、`delivery_repo_root`、`git_operation_repo_root`、`current_cwd`、`source_branch`、`ai_branch`；`code_repo_root` 必须等于 `git_operation_repo_root`。
- Git handoff 前由 AI 生成 `current.local.json`，再调用 prepare 生成 repo-local docs；prepare 前必须校验 session/title/files 是否属于本次任务，发现旧 session 或旧标题要先重启。
- commit/push 阶段不绕过 hook 阻断；commit 前还要做跨仓 `git status` 审计，确认没有误写到其他仓。
- 如果 docs/ 被 `.gitignore` 忽略，必须走受控 ignored-docs 暂存流程；不能临时手写 `git add -f`。
- commit 后调用 finish 关闭 session 并更新 checkpoint。

这样用户不需要记 Python 命令，只需要对首次 hook 激活、commit、push 等有副作用动作做授权。

## 与专业 Skill 的关系

- Git 分支、暂存、commit、push：交给 `git-trunk-workflow`。
- GitHub/GitLab/Gitee issue、PR/MR、review、CI、release 等平台对象：优先交给对应 MCP。
- AI 代码交付留存：交给 `ai-delivery-hook`。
- 数据库日常只读验证：优先用数据库 MCP；本地 `postgres-query` 仍作为受控脚本方案可用。
- 服务器日志读取：交给 `server-docker-logs-readonly`。

专业 Skill 返回阻断时，不能改用原生命令绕过；应停住并复述错误和下一步选项。

## 刻意不做

- 不自动触发所有普通代码任务；仍以用户明确启用总控编排为主。
- 不静默修改代码、配置、Git hook、数据库或远端分支。
- 不合并长期分支，不部署，不发布。
- 不把数据库、日志、Git、AI delivery 的领域规则复制进总控文档。
