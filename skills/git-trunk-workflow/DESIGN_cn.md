# git-trunk-workflow：保护分支靠代码，不靠信任

## 问题

AI Agent 执行 Git 操作很有用但很危险。一次 `git push --force` 或误合并到 main 就能毁掉工作。提示词写"不要 force push"是不可靠的——本仓库自己的事故记录已经证明了这一点。

## 设计理念

**保护分支、安全暂存和 push 限制由脚本逻辑强制执行。无论 AI 被要求做什么，它都无法绕过这些限制。**

AI 可以自由决定提交什么内容、怎么描述，但脚本物理上阻止它 push 到保护分支、force push 或盲目暂存所有文件。

## 职责分层

本 Skill 只是**安全 Git 执行层**，负责强制技术安全不变量（保护分支、不 force push、显式暂存）。它不拥有分支命名约定或业务交付流程决策。这些属于编排层（`work-orchestrator`），由编排层决定：

- 是否需要创建分支
- 使用哪个来源分支
- 分支叫什么名字（例如 `ai/<source>/<date>-<type>-<topic>` 格式）
- 什么时候 push

### 本地 Git 与托管平台 MCP 分层

本 skill 不试图替代 GitHub/GitLab/Gitee MCP。职责边界是：

| 操作类型 | 推荐入口 |
|---|---|
| 本地分支创建、显式暂存、commit、push | `git-trunk-workflow` |
| 保护分支、防 force push、审计留痕 | `git-trunk-workflow` |
| GitHub issue / PR / review / actions | GitHub MCP |
| GitLab issue / MR / pipeline | GitLab MCP |
| Gitee issue / PR / 仓库对象 | Gitee MCP |
| 合并 PR/MR、删分支、release 发布 | MCP 可做，但必须额外确认 |

关键原则：MCP 处理远端平台对象，本 skill 处理本地 Git 写操作。即使未来配置了通用 Git MCP，也不能用它绕过本 skill 的保护分支、显式暂存、禁 force push 和审计围栏。

## 实现思路

### 1. 保护分支注册表

`git_common.ps1` 中的 `Test-ProtectedBranch` 维护硬编码列表：
- 命名：main、master、dev、uat、prod、production、staging
- 前缀：release/*、hotfix/*

任何可能修改这些分支的脚本都会先检查该函数，匹配则直接退出。

### 2. Push 限制

`push_branch.ps1` 在 push 前执行检查：
1. 当前分支不能是保护分支（`Assert-NotProtectedBranch`）

只执行 `git push -u origin <当前分支>`。没有 `--force`，没有替代远端引用。

### 3. 暂存路径校验

`stage_paths.ps1` 拒绝：
- `.`、`*`、`:/`、`--all`、`-A`、`-u`（全量暂存）
- 包含通配符的路径
- 空路径

只接受显式文件路径。防止"git add 所有文件"导致无关或敏感文件被提交。

### 4. 无分支命名强制

本 Skill 不强制任何分支命名约定。脚本只拦截与保护分支同名的分支创建。命名约定（如 `ai/<source>/<YYYYMMDD>-<type>-<topic>`）由编排层（`work-orchestrator`）通过文档约束。

### 5. 安全同步

`create_branch.ps1` 只通过 `git pull --ff-only` 同步。如果 fast-forward 失败（历史分叉），脚本停止。不自动 merge，不自动 rebase。

### 6. Git 输出捕获

`Invoke-GitCapture` 在执行原生 Git 命令时临时将 `$ErrorActionPreference` 降为 `Continue`，捕获 stdout/stderr 后恢复原设置。脚本只根据 Git exit code 判断失败，避免 `remote:`、fetch/push 进度等 stderr 信息在 PowerShell StrictMode 下被误当异常。

### 7. Git 状态守卫

`Assert-NoGitOperationInProgress` 检查 MERGE_HEAD、REBASE_HEAD、CHERRY_PICK_HEAD 和 rebase 目录。如果存在任何中间状态，拒绝所有操作直到用户解决。

### 8. 保护分支上禁止 commit

`commit_cn.ps1` 在提交前调用 `Assert-NotProtectedBranch`。即使 AI 在保护分支上暂存了文件，commit 本身也会被拦截。

### 9. 暂存前校验文件存在性

`stage_paths.ps1` 将每个请求路径与 `git status` 输出交叉验证。如果路径无变更（拼写错误、路径不对、已提交），暂存被拒绝并明确列出缺失路径。

### 10. 审计留痕

所有 git 操作（创建分支、暂存、提交、推送、交接摘要）记录到 `logs/git-ops-YYYY-MM-DD.jsonl`，7 天轮转。审计记录包含时间戳、事件类型、分支、commit hash 和涉及文件。

### 11. 来源分支过期检测

`git_handoff_summary.ps1` 报告来源分支比当前分支领先多少 commit。如果开发期间来源有新提交，交接时明确警告潜在合并冲突。

### 12. 脚本失败阻断原生命令兜底

`create_branch.ps1` 失败时输出 `native_git_fallback_forbidden` 和 `blocked_next_step`。分支已存在、远端已存在、ff-only 失败等情况都必须停住，禁止模型改用 `git checkout -b` 或 `git switch -c` 绕过脚本。

### 13. Push 失败指引

`push_branch.ps1` 因代理/网络问题失败时，输出 `next_action` 包含 bypass 命令（`git -c http.proxy="" push`），而不是只报错。

## 向后兼容

`create_ai_branch.ps1` 和 `push_ai_branch.ps1` 保留为薄包装脚本，分别转发到 `create_branch.ps1` 和 `push_branch.ps1`。现有调用方不受影响。

## 什么被刻意删掉了

- **10 步流程文档**：模型知道 Git 流程
- **提交信息模板**：模型自然能写中文
- **合并/回灌策略指南**：模型能根据上下文评估
- **验证清单格式**：模型自己决定验证什么
- **分支生命周期管理细节**：模型能给清理建议
- **GitHub/GitLab/Gitee 平台流程模板**：平台对象交给对应 MCP，不塞进本地 Git skill
- **平台配置**（openai.yaml）：已废弃
- **push 时强制 `ai/*` 前缀**：替换为保护分支检查，这才是真正的安全不变量
- **创建时强制 `ai/*` 命名格式**：上移到编排层作为可选约定

## 文件结构

```
git-trunk-workflow/
├── SKILL.md                     # 围栏规则 + 脚本入口（~45 行）
├── DESIGN.md                    # 英文设计文档
├── DESIGN_cn.md                 # 本文件
└── scripts/
    ├── git_common.ps1           # 所有围栏逻辑（保护分支、校验）
    ├── git_preflight.ps1        # 只读仓库状态检查
    ├── create_branch.ps1        # 安全分支创建 + ff-only 同步
    ├── create_ai_branch.ps1     # 向后兼容包装 → create_branch.ps1
    ├── stage_paths.ps1          # 只允许显式路径暂存
    ├── commit_cn.ps1            # 中文提交 helper
    ├── push_branch.ps1          # 非保护分支 push，不 force
    ├── push_ai_branch.ps1       # 向后兼容包装 → push_branch.ps1
    ├── git_handoff_summary.ps1  # 交接事实采集
    └── test_git_safety.py       # 安全测试
```
