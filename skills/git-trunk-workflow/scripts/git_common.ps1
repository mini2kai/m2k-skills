Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

# --- 围栏常量 ---
$script:AUDIT_RETENTION_DAYS = 7
$script:MANAGED_WORKTREE_DIR = '.wt'
$script:REGISTRY_DIR_NAME = 'git-trunk-workflow'
$script:REGISTRY_FILE_NAME = 'worktrees.jsonl'

function Write-JsonResult {
    param([Parameter(Mandatory = $true)][hashtable]$Data)
    $Data | ConvertTo-Json -Depth 12
}

function Normalize-FullPath {
    param([Parameter(Mandatory = $true)][string]$Path)
    $full = [System.IO.Path]::GetFullPath($Path)
    $root = [System.IO.Path]::GetPathRoot($full)
    if ($full.Length -gt $root.Length) {
        $full = $full.TrimEnd([char[]]@([System.IO.Path]::DirectorySeparatorChar, [System.IO.Path]::AltDirectorySeparatorChar))
    }
    return $full
}

function Get-PathComparisonValue {
    param([Parameter(Mandatory = $true)][string]$Path)
    return (Normalize-FullPath -Path $Path).Replace([System.IO.Path]::AltDirectorySeparatorChar, [System.IO.Path]::DirectorySeparatorChar).ToLowerInvariant()
}

function Test-SamePath {
    param([Parameter(Mandatory = $true)][string]$Left, [Parameter(Mandatory = $true)][string]$Right)
    return (Get-PathComparisonValue -Path $Left) -eq (Get-PathComparisonValue -Path $Right)
}

function Test-PathInside {
    param([Parameter(Mandatory = $true)][string]$Child, [Parameter(Mandatory = $true)][string]$Parent)
    $childValue = Get-PathComparisonValue -Path $Child
    $parentValue = Get-PathComparisonValue -Path $Parent
    if ($childValue -eq $parentValue) { return $true }
    $separator = [System.IO.Path]::DirectorySeparatorChar
    return $childValue.StartsWith($parentValue + $separator)
}

function Get-GitAuditLogDir {
    Join-Path (Resolve-Path (Join-Path $PSScriptRoot '..')).Path 'logs'
}

function Write-GitAuditLog {
    param([Parameter(Mandatory = $true)][hashtable]$Event)
    $logDir = Get-GitAuditLogDir
    if (-not (Test-Path -LiteralPath $logDir)) {
        New-Item -ItemType Directory -Path $logDir -Force | Out-Null
    }
    # 清理过期日志
    Get-ChildItem -LiteralPath $logDir -Filter 'git-ops-*.jsonl' -File -ErrorAction SilentlyContinue |
        Where-Object { $_.LastWriteTime -lt (Get-Date).AddDays(-$script:AUDIT_RETENTION_DAYS) } |
        Remove-Item -Force
    $date = Get-Date
    $payload = [ordered]@{
        time = $date.ToString('yyyy-MM-ddTHH:mm:ss.fffzzz')
        skill = 'git-trunk-workflow'
    }
    foreach ($key in $Event.Keys) { $payload[$key] = $Event[$key] }
    $line = $payload | ConvertTo-Json -Compress -Depth 12
    $path = Join-Path $logDir ("git-ops-{0}.jsonl" -f $date.ToString('yyyy-MM-dd'))
    Add-Content -LiteralPath $path -Value $line -Encoding UTF8
}

function Invoke-GitCapture {
    param(
        [Parameter(Mandatory = $true)][string[]]$Args,
        [string]$RepoPath = ''
    )
    $previousErrorActionPreference = $ErrorActionPreference
    $ErrorActionPreference = 'Continue'
    try {
        if ([string]::IsNullOrWhiteSpace($RepoPath)) {
            $output = & git @Args 2>&1
        } else {
            $output = & git -C $RepoPath @Args 2>&1
        }
        $exitCode = $LASTEXITCODE
    }
    finally {
        $ErrorActionPreference = $previousErrorActionPreference
    }
    return @{
        ExitCode = $exitCode
        Lines = @($output | ForEach-Object { $_.ToString() })
    }
}

