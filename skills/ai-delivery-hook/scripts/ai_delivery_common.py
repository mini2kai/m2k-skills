from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

sys.dont_write_bytecode = True

SKILL_NAME = "ai-delivery-hook"
DEFAULT_TIMEOUT = 30
MAX_JSON_BYTES = 256 * 1024
MANAGED_BEGIN = "# BEGIN ai-delivery-hook managed"
MANAGED_END = "# END ai-delivery-hook managed"
DOC_LEVELS = {"full", "compact", "skip"}
TASK_TYPES = {"feature", "bugfix", "refactor", "docs", "config", "test", "hotfix", "manual-backfill"}
RISK_LEVELS = {"low", "medium", "high"}
SKIP_FORBIDDEN_TYPES = {"bugfix", "hotfix"}
STATE_NAMES = {
    "activation": "activation.local.json",
    "workspace": "workspace.local.json",
    "current": "current.local.json",
    "prepared": "prepared.local.json",
    "session": "session.local.json",
    "checkpoint": "checkpoint.local.json",
}


class DeliveryError(RuntimeError):
    def __init__(self, error_type: str, message: str, *, next_action: str | None = None, **details: Any) -> None:
        super().__init__(message)
        self.error_type = error_type
        self.message = message
        self.next_action = next_action
        self.details = details


def now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def emit(payload: dict[str, Any], exit_code: int = 0) -> None:
    payload.setdefault("skill", SKILL_NAME)
    payload.setdefault("ts", now_iso())
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    raise SystemExit(exit_code)


def emit_error(stage: str, exc: DeliveryError, exit_code: int = 1) -> None:
    payload: dict[str, Any] = {
        "ok": False,
        "stage": stage,
        "error_type": exc.error_type,
        "message": exc.message,
    }
    if exc.next_action:
        payload["next_action"] = exc.next_action
    payload.update(exc.details)
    emit(payload, exit_code)


def script_skill_root() -> Path:
    return Path(__file__).resolve().parents[1]


def resolve_path(value: str | Path) -> Path:
    return Path(value).expanduser().resolve()


def resolve_skill_root(value: str | Path | None = None) -> Path:
    root = resolve_path(value) if value else script_skill_root()
    if not root.exists():
        raise DeliveryError("missing_skill_root", f"未找到 skill 根目录：{root}", next_action="检查 --skill-root 参数")
    return root


def run_command(args: list[str], *, cwd: Path | None = None, timeout: int = DEFAULT_TIMEOUT) -> dict[str, Any]:
    try:
        proc = subprocess.run(
            args,
            cwd=str(cwd) if cwd else None,
            text=True,
            encoding="utf-8",
            errors="replace",
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=timeout,
            shell=False,
        )
        return {
            "ok": proc.returncode == 0,
            "returncode": proc.returncode,
            "stdout": proc.stdout.strip(),
            "stderr": proc.stderr.strip(),
            "command": args,
        }
    except FileNotFoundError as exc:
        return {"ok": False, "returncode": None, "stdout": "", "stderr": str(exc), "command": args, "error_type": "command_not_found"}
    except subprocess.TimeoutExpired as exc:
        return {"ok": False, "returncode": None, "stdout": exc.stdout or "", "stderr": exc.stderr or "", "command": args, "error_type": "timeout"}


def git(args: list[str], repo_root: Path | None = None, *, timeout: int = DEFAULT_TIMEOUT) -> dict[str, Any]:
    return run_command(["git", *args], cwd=repo_root, timeout=timeout)


def require_git_available() -> None:
    if shutil.which("git") is None:
        raise DeliveryError("git_missing", "未找到 git 命令。", next_action="安装 Git 或修复 PATH")


def resolve_repo_root(value: str | Path) -> Path:
    require_git_available()
    candidate = resolve_path(value)
    result = git(["rev-parse", "--show-toplevel"], candidate if candidate.exists() else None)
    if not result["ok"]:
        raise DeliveryError("not_git_repo", f"目标不是 Git 仓库：{candidate}", next_action="传入真实 Git 仓库路径或改用 --workspace-root")
    return resolve_path(result["stdout"])


def current_head(repo_root: Path) -> str | None:
    result = git(["rev-parse", "--verify", "HEAD"], repo_root)
    return result["stdout"] if result["ok"] and result["stdout"] else None


def git_relpath(repo_root: Path, path: Path) -> str:
    resolved = path.resolve()
    try:
        rel = resolved.relative_to(repo_root.resolve())
    except ValueError as exc:
        raise DeliveryError("path_outside_repo", f"路径不在 repo 内：{resolved}", next_action="检查生成路径或 files 字段") from exc
    return rel.as_posix()


def normalize_repo_relpath(rel: str) -> str:
    return rel.strip().replace("\\", "/")


