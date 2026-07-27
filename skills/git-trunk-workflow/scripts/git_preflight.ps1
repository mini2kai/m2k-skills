param(
    [switch]$Fetch,
    [string]$RepositoryPath = '',
    [switch]$ListWorktrees
)

. "$PSScriptRoot\git_common.ps1"

try {
    $repo = Assert-GitRepository -RepoPath $RepositoryPath
    Assert-NoGitOperationInProgress -RepoPath $repo
    $repoRoot = Get-RepoRoot -RepoPath $repo
    $branch = Get-CurrentBranch -RepoPath $repo
    $fetchRan = $false
    if ($Fetch) {
        Invoke-GitLines -RepoPath $repo -Args @('fetch', 'origin', '--prune') | Out-Null
        $fetchRan = $true
    }
    $aheadBehind = Get-AheadBehind -RepoPath $repo
    $status = Split-Status -RepoPath $repo
    $allBranches = @(Invoke-GitLines -RepoPath $repo -Args @('branch', '--list') | ForEach-Object { $_.Trim().TrimStart('*').Trim() } | Where-Object { $_ })
    $shortLivedBranches = @($allBranches | Where-Object { -not (Test-ProtectedBranch -Branch $_) })
    $warning = Get-LongLivedBranchWarning -Branch $branch
    $worktreeInfo = Get-WorktreeInfo -RepoPath $repo
    $managedWorktrees = @()
    if ($ListWorktrees) {
        $managedRoot = Get-ManagedWorktreeRoot -RepoPath $repo
        foreach ($record in Get-GitWorktreeRecords -RepoPath $repo) {
            $recordPath = Normalize-FullPath -Path $record.worktree
            $isPrimary = Test-SamePath -Left $recordPath -Right (Get-PrimaryWorktreePath -RepoPath $repo)
            $isManaged = ((-not $isPrimary) -and (Test-PathInside -Child $recordPath -Parent $managedRoot))
            $clean = $null
            if ((Test-Path -LiteralPath $recordPath) -and (-not $record.bare)) {
                try { $clean = Test-WorktreeClean -RepoPath $recordPath } catch { $clean = $null }
            }
            $managedWorktrees += [ordered]@{
                path = $recordPath
                branch = $record.branch
                head = $record.head
                is_primary = $isPrimary
                managed = $isManaged
                clean = $clean
                locked = $record.locked
                prunable = $record.prunable
                reason = $record.reason
            }
        }
    }
    Write-JsonResult @{
        ok = $true
        repo_root = $repoRoot
        current_worktree_path = $worktreeInfo.current_worktree_path
        primary_worktree_path = $worktreeInfo.primary_worktree_path
        managed_worktree_root = $worktreeInfo.managed_worktree_root
        is_primary_worktree = $worktreeInfo.is_primary_worktree
        is_managed_worktree = $worktreeInfo.is_managed_worktree
        current_branch = $branch
        head = Get-HeadSha -RepoPath $repo
        upstream = $aheadBehind.upstream
        ahead = $aheadBehind.ahead
        behind = $aheadBehind.behind
        fetch_ran = $fetchRan
        clean = (Test-WorktreeClean -RepoPath $repo)
        staged = $status.staged
        unstaged = $status.unstaged
        untracked = $status.untracked
        short_lived_branches = $shortLivedBranches
        managed_worktrees = $managedWorktrees
        warning = $warning
        next_action = '如需创建 AI 临时分支，请运行 create_branch.ps1 创建隔离 worktree；后续 Git 写操作必须在返回的 worktree_path 中执行。'
    }
} catch {
    Write-JsonResult @{ ok = $false; error = $_.Exception.Message }
    exit 1
}
