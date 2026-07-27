param(
    [string]$Remote = 'origin',
    [string]$RepoPath = '',
    [string]$ExpectedBranch = ''
)

# 向后兼容包装：直接调用通用版 push_branch.ps1；通用版已强制从隔离 worktree push。
$extraArgs = @('-Remote', $Remote)
if (-not [string]::IsNullOrWhiteSpace($RepoPath)) { $extraArgs += @('-RepoPath', $RepoPath) }
if (-not [string]::IsNullOrWhiteSpace($ExpectedBranch)) { $extraArgs += @('-ExpectedBranch', $ExpectedBranch) }
& "$PSScriptRoot\push_branch.ps1" @extraArgs
exit $LASTEXITCODE
