# AI Agent Guardrails

这个目录记录我在真实研发场景中，关于 AI Agent 协作约束的思考和实践。

不是框架文档，不是产品说明。是一个实践者的设计笔记。

## 核心问题

AI Agent 越来越强，但"能做"不等于"应该做"。

当你把数据库连接串、服务器 SSH 权限、Git push 权限交给 AI 时，真正的风险不是它做错——而是它做对了一件你没想让它做的事。

我关注的问题是：**如何让 AI Agent 在清晰的信任边界内稳定工作，既不过度限制、也不失去控制。**

## 核心主张

详见 [principles.md](./principles.md)

1. 默认只读，写操作需要显式授权
2. 高风险操作不是禁止，是加确认门槛
3. AI 应该先证明它理解了问题，再被允许动手
4. 安全规则跟着任务走，不是全局开关
5. 凭据和本地状态永远不进 AI 的持久上下文

## 实践案例

这些原则不是空想出来的。同目录下的 `skills/` 是它们的实现，每个 skill 都是一个具体的约束方案：

| 原则 | 对应实践 |
|---|---|
| 默认只读（MCP 优先 + 本地脚本） | [postgres-query](../skills/postgres-query/) — 仍在使用；日常查库建议优先配置数据库 MCP，本地脚本保留只读围栏和审计 |
| 确认门槛 | [git-trunk-workflow](../skills/git-trunk-workflow/) — 本地 Git 写操作强制隔离 worktree，commit/push 前必须确认；GitHub/GitLab/Gitee 平台对象优先 MCP |
| AI 交付记忆 | [ai-delivery-hook](../skills/ai-delivery-hook/) — 只读检索历史留存、`.worker_author_story/` 和接手前的人工提交；从 hook 强制收缩为上下文能力 |
| 先理解再动手 | [work-orchestrator](../skills/work-orchestrator/) — 阶段门强制先分析后实施，并在触发时维护项目级 Worker Author Story 交付故事日志 |
| 规则跟着任务走 | [server-docker-logs-readonly](../skills/server-docker-logs-readonly/) — 白名单脚本，不给通用 SSH |
| 凭据不持久化 | 数据库 MCP / [postgres-query](../skills/postgres-query/) — MCP DSN 和平台 token 不进仓库；本地 profile 用环境变量存密码 |

备注：`postgres-query` 仍然是围栏模型的早期代表案例，也仍在使用；新的推荐是先配置数据库 MCP，再按需使用本地受控脚本。GitHub/GitLab/Gitee 这类托管平台对象同理优先 MCP，本地 Git 写操作仍保留脚本围栏。

## 文章

| # | 标题 | 位置 |
|---|---|---|
| 01 | [postgres-query：用代码围栏替代提示词祈祷](../skills/postgres-query/DESIGN.md) | 仍在使用；MCP 优先配置 |
| 02 | (待写) | 信任边界 vs 能力边界：AI Agent 安全的真正问题 |
| 03 | [MCP 作用域与 Git 托管平台分层设计](./thoughts/2026-07-14-mcp-scope-and-git-hosting-design.md) | 数据库/Git MCP 与本地围栏取舍 |
| 04 | [元 Prompt 动态 Skill 与静态围栏的取舍](./thoughts/2026-08-04-meta-prompt-dynamic-skill-design.md) | 动态能力发现与代码围栏的混合架构 |
| 05 | [ai-delivery-hook 从强制围栏收缩为只读能力](./thoughts/2026-08-04-ai-delivery-hook-descope.md) | 未被激活的围栏、并发下的全局状态、围栏该守什么 |
| 06 | [Worker Author Story 交付故事日志设计](./thoughts/2026-08-05-worker-author-story-delivery-log.md) | 项目级交付日志：索引、分支 CSV、按月详细故事 |

## 探讨

| 分类 | 位置 |
|---|---|
| 进行中的问题讨论 | [discussions/README_cn.md](./discussions/README_cn.md) |

## 关于我

在中文研发团队里用 AI Agent 做日常交付。不是在做一个开源框架——是在一线实践中摸索 AI 协作的可控边界，并把可复用的部分沉淀下来。

这个仓库既是我的工具箱，也是我的实验室。
