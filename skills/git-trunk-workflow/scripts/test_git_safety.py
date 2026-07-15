"""测试 git_common.ps1 中的安全检查逻辑。

运行方式：
    cd skills/git-trunk-workflow/scripts
    python test_git_safety.py

通过 Python 重新实现 PowerShell 中的校验逻辑来验证设计意图。
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

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


# === 保护分支测试 ===

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

# === 暂存路径测试 ===

FORBIDDEN_PATHS = ['.', '*', ':/', '--all', '-A', '-u', '', '  ', 'src/*.ts', '**/*.py']

ALLOWED_PATHS = [
    'src/main.py',
    'skills/postgres-query/scripts/pg_query.py',
    'README.md',
    'manifest.json',
    'skills/git-trunk-workflow/SKILL.md',
]


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
    """push_branch.ps1 的逻辑：只要不是保护分支即可 push。"""
    failures = []
    # 应该允许 push（非保护分支，无论是否 ai/* 前缀）
    for branch in ['ai/dev/20260610-fix-bug', 'ai/uat/20260610-feat-new', 'feature/something', 'bugfix/test']:
        if is_protected_branch(branch):
            failures.append(f"FAIL (should allow push): {branch!r}")
    # 应该拒绝 push（保护分支）
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


def test_create_branch_failure_blocks_native_fallback():
    """create_branch.ps1 失败时必须明确禁止原生 Git 兜底。"""
    failures = []
    script_path = Path(__file__).resolve().with_name('create_branch.ps1')
    content = script_path.read_text(encoding='utf-8')
    required_snippets = [
        'native_git_fallback_forbidden',
        'blocked_next_step',
        'git checkout -b',
        'git switch -c',
    ]
    for snippet in required_snippets:
        if snippet not in content:
            failures.append(f"FAIL (create branch script missing fallback block): {snippet!r}")
    return failures


def test_git_common_uses_strict_safe_capture():
    """git_common.ps1 必须处理 clean 仓库空输出和 native stderr。"""
    failures = []
    script_path = Path(__file__).resolve().with_name('git_common.ps1')
    content = script_path.read_text(encoding='utf-8')
    required_snippets = [
        'function Invoke-GitCapture',
        "$ErrorActionPreference = 'Continue'",
        'ExitCode = $exitCode',
        'return @(Get-StatusShortLines).Count -eq 0',
    ]
    for snippet in required_snippets:
        if snippet not in content:
            failures.append(f"FAIL (git_common missing strict-safe capture): {snippet!r}")
    return failures


def test_controlled_ignored_staging_script():
    failures = []
    script_path = Path(__file__).resolve().with_name('stage_ignored_paths.ps1')
    if not script_path.exists():
        return ["FAIL (missing stage_ignored_paths.ps1)"]
    content = script_path.read_text(encoding='utf-8')
    required_snippets = [
        "check-ignore",
        "add', '-f'",
        "stage_ignored",
        "受控 ignored",
    ]
    for snippet in required_snippets:
        if snippet not in content:
            failures.append(f"FAIL (stage_ignored_paths script missing snippet): {snippet!r}")
    return failures


def main():
    all_failures = []
    tests = [
        ("protected_branches", test_protected_branches),
        ("stage_paths", test_stage_paths),
        ("push_protection", test_push_protection),
        ("commit_protection", test_commit_protection),
        ("commit_title_prefix", test_commit_title_prefix),
        ("create_branch_failure_blocks_native_fallback", test_create_branch_failure_blocks_native_fallback),
        ("git_common_uses_strict_safe_capture", test_git_common_uses_strict_safe_capture),
        ("controlled_ignored_staging_script", test_controlled_ignored_staging_script),
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
