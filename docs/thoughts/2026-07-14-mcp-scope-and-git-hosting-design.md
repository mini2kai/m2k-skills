# 2026-07-14 MCP 作用域与 Git 托管平台分层设计

## 起因

数据库已经开始使用 MCP 后，`postgres-query` 的定位需要重新校准：它不是废弃，而是从“默认查询入口”调整为“本地受控脚本方案”。同样的问题也出现在 Git：是否可以用 GitHub、GitLab、Gitee 或 Git MCP 替代 `git-trunk-workflow`？

结论是：**MCP 优先用于外部平台对象，本地高风险写操作继续保留代码围栏。**

## 当前 MCP 配置检查

按 ZCode 配置规则检查：

- 用户级配置：`~/.zcode/cli/config.json` 存在 `mcp.servers`，但当前为空。
- 当前仓库未发现 `.zcode/config.json`、`zcode.json` 或 `.agents/mcp.json`。
- 在 `C:/Users/lzsj/all` 搜索后，没有找到 `dazzle_dev` 的 ZCode MCP 配置落盘文件。
- 发现一个相近但不是 MCP 的本地连接 profile：`C:/Users/lzsj/all/lz_skills/.local/postgres-query/connections.local.json` 下的 `mdmaster-dazzle-dev`。

因此文档只记录 `dazzle_dev` 作为当前推荐/使用中的 MCP 配置示例，不声称已在 ZCode 配置文件中找到它。

## 数据库分层

| 场景 | 推荐入口 |
|---|---|
| 日常只读查询、结构查看、结果返回 | 数据库 MCP |
| 没有 MCP | `postgres-query` |
| 需要本地 SQL 安全检查、脱敏、审计、行数/超时硬上限 | `postgres-query` |
| 数据库写入、DDL、风险操作 | 只生成 SQL，不直接执行 |

当前记录的数据库 MCP 示例：

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

真实 DSN 不进 Git。项目里最多提交无密模板，个人真实配置放用户级或 ignored 本地配置。

## Git 分层

`git-trunk-workflow` 不应被通用 Git MCP 替代。它负责本地 Git 写操作的安全不变量：

- 保护分支拦截；
- 显式路径暂存；
- 禁止 force push；
- 保护分支禁止 commit/push；
- ff-only 同步；
- 审计留痕；
- 脚本失败禁止原生命令兜底。

GitHub/GitLab/Gitee MCP 适合处理远端平台对象：

| 平台对象 | 推荐入口 |
|---|---|
| issue 查询、创建、评论、关闭 | GitHub/GitLab/Gitee MCP |
| PR/MR 查询、创建、更新、评论 | GitHub/GitLab/Gitee MCP |
| review、reviewer、label、milestone | GitHub/GitLab/Gitee MCP |
| CI/actions/pipeline 状态查询 | GitHub/GitLab/Gitee MCP |
| release、tag、远端仓库元数据 | GitHub/GitLab/Gitee MCP |
| 本地 branch/stage/commit/push | `git-trunk-workflow` |

高风险平台动作，例如合并 PR/MR、删除远端分支、发布 release，仍需要额外确认。

## 项目级 vs 全局配置

MCP 配置不应简单全局化。

### 适合项目级

路径：

```text
<repo>/.zcode/config.json
```

适合放：

- 不含 token/DSN 的 server 名称和用途模板；
- 团队共享的 MCP 约定；
- 只读、低风险公共服务；
- “本项目数据库用 `dazzle_dev`，PR/MR 用 GitHub/GitLab/Gitee MCP”的说明。

### 适合用户级

路径：

```text
~/.zcode/cli/config.json
```

适合放：

- 数据库真实 DSN；
- `GITHUB_TOKEN` / `GITLAB_TOKEN` / `GITEE_TOKEN`；
- 私有 GitLab/Gitee base URL；
- 个人账号相关 MCP server；
- 任何 Authorization header 或 API key。

用户级同名 server 会覆盖项目级配置。工作区 MCP 会自动连接，因此只应打开可信项目。

## 最终原则

1. **MCP 优先，但不是替代所有 skill。**
2. **数据库 MCP 负责日常访问，`postgres-query` 保留本地围栏。**
3. **GitHub/GitLab/Gitee MCP 负责平台对象，`git-trunk-workflow` 保留本地 Git 写操作围栏。**
4. **项目级写无密模板和团队约定，用户级放真实凭据。**
5. **任何高风险远端动作仍需明确授权。**
