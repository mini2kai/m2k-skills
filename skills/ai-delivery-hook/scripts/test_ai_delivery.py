from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

sys.dont_write_bytecode = True

SCRIPT_DIR = Path(__file__).resolve().parent


def run(cmd: list[str], cwd: Path | None = None, check: bool = False) -> subprocess.CompletedProcess[str]:
    proc = subprocess.run(cmd, cwd=str(cwd) if cwd else None, text=True, encoding="utf-8", errors="replace", stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if check and proc.returncode != 0:
        raise AssertionError(f"command failed: {cmd}\nstdout={proc.stdout}\nstderr={proc.stderr}")
    return proc


def run_json(cmd: list[str], cwd: Path | None = None) -> tuple[int, dict]:
    proc = run(cmd, cwd=cwd)
    try:
        data = json.loads(proc.stdout)
    except json.JSONDecodeError as exc:
        raise AssertionError(f"stdout is not JSON for {cmd}: {proc.stdout}\nstderr={proc.stderr}") from exc
    return proc.returncode, data


def init_repo(root: Path) -> Path:
    repo = root / "repo"
    repo.mkdir()
    run(["git", "init"], repo, check=True)
    run(["git", "config", "user.email", "ai-delivery@example.local"], repo, check=True)
    run(["git", "config", "user.name", "AI Delivery Test"], repo, check=True)
    (repo / "app.py").write_text("print('hello')\n", encoding="utf-8")
    run(["git", "add", "app.py"], repo, check=True)
    run(["git", "commit", "-m", "initial"], repo, check=True)
    return repo


def make_skill_root(root: Path) -> Path:
    skill = root / "skill"
    shutil.copytree(SCRIPT_DIR, skill / "scripts")
    return skill


def write_current(skill: Path, files: list[str], doc_level: str = "full", task_type: str = "feature", extra: dict | None = None) -> None:
    data = {
        "type": task_type,
        "title": "修复邮件推送逻辑",
        "summary": "修复邮件推送触发条件。",
        "reason": "原逻辑在部分状态下未触发。",
        "changed_modules": ["mail"],
        "affected_modules": ["notification"],
        "risk_level": "low",
        "doc_level": doc_level,
        "validation": ["python -m py_compile app.py"],
        "files": files,
        "ai_notes": "测试记录。",
    }
    if extra:
        data.update(extra)
    (skill / "current.local.json").write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def script(name: str) -> str:
    return str(SCRIPT_DIR / name)


def test_no_session_passes(repo: Path, skill: Path) -> None:
    code, data = run_json([sys.executable, script("check_ai_delivery.py"), "--repo-root", str(repo), "--skill-root", str(skill), "--mode", "pre-commit"])
    assert code == 0 and data["ok"] is True


def test_prepare_and_check(repo: Path, skill: Path) -> None:
    (repo / "app.py").write_text("print('hello delivery')\n", encoding="utf-8")
    code, start = run_json([sys.executable, script("ai_delivery_start.py"), "--repo-root", str(repo), "--skill-root", str(skill), "--title", "修复邮件推送逻辑", "--type", "feature"])
    assert code == 0 and start["ok"] is True
    write_current(skill, ["app.py"])
    code, prepared = run_json([sys.executable, script("ai_delivery_prepare.py"), "--repo-root", str(repo), "--skill-root", str(skill)])
    assert code == 0 and prepared["ok"] is True
    assert (repo / prepared["delivery_doc"]).exists()
    assert (repo / prepared["workflow_doc"]).exists()
    run(["git", "add", "app.py", prepared["delivery_doc"], prepared["workflow_doc"]], repo, check=True)
    code, check = run_json([sys.executable, script("check_ai_delivery.py"), "--repo-root", str(repo), "--skill-root", str(skill), "--mode", "pre-commit"])
    assert code == 0 and check["ok"] is True
    run(["git", "commit", "-m", "delivery"], repo, check=True)
    code, finish = run_json([sys.executable, script("ai_delivery_finish.py"), "--repo-root", str(repo), "--skill-root", str(skill), "--status", "completed"])
    assert code == 0 and finish["ok"] is True


def test_prepare_rejects_session_mismatch(repo: Path, skill: Path) -> None:
    (repo / "app.py").write_text("print('hello delivery')\n", encoding="utf-8")
    code, _ = run_json([sys.executable, script("ai_delivery_start.py"), "--repo-root", str(repo), "--skill-root", str(skill), "--title", "旧标题", "--type", "feature"])
    assert code == 0
    write_current(skill, ["app.py"], extra={"title": "新标题"})
    code, data = run_json([sys.executable, script("ai_delivery_prepare.py"), "--repo-root", str(repo), "--skill-root", str(skill)])
    assert code != 0 and data["error_type"] == "invalid_session"


def test_prepare_rejects_file_mismatch(repo: Path, skill: Path) -> None:
    (repo / "app.py").write_text("print('hello delivery')\n", encoding="utf-8")
    code, _ = run_json([sys.executable, script("ai_delivery_start.py"), "--repo-root", str(repo), "--skill-root", str(skill), "--title", "修复邮件推送逻辑", "--type", "feature", "--force"])
    assert code == 0
    write_current(skill, ["missing.py"])
    code, data = run_json([sys.executable, script("ai_delivery_prepare.py"), "--repo-root", str(repo), "--skill-root", str(skill)])
    assert code != 0 and data["error_type"] == "current_files_mismatch"


def test_prepared_hash_stale_blocks(repo: Path, skill: Path) -> None:
    (repo / "stale.py").write_text("print('stale')\n", encoding="utf-8")
    code, _ = run_json([sys.executable, script("ai_delivery_start.py"), "--repo-root", str(repo), "--skill-root", str(skill), "--title", "修复邮件推送逻辑", "--type", "feature", "--force"])
    assert code == 0
    write_current(skill, ["stale.py"])
    code, prepared = run_json([sys.executable, script("ai_delivery_prepare.py"), "--repo-root", str(repo), "--skill-root", str(skill)])
    assert code == 0
    write_current(skill, ["stale.py"], extra={"summary": "prepare 后被修改"})
    run(["git", "add", "stale.py", prepared["delivery_doc"], prepared["workflow_doc"]], repo, check=True)
    code, data = run_json([sys.executable, script("check_ai_delivery.py"), "--repo-root", str(repo), "--skill-root", str(skill), "--mode", "pre-commit"])
    assert code != 0 and data["ok"] is False
    assert data["error_type"] == "delivery_check_failed"


def test_skip_rules(repo: Path, skill: Path) -> None:
    code, _ = run_json([sys.executable, script("ai_delivery_start.py"), "--repo-root", str(repo), "--skill-root", str(skill), "--title", "skip", "--type", "bugfix", "--force"])
    assert code == 0
    write_current(skill, ["app.py"], doc_level="skip", task_type="bugfix", extra={"skip_reason": "测试"})
    code, data = run_json([sys.executable, script("ai_delivery_prepare.py"), "--repo-root", str(repo), "--skill-root", str(skill)])
    assert code != 0 and data["error_type"] == "invalid_current"


def test_start_rejects_empty_title(repo: Path, skill: Path) -> None:
    code, data = run_json([sys.executable, script("ai_delivery_start.py"), "--repo-root", str(repo), "--skill-root", str(skill), "--title", "   ", "--type", "feature", "--force"])
    assert code != 0 and data["error_type"] == "invalid_title"


def test_prepare_detects_ignored_docs(repo: Path, skill: Path) -> None:
    (repo / "docs").mkdir(parents=True, exist_ok=True)
    (repo / ".gitignore").write_text("docs/\n", encoding="utf-8")
    (repo / "app.py").write_text("print('ignored docs delivery')\n", encoding="utf-8")
    code, _ = run_json([sys.executable, script("ai_delivery_start.py"), "--repo-root", str(repo), "--skill-root", str(skill), "--title", "忽略 docs", "--type", "feature", "--force"])
    assert code == 0
    write_current(skill, ["app.py"], extra={"title": "忽略 docs"})
    code, prepared = run_json([sys.executable, script("ai_delivery_prepare.py"), "--repo-root", str(repo), "--skill-root", str(skill)])
    assert code == 0 and prepared["ok"] is True
    assert prepared["docs_ignored"]
    assert prepared["next_action"] == "use_controlled_ignored_docs_stage_flow"


def test_activate_and_search(repo: Path, skill: Path) -> None:
    code, data = run_json([sys.executable, script("activate_project.py"), "--repo-root", str(repo), "--skill-root", str(skill)])
    assert code == 0 and data["ok"] is True
    hook = repo / ".git" / "hooks" / "pre-commit"
    text = hook.read_text(encoding="utf-8")
    assert text.startswith("#!/bin/sh")
    assert "BEGIN ai-delivery-hook managed" in text
    code, doctor = run_json([sys.executable, script("doctor.py"), "--repo-root", str(repo), "--skill-root", str(skill)])
    assert code == 0 and doctor["ok"] is True
    code, search = run_json([sys.executable, script("ai_delivery_search.py"), "--repo-root", str(repo), "--skill-root", str(skill), "--query", "邮件 推送"])
    assert code == 0 and search["ok"] is True


def main() -> None:
    checks = []
    with tempfile.TemporaryDirectory(prefix="ai-delivery-test-") as tmp:
        root = Path(tmp)
        repo = init_repo(root)
        skill = make_skill_root(root)
        tests = [
            test_no_session_passes,
            test_prepare_and_check,
            test_prepare_rejects_session_mismatch,
            test_prepare_rejects_file_mismatch,
            test_prepared_hash_stale_blocks,
            test_skip_rules,
            test_start_rejects_empty_title,
            test_prepare_detects_ignored_docs,
            test_activate_and_search,
        ]
        for fn in tests:
            fn(repo, skill)
            checks.append({"name": fn.__name__, "ok": True})
    print(json.dumps({"ok": True, "stage": "test_ai_delivery", "checks": checks}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
