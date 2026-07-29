# git-trunk-workflow：强制 worktree 隔离的安全 Git 执行层

## 问题

AI Agent 执行 Git 操作很有用但很危险。除了 `git push --force`、误提交到保护分支这类传统风险，多会话 AI 并发还会暴露普通 Git 工作区的共享状态问题：同一个仓库目录只有一个 HEAD、一个 working tree、一个 index。两个会话分别创建临时分支时，后一个 checkout 会切走前一个会话的 HEAD，暂存区和文件也可能互相污染。

## 设计理念

**保护分支、安全暂存、push 限制和并发隔离都由脚本逻辑强制执行。**

本 Skill 不再在主工作区通过 `git checkout -b` 创建 AI 临时分支，而是强制使用 `git worktree`：每个 AI 任务拥有独立 working tree、HEAD 和 index。AI 可以自由决定提交什么内容、怎么描述，但脚本物理上阻止它在主工作区写 Git、push 保护分支、force push 或盲目暂存所有文件。

## 职责分层

本 Skill 只是**安全 Git 执行层**，负责强制技术安全不变量：

- AI 临时分支必须在隔离 worktree 中创建；
- Git 写操作只能在受控 `.wt/` worktree 中执行；
- 保护分支不能 create、stage、commit、push；
- push 不允许 force；
- 暂存必须显式列路径；
- 所有写操作和 worktree 生命周期必须审计留痕。

它不拥有分支命名约定或业务交付流程决策。这些属于编排层（`work-orchestrator`），由编排层决定：

- 是否需要创建分支；
- 使用哪个来源分支；
- 分支叫什么名字（例如 `ai/<source>/<date>-<type>-<topic>`）；
- 当前任务涉及哪个 Git 子仓库；
- 什么时候 push；
- 什么时候清理 worktree。

## 本地 Git 与托管平台 MCP 分层

本 skill 不替代 GitHub/GitLab/Gitee MCP。职责边界是：

| 操作类型 | 推荐入口 |
|---|---|
| 本地隔离 worktree 分支创建、显式暂存、commit、push、清理 | `git-trunk-workflow` |
| 保护分支、防 force push、审计留痕 | `git-trunk-workflow` |
| GitHub issue / PR / review / actions | GitHub MCP |
| GitLab issue / MR / pipeline | GitLab MCP |
| Gitee issue / PR / 仓库对象 | Gitee MCP |
| 合并 PR/MR、删远端分支、release 发布 | MCP 可做，但必须额外确认 |

关键原则：MCP 处理远端平台对象，本 skill 处理本地 Git 写操作。即使未来配置了通用 Git MCP，也不能用它绕过本 skill 的保护分支、显式暂存、worktree 隔离、禁 force push 和审计围栏。

## 实现思路

### 1. 强制隔离 worktree

`create_branch.ps1` 使用：

```powershell
git worktree add <repo>/.wt/<safe-branch-name> -b <BranchName> <baseRef>
```

不再使用共享工作区中的 `git checkout <source>` 或 `git checkout -b <branch>`。默认 worktree 根目录为：

```text
<primary-worktree>/.wt/
```

分支名会被转换为 Windows 文件系统安全目录名。脚本会通过 Git common dir 下的 `info/exclude` 确保 `.wt/` 不污染主工作区 `git status`。

### 2. 显式 RepoPath / ExpectedBranch

入口脚本支持显式路径绑定：

- `create_branch.ps1` 使用 `-RepositoryPath <repo>` 定位具体 Git 子仓库；
- `stage_paths.ps1`、`stage_ignored_paths.ps1`、`commit_cn.ps1`、`push_branch.ps1`、`git_handoff_summary.ps1` 使用 `-RepoPath <worktree>`；
- 写操作支持 `-ExpectedBranch <branch>`，当前分支不匹配则拒绝。

这避免 AI 当前 CWD 错乱、跨子仓库误操作或并发会话串分支。

### 3. 受控 worktree guard

`git_common.ps1` 提供 `Assert-IsManagedIsolatedWorktree`。写操作会拒绝：

- 主工作区；
- 非 `.wt/` 下的外部 worktree；
- 当前路径不是 Git 工作区；
- 当前分支是保护分支；
- 当前分支不等于 `-ExpectedBranch`。

### 4. 保护分支注册表

`git_common.ps1` 中的 `Test-ProtectedBranch` 维护硬编码列表：