function Invoke-GitLines {
    param(
        [Parameter(Mandatory = $true)][string[]]$Args,
        [string]$RepoPath = ''
    )
    $result = Invoke-GitCapture -Args $Args -RepoPath $RepoPath
    if ($result.ExitCode -ne 0) {
        $prefix = if ([string]::IsNullOrWhiteSpace($RepoPath)) { 'git' } else { "git -C $RepoPath" }
        throw "$prefix $($Args -join ' ') failed: $($result.Lines -join [Environment]::NewLine)"
    }
    return @($result.Lines)
}

function Invoke-GitText {
    param(
        [Parameter(Mandatory = $true)][string[]]$Args,
        [string]$RepoPath = ''
    )
    return (Invoke-GitLines -Args $Args -RepoPath $RepoPath) -join [Environment]::NewLine
}

function Resolve-RepoPath {
    param([string]$Path = '')
    $target = $Path
    if ([string]::IsNullOrWhiteSpace($target)) { $target = (Get-Location).Path }
    if (-not (Test-Path -LiteralPath $target)) { throw "路径不存在：$target" }
    $resolved = (Resolve-Path -LiteralPath $target).Path
    $top = Invoke-GitCapture -RepoPath $resolved -Args @('rev-parse', '--show-toplevel')
    if ($top.ExitCode -eq 0) { return ($top.Lines -join '').Trim() }
    return $resolved
}

function Assert-GitRepository {
    param([string]$RepoPath = '')
    $repo = Resolve-RepoPath -Path $RepoPath
    $inside = Invoke-GitCapture -RepoPath $repo -Args @('rev-parse', '--is-inside-work-tree')
    if ($inside.ExitCode -ne 0 -or (($inside.Lines -join '').Trim() -ne 'true')) {
        throw "路径不是 Git 工作区：$repo"
    }
    return $repo
}

function Resolve-GitInternalPath {
    param([Parameter(Mandatory = $true)][string]$RepoPath, [Parameter(Mandatory = $true)][string]$GitPath)
    if ([System.IO.Path]::IsPathRooted($GitPath)) { return (Normalize-FullPath -Path $GitPath) }
    return (Normalize-FullPath -Path (Join-Path (Resolve-RepoPath -Path $RepoPath) $GitPath))
}

function Get-RepoRoot {
    param([string]$RepoPath = '')
    return (Invoke-GitText -RepoPath $RepoPath -Args @('rev-parse', '--show-toplevel')).Trim()
}

function Get-GitDir {
    param([string]$RepoPath = '')
    $repo = Resolve-RepoPath -Path $RepoPath
    $gitDir = (Invoke-GitText -RepoPath $repo -Args @('rev-parse', '--git-dir')).Trim()
    return Resolve-GitInternalPath -RepoPath $repo -GitPath $gitDir
}

function Get-GitCommonDir {
    param([string]$RepoPath = '')
    $repo = Resolve-RepoPath -Path $RepoPath
    $commonDir = (Invoke-GitText -RepoPath $repo -Args @('rev-parse', '--git-common-dir')).Trim()
    return Resolve-GitInternalPath -RepoPath $repo -GitPath $commonDir
}

function New-WorktreeRecord {
    return [pscustomobject][ordered]@{
        worktree = ''
        head = ''
        branch = ''
        branch_ref = ''
        bare = $false
        detached = $false
        locked = $false
        prunable = $false
        reason = ''
    }
}

