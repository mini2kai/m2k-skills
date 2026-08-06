# 2026-08-05 Worker Author Story 交付故事日志设计

## 背景

`work-orchestrator` 已经承担中文总控编排职责：Intake、Evidence、Plan、Execute、Verify、Handoff。此前交付留存主要依赖 `git-trunk-workflow` 的中文详细 commit，复杂需求可按需生成 `docs/delivery/` 文档。

新的实际需求是：每完成一次提交、一次 AI 临时分支交付，或一个较大的需求收口后，需要像日志一样长期记录“这次到底干了什么、从哪个分支迁出、提交到了哪里、是否 push、是否合回、上下游影响是什么”。这类记录要能被人直接阅读，也要能被后续 AI 接手时检索。

## 设计结论

不把历史日志写进 Skill 目录。Skill 目录只保存能力定义，历史日志是项目资产，应由 `work-orchestrator` 在 Handoff 阶段维护到目标项目或仓库中。

默认项目结构：

```text
.worker_author_story/
  INDEX.md
  branch-flow.csv
  logs/
    YYYY-MM.md
```

采用“轻索引 + CSV 分支流水账 + 按月详细日志”，而不是无限追加单个大文件。

## 文件职责

### INDEX.md

`INDEX.md` 是长期入口，只维护轻量索引：日期、需求/任务、类型、仓库、工作分支、状态和日志链接。

它解决“我要快速知道历史做过什么、应该去哪个月日志看详情”的问题。

### branch-flow.csv

`branch-flow.csv` 用 Excel 友好的方式记录分支流程。推荐字段：

```csv
story_id,created_at,requirement,type,repo,source_branch,work_branch,baseline_commit,commits,pushed,merge_status,merge_target,merge_commit,merged_at,log_file,note
```

它解决“以后大批量分支或需求并行时，分不清哪个 AI 分支从哪来、有没有合回”的问题。

`merge_status` 使用：

- `not_merged`
- `merged`
- `unknown`
- `not_applicable`

开始新分支或交付收口时，可以读取该 CSV，检查历史 `not_merged` 分支；如果能通过 Git 证据确认目标分支已包含对应 commit，再更新为 `merged`。

### logs/YYYY-MM.md

`logs/YYYY-MM.md` 按月追加详细交付故事。每个需求或提交新增一个章节，记录：

- 交付结论；
- 需求背景；
- 本次完成内容；
- 修改范围；
- 上游影响；
- 下游影响；
- SQL / 配置 / rollback；
- 验证记录；
- 风险和后续事项；
- 分支流程记录。

## 触发规则

必须维护 Worker Author Story 的场景：

- 用户明确要求“记录一下”“写交付日志”“写修改说明”“需求收口”“长期留存”“按提交生成文档”；
- 完成一个明确需求或较大任务，并产生 Git commit；
- 创建 AI 临时分支、push 临时分支，或需要记录分支是否合回；
- 涉及 SQL / rollback、配置、业务参数、数据链路、模型/跑批、上下游接口；
- 跨仓修改、hotfix、UAT/线上问题、高风险或复杂业务链路。

不默认写日志的场景：纯咨询、只读查询、无代码修改、单文件小 typo 且无 commit、用户明确说不要记录。

## 与现有 Skill 的职责边界

- `work-orchestrator`：判断是否触发、组织上下文、维护 `.worker_author_story/`。
- `ai-delivery-hook`：继续只读检索历史和 commits since；可以检索 `.worker_author_story/`，但不写日志。
- `git-trunk-workflow`：如果 `.worker_author_story/` 需要入库，负责显式暂存、中文 commit、push 和受控清理。

## 关键取舍

### 为什么不是一个无限大的 Markdown

单文件日志符合直觉，但长期会带来 Git 冲突、AI 读取困难、表格难维护和历史状态难更新的问题。按月拆分详细日志，可以控制文件大小；`INDEX.md` 和 `branch-flow.csv` 保留总览能力。

### 为什么不写进 Skill 目录

Skill 目录是能力实现资产，不是项目交付资产。写进 Skill 目录会导致不同项目历史混杂，也可能在 Skill 更新、重装、同步时丢失。

### 为什么不用 hook 强制

写日志是模型在 Handoff 阶段能完成的编排行为，不需要重新引入本地 Git hook 阻断。强制证据链如果未来确实需要，应放到 CI 层，而不是本地 hook。