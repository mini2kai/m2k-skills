param(
    [Parameter(Mandatory = $true)][string]$WorktreePath,
    [string]$ExpectedBranch = '',
    [switch]$Prune
)

. "$PSScriptRoot\git_common.ps1"

try {
    if (-not (Test-Path -LiteralPath $WorktreePath)) { throw "worktree 路径不存在：$WorktreePath" }
    $repo = Assert-GitRepository -RepoPath $WorktreePath
    Assert-NoGitOperationInProgress -RepoPath $repo
    $worktreeInfo = Assert-IsManagedIsolatedWorktree -RepoPath $repo -SkipRegistryCheck
    $branch = Get-CurrentBranch -RepoPath $repo
    Assert-NotProtectedBranch -Branch $branch -Action 'remove worktree'
    Assert-ExpectedBranch -RepoPath $repo -ExpectedBranch $ExpectedBranch
    if (-not (Test-WorktreeClean -RepoPath $repo)) {
        $status = Split-Status -RepoPath $repo
        throw "worktree 不干净，拒绝删除。staged=$($status.staged -join ', '); unstaged=$($status.unstaged -join ', '); untracked=$($status.untracked -join ', ')"
    }
    $ignored = @(Invoke-GitLines -RepoPath $repo -Args @('ls-files', '--others', '--ignored', '--exclude-standard'))
    if ($ignored.Count -gt 0) {
        throw "worktree 存在 ignored 未跟踪文件，拒绝删除以避免静默丢失：$($ignored -join ', ')"
    }

    $primary = $worktreeInfo.primary_worktree_path
    $head = Get-FullSha -RepoPath $repo
    Invoke-GitLines -RepoPath $primary -Args @('worktree', 'remove', $worktreeInfo.current_worktree_path) | Out-Null
    $pruneRan = $false
    if ($Prune) {
        Invoke-GitLines -RepoPath $primary -Args @('worktree', 'prune') | Out-Null
        $pruneRan = $true
    }

    Write-GitAuditLog -Event @{
        event = 'remove_worktree'
        repo_root = $primary
        worktree_path = $worktreeInfo.current_worktree_path
        primary_worktree_path = $primary
        is_isolated_worktree = $true
        branch = $branch
        expected_branch = $ExpectedBranch
        head = $head
        prune_ran = $pruneRan
    }
    Write-WorktreeRegistryEvent -RepoPath $primary -Event @{
        event = 'remove'
        status = 'removed'
        repo_root = $primary
        worktree_path = $worktreeInfo.current_worktree_path
        branch = $branch
        head = $head
        prune_ran = $pruneRan
    }
    Write-JsonResult @{
        ok = $true
        repo_root = $primary
        removed_worktree_path = $worktreeInfo.current_worktree_path
        branch = $branch
        expected_branch = $ExpectedBranch
        head = $head
        prune_ran = $pruneRan
        message = '已安全删除隔离 worktree。'
    }
} catch {
    Write-JsonResult @{ ok = $false; error = $_.Exception.Message; native_git_fallback_forbidden = $true }
    exit 1
}
