# 2026-07-13 AI 交付留存 Skill 开发设计

## 起因

想把“需求 / bug 修复 / 技术改造完成后留下开发方案记录”做成一个可跨项目复用的 skill。最初设想是：只要项目发生代码变更，就通过 Git hook 强制生成交付留存文档。

进一步讨论后，核心边界被修正：**只有 AI 自己参与修改代码时，才必须走交付留存流程。** 用户自己紧急修改、自己提交的代码不能被这套机制拦住；但下一次 AI 接手项目时，必须识别到上一次人工临时修改，并补充记录或纳入本次上下文。

因此，这个 skill 不是“所有 commit 的强制文档生成器”，而是“AI 参与代码交付时的留存围栏 + 人工变更接手补录机制”。

## 目标

设计一个新 skill：`ai-delivery-hook`。

一句话定义：

> `ai-delivery-hook` 用于在项目中安装 AI 交付留存机制，通过 AI session 状态、结构化 schema、显式脚本和 Git hooks，强制记录 AI 参与的代码变更，并在 AI 下次接手时发现和补录人工临时提交。

它要解决四个问题：

1. **AI 改代码必须留痕**：AI 完成需求、bug、技术改造后，必须生成结构化交付记录。
2. **人工提交不被阻断**：用户自己紧急修代码、自己 commit 时，不因缺少 AI 留存文档而失败。
3. **AI 接手时识别人工变更**：下一次 AI 开始工作前，必须检测上一次 AI 记录点之后的人工提交。
4. **后续开发可判断影响**：生成的文档要帮助未来开发人员或 AI 判断是否需要参考、是否影响其他模块、是否存在风险。

## 非目标

首版不做这些事情：

- 不强制所有代码提交都生成文档。
- 不拦截用户手动 commit / push。
- 不自动改写或暂存用户文件。
- 不做远端 CI 强校验。
- 不识别真实自然人身份，不依赖 Git author 判断 AI / 人工。
- 不把交付判断写成大量提示词流程。
- 不创建 `agents/openai.yaml`。
- 不创建 README、CHANGELOG、安装指南等额外文档。

## 核心设计判断

### 1. 以 AI session 判定是否强制

不能用“有源码变更”作为强制条件，因为人工紧急提交也会产生源码变更。

首版采用本地状态文件判定 AI 是否正在参与交付：

```text
.agents/skills/ai-delivery-hook/session.local.json
```

只有当该文件存在，且内容表明 `actor=ai`、`status=active` 时，Git hook 才进入强制校验。

没有 active AI session 时：

- `pre-commit` 放行；
- `pre-push` 放行；
- 不要求 `current.local.json`；
- 不要求 `prepared.local.json`；
- 不要求 delivery 文档。

这个设计保证用户人工提交不会被阻断。

### 2. 以 last_ai_seen_commit 识别人工变更

用户人工提交虽然不被阻断，但不能从 AI 视野里消失。

首版维护本地状态文件：

```text
.agents/skills/ai-delivery-hook/checkpoint.local.json
```

记录 AI 上次完成接手时看过的提交点：

```json
{
  "last_ai_seen_commit": "<commit>",
  "last_ai_delivery_commit": "<commit>",
  "updated_at": "2026-07-13T14:30:00+08:00"
}
```

下一次 AI 启动任务时执行：

```text
git log <last_ai_seen_commit>..HEAD
```

如果存在 commit，且这些 commit 没有对应补录记录，则脚本输出 `requires_manual_backfill=true`，要求 AI 先补录人工变更，或显式把人工变更纳入本次交付记录。

### 3. Hook 只检查，不自动生成

Git hooks 不应该在 pre-commit 中自动生成文档并暂存文件。

原因：

- hook 自动改文件容易让提交内容不可预测；
- 自动暂存可能把用户不想提交的文件带进去；
- hook 内写文档失败后恢复复杂；
- 这与当前仓库“显式脚本入口 + 可审计围栏”的原则不一致。

因此首版 hook 策略是：

- `ai_delivery_prepare.py` 显式生成文档；
- `check_ai_delivery.py` 在 hook 中只做校验；
- 缺失时阻断 AI session 下的 commit/push，并给出下一步命令。

## 推荐方案

采用“轻 SKILL.md + 厚脚本围栏 + 本地 Git hooks”的方案。

| 层 | 职责 |
|---|---|
| `SKILL.md` | 只说明围栏、脚本入口、AI 自由区 |
| `references/` | 放 schema、状态文件、文档产物等事实性协议 |
| `scripts/` | 实现激活、体检、历史检索、session、schema 校验、补录检测、文档生成、hook 校验 |
| `.agents/skills/ai-delivery-hook/hooks/` | 保存 hook 片段或 wrapper；激活时默认增量追加到真实 Git 仓库 hook |
| 生成文档 | 默认写入真实 `repo_root/docs/`，workspace 根目录只做可选索引 |

这个方案符合 `m2k-skills` 当前围栏模型：**必须执行的规则用代码保证，AI 在围栏以内自由判断内容。**

## Skill 目录结构

新 skill 目录设计：

```text
skills/ai-delivery-hook/
├── SKILL.md
├── DESIGN.md
├── DESIGN_cn.md
├── references/
│   ├── delivery_schema.md
│   ├── state_files.md
│   ├── generated_docs.md
│   └── hook_policy.md
└── scripts/
    ├── ai_delivery_common.py
    ├── activate_project.py
    ├── doctor.py
    ├── ai_delivery_search.py
    ├── ai_delivery_start.py
    ├── ai_delivery_prepare.py
    ├── ai_delivery_finish.py
    ├── check_ai_delivery.py
    └── test_ai_delivery.py
```

不创建：

```text
agents/openai.yaml
README.md
CHANGELOG.md
INSTALLATION_GUIDE.md
assets/templates/
```

模板内容由脚本生成，避免为了少量 Markdown 模板引入额外资产目录。若后续模板复杂化，再考虑放入 `references/generated_docs.md` 作为事实性格式说明，而不是话术模板。

## 目标项目落盘目录取舍

首版对齐现有项目级 skill 目录形态。对单仓项目，`workspace` 可以就是 Git 仓库；对多仓 workspace，`workspace` 是包含多个 Git 子仓库的上层目录：

```text
<workspace>/.agents/skills/ai-delivery-hook/
```

这和现有项目中的结构一致：

```text
.agents/skills/git-trunk-workflow/
.agents/skills/postgres-query/             # 本地受控脚本：数据库访问建议优先 MCP
.agents/skills/server-docker-logs-readonly/
.agents/skills/work-orchestrator/
```

不再使用上一版设想的 `.agent_skill/`，也不在业务项目根目录分散创建 `.ai-delivery/`、`.githooks/` 等多个目录。

原因：

- `.agents/skills/<skill-name>/` 已经是当前业务项目使用的项目级 skill 安装形态。
- `SKILL.md`、`scripts/`、`references/`、运行日志和 hook wrapper 放在同一个 skill 目录下，边界最清楚。
- 现有安装器已经会为 skill 目录写 `.m2k-skill.json`，并在更新时备份旧目录。
- 运行时日志放在 skill 目录内的 `logs/`，与现有 `git-trunk-workflow/logs/` 保持一致。
- 业务项目根目录不再新增多个隐藏目录，只保留统一的 `.agents/skills/` 入口。

目录名取舍：

| 目录 | 取舍 |
|---|---|
| `.skill/` | 短，但和当前项目实际 `.agents/skills/` 结构不一致 |
| `.agent_skill/` | 是上一版自造目录，不应继续使用 |
| `.agents/skills/` | 与现有项目级 skill 安装形态一致，首版采用 |

需要长期沉淀给后续开发人员或 AI 阅读的交付文档，仍然放在 `docs/`。这些文档是项目知识资产，不属于 skill 运行时临时文件。
## Skill 安装与业务项目激活边界

