# 探讨

这个目录记录还没有形成最终设计结论的问题讨论。格式按时间戳排列：先记录问题、观察和阶段性判断，后续再沉淀到 `thoughts/`、skill 设计文档或安装文档中。

## 2026-07-14 14:10:19 +0800｜通用 Git 版本管理 MCP 是否可以平替本地 Git skill？

### 背景

数据库访问从本地 `postgres-query` 转向数据库 MCP 后，实际体验明显变好：连接更直接，查询效率和交互体验更顺手，虽然会缺少一部分本地脚本能力（例如本地日志留存、脚本级审计和硬围栏），但这种取舍在日常使用中是合理的。

因此需要继续探讨：版本管理能力是否也能像数据库一样，改为 MCP 优先，甚至由通用 Git 版本管理 MCP 平替当前的 `git-trunk-workflow`。

### 当前问题

1. 是否可以把现有版本管理 skill 优化成 MCP？
   - 调查市面上是否已有成熟的 Git / GitHub / GitLab / Gitee MCP。
   - 判断哪些能力可以直接接入：本地 Git、远端 issue、PR/MR、review、CI、release 等。
   - 判断哪些能力不适合直接平替：保护分支、显式暂存、禁止 force push、审计留痕等。

2. 如何在 Code / Codex / Claude 上做通用设置？
   - 尽量避免每个客户端、每个项目都用不同方式重复配置。
   - 区分用户级配置和项目级配置。
   - 明确 token、DSN、私有 base URL 等敏感信息放在哪里。

### 阶段性判断

- 数据库 MCP 已经证明：当 MCP server 的能力边界清晰、协议稳定、操作以只读为主时，MCP 可以显著优于本地 skill 脚本。
- Git 需要拆开看：
  - GitHub/GitLab/Gitee 平台对象更像数据库 MCP，可以优先 MCP 化。
  - 本地 `branch/stage/commit/push` 是写仓库状态的高风险动作，是否能完全交给通用 Git MCP，需要重点验证 MCP 是否具备可配置围栏、审计和保护分支策略。
- 当前不急于把 `git-trunk-workflow` 标记为低优先级；更合理的路径是先做 MCP 调研和能力矩阵，再决定是否调整 skill 定位。

### 待调研

- 通用本地 Git MCP 的成熟度、维护状态、权限边界和风险。
- GitHub 官方/社区 MCP 的能力范围。
- GitLab 官方/社区 MCP 的能力范围。
- Gitee 是否有可用 MCP，或是否只能通过 API / CLI 间接接入。
- Claude Code、Codex、ZCode 的 MCP 配置格式差异，以及能否形成统一模板。

## 2026-07-14 14:22:26 +0800｜初步调研：Git 平台对象适合 MCP，本地 Git 写操作不宜立即平替

### 调研来源

- GitHub 官方 MCP Server：`https://github.com/github/github-mcp-server`
- MCP reference/community servers：`https://github.com/modelcontextprotocol/servers`
- Python 本地 Git MCP：`https://pypi.org/project/mcp-server-git/`
- MCP Git reference server：`https://github.com/modelcontextprotocol/servers/tree/main/src/git`
- Gitee MCP Server：`https://gitee.com/oschina/mcp-gitee`
- GitLab 旧参考实现：`https://github.com/modelcontextprotocol/servers-archived/tree/main/src/gitlab`
- GitLab 社区成熟方案：`https://github.com/zereight/gitlab-mcp`
- Claude Code MCP 配置文档：`https://code.claude.com/docs/en/mcp`
- Codex 配置参考入口：`https://developers.openai.com/codex/config-reference`

GitLab 旧参考实现已归档，不建议新项目采用；社区方案里 `zereight/gitlab-mcp` 功能面较广，但不是 GitLab 官方承诺，必须按 readonly、tool allowlist、token scope 保守启用。

### 能力矩阵

| 能力 | 已看到的 MCP 方案 | 初步判断 |
|---|---|---|
| GitHub issue / PR / review / actions / release | GitHub 官方 MCP Server | 成熟度较高，适合 MCP 优先 |
| Gitee issue / PR / release / repo 对象 | `oschina/mcp-gitee`，并提供 remote MCP | 可作为 Gitee 平台对象 MCP 候选 |
| GitLab issue / MR / pipeline | 待继续核验官方或主流 MCP | 暂不写死，后续补充 |
| 本地 `status/diff/log/branch/checkout/add/commit` | `mcp-server-git` / MCP Git reference server | 可用，但偏 beta/示例性质 |
| 本地 `push` | 本次看到的 Git reference 工具未明确包含 push | 不足以替代完整交付流程 |
| 保护分支、防 force push、显式暂存白名单、commit 前缀校验、审计 | 通用 Git MCP 未看到内建策略 | 不适合直接平替 `git-trunk-workflow` |

### 初步结论

版本管理不能简单类比数据库 MCP。数据库访问大多是只读查询，MCP server 的边界清晰；Git 本地写操作会直接改变仓库状态，风险集中在暂存范围、分支保护、commit 质量、push 行为和审计留痕。

更稳妥的路线是：

1. GitHub/GitLab/Gitee 平台对象优先 MCP。
2. 本地 Git 只读能力可以考虑 MCP 化，例如 status、diff、log、show。
3. 本地 Git 写操作暂时继续走 `git-trunk-workflow`。
4. 如果未来要平替，需要先找到或自建带策略层的 Git MCP，而不是直接接入通用 Git MCP：
   - 保护分支 denylist；
   - 禁止 force push；
   - 显式路径暂存；
   - commit message 前缀校验；
   - push 前确认；
   - JSON 审计日志；
   - 脚本/MCP 失败后禁止原生命令兜底。

### 通用配置方向

不同客户端的 MCP JSON 结构会有差异，但可以形成统一原则：

- 项目级配置只放无密模板、server 名称、用途说明和团队约定。
- 用户级配置放真实 token、DSN、私有 base URL。
- GitHub/GitLab/Gitee token 不进仓库。
- 数据库 DSN 不进仓库。
- 对支持 toolsets/read-only/disabled tools 的 MCP，默认收窄工具范围。
- 高风险动作（merge、release、删分支、push、写文件）即使由 MCP 执行，也要保留用户确认。

因此，当前不建议把 `git-trunk-workflow` 改成“低优先级”。建议下一步是新增一份 MCP 配置模板和能力矩阵，把平台对象先 MCP 化，把本地 Git 写操作继续留在受控 skill 中。
