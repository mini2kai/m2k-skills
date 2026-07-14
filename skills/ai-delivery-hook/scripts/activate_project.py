from __future__ import annotations

import argparse
import os
import stat
from pathlib import Path
from typing import Any

from ai_delivery_common import (
    MANAGED_BEGIN,
    MANAGED_END,
    DeliveryError,
    append_audit,
    emit,
    git,
    load_json,
    now_iso,
    resolve_path,
    resolve_repo_root,
    resolve_skill_root,
    state_path,
    write_json,
)

COMPLEX_HOOK_MARKERS = ("husky", "lint-staged", "pre-commit.com", "pre-commit run", "lefthook")
HOOK_NAMES = ("pre-commit", "pre-push")


def managed_block(skill_root: Path, mode: str) -> str:
    script = (skill_root / "scripts" / "check_ai_delivery.py").resolve().as_posix()
    skill = skill_root.resolve().as_posix()
    return "\n".join(
        [
            MANAGED_BEGIN,
            'repo_root="$(git rev-parse --show-toplevel)"',
            f'python "{script}" --repo-root "$repo_root" --skill-root "{skill}" --mode {mode}',
            "status=$?",
            "if [ $status -ne 0 ]; then",
            "  exit $status",
            "fi",
            MANAGED_END,
            "",
        ]
    )


def has_complex_hook(text: str) -> bool:
    lower = text.lower()
    return any(marker in lower for marker in COMPLEX_HOOK_MARKERS)


def hook_dir_for_repo(repo_root: Path) -> Path:
    configured = git(["config", "--get", "core.hooksPath"], repo_root)
    if configured["ok"] and configured["stdout"]:
        path = Path(configured["stdout"])
        return path if path.is_absolute() else (repo_root / path).resolve()
    git_dir_result = git(["rev-parse", "--git-dir"], repo_root)
    if not git_dir_result["ok"] or not git_dir_result["stdout"]:
        raise DeliveryError("git_dir_failed", "无法解析 .git 目录。", stderr=git_dir_result.get("stderr"))
    git_dir = Path(git_dir_result["stdout"])
    if not git_dir.is_absolute():
        git_dir = (repo_root / git_dir).resolve()
    return git_dir / "hooks"


def backup_hook(skill_root: Path, hook_path: Path) -> Path | None:
    if not hook_path.exists():
        return None
    stamp = now_iso().replace(":", "").replace("-", "")
    backup_dir = skill_root / "backups" / stamp
    backup_dir.mkdir(parents=True, exist_ok=True)
    target = backup_dir / f"{hook_path.parent.name}-{hook_path.name}"
    target.write_bytes(hook_path.read_bytes())
    return target


def upsert_block(text: str, block: str) -> tuple[str, str]:
    if MANAGED_BEGIN in text and MANAGED_END in text:
        start = text.index(MANAGED_BEGIN)
        end = text.index(MANAGED_END, start) + len(MANAGED_END)
        updated = text[:start] + block.rstrip() + text[end:]
        if not updated.endswith("\n"):
            updated += "\n"
        return updated, "replaced"
    if not text:
        return "#!/bin/sh\n\n" + block, "created"
    if not text.endswith("\n"):
        text += "\n"
    return text + "\n" + block, "appended"


