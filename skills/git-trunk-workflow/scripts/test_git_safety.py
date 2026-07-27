"""测试 git-trunk-workflow 的安全围栏与 worktree 隔离。

运行方式：
    cd skills/git-trunk-workflow/scripts
    python test_git_safety.py

测试分两类：
1. 纯 Python 规则测试和脚本关键片段回归；
2. 临时 Git 仓库集成测试，真实调用 PowerShell 入口脚本验证 worktree 隔离。
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
POWERSHELL = shutil.which("powershell") or shutil.which("pwsh")

# --- 从 git_common.ps1 提取的围栏规则 ---

PROTECTED_BRANCHES = {'main', 'master', 'dev', 'uat', 'prod', 'production', 'staging'}
PROTECTED_PREFIXES = ('release/', 'hotfix/')

COMMIT_PREFIXES = [
    'feat', 'fix', 'refactor', 'perf', 'style', 'config',
    'export', 'docs', 'chore', 'sql', 'hotfix', 'test', 'merge',
]
COMMIT_TITLE_PATTERN = re.compile(
    r'^\[(' + '|'.join(COMMIT_PREFIXES) + r')\]\s+.+'
)

FORBIDDEN_STAGE_PATHS = {'.', '*', ':/', '--all', '-A', '-u'}


def is_protected_branch(branch: str) -> bool:
    if branch in PROTECTED_BRANCHES:
        return True
    for prefix in PROTECTED_PREFIXES:
        if branch.startswith(prefix):
            return True
    return False


def is_valid_commit_title(title: str) -> bool:
    return COMMIT_TITLE_PATTERN.match(title) is not None


def is_forbidden_stage_path(path: str) -> bool:
    if path.strip() in FORBIDDEN_STAGE_PATHS:
        return True
    if '*' in path:
        return True
    if not path or path.isspace():
        return True
    return False


# === 基础围栏测试数据 ===

PROTECTED_CASES = [
    'main', 'master', 'dev', 'uat', 'prod', 'production', 'staging',
    'release/202606', 'release/v1.0', 'hotfix/login-fix',
]

NOT_PROTECTED_CASES = [
    'ai/dev/20260610-fix-bug',
    'feature/add-search',
    'bugfix/OTB-123',
    'experiment/test',
]

FORBIDDEN_PATHS = ['.', '*', ':/', '--all', '-A', '-u', '', '  ', 'src/*.ts', '**/*.py']

ALLOWED_PATHS = [
    'src/main.py',
    'skills/postgres-query/scripts/pg_query.py',
    'README.md',
    'manifest.json',
    'skills/git-trunk-workflow/SKILL.md',
]


class CommandError(AssertionError):
    pass


def run_cmd(cmd: list[str], cwd: Path | None = None, check: bool = True) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(
        cmd,
        cwd=str(cwd) if cwd else None,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    if check and result.returncode != 0:
        raise CommandError(
            f"command failed ({result.returncode}): {' '.join(cmd)}\n{result.stdout}"
        )
    return result


def run_git(repo: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    return run_cmd(['git', '-C', str(repo), *args], check=check)


def run_ps(script_name: str, *args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    if POWERSHELL is None:
        raise CommandError('PowerShell 不可用，无法运行 git-trunk-workflow 集成测试。')
    cmd = [
        POWERSHELL,
        '-NoProfile',
        '-ExecutionPolicy',
        'Bypass',
        '-File',
        str(SCRIPT_DIR / script_name),
        *args,
    ]
    return run_cmd(cmd, check=check)


def run_ps_json(script_name: str, *args: str, check: bool = True) -> tuple[subprocess.CompletedProcess[str], dict]:
    result = run_ps(script_name, *args, check=check)
    text = result.stdout.strip()
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise CommandError(f"PowerShell 输出不是 JSON：\n{text}") from exc
    if check and not data.get('ok'):
        raise CommandError(f"PowerShell JSON 返回失败：\n{text}")
    return result, data


def make_repo(root: Path) -> Path:
    repo = root / 'repo'
    repo.mkdir()
    run_cmd(['git', 'init'], cwd=repo)
    run_git(repo, 'config', 'user.email', 'test@example.com')
    run_git(repo, 'config', 'user.name', 'Test User')
    (repo / 'base.txt').write_text('base\n', encoding='utf-8')
    run_git(repo, 'add', 'base.txt')
    run_git(repo, 'commit', '-m', 'init')
    run_git(repo, 'branch', '-M', 'dev')
    return repo


def create_worktree(repo: Path, branch: str) -> Path:
    _, data = run_ps_json(
        'create_branch.ps1',
        '-RepositoryPath', str(repo),
        '-SourceBranch', 'dev',
        '-BranchName', branch,
    )
    if not data.get('worktree_path'):
        raise AssertionError('create_branch.ps1 未返回 worktree_path')
    worktree = Path(data['worktree_path'])
    if not worktree.exists():
        raise AssertionError(f'worktree 路径未创建：{worktree}')
    return worktree


def test_protected_branches():
    failures = []
    for branch in PROTECTED_CASES:
        if not is_protected_branch(branch):
            failures.append(f"FAIL (should be protected): {branch!r}")
    for branch in NOT_PROTECTED_CASES:
        if is_protected_branch(branch):
            failures.append(f"FAIL (should NOT be protected): {branch!r}")
    return failures


def test_stage_paths():
    failures = []
    for path in FORBIDDEN_PATHS:
        if not is_forbidden_stage_path(path):
            failures.append(f"FAIL (should be forbidden): {path!r}")
    for path in ALLOWED_PATHS:
        if is_forbidden_stage_path(path):
            failures.append(f"FAIL (should be allowed): {path!r}")
    return failures


def test_push_protection():
    """push_branch.ps1 的逻辑：保护分支必须拒绝。"""
    failures = []
    for branch in ['ai/dev/20260610-fix-bug', 'ai/uat/20260610-feat-new', 'feature/something', 'bugfix/test']:
        if is_protected_branch(branch):
            failures.append(f"FAIL (should allow push): {branch!r}")
    for branch in PROTECTED_CASES:
        if not is_protected_branch(branch):
            failures.append(f"FAIL (should block push on protected): {branch!r}")
    return failures


def test_commit_protection():
    """commit_cn.ps1 的逻辑：保护分支上不允许 commit。"""
    failures = []
    for branch in PROTECTED_CASES:
        if not is_protected_branch(branch):
            failures.append(f"FAIL (should block commit on): {branch!r}")
    for branch in ['ai/dev/20260610-fix-bug', 'feature/test']:
        if is_protected_branch(branch):
            failures.append(f"FAIL (should allow commit on): {branch!r}")
    return failures


def test_commit_title_prefix():
    """commit_cn.ps1 的逻辑：title 必须匹配 [prefix] 描述 格式。"""
    failures = []
    valid_titles = [
        '[feat] 新增导出字段',
        '[fix] 修复空指针异常',
        '[refactor] 重构查询模块',
        '[perf] 优化批量查询性能',
        '[style] 统一代码缩进',
        '[config] 新增页面配置 SQL',
        '[export] 导出模板增加列',
        '[docs] 更新 DESIGN.md',
        '[chore] 清理临时文件',
        '[sql] 新增索引',
        '[hotfix] 紧急修复线上登录失败',
        '[test] 补充单元测试',
        '[merge] 同步 dev 分支',
        '[feat] add new feature',
    ]
    invalid_titles = [
        '新增功能',
        'feat: 新增功能',
        'feat 新增功能',
        '[unknown] 未知前缀',
        '[FEAT] 大写不行',
        '[] 空前缀',
        '[feat]没有空格',
        '[feat]',
        '',
    ]
    for title in valid_titles:
        if not is_valid_commit_title(title):
            failures.append(f"FAIL (should be valid title): {title!r}")
    for title in invalid_titles:
        if is_valid_commit_title(title):
            failures.append(f"FAIL (should be invalid title): {title!r}")
    return failures


def test_create_branch_forces_worktree_and_blocks_native_fallback():
    failures = []
    content = (SCRIPT_DIR / 'create_branch.ps1').read_text(encoding='utf-8')
    required_snippets = [
        "'worktree', 'add'",
        'native_git_fallback_forbidden',
        'blocked_next_step',
        'git checkout -b',
        'git switch -c',
        'git worktree add',
        'worktree_path',
    ]
    forbidden_snippets = [
        "@('checkout', '-b'",
        "@('checkout', $SourceBranch)",
        "@('switch', '-c'",
    ]
    for snippet in required_snippets:
        if snippet not in content:
            failures.append(f"FAIL (create branch script missing snippet): {snippet!r}")
    for snippet in forbidden_snippets:
        if snippet in content:
            failures.append(f"FAIL (create branch script still uses shared checkout): {snippet!r}")
    return failures


def test_git_common_has_worktree_guards():
    failures = []
    content = (SCRIPT_DIR / 'git_common.ps1').read_text(encoding='utf-8')
    required_snippets = [
        'function Invoke-GitCapture',
        'param(',
        '[string]$RepoPath',
        "$ErrorActionPreference = 'Continue'",
        'ExitCode = $exitCode',
        'function Assert-IsManagedIsolatedWorktree',
        'function Assert-ExpectedBranch',
        'function Ensure-WorktreeRootIgnored',
        'function Write-WorktreeRegistryEvent',
        'function Assert-ActiveRegisteredWorktree',
        'return @(Get-StatusShortLines -RepoPath $RepoPath).Count -eq 0',
    ]
    for snippet in required_snippets:
        if snippet not in content:
            failures.append(f"FAIL (git_common missing worktree guard snippet): {snippet!r}")
    return failures


def test_write_scripts_require_managed_worktree():
    failures = []
    scripts = ['stage_paths.ps1', 'stage_ignored_paths.ps1', 'commit_cn.ps1', 'push_branch.ps1']
    for script in scripts:
        content = (SCRIPT_DIR / script).read_text(encoding='utf-8')
        for snippet in ['Assert-IsManagedIsolatedWorktree', 'Assert-ExpectedBranch', '[string]$RepoPath']:
            if snippet not in content:
                failures.append(f"FAIL ({script} missing worktree guard): {snippet!r}")
    return failures


def test_controlled_ignored_staging_script():
    failures = []
    script_path = SCRIPT_DIR / 'stage_ignored_paths.ps1'
    if not script_path.exists():
        return ["FAIL (missing stage_ignored_paths.ps1)"]
    content = script_path.read_text(encoding='utf-8')
    required_snippets = [
        'check-ignore',
        "add', '-f'",
        'stage_ignored',
        '受控 ignored',
    ]
    for snippet in required_snippets:
        if snippet not in content:
            failures.append(f"FAIL (stage_ignored_paths script missing snippet): {snippet!r}")
    return failures


def test_push_failure_does_not_suggest_native_push():
    failures = []
    content = (SCRIPT_DIR / 'push_branch.ps1').read_text(encoding='utf-8')
    forbidden = [
        'git -c http.proxy',
        'git -c https.proxy',
        'push -u $Remote $branch',
    ]
    required = ['native_git_fallback_forbidden', '重新运行 push_branch.ps1']
    for snippet in forbidden:
        if snippet in content:
            failures.append(f"FAIL (push script suggests native fallback): {snippet!r}")
    for snippet in required:
        if snippet not in content:
            failures.append(f"FAIL (push script missing fallback block): {snippet!r}")
    return failures


def test_wrappers_pass_worktree_parameters():
    failures = []
    checks = {
        'create_ai_branch.ps1': ['-RepositoryPath', '-SyncSource', '-NoCheckout', 'create_branch.ps1'],
        'push_ai_branch.ps1': ['-RepoPath', '-ExpectedBranch', '-Remote', 'push_branch.ps1'],
    }
    for script, snippets in checks.items():
        content = (SCRIPT_DIR / script).read_text(encoding='utf-8')
        for snippet in snippets:
            if snippet not in content:
                failures.append(f"FAIL ({script} missing wrapper passthrough): {snippet!r}")
    return failures


def test_worktree_integration():
    failures = []
    if POWERSHELL is None:
        return ['FAIL (PowerShell unavailable for integration tests)']
    with tempfile.TemporaryDirectory(prefix='git-trunk-worktree-') as tmp:
        repo = make_repo(Path(tmp))

        # 主工作区 dirty 不应阻断创建 isolated worktree。
        (repo / 'primary-dirty.txt').write_text('primary dirty\n', encoding='utf-8')
        worktree_a = create_worktree(repo, 'ai/dev/20260727-fix-a')
        current_primary = run_git(repo, 'branch', '--show-current').stdout.strip()
        if current_primary != 'dev':
            failures.append(f"FAIL (primary HEAD changed): {current_primary!r}")
        if 'primary-dirty.txt' not in run_git(repo, 'status', '--short').stdout:
            failures.append('FAIL (primary dirty state disappeared)')
        if run_git(worktree_a, 'branch', '--show-current').stdout.strip() != 'ai/dev/20260727-fix-a':
            failures.append('FAIL (worktree A branch mismatch)')

        # 第二个 worktree 可并发创建，状态互不污染。
        worktree_b = create_worktree(repo, 'ai/dev/20260727-fix-b')
        (worktree_a / 'a.txt').write_text('A\n', encoding='utf-8')
        (worktree_b / 'b.txt').write_text('B\n', encoding='utf-8')
        status_a = run_git(worktree_a, 'status', '--short').stdout
        status_b = run_git(worktree_b, 'status', '--short').stdout
        if 'a.txt' not in status_a or 'b.txt' in status_a:
            failures.append(f"FAIL (worktree A status polluted): {status_a!r}")
        if 'b.txt' not in status_b or 'a.txt' in status_b:
            failures.append(f"FAIL (worktree B status polluted): {status_b!r}")

        # 主工作区禁止 stage/commit/push。
        _, stage_primary = run_ps_json(
            'stage_paths.ps1',
            '-RepoPath', str(repo),
            '-Paths', 'primary-dirty.txt',
            check=False,
        )
        if stage_primary.get('ok') is not False or '主工作区' not in stage_primary.get('error', ''):
            failures.append(f"FAIL (primary stage was not blocked): {stage_primary}")
        _, commit_primary = run_ps_json('commit_cn.ps1', '-RepoPath', str(repo), '-Title', '[test] should block', check=False)
        if commit_primary.get('ok') is not False or '主工作区' not in commit_primary.get('error', ''):
            failures.append(f"FAIL (primary commit was not blocked): {commit_primary}")
        _, push_primary = run_ps_json('push_branch.ps1', '-RepoPath', str(repo), check=False)
        if push_primary.get('ok') is not False or '主工作区' not in push_primary.get('error', ''):
            failures.append(f"FAIL (primary push was not blocked): {push_primary}")

        # ExpectedBranch 不匹配时拒绝。
        _, mismatch = run_ps_json(
            'stage_paths.ps1',
            '-RepoPath', str(worktree_a),
            '-ExpectedBranch', 'ai/dev/other',
            '-Paths', 'a.txt',
            check=False,
        )
        if mismatch.get('ok') is not False or '期望分支' not in mismatch.get('error', ''):
            failures.append(f"FAIL (ExpectedBranch mismatch was not blocked): {mismatch}")

        # A/B 各自暂存提交，commit 落在各自分支。
        run_ps_json(
            'stage_paths.ps1',
            '-RepoPath', str(worktree_a),
            '-ExpectedBranch', 'ai/dev/20260727-fix-a',
            '-Paths', 'a.txt',
        )
        _, commit_a = run_ps_json(
            'commit_cn.ps1',
            '-RepoPath', str(worktree_a),
            '-ExpectedBranch', 'ai/dev/20260727-fix-a',
            '-Title', '[test] commit a',
        )
        run_ps_json(
            'stage_paths.ps1',
            '-RepoPath', str(worktree_b),
            '-ExpectedBranch', 'ai/dev/20260727-fix-b',
            '-Paths', 'b.txt',
        )
        _, commit_b = run_ps_json(
            'commit_cn.ps1',
            '-RepoPath', str(worktree_b),
            '-ExpectedBranch', 'ai/dev/20260727-fix-b',
            '-Title', '[test] commit b',
        )
        files_a = run_git(worktree_a, 'show', '--name-only', '--pretty=format:', commit_a['commit']).stdout
        files_b = run_git(worktree_b, 'show', '--name-only', '--pretty=format:', commit_b['commit']).stdout
        if 'a.txt' not in files_a or 'b.txt' in files_a:
            failures.append(f"FAIL (commit A includes wrong files): {files_a!r}")
        if 'b.txt' not in files_b or 'a.txt' in files_b:
            failures.append(f"FAIL (commit B includes wrong files): {files_b!r}")

        # dirty / ignored worktree 禁止删除，clean worktree 可删除。
        worktree_c = create_worktree(repo, 'ai/dev/20260727-fix-c')
        (worktree_c / 'dirty.txt').write_text('dirty\n', encoding='utf-8')
        _, remove_dirty = run_ps_json(
            'remove_worktree.ps1',
            '-WorktreePath', str(worktree_c),
            '-ExpectedBranch', 'ai/dev/20260727-fix-c',
            check=False,
        )
        if remove_dirty.get('ok') is not False or '不干净' not in remove_dirty.get('error', ''):
            failures.append(f"FAIL (dirty worktree remove was not blocked): {remove_dirty}")
        os.remove(worktree_c / 'dirty.txt')
        (worktree_c / '.gitignore').write_text('build/\n', encoding='utf-8')
        run_ps_json(
            'stage_paths.ps1',
            '-RepoPath', str(worktree_c),
            '-ExpectedBranch', 'ai/dev/20260727-fix-c',
            '-Paths', '.gitignore',
        )
        run_ps_json(
            'commit_cn.ps1',
            '-RepoPath', str(worktree_c),
            '-ExpectedBranch', 'ai/dev/20260727-fix-c',
            '-Title', '[test] add ignore rule',
        )
        (worktree_c / 'build').mkdir()
        (worktree_c / 'build' / 'ignored.tmp').write_text('ignored\n', encoding='utf-8')
        _, remove_ignored = run_ps_json(
            'remove_worktree.ps1',
            '-WorktreePath', str(worktree_c),
            '-ExpectedBranch', 'ai/dev/20260727-fix-c',
            check=False,
        )
        if remove_ignored.get('ok') is not False or 'ignored' not in remove_ignored.get('error', ''):
            failures.append(f"FAIL (ignored worktree remove was not blocked): {remove_ignored}")
        os.remove(worktree_c / 'build' / 'ignored.tmp')
        (worktree_c / 'build').rmdir()
        _, remove_clean = run_ps_json(
            'remove_worktree.ps1',
            '-WorktreePath', str(worktree_c),
            '-ExpectedBranch', 'ai/dev/20260727-fix-c',
            '-Prune',
        )
        if not remove_clean.get('ok') or worktree_c.exists():
            failures.append(f"FAIL (clean worktree remove failed): {remove_clean}")

        # list_worktrees 至少能识别受控 worktree。
        _, listing = run_ps_json('list_worktrees.ps1', '-RepositoryPath', str(repo))
        managed = [item for item in listing.get('worktrees', []) if item.get('managed')]
        if len(managed) < 2:
            failures.append(f"FAIL (list_worktrees did not report managed worktrees): {listing}")

        # 手动绕过脚本创建的 .wt worktree 没有 registry active 记录，后续写操作必须拒绝。
        manual_worktree = repo / '.wt' / 'manual-bypass'
        run_git(repo, 'worktree', 'add', '-b', 'ai/dev/manual-bypass', str(manual_worktree), 'dev')
        (manual_worktree / 'manual.txt').write_text('manual\n', encoding='utf-8')
        _, manual_stage = run_ps_json(
            'stage_paths.ps1',
            '-RepoPath', str(manual_worktree),
            '-ExpectedBranch', 'ai/dev/manual-bypass',
            '-Paths', 'manual.txt',
            check=False,
        )
        if manual_stage.get('ok') is not False or 'registry active' not in manual_stage.get('error', ''):
            failures.append(f"FAIL (manual worktree bypass was not blocked): {manual_stage}")
        os.remove(manual_worktree / 'manual.txt')
        run_git(repo, 'worktree', 'remove', str(manual_worktree))

    return failures


def main():
    all_failures = []
    tests = [
        ("protected_branches", test_protected_branches),
        ("stage_paths", test_stage_paths),
        ("push_protection", test_push_protection),
        ("commit_protection", test_commit_protection),
        ("commit_title_prefix", test_commit_title_prefix),
        ("create_branch_forces_worktree_and_blocks_native_fallback", test_create_branch_forces_worktree_and_blocks_native_fallback),
        ("git_common_has_worktree_guards", test_git_common_has_worktree_guards),
        ("write_scripts_require_managed_worktree", test_write_scripts_require_managed_worktree),
        ("controlled_ignored_staging_script", test_controlled_ignored_staging_script),
        ("push_failure_does_not_suggest_native_push", test_push_failure_does_not_suggest_native_push),
        ("wrappers_pass_worktree_parameters", test_wrappers_pass_worktree_parameters),
        ("worktree_integration", test_worktree_integration),
    ]

    for name, test_fn in tests:
        failures = test_fn()
        if failures:
            print(f"\n{'='*60}")
            print(f"FAILED: {name}")
            print(f"{'='*60}")
            for f in failures:
                print(f"  {f}")
            all_failures.extend(failures)
        else:
            print(f"  PASSED: {name}")

    print(f"\n{'='*60}")
    if all_failures:
        print(f"TOTAL FAILURES: {len(all_failures)}")
        raise SystemExit(1)
    else:
        print("ALL TESTS PASSED")
        raise SystemExit(0)


if __name__ == "__main__":
    main()
