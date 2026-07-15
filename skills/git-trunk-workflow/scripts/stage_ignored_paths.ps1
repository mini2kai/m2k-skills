param(
    [Parameter(Mandatory = $true)][string[]]$Paths
)

. "$PSScriptRoot\git_common.ps1"

try {
    Assert-NoGitOperationInProgress
    $repoRoot = Get-RepoRoot
    $current = Get-CurrentBranch
    $forbidden = @('.', '*', ':/', '--all', '-A', '-u')
    foreach ($path in $Paths) {
        if ([string]::IsNullOrWhiteSpace($path)) { throw '路径不能为空。' }
        if ($forbidden -contains $path.Trim()) { throw "拒绝全量或模糊暂存表达：$path。请显式传文件路径。" }
        if ($path.Contains('*')) { throw "拒绝通配符路径：$path。请显式传文件路径。" }
    }

    $ignored = @()
    foreach ($path in $Paths) {
        $normalized = $path.Trim().Replace('\', '/')
        $check = Invoke-GitCapture -Args @('check-ignore', '--quiet', '--', $normalized)
        if ($check.ExitCode -ne 0) {
            throw "以下路径未被 .gitignore 忽略，不能走受控 ignored 暂存：$path"
        }
        $ignored += $normalized
    }

    Invoke-GitLines -Args (@('add', '-f', '--') + $ignored) | Out-Null
    $status = Split-Status
    Write-GitAuditLog -Event @{
        event = 'stage_ignored'
        branch = $current
        paths = $ignored
    }
    Write-JsonResult @{
        ok = $true
        repo_root = $repoRoot
        current_branch = $current
        staged_paths_requested = $ignored
        staged_now = $status.staged
        unstaged_now = $status.unstaged
        untracked_now = $status.untracked
        message = '已按受控 ignored 路径暂存。'
    }
} catch {
    Write-JsonResult @{ ok = $false; error = $_.Exception.Message }
    exit 1
}
