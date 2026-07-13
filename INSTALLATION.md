# Installation and Usage Guide

本文档包含 M2K Skills 的完整安装方式、配置说明和使用示例。

## 安装方式概览

| 方式 | 适用场景 | 命令 |
|---|---|---|
| m2k-skills-tools（TUI） | 日常管理、批量安装更新 | `uvx --from m2k-skills-tools m2k-skills-tools` |
| PowerShell 安装器 | 单条命令快速安装 | `irm ... \| iex; Install-CodexSkill <name>` |
| Codex skill-installer | Codex 原生安装方式 | `python ... install-skill-from-github.py` |
| 手动 clone | 开发调试 | `git clone` + 手动 copy |

---

## m2k-skills-tools（推荐）

Python TUI 管理器，发布到 PyPI，支持 Codex 和 Claude 两种目标目录。

### 安装和启动

```powershell
# 直接运行（无需安装）
uvx --from m2k-skills-tools m2k-skills-tools

# 或安装为本地工具
uv tool install m2k-skills-tools
m2k-skills-tools
```

无参数启动进入全屏 TUI，首先选择安装目标目录。

### TUI 操作

```text
← / →    切换左右区域
↑ / ↓    移动选中项
Space    勾选/取消
Enter    确认
/        搜索（支持名称、状态、描述、标签、依赖）
b        返回首页
r        刷新
q        退出
```

### 常用命令

```powershell
# 查看安装状态
uvx --from m2k-skills-tools m2k-skills-tools status --target codex

# 安装到 Codex skills 目录
uvx --from m2k-skills-tools m2k-skills-tools add ai-worklog --target codex

# 安装到 Claude skills 目录
uvx --from m2k-skills-tools m2k-skills-tools add ai-worklog --target claude

# 更新全部已安装 skill（二次确认，自动备份）
uvx --from m2k-skills-tools m2k-skills-tools update all --target codex
```

### 本地开发调试

```powershell
# 直接运行源码
uv run --project packages/m2k-skills-tools m2k-skills-tools status --target codex

# 安装为可编辑模式
uv tool install -e packages/m2k-skills-tools
m2k-skills-tools --target codex
```

### 功能说明

- 支持 Codex、Claude、当前目录、自定义目录
- 显示本地版本、线上版本、安装时间、更新状态
- 安装和更新时自动备份旧目录
- 恢复本地 `*.local.json` / `*.local.jsonc` 配置
- 搜索 skill 名称、依赖、标签和描述
- 环境检查：Python、uv、Git、PowerShell、Node、npx、GitHub manifest

---

## PowerShell 安装器

适合不需要 TUI 的场景，单条命令完成安装。

### 基本安装

```powershell
cd $HOME\.codex\skills
irm https://raw.githubusercontent.com/mini2kai/m2k-skills/main/scripts/install.ps1 | iex; Install-CodexSkill ai-worklog
```

安装完成后重启 Codex 让新 skill 生效。

### 查看可安装列表

```powershell
irm https://raw.githubusercontent.com/mini2kai/m2k-skills/main/scripts/install.ps1 | iex; Install-CodexSkill -List
```

### 覆盖安装

```powershell
irm https://raw.githubusercontent.com/mini2kai/m2k-skills/main/scripts/install.ps1 | iex; Install-CodexSkill ai-worklog -Force
```

### 从指定版本安装

```powershell
irm https://raw.githubusercontent.com/mini2kai/m2k-skills/main/scripts/install.ps1 | iex; Install-CodexSkill ai-worklog -Ref v1.0.0
```

### 从 fork 安装

```powershell
irm https://raw.githubusercontent.com/mini2kai/m2k-skills/main/scripts/install.ps1 | iex; Install-CodexSkill ai-worklog -Repo owner/repo -Ref main
```

### 不使用 irm | iex

```powershell
Invoke-WebRequest https://raw.githubusercontent.com/mini2kai/m2k-skills/main/scripts/install.ps1 -OutFile install.ps1
powershell -ExecutionPolicy Bypass -File .\install.ps1 ai-worklog
```

### 参数说明

| 参数 | 默认值 | 说明 |
|---|---|---|
| `Skill` | 无 | skill 名称，如 `ai-worklog`、`postgres-query` |
| `-List` | 关闭 | 列出可安装 skill |
| `-Force` | 关闭 | 覆盖安装（自动备份旧目录） |
| `-Repo` | `mini2kai/m2k-skills` | GitHub 仓库 `owner/repo` |
| `-Ref` | `main` | 分支、tag 或 commit ref |

---

## Codex skill-installer

Codex 自带的安装方式：

