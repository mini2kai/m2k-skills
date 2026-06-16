---
name: lark-cli-config
description: Use before any Feishu/Lark document, wiki, sheet, drive, or lark-cli operation. This skill guides lark-cli environment checks, user authorization, scope recovery, safe document fetch/create/update workflows, high-risk operation confirmation, and iterative skill improvement when a requested Feishu capability is not yet supported.
metadata:
  short-description: Step-by-step lark-cli authorization guide
---

# Lark CLI Config

## 触发规则

遇到 Feishu/Lark document、wiki、sheet、drive、base、bitable、权限、授权、`lark-cli` 相关任务时，先使用这个 skill。

当前稳定封装的主链路是 Feishu 文档读写：读取、创建、覆盖更新、写后验证、授权诊断。sheet、base、drive、权限变更等场景会触发本 skill，但如果 wrapper 尚未支持，必须先按“不支持功能时的处理规则”调研并沉淀，不能把未封装能力说成已稳定支持。

典型场景：
- 读取、fetch、创建、更新、覆盖、发布 Feishu document/wiki。
- 处理使用者贴出的完整飞书文档链接、wiki 链接、`doc_token`、`wiki_node_token`。
- 读取或写入 sheet/base/bitable。
- 处理 Feishu 链接、`doc_token`、`wiki_node_token`、`spreadsheet_token`。
- 排查 `lark-cli`、scope、authorization URL、`user token`、`bot identity`、`device login`。
- 其他 skill 准备同步飞书文档前。

## 执行入口

优先使用脚本，避免把执行细节塞入上下文：

- 环境诊断：`python scripts/env_diagnostics.py`
- 授权状态：`python scripts/auth_manager.py status`
- 引导登录：`python scripts/auth_manager.py login --domain docs,wiki,drive`（默认拿到 URL 立即返回，不等待授权完成）
- 登出：`python scripts/auth_manager.py logout`
- 文档操作：`python scripts/doc_ops_wrapper.py preflight|execute --operation <operation> --target <url-or-token> ...`
- 文档快读：`python scripts/doc_ops_wrapper.py execute --operation docs_fetch --target <doc-url> --include-text`
- 表格只读：`python scripts/sheet_ops_wrapper.py preflight|execute --operation sheets_read --target <sheet-url> --include-text`
- 本地自测：`python scripts/self_test.py`

所有脚本输出 JSON。Agent 应读取 JSON 的 `ok`、`stage`、`target`、`diagnostics`、`next_action`、`requires_confirmation`、`requires_user_action`、`risk`、`message` 字段决定下一步。

授权登录是人工参与点：当 `auth_manager.py login` 返回 `stage=auth_login_user_action_required` 或 `requires_user_action=true` 时，必须立即把完整 `verification_url` 和 `user_code` 明确展示给使用者，或用可用浏览器工具打开该 URL，然后暂停等待使用者完成授权。不得在没有展示 URL 的情况下继续后台等待；只有 URL 已展示且使用者要求代等时，才可加 `--wait`。

## 文档读写主链路

所有 Feishu 文档读写按同一条链路执行：

1. `env_diagnostics`：确认 `lark-cli` 或 `npx @larksuite/cli` 可用，记录 runner、路径、版本和阻塞项。
2. `auth_status`：确认 `user` 授权有效，读取 `identity`、`tokenStatus`、`expiresAt`、`expiresInSeconds`。
3. `target_resolve`：通过 `--target` 接收完整 URL、`doc_token` 或 `wiki_node_token`，由脚本归一化目标。
4. `preflight`：读取目标、检查本地 markdown、判断风险和是否需要使用者确认。
5. `execute`：执行读写操作。高风险写入没有明确确认不得执行。
6. `post_verify`：写入后必须 fetch/read 验证，并在 JSON 里返回 `fetch_verify_ok`、`title` 和目标信息。

稳定 operation：

- `docs_fetch`：读取文档。低风险，不需要确认；分析长文档时使用 `--include-text` 输出清洗全文。
- `docs_create`：从本地 UTF-8 markdown 创建文档。创建后必须解析新文档并 fetch 验证。
- `docs_update_overwrite`：用本地 UTF-8 markdown 覆盖目标文档正文。高风险，必须先 preflight，再等待明确确认后 execute `--confirmed`。

## 文档只读快速链路

当使用者只要求读取或分析 Feishu document/docx/wiki 内容时，走低风险快读：

1. 从 URL 直接识别 `doc_token` 或 `wiki_node_token`。
2. 直接执行 `docs +fetch`，不进入覆盖/写入 preflight。
3. 使用 `--include-text` 输出清洗后的 `cleaned_text`，用于完整分析；`--include-preview` 只用于短预览。
4. 只读失败时再进入授权、scope 或目标诊断。

稳定 operation：

- `docs_fetch`：只读读取目标文档，低风险，不需要确认。

## 表格只读快速链路

当使用者提供 Feishu spreadsheet URL 且 URL 中包含 `sheet=` 参数时，优先走快速链路：