当前 `m2k-skills` 安装器只负责安装 skill 本体：

```text
Install-CodexSkill ai-delivery-hook
m2k-skills-tools install ai-delivery-hook
```

它的行为是：

- 下载或读取 skill；
- 复制 skill 文件到安装目录；
- 已存在旧版本时先备份；
- 恢复兼容的 `.local.json` 配置；
- 不自动修改任意业务项目；
- 不自动配置 Git hook。

这个边界应该保留。通用安装器不应自动执行某个 skill 的项目级副作用，否则安装一个 skill 就可能修改当前目录的 Git 配置，风险太高。

因此 `ai-delivery-hook` 需要第二步显式激活目标 Git 仓库或 workspace：

```bash
python <workspace>/.agents/skills/ai-delivery-hook/scripts/activate_project.py --repo-root <repo-root>
```

多仓 workspace 使用：

```bash
python <workspace>/.agents/skills/ai-delivery-hook/scripts/activate_project.py --workspace-root <workspace> --discover-repos
```

`activate_project.py` 是首版唯一推荐入口。它的职责是“激活业务项目 hook”，不是“安装 skill 本体”。

## 推荐安装到 workspace 的方式

对于 `DI_SU` 这类“根目录不是 Git 仓库，子目录才是 Git 仓库”的结构，skill 应安装到 workspace 根目录：

```text
<workspace>/.agents/skills/
```

两种等价方式：

```powershell
cd <workspace>\.agents\skills
irm https://raw.githubusercontent.com/mini2kai/m2k-skills/main/scripts/install.ps1 | iex
Install-CodexSkill ai-delivery-hook
```

或者使用管理器指定目录：

```bash
m2k-skills-tools --skills-dir <workspace>/.agents/skills add ai-delivery-hook
```

安装完成后，workspace 内应出现：

```text
<workspace>/.agents/skills/ai-delivery-hook/
```

然后再显式激活 hook。

单仓库项目：

```bash
python <workspace>/.agents/skills/ai-delivery-hook/scripts/activate_project.py --repo-root <repo-root>
```

多仓库 workspace：

```bash
python <workspace>/.agents/skills/ai-delivery-hook/scripts/activate_project.py --workspace-root <workspace> --discover-repos
```

这里的关键区别是：

- **安装 skill**：把 `ai-delivery-hook` 放到 workspace 的 `.agents/skills/`，由现有安装器负责版本、备份、更新。
- **激活 hook**：给一个或多个真实 Git 子仓库增量接入 ai-delivery 受管 hook 区块；优先追加到既有 hook，不默认接管 `core.hooksPath`。
## 目标项目运行时目录结构

激活到业务项目后，目标项目中的 skill 目录既包含 skill 本体，也包含该 skill 的本地运行态：

```text
.agents/skills/ai-delivery-hook/
├── SKILL.md
├── DESIGN.md
├── DESIGN_cn.md
├── .m2k-skill.json
├── activation.local.json
├── config.local.json
├── workspace.local.json
├── current.local.json
├── prepared.local.json
├── session.local.json
├── checkpoint.local.json
├── references/
├── scripts/
├── hooks/
│   ├── pre-commit
│   └── pre-push
├── logs/
│   └── ai-delivery-YYYY-MM-DD.jsonl
└── backups/
    └── YYYYMMDD-HHmmss/
```

各文件职责：

| 文件 | 职责 | 默认提交 |
|---|---|---|
| `.m2k-skill.json` | m2k 安装记录，沿用现有安装器 | 可选，按项目策略 |
| `activation.local.json` | 当前业务项目 hook 激活信息、hook 版本 | 否 |
| `config.local.json` | skill 本地配置，例如默认文档等级、hook 策略 | 否 |
| `workspace.local.json` | workspace 到多个 repo 的映射、docs_mode、repo_id | 否 |
| `current.local.json` | AI 本次交付输入；多仓时可包含每个 repo 的记录 | 否 |
| `prepared.local.json` | `ai_delivery_prepare.py` 生成的产物清单、current hash、文档路径 | 否 |
| `session.local.json` | active AI session 状态 | 否 |
| `checkpoint.local.json` | last_ai_seen_commit 等本地接手基线 | 否 |
| `hooks/` | Git hook wrapper | 可选，建议随项目级 skill 一起保留 |
| `logs/` | 本地审计日志 | 否 |
| `backups/` | 激活或升级前的本地备份 | 否 |

使用 `.local.json` 命名是刻意设计：现有安装器在更新 skill 时会尝试恢复兼容的 `.local.json` 文件。这样 `activation.local.json`、`config.local.json`、`workspace.local.json`、`current.local.json`、`prepared.local.json`、`session.local.json`、`checkpoint.local.json` 在版本更新后更容易保留。

`logs/` 目录属于运行时产物。现有安装器会在更新前备份旧 skill 目录，因此旧日志不会直接丢失；首版不强制把旧日志恢复到新目录，后续如有需要可以由 `activate_project.py` 做日志迁移。

推荐在业务项目根目录或 `.agents/skills/ai-delivery-hook/.gitignore` 中忽略：

```text
*.local.json
logs/
backups/
```

真正应该提交的是生成后的项目知识文档：

```text
<repo_root>/docs/需求缺陷交付流程规范.md   # 可选
<repo_root>/docs/delivery/**/*.md
<repo_root>/docs/ai-workflow/**/*.md
```
## 目标项目激活与更新策略

`activate_project.py` 必须是幂等的：同一个业务项目可以重复执行。

激活或更新时：

1. 读取 `.agents/skills/ai-delivery-hook/activation.local.json`。
2. 判断已激活版本、skill 路径、hook wrapper 版本是否变化。
3. 变更前备份受管文件到 `.agents/skills/ai-delivery-hook/backups/YYYYMMDD-HHmmss/`。
4. 保留 `current.local.json`、`prepared.local.json`、`checkpoint.local.json`、`config.local.json`、`logs/ai-delivery-YYYY-MM-DD.jsonl`。
5. 只更新受管 hook wrapper 和 `activation.local.json`。
6. 不删除未知文件。
7. 不覆盖用户已有非受管 hook 内容。

`activation.local.json` 示例：

```json
{
  "skill": "ai-delivery-hook",
  "skill_version": "0.1.0",
  "skill_path": "<installed-skill-path>",
  "activation_mode": "append-existing",
  "hook_wrapper_version": "1",
  "activated_at": "2026-07-13T15:30:00+08:00"
}
```

如果 skill 本体更新，通用安装器负责备份旧 skill；业务项目激活脚本负责更新目标项目里的 hook wrapper 和 install metadata。两层备份互不替代。

## 目标项目安装后的文件

安装并激活后，要把“skill 运行态”和“项目知识资产”分开看。

skill 运行态默认只出现在 workspace 级 skill 目录：

```text
<workspace>/.agents/skills/ai-delivery-hook/
├── activation.local.json
├── config.local.json
├── workspace.local.json
├── current.local.json
├── prepared.local.json
├── session.local.json
├── checkpoint.local.json
├── hooks/
├── logs/ai-delivery-YYYY-MM-DD.jsonl
└── backups/
```

生成的项目知识资产默认写入真实 Git 仓库：

```text
<repo_root>/docs/
├── 需求缺陷交付流程规范.md          # 可选
├── delivery/YYYY-MM-DD/<slug>-delivery.md
└── ai-workflow/YYYY-MM-DD/<slug>-ai-workflow.md
```

本地状态和审计文件建议由 `.agents/skills/ai-delivery-hook/.gitignore` 忽略：

```text
*.local.json
logs/
backups/
```

`checkpoint.local.json` 是否提交有两种选择：

| 选择 | 优点 | 缺点 |
|---|---|---|
| 提交 `checkpoint.local.json` | 多机器 AI 能共享 last seen commit | 会产生状态文件提交噪音 |
| 不提交 `checkpoint.local.json` | 本地干净，不污染业务仓库 | 多机器接手需要重新基线 |

