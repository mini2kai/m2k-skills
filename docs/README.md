# AI Agent Guardrails

[中文版](./README_cn.md)

Design notes on AI Agent collaboration constraints, from real-world practice.

Not a framework. Not a product. A practitioner's design journal.

## The Problem

AI Agents are increasingly capable, but "can do" does not mean "should do."

When you hand an AI a database connection string, SSH access, or Git push permission, the real risk isn't that it makes a mistake — it's that it correctly executes something you never intended.

The question I'm working on: **How to let AI Agents work stably within clear trust boundaries — neither over-restricted nor out of control.**

## Core Assertions

See [principles.md](./principles.md) / [principles_cn.md](./principles_cn.md)

1. Read-only by default; write operations require explicit authorization
2. High-risk operations are not banned — they require confirmation gates
3. AI should prove it understands the problem before being allowed to act
4. Safety rules travel with the task, not as global switches
5. Credentials and local state never enter AI's persistent context

## Practice Cases

These principles are not theoretical. The `skills/` directory contains their implementations — each skill is a concrete constraint solution:

| Principle | Implementation |
|---|---|
| Read-only default (MCP first + local scripts) | [postgres-query](../skills/postgres-query/) — still in use; configure database MCP first for daily access, keep local scripts for read-only fences and audit |
| Confirmation gates | [git-trunk-workflow](../skills/git-trunk-workflow/) — local commit/push requires confirmation; GitHub/GitLab/Gitee platform objects prefer MCP |
| AI delivery memory | [ai-delivery-hook](../skills/ai-delivery-hook/) — active AI sessions require repo-local delivery records while human commits remain unblocked |
| Understand before acting | [work-orchestrator](../skills/work-orchestrator/) — phase gates enforce analysis before execution and route code tasks into AI delivery retention |
| Rules follow the task | [server-docker-logs-readonly](../skills/server-docker-logs-readonly/) — allowlist scripts, no general SSH |
| Credentials don't persist | Database MCP / [postgres-query](../skills/postgres-query/) — MCP DSNs and platform tokens stay out of Git; local profiles use env vars for passwords |

Note: `postgres-query` remains an early representative fence-model case and is still in use; the updated recommendation is to configure database MCP first, then use local guarded scripts when needed. GitHub/GitLab/Gitee hosting-platform objects follow the same MCP-first idea, while local Git writes keep script fences.

## Articles

| # | Title | Location |
|---|---|---|
| 01 | [postgres-query: Code fences over prompt prayers](../skills/postgres-query/DESIGN.md) | Still used; MCP-first configuration |
| 02 | (planned) | Trust boundaries vs capability boundaries |
| 03 | [MCP scope and Git hosting platform layering](./thoughts/2026-07-14-mcp-scope-and-git-hosting-design.md) | Database/Git MCP and local fence trade-offs |
| 04 | (planned) | How "analyze first, don't modify" changes AI collaboration quality |

## Discussions

| Category | Location |
|---|---|
| Open questions under discussion | [discussions/README.md](./discussions/README.md) |

## About

Building AI Agent workflows in Chinese development teams. Not creating an open-source framework — exploring controllable boundaries for AI collaboration through hands-on practice, and distilling the reusable parts.

This repository is both my toolbox and my laboratory.
