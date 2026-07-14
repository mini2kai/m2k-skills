# Document Levels

## full

适用：需求、bugfix、hotfix、跨模块、跨仓、有行为变化的重构。

生成：

- delivery 文档
- AI workflow 文档

必须记录背景、范围、影响、风险、验证和参考判断。

## compact

适用：小范围修复、小配置、小样式、小文案、小测试补充。

生成：

- 精简 delivery 文档
- 短 workflow 文档

仍需记录变更文件、行为影响、验证方式和是否需要后续参考。

## skip

适用：纯格式化、无行为变化、仅补注释等低风险小改。

规则：

- 必须有 `skip_reason`
- 必须生成最小 delivery 记录
- workflow 文档可为空

禁止用于：

- `bugfix`
- `hotfix`
- 跨仓任务
- `risk_level=high`
- 权限、订单、财务、支付、数据写入等高风险逻辑