首版建议：**默认不提交 `checkpoint.local.json`，但脚本支持项目配置选择是否提交。** 原因是这个工具首要解决本地 AI 协作留存，不能一开始强迫所有业务仓库承受状态文件噪音。


## 安装后的脚本调用策略

目标项目激活 hooks 后，真实 Git hook 文件里只追加轻量 managed block，不复制 Python 业务逻辑。

推荐 managed block 行为：

```text
repo_root=$(git rev-parse --show-toplevel)
skill_root=<activate_project.py 写入的 workspace skill 路径>
python "$skill_root/scripts/check_ai_delivery.py" --repo-root "$repo_root" --skill-root "$skill_root" --mode pre-commit
```

设计取舍：

| 方案 | 取舍 |
|---|---|
| hook 复制完整 Python 逻辑到业务项目 | 自包含，但 skill 更新后各项目脚本会漂移 |
| hook 只引用已安装 skill 脚本 | 更新集中，逻辑一致，但 skill 路径变化后要重新 activate |
| hook 每次动态查找 skill | 灵活，但增加不确定性和启动成本 |

首版采用第二种：**hook 由 `activate_project.py` 写入 `skill_root`，再调用该 skill 下的脚本。**

原因：workspace 模式下 `.agents/skills/ai-delivery-hook/` 不一定在 `repo_root` 内，不能假设 `$repo_root/.agents/skills/...` 一定存在。围栏逻辑应该集中维护，不能在多个 Git 子仓库中复制后各自漂移。

Hook 文件使用 Git 默认 hook shell 形式，保证 Git for Windows / macOS / Linux 都能执行。Python 入口仍由脚本内部做跨平台处理。

## Hook 增量接入策略

不能默认用 `core.hooksPath` 直接接管项目 hook。

原因：如果项目已经有 Husky、lint-staged、pre-commit framework、自定义 `.git/hooks`、或已有 `core.hooksPath`，直接改成 `.agents/skills/ai-delivery-hook/hooks` 会让原有 hook 逻辑失效。

首版推荐采用“增量接入优先，独占接管兜底不用”的策略。

### 接入模式

| 模式 | 行为 | 是否推荐 |
|---|---|---|
| `append-existing` | 在已有 hook 文件中追加 ai-delivery 受管区块 | 默认推荐 |
| `managed-hooks-path` | 仅当项目没有任何 hook 配置时，设置 `core.hooksPath` 到 ai-delivery hooks | 可选兜底 |
| `manual` | 检测到复杂 hook 管理器时只输出手动接入片段 | 推荐用于高风险项目 |
| `overwrite` | 覆盖已有 hook | 禁止 |

### 默认算法

`activate_project.py` 对每个 Git 仓库执行：

```text
1. 读取 git config --get core.hooksPath。
2. 如果 hooksPath 存在：
   2.1 定位 hooksPath/pre-commit 与 hooksPath/pre-push。
   2.2 若文件存在，追加或替换 ai-delivery managed block。
   2.3 若文件不存在，创建文件并写入 managed block。
   2.4 不修改 core.hooksPath。
3. 如果 hooksPath 不存在：
   3.1 检查 .git/hooks/pre-commit 与 .git/hooks/pre-push。
   3.2 若存在真实 hook 文件，追加或替换 managed block。
   3.3 若不存在真实 hook 文件，可创建 .git/hooks/pre-commit / pre-push 并写入 managed block。
   3.4 不强制设置 core.hooksPath。
4. 如果检测到 hook 文件由 Husky 等工具生成且不适合自动修改：
   4.1 输出 requires_user_action=true。
   4.2 给出需要粘贴的 ai-delivery 调用片段。
```

也就是说：**能追加就追加，不接管；能保留就保留，不覆盖。**

### 受管区块

追加内容必须放在清晰的受管区块内：

```sh
# BEGIN ai-delivery-hook managed
repo_root="$(git rev-parse --show-toplevel)"
skill_root="<activate_project.py 写入的 skill_root>"
python "$skill_root/scripts/check_ai_delivery.py" --repo-root "$repo_root" --skill-root "$skill_root" --mode pre-commit
status=$?
if [ $status -ne 0 ]; then
  exit $status
fi
# END ai-delivery-hook managed
```

实际 `skill_root` 不能硬编码为 `../`。`activate_project.py` 应在激活时计算出稳定路径；如果无法稳定定位 skill，则返回 `requires_user_action=true`，输出手动接入片段。

重复激活时：

- 如果受管区块不存在：追加。
- 如果受管区块存在：只替换区块内部。
- 区块外任何内容不改。
- 替换前备份原 hook 文件到 `backups/YYYYMMDD-HHmmss/`。

### 与原有 hook 的执行顺序

默认把 ai-delivery 区块追加到 hook 文件末尾。

原因：

- 原有 lint/test/format hook 先跑，保留项目既有质量门禁。
- ai-delivery 作为交付留存检查，在最后判断是否缺少 AI 交付记录。
- 如果原 hook 已失败，Git 会提前退出，ai-delivery 不一定执行；这是可以接受的，因为代码质量门禁失败时本来也不应该提交。

后续可以支持配置：

```json
{
  "hook_order": "after-existing"
}
```

可选值：

| 值 | 含义 |
|---|---|
| `after-existing` | 默认，追加到末尾 |
| `before-existing` | 放到开头，先检查 AI 留存 |
| `manual` | 不自动写入，输出片段 |

### core.hooksPath 的使用原则

`core.hooksPath` 只在以下场景使用：

- 当前仓库没有配置 `core.hooksPath`；
- `.git/hooks/pre-commit` 和 `.git/hooks/pre-push` 不存在真实自定义内容；
- 用户明确选择 `--mode managed-hooks-path`。

否则不修改 `core.hooksPath`。

这条规则是围栏：**不得因为激活 ai-delivery-hook 而覆盖或绕过项目已有 hook 体系。**

### 手动接入片段

如果检测到复杂 hook 体系，脚本输出：

```json
{
  "ok": false,
  "requires_user_action": true,
  "message": "检测到已有 hook 管理器，未自动修改。",
  "snippet": "...",
  "next_action": "请将 snippet 加入现有 pre-commit/pre-push 流程。"
}
```

这样比自动覆盖更安全，也符合现有 skill-dev 的围栏思想。

## 本地状态与提交边界

首版默认这些文件是本地临时状态，不进入业务仓库提交：

```text
.agents/skills/ai-delivery-hook/workspace.local.json
.agents/skills/ai-delivery-hook/current.local.json
.agents/skills/ai-delivery-hook/prepared.local.json
.agents/skills/ai-delivery-hook/session.local.json
.agents/skills/ai-delivery-hook/checkpoint.local.json
.agents/skills/ai-delivery-hook/logs/ai-delivery-YYYY-MM-DD.jsonl
```

`activate_project.py` 可以创建：

```text
.agents/skills/ai-delivery-hook/.gitignore
```

建议内容：

```text
*.local.json
logs/
backups/
__pycache__/
.pytest_cache/
```

真正应该提交的是生成后的文档：

```text
<repo_root>/docs/需求缺陷交付流程规范.md   # 可选
<repo_root>/docs/delivery/**/*.md
<repo_root>/docs/ai-workflow/**/*.md
```

如果团队希望多机器共享 `last_ai_seen_commit`，后续再通过显式配置开启 tracked state。首版不默认提交 `checkpoint.local.json`，避免把本地协作状态污染到所有业务仓库。
## Workspace 与多仓库模式

有些业务目录本身不是 Git 仓库，而是一个 workspace：

```text
DI_SU/
├── .agents/skills/
├── docs/
├── biz_spec_app/                 # Git repo
├── linezone_dazzle_backend_1/     # Git repo
├── linezone_dazzle_frontend_1/    # Git repo
└── demo/                         # 非 Git 目录
```

