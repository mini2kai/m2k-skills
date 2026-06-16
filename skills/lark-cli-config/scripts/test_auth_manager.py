import io
import json
from contextlib import redirect_stdout
from types import SimpleNamespace

import auth_manager


def _run_login(start_result, *, wait=False, complete_result=None):
    original_run_cli = auth_manager.run_cli
    original_check_auth_status = auth_manager.check_auth_status
    calls = []

    def fake_run_cli(args, timeout=60):
        calls.append({"args": args, "timeout": timeout})
        if "--no-wait" in args:
            return start_result
        return complete_result or {"ok": False, "stdout": "", "stderr": "not completed", "diagnostics": None}

    try:
        auth_manager.run_cli = fake_run_cli
        auth_manager.check_auth_status = lambda: {"ok": True, "identity": "user", "tokenStatus": "valid"}
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            try:
                auth_manager.login(SimpleNamespace(domain="docs,wiki,drive", timeout=3, wait=wait))
            except SystemExit as exc:
                code = exc.code
            else:
                code = 0
        return code, _last_json(buffer.getvalue()), calls
    finally:
        auth_manager.run_cli = original_run_cli
        auth_manager.check_auth_status = original_check_auth_status


def _last_json(text):
    decoder = json.JSONDecoder()
    index = 0
    payloads = []
    while index < len(text):
        while index < len(text) and text[index].isspace():
            index += 1
        if index >= len(text):
            break
        payload, offset = decoder.raw_decode(text, index)
        payloads.append(payload)
        index = offset
    return payloads[-1]


def check(name, ok, detail=None):
    return {"name": name, "ok": bool(ok), "detail": detail}


def main():
    checks = []

    start_result = {
        "ok": True,
        "stdout": json.dumps({
            "device_code": "secret-device-code",
            "verification_url": "https://open.feishu.cn/device",
            "user_code": "ABCD-EFGH",
            "expires_in": 600,
        }),
        "stderr": "",
        "diagnostics": None,
    }
    code, payload, calls = _run_login(start_result)
    checks.append(check("login_returns_url_without_waiting", code == 2 and payload.get("stage") == "auth_login_user_action_required", payload))
    checks.append(check("login_does_not_call_device_wait_by_default", len(calls) == 1, calls))
    checks.append(check("login_marks_user_action", payload.get("requires_user_action") is True and payload.get("verification_url"), payload))

    missing_url = {
        "ok": True,
        "stdout": json.dumps({"device_code": "secret-device-code", "user_code": "ABCD-EFGH"}),
        "stderr": "",
        "diagnostics": None,
    }
    code, payload, calls = _run_login(missing_url)
    checks.append(check("missing_url_stops_immediately", code == 1 and payload.get("stage") == "auth_login_url_missing" and len(calls) == 1, payload))

    code, payload, calls = _run_login(start_result, wait=True)
    checks.append(check("wait_mode_is_explicit", code == 1 and len(calls) == 2 and payload.get("stage") == "auth_login_complete", {"payload": payload, "calls": calls}))

    ok = all(item["ok"] for item in checks)
    print(json.dumps({"ok": ok, "stage": "test_auth_manager", "checks": checks}, ensure_ascii=False, indent=2))
    raise SystemExit(0 if ok else 1)


if __name__ == "__main__":
    main()
