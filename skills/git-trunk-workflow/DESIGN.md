# git-trunk-workflow: Protected Branches as Code, Not Trust

[中文版](./DESIGN_cn.md)

## Problem

AI Agents doing Git operations is useful but dangerous. A single `git push --force` or accidental merge to main can destroy work. Prompting "don't force push" is unreliable — as demonstrated in this repository's own incident log.

## Design Philosophy

**Protected branches, safe staging, and push restrictions are enforced by script logic. AI cannot bypass them regardless of what it's told to do.**

The AI has full freedom to decide *what* to commit and *how* to describe it, but the scripts physically prevent it from pushing to protected branches, force pushing, or staging everything blindly.

## Responsibility Layers

This skill is a **safe Git execution layer** only. It enforces technical safety invariants (protected branches, no force push, explicit staging). It does NOT own branch naming conventions or business delivery workflow decisions. Those belong to the orchestration layer (`work-orchestrator`), which decides:

- Whether a branch is needed
- Which source branch to use
- What to name the branch (e.g. `ai/<source>/<date>-<type>-<topic>`)
- When to push

### Local Git vs Hosting Platform MCP

This skill does not try to replace GitHub/GitLab/Gitee MCPs. The responsibility boundary is:

| Operation type | Recommended entry |
|---|---|
| Local branch creation, explicit staging, commit, push | `git-trunk-workflow` |
| Protected branches, no force push, audit trail | `git-trunk-workflow` |
| GitHub issues / PRs / reviews / actions | GitHub MCP |
| GitLab issues / MRs / pipelines | GitLab MCP |
| Gitee issues / pull requests / repository objects | Gitee MCP |
| Merging PR/MR, deleting branches, publishing releases | MCP may perform it, but requires extra confirmation |

Core principle: MCP handles remote hosting-platform objects; this skill handles local Git writes. Even if a generic Git MCP is configured later, it must not bypass this skill's protected-branch, explicit-staging, no-force-push, and audit fences.

## Implementation

### 1. Protected Branch Registry

`Test-ProtectedBranch` in `git_common.ps1` maintains a hardcoded list:
- Named: main, master, dev, uat, prod, production, staging
- Prefixed: release/*, hotfix/*

Any script that would modify these branches checks this function first and exits on match.

### 2. Push Restriction

`push_branch.ps1` checks before push:
1. Current branch must NOT be protected (`Assert-NotProtectedBranch`)

Only `git push -u origin <current-branch>` is executed. No `--force`, no alternative remote refs.

### 3. Stage Path Validation

`stage_paths.ps1` rejects:
- `.`, `*`, `:/`, `--all`, `-A`, `-u` (bulk staging)
- Any path containing wildcards
- Empty paths

Only explicit file paths are accepted. This prevents "git add everything" scenarios where unrelated or sensitive files get committed.

### 3.1 Controlled Ignored Staging

`stage_ignored_paths.ps1` is the only supported fallback for ignored paths that need to be committed. It:
- accepts only explicit file paths
- requires each path to be ignored by `.gitignore`
- stages with `git add -f` internally
- preserves the same audit/logging style as other Git helpers

This keeps ignored docs handling controlled instead of ad hoc.

### 4. No Branch Name Enforcement

This skill does not enforce any branch naming convention. The scripts only block creation of branches that share names with protected branches. Naming conventions (e.g. `ai/<source>/<YYYYMMDD>-<type>-<topic>`) are owned and enforced by the orchestration layer (`work-orchestrator`) via documentation.

### 5. Safe Sync Only

`create_branch.ps1` only syncs via `git pull --ff-only`. If fast-forward fails (diverged history), the script stops. No automatic merge, no automatic rebase.

### 6. Git Output Capture

`Invoke-GitCapture` temporarily sets `$ErrorActionPreference` to `Continue` while running native Git commands, captures stdout/stderr, and then restores the previous setting. Scripts judge failure only by Git exit code, so `remote:` lines and fetch/push progress on stderr do not become false PowerShell exceptions under StrictMode.

### 7. Git State Guard

`Assert-NoGitOperationInProgress` checks for MERGE_HEAD, REBASE_HEAD, CHERRY_PICK_HEAD, and rebase directories. If any exist, all operations are refused until the user resolves the state.

### 8. Commit on Protected Branch Rejected

`commit_cn.ps1` calls `Assert-NotProtectedBranch` before committing. Even if AI somehow stages files on a protected branch, the commit itself is blocked.

### 9. File Existence Validation Before Staging

`stage_paths.ps1` cross-checks every requested path against `git status` output. If a path has no changes (typo, wrong path, already committed), staging is refused with an explicit error listing the missing paths.

### 10. Audit Trail

All git operations (create branch, stage, commit, push, handoff summary) are logged to `logs/git-ops-YYYY-MM-DD.jsonl` with 7-day rotation. Audit records include timestamp, event type, branch, commit hash, and affected files.

### 11. Source Branch Staleness Detection

`git_handoff_summary.ps1` reports how many commits the source branch is ahead of the current branch. If source moved forward during development, the handoff explicitly warns about potential merge conflicts.

### 12. Script Failures Block Native Fallbacks

When `create_branch.ps1` fails, it outputs `native_git_fallback_forbidden` and `blocked_next_step`. Existing local branches, existing remote branches, and ff-only failures must stop the operation; the model must not bypass the script with `git checkout -b` or `git switch -c`.

### 13. Push Failure Guidance

When `push_branch.ps1` fails due to proxy/network issues, it outputs a `next_action` with a bypass command (`git -c http.proxy="" push`) instead of just an error message.

## Backward Compatibility

`create_ai_branch.ps1` and `push_ai_branch.ps1` are kept as thin wrappers that delegate to `create_branch.ps1` and `push_branch.ps1` respectively. Existing callers continue to work.

## What Was Deliberately Removed

- **10-step workflow documentation**: model knows Git flow
- **Commit message templates**: model writes Chinese naturally
- **Merge/backport strategy guide**: model can assess based on context
- **Validation checklist format**: model decides what to verify
- **Branch lifecycle management details**: model can suggest cleanup
- **GitHub/GitLab/Gitee platform workflow templates**: platform objects belong to the corresponding MCP, not this local Git skill
- **Platform config** (openai.yaml): obsolete
- **`ai/*` prefix enforcement on push**: replaced by protected-branch check, which is the actual safety invariant
- **`ai/*` naming enforcement on create**: moved to orchestration layer as an optional convention

## File Structure

```
git-trunk-workflow/
├── SKILL.md                     # Fence rules + script entry (~45 lines)
├── DESIGN.md                    # This file
├── DESIGN_cn.md                 # Chinese version
└── scripts/
    ├── git_common.ps1           # All fence logic (protected branches, validation)
    ├── git_preflight.ps1        # Read-only repo state check
    ├── create_branch.ps1        # Safe branch creation with ff-only sync
    ├── create_ai_branch.ps1     # Backward-compat wrapper → create_branch.ps1
    ├── stage_paths.ps1          # Explicit-path-only staging
    ├── commit_cn.ps1            # Chinese commit helper
    ├── push_branch.ps1          # Non-protected branch push, no force
    ├── push_ai_branch.ps1       # Backward-compat wrapper → push_branch.ps1
    ├── git_handoff_summary.ps1  # Handoff facts collection
    └── test_git_safety.py       # Safety tests
```