这种情况下必须区分两个概念：

| 概念 | 含义 | 示例 |
|---|---|---|
| `workspace_root` | 整体业务工作区，放 `.agents/skills` 和可选本地索引 | `DI_SU/` |
| `repo_root` | 真正有 `.git` 的代码仓库，也是默认文档落盘位置 | `linezone_dazzle_backend_1/` |
| `repo_id` | 交付留存里的稳定仓库标识，不再决定主文档存储根目录 | `backend` / `frontend` / `biz_spec_app` |
| `repo_kind` | 仓库类型 | `frontend` / `backend` / `app` / `service` / `unknown` |

Git hook 只能绑定到真实 Git 仓库，所以在 workspace 模式下：

- skill 安装在 `workspace_root/.agents/skills/ai-delivery-hook/`。
- hook 激活要分别写入每个子仓库的 Git hook。
- 文档默认生成到对应 `repo_root/docs/`，确保能跟随真实代码仓库提交。
- workspace 根目录只保留可选索引，不作为首版强制交付资产。

## Workspace 配置文件

首版增加可选配置：

```text
.agents/skills/ai-delivery-hook/workspace.local.json
```

示例：

```json
{
  "workspace_root": ".",
  "docs_mode": "repo",
  "workspace_index": false,
  "workspace_index_path": "docs/ai-delivery-index.md",
  "repositories": [
    {
      "id": "biz_spec_app",
      "path": "biz_spec_app",
      "kind": "app",
      "display_name": "规格应用",
      "docs_root": "docs"
    },
    {
      "id": "backend",
      "path": "linezone_dazzle_backend_1",
      "kind": "backend",
      "display_name": "后端服务",
      "docs_root": "docs"
    },
    {
      "id": "frontend",
      "path": "linezone_dazzle_frontend_1",
      "kind": "frontend",
      "display_name": "前端工程",
      "docs_root": "docs"
    }
  ]
}
```

如果没有配置，`activate_project.py` 可以自动扫描 `workspace_root` 的直接子目录，识别包含 `.git` 的目录：

```text
repo_id = 子目录名
repo_kind = unknown
```

自动扫描只能作为兜底。正式项目建议写 `workspace.local.json`，因为目录名不一定能准确表达前端、后端、业务应用的含义。

文档默认写入各自 `repo_root/docs/` 后，`repo_id` 不再承担“决定文档放哪里”的职责；它仍用于 session、checkpoint、跨仓关联、历史检索和最终报告中的稳定标识。

## Workspace 激活策略

`activate_project.py` 支持两种模式：

```bash
python .agents/skills/ai-delivery-hook/scripts/activate_project.py --repo-root <git-repo>
python .agents/skills/ai-delivery-hook/scripts/activate_project.py --workspace-root <workspace> --discover-repos
```

处理规则：

| 输入 | 行为 |
|---|---|
| `--repo-root` 是 Git 仓库 | 只激活该仓库 hook |
| `--repo-root` 不是 Git 仓库 | 返回错误，提示改用 `--workspace-root` |
| `--workspace-root` 有配置 | 按 `workspace.local.json` 激活多个子仓库 |
| `--workspace-root --discover-repos` | 扫描直接子目录下的 Git 仓库并激活 |

每个子仓库都需要自己的 Git hook 配置，因为 Git 提交发生在子仓库内，不会触发 workspace 根目录的 hook。

对于 `DI_SU` 这类结构，激活结果应类似：

```text
biz_spec_app/.git/hooks/pre-commit
  # BEGIN ai-delivery-hook managed
  ...
  # END ai-delivery-hook managed

linezone_dazzle_backend_1/.git/hooks/pre-commit
  # BEGIN ai-delivery-hook managed
  ...
  # END ai-delivery-hook managed

linezone_dazzle_frontend_1/.git/hooks/pre-commit
  # BEGIN ai-delivery-hook managed
  ...
  # END ai-delivery-hook managed
```

如果某个子仓库已经配置了 `core.hooksPath`，则在该 hooksPath 指向的 hook 文件中追加受管区块；不修改既有 `core.hooksPath`。hook wrapper 运行时通过 `git rev-parse --show-toplevel` 获取当前 `repo_root`，再根据 `workspace.local.json` 反查 `repo_id` 和 `repo_kind`。

## 多仓文档生成策略

首版推荐：**文档写入真正发生代码提交的 Git 仓库内。**

也就是说，前端改动写到前端仓库，后端改动写到后端仓库，应用改动写到应用仓库：

```text
<repo>/docs/delivery/YYYY-MM-DD/<type>-<slug>-delivery.md
<repo>/docs/ai-workflow/YYYY-MM-DD/<type>-<slug>-ai-workflow.md
```

例如：

```text
linezone_dazzle_backend_1/docs/delivery/2026-07-13/bugfix-mail-push-delivery.md
linezone_dazzle_frontend_1/docs/delivery/2026-07-13/feature-order-page-delivery.md
biz_spec_app/docs/delivery/2026-07-13/feature-spec-rule-delivery.md
```

原因：

- 文档跟随真实 Git 仓库提交和推送，不会落在未版本化的 workspace 根目录。
- 后续开发人员 clone 某个仓库时，能直接拿到该仓库的交付记忆。
- AI 修改某个仓库时，优先读取该仓库自己的 `docs/`，上下文更聚焦。
- 不再强依赖目录名作为文档区分，因为文档天然在对应仓库下。

workspace 根目录可以保留可选汇总，不作为首版必需能力：

```text
<workspace>/docs/ai-delivery-index.md
```

这个索引只记录链接，不承载主文档：

```markdown
# AI Delivery Index

## backend
- linezone_dazzle_backend_1/docs/delivery/2026-07-13/bugfix-mail-push-delivery.md

## frontend
- linezone_dazzle_frontend_1/docs/delivery/2026-07-13/feature-order-page-delivery.md
```

如果 workspace 根目录不是 Git 仓库，索引只是本地辅助，不作为强制交付资产。

## 跨仓任务文档策略

跨多个仓库的一次 AI 任务，不在未版本化 workspace 根目录生成唯一主文档。改为：

1. 每个涉及仓库各自生成一份 repo-local delivery 文档。
2. 每份文档都包含同一个 `session_id`。
3. 每份文档都包含“关联仓库变更”章节，列出其他仓库的文档路径和 commit range。
4. 如 workspace 索引目录可版本化，再额外生成可选 workspace index；否则不生成集中主文档。

repo-local 文档示例：

```text
linezone_dazzle_backend_1/docs/delivery/2026-07-13/feature-order-flow-delivery.md
linezone_dazzle_frontend_1/docs/delivery/2026-07-13/feature-order-flow-delivery.md
```

两份文档都写：

```markdown
## 关联仓库变更

| repo | role | commit_range | delivery_doc |
|---|---|---|---|
| backend | 接口改动 | A..B | 当前文档 |
| frontend | 页面改动 | C..D | ../linezone_dazzle_frontend_1/docs/... |
```

这样既保证文档被各自仓库提交，又保留跨仓上下文。

## 文档模式配置

`workspace.local.json` 支持：

```json
{
  "docs_mode": "repo",
  "workspace_index": true
}
```

取值设计：

| `docs_mode` | 行为 |
|---|---|
| `repo` | 默认。文档生成到各子仓库自己的 `docs/` |
| `workspace-index` | repo 文档为主，workspace 只生成索引 |
| `workspace` | 仅当 workspace 根目录本身受 Git 管理时可用 |

首版默认 `repo`。

## 多仓库状态文件

workspace 模式下，`checkpoint.local.json` 不能只存一个 `last_ai_seen_commit`，必须按仓库存：

