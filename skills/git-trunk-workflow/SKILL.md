---
name: git-trunk-workflow
description: Safe local Git operations with mandatory isolated git worktree branches, protected-branch enforcement, explicit staging, Chinese commits, push of non-protected branches, controlled worktree cleanup, and audit trail. Use when the user asks to create a short-lived branch, stage files, write Chinese commits, push non-protected branches, list/remove AI worktrees, or produce merge handoff notes. GitHub/GitLab/Gitee issue/PR/MR/review/CI/release operations should prefer the corresponding MCP; this skill does not merge long-lived branches, deploy, force push, discard changes, or run destructive Git operations.
---

# Git Trunk Workflow

## 围栏（代码强制，不可绕过）

以下限制由 `git_common.ps1` 和入口脚本代码执行：

- **强制 worktree 隔离**：AI 临时分支必须由 `create_branch.ps1` 创建到 `<repo>/.wt/<safe-branch>/`；禁止在主工作区 `checkout -b` / `switch -c`。
- **Git 写操作只允许在受控 worktree**：`stage_paths.ps1`、`stage_ignored_paths.ps1`、`commit_cn.ps1`、`push_branch.ps1`、`git_handoff_summary.ps1` 默认拒绝主工作区和非 `.wt/` worktree。
- **期望分支校验**：写操作支持 `-ExpectedBranch`，当前分支不匹配时拒绝，防止错目录、错分支提交。
- **保护分支拦截**：`Test-ProtectedBranch` 拒绝对 main/master/dev/uat/prod/release/* 的 create、stage、commit、push 和 worktree remove。
- **只 push 非保护分支**：`push_branch.ps1` 检查当前分支不是保护分支，否则直接拒绝。
- **禁止 force push**：脚本只执行 `git push -u`，不带 `--force`。
- **保护分支上禁止 commit**：`commit_cn.ps1` 提交前检查当前分支不是保护分支。
- **commit title 前缀强制**：`Assert-CommitTitlePrefix` 校验 title 必须以 `[feat]`、`[fix]`、`[refactor]`、`[perf]`、`[style]`、`[config]`、`[export]`、`[docs]`、`[chore]`、`[sql]`、`[hotfix]`、`[test]`、`[merge]` 之一开头，后跟空格和描述文字，否则拒绝提交。
- **禁止全量暂存**：`stage_paths.ps1` 拒绝 `.`、`*`、`--all`、`-A`、`-u`、通配符。
- **受控 ignored 暂存**：`stage_ignored_paths.ps1` 只允许显式列出的、确实被 `.gitignore` 或本地 exclude 忽略的路径使用 `git add -f`。
- **暂存前校验文件存在性**：路径不在目标 worktree 的 git status 中则拒绝，防止空暂存。
- **Git 中间状态检测**：`Assert-NoGitOperationInProgress` 检测 rebase/merge/cherry-pick 中间状态，有则拒绝执行。
- **同步只允许快进语义**：创建 worktree 时不自动 merge/rebase；本地来源与远端来源分叉时拒绝。
- **Git 输出按 exit code 判定**：`Invoke-GitCapture` 捕获 stdout/stderr，但只用 Git exit code 判断失败，避免 remote/progress 信息误报 error。
- **脚本失败即阻断**：入口脚本失败时禁止改用原生 `git checkout -b`、`git switch -c`、`git worktree add`、`git add`、`git commit` 或 `git push` 兜底；必须说明错误，修正原因后重跑脚本。
- **审计与 registry 留痕**：所有 git 写操作记录到 `logs/git-ops-YYYY-MM-DD.jsonl`，7 天轮转；worktree 生命周期登记到 Git common dir 下的 `git-trunk-workflow/worktrees.jsonl`。
- **安全清理**：`remove_worktree.ps1` 只删除受控 `.wt/` worktree；有未提交改动时拒绝删除，不默认 force。

## 脚本入口

```text
scripts/git_preflight.ps1       [-RepositoryPath <repo>] [-Fetch] [-ListWorktrees]
scripts/create_branch.ps1       -SourceBranch <branch> -BranchName <name> [-RepositoryPath <repo>] [-SyncSource]
scripts/create_ai_branch.ps1    -SourceBranch <branch> -BranchName <name> [-RepositoryPath <repo>] [-SyncSource]
scripts/list_worktrees.ps1      [-RepositoryPath <repo>]
scripts/stage_paths.ps1         -RepoPath <worktree> [-ExpectedBranch <branch>] -Paths path1,path2
scripts/stage_ignored_paths.ps1 -RepoPath <worktree> [-ExpectedBranch <branch>] -Paths path1,path2
scripts/commit_cn.ps1           -RepoPath <worktree> [-ExpectedBranch <branch>] -Title "..." [-Bullets "...","..."]
scripts/push_branch.ps1         -RepoPath <worktree> [-ExpectedBranch <branch>] [-Remote origin]
scripts/push_ai_branch.ps1      -RepoPath <worktree> [-ExpectedBranch <branch>] [-Remote origin]
scripts/git_handoff_summary.ps1 -RepoPath <worktree> [-ExpectedBranch <branch>] [-SourceBranch <branch>] [-PrimaryTarget <branch>] [-BackportTarget <branch>]
scripts/remove_worktree.ps1     -WorktreePath <worktree> [-ExpectedBranch <branch>] [-Prune]
```

调用方式：`powershell -NoProfile -ExecutionPolicy Bypass -File scripts/<name>.ps1 [参数]`

## 标准调用顺序

1. 在目标子仓库上运行 `create_branch.ps1 -RepositoryPath <repo> -SourceBranch <source> -BranchName <branch>`。
2. 读取返回 JSON 中的 `worktree_path`。
3. 后续代码修改、显式暂存、commit、push、handoff 全部绑定该 `worktree_path`，并建议传 `-ExpectedBranch <branch>`。
4. 合并完成并确认无未提交改动后，用 `remove_worktree.ps1` 清理。

多仓 workspace 下，必须分别对每个真实 Git 子仓库创建和记录自己的 `worktree_path`；不要在非 Git 根目录猜测执行。

## 托管平台 MCP 边界

本 skill 只负责本地 Git 状态和本地仓库写操作。GitHub/GitLab/Gitee 上的 issue、PR/MR、review、CI、release、远端仓库元数据等平台对象，优先交给对应 MCP。

本地隔离 worktree 创建、显式暂存、commit、push、清理仍必须走本 skill；不得用通用 Git MCP 或平台 MCP 绕过保护分支、显式暂存、禁止 force push、worktree 隔离和审计围栏。

## 围栏以内（AI 自由发挥）

在上述围栏保护下，AI 自行决定：

- 来源分支选择建议
- 分支命名（命名约定由调用方决定，例如 work-orchestrator 使用 `ai/<source>/<date>-<type>-<topic>` 格式）
- commit message 内容和详细程度
- 文件归属判断（本次任务 vs 无关变更）
- 验证方式和结果总结
- 交接摘要内容和格式
- 合并/回灌建议
- 判断是否需要 GitHub/GitLab/Gitee MCP 处理 PR/MR、issue、review 或 CI 信息
