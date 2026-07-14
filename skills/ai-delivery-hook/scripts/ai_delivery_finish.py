from __future__ import annotations

import argparse
from pathlib import Path

from ai_delivery_common import (
    DeliveryError,
    add_common_args,
    append_audit,
    current_head,
    emit,
    emit_error,
    ensure_active_session,
    load_json,
    now_iso,
    resolve_repo_root,
    resolve_skill_root,
    safe_repo_path,
    state_path,
    write_json,
)


def validate_completed(repo_root: Path, skill_root: Path) -> dict:
    prepared = load_json(state_path(skill_root, "prepared"), required=True) or {}
    delivery = prepared.get("delivery_doc")
    if not delivery:
        raise DeliveryError("missing_delivery_doc", "prepared.local.json 缺少 delivery_doc。", next_action="重新运行 ai_delivery_prepare.py")
    target = safe_repo_path(repo_root, str(delivery))
    if not target.exists():
        raise DeliveryError("delivery_doc_missing", f"交付文档不存在：{delivery}", next_action="重新运行 ai_delivery_prepare.py")
    workflow = prepared.get("workflow_doc")
    if workflow and not safe_repo_path(repo_root, str(workflow)).exists():
        raise DeliveryError("workflow_doc_missing", f"AI workflow 文档不存在：{workflow}", next_action="重新运行 ai_delivery_prepare.py")
    return prepared


def run() -> None:
    parser = argparse.ArgumentParser(description="关闭 AI delivery session。")
    add_common_args(parser)
    parser.add_argument("--status", choices=["completed", "abandoned", "no-code"], default="completed")
    args = parser.parse_args()

    repo_root = resolve_repo_root(args.repo_root)
    skill_root = resolve_skill_root(args.skill_root)
    session = ensure_active_session(skill_root)
    head = current_head(repo_root)
    prepared = validate_completed(repo_root, skill_root) if args.status == "completed" else None
    if args.status == "completed" and not head:
        raise DeliveryError("head_missing", "当前仓库没有可记录的 HEAD。", next_action="先完成提交或使用 --status no-code/abandoned")

    checkpoint = load_json(state_path(skill_root, "checkpoint"), required=False) or {}
    checkpoint["last_ai_seen_commit"] = head or checkpoint.get("last_ai_seen_commit")
    if args.status == "completed":
        checkpoint["last_ai_delivery_commit"] = head
    checkpoint["updated_at"] = now_iso()
    write_json(state_path(skill_root, "checkpoint"), checkpoint)

    session["status"] = "finished"
    session["finished_status"] = args.status
    session["finished_at"] = now_iso()
    session["finished_commit"] = head
    write_json(state_path(skill_root, "session"), session)
    append_audit(skill_root, "finish", {"repo_root": str(repo_root), "session_id": session.get("session_id"), "status": args.status, "head": head})
    emit(
        {
            "ok": True,
            "stage": "ai_delivery_finish",
            "status": args.status,
            "session_id": session.get("session_id"),
            "checkpoint_path": str(state_path(skill_root, "checkpoint")),
            "delivery_doc": prepared.get("delivery_doc") if prepared else None,
            "message": "AI delivery session 已关闭。",
            "next_action": "handoff_summary",
        }
    )


if __name__ == "__main__":
    try:
        run()
    except DeliveryError as exc:
        emit_error("ai_delivery_finish", exc)
