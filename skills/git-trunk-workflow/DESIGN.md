# git-trunk-workflow: Safe Git Execution with Mandatory Worktree Isolation

[中文版](./DESIGN_cn.md)

## Problem

AI Agents doing Git operations are useful but dangerous. Traditional risks include `git push --force` and accidental commits to protected branches. Concurrent AI sessions add a deeper Git risk: a normal repository checkout has one shared HEAD, one working tree, and one index. Two sessions creating short-lived branches in the same checkout can switch each other's HEAD, mix files, and stage each other's changes.

## Design Philosophy

**Protected branches, safe staging, push restrictions, and concurrency isolation are enforced by scripts.**

This skill no longer creates AI branches with `git checkout -b` in the primary working tree. It always creates a linked `git worktree`, so each AI task gets its own working tree, HEAD, and index. AI can decide what to commit and how to describe it, but scripts physically prevent writes in the primary checkout, protected-branch pushes, force pushes, and blind bulk staging.

## Responsibility Layers

This skill is a **safe Git execution layer** only. It enforces technical safety invariants:

- AI short-lived branches must be created as isolated worktrees.
- Git writes may run only inside managed `.wt/` worktrees.
- Protected branches cannot be created, staged, committed, pushed, or removed as task worktrees.
- Push never uses force.
- Staging requires explicit paths.
- Git writes and worktree lifecycle events are audited.

It does not own branch naming conventions or business delivery decisions. Those belong to the orchestration layer (`work-orchestrator`), which decides the source branch, branch name, target repository, push timing, and cleanup timing.

## Local Git vs Hosting Platform MCP

This skill does not replace GitHub/GitLab/Gitee MCPs.

| Operation type | Recommended entry |
|---|---|
| Local isolated worktree branch creation, explicit staging, commit, push, cleanup | `git-trunk-workflow` |
| Protected branches, no force push, audit trail | `git-trunk-workflow` |
| GitHub issues / PRs / reviews / actions | GitHub MCP |
| GitLab issues / MRs / pipelines | GitLab MCP |
| Gitee issues / pull requests / repository objects | Gitee MCP |
| Merging PR/MR, deleting remote branches, publishing releases | MCP may perform it, but requires extra confirmation |

Core principle: MCP handles remote hosting-platform objects; this skill handles local Git writes. A generic Git MCP must not bypass this skill's protected-branch, explicit-staging, worktree-isolation, no-force-push, or audit fences.

## Implementation

### 1. Mandatory Isolated Worktrees

`create_branch.ps1` creates branches with:

```powershell
git worktree add <repo>/.wt/<safe-branch-name> -b <BranchName> <baseRef>
```

It no longer runs `git checkout <source>` or `git checkout -b <branch>` in the shared checkout. The default managed worktree root is:

```text
<primary-worktree>/.wt/
```

The branch name is converted into a Windows-safe directory name. The script ensures `.wt/` is ignored through the Git common dir `info/exclude`, so the primary checkout's `git status` is not polluted.

### 2. Explicit RepoPath and ExpectedBranch

Scripts bind operations to explicit paths:

- `create_branch.ps1` accepts `-RepositoryPath <repo>` to locate the concrete Git repository.
- `stage_paths.ps1`, `stage_ignored_paths.ps1`, `commit_cn.ps1`, `push_branch.ps1`, and `git_handoff_summary.ps1` accept `-RepoPath <worktree>`.
- Git write scripts accept `-ExpectedBranch <branch>` and refuse to continue if the current branch differs.

This prevents wrong-CWD, wrong-repo, wrong-branch, and concurrent-session mistakes.

### 3. Managed Worktree Guard

`git_common.ps1` provides `Assert-IsManagedIsolatedWorktree`. Git write scripts refuse:

- the primary checkout;
- external worktrees outside the managed `.wt/` root;
- non-Git paths;
- protected branches;
- branches that do not match `-ExpectedBranch`.

### 4. Protected Branch Registry

`Test-ProtectedBranch` in `git_common.ps1` maintains a hardcoded list:

- Named: main, master, dev, uat, prod, production, staging
- Prefixed: release/*, hotfix/*

Any script that would modify those branches checks this function first and exits on match.

### 5. Push Restriction

`push_branch.ps1` checks that it runs inside a managed isolated worktree, that the branch is not protected, and that `-ExpectedBranch` matches when provided.

It only runs:

```powershell
git push -u <remote> <current-branch>
```

No `--force`, no alternative remote ref. Push failure guidance tells the user to fix network/permission state and rerun the script; it does not provide a native `git push` bypass command.

### 6. Stage Path Validation

`stage_paths.ps1` rejects:

- `.`, `*`, `:/`, `--all`, `-A`, `-u`
- any wildcard path
- empty paths

It accepts explicit file paths only and cross-checks every requested path against the target worktree's `git status` output.

### 7. Controlled Ignored Staging

`stage_ignored_paths.ps1` is the only controlled entry for ignored paths. It accepts explicit paths, requires each path to be ignored by `.gitignore` or local exclude, runs `git add -f` internally, and writes audit logs.

### 8. Safe Sync Semantics

Worktree creation prefers `origin/<SourceBranch>` as the base ref, falling back to local `<SourceBranch>` when the remote ref is absent. If local and remote source refs diverge and local is not an ancestor of remote, the script refuses to merge or rebase automatically. `-SyncSource` only runs `git fetch origin --prune`; it does not checkout or pull in the primary checkout.

### 9. Git Output Capture

`Invoke-GitCapture` supports `-RepoPath` and runs Git as `git -C <RepoPath> ...`. It temporarily sets `$ErrorActionPreference` to `Continue`, captures stdout/stderr, restores the previous setting, and judges failure only by Git exit code.

### 10. Git State Guard

`Assert-NoGitOperationInProgress` checks MERGE_HEAD, REBASE_HEAD, CHERRY_PICK_HEAD, BISECT_LOG, and rebase directories. If any state is present, scripts refuse to continue until the user resolves it.

### 11. Commit Protection

`commit_cn.ps1` checks managed-worktree isolation, protected branches, expected branch, and commit title prefix before committing. Empty staging area still refuses commit.

### 12. Audit Trail and Registry

Git writes and handoff summaries are logged to:

```text
logs/git-ops-YYYY-MM-DD.jsonl
```

with 7-day rotation. Audit records include repo root, worktree path, primary worktree path, branch, commit hash, and affected files.

Worktree lifecycle is also registered under Git common dir:

```text
<git-common-dir>/git-trunk-workflow/worktrees.jsonl
```

The registry records create/remove events for recovery, inspection, expiry reminders, and safe cleanup.

### 13. Safe Cleanup

`remove_worktree.ps1` removes only managed `.wt/` worktrees. It checks that the path exists, is a Git worktree, is under the managed root, is on a non-protected branch, matches `-ExpectedBranch`, and has a clean `git status --short`. Dirty worktrees are refused. No force remove is used by default.

### 14. Script Failures Block Native Fallbacks

Script failures output `native_git_fallback_forbidden` or clear blocking guidance. Existing branches, remote branches, occupied worktree paths, protected branches, ExpectedBranch mismatches, dirty worktrees, and other guard failures must stop the operation. The model must not bypass scripts with native `git checkout -b`, `git switch -c`, `git worktree add`, `git add`, `git commit`, or `git push`.

## Backward Compatibility

`create_ai_branch.ps1` and `push_ai_branch.ps1` remain thin wrappers around `create_branch.ps1` and `push_branch.ps1`.

Core semantics changed deliberately:

- `create_branch.ps1` always creates an isolated worktree and never switches the current checkout.
- `-NoCheckout` remains accepted but is deprecated because worktree mode never switches the primary checkout.
- Later write operations need `-RepoPath <worktree_path>`, or the current CWD must already be inside a managed `.wt/` worktree.

## File Structure

```text
git-trunk-workflow/
├── SKILL.md                     # Fence rules + script entries
├── DESIGN.md                    # This file
├── DESIGN_cn.md                 # Chinese version
└── scripts/
    ├── git_common.ps1           # Git helpers, fences, worktree guard, registry
    ├── git_preflight.ps1        # Repository and worktree preflight
    ├── create_branch.ps1        # Create isolated worktree short-lived branch
    ├── create_ai_branch.ps1     # Backward-compat wrapper → create_branch.ps1
    ├── list_worktrees.ps1       # List Git worktrees and registry state
    ├── stage_paths.ps1          # Explicit-path-only staging, worktree only
    ├── stage_ignored_paths.ps1  # Controlled ignored-path staging, worktree only
    ├── commit_cn.ps1            # Chinese commit helper, worktree only
    ├── push_branch.ps1          # Non-protected branch push, no force, worktree only
    ├── push_ai_branch.ps1       # Backward-compat wrapper → push_branch.ps1
    ├── git_handoff_summary.ps1  # Handoff facts collection, worktree only
    ├── remove_worktree.ps1      # Safe managed worktree cleanup
    └── test_git_safety.py       # Safety and worktree integration tests
```
