# 2026-06-17 Skill 作用域与协作架构的思考

## 起因

发现全局安装的 skill 会在不相关的项目里被误触发——在别的项目里随便说"帮我 commit 一下"，git-trunk-workflow 就跳出来强制走脚本流程。这不是想要的行为。

## 核心发现：项目级安装比全局安装更重要

Skill 应该装在项目级（`项目/.claude/skills/`），而不是全局（`~/.claude/skills/`）。

- 全局安装 = 所有项目都加载所有 skill，作用域失控
- 项目级安装 = 每个项目只加载自己需要的 skill，按需配置，互不干扰

每个项目就像 `package.json` 一样，只声明自己需要的依赖。

## Skill 的两个层次

**底层通用 skill**（基础能力，被编排层调用）：
- `work-orchestrator` — 总控编排，动态路由
- `git-trunk-workflow` — 安全 git 操作
- `postgres-query` — 只读数据库
- `server-docker-logs-readonly` — 只读日志

**业务个性化 skill**（绑定特定项目/场景）：
- `otb-*` — OTB 业务
- `lark-cli-config` — 接飞书的项目
- `web-demo-publisher` — 需要发布 demo 的项目

## Description 是路由的唯一依据

Claude Code 靠 SKILL.md 的 `description` 决定是否触发，没有代码级的开关。

防止误触的关键：**description 要收窄触发条件，加否定排除句**。

例如 git-trunk-workflow 应该写：
> 仅当用户明确说"走脚本提交"、"用 trunk 流程"，或由 work-orchestrator 编排调用时激活。普通的 git add/commit/push 不应触发本 Skill。

## Skill 协作 vs Multi-Agent

- **多 skill**：一个模型实例，加载多套行为规则，共享上下文，顺序执行
- **多 agent**：多个模型实例，各自独立上下文，可并行，但协调成本高

我的工作流基本是线性的（取证 → 分析 → 方案 → 实施 → 验证），每步依赖上一步结果，适合多 skill 而不是多 agent。work-orchestrator + 多 skill 本质就是 orchestrator-subagent 模式，只不过 subagent 是用自然语言定义的 SKILL.md。

## 脚本失败策略

当前问题：脚本报错时 AI 在循环里反复尝试，消耗大量 token 和时间。

根本原因是 SKILL.md 没有明确定义失败行为，AI 默认"遇到问题多试几次"。

解法：
1. 脚本统一 exit code 语义（0=成功，1=执行失败可重试一次，2=前置条件不满足不要重试）
2. SKILL.md 加失败围栏——脚本非 0 退出立即停下来，输出原因给用户，不得循环尝试

## 下一步

- 清理全局 `~/.claude/skills/`，全部改为项目级安装
- 给各 skill 的 description 加否定条件
- 给有脚本的 skill 加失败处理围栏
