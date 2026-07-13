# Generated Docs

## Delivery 文档

路径：

```text
<repo_root>/docs/delivery/YYYY-MM-DD/<slug>-delivery.md
```

用途：给后续开发人员或 AI 判断模块历史、影响范围和风险。

核心章节：

- 归纳
- 参考判断
- 变更背景
- 变更范围
- 影响范围
- 风险与注意事项
- 验证记录
- 后续事项
- 关联文件
- AI Session
- AI 接手前人工变更（可选）

## AI workflow 文档

路径：

```text
<repo_root>/docs/ai-workflow/YYYY-MM-DD/<slug>-ai-workflow.md
```

用途：记录 AI 协作判断，不追求完整对话复盘。

核心章节：

- 任务入口
- AI Session
- 关键判断
- 使用的上下文
- 执行过的验证
- 未覆盖风险
- 人工变更接手情况

## skip 记录

`doc_level=skip` 时仍生成最小 delivery 记录，并必须说明 `skip_reason`。workflow 文档可为空。
