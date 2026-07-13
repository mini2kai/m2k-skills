# postgres-query：用代码围栏替代提示词祈祷

## 维护状态（2026-07-13）

这个 skill 暂时放一放，标记为**低优先级**。现在数据库访问优先交给客户端提供的数据库 MCP：MCP 已经可以平替甚至更顺手地完成只读查询、结构查看和结果返回，不再需要为日常查库继续扩展一套本地 profile + Python 脚本流程。

`postgres-query` 后续主要保留为历史设计案例和无 MCP 时的本地兜底：它的价值仍在 `sql_guard.py`、行数/超时硬上限、脱敏和审计这些代码围栏，但不再作为数据库访问的默认方向。

## 问题

AI Agent 查数据库，风险不在于它写错 SQL——而在于它执行了一条你没想让它执行的 SQL。

传统做法是在 system prompt 里写"禁止执行 DELETE"。但这是提示词约束，模型可以忽略、遗忘、被注入绕过。你本质上是在祈祷模型遵守规则。

## 设计理念

**不靠 AI 自觉，靠代码强制。**

所有 SQL 在到达数据库之前，必须通过一个 Python 模块（`sql_guard.py`）的验证。这个模块不关心是谁调用它、为什么调用、上下文是什么——它只做一件事：这条 SQL 是不是只读的？不是就 `raise ValueError`，物理上不可能执行。

围栏以内的事（写什么 SQL、怎么解释结果、怎么跟用户沟通）完全交给 AI 自由发挥。我不教 AI 怎么走路，我只管围栏的高度和位置。

## 实现思路

### 1. SQL 只读断言

核心是 `sql_guard.py` 里的 `assert_read_only()` 函数：

```
原始 SQL
  → 规范化（去空白、去尾分号）
  → 遮蔽字面值和注释（字符串内的 DELETE 不会被误判）
  → 拒绝多语句（遮蔽后仍有分号即拒绝）
  → 首关键字白名单（只允许 SELECT/WITH/SHOW/EXPLAIN）
  → 全文黑名单扫描（18 个危险关键字）
  → EXPLAIN ANALYZE 额外拦截
```

关键设计：先遮蔽再检查。`SELECT 'DELETE FROM users'` 是安全的，因为 DELETE 在字符串里。遮蔽函数把所有单引号、双引号、dollar-quote、行注释、块注释的内容替换为等长空格，只对裸 token 做判断。

### 2. 硬上限兜底

```python
MAX_ROWS = 1000     # 单次查询最多返回行数
MAX_TIMEOUT = 120   # 秒
```

即使 AI 传入 `--limit 99999`，limit 也会被截断到 1000。`pg_query.py` 不再把用户 SQL 包成 `SELECT * FROM (...) LIMIT N`，而是在执行原始只读 SQL 后用 `fetchmany(limit + 1)` 截断输出，避免 Greenplum 等系统目录表对子查询包裹不兼容。即使传入 `--timeout 9999`，`clamp_timeout()` 截断到 120。调用方无法突破输出上限。

### 3. 凭据不落盘

- 临时 DSN 只在进程内存中存活，查完即消失
- 长期配置用 `passwordEnv` 引用环境变量，配置文件里没有明文密码
- 所有输出路径经过 `redact()`，密码被替换为 `***`
- `connections.local.json` 在 `.gitignore` 中，不进仓库

### 4. 审计留痕

每次操作自动追加到 `audit.local.jsonl`：

```json
{"ts":"2026-06-10T09:30:00+00:00","action":"query","connection":"host='***' ...","sql_hash":"a1b2c3d4e5f6","sql_preview":"SELECT * FROM users WHERE...","rows":42}
{"ts":"2026-06-10T09:30:05+00:00","action":"blocked","reason":"检测到风险关键字 'DELETE'","sql_preview":"DELETE FROM users..."}
```

AI 无法阻止留痕。拦截记录和成功查询同等对待。

### 5. 无连接不执行

连接信息的解析有明确优先级（DSN > profile > 环境变量 > 配置文件），全部没有时脚本输出错误并退出。不猜测、不从项目文件里翻找。

## 什么被刻意删掉了

- **常见 SQL 模板**：模型知道怎么查 `information_schema`
- **引导话术**：模型知道怎么跟人说话
- **错误处理指南**：脚本输出的 JSON 已自描述
- **驱动安装文档**：模型知道怎么装 pip 包
- **平台特定配置**（openai.yaml）：会过时

删掉的这些有一个共同特征：它们在教 AI 怎么在围栏里走路。模型进步后它们变成噪音，但围栏本身不会过时。

## 核心原则

这个 skill 的设计浓缩为一句话：

> **脚本强制执行的，留。给 AI 看的说明文字，删。**

`raise ValueError` 比"请不要执行 DELETE"强一万倍——前者是工程保障，后者是信任假设。

## 文件结构

```
postgres-query/
├── SKILL.md                   # 围栏规则 + 脚本入口（~40 行）
├── references/
│   └── connection.md          # 连接优先级和配置格式（纯事实）
└── scripts/
    ├── sql_guard.py           # SQL 安全检查器（零依赖，可独立复用）
    ├── pg_common.py           # 连接管理 + 脱敏 + 审计
    ├── pg_query.py            # 只读查询
    ├── pg_schema.py           # 结构查看
    ├── pg_explain.py          # 查询计划
    ├── pg_profiles.py         # 本机 profile 列表
    └── test_sql_safety.py     # 安全测试（42 cases）
```

每个文件的职责边界清晰：`sql_guard.py` 管"能不能执行"，`pg_common.py` 管"连谁、怎么连、记什么"，入口脚本只做组装。
