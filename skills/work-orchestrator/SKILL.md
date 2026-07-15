---
name: work-orchestrator
description: 仅当用户明确要求使用 work-orchestrator、启用总控编排、编排分析、先分析不修改、先定位再出方案、先给方案不要改代码、先评估影响范围、先出验证方案，或要求把需求、bug、UAT/线上报错从取证、方案、授权实施、验证到交付收口动态串起来时使用。用于中文工作流中的问题定位、需求分析、证据收集、影响范围评估、方案设计、验证计划，以及在用户授权后按当前本地可用 Skill 动态交接 Git 临时分支、代码实施、AI delivery 留存、数据库只读验证、日志验证和交付摘要；代码类任务若存在 ai-delivery-hook，应主动检测/请求授权激活，并自动编排 start/prepare/finish。本 Skill 默认不直接修改代码、配置、数据库或仓库状态，不合并长期分支，不部署。
---

# Work Orchestrator

## 定位

本 Skill 是手动触发的中文总控编排模式，用于让需求、bug、UAT/线上报错等工作先变清楚，再决定是否进入实施和交付。

它负责判断：当前问题是什么、证据从哪里来、哪些能力可用、是否需要 Git 分支、证据是否足够、什么时候必须停住、授权后应该把哪些上下文交给哪个专业 Skill。

它不是固定流水线，也不是专业 Skill 的总包实现器。它不假设某个专业 Skill 一定存在，不吞并专业 Skill 的安全规则，不替用户合并长期分支或部署。

## 触发规则

推荐通过 `$work-orchestrator` 或 UI 手动选择来启用。本 Skill 只在用户明确表达以下意图时使用：

- 使用 `$work-orchestrator`
- 启用总控编排
- 编排分析
- 先分析不修改
- 先定位再出方案
- 先给方案不要改代码
- 先评估影响范围
- 先出验证方案
- 全链路处理这个需求或 bug
- 从需求/报错到交付帮我编排
- 先取证、再授权实施、再验证交付
- UAT/线上问题先定位再安排修复

普通的“帮我改”“实现一下”“修复这个问题”“加一个字段”不应自动触发本 Skill。若未显式启用，优先按普通开发或对应专业 Skill 独立处理。

如果用户明确指定某个专业 Skill，优先按该专业 Skill 独立处理，不强行插入本 Skill。若指定 Skill 当前不可用，说明不可用并给出替代方案。

## 职责边界

默认分析阶段可以做：

- 理解用户目标、现象和约束
- 用一句话归纳当前问题，不强行套固定分类
- 判断需要哪些能力和证据来源
- 阅读代码、配置、页面、接口和调用链
- 编排当前可用的专业 Skill 进行只读取证或分析
- 设计数据库只读验证 SQL 或日志检索条件
- 分析根因、影响范围、风险点和依赖关系
- 输出推荐方案、实施步骤、验证计划和阻断条件

用户明确授权后可以编排：

- Git preflight、来源分支确认、AI 临时分支创建和交付收口
- 代码、配置、页面、Mapper、导出、异步任务等实施
- 数据库只读验证、日志复核、测试和构建
- 中文 commit、可选 push 临时分支、合并前交接摘要

始终不默认做：

- 未授权修改代码、配置、数据库或仓库状态
- 写数据库、执行 DDL/DML、修改线上配置
- 合并 `dev`、`uat`、`main`、`master`、`release/*`、`prod` 等长期分支
- 部署或发布
- 破坏性 Git 操作，例如 reset hard、clean、force push、删除分支/tag
- 在工作区改动归属不明时继续实施

## 能力路由规则

**核心原则：有 skill 覆盖的操作，必须走 skill。没有 skill 覆盖的操作，自由发挥。**

### 路由判断

每次进入 Execute 阶段前，检查当前可见 Skill 列表。对于本次任务涉及的每类操作：

- 有匹配的 Skill → **必须通过该 Skill 的脚本执行，不允许用原生命令绕过**
- 没有匹配的 Skill → 自由发挥，但需遵守通用安全边界

### 不可绕过清单

当以下能力可用时，对应操作**只能通过受控入口执行**。数据库能力优先使用当前客户端暴露的只读数据库 MCP；`postgres-query` 仍作为本地受控脚本方案可用。GitHub/GitLab/Gitee 等托管平台对象优先交给对应 MCP，本地 Git 写操作仍交给 `git-trunk-workflow`。