function Get-GitWorktreeRecords {
    param([string]$RepoPath = '')
    $repo = Assert-GitRepository -RepoPath $RepoPath
    $lines = Invoke-GitLines -RepoPath $repo -Args @('worktree', 'list', '--porcelain')
    $records = @()
    $record = New-WorktreeRecord
    foreach ($line in $lines) {
        if ([string]::IsNullOrWhiteSpace($line)) {
            if (-not [string]::IsNullOrWhiteSpace($record.worktree)) { $records += $record }
            $record = New-WorktreeRecord
            continue
        }
        if ($line.StartsWith('worktree ')) {
            $record.worktree = $line.Substring(9)
        } elseif ($line.StartsWith('HEAD ')) {
            $record.head = $line.Substring(5)
        } elseif ($line.StartsWith('branch ')) {
            $record.branch_ref = $line.Substring(7)
            if ($record.branch_ref.StartsWith('refs/heads/')) {
                $record.branch = $record.branch_ref.Substring(11)
            } else {
                $record.branch = $record.branch_ref
            }
        } elseif ($line -eq 'bare') {
            $record.bare = $true
        } elseif ($line -eq 'detached') {
            $record.detached = $true
        } elseif ($line -eq 'locked') {
            $record.locked = $true
        } elseif ($line.StartsWith('locked ')) {
            $record.locked = $true
            $record.reason = $line.Substring(7)
        } elseif ($line -eq 'prunable') {
            $record.prunable = $true
        } elseif ($line.StartsWith('prunable ')) {
            $record.prunable = $true
            $record.reason = $line.Substring(9)
        }
    }
    if (-not [string]::IsNullOrWhiteSpace($record.worktree)) { $records += $record }
    return @($records)
}

function Get-PrimaryWorktreePath {
    param([string]$RepoPath = '')
    $records = @(Get-GitWorktreeRecords -RepoPath $RepoPath)
    if ($records.Count -eq 0) { throw '未能读取 git worktree 列表。' }
    return Normalize-FullPath -Path $records[0].worktree
}

function Get-ManagedWorktreeRoot {
    param([string]$RepoPath = '')
    $primary = Get-PrimaryWorktreePath -RepoPath $RepoPath
    return Normalize-FullPath -Path (Join-Path $primary $script:MANAGED_WORKTREE_DIR)
}

function Get-WorktreeInfo {
    param([string]$RepoPath = '')
    $repo = Assert-GitRepository -RepoPath $RepoPath
    $repoRoot = Normalize-FullPath -Path (Get-RepoRoot -RepoPath $repo)
    $primary = Get-PrimaryWorktreePath -RepoPath $repo
    $commonDir = Get-GitCommonDir -RepoPath $repo
    $managedRoot = Get-ManagedWorktreeRoot -RepoPath $repo
    $isPrimary = Test-SamePath -Left $repoRoot -Right $primary
    $isManaged = ((-not $isPrimary) -and (Test-PathInside -Child $repoRoot -Parent $managedRoot))
    $branch = ''
    $head = ''
    try { $branch = Get-CurrentBranch -RepoPath $repoRoot } catch { $branch = '' }
    try { $head = Get-FullSha -RepoPath $repoRoot } catch { $head = '' }
    return [pscustomobject][ordered]@{
        repo_root = $repoRoot
        worktree_path = if ($isPrimary) { '' } else { $repoRoot }
        current_worktree_path = $repoRoot
        primary_worktree_path = $primary
        git_common_dir = $commonDir
        managed_worktree_root = $managedRoot
        is_primary_worktree = $isPrimary
        is_managed_worktree = $isManaged
        is_isolated_worktree = $isManaged
        current_branch = $branch
        head = $head
    }
}

function Test-IsManagedWorktree {
    param([string]$RepoPath = '')
    $info = Get-WorktreeInfo -RepoPath $RepoPath
    return [bool]$info.is_managed_worktree
}

function Assert-IsManagedIsolatedWorktree {
    param([string]$RepoPath = '', [switch]$SkipRegistryCheck)
    $info = Get-WorktreeInfo -RepoPath $RepoPath
    if ($info.is_primary_worktree) {
        throw "当前路径是主工作区：$($info.current_worktree_path)。AI Git 写操作必须在 create_branch.ps1 返回的 .wt 隔离 worktree 中执行。"
    }
    if (-not $info.is_managed_worktree) {
        throw "当前 worktree 不在受控目录 $($info.managed_worktree_root) 下，拒绝执行 Git 写操作。"
    }
    if (-not $SkipRegistryCheck) { Assert-ActiveRegisteredWorktree -WorktreeInfo $info }
    return $info
}

