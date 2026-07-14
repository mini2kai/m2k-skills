from __future__ import annotations

import argparse
from datetime import datetime

from ai_delivery_common import (
    DeliveryError,
    add_common_args,
    append_audit,
    checkpoint_for_repo,
    current_head,
    emit,
    emit_error,
    git,
    load_active_session,
    load_json,
    now_iso,
    resolve_repo_root,
    resolve_skill_root,
    state_path,
    write_json,
)


def unrecorded_commits(repo_root, last_seen: str | None) -> list[dict[str, str]]:
    if not last_seen:
        return []
    check = git(["rev-parse", "--verify", last_seen], repo_root)
    if not check["ok"]:
        return []
    result = git(["log", f"{last_seen}..HEAD", "--format=%H%x09%s"], repo_root)
    if not result["ok"] or not result["stdout"]:
        return []
    commits: list[dict[str, str]] = []
    for line in result["stdout"].splitlines():
        sha, _, subject = line.partition("\t")
        commits.append({"commit": sha, "subject": subject})
    return commits


def run() -> None:
    parser = argparse.ArgumentParser(description="开启 AI delivery session。")
    add_common_args(parser)
    parser.add_argument("--title", required=True)
    parser.add_argument("--type", required=True, dest="task_type")
    parser.add_argument("--repo-id", default="default")
    parser.add_argument("--session-id")
    parser.add_argument("--force", action="store_true", help="覆盖已有 active session。")
    args = parser.parse_args()

    repo_root = resolve_repo_root(args.repo_root)
    skill_root = resolve_skill_root(args.skill_root)
    existing = load_active_session(skill_root)
    if existing and not args.force:
        raise DeliveryError("session_already_active", "已有 active AI session。", next_action="先运行 ai_delivery_finish.py 或使用 --force")

    head = current_head(repo_root)
    checkpoint = load_json(state_path(skill_root, "checkpoint"), required=False)
    repo_checkpoint = checkpoint_for_repo(checkpoint, args.repo_id)
    last_seen = repo_checkpoint.get("last_ai_seen_commit") if isinstance(repo_checkpoint, dict) else None
    initialized = False
    if not last_seen:
        last_seen = head
        initialized = True

    session_id = args.session_id or datetime.now().strftime("%Y%m%d-%H%M%S-ai")
    session = {
        "session_id": session_id,
        "actor": "ai",
        "status": "active",
        "repo_id": args.repo_id,
        "repo_root": str(repo_root),
        "started_at": now_iso(),
        "base_commit": head,
        "task_title": args.title,
        "task_type": args.task_type,
    }
    write_json(state_path(skill_root, "session"), session)
    if initialized:
        write_json(
            state_path(skill_root, "checkpoint"),
            {"last_ai_seen_commit": last_seen, "last_ai_delivery_commit": None, "updated_at": now_iso()},
        )
    commits = unrecorded_commits(repo_root, None if initialized else str(last_seen))
    append_audit(skill_root, "start", {"repo_root": str(repo_root), "session_id": session_id, "requires_manual_backfill": bool(commits)})
    payload = {
        "ok": not bool(commits),
        "stage": "ai_delivery_start",
        "session_id": session_id,
        "session_path": str(state_path(skill_root, "session")),
        "base_commit": head,
        "initialized": initialized,
        "requires_manual_backfill": bool(commits),
        "unrecorded_commits": commits,
        "message": "AI delivery session 已开启。" if not commits else "检测到上次 AI 接手后存在人工提交，需要先补录。",
        "next_action": "write_current_and_prepare" if not commits else "生成 manual-backfill 类型 current.local.json 后运行 ai_delivery_prepare.py",
    }
    emit(payload, 0 if not commits else 2)


if __name__ == "__main__":
    try:
        run()
    except DeliveryError as exc:
        emit_error("ai_delivery_start", exc)