def safe_repo_path(repo_root: Path, rel: str) -> Path:
    normalized = normalize_repo_relpath(rel)
    if not normalized or normalized.startswith("/") or re.match(r"^[A-Za-z]:", normalized):
        raise DeliveryError("invalid_repo_path", f"必须使用仓库内相对路径：{rel}", next_action="修正 current.local.json 的 files 字段")
    target = (repo_root / normalized).resolve()
    try:
        target.relative_to(repo_root.resolve())
    except ValueError as exc:
        raise DeliveryError("path_outside_repo", f"路径越界：{rel}", next_action="修正 current.local.json 的 files 字段") from exc
    return target


def state_path(skill_root: Path, name: str) -> Path:
    if name not in STATE_NAMES:
        raise DeliveryError("unknown_state", f"未知状态文件：{name}")
    return skill_root / STATE_NAMES[name]


def load_json(path: Path, *, required: bool = False) -> dict[str, Any] | None:
    if not path.exists():
        if required:
            raise DeliveryError("missing_json", f"缺少文件：{path}", next_action="按提示生成对应 .local.json 文件")
        return None
    if path.stat().st_size > MAX_JSON_BYTES:
        raise DeliveryError("json_too_large", f"JSON 文件超过上限：{path}", next_action="精简该 JSON 文件")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise DeliveryError("invalid_json", f"JSON 解析失败：{path}：{exc}", next_action="修正 JSON 格式") from exc
    if not isinstance(data, dict):
        raise DeliveryError("invalid_json_root", f"JSON 顶层必须是对象：{path}")
    return data


def write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    tmp.replace(path)


def append_audit(skill_root: Path, event: str, payload: dict[str, Any]) -> None:
    try:
        log_dir = skill_root / "logs"
        log_dir.mkdir(parents=True, exist_ok=True)
        day = datetime.now().strftime("%Y-%m-%d")
        record = {"ts": now_iso(), "event": event, **payload}
        with (log_dir / f"ai-delivery-{day}.jsonl").open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(record, ensure_ascii=False, separators=(",", ":")) + "\n")
    except OSError:
        return


def hash_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def slugify(value: str, fallback: str = "ai-delivery") -> str:
    text = value.strip().lower()
    text = re.sub(r"[^a-z0-9\u4e00-\u9fff]+", "-", text)
    text = re.sub(r"-+", "-", text).strip("-")
    if not text:
        text = fallback
    return text[:80].strip("-") or fallback


def parse_status_paths(output: str) -> list[str]:
    paths: list[str] = []
    for line in output.splitlines():
        if not line.strip():
            continue
        if len(line) >= 3 and line[2] == " ":
            raw = line[3:]
        elif len(line) >= 2 and line[1] == " ":
            raw = line[2:]
        else:
            raw = line.strip()
        if " -> " in raw:
            raw = raw.split(" -> ", 1)[1]
        paths.append(raw.strip().replace("\\", "/"))
    return sorted(set(paths))


def changed_files(repo_root: Path) -> list[str]:
    result = git(["-c", "core.quotePath=false", "status", "--porcelain"], repo_root)
    if not result["ok"]:
        raise DeliveryError("git_status_failed", "读取 git status 失败。", stderr=result.get("stderr"), next_action="先修复 Git 仓库状态")
    return parse_status_paths(result["stdout"])


def staged_files(repo_root: Path) -> list[str]:
    result = git(["-c", "core.quotePath=false", "diff", "--cached", "--name-only", "--diff-filter=ACMRTD"], repo_root)
    if not result["ok"]:
        raise DeliveryError("git_diff_failed", "读取 staged files 失败。", stderr=result.get("stderr"), next_action="先修复 Git 仓库状态")
    return sorted(set(line.strip().replace("\\", "/") for line in result["stdout"].splitlines() if line.strip()))


def docs_paths(repo_root: Path, title: str, task_type: str, doc_level: str) -> tuple[Path, Path | None]:
    today = datetime.now().strftime("%Y-%m-%d")
    slug = slugify(f"{task_type}-{title}", fallback=task_type or "ai-delivery")
    delivery = repo_root / "docs" / "delivery" / today / f"{slug}-delivery.md"
    workflow = None if doc_level == "skip" else repo_root / "docs" / "ai-workflow" / today / f"{slug}-ai-workflow.md"
    return delivery, workflow