- 命名：main、master、dev、uat、prod、production、staging；
- 前缀：release/*、hotfix/*。

任何可能修改这些分支的脚本都会先检查该函数，匹配则直接退出。

### 5. Push 限制

`push_branch.ps1` 在 push 前检查：

1. 当前路径必须是受控 isolated worktree；
2. 当前分支不能是保护分支；
3. `-ExpectedBranch` 若存在必须匹配。

只执行 `git push -u <remote> <当前分支>`。没有 `--force`，没有替代远端引用。push 失败时只提示修复网络/权限后重跑脚本，不再给原生 `git push` 兜底命令。

### 6. 暂存路径校验

`stage_paths.ps1` 拒绝：

- `.`、`*`、`:/`、`--all`、`-A`、`-u`；
- 包含通配符的路径；
- 空路径。

只接受显式文件路径，并将每个请求路径与目标 worktree 的 `git status` 输出交叉验证。如果路径无变更（拼写错误、路径不对、已提交），暂存被拒绝并明确列出缺失路径。

### 7. 受控 ignored 暂存

`stage_ignored_paths.ps1` 是 ignored 文件入库的唯一受控入口。它：

- 只接受显式文件路径；
- 要求每个路径确实被 `.gitignore` 或本地 exclude 忽略；
- 内部执行 `git add -f`；
- 写入审计日志。

### 8. 安全同步

创建 worktree 时优先使用 `origin/<SourceBranch>` 作为 base ref；不存在时使用本地 `<SourceBranch>`。如果本地来源与远端来源不一致，且本地不是远端祖先，脚本拒绝自动 merge/rebase。`-SyncSource` 只执行 `git fetch origin --prune`，不会在主工作区 checkout 或 pull。

### 9. Git 输出捕获

`Invoke-GitCapture` 支持 `-RepoPath`，执行时内部使用 `git -C <RepoPath>`。它临时将 `$ErrorActionPreference` 降为 `Continue`，捕获 stdout/stderr 后恢复原设置。脚本只根据 Git exit code 判断失败，避免 `remote:`、fetch/push 进度等 stderr 信息在 PowerShell StrictMode 下被误当异常。

### 10. Git 状态守卫

`Assert-NoGitOperationInProgress` 检查 MERGE_HEAD、REBASE_HEAD、CHERRY_PICK_HEAD、BISECT_LOG 和 rebase 目录。如果存在任何中间状态，拒绝所有操作直到用户解决。

### 11. commit 保护

`commit_cn.ps1` 在提交前调用：

- `Assert-IsManagedIsolatedWorktree`；
- `Assert-NotProtectedBranch`；
- `Assert-ExpectedBranch`；
- `Assert-CommitTitlePrefix`。

即使 AI 在错误位置暂存了文件，commit 本身也会被拦截。

### 12. 审计与 registry

所有 git 写操作和交接摘要记录到：

```text
logs/git-ops-YYYY-MM-DD.jsonl
```

7 天轮转。审计记录包含 repo root、worktree path、primary worktree path、分支、commit hash、涉及文件等信息。

worktree 生命周期额外登记到 Git common dir：

```text
<git-common-dir>/git-trunk-workflow/worktrees.jsonl
```

它记录 create/remove 事件，方便找回、排查、过期提醒和安全清理。

### 13. 安全清理

`remove_worktree.ps1` 只删除受控 `.wt/` worktree。删除前检查：

- 路径存在且是 Git worktree；
- 路径位于受控 `.wt/` 下；
- 当前分支不是保护分支；
- `-ExpectedBranch` 匹配；
- `git status --short` 为空。

有未提交改动时拒绝删除，不默认 force。

### 14. 脚本失败阻断原生命令兜底

脚本失败时输出 `native_git_fallback_forbidden` 或明确阻断信息。分支已存在、远端已存在、worktree 路径占用、保护分支、ExpectedBranch 不匹配、dirty worktree 等情况都必须停住，禁止模型改用 `git checkout -b`、`git switch -c`、`git worktree add`、`git add`、`git commit` 或 `git push` 绕过脚本。

## 向后兼容

`create_ai_branch.ps1` 和 `push_ai_branch.ps1` 保留为薄包装脚本，分别转发到 `create_branch.ps1` 和 `push_branch.ps1`。

但核心语义已升级：

- `create_branch.ps1` 总是创建 isolated worktree，不再切换当前工作区；
- `-NoCheckout` 保留但废弃，因为 worktree 模式天然不会切主工作区；
- 后续写操作需要 `-RepoPath <worktree_path>`，或当前 CWD 必须位于受控 `.wt/` worktree。

## 文件结构

```text
git-trunk-workflow/
├── SKILL.md                     # 围栏规则 + 脚本入口
├── DESIGN.md                    # 英文设计文档
├── DESIGN_cn.md                 # 本文件
└── scripts/
    ├── git_common.ps1           # 公共 Git helper、围栏、worktree guard、registry
    ├── git_preflight.ps1        # 仓库状态和 worktree 预检
    ├── create_branch.ps1        # 创建隔离 worktree 临时分支
    ├── create_ai_branch.ps1     # 向后兼容包装 → create_branch.ps1
    ├── list_worktrees.ps1       # 列出 Git worktree 和 registry 状态
    ├── stage_paths.ps1          # 只允许显式路径暂存，强制 worktree
    ├── stage_ignored_paths.ps1  # 受控 ignored 路径暂存，强制 worktree
    ├── commit_cn.ps1            # 中文提交 helper，强制 worktree
    ├── push_branch.ps1          # 非保护分支 push，不 force，强制 worktree
    ├── push_ai_branch.ps1       # 向后兼容包装 → push_branch.ps1
    ├── git_handoff_summary.ps1  # 交接事实采集，强制 worktree
    ├── remove_worktree.ps1      # 安全清理受控 worktree
    └── test_git_safety.py       # 安全和 worktree 集成测试
```
