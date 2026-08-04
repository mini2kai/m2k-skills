# M2K Skills

[![GitHub stars](https://img.shields.io/github/stars/mini2kai/m2k-skills?style=social)](https://github.com/mini2kai/m2k-skills/stargazers)
[![GitHub forks](https://img.shields.io/github/forks/mini2kai/m2k-skills?style=social)](https://github.com/mini2kai/m2k-skills/forks)
[![GitHub issues](https://img.shields.io/github/issues/mini2kai/m2k-skills)](https://github.com/mini2kai/m2k-skills/issues)
[![Skills](https://img.shields.io/badge/skills-9-success)](#skill-catalog)
[![Manager](https://img.shields.io/badge/manager-m2k--skills--tools-00A6D6)](#安装)
[![License](https://img.shields.io/badge/license-Non--Commercial-lightgrey)](#许可证)

一组可复用、可审计的 AI Agent 协作技能，安全约束由代码强制执行。

## 这是什么

M2K Skills 是在真实中文研发场景中实践 AI Agent 安全协作的产物。每个 skill 定义了 AI 不可越过的安全边界（围栏），围栏由代码保证——不是提示词建议，是 `raise`/`exit`/硬上限。围栏以内，完全信任模型能力。

这个仓库既是日常工具箱，也是方法论实验室。

> **设计理念** 见 [docs/](./docs/) — 核心原则、方法论和实践案例。

## 设计理念

> **用代码强制的边界，而非基于提示词的建议。**

核心主张：

1. 默认只读，写操作需要显式授权
2. 高风险操作不是禁止，是加确认门槛
3. AI 应该先证明它理解了问题，再被允许动手
4. 安全规则跟着任务走，不是全局开关
5. 凭据和本地状态永远不进 AI 的持久上下文

每个 skill 的设计理念和实现思路记录在各自的 `DESIGN.md` / `DESIGN_cn.md` 中。

## Skill 目录

| Skill | 说明 | 安全边界 |
|---|---|---|
| `postgres-query` | PostgreSQL 只读查询、结构查看、查询计划分析（仍在使用，建议优先配置数据库 MCP） | 本地受控脚本：SQL 白名单检查、危险关键字拦截、行数/超时硬上限、凭据脱敏、审计日志 |
| `server-docker-logs-readonly` | 服务器日志只读排查 | 白名单脚本限定路径，禁止 SSH/Docker 直接命令 |
| `git-trunk-workflow` | AI 短生命周期本地 Git 隔离 worktree 交付；GitHub/GitLab/Gitee 平台对象优先 MCP | 强制 worktree 隔离，禁止 force push/reset hard/删分支，显式暂存，commit/push 需确认 |
| `ai-delivery-hook` | AI 交付历史检索、人工变更检测 | 纯只读：不写仓库、不装 hook、不阻断提交；参数硬上限 |
| `work-orchestrator` | 全链路总控编排 | 阶段门强制先分析后实施，代码类任务在授权后交接专业 Skill |
| `ai-worklog` | AI 协作日报和报工统计 | 先预览再生成，不输出敏感凭据 |
| `lark-cli-config` | 飞书/Lark CLI 授权和文档操作 | 授权 URL 必须显式展示或打开，高风险写入需确认 |
| `web-demo-publisher` | Web Demo 生成、预览和发布 | 固定端口发布，外网失败不阻塞本地 |
| `skill-dev` | Skill 开发、验证和发布流程 | 围栏模型开发规范，commit/push/PyPI 需确认 |

## 安装

详细安装指南见 [INSTALLATION_cn.md](./INSTALLATION_cn.md)。

快速开始：

```powershell
# TUI 管理器（推荐）
uvx --from m2k-skills-tools m2k-skills-tools

# 或 PowerShell 单条安装
cd $HOME\.codex\skills
irm https://raw.githubusercontent.com/mini2kai/m2k-skills/main/scripts/install.ps1 | iex; Install-CodexSkill ai-worklog
```

## 仓库结构

```text
m2k-skills/
├── skills/              # 独立 skill（SKILL.md + DESIGN.md + scripts/ + references/）
├── docs/                # 设计理念、核心原则、实践文章
├── packages/            # m2k-skills-tools（Python TUI 管理器）
├── scripts/             # PowerShell 安装器
├── manifest.json        # Skill 元数据、版本和依赖
├── INSTALLATION.md      # 安装使用说明（英文）
├── INSTALLATION_cn.md   # 安装使用说明（中文）
└── README.md
```

## 安全模型

| 层 | 机制 |
|---|---|
| 数据库安全（MCP 优先 + 本地脚本） | 日常查库建议优先配置数据库 MCP；本地 `sql_guard.py` 提供白名单/黑名单检查、字面值遮蔽、多语句拒绝 |
| 凭据保护 | `redact()` 脱敏、`passwordEnv` 环境变量引用、不落盘 |
| 操作控制 | 只读默认、风险操作只生成不执行、本地 commit/push 需确认；GitHub/GitLab/Gitee 平台对象优先 MCP 且高风险动作需额外授权 |
| 审计 | 操作和拦截事件自动写入 `*.local.jsonl` |
| 数据隔离 | `*.local.json`/`*.local.jsonl` 不进 Git |

## 参与贡献

本仓库遵循围栏模型开发。新增或优化 skill 时：

1. 先识别围栏（代码强制什么）和自由区（交给模型什么）
2. 围栏逻辑写独立模块，零外部依赖，必须有测试
3. SKILL.md 只写围栏规则 + 脚本入口（40-60 行）
4. DESIGN.md 记录设计理念（给人看）

详见 `skills/skill-dev/references/design_philosophy.md`。

## 许可证

非商业许可：允许个人学习、自用和组织内部非商业使用。禁止未经授权的商业使用、转售或付费分发。

商业使用请联系仓库作者获得书面授权。完整条款见 [LICENSE](./LICENSE)。
