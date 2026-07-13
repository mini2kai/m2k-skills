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
| Read-only default (historical/local fallback) | [postgres-query](../skills/postgres-query/) — low priority; prefer database MCP for daily database access, keep scripts as a no-MCP read-only fallback |
| Confirmation gates | [git-trunk-workflow](../skills/git-trunk-workflow/) — commit/push requires confirmation |
| Understand before acting | [work-orchestrator](../skills/work-orchestrator/) — phase gates enforce analysis before execution |
| Rules follow the task | [server-docker-logs-readonly](../skills/server-docker-logs-readonly/) — allowlist scripts, no general SSH |
| Credentials don't persist (historical/local fallback) | [postgres-query](../skills/postgres-query/) — temporary connections discarded after use; reference only when not using MCP |

Note: `postgres-query` remains an early representative fence-model case, but since 2026-07-13 it is no longer the primary direction for database access; future database work should prefer database MCP.

## Articles

| # | Title | Location |
|---|---|---|
| 01 | [postgres-query: Code fences over prompt prayers](../skills/postgres-query/DESIGN.md) | Historical case; low-priority maintenance |
| 02 | (planned) | Trust boundaries vs capability boundaries |
| 03 | (planned) | How "analyze first, don't modify" changes AI collaboration quality |

## About

Building AI Agent workflows in Chinese development teams. Not creating an open-source framework — exploring controllable boundaries for AI collaboration through hands-on practice, and distilling the reusable parts.

This repository is both my toolbox and my laboratory.
