from __future__ import annotations

import argparse
from pathlib import Path

from ai_delivery_common import (
    DeliveryError,
    add_common_args,
    append_audit,
    emit,
    emit_error,
    hash_file,
    load_active_session,
    load_json,
    require_current,
    resolve_repo_root,
    resolve_skill_root,
    safe_repo_path,
    staged_files,
    state_path,
)


def require_prepared(skill_root: Path) -> dict:
    return load_json(state_path(skill_root, "prepared"), required=True) or {}


def validate_prepared(repo_root: Path, skill_root: Path, mode: str) -> tuple[dict, list[str]]:
    current_path, _current = require_current(skill_root, repo_root)
    prepared = require_prepared(skill_root)
    errors: list[str] = []
    if prepared.get("current_sha256") != hash_file(current_path):
        errors.append("prepared.local.json 的 current_sha256 已过期，请重新运行 ai_delivery_prepare.py")
    delivery_rel = prepared.get("delivery_doc")
    workflow_rel = prepared.get("workflow_doc")
    required_docs: list[str] = []
    for rel in [delivery_rel, workflow_rel]:
        if not rel:
            continue
        try:
            target = safe_repo_path(repo_root, str(rel))
        except DeliveryError as exc:
            errors.append(exc.message)
            continue
        required_docs.append(str(rel).replace("\\", "/"))
        if not target.exists():
            errors.append(f"生成文档不存在：{rel}")
    prepared_files = {str(item).replace("\\", "/") for item in prepared.get("changed_files", []) if isinstance(item, str)}
    if mode == "pre-commit":
        staged = set(staged_files(repo_root))
        if staged:
            missing_docs = [rel for rel in required_docs if rel not in staged]
            if missing_docs:
                errors.append("生成文档未暂存：" + ", ".join(missing_docs))
            unexpected = sorted(staged - prepared_files)
            if unexpected:
                errors.append("staged files 未被 prepared.local.json 覆盖：" + ", ".join(unexpected))
    if mode == "pre-push":
        errors.append("AI session 仍处于 active，push 前请先运行 ai_delivery_finish.py --status completed")
    if errors:
        raise DeliveryError("delivery_check_failed", "AI delivery 校验失败。", errors=errors, next_action="按 errors 修正后重新运行 prepare/check")
    return prepared, required_docs


def run() -> None:
    parser = argparse.ArgumentParser(description="Git hook 校验 AI delivery 留存。")
    add_common_args(parser)
    parser.add_argument("--mode", choices=["pre-commit", "pre-push", "ai-start"], required=True)
    args = parser.parse_args()

    repo_root = resolve_repo_root(args.repo_root)
    skill_root = resolve_skill_root(args.skill_root)
    session = load_active_session(skill_root)
    if not session:
        emit({"ok": True, "stage": "check_ai_delivery", "mode": args.mode, "message": "无 active AI session，放行。", "next_action": "none"})
    prepared, required_docs = validate_prepared(repo_root, skill_root, args.mode)
    append_audit(skill_root, "check", {"repo_root": str(repo_root), "mode": args.mode, "session_id": session.get("session_id"), "required_docs": required_docs})
    emit(
        {
            "ok": True,
            "stage": "check_ai_delivery",
            "mode": args.mode,
            "session_id": session.get("session_id"),
            "delivery_doc": prepared.get("delivery_doc"),
            "workflow_doc": prepared.get("workflow_doc"),
            "message": "AI delivery 校验通过。",
            "next_action": "continue_git_operation",
        }
    )


if __name__ == "__main__":
    try:
        run()
    except DeliveryError as exc:
        emit_error("check_ai_delivery", exc)