| 操作 | 可用受控入口 | 禁止直接使用 |
|---|---|---|
| Git 分支创建、暂存、commit、push | `git-trunk-workflow` | `git switch -c`、`git checkout -b`、`git add`、`git commit`、`git push`（分支命名由本 Skill 按 AI 临时分支命名约定决定，传入 create_branch.ps1 执行）|
| GitHub/GitLab/Gitee 平台对象 | 对应平台 MCP（优先） | 未授权创建/合并 PR/MR、直接猜测 API、把平台 MCP 当成本地 Git 围栏兜底 |
| AI 代码交付留存 | `ai-delivery-hook` | AI 自己口头记录、只在最终回复里说明、跳过 current/prepared/docs |
| 数据库只读查询 | 数据库 MCP（优先）或本地受控脚本 `postgres-query` | 直接 `psql`、手写连接代码、数据库写入/DDL |
| 服务器日志读取 | `server-docker-logs-readonly` | `ssh`、`docker exec`、`scp` |

当这些 Skill 不可用时（未安装），上述原生命令可以使用，但必须先说明缺失能力并获得用户确认。

如果专业 Skill 的脚本已经运行但返回失败，视为该操作被专业围栏阻断；不得改用上表中的原生命令兜底。正确做法是停住，复述脚本错误和下一步选项，待用户确认后修正参数或重新运行专业 Skill 脚本。

### 缺失能力时

- 明确说明缺失哪个 Skill
- 给出临时替代方案
- 等待用户确认后再用原生方式执行
- 安全边界不因 Skill 缺失而放宽（数据库仍只读、Git 仍不 force push）

## 任务类型归纳

不要把任务强行塞进固定分类。先用一句话归纳当前问题：

- 当前要解决什么现象或目标？
- 触发来源是什么？
- 可能涉及哪些能力？
- 当前最关键的不确定点是什么？

可以参考但不限于需求开发、bug 修复、UAT 问题、线上异常、数据问题、配置问题、导出问题、异步任务、外部系统问题、文档整理、Git 交付。输出时使用“问题简述”，不要只输出标签。

示例：

```text
问题简述：UAT 导出接口在历史数据缺少字段时返回异常，需要结合日志、Mapper SQL 和现有数据确认根因。
```

## AI 临时分支命名约定

当需要 Git 分支且由 AI 协作交付时，分支命名遵循：

```
ai/<source>/<YYYYMMDD>-<type>-<topic>
```

- `source`：来源分支名（如 dev、uat、main）
- `date`：创建日期，8 位数字
- `type`：fix | feat | bug | hotfix | docs | chore | refactor
- `topic`：简短英文描述，用连字符分隔

示例：`ai/dev/20260612-feat-export-column`

此约定由本 Skill 在编排时决定并通过文档约束；`git-trunk-workflow` 只负责安全执行，不强制命名格式。

## AI delivery 留存编排

当当前可见 Skill 中存在 `ai-delivery-hook`，且任务进入代码/配置/测试文件修改或 Git 交付路径时，本 Skill 必须把它纳入编排：

1. **Intake / Evidence**：优先调用 `ai_delivery_search.py` 检索历史 delivery/workflow 留存，作为影响范围和历史风险证据。
2. **Execute 前**：调用 `doctor.py` 检查当前仓库是否已接入 managed hook。
3. **多仓 workspace 强制**：如果 workspace 下存在多个 `.git`，实施前必须先输出 repo map，并显式锁定 `workspace_root`、`code_repo_root`、`delivery_repo_root`、`git_operation_repo_root`、`current_cwd`、`source_branch`、`ai_branch`。其中 `code_repo_root` 必须等于 `git_operation_repo_root`，不一致就停住。
4. **未激活时**：不得静默修改 Git hook；先询问用户是否允许为当前 repo 执行 `activate_project.py --repo-root <repo>`。用户同意后由 AI 自动调用，用户不需要手动输入命令。
5. **Execute 开始前**：调用 `ai_delivery_start.py` 开启 active AI session。若返回 `requires_manual_backfill=true`，先补录或纳入本次交付上下文。
6. **Git handoff 前**：AI 自动写 `current.local.json`，再调用 `ai_delivery_prepare.py` 生成 repo-local docs 和 `prepared.local.json`。prepare 前必须校验 `session.title / session.type / session.repo_root` 与 `current.local.json.title / current.local.json.files` 是否属于本次任务；发现旧标题、旧文件或旧摘要时必须先清理或重启 session。
7. **commit / push**：由 hook 被动调用 `check_ai_delivery.py`，不得绕过阻断；commit 前还要做跨仓 `git status` 审计，确认变更只在目标代码仓和目标 delivery 仓。
8. **commit 后、push 前或交付收口时**：调用 `ai_delivery_finish.py --status completed` 关闭 session 并更新 checkpoint。
9. **docs 被 ignore 时**：不能临时手写 `git add -f` 兜底，必须走受控 ignored-docs 暂存流程，或者明确说明文档不入库。