def validate_current(data: dict[str, Any], repo_root: Path) -> list[str]:
    errors: list[str] = []
    required = ["type", "title", "summary", "changed_modules", "risk_level", "doc_level", "validation", "files"]
    for key in required:
        if key not in data:
            errors.append(f"缺少字段：{key}")
    title = str(data.get("title", "")).strip()
    task_type = str(data.get("type", "")).strip()
    risk_level = str(data.get("risk_level", "")).strip()
    doc_level = str(data.get("doc_level", "")).strip()
    if not title:
        errors.append("title 不能为空")
    if task_type not in TASK_TYPES:
        errors.append(f"type 不在枚举内：{task_type}")
    if risk_level not in RISK_LEVELS:
        errors.append(f"risk_level 不在枚举内：{risk_level}")
    if doc_level not in DOC_LEVELS:
        errors.append(f"doc_level 不在枚举内：{doc_level}")
    for key in ("changed_modules", "validation", "files"):
        value = data.get(key)
        if not isinstance(value, list) or not value:
            errors.append(f"{key} 必须是非空数组")
    if doc_level == "skip":
        if not str(data.get("skip_reason", "")).strip():
            errors.append("doc_level=skip 时必须提供 skip_reason")
        if task_type in SKIP_FORBIDDEN_TYPES:
            errors.append(f"{task_type} 不允许使用 doc_level=skip")
        if bool(data.get("cross_repo")) or len(data.get("repositories", []) or []) > 1:
            errors.append("跨仓任务不允许使用 doc_level=skip")
        if risk_level == "high":
            errors.append("high 风险任务不允许使用 doc_level=skip")
    files = data.get("files", []) if isinstance(data.get("files"), list) else []
    normalized_files: list[str] = []
    for item in files:
        if not isinstance(item, str):
            errors.append("files 中只能包含字符串路径")
            continue
        normalized = normalize_repo_relpath(item)
        if not normalized:
            errors.append("files 中不能包含空白路径")
            continue
        normalized_files.append(normalized)
        try:
            safe_repo_path(repo_root, normalized)
        except DeliveryError as exc:
            errors.append(exc.message)
    if len(normalized_files) != len(set(normalized_files)):
        errors.append("files 中存在重复路径")
    return errors


def require_current(skill_root: Path, repo_root: Path) -> tuple[Path, dict[str, Any]]:
    path = state_path(skill_root, "current")
    data = load_json(path, required=True) or {}
    errors = validate_current(data, repo_root)
    if errors:
        raise DeliveryError("invalid_current", "current.local.json 校验失败。", errors=errors, next_action="修正 current.local.json 后重新运行 prepare")
    return path, data


def load_active_session(skill_root: Path) -> dict[str, Any] | None:
    data = load_json(state_path(skill_root, "session"), required=False)
    if not data:
        return None
    if data.get("actor") == "ai" and data.get("status") == "active":
        return data
    return None


def validate_active_session(session: dict[str, Any], repo_root: Path, current: dict[str, Any] | None = None) -> list[str]:
    errors: list[str] = []
    if session.get("actor") != "ai":
        errors.append("session.actor 必须是 ai")
    if session.get("status") != "active":
        errors.append("session.status 必须是 active")
    if not str(session.get("session_id", "")).strip():
        errors.append("session.session_id 不能为空")
    if str(session.get("repo_root", "")).strip() != str(repo_root):
        errors.append("session.repo_root 与当前 --repo-root 不一致")
    task_title = str(session.get("task_title", "")).strip()
    task_type = str(session.get("task_type", "")).strip()
    if not task_title:
        errors.append("session.task_title 不能为空")
    if task_type not in TASK_TYPES:
        errors.append(f"session.task_type 不合法：{task_type}")
    if current is not None:
        current_title = str(current.get("title", "")).strip()
        current_type = str(current.get("type", "")).strip()
        if current_title != task_title:
            errors.append("session.task_title 与 current.local.json.title 不一致")
        if current_type != "manual-backfill" and task_type != current_type:
            errors.append("session.task_type 与 current.local.json.type 不一致")
    return errors


def normalize_file_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    normalized: list[str] = []
    for item in value:
        if isinstance(item, str):
            path = normalize_repo_relpath(item)
            if path:
                normalized.append(path)
    return normalized


def current_file_set(data: dict[str, Any]) -> set[str]:
    return set(normalize_file_list(data.get("files")))


def is_git_ignored(repo_root: Path, rel: str) -> bool:
    result = git(["check-ignore", "-q", "--", normalize_repo_relpath(rel)], repo_root)
    return result["ok"]


def current_docs_set(data: dict[str, Any]) -> set[str]:
    docs = data.get("docs_ignored", [])
    return set(normalize_file_list(docs))


def ensure_active_session(skill_root: Path) -> dict[str, Any]:
    session = load_active_session(skill_root)
    if not session:
        raise DeliveryError("no_active_session", "没有 active AI session。", next_action="先运行 ai_delivery_start.py")
    return session


def checkpoint_for_repo(checkpoint: dict[str, Any] | None, repo_id: str | None = None) -> dict[str, Any]:
    if not checkpoint:
        return {}
    repos = checkpoint.get("repositories")
    if repo_id and isinstance(repos, dict) and isinstance(repos.get(repo_id), dict):
        return repos[repo_id]
    return checkpoint


def read_doc_summary(path: Path, max_chars: int = 800) -> str:
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""
    text = re.sub(r"\s+", " ", text).strip()
    return text[:max_chars]


def add_common_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--repo-root", required=True, help="真实 Git 仓库根目录。")
    parser.add_argument("--skill-root", help="ai-delivery-hook skill 根目录，默认脚本所在 skill。")


def cli_guard(stage: str, fn) -> None:  # type: ignore[no-untyped-def]
    try:
        fn()
    except DeliveryError as exc:
        emit_error(stage, exc)
