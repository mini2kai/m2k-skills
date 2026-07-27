param(
    [string]$RepositoryPath = ''
)

. "$PSScriptRoot\git_common.ps1"

try {
    $repo = Assert-GitRepository -RepoPath $RepositoryPath
    $primary = Get-PrimaryWorktreePath -RepoPath $repo
    $managedRoot = Get-ManagedWorktreeRoot -RepoPath $repo
    $registry = Read-WorktreeRegistry -RepoPath $repo
    $items = @()
    foreach ($record in Get-GitWorktreeRecords -RepoPath $repo) {
        $path = Normalize-FullPath -Path $record.worktree
        $isPrimary = Test-SamePath -Left $path -Right $primary
        $managed = ((-not $isPrimary) -and (Test-PathInside -Child $path -Parent $managedRoot))
        $clean = $null
        if ((Test-Path -LiteralPath $path) -and (-not $record.bare)) {
            try { $clean = Test-WorktreeClean -RepoPath $path } catch { $clean = $null }
        }
        $registryEvents = @($registry | Where-Object {
            $pathProp = $_.PSObject.Properties['worktree_path']
            $null -ne $pathProp -and (-not [string]::IsNullOrWhiteSpace([string]$pathProp.Value)) -and (Test-SamePath -Left ([string]$pathProp.Value) -Right $path)
        })
        $items += [ordered]@{
            path = $path
            branch = $record.branch
            branch_ref = $record.branch_ref
            head = $record.head
            is_primary = $isPrimary
            managed = $managed
            clean = $clean
            locked = $record.locked
            prunable = $record.prunable
            reason = $record.reason
            registry_events = $registryEvents
        }
    }

    Write-JsonResult @{
        ok = $true
        repo_root = Get-RepoRoot -RepoPath $repo
        primary_worktree_path = $primary
        managed_worktree_root = $managedRoot
        registry_path = Get-WorktreeRegistryPath -RepoPath $repo
        worktrees = $items
    }
} catch {
    Write-JsonResult @{ ok = $false; error = $_.Exception.Message }
    exit 1
}