若 `ai-delivery-hook` 不可用，代码类任务仍可继续，但最终 handoff 必须说明“未启用 AI delivery 留存”，并建议安装/启用该 Skill。

## 阶段门

使用阶段门推进，避免分析、实施、交付混在一起。

### A. Intake 问题进入

识别输入来源：用户口述、飞书需求/设计文档、服务器日志、数据库异常数据、页面/API/导出/异步异常、Git 分支问题等。

输出：问题简述、当前已知事实、缺少的关键条件。

### B. Evidence 证据收集

按需动态匹配当前可用 Skill 或通用方式：

- 需求/文档：目标、验收标准、字段口径。
- 日志：时间范围、关键日志、trace/request id、异常堆栈。
- 数据库：表结构、现有数据、只读 SQL、验证结论。
- 代码：调用链、Mapper、配置、页面、异步任务、外部系统。
- Git：当前分支、来源分支候选、工作区状态、历史提交；如涉及托管平台，再补充 issue/PR/MR/CI/release 等平台对象证据。

输出：证据清单、证据充分度、根因假设、待验证项。

### C. Plan 方案设计

输出根因判断、影响范围、推荐方案、预计修改文件/模块/配置、数据库/导出/异步/外部系统影响、验证计划、风险点。

此阶段结束必须停住，等待用户授权。

### D. Execute 授权实施

用户明确回复“按方案处理 / 授权修改 / 继续实现”后才进入实施。

若需要修改代码或仓库状态，先判断是否需要 Git 分支并确认来源分支；再交接当前可用的 Git 交付能力或临时 Git 方案。若 `ai-delivery-hook` 可用，同时检查 hook 激活状态，未激活时先请求用户授权激活；激活或确认已激活后，进入代码实施前自动开启 AI delivery session。

### E. Verify 验证

按方案收口验证：单元测试、构建、接口/页面验证、数据库只读验证、日志复核、未执行项说明。

### F. Handoff 交付

代码类任务完成后，需要输出合并前交接摘要。若 `ai-delivery-hook` 可用，Git handoff 前必须先生成 `current.local.json` 并调用 `ai_delivery_prepare.py`，把生成的 delivery/workflow 文档纳入显式暂存清单；commit 完成后调用 `ai_delivery_finish.py` 收口。若当前有可用 Git 交付 Skill，优先交给它完成变更归属检查、显式暂存、中文详细 commit、可选 push 临时分支和 handoff。否则按普通 Git 方案逐步确认。

正式技术/业务文档只在用户明确要求时输出。

## 证据充分度

输出方案前必须标注证据充分度：

- 充分：已有代码、日志、数据或需求证据支持结论，可以给出明确方案。
- 部分充分：已有证据支持主要方向，但仍有待验证项；方案必须标注假设。
- 不充分：关键证据缺失，不能给确定结论；应先补充证据或给临时验证方案。

证据不足时，不要把假设写成结论。

## Git 分支需求判断

不是所有任务都需要 Git 分支。

需要 Git 分支：

- 修改业务代码、配置文件、测试文件、导出模板、仓库文件或 skill 文件。
- 需要提交、push 或交付 review。

通常不需要 Git 分支：

- 只读查库、只读查日志、只做方案分析、只总结文档、只输出 SQL 或检索命令。

不确定时，先说明判断依据，再询问用户是否进入临时分支开发。

## 来源分支决策

需要 Git 分支时，必须确认来源分支。用户指定优先级最高，例如“从 uat 迁出”“基于 dev 做”“当前分支就是问题分支”“从 release/xxx hotfix”。

