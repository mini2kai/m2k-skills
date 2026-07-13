from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

from ai_delivery_common import (
    DeliveryError,
    add_common_args,
    append_audit,
    changed_files,
    current_head,
    docs_paths,
    emit,
    emit_error,
    git_relpath,
    hash_file,
    require_current,
    resolve_repo_root,
    resolve_skill_root,
    state_path,
    write_json,
    ensure_active_session,
    now_iso,
)


def md_list(items: list[Any]) -> str:
    if not items:
        return "- 无"
    return "\n".join(f"- {item}" for item in items)


def render_delivery(current: dict[str, Any], session: dict[str, Any]) -> str:
    doc_level = current.get("doc_level")
    lines = [
        f"# {current.get('title')} 交付留存",
        "",
        "## 归纳",
        "",
        str(current.get("summary", "")),
        "",
        "## 参考判断",
        "",
        f"- 文档等级：`{doc_level}`",
        f"- 后续开发是否应参考：{'是' if doc_level != 'skip' else '通常不需要，除非涉及相同文件'}",
        f"- 任务类型：`{current.get('type')}`",
        f"- 风险等级：`{current.get('risk_level')}`",
        "",
        "## 变更背景",
        "",
        str(current.get("reason") or current.get("summary") or "未填写。"),
        "",
        "## 变更范围",
        "",
        md_list(current.get("changed_modules", [])),
        "",
        "## 影响范围",
        "",
        md_list(current.get("affected_modules", [])),
        "",
        "## 风险与注意事项",
        "",
        str(current.get("risk_notes") or "未记录额外风险。"),
        "",
        "## 验证记录",
        "",
        md_list(current.get("validation", [])),
        "",
        "## 后续事项",
        "",
        md_list(current.get("follow_up", [])),
        "",
        "## 关联文件",
        "",
        md_list(current.get("files", [])),
        "",
        "## AI Session",
        "",
        f"- session_id: `{session.get('session_id')}`",
        f"- repo_id: `{session.get('repo_id')}`",
        f"- base_commit: `{session.get('base_commit')}`",
    ]
    if doc_level == "skip":
        lines.extend(["", "## skip reason", "", str(current.get("skip_reason"))])
    if current.get("manual_backfill") or current.get("type") == "manual-backfill":
        lines.extend(["", "## AI 接手前人工变更", "", str(current.get("manual_backfill") or "见 commit 范围。")])
    return "\n".join(lines).rstrip() + "\n"


def render_workflow(current: dict[str, Any], session: dict[str, Any], repo_root: Path) -> str:
    lines = [
        f"# {current.get('title')} AI 工作流留存",
        "",
        "## 任务入口",
        "",
        f"- type: `{current.get('type')}`",
        f"- title: {current.get('title')}",
        "",
        "## AI Session",
        "",
        f"- session_id: `{session.get('session_id')}`",
        f"- repo_root: `{repo_root}`",
        f"- base_commit: `{session.get('base_commit')}`",
        "",
        "## 关键判断",
        "",
        str(current.get("ai_notes") or "未记录额外判断。"),
        "",
        "## 使用的上下文",
        "",
        md_list(current.get("context", [])),
        "",
        "## 执行过的验证",
        "",
        md_list(current.get("validation", [])),
        "",
        "## 未覆盖风险",
        "",
        str(current.get("risk_notes") or "未记录。"),
        "",
        "## 人工变更接手情况",
        "",
        str(current.get("manual_backfill") or "未检测到需要记录的人工变更。"),
    ]
    return "\n".join(lines).rstrip() + "\n"


def run() -> None:
    parser = argparse.ArgumentParser(description="生成 AI delivery repo-local 留存文档。")
    add_common_args(parser)
    parser.add_argument("--mode", choices=["normal", "manual-backfill"], default="normal")
    args = parser.parse_args()

    repo_root = resolve_repo_root(args.repo_root)
    skill_root = resolve_skill_root(args.skill_root)
    session = ensure_active_session(skill_root)
    current_path, current = require_current(skill_root, repo_root)
    if args.mode == "manual-backfill":
        current["type"] = "manual-backfill"
    doc_level = str(current["doc_level"])
    delivery_doc, workflow_doc = docs_paths(repo_root, str(current["title"]), str(current["type"]), doc_level)
    delivery_doc.parent.mkdir(parents=True, exist_ok=True)
    delivery_doc.write_text(render_delivery(current, session), encoding="utf-8")
    if workflow_doc:
        workflow_doc.parent.mkdir(parents=True, exist_ok=True)
        workflow_doc.write_text(render_workflow(current, session, repo_root), encoding="utf-8")

    current_hash = hash_file(current_path)
    generated = [git_relpath(repo_root, delivery_doc)]
    if workflow_doc:
        generated.append(git_relpath(repo_root, workflow_doc))
    changed = sorted(set(changed_files(repo_root)) | set(current.get("files", [])) | set(generated))
    prepared = {
        "session_id": session.get("session_id"),
        "repo_id": session.get("repo_id"),
        "repo_root": str(repo_root),
        "doc_level": doc_level,
        "current_sha256": current_hash,
        "prepared_at": now_iso(),
        "git_head": current_head(repo_root),
        "changed_files": changed,
        "delivery_doc": generated[0],
        "workflow_doc": generated[1] if len(generated) > 1 else None,
    }
    write_json(state_path(skill_root, "prepared"), prepared)
    append_audit(skill_root, "prepare", {"repo_root": str(repo_root), "session_id": session.get("session_id"), "doc_level": doc_level, "delivery_doc": generated[0]})
    emit(
        {
            "ok": True,
            "stage": "ai_delivery_prepare",
            "doc_level": doc_level,
            "delivery_doc": generated[0],
            "workflow_doc": prepared.get("workflow_doc"),
            "prepared_path": str(state_path(skill_root, "prepared")),
            "validated_files": changed,
            "message": "AI 交付留存文档已生成。",
            "next_action": "stage_code_and_generated_docs",
        }
    )


if __name__ == "__main__":
    try:
        run()
    except DeliveryError as exc:
        emit_error("ai_delivery_prepare", exc)
