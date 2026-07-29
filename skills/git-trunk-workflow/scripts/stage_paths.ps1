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
    Assert-NotProtectedBranch -Branch $current -Action 'stage'
    Assert-ExpectedBranch -RepoPath $repo -ExpectedBranch $ExpectedBranch

    $forbidden = @('.', '*', ':/', '--all', '-A', '-u')
    foreach ($path in $Paths) {
        if ([string]::IsNullOrWhiteSpace($path)) { throw '路径不能为空。' }
        if ($forbidden -contains $path.Trim()) { throw "拒绝全量或模糊暂存表达：$path。请显式传文件路径。" }
        if ($path.Contains('*')) { throw "拒绝通配符路径：$path。请显式传文件路径。" }
    }

    # 校验文件存在性：确认路径在目标 worktree 的 git status 中真实存在
    $statusLines = Get-StatusShortLines -RepoPath $repo
    $knownPaths = @()
    foreach ($line in $statusLines) {
        if ($line.Length -ge 3) {
            $filePath = $line.Substring(3).Trim()
            # 处理重命名 "old -> new" 格式
            if ($filePath.Contains(' -> ')) {
                $parts = $filePath -split ' -> '
                $knownPaths += $parts[0].Trim()
                $knownPaths += $parts[1].Trim()
            } else {
                $knownPaths += $filePath
            }
        }
    }

    $notFound = @()
    foreach ($path in $Paths) {
        $normalized = $path.Trim().Replace('\', '/')
        $found = $false
        foreach ($known in $knownPaths) {
            if ($known.Replace('\', '/') -eq $normalized) { $found = $true; break }
        }
        if (-not $found) { $notFound += $path }
    }
    if ($notFound.Count -gt 0) {
        throw "以下路径不在目标 worktree 的 git status 中，无法暂存（可能路径错误或文件无改动）：$($notFound -join ', ')"
    }

    Invoke-GitLines -RepoPath $repo -Args (@('add', '--') + $Paths) | Out-Null
    $status = Split-Status -RepoPath $repo
    Write-GitAuditLog -Event @{
        event = 'stage'
        repo_root = $worktreeInfo.primary_worktree_path
        worktree_path = $worktreeInfo.current_worktree_path
        primary_worktree_path = $worktreeInfo.primary_worktree_path
        is_isolated_worktree = $worktreeInfo.is_isolated_worktree
        branch = $current
        expected_branch = $ExpectedBranch
        paths = $Paths
        head = Get-FullSha -RepoPath $repo
    }
    Write-JsonResult @{
        ok = $true
        repo_root = $worktreeInfo.primary_worktree_path
        worktree_path = $worktreeInfo.current_worktree_path
        current_branch = $current
        expected_branch = $ExpectedBranch
        staged_paths_requested = $Paths
        staged_now = $status.staged
        unstaged_now = $status.unstaged
        untracked_now = $status.untracked
        message = '已在隔离 worktree 中按显式路径暂存。'
    }
} catch {
    Write-JsonResult @{ ok = $false; error = $_.Exception.Message; native_git_fallback_forbidden = $true }
    exit 1
}
