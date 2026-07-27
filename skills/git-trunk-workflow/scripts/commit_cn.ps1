param(
    [Parameter(Mandatory = $true)][string]$Title,
    [string[]]$Bullets = @(),
    [string]$RepoPath = '',
    [string]$ExpectedBranch = ''
)

. "$PSScriptRoot\git_common.ps1"

try {
    $repo = Assert-GitRepository -RepoPath $RepoPath
    Assert-NoGitOperationInProgress -RepoPath $repo
    $worktreeInfo = Assert-IsManagedIsolatedWorktree -RepoPath $repo
    $branch = Get-CurrentBranch -RepoPath $repo
    Assert-NotProtectedBranch -Branch $branch -Action 'commit'
    Assert-ExpectedBranch -RepoPath $repo -ExpectedBranch $ExpectedBranch
    Assert-CommitTitlePrefix -Title $Title
    $status = Split-Status -RepoPath $repo
    if ($status.staged.Count -eq 0) {
        throw '暂存区为空，拒绝 commit。请先显式暂存本次任务相关文件。'
    }
    $commitArgs = @('commit', '-m', $Title)
    foreach ($bullet in $Bullets) {
        if (-not [string]::IsNullOrWhiteSpace($bullet)) {
            $text = $bullet.Trim()
            if (-not $text.StartsWith('-')) { $text = "- $text" }
            $commitArgs += @('-m', $text)
        }
    }
    $commitResult = Invoke-GitCapture -RepoPath $repo -Args $commitArgs
    if ($commitResult.ExitCode -ne 0) {
        throw "git commit 失败：$($commitResult.Lines -join [Environment]::NewLine)"
    }
    $postStatus = Split-Status -RepoPath $repo
    $commit = Get-FullSha -RepoPath $repo
    Write-GitAuditLog -Event @{
        event = 'commit'
        repo_root = $worktreeInfo.primary_worktree_path
        worktree_path = $worktreeInfo.current_worktree_path
        primary_worktree_path = $worktreeInfo.primary_worktree_path
        is_isolated_worktree = $worktreeInfo.is_isolated_worktree
        branch = $branch
        expected_branch = $ExpectedBranch
        commit = $commit
        title = $Title
        files = $status.staged
    }
    Write-JsonResult @{
        ok = $true
        repo_root = $worktreeInfo.primary_worktree_path
        worktree_path = $worktreeInfo.current_worktree_path
        current_branch = $branch
        expected_branch = $ExpectedBranch
        commit = $commit
        commit_short = Get-HeadSha -RepoPath $repo
        title = $Title
        bullets = $Bullets
        committed_files = $status.staged
        unstaged_remaining = $postStatus.unstaged
        untracked_remaining = $postStatus.untracked
        message = '已在隔离 worktree 中创建中文详细 commit。'
    }
} catch {
    Write-JsonResult @{ ok = $false; error = $_.Exception.Message; native_git_fallback_forbidden = $true }
    exit 1
}