```json
{
  "workspace_root": "C:/Users/lzsj/all/pycharm_data/ai/fock/di_su",
  "repositories": {
    "backend": {
      "path": "linezone_dazzle_backend_1",
      "last_ai_seen_commit": "<commit>",
      "last_ai_delivery_commit": "<commit>"
    },
    "frontend": {
      "path": "linezone_dazzle_frontend_1",
      "last_ai_seen_commit": "<commit>",
      "last_ai_delivery_commit": "<commit>"
    }
  },
  "updated_at": "2026-07-13T16:30:00+08:00"
}
```

AI 下次接手时要逐仓库检查：

```text
git -C <repo_path> log <last_ai_seen_commit>..HEAD
```

如果某个仓库有人工未记录提交，只补录对应仓库；如果多个仓库都有未记录提交，逐仓库生成 repo-local 补录文档，并用同一个 `session_id` 和“关联仓库变更”章节互相引用。

## 数据协议

### current.local.json

AI 本次交付的结构化输入：

```json
{
  "type": "feature",
  "title": "修复邮件推送逻辑",
  "summary": "修复邮件推送触发条件，补充失败重试记录。",
  "reason": "原逻辑在部分订单状态下没有触发推送。",
  "changed_modules": ["mail", "order"],
  "affected_modules": ["notification", "order-status"],
  "risk_level": "medium",
  "risk_notes": "可能影响订单状态变更后的通知时机。",
  "doc_level": "full",
  "validation": ["运行单元测试", "人工检查推送入口"],
  "files": ["src/mail/push.py", "src/order/service.py"],
  "follow_up": ["观察线上失败率"],
  "ai_notes": "复用原有重试队列，没有新增调度器。"
}
```

必填字段：

```text
type
title
summary
changed_modules
risk_level
doc_level
validation
files
```

字段约束：

- `type` 只能是 `feature | bugfix | refactor | docs | config | test | hotfix | manual-backfill`。
- `risk_level` 只能是 `low | medium | high`。
- `doc_level` 只能是 `full | compact | skip`。
- `doc_level=skip` 时必须提供 `skip_reason`，并说明为什么本次无需长文档。
- `changed_modules` 必须是非空数组。
- `validation` 必须是非空数组。
- `files` 必须是非空数组。
- `files` 中的路径必须存在于仓库，或出现在当前 git diff / staged diff 中。
- JSON 文件大小设置硬上限，建议 256KB。

### session.local.json

AI session 状态：

```json
{
  "session_id": "20260713-143000-ai",
  "actor": "ai",
  "status": "active",
  "repo_id": "backend",
  "repo_root": "C:/workspace/project/backend",
  "started_at": "2026-07-13T14:30:00+08:00",
  "base_commit": "<commit>",
  "task_title": "修复邮件推送逻辑",
  "task_type": "bugfix"
}
```

字段约束：

- `session_id` 在一次 AI 任务内稳定；跨仓任务共用同一个 `session_id`。
- `actor` 首版只接受 `ai`。
- `status` 只能是 `active | finished`。
- `base_commit` 必须是当前仓库可解析 commit。
- active session 下 hook 才启用强制校验。

### checkpoint.local.json

AI 接手基线：

```json
{
  "last_ai_seen_commit": "<commit>",
  "last_ai_delivery_commit": "<commit>",
  "updated_at": "2026-07-13T15:00:00+08:00"
}
```

如果 `checkpoint.local.json` 不存在，首版策略：

- `ai_delivery_start.py` 把当前 `HEAD` 初始化为 `last_ai_seen_commit`；
- 输出 `initialized=true`；
- 不追溯更早历史，避免第一次安装就要求补全整个项目历史。

### prepared.local.json

`ai_delivery_prepare.py` 的产物清单，用于让 hook 判断“当前交付记录是否已经针对最新变更生成”：

```json
{
  "session_id": "20260713-143000-ai",
  "repo_id": "backend",
  "repo_root": "C:/workspace/project/backend",
  "doc_level": "full",
  "current_sha256": "<hash-of-current.local.json>",
  "prepared_at": "2026-07-13T15:20:00+08:00",
  "git_head": "<commit-or-null>",
  "changed_files": ["src/mail/push.py"],
  "delivery_doc": "docs/delivery/2026-07-13/bugfix-mail-push-delivery.md",
  "workflow_doc": "docs/ai-workflow/2026-07-13/bugfix-mail-push-ai-workflow.md"
}
```

校验规则：

- `current_sha256` 必须与当前 `current.local.json` 一致；否则说明 prepare 后又改过交付输入，hook 必须阻断。
- `delivery_doc` 必须存在；`workflow_doc` 在 `doc_level=skip` 时可为空，但必须有结构化 skip 记录。
- `changed_files` 必须覆盖当前 staged diff 或待推送 commit 范围中的 AI 变更文件。
- 如果 prepare 后又修改了代码，导致 changed files 不一致，hook 输出 `next_action=rerun_prepare`。

## 生命周期

### 1. 安装 skill 本体

安装由现有 `m2k-skills` 安装器负责，不由本 skill 脚本直接复制自身：

```text
Install-CodexSkill ai-delivery-hook
m2k-skills-tools install ai-delivery-hook
```

安装完成后应得到：

```text
<workspace>/.agents/skills/ai-delivery-hook/
```

### 2. 激活真实 Git 仓库

单仓库项目：

```bash
python <workspace>/.agents/skills/ai-delivery-hook/scripts/activate_project.py --repo-root <repo-root>
```

多仓库 workspace：

```bash
python <workspace>/.agents/skills/ai-delivery-hook/scripts/activate_project.py --workspace-root <workspace> --discover-repos
```

脚本做这些事：

1. 校验目标是 Git 仓库，或 workspace 下能发现 Git 子仓库。
2. 写入或更新 `activation.local.json`、`workspace.local.json`。
3. 创建 `.agents/skills/ai-delivery-hook/.gitignore`。
4. 对每个真实 Git 仓库增量写入 ai-delivery managed block。
5. 检测复杂 hook 体系；无法安全追加时返回 `requires_user_action=true` 和手动 snippet。
6. 不覆盖用户已有 hook，不默认设置 `core.hooksPath`。
7. 输出 JSON 结果。

### 3. Worker / AI 开始前检索历史留存

在真正改代码前，总编排或 AI 可以先检索历史交付记忆：

```bash
python <skill-root>/scripts/ai_delivery_search.py --repo-root <repo-root> --query "邮件推送 订单状态"
```

它只读取当前仓库的：

```text
<repo_root>/docs/delivery/
<repo_root>/docs/ai-workflow/
```

输出相似历史记录、涉及模块、风险提示和可参考程度。这个步骤不修改代码，也不创建 active session；它用于辅助方案设计。

### 4. AI 开始任务

准备进入代码修改前执行：

```bash
python <skill-root>/scripts/ai_delivery_start.py --repo-root <repo-root> --title "修复邮件推送逻辑" --type bugfix
```

脚本做这些事：

1. 初始化或读取 `checkpoint.local.json`。
2. 检查 `last_ai_seen_commit..HEAD` 是否存在未补录提交。
3. 创建 active `session.local.json`，写入 `session_id`、`base_commit`、`task_title`、`task_type`。
4. 输出是否需要先补录人工变更。

如果发现人工未记录提交，输出：

```json
{
  "ok": false,
  "requires_manual_backfill": true,
  "commits": ["<commit>"],
  "message": "检测到上次 AI 接手后存在人工提交，需要先补录。",
  "next_action": "生成 manual-backfill 类型 current.local.json 后运行 ai_delivery_prepare.py。"
}
```

### 5. AI 修改代码

AI 正常读取代码、修改代码、验证。这个过程不由本 skill 细写步骤，交给模型、总编排和其他专业 skill。

边界：如果最终没有代码变更，应调用 finish 的 `abandoned` 或 `no-code` 状态关闭 session，不留下伪交付文档。

### 6. AI 准备交付留存

AI 写入或更新：