1. 从 URL 直接提取 `spreadsheet_token` 和 `sheet_id`。
2. 默认跳过 `sheets +info`，直接执行 `sheets +read`。
3. 默认一次性读取 `A1:AZ500`，不要因为几百行表格拆成多次网络请求。
4. 读取后在本地清洗：删除全空行、全空列，富文本 mention 转普通文本，移除 `_notice`、revision、样式和 merge 噪声。
5. 给大模型总结时优先使用 `cleaned_text`，不要把 CLI 原始 JSON 直接放入上下文。

只有以下情况才调用 `sheets +info`：URL 没有 `sheet=`、使用者要求列出所有 sheet、直接读取失败需要诊断、或明确需要 sheet 标题/行列数。

稳定 operation：

- `sheets_read`：只读读取目标 sheet，低风险，不需要确认。

## 规则导航

按需读取这些 reference，不要默认整篇加载：

- scope 映射：`references/scopes.json`
- 安全规则：`references/security_policy.md`
- Windows 中文上传：`references/windows_encoding_guide.md`
- 常见错误处理：`references/lark_cli_error_map.md`
- 操作风险矩阵：`references/operation_risk_matrix.json`

## 标准流程

1. 运行 `scripts/env_diagnostics.py`，确认 `lark-cli` 可用，并检查 runner、版本、warnings、blocking。
2. 运行 `scripts/auth_manager.py status`，确认 `identity` 和 `tokenStatus`。
3. 如果没有 `user` 授权，运行 `scripts/auth_manager.py login --domain docs,wiki,drive`。该命令默认会在拿到 verification URL 后退出；必须明确告诉使用者打开该 URL、确认 user code、授权指定 Feishu 能力，并停下来等待使用者完成。不要要求输入密码、token 或 cookie。
4. 使用者完成授权后，运行 `scripts/auth_manager.py status` 验证；如使用者明确要求代等，才运行 `scripts/auth_manager.py login --domain docs,wiki,drive --wait`。
5. 读取类操作可用 `doc_ops_wrapper.py execute --operation docs_fetch --target <url-or-token>` 直接执行。
6. 写入、覆盖、移动、删除、权限变更先运行 `doc_ops_wrapper.py preflight`。
7. 如果返回 `requires_confirmation: true`，必须向使用者展示目标、风险、影响和验证方式，等待明确确认后才能执行 `--confirmed`。
8. 写入后必须执行 fetch/read 验证。

## 使用者交互规则

需要使用者接入或确认时，必须明确说明：

- 当前操作：读取、创建、覆盖更新、验证或授权。
- 需要输入：飞书文档链接、`doc_token`、`wiki_node_token`、本地 markdown 文件路径。
- 授权方式：打开 verification URL，确认 user code；不要提供密码、token、cookie。
- 授权 URL：如果脚本返回 `verification_url`，必须原样展示或打开；如果没有返回 URL 或等待超时，必须停下来告诉使用者需要协助授权诊断，不得静默重试或继续等待。
- 风险影响：覆盖、删除、移动、权限类操作必须说明影响范围和可恢复性。
- 验证方式：执行后如何证明成功，例如 fetch 验证、标题、目标 token、内容 preview。

高风险覆盖更新必须展示：目标 title/token/URL、操作类型、影响范围、可恢复性、执行后验证方式、确认短语 `确认覆盖该 Feishu 文档`。

## 不支持功能时的处理规则

当使用者需要的 Feishu 功能当前脚本或 skill 不支持时：

1. 不要直接拒绝，也不要编造能力。
2. 先检索可行处理方式：优先查 `lark-cli <command> --help`、`lark-cli schema ...`、本 skill references、已安装 lark-cli 能力；必要时查询官方文档或公开实现。
3. 先用只读命令或 `--dry-run` 验证方案可行性。
4. 引导使用者完成当前任务；高风险操作仍按安全确认流程执行。
5. 任务完成后，把可复用经验沉淀回本 skill：更新脚本、references 或 `SKILL.md` 导航，并运行 `quick_validate.py`。

## 安全底线

- 命令、参数、scope、JSON 字段、文件名保持英文；说明和引导使用中文。
- 不保存或泄露 `app secret`、`access token`、`refresh token`、cookie、密码。
- 默认优先 `--as user`。
- wrapper 当前只允许 `--as user`，避免 bot/auto 与 user 授权链路混淆。
- delete、move、permission transfer、permission delete、batch write、`docs +update --mode overwrite` 等高风险操作必须先确认。
- 用户只要求查看或读取时，不得升级为写入、覆盖、删除或权限变更。

## 最终反馈

完成后只报告：
- `lark-cli` 可用状态。
- `auth identity`：`user`、`bot` 或 `auto`。
- `tokenStatus` 和 `expiresAt`。
- 已验证的 command 或 operation。
- 高风险操作的确认与验证结果。
- 剩余 blocker 或已沉淀的 skill 优化项。