```powershell
python $HOME\.codex\skills\.system\skill-installer\scripts\install-skill-from-github.py --repo mini2kai/m2k-skills --path skills/ai-worklog
python $HOME\.codex\skills\.system\skill-installer\scripts\install-skill-from-github.py --repo mini2kai/m2k-skills --path skills/postgres-query
python $HOME\.codex\skills\.system\skill-installer\scripts\install-skill-from-github.py --repo mini2kai/m2k-skills --path skills/skill-dev
python $HOME\.codex\skills\.system\skill-installer\scripts\install-skill-from-github.py --repo mini2kai/m2k-skills --path skills/lark-cli-config
python $HOME\.codex\skills\.system\skill-installer\scripts\install-skill-from-github.py --repo mini2kai/m2k-skills --path skills/server-docker-logs-readonly
python $HOME\.codex\skills\.system\skill-installer\scripts\install-skill-from-github.py --repo mini2kai/m2k-skills --path skills/git-trunk-workflow
python $HOME\.codex\skills\.system\skill-installer\scripts\install-skill-from-github.py --repo mini2kai/m2k-skills --path skills/web-demo-publisher
python $HOME\.codex\skills\.system\skill-installer\scripts\install-skill-from-github.py --repo mini2kai/m2k-skills --path skills/work-orchestrator
```

---

## 安装行为

### 安装目标

安装器把 skill 复制到当前执行目录：

```text
<current-directory>\<skill-name>\
```

例如在 `C:\Users\you\.codex\skills` 下安装 `ai-worklog`：

```text
C:\Users\you\.codex\skills\ai-worklog\
```

### 覆盖策略

- 默认不覆盖同名目录
- `-Force` 覆盖前自动备份到 `.backup/<skill-name>-yyyyMMdd-HHmmss`
- `*.local.json`、`*.local.jsonc` 在新版结构兼容时自动恢复
- 新版结构变化时保留新模板，提示用户从备份迁移
- Excel、日志、preview、state 等运行文件只保留在备份目录

---

## Skill 使用示例

### postgres-query

> 维护状态：低优先级；日常数据库访问优先使用数据库 MCP。本节仅作为无 MCP 时的本地脚本兜底示例。

```powershell
# 查看本地连接配置
python .\postgres-query\scripts\pg_profiles.py

# 只读查询
python .\postgres-query\scripts\pg_query.py --profile dev --sql "select now()" --limit 20

# 表结构
python .\postgres-query\scripts\pg_schema.py --table public.orders --profile dev

# 查询计划
python .\postgres-query\scripts\pg_explain.py --sql "select * from orders where id = 1" --profile dev
```

本地连接配置：`postgres-query/scripts/connections.local.json`，密码用 `passwordEnv` 引用环境变量。

### ai-worklog

```powershell
# 生成预览
python .\ai-worklog\scripts\ai_worklog_collect.py --date today --preview

# 从预览生成正式 Excel
python .\ai-worklog\scripts\ai_worklog_collect.py --date today --from-preview .\ai-worklog\data\ai_worklog_preview.xlsx --excel
```

或通过自然语言触发：`帮我整理今天 AI 完成的内容`

### server-docker-logs-readonly

目标配置：`server-docker-logs-readonly/scripts/targets.local.json`

只允许通过白名单脚本查询，禁止直接 SSH/Docker 命令。

### web-demo-publisher

```powershell
# 发布到 localhost:9999
powershell -ExecutionPolicy Bypass -File .\web-demo-publisher\scripts\publish.ps1 -ProjectPath . -UseCpolar auto

# 从模板生成
powershell -ExecutionPolicy Bypass -File .\web-demo-publisher\scripts\generate-from-template.ps1 -Template landing-product -DestinationPath .\demo-page
```

### git-trunk-workflow

通过自然语言触发：`从 uat 拉一个 ai 分支处理这个问题`

### work-orchestrator

通过自然语言触发：`先分析不修改，帮我定位这个问题`

---

## 环境要求

| 依赖 | 用途 | 必需 |
|---|---|---|
| Python 3.10+ | 脚本执行 | 是 |
| Git | 版本管理和交付 | 是 |
| uv | TUI 管理器运行 | 推荐 |
| PowerShell | 安装器和部分脚本 | Windows 下是 |
| Node.js / npx | lark-cli-config、web-demo-publisher | 按需 |
| psycopg / psycopg2 | postgres-query（低优先级，本地兜底；日常查库优先 MCP） | 按需 |
| paramiko | server-docker-logs-readonly | 按需 |
| openpyxl | ai-worklog Excel 输出 | 按需 |