function ConvertTo-SafeWorktreeName {
    param([Parameter(Mandatory = $true)][string]$Branch)
    $name = $Branch.Trim()
    $name = $name -replace '[\\/:\*\?"<>\|\s]+', '-'
    $name = $name -replace '[^\p{L}\p{Nd}._-]+', '-'
    $name = $name -replace '-{2,}', '-'
    $name = $name.Trim([char[]]@('.', '-'))
    if ([string]::IsNullOrWhiteSpace($name)) { $name = 'worktree' }
    if ($name.Length -gt 80) {
        $md5 = [System.Security.Cryptography.MD5]::Create()
        try {
            $bytes = [System.Text.Encoding]::UTF8.GetBytes($Branch)
            $hashBytes = $md5.ComputeHash($bytes)
            $hash = ([System.BitConverter]::ToString($hashBytes) -replace '-', '').ToLowerInvariant().Substring(0, 12)
        } finally {
            $md5.Dispose()
        }
        $prefix = $name.Substring(0, 60).Trim([char[]]@('.', '-'))
        $name = "$prefix-$hash"
    }
    return $name
}

function Ensure-WorktreeRootIgnored {
    param([string]$RepoPath = '')
    $repo = Assert-GitRepository -RepoPath $RepoPath
    $commonDir = Get-GitCommonDir -RepoPath $repo
    $infoDir = Join-Path $commonDir 'info'
    if (-not (Test-Path -LiteralPath $infoDir)) { New-Item -ItemType Directory -Path $infoDir -Force | Out-Null }
    $excludePath = Join-Path $infoDir 'exclude'
    if (-not (Test-Path -LiteralPath $excludePath)) { New-Item -ItemType File -Path $excludePath -Force | Out-Null }
    $lines = @(Get-Content -LiteralPath $excludePath -ErrorAction SilentlyContinue)
    $hasRule = $false
    foreach ($line in $lines) {
        $trimmed = $line.Trim()
        if ($trimmed -eq '.wt/' -or $trimmed -eq '/.wt/' -or $trimmed -eq '.wt') { $hasRule = $true; break }
    }
    if (-not $hasRule) { Add-Content -LiteralPath $excludePath -Value '.wt/' -Encoding UTF8 }
    return $excludePath
}

function Get-WorktreeRegistryDir {
    param([string]$RepoPath = '')
    $commonDir = Get-GitCommonDir -RepoPath $RepoPath
    return Join-Path $commonDir $script:REGISTRY_DIR_NAME
}

function Get-WorktreeRegistryPath {
    param([string]$RepoPath = '')
    return Join-Path (Get-WorktreeRegistryDir -RepoPath $RepoPath) $script:REGISTRY_FILE_NAME
}

function Write-WorktreeRegistryEvent {
    param([string]$RepoPath = '', [Parameter(Mandatory = $true)][hashtable]$Event)
    $dir = Get-WorktreeRegistryDir -RepoPath $RepoPath
    if (-not (Test-Path -LiteralPath $dir)) { New-Item -ItemType Directory -Path $dir -Force | Out-Null }
    $date = Get-Date
    $payload = [ordered]@{
        time = $date.ToString('yyyy-MM-ddTHH:mm:ss.fffzzz')
        skill = 'git-trunk-workflow'
    }
    foreach ($key in $Event.Keys) { $payload[$key] = $Event[$key] }
    $line = $payload | ConvertTo-Json -Compress -Depth 12
    Add-Content -LiteralPath (Get-WorktreeRegistryPath -RepoPath $RepoPath) -Value $line -Encoding UTF8
}

function Read-WorktreeRegistry {
    param([string]$RepoPath = '')
    $path = Get-WorktreeRegistryPath -RepoPath $RepoPath
    if (-not (Test-Path -LiteralPath $path)) { return @() }
    $items = @()
    foreach ($line in @(Get-Content -LiteralPath $path -ErrorAction SilentlyContinue)) {
        if ([string]::IsNullOrWhiteSpace($line)) { continue }
        try { $items += ($line | ConvertFrom-Json) } catch { }
    }
    return @($items)
}

function Get-LatestWorktreeRegistryEvent {
    param([string]$RepoPath = '', [Parameter(Mandatory = $true)][string]$WorktreePath)
    $latest = $null
    foreach ($event in Read-WorktreeRegistry -RepoPath $RepoPath) {
        $pathProp = $event.PSObject.Properties['worktree_path']
        if ($null -eq $pathProp -or [string]::IsNullOrWhiteSpace([string]$pathProp.Value)) { continue }
        if (Test-SamePath -Left ([string]$pathProp.Value) -Right $WorktreePath) { $latest = $event }
    }
    return $latest
}

