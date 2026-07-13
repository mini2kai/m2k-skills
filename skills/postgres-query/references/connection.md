# 连接解析优先级

> 维护状态：`postgres-query` 已标记为低优先级；日常数据库访问优先使用数据库 MCP。本页仅用于没有 MCP、必须走本地脚本兜底时配置连接。

1. `--dsn` 临时 DSN
2. `--profile` 指定本机连接别名
3. 环境变量 `POSTGRES_DSN`
4. 环境变量 `PGHOST` + `PGPORT` + `PGDATABASE` + `PGUSER` + `PGPASSWORD` + `PGSSLMODE`
5. `scripts/connections.local.json` 的 `defaultProfile`

以上全无时，脚本输出 `missing_connection` 错误并停止。

# connections.local.json 格式

```json
{
  "defaultProfile": "example-readonly-db",
  "profiles": {
    "example-readonly-db": {
      "description": "只读 PostgreSQL 连接示例",
      "host": "your-db-host",
      "port": 5432,
      "dbname": "your_db",
      "user": "readonly_user",
      "passwordEnv": "PGPASSWORD_EXAMPLE_READONLY_DB",
      "sslmode": "disable"
    }
  }
}
```

密码通过 `passwordEnv` 引用环境变量，不明文写入。
