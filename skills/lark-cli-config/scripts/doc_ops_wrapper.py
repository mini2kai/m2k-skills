import argparse

from common import (
    add_common_args,
    check_auth_status,
    clean_doc_text,
    ensure_utf8_file,
    extract_created_doc_reference,
    infer_title_from_fetch_output,
    json_exit,
    load_reference_json,
    normalize_document_target,
    prepare_markdown_cli_file,
    run_cli,
)


SUPPORTED_OPERATIONS = {"docs_fetch", "docs_create", "docs_update_overwrite"}


def risk_info(operation):
    matrix = load_reference_json("operation_risk_matrix.json")
    return matrix.get(operation, {
        "risk": "unknown",
        "requires_confirmation": True,
        "preflight_read_required": True,
        "post_verify_required": True,
        "description": "未登记操作",
    })


def require_auth(as_identity="user"):
    auth = check_auth_status(as_identity)
    if not auth["ok"]:
        json_exit({
            "ok": False,
            "stage": "auth_check",
            "error_type": "auth_missing",
            "requiredIdentity": auth.get("requiredIdentity"),
            "identity": auth.get("identity"),
            "tokenStatus": auth.get("tokenStatus"),
            "expiresAt": auth.get("expiresAt"),
            "message": auth.get("message") or "当前没有可用 user 授权",
            "diagnostics": auth.get("diagnostics"),
            "next_action": "run_auth_login",
        }, code=1)
    return auth


def fetch_doc(doc_arg, as_identity="user", output_format="pretty"):
    return run_cli(["docs", "+fetch", "--doc", doc_arg, "--as", as_identity, "--format", output_format], timeout=120)


def update_doc_overwrite(doc_arg, file_info, as_identity="user"):
    return run_cli([
        "docs", "+update",
        "--doc", doc_arg,
        "--mode", "overwrite",
        "--markdown", file_info["cli_markdown_arg"],
        "--as", as_identity,
    ], timeout=180, cwd=file_info["cli_cwd"])


def update_doc_overwrite_v2(doc_arg, file_info, as_identity="user"):
    return run_cli([
        "docs", "+update",
        "--api-version", "v2",
        "--doc", doc_arg,
        "--command", "overwrite",
        "--content", file_info["cli_markdown_arg"],
        "--doc-format", "markdown",
        "--as", as_identity,
    ], timeout=180, cwd=file_info["cli_cwd"])


def resolve_target_or_exit(args, stage):
    target = normalize_document_target(target=args.target, doc=args.doc, wiki_node=args.wiki_node)
    if not target["ok"]:
        json_exit({
            "ok": False,
            "stage": stage,
            "operation": args.operation,
            "target": target,
            "message": target["message"],
            "next_action": target.get("next_action"),
        }, code=1)
    return target


def error_message(result, fallback):
    diagnostics = result.get("diagnostics") or {}
    return diagnostics.get("message") or result.get("stderr") or result.get("stdout") or fallback


def create_result_message(result, created_target, verify):
    if result["ok"] and created_target.get("ok") and verify["ok"]:
        return "文档创建成功并完成 fetch 验证"
    if result["ok"] and not created_target.get("ok"):
        return created_target.get("message") or "文档已创建，但未能从 CLI 输出解析新文档链接或 doc_token"
    if result["ok"] and created_target.get("ok") and not verify["ok"]:
        return error_message(verify, "文档已创建，但 fetch 验证失败")
    return error_message(result, "文档创建失败")


def preflight_docs_fetch(args):
    target = resolve_target_or_exit(args, "preflight")
    auth = require_auth(args.as_identity)
    info = risk_info("docs_fetch")
    json_exit({
        "ok": True,
        "stage": "preflight",
        "operation": "docs_fetch",
        "risk": info["risk"],
        "requires_confirmation": info["requires_confirmation"],
        "identity": auth.get("identity"),
        "target": target,
        "message": "读取操作风险较低，可直接 execute。",
        "next_action": "execute_docs_fetch",
    })


def execute_docs_fetch(args):
    target = resolve_target_or_exit(args, "execute")
    auth = require_auth(args.as_identity)
    result = fetch_doc(target["doc_arg"], args.as_identity, args.format)
    cleaned_text = clean_doc_text(result.get("stdout", "")) if result["ok"] else ""
    title = infer_title_from_fetch_output(cleaned_text or result.get("stdout", ""))
    json_exit({
        "ok": result["ok"],
        "stage": "execute",
        "operation": "docs_fetch",
        "risk": risk_info("docs_fetch")["risk"],
        "identity": auth.get("identity"),
        "target": {**target, "title": title},
        "result": {
            "verified": result["ok"],
            "title": title,
            "content_preview": cleaned_text[:1200] if args.include_preview else None,
            "full_text_chars": len(cleaned_text),
        },
        "cleaned_text": cleaned_text[:args.max_text_chars] if args.include_text else None,
        "diagnostics": result.get("diagnostics"),
        "message": "文档读取成功" if result["ok"] else error_message(result, "文档读取失败"),
        "next_action": None if result["ok"] else "inspect_docs_fetch_error",
    }, code=0 if result["ok"] else 1)