def activate_hook(repo_root: Path, skill_root: Path, hook_name: str, mode: str) -> dict[str, Any]:
    hooks_dir = hook_dir_for_repo(repo_root)
    hook_path = hooks_dir / hook_name
    check_mode = "pre-commit" if hook_name == "pre-commit" else "pre-push"
    block = managed_block(skill_root, check_mode)
    if mode == "manual":
        return {"hook": hook_name, "ok": False, "requires_user_action": True, "snippet": block, "message": "manual 模式未修改 hook。"}
    existing = hook_path.read_text(encoding="utf-8", errors="replace") if hook_path.exists() else ""
    if existing and MANAGED_BEGIN not in existing and has_complex_hook(existing):
        return {
            "hook": hook_name,
            "ok": False,
            "requires_user_action": True,
            "snippet": block,
            "message": "检测到复杂 hook 管理器，未自动修改。",
        }
    hooks_dir.mkdir(parents=True, exist_ok=True)
    backup = backup_hook(skill_root, hook_path)
    updated, action = upsert_block(existing, block)
    hook_path.write_text(updated, encoding="utf-8")
    try:
        hook_path.chmod(hook_path.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    except OSError:
        pass
    return {"hook": hook_name, "ok": True, "path": str(hook_path), "action": action, "backup": str(backup) if backup else None}


def discover_repos(workspace_root: Path) -> list[Path]:
    repos: list[Path] = []
    for child in sorted(workspace_root.iterdir()):
        if child.is_dir() and (child / ".git").exists():
            repos.append(resolve_repo_root(child))
    if (workspace_root / ".git").exists():
        repos.insert(0, resolve_repo_root(workspace_root))
    return sorted(set(repos))


def load_workspace_repos(workspace_root: Path, skill_root: Path, discover: bool) -> list[Path]:
    config = load_json(state_path(skill_root, "workspace"), required=False)
    repos: list[Path] = []
    if isinstance(config, dict) and isinstance(config.get("repositories"), list):
        for item in config["repositories"]:
            if isinstance(item, dict) and item.get("path"):
                repos.append(resolve_repo_root(workspace_root / str(item["path"])))
    if discover or not repos:
        repos.extend(discover_repos(workspace_root))
    return sorted(set(repos))


def run() -> None:
    parser = argparse.ArgumentParser(description="激活 ai-delivery-hook 到真实 Git 仓库。")
    parser.add_argument("--repo-root", help="单个 Git 仓库根目录。")
    parser.add_argument("--workspace-root", help="workspace 根目录。")
    parser.add_argument("--skill-root", help="ai-delivery-hook skill 根目录。")
    parser.add_argument("--discover-repos", action="store_true", help="扫描 workspace 直接子目录中的 Git 仓库。")
    parser.add_argument("--mode", choices=["append-existing", "manual"], default="append-existing")
    args = parser.parse_args()

    skill_root = resolve_skill_root(args.skill_root)
    if bool(args.repo_root) == bool(args.workspace_root):
        raise DeliveryError("invalid_args", "--repo-root 与 --workspace-root 必须二选一。")
    repos = [resolve_repo_root(args.repo_root)] if args.repo_root else load_workspace_repos(resolve_path(args.workspace_root), skill_root, args.discover_repos)
    if not repos:
        raise DeliveryError("no_repos", "没有找到可激活的 Git 仓库。", next_action="检查 --repo-root 或使用 --discover-repos")

    results: list[dict[str, Any]] = []
    requires_user_action = False
    for repo in repos:
        hook_results = [activate_hook(repo, skill_root, hook, args.mode) for hook in HOOK_NAMES]
        requires_user_action = requires_user_action or any(item.get("requires_user_action") for item in hook_results)
        results.append({"repo_root": str(repo), "hooks": hook_results})

    activation = {
        "skill": "ai-delivery-hook",
        "skill_path": str(skill_root),
        "activation_mode": args.mode,
        "activated_at": now_iso(),
        "repositories": [str(repo) for repo in repos],
    }
    write_json(state_path(skill_root, "activation"), activation)
    append_audit(skill_root, "activate", {"repositories": [str(repo) for repo in repos], "requires_user_action": requires_user_action})
    emit(
        {
            "ok": not requires_user_action,
            "stage": "activate_project",
            "requires_user_action": requires_user_action,
            "activation_path": str(state_path(skill_root, "activation")),
            "results": results,
            "message": "激活完成。" if not requires_user_action else "部分 hook 需要手动接入 snippet。",
            "next_action": "run_doctor" if not requires_user_action else "将 snippet 加入现有 hook 后运行 doctor.py",
        },
        0 if not requires_user_action else 2,
    )


if __name__ == "__main__":
    try:
        run()
    except DeliveryError as exc:
        from ai_delivery_common import emit_error

        emit_error("activate_project", exc)