function Assert-ActiveRegisteredWorktree {
    param([Parameter(Mandatory = $true)]$WorktreeInfo)
    $latest = Get-LatestWorktreeRegistryEvent -RepoPath $WorktreeInfo.current_worktree_path -WorktreePath $WorktreeInfo.current_worktree_path
    if ($null -eq $latest) {
        throw "当前 worktree 缺少 git-trunk-workflow registry active 记录，拒绝执行 Git 写操作。请通过 create_branch.ps1 创建隔离 worktree，不要手动 git worktree add。"
    }
    $eventProp = $latest.PSObject.Properties['event']
    $statusProp = $latest.PSObject.Properties['status']
    $branchProp = $latest.PSObject.Properties['branch']
    $eventName = if ($null -ne $eventProp) { [string]$eventProp.Value } else { '' }
    $status = if ($null -ne $statusProp) { [string]$statusProp.Value } else { '' }
    $branch = if ($null -ne $branchProp) { [string]$branchProp.Value } else { '' }
    if ($eventName -eq 'remove' -or $status -eq 'removed') {
        throw "当前 worktree 的 registry 状态为 removed，拒绝执行 Git 写操作：$($WorktreeInfo.current_worktree_path)"
    }
    if (-not [string]::IsNullOrWhiteSpace($branch) -and $branch -ne $WorktreeInfo.current_branch) {
        throw "当前 worktree registry 分支是 $branch，但实际当前分支是 $($WorktreeInfo.current_branch)，拒绝继续。"
    }
}

function Assert-NotProtectedBranch {
    param([Parameter(Mandatory = $true)][string]$Branch, [string]$Action = 'operation')
    if (Test-ProtectedBranch -Branch $Branch) {
        throw "当前分支 $Branch 是保护分支，拒绝 $Action。"
    }
}

function Get-CurrentBranch {
    param([string]$RepoPath = '')
    return (Invoke-GitText -RepoPath $RepoPath -Args @('branch', '--show-current')).Trim()
}

function Assert-ExpectedBranch {
    param([string]$RepoPath = '', [string]$ExpectedBranch = '')
    if ([string]::IsNullOrWhiteSpace($ExpectedBranch)) { return }
    $current = Get-CurrentBranch -RepoPath $RepoPath
    if ($current -ne $ExpectedBranch) {
        throw "当前分支是 $current，不是期望分支 $ExpectedBranch，拒绝继续。"
    }
}

function Get-HeadSha {
    param([string]$Ref = 'HEAD', [string]$RepoPath = '')
    return (Invoke-GitText -RepoPath $RepoPath -Args @('rev-parse', '--short=12', $Ref)).Trim()
}

function Get-FullSha {
    param([string]$Ref = 'HEAD', [string]$RepoPath = '')
    return (Invoke-GitText -RepoPath $RepoPath -Args @('rev-parse', $Ref)).Trim()
}

function Get-Upstream {
    param([string]$RepoPath = '')
    $result = Invoke-GitCapture -RepoPath $RepoPath -Args @('rev-parse', '--abbrev-ref', '--symbolic-full-name', '@{u}')
    if ($result.ExitCode -ne 0) { return '' }
    return ($result.Lines -join '').Trim()
}

function Get-StatusShortLines {
    param([string]$RepoPath = '')
    return @(Invoke-GitLines -RepoPath $RepoPath -Args @('status', '--short'))
}

function Test-WorktreeClean {
    param([string]$RepoPath = '')
    return @(Get-StatusShortLines -RepoPath $RepoPath).Count -eq 0
}

$script:COMMIT_PREFIXES = @(
    'feat', 'fix', 'refactor', 'perf', 'style', 'config',
    'export', 'docs', 'chore', 'sql', 'hotfix', 'test', 'merge'
)

