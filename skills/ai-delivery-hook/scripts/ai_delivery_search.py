from __future__ import annotations

import argparse

from ai_delivery_common import add_common_args, cli_guard, emit, read_doc_summary, resolve_repo_root

SEARCH_DIRS = (("docs", "delivery"), ("docs", "ai-workflow"), ("docs", "thoughts"), (".worker_author_story",))
SEARCH_SUFFIXES = {".md", ".csv"}


def score_text(text: str, terms: list[str]) -> int:
    lower = text.lower()
    return sum(lower.count(term.lower()) for term in terms if term)


def run() -> None:
    parser = argparse.ArgumentParser(description="只读检索 repo-local 交付与设计留存文档。")
    add_common_args(parser)
    parser.add_argument("--query", required=True)
    parser.add_argument("--limit", type=int, default=10)
    args = parser.parse_args()

    repo_root = resolve_repo_root(args.repo_root)
    terms = [item for item in args.query.replace("/", " ").replace("-", " ").split() if item]
    matches: list[dict[str, object]] = []
    for parts in SEARCH_DIRS:
        root = repo_root.joinpath(*parts)
        if not root.exists():
            continue
        for path in root.rglob("*"):
            if not path.is_file() or path.suffix.lower() not in SEARCH_SUFFIXES:
                continue
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
    cli_guard("ai_delivery_search", run)
