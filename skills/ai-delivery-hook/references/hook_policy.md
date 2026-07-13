# Hook Policy

## 强制条件

只在 active AI session 下强制：

```json
{
  "actor": "ai",
  "status": "active"
}
```

没有 active session 时：

- `pre-commit` 放行
- `pre-push` 放行
- 不要求 current/prepared/docs

## Hook 只检查，不生成

Git hook 不生成文档、不暂存文件、不修改用户文件。缺失时只阻断并输出下一步命令。

## 增量接入

`activate_project.py` 默认只追加 managed block：

```sh
# BEGIN ai-delivery-hook managed
...
# END ai-delivery-hook managed
```

重复激活时只替换 managed block 内部，不修改区块外内容。

## 复杂 hook

检测到 Husky、lint-staged、pre-commit framework、lefthook 等复杂 hook 管理器时，不自动修改，输出 `requires_user_action=true` 和 snippet。

## 不使用 commit author

不通过 Git author/email 判断 AI 或人工，因为 AI 可能使用用户本机 Git 配置，author 不是可靠来源。