function Assert-CommitTitlePrefix {
    param([Parameter(Mandatory = $true)][string]$Title)
    $pattern = '^\[(' + ($script:COMMIT_PREFIXES -join '|') + ')\]\s+.+'
    if ($Title -notmatch $pattern) {
        $allowed = $script:COMMIT_PREFIXES | ForEach-Object { "[$_]" }
        throw "commit title 格式错误：必须以允许的前缀开头，例如 [feat] 新增功能。`n允许的前缀：$($allowed -join '、')`n收到：$Title"
    }
}

function Test-ProtectedBranch {
    param([Parameter(Mandatory = $true)][string]$Branch)
    return ($Branch -in @('main', 'master', 'dev', 'uat', 'prod', 'production', 'staging')) -or $Branch.StartsWith('release/') -or $Branch.StartsWith('hotfix/')
}

function Get-LongLivedBranchWarning {
    param([Parameter(Mandatory = $true)][string]$Branch)
    if (Test-ProtectedBranch -Branch $Branch) {
        return "当前分支 $Branch 是长期分支，禁止默认 push、merge 或直接提交交付。"
    }
    return ''
}

function Get-AheadBehind {
    param([string]$RepoPath = '')
    $upstream = Get-Upstream -RepoPath $RepoPath
    if ([string]::IsNullOrWhiteSpace($upstream)) {
        return @{ upstream = ''; ahead = $null; behind = $null }
    }
    $counts = (Invoke-GitText -RepoPath $RepoPath -Args @('rev-list', '--left-right', '--count', 'HEAD...@{u}')).Trim() -split '\s+'
    return @{ upstream = $upstream; ahead = [int]$counts[0]; behind = [int]$counts[1] }
}

function Split-Status {
    param([string]$RepoPath = '')
    $staged = New-Object System.Collections.Generic.List[string]
    $unstaged = New-Object System.Collections.Generic.List[string]
    $untracked = New-Object System.Collections.Generic.List[string]
    foreach ($line in Get-StatusShortLines -RepoPath $RepoPath) {
        if ($line.StartsWith('??')) {
            $untracked.Add($line.Substring(3))
            continue
        }
        if ($line.Length -ge 3) {
            if ($line[0] -ne ' ') { $staged.Add($line.Substring(3)) }
            if ($line[1] -ne ' ') { $unstaged.Add($line.Substring(3)) }
        }
    }
    return @{ staged = @($staged); unstaged = @($unstaged); untracked = @($untracked) }
}

function Assert-NoGitOperationInProgress {
    param([string]$RepoPath = '')
    $gitDir = Get-GitDir -RepoPath $RepoPath
    $markers = @('MERGE_HEAD', 'REBASE_HEAD', 'CHERRY_PICK_HEAD', 'BISECT_LOG')
    foreach ($marker in $markers) {
        if (Test-Path (Join-Path $gitDir $marker)) {
            throw "检测到 Git 中间状态 $marker，先处理完成后再执行此脚本。"
        }
    }
    if (Test-Path (Join-Path $gitDir 'rebase-merge')) { throw '检测到 rebase-merge 中间状态。' }
    if (Test-Path (Join-Path $gitDir 'rebase-apply')) { throw '检测到 rebase-apply 中间状态。' }
}

function Get-RemoteRefSha {
    param([Parameter(Mandatory = $true)][string]$RemoteRef, [string]$RepoPath = '')
    $result = Invoke-GitCapture -RepoPath $RepoPath -Args @('rev-parse', '--verify', '--quiet', $RemoteRef)
    if ($result.ExitCode -ne 0) { return '' }
    return ($result.Lines -join '').Trim()
}

function Test-GitRefExists {
    param([Parameter(Mandatory = $true)][string]$Ref, [string]$RepoPath = '')
    $result = Invoke-GitCapture -RepoPath $RepoPath -Args @('rev-parse', '--verify', '--quiet', $Ref)
    return $result.ExitCode -eq 0
}

function Test-GitAncestor {
    param([Parameter(Mandatory = $true)][string]$Ancestor, [Parameter(Mandatory = $true)][string]$Descendant, [string]$RepoPath = '')
    $result = Invoke-GitCapture -RepoPath $RepoPath -Args @('merge-base', '--is-ancestor', $Ancestor, $Descendant)
    return $result.ExitCode -eq 0
}
