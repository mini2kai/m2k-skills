from __future__ import annotations

import argparse
from pathlib import Path

from ai_delivery_common import DeliveryError, add_common_args, emit, emit_error, read_doc_summary, resolve_repo_root, resolve_skill_root


def score_text(text: str, terms: list[str]) -> int:
    lower = text.lower()
    return sum(lower.count(term.lower()) for term in terms if term)


def run() -> None:
    parser = argparse.ArgumentParser(description="只读检索 repo-local AI delivery 历史文档。")
    add_common_args(parser)
    parser.add_argument("--query", required=True)
    parser.add_argument("--limit", type=int, default=10)
    args = parser.parse_args()

    repo_root = resolve_repo_root(args.repo_root)
    resolve_skill_root(args.skill_root)
    terms = [item for item in args.query.replace("/", " ").replace("-", " ").split() if item]
    roots = [repo_root / "docs" / "delivery", repo_root / "docs" / "ai-workflow"]
    matches: list[dict[str, object]] = []
    for root in roots:
        if not root.exists():
            continue
        for path in root.rglob("*.md"):
            rel = path.relative_to(repo_root).as_posix()
            summary = read_doc_summary(path)
            score = score_text(rel + " " + summary, terms)
            if score > 0:
                matches.append({"path": rel, "score": score, "summary": summary})
    matches.sort(key=lambda item: (-int(item["score"]), str(item["path"])))
    limit = max(1, min(args.limit, 50))
    emit(
        {
            "ok": True,
            "stage": "ai_delivery_search",
            "query": args.query,
            "matches": matches[:limit],
            "total_matches": len(matches),
            "message": "历史留存检索完成。" if matches else "未找到匹配的历史留存文档。",
            "next_action": "use_matches_as_context" if matches else "continue_without_history",
        }
    )


if __name__ == "__main__":
    try:
        run()
    except DeliveryError as exc:
        emit_error("ai_delivery_search", exc)