```text
<workspace>/.agents/skills/ai-delivery-hook/current.local.json
```

然后执行：

```bash
python <skill-root>/scripts/ai_delivery_prepare.py --repo-root <repo-root>
```

脚本做这些事：

1. 校验 active `session.local.json`。
2. 校验 `current.local.json` schema 和 `doc_level`。
3. 读取 git changed files / staged files。
4. 按 `doc_level` 生成 repo-local 文档。
5. 写入 `prepared.local.json`，记录 current hash、文档路径、changed files。
6. 写审计日志。
7. 输出生成路径和下一步。

### 7. commit / push 校验

真实 Git hook 调用：

```bash
python <skill-root>/scripts/check_ai_delivery.py --repo-root <repo-root> --skill-root <skill-root> --mode pre-commit
python <skill-root>/scripts/check_ai_delivery.py --repo-root <repo-root> --skill-root <skill-root> --mode pre-push
```

没有 active AI session：直接 `ok=true` 放行。

存在 active AI session：校验 `current.local.json`、`prepared.local.json` 和生成文档是否存在、是否与当前变更匹配。失败则阻断，并输出具体 `next_action`。

### 8. AI 完成任务

commit 成功后执行：

```bash
python <skill-root>/scripts/ai_delivery_finish.py --repo-root <repo-root> --status completed
```

脚本做这些事：

1. 校验本次交付文档存在。
2. 读取最新 `HEAD`，确认本次提交已经完成。
3. 更新 `checkpoint.local.json.last_ai_seen_commit` 为当前 `HEAD`。
4. 更新 `last_ai_delivery_commit`。
5. 将 `session.local.json` 标记 finished 或删除。
6. 写审计日志。

如果任务中途取消：

```bash
python <skill-root>/scripts/ai_delivery_finish.py --repo-root <repo-root> --status abandoned
```

取消状态不得更新 `last_ai_delivery_commit`，但可以清理 active session，避免后续人工提交被误判为 AI session。

## Worker / 总编排接入协议

`ai-delivery-hook` 不吞并 `work-orchestrator`，也不替代 `git-trunk-workflow`。它只提供“AI 代码交付留存围栏”和“历史交付记忆检索”。

总编排接入建议：

| 阶段 | 总编排动作 | 调用 |
|---|---|---|
| Intake / Evidence | 查询历史交付记忆，辅助判断是否做过类似修改 | `ai_delivery_search.py` |
| Plan 后、Execute 前 | 用户授权实施且即将改代码时，开启 AI session | `ai_delivery_start.py` |
| Execute | 正常修改代码，不由本 skill 接管 | 无 |
| Verify 后、Git 交付前 | 写 `current.local.json` 并生成留存文档 | `ai_delivery_prepare.py` |
| Git commit / push | 由 Git hook 被动校验，不替代 Git skill | `check_ai_delivery.py` |
| Handoff 后 | 提交完成后关闭 session、更新 checkpoint | `ai_delivery_finish.py` |

与 `git-trunk-workflow` 和托管平台 MCP 的关系：

- 分支创建、显式暂存、commit、push 仍由 `git-trunk-workflow` 负责。
- `ai-delivery-hook` 必须在暂存/commit 前完成 prepare，确保文档也被纳入本次显式暂存范围。
- 如果 `git-trunk-workflow` 因工作区不干净或路径不明确而阻断，`ai-delivery-hook` 不得绕过它。
- 如果 `ai-delivery-hook` 因缺少留存而阻断，`git-trunk-workflow` 不得改用原生 Git 兜底。
- GitHub/GitLab/Gitee 的 PR/MR、issue、CI、review 等平台对象优先交给对应 MCP，但平台 MCP 不得替代本地 Git 围栏。

总编排的关键约束：**只要进入 AI 代码实施，就必须显式开启 session；只要准备提交 AI 变更，就必须显式 prepare；不能只依赖模型记忆。**

## 人工临时变更补录机制

### 场景

1. AI 上次完成任务，`checkpoint.local.json.last_ai_seen_commit = A`。
2. 用户自己紧急修改代码并 commit，产生提交 `B`。
3. 用户没有运行 AI 交付流程。
4. 下一次 AI 开始任务时，当前 `HEAD = B`。

### 检测

`ai_delivery_start.py` 执行：

```text
git log A..HEAD
```

发现 `B`。

### 处理方式

首版支持两种处理策略，由 AI 根据上下文选择：

1. **单独补录**：生成 `manual-backfill` 类型文档，记录人工提交内容、影响范围、AI 接手判断。
2. **纳入本次交付**：在本次 delivery 文档增加“接手前人工变更”章节，说明这些提交如何影响本次任务。

推荐默认使用“单独补录”。原因：人工变更和 AI 本次交付责任边界更清晰。

补录文档示例路径：

```text
<repo_root>/docs/delivery/YYYY-MM-DD/manual-backfill-<short-sha>-delivery.md
```

补录文档必须包含：

- 人工 commit 范围；
- 涉及文件；
- AI 对变更目的的判断；
- 可能影响模块；
- 是否影响本次 AI 任务；
- 是否需要补充验证。

## 文档分级策略

为避免每次小改都生成长文档，首版引入 `doc_level`：

| `doc_level` | 适用场景 | 生成内容 | hook 要求 |
|---|---|---|---|
| `full` | 需求、bugfix、hotfix、跨模块/跨仓改动、有行为变化的重构 | delivery + workflow 两份文档，章节完整 | 必须有 delivery 和 workflow |
| `compact` | 小范围修复、文案、样式、配置、小测试补充 | delivery 完整但内容精简；workflow 可生成短版 | 必须有 delivery，workflow 建议生成 |
| `skip` | 纯格式化、无行为变化、仅补注释、无交付价值的小调整 | 只生成结构化 skip 记录 | 必须有 `skip_reason`，不得完全无记录 |

### `full`

`full` 是默认等级，必须回答：

- 为什么改；
- 改了哪些模块；
- 影响哪些模块；
- 有哪些风险；
- 如何验证；
- 后续开发是否应参考这份文档。

### `compact`

`compact` 仍然生成 repo-local delivery 文档，但正文可以短。必须包含：

- 摘要；
- 变更文件；
- 行为影响；
- 验证方式；
- 是否需要后续参考。

### `skip`

`skip` 不是“不留记录”，而是“留最小记录”。必须包含：

- `skip_reason`；
- 变更文件；
- 为什么没有行为变化；
- 如何确认不会影响业务；
- AI 判断的不确定部分。

`skip` 不能用于以下场景：

- bugfix / hotfix；
- 修改权限、订单、财务、支付、数据写入逻辑；
- 跨仓或跨模块变更；
- 任何需要用户或测试人员验证的行为变化。

## 生成文档格式

### delivery 文档

用于后续开发人员或 AI 判断“这个模块之前发生过什么”。

建议结构：

```markdown
# <title> 交付留存

## 归纳

## 参考判断

## 变更背景

## 变更范围

## 影响范围

## 风险与注意事项

## 验证记录

## 后续事项

## 关联文件

## AI 接手前人工变更（可选）
```

“参考判断”是关键章节，必须直接回答：

- 后续开发是否应该参考本文档？
- 哪些模块变更时需要回看本文档？
- 改其他模块是否可能影响当前模块？
- 本文档不能作为依据的部分是什么？

### AI workflow 文档

用于记录 AI 协作过程，而不是业务交付本身。

建议结构：

```markdown
# <title> AI 工作流留存

## 任务入口

## AI Session

## 关键判断

## 使用的上下文

## 执行过的验证

## 未覆盖风险

## 人工变更接手情况
```

workflow 文档不追求详尽复盘每一步对话，只记录未来有价值的判断依据。

## 脚本职责

### ai_delivery_common.py

公共能力：

