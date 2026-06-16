import argparse
import json

from common import check_auth_status, json_exit, parse_json_text, run_cli


def status(_args):
    auth = check_auth_status()
    json_exit({
        "ok": auth["ok"],
        "stage": "auth_status",
        "requiredIdentity": auth.get("requiredIdentity"),
        "identity": auth.get("identity"),
        "tokenStatus": auth.get("tokenStatus"),
        "expiresAt": auth.get("expiresAt"),
        "expiresInSeconds": auth.get("expiresInSeconds"),
        "userName": auth.get("userName"),
        "message": auth.get("message"),
        "diagnostics": auth.get("diagnostics"),
        "next_action": None if auth["ok"] else "run_auth_login",
    }, code=0)


def login(args):
    start = run_cli(["auth", "login", "--domain", args.domain, "--no-wait", "--json"], timeout=60)
    data = parse_json_text(start.get("stdout", ""))
    if not start["ok"] or not isinstance(data, dict) or not data.get("device_code"):
        json_exit({
            "ok": False,
            "stage": "auth_login_start",
            "message": start.get("stderr") or start.get("stdout") or "无法发起 device login",
            "requires_user_action": True,
            "operator_instruction": "没有拿到 verification URL。不要继续等待；把该错误明确告诉使用者，并请使用者协助检查 lark-cli auth login 输出。",
            "diagnostics": start.get("diagnostics"),
            "next_action": "inspect_lark_cli_auth_help",
        }, code=1)

    prompt = {
        "ok": False,
        "stage": "auth_login_user_action_required",
        "verification_url": data.get("verification_url"),
        "user_code": data.get("user_code"),
        "expires_in": data.get("expires_in"),
        "requires_user_action": True,
        "message": "请打开 verification_url，确认 user_code，并授权 lark-cli 访问指定 Feishu 能力；脚本不会要求你输入密码、token 或 cookie。",
        "operator_instruction": "必须把 verification_url 和 user_code 明确展示给使用者，或用可用浏览器工具打开该 URL，然后暂停等待使用者完成授权。不要在后台静默等待到超时。",
        "domains": args.domain,
        "next_action": "authorize_in_browser",
    }

    if not prompt.get("verification_url"):
        prompt.update({
            "stage": "auth_login_url_missing",
            "message": "lark-cli 返回了 device_code，但没有返回 verification_url。需要使用者协助授权诊断。",
            "next_action": "ask_user_to_help_auth_url_missing",
        })
        json_exit(prompt, code=1)

    if not args.wait:
        json_exit(prompt, code=2)

    print(json.dumps(prompt, ensure_ascii=False, indent=2), flush=True)

    complete = run_cli(["auth", "login", "--device-code", data["device_code"]], timeout=args.timeout)
    if not complete["ok"]:
        json_exit({
            "ok": False,
            "stage": "auth_login_complete",
            "message": complete.get("stderr") or complete.get("stdout") or "device login 未完成",
            "requires_user_action": True,
            "operator_instruction": "等待授权未完成。必须明确告知使用者：如果已经授权，先运行 status 验证；如果还没授权，重新运行 login 获取并展示新的 verification_url。",
            "diagnostics": complete.get("diagnostics"),
            "next_action": "ask_user_to_finish_authorization_then_check_status",
        }, code=1)

    auth = check_auth_status()
    json_exit({
        "ok": auth["ok"],
        "stage": "auth_login_verified",
        "requiredIdentity": auth.get("requiredIdentity"),
        "identity": auth.get("identity"),
        "tokenStatus": auth.get("tokenStatus"),
        "expiresAt": auth.get("expiresAt"),
        "expiresInSeconds": auth.get("expiresInSeconds"),
        "userName": auth.get("userName"),
        "message": "登录成功并验证通过" if auth["ok"] else "登录完成但验证未通过",
        "diagnostics": auth.get("diagnostics"),
        "next_action": None if auth["ok"] else "inspect_auth_status",
    }, code=0 if auth["ok"] else 1)


def logout(_args):
    result = run_cli(["auth", "logout"], timeout=60)
    auth = check_auth_status()
    json_exit({
        "ok": result["ok"] and not auth["ok"],
        "stage": "auth_logout",
        "message": "已退出 user 授权" if result["ok"] else (result.get("stderr") or result.get("stdout")),
        "identity_after": auth.get("identity"),
        "next_action": "run_auth_login" if result["ok"] else "inspect_logout_error",
    }, code=0 if result["ok"] else 1)


def main():
    parser = argparse.ArgumentParser(description="Manage lark-cli user authorization")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("status")

    login_parser = sub.add_parser("login")
    login_parser.add_argument("--domain", default="docs,wiki,drive")
    login_parser.add_argument("--timeout", type=int, default=650)
    login_parser.add_argument("--wait", action="store_true", help="Wait for device authorization after the URL has already been shown to the user")

    sub.add_parser("logout")

    args = parser.parse_args()
    if args.command == "status":
        status(args)
    elif args.command == "login":
        login(args)
    elif args.command == "logout":
        logout(args)


if __name__ == "__main__":
    main()
