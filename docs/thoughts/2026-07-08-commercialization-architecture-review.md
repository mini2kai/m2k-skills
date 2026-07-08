# 2026-07-08 商业化架构方案的评审与取舍

## 起因

想给 skill 中心加一套商业化能力："核心资产防白嫖 + 全网使用量精准统计计费 + 客户端无感热更新 + 零服务器成本"，并杜绝动态下发可能导致的 RCE 风险。整体走 GitHub + Cloudflare 边缘计算的轻量化混合架构。

原始方案要点：
- 本地热插拔加密包（`.pyd` 二进制密核）+ 云端边缘记账拼装 + GitHub 静态文件托管
- Cloudflare Worker 拦截请求、KV 扣额度、D1 存隐藏 prompt
- 启动时静默从 GitHub 下载最新 `.pyd` 覆盖本地
- 云端组装标准 messages，客户端用自带 LLM Key 跑推理

## 评审结论：方案对不上现有形态，核心部分否决

### 1. 运行机制对不上

方案假设 skill 是"能被 Python import 并执行的库"（`__init__.py → import core_logic.pyd → execute_skill_workflow()`）。

但实际环境是 **Agent 解析 SKILL.md 文本指令**——Agent 不调 `run()`，它在自然语言层决定"现在该跑哪个脚本、传什么参数、怎么执行围栏"。把 `SKILL.md` 换成 `.pyd`，等于把 Agent 大脑里的判定逻辑塞进黑盒，Agent 再也无法遵守 SKILL.md 里写死的安全规则（"高风险写入没确认不得执行""SQL 只读""禁止直接 SSH"）。这直接瓦解了最值钱的"围栏"那套。

### 2. 价值载体对不上

"云端藏 system_prompt" 只对纯文本生成型 skill 有用。

现有 8 个 skill 全是**安全执行/工具型**：
- `postgres-query` 价值在 SQL 安全围栏 + 脱敏 + 审计
- `git-trunk-workflow` 价值在分支保护 + commit 前缀强检
- `lark-cli-config` 价值在授权链路 + lark-cli wrapper
- `server-docker-logs-readonly` 价值在 SSH/Docker 黑名单

value 在"做了什么、禁了什么"，不在"让 LLM 说什么话"。把这些拆成"云端藏 prompt + 本地跑 LLM 生成"，真正值钱的执行层留在明面，反把不该加密的提示词加密了。

### 3. 计费模型对不上

按"调 LLM 拼一次 messages"计费，对"一次任务里脚本跑很多次"的执行类 skill 是失真的——干活的是脚本，messages 拼一次扣一次，要么低估要么高估。真实计费维度应是"动作执行次数/复杂度"，但那个维度方案根本没覆盖。

### 4. RCE 风险与自己写过的原则正面对撞

"启动时静默从 GitHub 下载 `.pyd` 覆盖本地"本质就是远程代码执行通道。这跟 `skills/skill-dev` 里自己写的"独立安全模块、显式授权、审计留痕"正面对撞，法律和信任上对一个面向开发者的工具尤其烫手。

### 一票否决清单

明确不引入本生态的部分：
- `.pyd` 二进制下发 + 启动静默覆盖
- 云端藏 `system_prompt` 再下发
- `__init__.py + run()` 这套"库式"运行模型（ZCode/Codex 不是这么调 skill 的）

### 可以独立借鉴的部分

| 可借鉴点 | 怎么融进现有形态 |
|---|---|
| Cloudflare Worker 做 license/额度/调用量统计 | 装包或 `uvx` 安装时一次性激活 license，本地脚本执行前可选上报（非阻断；断网能用） |
| KV 存剩余额度、D1 存 skill 元数据 | 适合做"按 skill 包卖订阅号"的记账后端 |
| 基于 IP 的限流 | Worker 入口都要加 |
| 版本热更新 | 不热更新 `.pyd`，改成"启动检查 manifest 版本，提示用户 `uvx --upgrade`"，断网不阻断、不动态加载二进制 |
| 用户自己的 LLM Key 跑推理 | 现有形态天然符合 |

## 第二轮：聚焦"实时更新 skill"的取舍

### 现状——主动更新能力已经做完了

`m2k-skills-tools` 已覆盖：
- `status`：本地 vs 远端 `manifest.json` 版本对比
- `update [skill|all]`：带备份、覆盖、`.local.json` config schema 比对恢复
- `info <skill>`：本地版本 + 线上版本
- `install.ps1 -Force`：等价入口

"实时更新"这个缺口不是"功能缺失"，是"主动 vs 被动"——用户得自己想起来去跑 `status`/`update`，不跑就永远落后也不自知。

### "实时"分四个层次，只取一层

| 层次 | 含义 | 取舍 |
|---|---|---|
| ① 用时感知 | Agent 触发某 skill 时顺手自检版本，落后就在对话里提示（不阻断） | 可选 |
| ② 一键到位 | 上面那个提示里直接给一条 `m2k-skills-tools update <skill>` | 配合 ① |
| ③ 作者改完秒推到所有用户机上 | 长连接 push / WebSocket | 否决 |
| ④ 启动静默自动覆盖 | `.pyd` 那套 | 否决 |

