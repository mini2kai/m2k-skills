from __future__ import annotations

import argparse

from ai_delivery_common import add_common_args, cli_guard, emit, git, resolve_repo_root


def commits_since(repo_root, since: str, limit: int) -> tuple[list[dict[str, str]], str | None]:
    check = git(["rev-parse", "--verify", "--quiet", since], repo_root)
    if not check["ok"]:
        return [], f"无法解析 since 版本：{since}"
    result = git(["log", f"{since}..HEAD", f"--max-count={limit}", "--format=%H%x09%an%x09%ad%x09%s", "--date=short"], repo_root)
    if not result["ok"]:
        return [], result["stderr"] or "git log 执行失败"
    commits: list[dict[str, str]] = []
    for line in result["stdout"].splitlines():
        parts = line.split("\t")
        if len(parts) < 4:
            continue
        commits.append({"commit": parts[0][:12], "author": parts[1], "date": parts[2], "subject": parts[3]})
    return commits, None


def run() -> None:
    parser = argparse.ArgumentParser(description="只读列出指定版本之后的提交，供 AI 接手时判断人工变更。")
    add_common_args(parser)
    parser.add_argument("--since", required=True, help="起始版本，例如上次 AI 交付的 commit、tag 或 origin/main。")
    parser.add_argument("--limit", type=int, default=50)
    args = parser.parse_args()

    repo_root = resolve_repo_root(args.repo_root)
    limit = max(1, min(args.limit, 200))
    commits, error = commits_since(repo_root, args.since.strip(), limit)
    emit(
        {
            "ok": error is None,
            "stage": "ai_delivery_since",
            "repo_root": str(repo_root),
            "since": args.since,
            "commit_count": len(commits),
            "commits": commits,
            "error": error,
            "message": error or (f"发现 {len(commits)} 个提交。" if commits else "没有新提交。"),
            "next_action": "review_commits_as_context" if commits else "continue",
        },
        0 if error is None else 1,
    )


if __name__ == "__main__":
    cli_guard("ai_delivery_since", run)
