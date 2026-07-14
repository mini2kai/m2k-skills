from __future__ import annotations

import argparse
from pathlib import Path

from ai_delivery_common import (
    MANAGED_BEGIN,
    DeliveryError,
    emit,
    emit_error,
    git,
    load_active_session,
    load_json,
    resolve_path,
    resolve_repo_root,
    resolve_skill_root,
    state_path,
)
from activate_project import hook_dir_for_repo, discover_repos


def check_repo(repo_root: Path, skill_root: Path) -> list[dict[str, object]]:
    checks: list[dict[str, object]] = []
    checks.append({"name": "repo_root", "ok": True, "detail": str(repo_root)})
    try:
        hooks_dir = hook_dir_for_repo(repo_root)
        checks.append({"name": "hooks_dir", "ok": hooks_dir.exists(), "detail": str(hooks_dir)})
        for hook in ("pre-commit", "pre-push"):
            path = hooks_dir / hook
            text = path.read_text(encoding="utf-8", errors="replace") if path.exists() else ""
            checks.append({"name": f"{hook}_managed_block", "ok": MANAGED_BEGIN in text, "detail": str(path)})
    except DeliveryError as exc:
        checks.append({"name": "hooks_dir", "ok": False, "detail": exc.message})
    docs_root = repo_root / "docs"
    checks.append({"name": "repo_local_docs", "ok": docs_root.exists(), "detail": str(docs_root)})
    session = load_active_session(skill_root)
    checks.append({"name": "active_session", "ok": session is None, "detail": "无 active session" if session is None else "存在 active session"})
    checkpoint = load_json(state_path(skill_root, "checkpoint"), required=False)
    if checkpoint and checkpoint.get("last_ai_seen_commit"):
        result = git(["rev-parse", "--verify", str(checkpoint["last_ai_seen_commit"])], repo_root)
        checks.append({"name": "checkpoint_commit", "ok": result["ok"], "detail": str(checkpoint["last_ai_seen_commit"])})
    return checks


def run() -> None:
    parser = argparse.ArgumentParser(description="只读检查 ai-delivery-hook 激活状态。")
    parser.add_argument("--repo-root", help="单个 Git 仓库根目录。")
    parser.add_argument("--workspace-root", help="workspace 根目录。")
    parser.add_argument("--skill-root", help="ai-delivery-hook skill 根目录。")
    args = parser.parse_args()

    skill_root = resolve_skill_root(args.skill_root)
    if bool(args.repo_root) == bool(args.workspace_root):
        raise DeliveryError("invalid_args", "--repo-root 与 --workspace-root 必须二选一。")
    repos = [resolve_repo_root(args.repo_root)] if args.repo_root else discover_repos(resolve_path(args.workspace_root))
    if not repos:
        raise DeliveryError("no_repos", "没有可检查的 Git 仓库。")
    repo_results = [{"repo_root": str(repo), "checks": check_repo(repo, skill_root)} for repo in repos]
    failed = [check for repo in repo_results for check in repo["checks"] if not check.get("ok")]
    status = "ok" if not failed else "warning"
    emit(
        {
            "ok": True,
            "stage": "doctor",
            "status": status,
            "repositories": repo_results,
            "message": "体检完成。" if status == "ok" else "体检完成，存在需要关注的项目。",
            "next_action": "none" if status == "ok" else "查看 checks 中 ok=false 的项目并修复",
        }
    )


if __name__ == "__main__":
    try:
        run()
    except DeliveryError as exc:
        emit_error("doctor", exc)