- repo root 解析；
- Git 命令封装；
- JSON 读取 / 写入；
- schema 校验；
- slug 生成；
- 路径安全检查；
- 审计日志；
- JSON 输出协议。

围栏：

- 拒绝 repo root 外路径；
- JSON 文件大小上限；
- Git 命令超时；
- 运行态输出固定在 `.agents/skills/ai-delivery-hook/` 下；交付文档固定在目标 `repo_root/docs/` 下；
- 所有脚本输出 JSON。

### activate_project.py

负责把已安装的 skill 增量激活到一个或多个真实 Git 仓库。

输入：

```text
--repo-root
--workspace-root
--discover-repos
--mode append-existing|managed-hooks-path|manual
```

输出重点：

```text
ok
activated_repos
requires_user_action
snippet
activation_path
next_action
```

### doctor.py

负责本地体检，不修改文件。

检查项：

- 当前 workspace 下有哪些 Git 仓库；
- 哪些仓库已激活 ai-delivery managed block；
- 哪些仓库 hook 无法安全追加；
- `core.hooksPath` 是否指向不存在目录；
- `skill_root` 是否可解析；
- repo-local `docs/` 是否存在、是否在 Git 仓库内；
- 是否存在 active session、过期 session、未补录人工提交；
- 当前 skill 版本和 activation metadata 是否一致。

输出重点：

```text
ok
status=ok|warning|blocked
checks
next_action
```

### ai_delivery_search.py

负责在当前 repo 的历史留存文档中做轻量检索，只读不写。

输入：

```text
--repo-root
--query
--limit
```

行为：

- 读取 `<repo_root>/docs/delivery/` 和 `<repo_root>/docs/ai-workflow/`；
- 按标题、模块、文件路径、关键词做本地文本匹配；
- 返回可参考文档、相关模块、风险提示；
- 不访问外部服务，不修改文件。

### ai_delivery_start.py

负责开启 AI session 和接手检查。

输入：

```text
--repo-root
--title
--type
```

输出重点：

```text
ok
requires_manual_backfill
session_path
base_commit
unrecorded_commits
next_action
```

### ai_delivery_prepare.py

负责根据 `current.local.json` 生成交付文档。

输入：

```text
--repo-root
--mode normal|manual-backfill
```

输出重点：

```text
ok
doc_level
delivery_doc
workflow_doc
prepared_path
validated_files
next_action
```

### check_ai_delivery.py

负责 hook 校验。

输入：

```text
--repo-root
--skill-root
--mode pre-commit|pre-push|ai-start
```

行为：

- 无 active AI session：放行。
- 有 active AI session：严格校验 `current.local.json`、`prepared.local.json` 和生成文档。
- `prepared.local.json` 的 current hash 或 changed files 过期：阻断并提示重新 prepare。
- 缺失留存：阻断并输出下一步。

### ai_delivery_finish.py

负责关闭 AI session 和更新接手基线。

输入：

```text
--repo-root
--status completed|abandoned|no-code
```

行为：

- 校验交付文档存在；
- 更新 `checkpoint.local.json`；
- 删除或 finish `session.local.json`；
- 写审计日志。

## Hook 策略

### pre-commit

伪逻辑：

```text
if no active session:
  pass
else:
  validate current.local.json
  validate prepared.local.json
  validate generated delivery docs
  validate staged changed files are covered
  pass or block
```

### pre-push

伪逻辑：

```text
if no active session:
  pass
else:
  validate session can be finished
  validate prepared.local.json still matches current input
  validate delivery docs exist
  validate no missing AI delivery record
  pass or block
```

### 为什么不用 commit author 判断

不依赖 Git author / email 区分 AI 和人。

原因：

- AI 可能使用用户本机 Git 配置；
- 用户也可能使用自动化账号；
- commit author 不代表变更发起者；
- 这种判断不可移植。

active AI session 是更明确的本地意图信号。

## SKILL.md 设计

`SKILL.md` 保持短，只写：

```text
## 围栏（代码强制，不可绕过）
- active AI session 下必须有 current.local.json
- current.local.json 必须通过 schema 校验
- prepare 后必须生成 prepared.local.json
- AI session 下 commit/push 必须存在 repo-local 交付文档
- ai-start 必须检测 last_ai_seen_commit..HEAD 的人工未记录提交
- hook 无 active session 时不得阻断人工提交
- 所有脚本输出 JSON 并写审计

## 脚本入口
- activate_project.py
- doctor.py
- ai_delivery_search.py
- ai_delivery_start.py
- ai_delivery_prepare.py
- check_ai_delivery.py
- ai_delivery_finish.py

## 围栏以内（AI 自由发挥）
- 如何描述变更
- 如何判断影响模块
- 如何总结风险
- 如何决定人工变更单独补录还是纳入本次交付
```

不在 `SKILL.md` 写详细流程、话术模板、示例文档正文。

## references 设计

### delivery_schema.md

记录 `current.local.json`、`prepared.local.json`、`session.local.json`、`checkpoint.local.json` 的字段、枚举、必填规则。

### state_files.md

记录 `.agents/skills/ai-delivery-hook/` 下文件的生命周期、是否建议提交、初始化策略。

### generated_docs.md

记录生成文档的章节和每个章节的判定用途。

### hook_policy.md

记录 hook 只检查不生成、active session 才阻断、人工提交放行、增量接入优先的规则。

### doc_levels.md

记录 `full | compact | skip` 的适用条件、禁止使用 skip 的场景、每种等级生成哪些文档。

### orchestrator_integration.md

记录总编排在 Intake、Execute、Verify、Handoff 阶段如何调用 search/start/prepare/finish。

这些都是事实性协议，适合放 references；不写模型话术。

## 测试设计

`test_ai_delivery.py` 覆盖这些场景：

### 激活与 doctor 场景

- 单 Git 仓库执行 `activate_project.py --repo-root`，成功追加 managed block。
- 多仓 workspace 执行 `activate_project.py --workspace-root --discover-repos`，逐仓库激活。
- 重复激活只替换 managed block，不重复追加。
- 已有普通 hook 时，只追加受管区块，不改区块外内容。
- 检测到复杂 hook 管理器时返回 `requires_user_action=true`。
- `doctor.py` 能发现未激活仓库、无效 hooksPath、缺失 skill_root、过期 session。

### 通过场景

- 无 session 时 pre-commit 放行。
- 无 session 时 pre-push 放行。
- active session + 合法 `current.local.json` + `prepared.local.json` + 已生成文档时放行。
- 首次安装无 `checkpoint.local.json` 时初始化成功。
- 人工提交被检测后，manual-backfill 文档生成成功。
- `doc_level=full` 生成 delivery + workflow。
- `doc_level=compact` 生成精简 delivery，workflow 可短版。
- `doc_level=skip` 在合法 skip reason 下生成最小记录。
- `ai_delivery_search.py` 只读检索 repo-local 历史文档。

### 阻断场景

- active session 下缺少 `current.local.json`。
- `current.local.json` 非法 JSON。
- 缺少必填字段。
- `risk_level` 不在枚举内。
- `doc_level` 不在枚举内。
- `doc_level=skip` 缺少 `skip_reason`。
- bugfix / hotfix / 跨仓场景使用 `doc_level=skip`。
- `validation` 为空。
- `files` 引用 repo 外路径。
- active session 下缺少 `prepared.local.json`。
- `prepared.local.json.current_sha256` 与当前 `current.local.json` 不一致。
- active session 下缺少 delivery 文档。
- active session 下 staged files 未被 `current.local.json` 或 `prepared.local.json` 覆盖。

### 边界场景

- `current.local.json` 超过大小上限。
- `last_ai_seen_commit` 不存在或不可解析。
- Git 仓库没有 commit。
- HEAD detached。
- 合并提交出现在人工未记录范围。
- 文件被删除但仍在 diff 中。
- 文件重命名。
- prepare 后又新增修改，hook 要求重新 prepare。
- workspace 根目录不是 Git 仓库，但子仓库可被发现。

