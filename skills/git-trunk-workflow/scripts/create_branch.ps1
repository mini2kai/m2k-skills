param(
    [Parameter(Mandatory = $true)][string]$SourceBranch,
    [Parameter(Mandatory = $true)][string]$BranchName,
    [string]$RepositoryPath = '',
    [switch]$SyncSource,
    [switch]$NoCheckout
)

. "$PSScriptRoot\git_common.ps1"

try {
    $repoRoot = Assert-GitRepository -RepoPath $RepositoryPath
    Assert-NoGitOperationInProgress -RepoPath $repoRoot
    Assert-NotProtectedBranch -Branch $BranchName -Action 'create isolated worktree branch'
    $branchNameCheck = Invoke-GitCapture -RepoPath $repoRoot -Args @('check-ref-format', "refs/heads/$BranchName")
    if ($branchNameCheck.ExitCode -ne 0) { throw "分支名非法：$BranchName。$($branchNameCheck.Lines -join [Environment]::NewLine)" }
    $sourceBranchCheck = Invoke-GitCapture -RepoPath $repoRoot -Args @('check-ref-format', "refs/heads/$SourceBranch")
    if ($sourceBranchCheck.ExitCode -ne 0) { throw "来源分支名非法：$SourceBranch。$($sourceBranchCheck.Lines -join [Environment]::NewLine)" }

    $fetchRan = $false
    if ($SyncSource) {
        Invoke-GitLines -RepoPath $repoRoot -Args @('fetch', 'origin', '--prune') | Out-Null
        $fetchRan = $true
    }

    $localBranchRef = "refs/heads/$BranchName"
    $exists = Invoke-GitCapture -RepoPath $repoRoot -Args @('rev-parse', '--verify', '--quiet', $localBranchRef)
    if ($exists.ExitCode -eq 0) {
        throw "本地分支已存在：$BranchName。禁止改用 git checkout -b、git switch -c 或 git worktree add 绕过脚本；请确认是否切换到已有隔离 worktree、改用新分支名，或清理后重新运行本脚本。"
    }

    $remoteNewBranch = "origin/$BranchName"
    $remoteNewBranchRef = "refs/remotes/origin/$BranchName"
    $remoteExists = Invoke-GitCapture -RepoPath $repoRoot -Args @('rev-parse', '--verify', '--quiet', $remoteNewBranchRef)
    if ($remoteExists.ExitCode -eq 0) {
        throw "远端分支已存在：$remoteNewBranch。禁止改用 git checkout -b、git switch -c 或 git worktree add 绕过脚本；请确认是否跟踪远端已有分支或改用新分支名。"
    }

    $sourceLocalRef = "refs/heads/$SourceBranch"
    $sourceRemote = "origin/$SourceBranch"
    $sourceRemoteRef = "refs/remotes/origin/$SourceBranch"
    $sourceLocalExists = Test-GitRefExists -RepoPath $repoRoot -Ref $sourceLocalRef
    $sourceRemoteExists = Test-GitRefExists -RepoPath $repoRoot -Ref $sourceRemoteRef
    if (-not $sourceLocalExists -and -not $sourceRemoteExists) {
        throw "来源分支不存在：$SourceBranch，也找不到 $sourceRemote。请先确认来源分支或执行 -SyncSource 后重试。"
    }

    $baseRef = if ($sourceRemoteExists) { $sourceRemoteRef } else { $sourceLocalRef }
    if ($sourceLocalExists -and $sourceRemoteExists) {
        $sourceLocalSha = Get-FullSha -RepoPath $repoRoot -Ref $sourceLocalRef
        $sourceRemoteSha = Get-FullSha -RepoPath $repoRoot -Ref $sourceRemoteRef
        if ($sourceLocalSha -ne $sourceRemoteSha) {
            $localIsAncestor = Test-GitAncestor -RepoPath $repoRoot -Ancestor $sourceLocalRef -Descendant $sourceRemoteRef
            if (-not $localIsAncestor) {
                throw "来源分支 $SourceBranch 与 $sourceRemote 不一致，且本地不是远端的祖先；拒绝自动 merge/rebase。请先人工确认来源分支状态后重试。"
            }
        }
    }

    $sourceCommit = Get-FullSha -RepoPath $repoRoot -Ref $baseRef
    $sourceRemoteShaOut = if ($sourceRemoteExists) { Get-FullSha -RepoPath $repoRoot -Ref $sourceRemoteRef } else { '' }
    $safeName = ConvertTo-SafeWorktreeName -Branch $BranchName
    $worktreeRoot = Get-ManagedWorktreeRoot -RepoPath $repoRoot
    $worktreePath = Normalize-FullPath -Path (Join-Path $worktreeRoot $safeName)

    if (Test-Path -LiteralPath $worktreePath) {
        throw "目标 worktree 路径已存在：$worktreePath。为避免覆盖或误用，拒绝创建。"
    }

    $records = Get-GitWorktreeRecords -RepoPath $repoRoot
    foreach ($record in $records) {
        if ((-not [string]::IsNullOrWhiteSpace($record.worktree)) -and (Test-SamePath -Left $record.worktree -Right $worktreePath)) {
            throw "目标 worktree 路径已被 Git 登记占用：$worktreePath。请先清理残留 worktree。"
        }
        if ($record.branch -eq $BranchName) {
            throw "分支 $BranchName 已被 worktree 占用：$($record.worktree)。请切换到该 worktree 或改用新分支名。"
        }
    }

    $excludePath = Ensure-WorktreeRootIgnored -RepoPath $repoRoot
    Invoke-GitLines -RepoPath $repoRoot -Args @('worktree', 'add', '-b', $BranchName, $worktreePath, $baseRef) | Out-Null

    $newHead = Get-FullSha -RepoPath $worktreePath
    Write-GitAuditLog -Event @{
        event = 'create_worktree'
        repo_root = $repoRoot
        worktree_path = $worktreePath
        primary_worktree_path = Get-PrimaryWorktreePath -RepoPath $repoRoot
        is_isolated_worktree = $true
        source_branch = $SourceBranch
        source_ref = $baseRef
        source_commit = $sourceCommit
        source_remote_ref = $sourceRemote
        source_remote_commit = $sourceRemoteShaOut
        new_branch = $BranchName
        new_branch_head = $newHead
        fetch_ran = $fetchRan
        no_checkout_deprecated = [bool]$NoCheckout
        exclude_path = $excludePath
    }
    Write-WorktreeRegistryEvent -RepoPath $repoRoot -Event @{
        event = 'create'
        status = 'active'
        repo_root = $repoRoot
        worktree_path = $worktreePath
        source_branch = $SourceBranch
        source_ref = $baseRef
        source_commit = $sourceCommit
        branch = $BranchName
        head = $newHead
    }
    Write-JsonResult @{
        ok = $true
        repo_root = $repoRoot
        primary_worktree_path = Get-PrimaryWorktreePath -RepoPath $repoRoot
        worktree_path = $worktreePath
        managed_worktree_root = $worktreeRoot
        source_branch = $SourceBranch
        source_ref = $baseRef
        source_commit = $sourceCommit
        source_remote_ref = $sourceRemote
        source_remote_commit = $sourceRemoteShaOut
        fetch_ran = $fetchRan
        pull_ff_only_ran = $false
        new_branch = $BranchName
        new_branch_head = $newHead
        no_checkout_deprecated = [bool]$NoCheckout
        message = '已创建隔离 worktree 临时分支；后续修改、暂存、commit、push 必须在 worktree_path 中执行。'
    }
} catch {
    Write-JsonResult @{
        ok = $false
        error = $_.Exception.Message
        native_git_fallback_forbidden = $true
        blocked_next_step = '停止当前 Git 操作，不要手动执行 git checkout -b、git switch -c、git worktree add、git add、git commit 或 git push；向用户说明脚本错误并在修正原因后重新运行本脚本。'
    }
    exit 1
}
