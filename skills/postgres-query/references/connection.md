# 数据库连接与 MCP 配置

`postgres-query` 仍可作为本地受控脚本方案使用；新环境和日常查库建议优先配置数据库 MCP。真实 DSN、账号密码和 token 不要提交到 Git。

# 推荐：数据库 MCP

当前先记录一个已采用的 PostgreSQL MCP 配置示例：`dazzle_dev`。

## ZCode 工作区级配置

适合放项目共享的无密配置模板，路径：

```text
<repo>/.zcode/config.json
```

字段使用 `mcp.servers`：

```json
{
  "mcp": {
    "servers": {
      "dazzle_dev": {
        "type": "stdio",
        "command": "npx",
        "args": [
          "-y",
          "@modelcontextprotocol/server-postgres",
          "<POSTGRES_DSN>"
        ],
        "timeoutMs": 30000
      }
    }
  }
}
```

如果 `<POSTGRES_DSN>` 含账号密码，不要把这个文件提交到仓库；可以提交无密模板，真实 DSN 放用户级配置或本地 ignored 配置。

## ZCode 用户级配置

适合放个人真实连接信息，路径：

```text
~/.zcode/cli/config.json
```

同样使用 `mcp.servers`。用户级同名 server 会覆盖工作区级 server。

## 兼容 fallback 配置

如果使用兼容路径：

```text
<repo>/.agents/mcp.json
```

顶层字段是 `mcpServers`，不是 `mcp.servers`：

```json
{
  "mcpServers": {
    "dazzle_dev": {
      "type": "stdio",
      "command": "npx",
      "args": [
        "-y",
        "@modelcontextprotocol/server-postgres",
        "<POSTGRES_DSN>"
      ],
      "timeoutMs": 30000
    }
  }
}
```

# 本地脚本连接解析优先级

没有数据库 MCP、或明确需要本地脚本围栏审计时，`postgres-query` 按以下优先级解析连接：

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
