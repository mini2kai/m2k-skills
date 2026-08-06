"""ai-delivery-hook 只读能力测试：仓库解析、提交检索、留存检索。"""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parent))

from ai_delivery_common import DeliveryError, git, read_doc_summary, resolve_repo_root  # noqa: E402
from ai_delivery_search import SEARCH_DIRS, SEARCH_SUFFIXES, score_text  # noqa: E402
from ai_delivery_since import commits_since  # noqa: E402

PASSED = 0
FAILED: list[str] = []


def check(name: str, condition: bool, detail: str = "") -> None:
    global PASSED
    if condition:
        PASSED += 1
    else:
        FAILED.append(f"{name}{f'：{detail}' if detail else ''}")


def init_repo(root: Path) -> None:
    git(["init", "--initial-branch=main"], root)
    git(["config", "user.email", "test@example.com"], root)
    git(["config", "user.name", "test"], root)


def commit_file(root: Path, rel: str, content: str, subject: str) -> str:
    target = root / rel
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")
    git(["add", "--", rel], root)
    git(["commit", "-m", subject], root)
    return git(["rev-parse", "HEAD"], root)["stdout"]


def test_resolve_repo_root(tmp: Path) -> None:
    plain = tmp / "plain"
    plain.mkdir()
    try:
        resolve_repo_root(plain)
        check("非 Git 目录必须拒绝", False, "未抛出 DeliveryError")
    except DeliveryError as exc:
        check("非 Git 目录必须拒绝", exc.error_type == "not_git_repo", exc.error_type)

    repo = tmp / "repo"
    repo.mkdir()
    init_repo(repo)
    commit_file(repo, "a.txt", "a", "init")
    check("Git 仓库解析成功", resolve_repo_root(repo) == repo.resolve())

    nested = repo / "sub" / "deep"
    nested.mkdir(parents=True)
    check("子目录解析到仓库根", resolve_repo_root(nested) == repo.resolve())


def test_commits_since(tmp: Path) -> None:
    repo = tmp / "since"
    repo.mkdir()
    init_repo(repo)
    base = commit_file(repo, "a.txt", "a", "base commit")
    commit_file(repo, "b.txt", "b", "second commit")
    commit_file(repo, "c.txt", "c", "third commit")

    commits, error = commits_since(repo, base, 50)
    check("有效范围无错误", error is None, str(error))
    check("检出 base 之后的两个提交", len(commits) == 2, str(len(commits)))
    subjects = [item["subject"] for item in commits]
    check("包含提交标题", "third commit" in subjects and "second commit" in subjects, str(subjects))
    check("提交字段完整", all({"commit", "author", "date", "subject"} <= set(item) for item in commits))

    head_commits, head_error = commits_since(repo, "HEAD", 50)
    check("HEAD 之后没有新提交", head_error is None and head_commits == [], str(head_commits))

    bad_commits, bad_error = commits_since(repo, "no-such-ref", 50)
    check("非法 ref 返回错误", bad_error is not None and bad_commits == [], str(bad_error))

    limited, _ = commits_since(repo, base, 1)
    check("limit 生效", len(limited) == 1, str(len(limited)))


def test_score_and_summary(tmp: Path) -> None:
    check("命中计数", score_text("delivery bugfix delivery", ["delivery"]) == 2)
    check("大小写不敏感", score_text("Delivery Bugfix", ["delivery", "bugfix"]) == 2)
    check("未命中返回 0", score_text("nothing here", ["delivery"]) == 0)
    check("空 term 被忽略", score_text("abc", ["", "abc"]) == 1)
    check("检索范围包含 Worker Author Story", (".worker_author_story",) in SEARCH_DIRS)
    check("检索支持 CSV", ".csv" in SEARCH_SUFFIXES)

    doc = tmp / "doc.md"
    doc.write_text("# Title\n\n多行\n内容   带空白", encoding="utf-8")
    summary = read_doc_summary(doc)
    check("摘要压缩空白", "  " not in summary and "\n" not in summary, summary)
    check("摘要截断", len(read_doc_summary(doc, max_chars=5)) == 5)
    check("缺失文件返回空串", read_doc_summary(tmp / "missing.md") == "")


def main() -> None:
    with tempfile.TemporaryDirectory() as raw:
        tmp = Path(raw)
        test_resolve_repo_root(tmp)
        test_commits_since(tmp)
        test_score_and_summary(tmp)

    print(f"passed: {PASSED}")
    if FAILED:
        print(f"failed: {len(FAILED)}")
        for item in FAILED:
            print(f"  - {item}")
        raise SystemExit(1)
    print("all tests passed")


if __name__ == "__main__":
    main()
