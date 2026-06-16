# M2K Skills

[中文版](./README_cn.md)

[![GitHub stars](https://img.shields.io/github/stars/mini2kai/m2k-skills?style=social)](https://github.com/mini2kai/m2k-skills/stargazers)
[![GitHub forks](https://img.shields.io/github/forks/mini2kai/m2k-skills?style=social)](https://github.com/mini2kai/m2k-skills/forks)
[![GitHub issues](https://img.shields.io/github/issues/mini2kai/m2k-skills)](https://github.com/mini2kai/m2k-skills/issues)
[![Skills](https://img.shields.io/badge/skills-8-success)](#skill-catalog)
[![Manager](https://img.shields.io/badge/manager-m2k--skills--tools-00A6D6)](#installation)
[![License](https://img.shields.io/badge/license-Non--Commercial-lightgrey)](#license)

A collection of reusable, auditable AI Agent skills with code-enforced safety boundaries.

## What Is This

M2K Skills is the product of practicing safe AI Agent collaboration in real-world development scenarios. Each skill defines safety boundaries that AI cannot cross (fences), enforced by code — not prompt suggestions, but `raise`/`exit`/hard limits. Inside the fence, the model has full autonomy.

This repository is both a daily toolbox and a methodology laboratory.

## Design Philosophy

> **Code-enforced boundaries, not prompt-based suggestions.**

See [docs/](./docs/) for core principles, methodology, and practice cases.

Core assertions:

1. Read-only by default; write operations require explicit authorization
2. High-risk operations are not banned — they require confirmation gates
3. AI should prove it understands the problem before being allowed to act
4. Safety rules travel with the task, not as global switches
5. Credentials and local state never enter AI's persistent context

Each skill's design rationale is documented in its own `DESIGN.md`.

## Skill Catalog

| Skill | Description | Safety Boundary |
|---|---|---|
| `postgres-query` | PostgreSQL read-only queries, schema inspection, query plan analysis | SQL whitelist check, dangerous keyword interception, row/timeout hard limits, credential redaction, audit log |
| `server-docker-logs-readonly` | Server log read-only inspection | Allowlist scripts restrict paths; direct SSH/Docker commands forbidden |
| `git-trunk-workflow` | AI short-lived Git branch delivery | Force push/reset hard/branch deletion forbidden; commit/push requires confirmation |
| `work-orchestrator` | Full-chain orchestration | Phase gates enforce analysis before execution; no modification without authorization |
| `ai-worklog` | AI collaboration daily report and timesheet | Preview before generation; no sensitive credentials in output |
| `lark-cli-config` | Feishu/Lark CLI authorization and document operations | Auth URLs must be shown or opened explicitly; high-risk writes require confirmation |
| `web-demo-publisher` | Web demo generation, preview, and publishing | Fixed port publishing; external network failure doesn't block local preview |
| `skill-dev` | Skill development, validation, and publishing workflow | Fence model development standard; commit/push/PyPI requires confirmation |

## Installation

See [INSTALLATION.md](./INSTALLATION.md) for the full guide.

Quick start:

```powershell
# TUI manager (recommended)
uvx --from m2k-skills-tools m2k-skills-tools

# Or single PowerShell command
cd $HOME\.codex\skills
irm https://raw.githubusercontent.com/mini2kai/m2k-skills/main/scripts/install.ps1 | iex; Install-CodexSkill postgres-query
```

## Repository Structure

```text
m2k-skills/
├── skills/              # Independent skills (SKILL.md + DESIGN.md + scripts/ + references/)
├── docs/                # Design philosophy, core principles, practice articles
├── packages/            # m2k-skills-tools (Python TUI manager)
├── scripts/             # PowerShell installer
├── manifest.json        # Skill metadata, versions, and dependencies
├── INSTALLATION.md      # Full installation and usage guide
└── README.md
```

## Security Model

| Layer | Mechanism |
|---|---|
| SQL Safety | Whitelist/blacklist checks, literal masking, multi-statement rejection (`sql_guard.py`) |
| Credential Protection | `redact()` masking, `passwordEnv` env var references, never persisted to disk |
| Operation Control | Read-only default, risky operations generate-only (not executed), commit/push requires confirmation |
| Audit | Operations and interceptions automatically logged to `*.local.jsonl` |
| Data Isolation | `*.local.json`/`*.local.jsonl` excluded from Git |

## Contributing

This repository follows the fence model for development. When creating or optimizing a skill:

1. Identify the fence (what code enforces) and the free zone (what the model decides)
2. Fence logic in independent modules, zero external dependencies, must have tests
3. SKILL.md contains only fence rules + script entry points (40-60 lines)
4. DESIGN.md documents design rationale (for humans)

See `skills/skill-dev/references/design_philosophy.md` for details.

## License

Non-commercial license: personal learning, self-use, and internal non-commercial organizational use permitted. Unauthorized commercial use, resale, or paid distribution prohibited.

For commercial licensing, contact the repository author for written authorization. Full terms in [LICENSE](./LICENSE).
