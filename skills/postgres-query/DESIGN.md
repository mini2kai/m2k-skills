# postgres-query: Code Fences Over Prompt Prayers

[中文版](./DESIGN_cn.md)

## Maintenance Status (2026-07-13)

This skill is now on hold and marked **low priority**. Day-to-day database access should prefer the database MCP available in the client: MCP can already replace, and often improve on, local profile + Python script workflows for read-only queries, schema inspection, and result retrieval.

`postgres-query` remains useful as a historical fence-model case study and as a local fallback when no database MCP is available. Its durable value is still `sql_guard.py`, row/timeout hard caps, credential redaction, and audit logging — but it is no longer the default direction for database access.

## Problem

When an AI Agent queries a database, the risk isn't that it writes wrong SQL — it's that it executes SQL you never intended.

The traditional approach is writing "do not execute DELETE" in the system prompt. But that's a prompt constraint — the model can ignore it, forget it, or be injection-bypassed. You're essentially praying the model follows the rule.

## Design Philosophy

**Don't rely on AI self-discipline. Rely on code enforcement.**

All SQL must pass through a Python module (`sql_guard.py`) before reaching the database. This module doesn't care who's calling it, why, or in what context — it does one thing: is this SQL read-only? If not, `raise ValueError`. Physically impossible to execute.

Inside the fence (what SQL to write, how to explain results, how to talk to users), AI has complete freedom. I don't teach AI how to walk; I only manage the fence's height and position.

## Implementation

### 1. SQL Read-Only Assertion

The core is `assert_read_only()` in `sql_guard.py`:

```
Raw SQL
  → Normalize (strip whitespace, trailing semicolons)
  → Mask literals and comments (DELETE inside a string won't trigger false positive)
  → Reject multi-statements (semicolons after masking = rejected)
  → First keyword whitelist (only SELECT/WITH/SHOW/EXPLAIN allowed)
  → Full-text blacklist scan (18 dangerous keywords)
  → Extra EXPLAIN ANALYZE block
```

Key design: mask first, then check. `SELECT 'DELETE FROM users'` is safe because DELETE is inside a string. The masking function replaces all single-quote, double-quote, dollar-quote, line comment, and block comment content with equal-length spaces, then checks only bare tokens.

### 2. Hard Limits

```python
MAX_ROWS = 1000     # Maximum rows per query
MAX_TIMEOUT = 120   # Seconds
```

Even if AI passes `--limit 99999`, the limit is clamped to 1000. `pg_query.py` no longer rewrites user SQL as `SELECT * FROM (...) LIMIT N`; it executes the original read-only SQL and truncates output with `fetchmany(limit + 1)`, avoiding Greenplum compatibility issues around wrapped system catalog queries. Even if AI passes `--timeout 9999`, `clamp_timeout()` clamps to 120. Callers cannot breach the output ceiling.

### 3. Credentials Never Persist

- Temporary DSN lives only in process memory, discarded after query
- Long-term config uses `passwordEnv` to reference environment variables — no plaintext passwords in files
- All output paths pass through `redact()`, passwords replaced with `***`
- `connections.local.json` is in `.gitignore`, never committed

### 4. Audit Trail

Every operation appends to `audit.local.jsonl`:

```json
{"ts":"2026-06-10T09:30:00+00:00","action":"query","connection":"host='***' ...","sql_hash":"a1b2c3d4e5f6","sql_preview":"SELECT * FROM users WHERE...","rows":42}
{"ts":"2026-06-10T09:30:05+00:00","action":"blocked","reason":"Detected dangerous keyword 'DELETE'","sql_preview":"DELETE FROM users..."}
```

AI cannot prevent audit logging. Blocked attempts and successful queries are treated equally.

### 5. No Connection, No Execution

Connection resolution has a clear priority (DSN > profile > env vars > config file). When all fail, the script outputs an error and exits. No guessing, no searching through project files.

## What Was Deliberately Removed

- **Common SQL templates**: any model knows how to query `information_schema`
- **Conversation guides**: any model knows how to talk to humans
- **Error handling guides**: script JSON output is self-describing
- **Driver installation docs**: any model knows how to install pip packages
- **Platform-specific config** (openai.yaml): will become obsolete

Everything removed shares one trait: it was teaching AI how to walk inside the fence. As models improve, these become noise — but the fence itself never expires.

## Core Principle

This skill's design condensed into one sentence:

> **What's enforced by script, stays. What's explained to AI in text, goes.**

`raise ValueError` is a million times stronger than "please don't execute DELETE" — the former is engineering guarantee, the latter is a trust assumption.

## File Structure

```
postgres-query/
├── SKILL.md                   # Fence rules + script entry (~40 lines)
├── DESIGN.md                  # Design philosophy (this file, for humans)
├── DESIGN_cn.md               # Chinese version
├── references/
│   └── connection.md          # Connection priority and config format (facts only)
└── scripts/
    ├── sql_guard.py           # SQL safety checker (zero deps, independently reusable)
    ├── pg_common.py           # Connection management + redaction + audit
    ├── pg_query.py            # Read-only queries
    ├── pg_schema.py           # Schema inspection
    ├── pg_explain.py          # Query plans
    ├── pg_profiles.py         # Local profile listing
    └── test_sql_safety.py     # Safety tests (42 cases)
```

Each file has clear responsibility boundaries: `sql_guard.py` handles "can this execute?", `pg_common.py` handles "connect to what, how, and record what", entry scripts only assemble.