测试使用临时 Git 仓库，不依赖外部服务，不写用户真实仓库。

## Manifest 和版本

新增 manifest 条目：

```json
"ai-delivery-hook": {
  "path": "skills/ai-delivery-hook",
  "version": "0.1.0",
  "description": "AI 参与代码交付时的留存围栏：active AI session 下强制校验 current.local.json 和交付文档；人工提交不阻断，下次 AI 接手时检测并补录未记录人工变更。",
  "tags": [
    "ai",
    "delivery",
    "documentation",
    "git-hooks",
    "audit",
    "workflow"
  ],
  "requires": [
    "python",
    "git"
  ]
}
```

首版版本号：`0.1.0`。

## README 更新

仓库 README / README_cn 后续增加一行能力说明即可，不展开完整使用说明：

```text
ai-delivery-hook：AI 参与代码交付时生成结构化交付留存，并在 AI 下次接手时发现人工临时提交。
```

## 验证命令

实现完成后至少运行：

```bash
python skills/ai-delivery-hook/scripts/test_ai_delivery.py
python skills/skill-dev/scripts/validate_skill_repo.py --repo-root . --skill ai-delivery-hook
python -m json.tool manifest.json
```

如果实现包含 Python 脚本语法检查，注意清理 `__pycache__`。

## 风险与取舍

### 风险 1：AI 忘记 start session

如果 AI 没有执行 `ai_delivery_start.py`，hook 不会强制。

取舍：这是首版最大软肋。缓解方式不是让 hook 猜测所有提交，而是让总编排在进入代码实施前显式调用 start，并让 `doctor.py` 能发现疑似过期 session、未补录提交和未激活仓库。

### 风险 2：checkpoint.local.json 不提交导致多机器断点不一致

默认本地状态在多机器间不共享。

取舍：首版优先减少业务仓库噪音。后续可增加项目配置：`state_mode=tracked|local`。如果团队确实多机器频繁接手，再考虑提交受控 checkpoint 或生成 repo-local checkpoint 文档。

### 风险 3：人工变更目的无法准确判断

AI 只能根据 commit diff 和上下文推断人工变更目的。

取舍：补录文档必须明确“AI 判断依据”和“不确定部分”，不能伪装成用户真实意图。无法判断时应标记 `requires_human_confirmation=true`。

### 风险 4：hook 接入影响已有 hook 体系

目标项目可能已有 hooksPath、Husky、lint-staged、pre-commit framework 或手写 hook。

取舍：`activate_project.py` 必须采用增量接入优先策略。能追加受管区块就追加；检测到复杂 hook 管理器时输出 `requires_user_action=true` 和手动接入片段；禁止覆盖原 hook。原则是：宁可本 skill 激活失败，也不能破坏原 hook 行为。

### 风险 5：文档生成太重影响交付速度

如果每次小改都要求长文档，会降低使用意愿。

取舍：通过 `doc_level=full|compact|skip` 分级。`skip` 只能用于无行为变化的小改，并且仍需最小结构化记录；bugfix、hotfix、跨仓、权限/数据/订单/支付等场景禁止 skip。

### 风险 6：repo-local 文档未被纳入提交

即使文档生成到 `<repo_root>/docs/`，AI 或 Git 流程仍可能只暂存代码，忘记暂存文档。

取舍：`prepared.local.json` 记录 delivery/workflow 路径；hook 在 active session 下校验文档存在并位于当前 repo。最终是否暂存由 `git-trunk-workflow` 显式路径控制；总编排必须把生成文档路径交给 Git 交付步骤。

### 风险 7：`--no-verify` 可以绕过本地 hook

Git 本地 hook 天然可被 `git commit --no-verify` 绕过。

取舍：首版只做本地围栏，不做远端 CI 强制。后续如需更硬约束，可在 AI 分支或带 `AI-Delivery: required` trailer 的提交上做 CI 校验，避免误伤人工提交。

### 风险 8：过期 prepared 导致误放行

AI prepare 后又继续改代码，如果 hook 只检查文档存在，可能误放行旧文档。

取舍：引入 `prepared.local.json`，保存 `current_sha256` 和 `changed_files`。hook 必须校验 current hash 与 staged/待推送文件范围；不一致就要求重新运行 prepare。

## 实施阶段拆分

### Phase 1：核心围栏可用

- 创建 skill 目录和 references。
- 实现 `activate_project.py`，支持 repo-root、workspace-root、增量 managed block。
- 实现 `doctor.py`，只读检查激活状态和本地风险。
- 实现 `ai_delivery_search.py`，只读检索 repo-local 历史留存文档。
- 实现 JSON schema 校验：`current.local.json`、`prepared.local.json`、`session.local.json`、`checkpoint.local.json`。
- 实现 session start / prepare / finish。
- 实现 check 脚本，校验 active session、prepared hash、repo-local 文档和 changed files。
- 支持 `doc_level=full|compact|skip`。
- 生成 repo-local delivery / workflow 文档。
- 写临时 Git 仓库测试。
- 更新 manifest / README。

### Phase 2：补录与多仓增强

- 更细致的 commit 范围分析。
- 支持把人工变更纳入本次交付或单独补录。
- 多仓任务逐仓库生成 repo-local 文档，并通过 session_id 互链。
- 支持 `state_mode=tracked|local`。
- 增强合并提交、删除文件、重命名文件处理。
- workspace index 仅作为可选索引，不作为主文档。

### Phase 3：总编排接入

- 让 `work-orchestrator` 在 Intake / Evidence 阶段调用 `ai_delivery_search.py`。
- 在用户授权实施且即将改代码前调用 `ai_delivery_start.py`。
- 在 Git 交付前调用 `ai_delivery_prepare.py`，并把生成文档路径交给 Git 交付步骤显式暂存。
- 在 commit 完成后调用 `ai_delivery_finish.py`。
- 根据真实遗漏事故决定是否增加 CI 级别校验。

首版建议做到 Phase 1，并为 Phase 2 / Phase 3 保留接口；如果要与总编排马上形成闭环，Phase 3 的调用协议可以先写入 `work-orchestrator` 文档，但不必让本 skill 吞并总编排。

## 最终结论

`ai-delivery-hook` 应该被设计成 AI 代码交付的工程围栏，而不是通用 commit 文档强制器。

核心规则是：

```text
人工提交不阻断。
AI session 下强制留存。
AI 下次接手必须发现人工未记录提交。
补录人工变更，或显式纳入本次交付。
```

这个设计同时满足两件事：

1. 用户可以在紧急情况下自己修代码、自己提交，不被 AI 工具链卡住。
2. AI 下一次接手时不会忽略人工临时变更，能把它们纳入项目历史和影响判断。

这也是首版最重要的边界：**强制 AI 负责 AI 做过的事，同时让 AI 记住人临时做过的事。**

## 同日补充：数据库查询与 Git 平台对象的 MCP 优先

今天重新评估 `postgres-query` 后，判断它不是要废弃，而是要改变默认入口：数据库 MCP 能更自然地处理日常查询、结构查看和结果返回；`postgres-query` 继续承担本地受控脚本、围栏审计和无 MCP 场景。

后续策略：

1. 日常数据库查询、结构查看和结果返回优先配置数据库 MCP。
2. `postgres-query` 仍在使用；当没有 MCP、用户明确要求本地脚本、或需要 `sql_guard.py`、脱敏、审计、行数/超时硬上限时继续使用。
3. `work-orchestrator` 的数据库路由调整为“MCP 优先，本地受控脚本可用”。
4. GitHub/GitLab/Gitee 的 issue、PR/MR、review、CI、release 等平台对象优先走对应 MCP。
5. 本地分支、显式暂存、commit、push 仍由 `git-trunk-workflow` 负责，不能用 MCP 绕过保护分支、禁 force push 和审计围栏。