③ 要常驻后端 + 长连接，跟"零服务器成本"和"离线可用"直接对着干；④ 等于一边开车一边换轮胎，且违反 skill-dev 的"显式授权"原则。

### 最小落地（如果要做）

在 `work-orchestrator/SKILL.md` 编排流程里加一句"开始前可选跑一次 `m2k-skills-tools status` 自检"，5 行 markdown，不碰脚本、不缓存、不静默。

### 否决项

- 不要把 `check` 放进每个 `*.py` 启动里——一次任务脚本跑很多次，没意义还拖慢
- 不要启动时静默 `git pull` / 覆盖——污染正在使用中的 SKILL.md，反而废掉 `install.ps1` 已做好的备份 + schema 比对
- 不要引入 Worker 来管"实时更新通知"——版本检查 GitHub raw 一行就够，徒增 RCE 入口和后端维护

## 最终决定：开源 + 不统计调用 → 什么都不加

基于两个前提：
1. **开源**：不卖激活号 → 不需要 KV 扣额度；不做商业报表 → 不需要 D1 记调用量明细；不卡用户位 → 不需要 Worker 拼 messages、不需要 IP 限流防刷量。
2. **不统计调用**：整层 Cloudflare 后端基建（Worker + KV + D1 + 限流）对开源形态是纯粹负债——免费维护一份没人刷卡的后端，徒增两个故障面和一处 RCE 风险。可以全扔。

**结论：现状够用，不搞统计后端，不加商业化层。** "实时更新"如果非加，只在 orchestrator 加一条可选 markdown 提醒，不碰脚本、不走后端、不缓存、不静默。

## 后续优化建议（不急，按优先级排）

### 高优先级

**1. `.gitignore` 加凭据泄露兜底**
- `connections.local.json`、`targets.local.json` 靠 `.local.json` 命名约定防泄露，但命名规范跟着 fork 传不走
- 用 `install.ps1` 里已有的 `Get-CodexLocalConfigFiles` 判断做一道机器兜底（pre-commit hook 或 `.gitignore` 扩展）
- 价值：开源被 fork 改造时仍能防凭据上 GitHub

**2. 脚本 JSON 输出 schema 统一**
- 现在各 skill 脚本输出字段各写各的：`ok`、`stage`、`target`、`requires_confirmation`、`requires_user_action`、`risk`、`next_action`、`fetch_verify_ok`...
- Agent 读 JSON 靠 LLM 每次猜字段，漏读 `requires_user_action` 就出过 lark-cli "没展示 URL 就后台等" 的反复 fix
- 解法：在 `docs/` 固化一份 `script-result-protocol.md`，定义必备/可选字段、布尔字段什么时候必须为 true。新 skill 强制走，老 skill 平迁。不改业务脚本，只立契约。

**3. `requires_user_action` 提升为协议一等公民**
- lark-cli 踩过的坑说明"需要人工"信号在 JSON 里不能一眼看出就一定漏
- 协议里强制：凡是脚本需要用户先去外部完成动作（授权、确认、填凭据），JSON 必须 `requires_user_action=true` + 配 `next_action` 人可读字符串
- 等于把 lark-cli 一次踩坑的经验沉淀成项目级契约，不重复付学费

### 中优先级

**4. 版本号语义断链**
- `manifest.json` 每个 skill 有 `version`，但和 git release、和"用户该跑 update"的信号没有强约束
- `status` 依赖这个字符串，一旦和实际更新内容对不上，用户会习惯"反正 status 也看不出啥"
- 选其一固定：要么开 release 流程（tag == manifest 版本），要么 README 写明"改了直接 bump manifest"

**5. `m2k-skills-tools` 依赖瘦身**
- `pyproject.toml` 依赖 `textual`+`inquirerpy`+`rich` 三套 UI 库
- `textual` 是个大包，如果实际只用简单菜单，砍掉能让 `uvx` 安装明显变快
- 跑一次 `uvx m2k-skills-tools` 确认哪个 UI 库真用到，没真用的从 `pyproject.toml` 移走

### 不建议改

- **不要重写 `install.ps1`**——`Remove-CodexJsonComments` / `Compare-CodexConfigSchema` / `Restore-CodexLocalConfigs` 写得很用心，纯 refactor 性价比低，易引回归
- **不要把 `m2k-skills-tools` 和 `install.ps1` 二选一**——两套入口服务两群人是好事
- **不要加 tier/license 字段**——不走商业化，加了反而误导 fork 的人

## 下一步

- 接受现状不急着改，后续改进排期按上面优先级慢慢推
- 如果只能做一件，选 #2 + #3 合并：先写一份 `script-result-protocol.md` 立契约，老 skill 平迁慢慢来没压力