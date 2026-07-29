param(
    [string]$Remote = 'origin',
    [string]$RepoPath = '',
    [string]$ExpectedBranch = ''
)

. "$PSScriptRoot\git_common.ps1"

try {
    $repo = Assert-GitRepository -RepoPath $RepoPath
    Assert-NoGitOperationInProgress -RepoPath $repo
    $worktreeInfo = Assert-IsManagedIsolatedWorktree -RepoPath $repo
    $branch = Get-CurrentBranch -RepoPath $repo
    Assert-NotProtectedBranch -Branch $branch -Action 'push'
    Assert-ExpectedBranch -RepoPath $repo -ExpectedBranch $ExpectedBranch
    $pushResult = Invoke-GitCapture -RepoPath $repo -Args @('push', '-u', $Remote, $branch)
    if ($pushResult.ExitCode -ne 0) {
        $errorText = $pushResult.Lines -join [Environment]::NewLine
        $nextAction = 'git push 失败。请修复网络、权限或远端状态后重新运行 push_branch.ps1；禁止改用原生 git push 兜底。'
        if ($errorText -match 'Proxy|proxy|CONNECT') {
            $nextAction = '疑似网络代理问题。请修复代理配置后重新运行 push_branch.ps1；禁止改用原生 git push 兜底。'
        }
        Write-JsonResult @{ ok = $false; error = 'push_failed'; message = $errorText; next_action = $nextAction; native_git_fallback_forbidden = $true }
        exit 1
    }
    $head = Get-FullSha -RepoPath $repo
    Write-GitAuditLog -Event @{
        event = 'push'
        repo_root = $worktreeInfo.primary_worktree_path
        worktree_path = $worktreeInfo.current_worktree_path
        primary_worktree_path = $worktreeInfo.primary_worktree_path
        is_isolated_worktree = $worktreeInfo.is_isolated_worktree
        remote = $Remote
        branch = $branch
        expected_branch = $ExpectedBranch
        head = $head
    }
    Write-JsonResult @{
        ok = $true
        repo_root = $worktreeInfo.primary_worktree_path
        worktree_path = $worktreeInfo.current_worktree_path
        remote = $Remote
        branch = $branch
        expected_branch = $ExpectedBranch
        head = $head
        message = '已 push 当前隔离 worktree 分支。'
    }
} catch {
    Write-JsonResult @{ ok = $false; error = $_.Exception.Message; native_git_fallback_forbidden = $true }
    exit 1
}
