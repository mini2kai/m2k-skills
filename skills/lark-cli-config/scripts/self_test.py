from common import (
    _extract_identity_status,
    classify_cli_error,
    clean_sheet_values,
    extract_created_doc_reference,
    json_exit,
    normalize_document_target,
    normalize_sheet_target,
    prepare_markdown_cli_file,
)


def check(name, ok, detail=None):
    return {"name": name, "ok": bool(ok), "detail": detail}


def main():
    checks = []

    doc_url = normalize_document_target("https://example.feishu.cn/docx/ABCDEF154326")
    checks.append(check("doc_url_resolves", doc_url.get("ok") and doc_url.get("doc") == "ABCDEF154326", doc_url))

    wiki_url = normalize_document_target("https://example.feishu.cn/wiki/WIKINODE123")
    checks.append(check("wiki_url_resolves", wiki_url.get("ok") and wiki_url.get("wiki_node") == "WIKINODE123", wiki_url))

    bad_url = normalize_document_target("https://example.com/docx/ABCDEF154326")
    checks.append(check("foreign_url_rejected", not bad_url.get("ok") and bad_url.get("next_action") == "provide_feishu_doc_url_or_token", bad_url))

    missing_scope = classify_cli_error("", "missing scope docs:document.content:read https://open.feishu.cn/app/auth")
    checks.append(check("missing_scope_classified", missing_scope.get("error_type") == "missing_scope", missing_scope))

    auth_missing = classify_cli_error("No user logged in", "")
    checks.append(check("auth_missing_classified", auth_missing.get("next_action") == "run_auth_login", auth_missing))

    nested_auth = _extract_identity_status({
        "identity": "user",
        "verified": True,
        "identities": {
            "user": {
                "available": True,
                "verified": True,
                "tokenStatus": "valid",
                "expiresAt": "2026-06-16T16:54:14+08:00",
                "userName": "测试用户",
            }
        },
    }, "user")
    checks.append(check("nested_auth_schema_supported", nested_auth.get("tokenStatus") == "valid" and nested_auth.get("userName") == "测试用户", nested_auth))

    created = extract_created_doc_reference('{"url":"https://example.feishu.cn/docx/CREATEDTOKEN"}')
    checks.append(check("created_doc_reference_extracted", created.get("ok") and created.get("doc") == "CREATEDTOKEN", created))

    sheet_url = normalize_sheet_target("https://example.feishu.cn/sheets/SHEETTOKEN123?sheet=abcDEF")
    checks.append(check("sheet_url_resolves", sheet_url.get("ok") and sheet_url.get("spreadsheet_token") == "SHEETTOKEN123" and sheet_url.get("sheet_id") == "abcDEF", sheet_url))

    sheet_missing_id = normalize_sheet_target("https://example.feishu.cn/sheets/SHEETTOKEN123")
    checks.append(check("sheet_missing_id_requires_fallback", not sheet_missing_id.get("ok") and sheet_missing_id.get("next_action") == "provide_sheet_id_or_allow_info_fallback", sheet_missing_id))

    cleaned = clean_sheet_values([
        [None, "", None],
        ["页面名称", [{"text": "投产明细", "type": "text"}], None],
        [None, None, None],
        ["按钮", "提交", "导出"],
    ])
    checks.append(check("sheet_values_cleaned", cleaned["row_count"] == 2 and cleaned["column_count"] == 3 and "投产明细" in cleaned["text"], cleaned))

    markdown_file = prepare_markdown_cli_file(__file__)
    checks.append(check("markdown_cli_file_uses_relative_at_file", markdown_file.get("cli_markdown_arg") == "@self_test.py" and markdown_file.get("cli_cwd"), markdown_file))

    ok = all(item["ok"] for item in checks)
    json_exit({
        "ok": ok,
        "stage": "self_test",
        "checks": checks,
        "message": "lark-cli-config 本地自测通过" if ok else "lark-cli-config 本地自测失败",
        "next_action": None if ok else "inspect_failed_checks",
    }, code=0 if ok else 1)


if __name__ == "__main__":
    main()