如果用户没有指定，先根据问题来源给建议，但不要直接当成事实：

- UAT 问题：建议来源 `uat`。
- 开发需求：建议来源 `dev`。
- 线上 hotfix：建议来源 `release/*` 或 `prod`。
- 当前分支问题：建议来源当前分支。

创建分支前必须让用户确认来源分支，或确认“使用当前分支作为来源”。

## 阻断条件

遇到以下情况时，不要继续实施，必须停住并说明阻断原因、缺少什么、临时解决方案、需要用户提供什么：

- 用户未授权实施，但任务需要修改代码、配置或仓库状态。
- 缺少关键证据，无法判断根因或影响范围。
- 本地没有所需专业 Skill，且用户未提供临时替代方案所需信息。
- 需要数据库验证但没有连接信息或只读权限。
- 需要日志验证但没有时间范围、关键词、trace id 或日志访问方式。
- 需要 Git 分支但来源分支不明确。
- 工作区不干净且改动归属不明。
- 涉及写库、DDL、线上配置、部署、合并长期分支。
- 需要高风险 Git 操作，例如 reset hard、clean、force push、rebase。
- 用户要求的操作与专业 Skill 的安全规则冲突。

## 最小充分上下文

调用专业 Skill 前，只传递完成该步骤所需的信息，避免把无关证据、长文档或完整日志全部塞过去。但不能因为精简而遗漏关键判断依据。

上下文包必须包含：

- 本次目标或问题简述。
- 当前已确认事实。
- 待验证假设。
- 相关文件、表、日志、文档链接或关键标识。
- 该 Skill 需要回答的问题。
- 输出结果如何回到总控判断。
- 安全边界或禁止动作。

给数据库能力：优先交给数据库 MCP；说明要验证什么、表名/字段/条件、只读 SQL 或查询目标、预期结果如何解释。没有 MCP、用户明确要求、或需要本地围栏审计时，使用 `postgres-query` 本地受控脚本。

给日志能力：说明时间范围、服务/模块、关键词/trace id/request id、需要确认的异常链路。

给 Git 能力：说明是否需要分支、来源分支候选、任务 topic、是否允许 push、最终不合并不部署。若涉及 GitHub/GitLab/Gitee 平台对象，说明平台、仓库、issue/PR/MR id、目标动作，并优先交给对应 MCP。

给 AI delivery 留存能力：说明 repo root、任务标题、任务类型、变更文件、验证结果、风险等级、文档等级；首次激活 hook 前必须携带用户授权结论。

给实施能力：说明需求/问题摘要、根因或假设、预计修改范围、不应改变的旧行为、验证计划和风险点。

## 能力路由

本表只是能力候选，不是固定调用顺序。每次必须根据当前可见 Skill 的 `name` 和 `description` 判断是否可用。

| 能力需求 | 可用 Skill 的匹配方式 | 无可用 Skill 时 |
| --- | --- | --- |
| 需求/文档读取 | description 包含 Feishu、Lark、doc、wiki、sheet、drive 等能力 | 请用户提供文档内容、截图、链接可访问方式，或临时使用可用 CLI/浏览器读取 |
| 服务器日志读取 | description 包含 server、log、docker、readonly、incident 等能力 | 请用户提供日志片段、路径、时间范围、关键词；或输出检索命令 |
| 数据库只读验证 | 优先匹配当前客户端可用的数据库 MCP；无 MCP 时匹配 `postgres-query`（description 包含 PostgreSQL、pgsql、database、readonly、schema、query 等能力） | 询问临时连接信息和只读权限；优先建议配置/使用数据库 MCP，必要时使用本地受控脚本方案 |
| Git 临时分支交付 | name 为 `git-trunk-workflow`，或 description 包含 Git、branch、commit、push、staging、handoff、protected 等能力 | 使用普通 Git 命令给计划，实施前逐步确认 |
| GitHub/GitLab/Gitee 平台协作 | 当前可用 MCP 中包含 github、gitlab、gitee、issue、PR、MR、review、CI、release 等能力 | 询问平台、仓库和目标对象；无 MCP 时建议配置 MCP，或经用户确认后使用 gh/glab/API/网页方式 |
| AI delivery 留存 | name 为 `ai-delivery-hook`，或 description 包含 AI delivery、active session、current/prepared、repo-local docs、git hooks 等能力 | 最终 handoff 说明未启用留存，并建议安装/启用 |
| 代码或配置实施 | description 包含相关业务域、fullstack、page、config、mapper、export、ERP 等能力 | 使用普通代码开发流程，但先明确风险和验证计划 |
| 正式变更文档 | description 包含 change doc、技术版、业务版、飞书文档等能力 | 用户明确要求后，用普通 Markdown 输出或询问目标文档格式 |

