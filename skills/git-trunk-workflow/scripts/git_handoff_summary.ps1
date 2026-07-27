param(
    [string]$SourceBranch = '',
    [string]$PrimaryTarget = '',
    [string]$BackportTarget = '',
    [string]$RepoPath = '',
    [string]$ExpectedBranch = ''
)

. "$PSScriptRoot\git_common.ps1"

function Get-DiffStatSafe {
    param([string]$Range, [string]$RepoPath = '')
    $result = Invoke-GitCapture -RepoPath $RepoPath -Args @('diff', '--stat', $Range)
    if ($result.ExitCode -ne 0) { return @() }
    return @($result.Lines)
}

function Get-LogSafe {
    param([string]$Range, [string]$RepoPath = '')
    $result = Invoke-GitCapture -RepoPath $RepoPath -Args @('log', '--oneline', $Range)
    if ($result.ExitCode -ne 0) { return @() }
    return @($result.Lines)
}

function Get-AheadBehindRange {
    param([string]$Ref1, [string]$Ref2, [string]$RepoPath = '')
    $result = Invoke-GitCapture -RepoPath $RepoPath -Args @('rev-list', '--left-right', '--count', "$Ref1...$Ref2")
    if ($result.ExitCode -ne 0) { return @{ ahead = $null; behind = $null } }
    $counts = ($result.Lines -join '').Trim() -split '\s+'
    return @{ ahead = [int]$counts[0]; behind = [int]$counts[1] }
}

try {
    $repo = Assert-GitRepository -RepoPath $RepoPath
    Assert-NoGitOperationInProgress -RepoPath $repo
    $worktreeInfo = Assert-IsManagedIsolatedWorktree -RepoPath $repo
    $branch = Get-CurrentBranch -RepoPath $repo
    Assert-ExpectedBranch -RepoPath $repo -ExpectedBranch $ExpectedBranch
    $status = Split-Status -RepoPath $repo
    $upstream = Get-Upstream -RepoPath $repo
    $remotePushed = -not [string]::IsNullOrWhiteSpace($upstream)
    $commits = @()
    $sourceLocalRef = if ($SourceBranch) { "refs/heads/$SourceBranch" } else { '' }
    $sourceRemoteRef = if ($SourceBranch) { "refs/remotes/origin/$SourceBranch" } else { '' }
    if ($SourceBranch) {
        $commitBaseRef = if (Test-GitRefExists -RepoPath $repo -Ref $sourceLocalRef) { $sourceLocalRef } else { $SourceBranch }
        $commits = @(Get-LogSafe -RepoPath $repo -Range "$commitBaseRef..HEAD")
    } else {
        $commits = @(Get-LogSafe -RepoPath $repo -Range '-5')
    }
    $primaryDiff = @()
    $primaryAheadBehind = @{ ahead = $null; behind = $null }
    if ($PrimaryTarget) {
        $primaryDiff = @(Get-DiffStatSafe -RepoPath $repo -Range "$PrimaryTarget..HEAD")
        $primaryAheadBehind = Get-AheadBehindRange -RepoPath $repo -Ref1 'HEAD' -Ref2 $PrimaryTarget
    }
    $backportDiff = @()
    if ($BackportTarget) { $backportDiff = @(Get-DiffStatSafe -RepoPath $repo -Range "$BackportTarget..HEAD") }

    # 来源分支领先当前分支多少（开发期间来源有新提交）
    $sourceAheadOfAi = $null
    $sourceCommit = ''
    $sourceRemoteRef = ''
    $sourceRemoteCommit = ''
    if ($SourceBranch) {
        if (Test-GitRefExists -RepoPath $repo -Ref $sourceLocalRef) { $sourceCommit = Get-FullSha -RepoPath $repo -Ref $sourceLocalRef }
        $sourceRemoteRef = "origin/$SourceBranch"
        $sourceRemoteCommit = Get-RemoteRefSha -RepoPath $repo -RemoteRef "refs/remotes/origin/$SourceBranch"
        # 来源分支比当前 ai 分支领先多少
        $sourceAheadBaseRef = if (Test-GitRefExists -RepoPath $repo -Ref $sourceLocalRef) { $sourceLocalRef } else { "refs/remotes/origin/$SourceBranch" }
        $sourceVsAi = Get-AheadBehindRange -RepoPath $repo -Ref1 $sourceAheadBaseRef -Ref2 'HEAD'
        $sourceAheadOfAi = $sourceVsAi.ahead
    }

    $head = Get-FullSha -RepoPath $repo
    Write-GitAuditLog -Event @{
        event = 'handoff_summary'
        repo_root = $worktreeInfo.primary_worktree_path
        worktree_path = $worktreeInfo.current_worktree_path
        primary_worktree_path = $worktreeInfo.primary_worktree_path
        is_isolated_worktree = $worktreeInfo.is_isolated_worktree
        branch = $branch
        expected_branch = $ExpectedBranch
        source_branch = $SourceBranch
        primary_target = $PrimaryTarget
        head = $head
    }
    Write-JsonResult @{
        ok = $true
        repo_root = $worktreeInfo.primary_worktree_path
        worktree_path = $worktreeInfo.current_worktree_path
        primary_worktree_path = $worktreeInfo.primary_worktree_path
        current_branch = $branch
        expected_branch = $ExpectedBranch
        current_head = $head
        source_branch = $SourceBranch
        source_commit = $sourceCommit
        source_remote_ref = $sourceRemoteRef
        source_remote_commit = $sourceRemoteCommit
        source_ahead_of_ai = $sourceAheadOfAi
        source_ahead_warning = if ($sourceAheadOfAi -and $sourceAheadOfAi -gt 0) { "来源分支 $SourceBranch 比当前分支领先 $sourceAheadOfAi 个 commit，合并时可能有冲突。" } else { $null }
        upstream = $upstream
        remote_pushed = $remotePushed
        commits = $commits
        clean = (Test-WorktreeClean -RepoPath $repo)
        staged_remaining = $status.staged
        unstaged_remaining = $status.unstaged
        untracked_remaining = $status.untracked
        primary_target = $PrimaryTarget
        primary_target_diff_stat = $primaryDiff
        primary_target_ahead = $primaryAheadBehind.ahead
        primary_target_behind = $primaryAheadBehind.behind
        backport_target = $BackportTarget
        backport_target_diff_stat = $backportDiff
        cleanup_suggestion = '合并完成并确认回灌后，可运行 remove_worktree.ps1 清理隔离 worktree；有未提交改动时脚本会拒绝删除。'
        cleanup_command = "powershell -NoProfile -ExecutionPolicy Bypass -File `"$PSScriptRoot\remove_worktree.ps1`" -WorktreePath `"$($worktreeInfo.current_worktree_path)`" -ExpectedBranch `"$branch`" -Prune"
        merge_warning = '脚本不执行长期分支 merge；如目标分支差异较大，优先建议 cherry-pick 或从目标分支重新开临时分支适配。'
    }
} catch {
    Write-JsonResult @{ ok = $false; error = $_.Exception.Message; native_git_fallback_forbidden = $true }
    exit 1
}
