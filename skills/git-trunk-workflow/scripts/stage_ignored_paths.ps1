param(
    [Parameter(Mandatory = $true)][string[]]$Paths,
    [string]$RepoPath = '',
    [string]$ExpectedBranch = ''
)

. "$PSScriptRoot\git_common.ps1"

try {
    $repo = Assert-GitRepository -RepoPath $RepoPath
    Assert-NoGitOperationInProgress -RepoPath $repo
    $worktreeInfo = Assert-IsManagedIsolatedWorktree -RepoPath $repo
    $current = Get-CurrentBranch -RepoPath $repo
    Assert-NotProtectedBranch -Branch $current -Action 'stage ignored'
    Assert-ExpectedBranch -RepoPath $repo -ExpectedBranch $ExpectedBranch

    $forbidden = @('.', '*', ':/', '--all', '-A', '-u')
    foreach ($path in $Paths) {
        if ([string]::IsNullOrWhiteSpace($path)) { throw '路径不能为空。' }
        if ($forbidden -contains $path.Trim()) { throw "拒绝全量或模糊暂存表达：$path。请显式传文件路径。" }
        if ($path.Contains('*')) { throw "拒绝通配符路径：$path。请显式传文件路径。" }
    }

    $ignored = @()
    foreach ($path in $Paths) {
        $normalized = $path.Trim().Replace('\', '/')
        $check = Invoke-GitCapture -RepoPath $repo -Args @('check-ignore', '--quiet', '--', $normalized)
        if ($check.ExitCode -ne 0) {
            throw "以下路径未被 .gitignore 或本地 exclude 忽略，不能走受控 ignored 暂存：$path"
        }
        $ignored += $normalized
    }

    Invoke-GitLines -RepoPath $repo -Args (@('add', '-f', '--') + $ignored) | Out-Null
    $status = Split-Status -RepoPath $repo
    Write-GitAuditLog -Event @{
        event = 'stage_ignored'
        repo_root = $worktreeInfo.primary_worktree_path
        worktree_path = $worktreeInfo.current_worktree_path
        primary_worktree_path = $worktreeInfo.primary_worktree_path
        is_isolated_worktree = $worktreeInfo.is_isolated_worktree
        branch = $current
        expected_branch = $ExpectedBranch
        paths = $ignored
        head = Get-FullSha -RepoPath $repo
    }
    Write-JsonResult @{
        ok = $true
        repo_root = $worktreeInfo.primary_worktree_path
        worktree_path = $worktreeInfo.current_worktree_path
        current_branch = $current
        expected_branch = $ExpectedBranch
        staged_paths_requested = $ignored
        staged_now = $status.staged
        unstaged_now = $status.unstaged
        untracked_now = $status.untracked
        message = '已在隔离 worktree 中按受控 ignored 路径暂存。'
    }
} catch {
    Write-JsonResult @{ ok = $false; error = $_.Exception.Message; native_git_fallback_forbidden = $true }
    exit 1
}
