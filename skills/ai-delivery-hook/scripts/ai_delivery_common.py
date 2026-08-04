from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

sys.dont_write_bytecode = True

SKILL_NAME = "ai-delivery-hook"
DEFAULT_TIMEOUT = 30


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


def resolve_path(value: str | Path) -> Path:
    return Path(value).expanduser().resolve()


def run_command(args: list[str], cwd: Path | None = None, *, timeout: int = DEFAULT_TIMEOUT) -> dict[str, Any]:
    try:
        completed = subprocess.run(
            args,
            cwd=str(cwd) if cwd else None,
            text=True,
            capture_output=True,
            timeout=timeout,
            encoding="utf-8",
            errors="replace",
        )
    except FileNotFoundError as exc:
        return {"ok": False, "returncode": None, "stdout": "", "stderr": str(exc), "command": args}
    except subprocess.TimeoutExpired as exc:
        return {"ok": False, "returncode": None, "stdout": exc.stdout or "", "stderr": exc.stderr or "", "command": args}
    return {
        "ok": completed.returncode == 0,
        "returncode": completed.returncode,
        "stdout": completed.stdout.strip(),
        "stderr": completed.stderr.strip(),
        "command": args,
    }


def git(args: list[str], repo_root: Path | None = None, *, timeout: int = DEFAULT_TIMEOUT) -> dict[str, Any]:
    return run_command(["git", *args], cwd=repo_root, timeout=timeout)


def resolve_repo_root(value: str | Path) -> Path:
    candidate = resolve_path(value)
    result = git(["rev-parse", "--show-toplevel"], candidate)
    if not result["ok"]:
        raise DeliveryError(
            "not_git_repo",
            f"目标不是 Git 仓库：{candidate}",
            next_action="传入真实 Git 仓库路径",
        )
    return resolve_path(result["stdout"])


def read_doc_summary(path: Path, max_chars: int = 800) -> str:
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""
    return re.sub(r"\s+", " ", text).strip()[:max_chars]


def add_common_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--repo-root", required=True, help="真实 Git 仓库根目录。")


def cli_guard(stage: str, fn) -> None:  # type: ignore[no-untyped-def]
    try:
        fn()
    except DeliveryError as exc:
        emit_error(stage, exc)
