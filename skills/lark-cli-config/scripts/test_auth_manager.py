import io
import json
import tempfile
from contextlib import redirect_stdout
from pathlib import Path
from types import SimpleNamespace

import auth_manager


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


def _run_with_patches(func, args, fake_run_cli, fake_auth=None):
    original_run_cli = auth_manager.run_cli
    original_check_auth_status = auth_manager.check_auth_status
    original_state_file = auth_manager.AUTH_STATE_FILE
    calls = []

    def wrapped_run_cli(cli_args, timeout=60):
        calls.append({"args": cli_args, "timeout": timeout})
        return fake_run_cli(cli_args, timeout)

    with tempfile.TemporaryDirectory() as tmp:
        try:
            auth_manager.AUTH_STATE_FILE = Path(tmp) / ".lark-auth-device.json"
            auth_manager.run_cli = wrapped_run_cli
            auth_manager.check_auth_status = fake_auth or (lambda: {"ok": True, "identity": "user", "tokenStatus": "valid"})
            buffer = io.StringIO()
            with redirect_stdout(buffer):
                try:
                    func(args)
                except SystemExit as exc:
                    code = exc.code
                else:
                    code = 0
            state_exists = auth_manager.AUTH_STATE_FILE.exists()
            state = json.loads(auth_manager.AUTH_STATE_FILE.read_text(encoding="utf-8")) if state_exists else None
            return code, _last_json(buffer.getvalue()), calls, state
        finally:
            auth_manager.run_cli = original_run_cli
            auth_manager.check_auth_status = original_check_auth_status
            auth_manager.AUTH_STATE_FILE = original_state_file


def _run_login(start_result, *, wait=False, complete_result=None):
    def fake_run_cli(args, _timeout=60):
        if "--no-wait" in args:
            return start_result
        return complete_result or {"ok": False, "stdout": "", "stderr": "not completed", "diagnostics": None}

    return _run_with_patches(
        auth_manager.login,
        SimpleNamespace(domain="docs,wiki,drive", timeout=3, wait=wait),
        fake_run_cli,
    )


def _run_complete(state, *, complete_result=None, auth=None):
    def fake_run_cli(args, _timeout=60):
        if "--device-code" in args:
            return complete_result or {"ok": True, "stdout": "OK", "stderr": "", "diagnostics": None}
        return {"ok": False, "stdout": "", "stderr": "unexpected", "diagnostics": None}

    def setup_and_complete(args):
        auth_manager.AUTH_STATE_FILE.write_text(json.dumps(state, ensure_ascii=False), encoding="utf-8")
        return auth_manager.complete(args)

    return _run_with_patches(
        setup_and_complete,
        SimpleNamespace(timeout=3),
        fake_run_cli,
        fake_auth=auth or (lambda: {"ok": True, "identity": "user", "tokenStatus": "valid", "userName": "测试用户"}),
    )


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
    code, payload, calls, state = _run_login(start_result)
    checks.append(check("login_returns_url_without_waiting", code == 2 and payload.get("stage") == "auth_login_user_action_required", payload))
    checks.append(check("login_does_not_call_device_wait_by_default", len(calls) == 1, calls))
    checks.append(check("login_marks_user_action", payload.get("requires_user_action") is True and payload.get("verification_url"), payload))
    checks.append(check("login_saves_resumable_device_state", state and state.get("device_code") == "secret-device-code", state))

    missing_url = {
        "ok": True,
        "stdout": json.dumps({"device_code": "secret-device-code", "user_code": "ABCD-EFGH"}),
        "stderr": "",
        "diagnostics": None,
    }
    code, payload, calls, _state = _run_login(missing_url)
    checks.append(check("missing_url_stops_immediately", code == 1 and payload.get("stage") == "auth_login_url_missing" and len(calls) == 1, payload))

    code, payload, calls, _state = _run_login(start_result, wait=True)
    checks.append(check("wait_mode_is_explicit", code == 1 and len(calls) == 2 and payload.get("stage") == "auth_login_complete", {"payload": payload, "calls": calls}))

    code, payload, calls, state_after = _run_complete({
        "device_code": "secret-device-code",
        "verification_url": "https://open.feishu.cn/device",
        "user_code": "ABCD-EFGH",
        "expires_at": 4102444800,
    })
    checks.append(check("complete_uses_saved_device_code", code == 0 and calls and calls[0]["args"][-1] == "secret-device-code", {"payload": payload, "calls": calls}))
    checks.append(check("complete_clears_state_after_success", state_after is None, state_after))

    ok = all(item["ok"] for item in checks)
    print(json.dumps({"ok": ok, "stage": "test_auth_manager", "checks": checks}, ensure_ascii=False, indent=2))
    raise SystemExit(0 if ok else 1)


if __name__ == "__main__":
    main()