调用专业 Skill 时，先说明三点：为什么需要它、需要它补充什么、它的结果如何回到当前总控分析中。

## 证据规则

代码证据需要包含：文件路径、行号、关键逻辑、该逻辑如何支持当前判断。

数据库证据需要包含：表名和字段、查询条件、只读验证 SQL、预期结果或如何解释结果。

日志证据需要包含：日志来源、时间范围、关键词或 trace id/request id/user id/page id/task id 等标识、关键日志行、日志如何支持当前判断。

如果无法直接读取数据库或日志，输出可执行的只读 SQL、日志检索条件和预期判断标准。

## 专业 Skill 独立性

各专业 Skill 必须保持独立可用：

- 不把本 Skill 作为其他 Skill 的前置步骤。
- 不复制或覆盖专业 Skill 的安全规则、脚本规则和领域细节。
- 用户明确点名某个专业 Skill 时，直接使用该专业 Skill，不强行套总控编排。
- 本 Skill 只在被手动启用时参与，并只负责判断“需要哪些能力”。
- 进入专业 Skill 后，遵守该专业 Skill 自己的流程和风险边界。

## 授权交接

当已经形成方案但尚未实施时，用简短方式停住并确认：

```text
当前 work-orchestrator 阶段已完成分析和方案设计，尚未修改代码、配置或仓库状态。
如需继续实施，请明确回复：按方案处理 / 授权修改 / 继续实现。
```

如果方案涉及修改，交接前列出：预计修改的文件/模块/配置、每处修改原因、主要风险点、验证步骤、是否需要 Git 分支、建议来源分支或需要用户指定来源分支。

用户授权后：

- 代码类实施优先确认 Git 分支需求和来源分支。
- 若本地有 `ai-delivery-hook`，由 AI 自动检查 hook 状态；未激活时必须单独询问是否允许增量写入当前 repo 的 Git hook，用户同意后再自动执行 `activate_project.py`。
- 若本地有 `ai-delivery-hook`，由 AI 自动执行 search/start/prepare/finish；用户不需要手动运行这些 Python 命令。
- 若本地有适配的 Git 交付 Skill，交给它做 preflight、临时分支、提交和交接；否则使用临时 Git 方案并逐步确认。
- 若涉及 GitHub/GitLab/Gitee issue、PR/MR、review、CI、release 等平台对象，优先交给对应 MCP；不得把平台 MCP 当作本地 Git 围栏失败后的兜底。
- 非代码类实施，例如纯只读查库、只读日志、方案分析，不需要创建 Git 分支，也不需要开启 AI delivery session。
- 实施完成后，代码类任务必须输出合并前交接摘要，并明确未合并长期分支、未部署。

## 最终交付

代码类任务完成后，最终输出应包含：

- 问题/需求来源。
- 问题简述和根因摘要。
- 方案摘要。
- 来源分支和 AI 临时分支，如果有。
- commit 列表和是否已 push，如果有。
- AI delivery 留存状态，以及 delivery/workflow 文档路径，如果已启用。
- 修改文件和变更归属。
- 验证结果和未执行项。
- 数据库/日志证据或待验证项。
- 第一合并目标和是否建议回灌。
- 发布注意事项和回滚建议。
- 剩余风险。
- 明确说明未合并长期分支、未部署。

交付状态与 Git 交付能力保持一致：`Ready to merge`、`Ready for review`、`Blocked`。

## 文档输出规则

默认不生成正式技术版/业务版文档。只有用户明确要求时，才调用文档类 Skill 或输出正式文档。

明确触发包括：

- 整理成技术文档。
- 输出技术版+业务版。
- 同步到飞书。
- 给业务方说明。
- 形成变更文档。

如果用户没有明确要求，最终只输出简洁 handoff 摘要，不创建正式文档。