def preflight_docs_create(args):
    auth = require_auth(args.as_identity)
    file_info = prepare_markdown_cli_file(args.markdown)
    info = risk_info("docs_create")
    ok = file_info["ok"] and bool(args.title)
    json_exit({
        "ok": ok,
        "stage": "preflight",
        "operation": "docs_create",
        "risk": info["risk"],
        "requires_confirmation": info["requires_confirmation"],
        "identity": auth.get("identity"),
        "target": {"type": "wiki_node", "wiki_node": args.wiki_node, "title": args.title},
        "local_input": file_info,
        "message": "创建文档前置检查通过" if ok else "创建文档前置检查未通过",
        "next_action": "execute_docs_create" if ok else "fix_preflight_blocker",
    }, code=0 if ok else 1)


def execute_docs_create(args):
    auth = require_auth(args.as_identity)
    file_info = prepare_markdown_cli_file(args.markdown)
    if not file_info["ok"]:
        json_exit({
            "ok": False,
            "stage": "execute",
            "operation": "docs_create",
            "local_input": file_info,
            "message": "markdown 文件检查失败，拒绝创建文档",
            "next_action": "fix_markdown_file",
        }, code=1)
    cli_args = ["docs", "+create", "--title", args.title, "--markdown", file_info["cli_markdown_arg"], "--as", args.as_identity]
    if args.wiki_node:
        cli_args[2:2] = ["--wiki-node", args.wiki_node]
    result = run_cli(cli_args, timeout=180, cwd=file_info["cli_cwd"])
    created_target = extract_created_doc_reference(result.get("stdout", "")) if result["ok"] else {"ok": False}
    verify = fetch_doc(created_target["doc_arg"], args.as_identity, "pretty") if created_target.get("ok") else {"ok": False, "stdout": "", "stderr": "created target unresolved"}
    title = infer_title_from_fetch_output(verify.get("stdout", ""))
    json_exit({
        "ok": result["ok"] and created_target.get("ok") and verify["ok"],
        "stage": "execute",
        "operation": "docs_create",
        "risk": risk_info("docs_create")["risk"],
        "identity": auth.get("identity"),
        "target": {"type": "wiki_node", "wiki_node": args.wiki_node, "title": args.title},
        "created_target": {**created_target, "title": title} if created_target.get("ok") else created_target,
        "local_input": file_info,
        "result": {
            "create_ok": result["ok"],
            "target_resolved": created_target.get("ok", False),
            "fetch_verify_ok": verify["ok"],
            "title": title,
        },
        "raw_result_preview": result.get("stdout", "")[:1200],
        "diagnostics": result.get("diagnostics") or verify.get("diagnostics"),
        "message": create_result_message(result, created_target, verify),
        "next_action": None if result["ok"] and created_target.get("ok") and verify["ok"] else "inspect_docs_create_or_verify_error",
    }, code=0 if result["ok"] and created_target.get("ok") and verify["ok"] else 1)


def preflight_docs_update_overwrite(args):
    target = resolve_target_or_exit(args, "preflight")
    auth = require_auth(args.as_identity)
    info = risk_info("docs_update_overwrite")
    fetch = fetch_doc(target["doc_arg"], args.as_identity, "pretty")
    title = infer_title_from_fetch_output(fetch.get("stdout", ""))
    file_info = prepare_markdown_cli_file(args.markdown)
    ok = fetch["ok"] and file_info["ok"]
    json_exit({
        "ok": ok,
        "stage": "preflight",
        "operation": "docs_update_overwrite",
        "risk": info["risk"],
        "requires_confirmation": True,
        "identity": auth.get("identity"),
        "target": {**target, "title": title, "fetch_verified": fetch["ok"]},
        "local_input": file_info,
        "impact": [
            "目标 Feishu 文档正文将被本地 markdown 完整替换。",
            "原文档内容可能无法通过 lark-cli 自动恢复。",
            "执行后会立即 docs +fetch 校验标题和主要内容。",
        ],
        "confirm_phrase": "确认覆盖该 Feishu 文档",
        "diagnostics": fetch.get("diagnostics"),
        "message": "覆盖更新前置检查通过，等待使用者确认" if ok else "覆盖更新前置检查未通过",
        "next_action": "ask_user_confirmation" if ok else "fix_preflight_blocker",
    }, code=0 if ok else 1)


