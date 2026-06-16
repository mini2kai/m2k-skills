# lark-cli 常见错误处理

## No user logged in

含义：当前没有 user token，只有 bot/tenant identity。

处理：运行 `scripts/auth_manager.py login --domain docs,wiki,drive`。默认返回 `verification_url` 和 `user_code` 后立即停下，必须把 URL/code 明确展示给使用者或打开 URL，等使用者完成授权后再运行 `scripts/auth_manager.py status`。

## need_user_authorization

含义：当前操作需要 user 授权。

处理：启动 device login，展示 `verification_url` 和 `user_code`，等待使用者完成授权后使用 `--as user` 重试。不要在没有展示 URL 的情况下后台等待。

结构化输出：`stage=auth_login_user_action_required`，`requires_user_action=true`，保留 `verification_url`、`user_code`，`next_action=authorize_in_browser`。

## auth login URL missing

含义：`lark-cli auth login --no-wait --json` 返回了 device login 信息，但没有可展示的 `verification_url`；或者 CLI 输出异常导致无法提取 URL。

处理：立即停下来告诉使用者需要协助授权诊断，不要继续等待到超时。展示 stdout/stderr 摘要和下一步，例如检查 `lark-cli auth login --help` 或重新发起 login。

结构化输出：`stage=auth_login_url_missing`，`requires_user_action=true`，`next_action=ask_user_to_help_auth_url_missing`。

## missing scope

含义：当前 token 没有目标 API 所需 scope。

处理：展示 CLI 输出中的 exact scopes；如果 CLI 给出 app authorization URL，要求使用者打开并批准后重试一次。

结构化输出：`error_type=missing_scope`，保留 `missing_scopes` 和 `authorization_url`，`next_action=open_authorization_url` 或 `grant_missing_scopes`。

## auth expired

含义：user token 已过期或验证失败。

处理：运行 `scripts/auth_manager.py login --domain docs,wiki,drive` 重新授权，拿到 URL 后交给使用者并暂停；不要要求使用者提供 token。

结构化输出：`error_type=auth_expired`，`next_action=run_auth_login`。

## permission denied

含义：当前 user 没有目标文档、wiki node 或空间权限。

处理：要求文档所有者给当前用户授权，或让使用者提供有权限的链接/账号后重试。

结构化输出：`error_type=permission_denied`，`next_action=ask_owner_grant_access`。

## target not found

含义：链接、`doc_token`、`wiki_node_token` 无效，或目标资源不存在。

处理：要求使用者提供完整 Feishu 文档链接，或重新复制 token；不要继续写入。

结构化输出：`error_type=target_not_found`，`next_action=check_target_url`。

## network error

含义：连接 Feishu 服务失败、代理异常、超时或 DNS/HTTPS 连接问题。

处理：重试一次；仍失败时让使用者检查网络或代理配置。

结构化输出：`error_type=network_error`，`next_action=retry_or_check_proxy`。

## app authorization URL

含义：应用后台或用户授权缺少权限。

处理：展示完整 URL，等待使用者完成授权；不要自己猜 scope。若没有完整 URL，立即停下来请使用者协助授权诊断。

结构化输出：`error_type=authorization_required`，保留 `authorization_url`，`next_action=open_authorization_url`。

## stale fetch after update

含义：update 后立即 fetch 可能读到旧内容。

处理：串行再 fetch 一次，不要并行 update/fetch。

## proxy warning

含义：代理提示不一定阻塞。

处理：只有在连接失败或凭据异常时才作为 blocker 报告。
