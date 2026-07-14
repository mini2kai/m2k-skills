---
name: postgres-query
description: PostgreSQL/pgsql/PG 本地只读查询脚本围栏；当前仍在使用，但建议优先配置当前客户端可用的数据库 MCP。Use when the user explicitly asks for postgres-query/local guarded scripts/sql_guard.py/audit caps, when no database MCP is available, or when PostgreSQL read-only queries, schema inspection, or EXPLAIN need local code-enforced guards. 连接方式不明确时必须先询问临时连接信息；风险写入或 DDL 请求只生成 SQL，不直接执行。
---

# PostgreSQL Query

## 使用定位：仍在使用，MCP 优先

本 skill 当前仍作为 PostgreSQL/Greenplum 的本地受控查询方案使用。它的核心价值是 `sql_guard.py`、行数/超时硬上限、凭据脱敏和审计留痕。

新环境和日常查库建议优先配置数据库 MCP；没有 MCP、用户明确要求使用本地脚本、或需要本地围栏审计时，再使用 `postgres-query`。

当前推荐的数据库 MCP 示例（真实 DSN 不要提交到 Git）：

```json
{
  "mcp": {
    "servers": {
      "dazzle_dev": {
        "type": "stdio",
        "command": "npx",
        "args": ["-y", "@modelcontextprotocol/server-postgres", "<POSTGRES_DSN>"],
        "timeoutMs": 30000
      }
    }
  }
}
```

项目级配置路径优先用 `<repo>/.zcode/config.json`；用户级私密配置放 `~/.zcode/cli/config.json`。详见 `references/connection.md`。

## 围栏（代码强制，不可绕过）

以下限制由脚本代码执行，AI 无法选择是否遵守：

- **只读白名单**：`sql_guard.py` 只放行 `SELECT`、`WITH`、`SHOW`、`EXPLAIN`（不含 ANALYZE）。其他一律 `raise ValueError`。
- **危险关键字拦截**：SQL 经过字面值/注释遮蔽后，出现 INSERT/UPDATE/DELETE/DROP/ALTER/CREATE/TRUNCATE/GRANT/REVOKE/VACUUM/CALL/DO/COPY/MERGE/REFRESH/LOCK/SETVAL/NEXTVAL 即拒绝。
- **硬上限**：单次最多输出 1000 行（`MAX_ROWS`，通过 `fetchmany` 截断，不改写原 SQL），超时最长 120 秒（`MAX_TIMEOUT`）。
- **凭据脱敏**：`redact()` 在所有输出路径上遮蔽密码。
- **审计留痕**：每次查询、拦截、连接事件写入 `scripts/audit.local.jsonl`。
- **无连接不执行**：连接信息缺失时脚本输出错误并停止，不猜测。

## 脚本入口

```bash
python scripts/pg_query.py   --sql "..." [--limit N] [--dsn|--profile]
python scripts/pg_schema.py  --sql "..." | --list-schemas | --list-tables | --table schema.table
python scripts/pg_explain.py --sql "..."
python scripts/pg_profiles.py
```

连接优先级：`--dsn` > `--profile` > `POSTGRES_DSN` > `PGHOST/...` 环境变量 > `connections.local.json`。

详见 `references/connection.md`。

## 围栏以内（AI 自由发挥）

在上述围栏的保护下，AI 自行决定：

- 写什么 SQL
- 怎么跟用户沟通
- 怎么解释结果
- 是否需要多次查询
- 如何引导用户提供连接信息
- 如何处理错误和重试