def execute_docs_update_overwrite(args):
    target = resolve_target_or_exit(args, "execute")
    auth = require_auth(args.as_identity)
    if not args.confirmed:
        json_exit({
            "ok": False,
            "stage": "execute",
            "operation": "docs_update_overwrite",
            "risk": risk_info("docs_update_overwrite")["risk"],
            "requires_confirmation": True,
            "message": "缺少 --confirmed，拒绝执行覆盖更新。",
            "confirm_phrase": "确认覆盖该 Feishu 文档",
            "next_action": "ask_user_confirmation",
        }, code=1)
    file_info = prepare_markdown_cli_file(args.markdown)
    if not file_info["ok"]:
        json_exit({
            "ok": False,
            "stage": "execute",
            "operation": "docs_update_overwrite",
            "local_input": file_info,
            "message": "markdown 文件检查失败，拒绝覆盖更新",
            "next_action": "fix_markdown_file",
        }, code=1)
    update = update_doc_overwrite(target["doc_arg"], file_info, args.as_identity)
    if not update["ok"] and "--command is required" in (update.get("stdout", "") + update.get("stderr", "")):
        update = update_doc_overwrite_v2(target["doc_arg"], file_info, args.as_identity)
    verify = fetch_doc(target["doc_arg"], args.as_identity, "pretty") if update["ok"] else {"ok": False, "stdout": "", "stderr": "update failed"}
    title = infer_title_from_fetch_output(verify.get("stdout", ""))
    json_exit({
        "ok": update["ok"] and verify["ok"],
        "stage": "execute",
        "operation": "docs_update_overwrite",
        "risk": risk_info("docs_update_overwrite")["risk"],
        "identity": auth.get("identity"),
        "target": {**target, "title": title},
        "local_input": file_info,
        "result": {"update_ok": update["ok"], "fetch_verify_ok": verify["ok"], "title": title},
        "diagnostics": update.get("diagnostics") or verify.get("diagnostics"),
        "message": "覆盖更新成功并完成 fetch 验证" if update["ok"] and verify["ok"] else error_message(update, verify.get("stderr") or "覆盖更新或验证失败"),
        "next_action": None if update["ok"] and verify["ok"] else "inspect_update_or_verify_error",
    }, code=0 if update["ok"] and verify["ok"] else 1)


def unsupported(args):
    info = risk_info(args.operation)
    json_exit({
        "ok": False,
        "stage": args.stage,
        "operation": args.operation,
        "risk": info["risk"],
        "requires_confirmation": info.get("requires_confirmation", True),
        "error_type": "unsupported_operation",
        "message": "当前 wrapper 尚不支持该 operation。请先检索 lark-cli help/schema 或官方文档，使用只读命令验证处理方式，完成任务后将稳定流程沉淀回 skill。",
        "next_action": "research_capability_then_iterate_skill",
    }, code=2)


def build_parser():
    parser = argparse.ArgumentParser(description="Safe Feishu document operation wrapper")
    parser.add_argument("stage", choices=["preflight", "execute"])
    parser.add_argument("--operation", required=True)
    parser.add_argument("--target", help="Feishu document/wiki URL, doc_token, or wiki_node_token")
    parser.add_argument("--doc")
    parser.add_argument("--wiki-node")
    parser.add_argument("--title")
    parser.add_argument("--markdown")
    parser.add_argument("--confirmed", action="store_true")
    parser.add_argument("--include-preview", action="store_true")
    parser.add_argument("--include-text", action="store_true")
    parser.add_argument("--max-text-chars", type=int, default=30000)
    add_common_args(parser)
    return parser


def main():
    args = build_parser().parse_args()
    if args.operation not in SUPPORTED_OPERATIONS:
        unsupported(args)

    if args.stage == "preflight" and args.operation == "docs_fetch":
        preflight_docs_fetch(args)
    elif args.stage == "execute" and args.operation == "docs_fetch":
        execute_docs_fetch(args)
    elif args.stage == "preflight" and args.operation == "docs_create":
        if not args.title or not args.markdown:
            json_exit({"ok": False, "message": "缺少 --title 或 --markdown", "next_action": "provide_required_args"}, code=1)
        preflight_docs_create(args)
    elif args.stage == "execute" and args.operation == "docs_create":
        if not args.title or not args.markdown:
            json_exit({"ok": False, "message": "缺少 --title 或 --markdown", "next_action": "provide_required_args"}, code=1)
        execute_docs_create(args)
    elif args.stage == "preflight" and args.operation == "docs_update_overwrite":
        if not args.markdown:
            json_exit({"ok": False, "message": "缺少 --markdown", "next_action": "provide_required_args"}, code=1)
        preflight_docs_update_overwrite(args)
    elif args.stage == "execute" and args.operation == "docs_update_overwrite":
        if not args.markdown:
            json_exit({"ok": False, "message": "缺少 --markdown", "next_action": "provide_required_args"}, code=1)
        execute_docs_update_overwrite(args)


if __name__ == "__main__":
    main()
