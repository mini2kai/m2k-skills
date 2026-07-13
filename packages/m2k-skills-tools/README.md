# m2k-skills-tools

漂亮的终端管理工具，用于安装、更新、查看和诊断 [mini2kai/m2k-skills](https://github.com/mini2kai/m2k-skills) 仓库中的 skills。

无参数启动会进入全屏 TUI，并先选择安装目标目录。顶部 Logo 常驻，左侧菜单切换页面，右侧显示当前页面内容。`←` / `→` 切换左右区域，`↑` / `↓` 移动选中项，`Space` 用 `□` / `✓` 勾选，`Enter` 确认，`/` 聚焦筛选框，`b` 返回首页，`r` 刷新，`q` 退出。Tab 已禁用，统一使用方向键。选择目标目录后会后台预加载安装状态和环境检查；manifest/status/doctor 在当前 TUI 会话内缓存，按 `r` 强制刷新。安装/更新合并为一个页面，第一项支持全选/取消全选，每个 skill 下方显示简介和依赖，状态固定显示在右侧；安装/更新、详情、配置列表支持按名称、状态、描述、标签和依赖筛选；未安装项选中后安装，非最新项选中后更新，最新项不可选。安装/更新过程会显示下载、解压、复制文件、恢复配置等进度和日志。

```powershell
uvx --from m2k-skills-tools m2k-skills-tools
uvx --from m2k-skills-tools m2k-skills-tools status --target codex
uvx --from m2k-skills-tools m2k-skills-tools add ai-worklog --target claude
```

本仓库开发调试时可以直接运行：

```powershell
uv run --project packages/m2k-skills-tools m2k-skills-tools status --target codex
```

本地长期试用可以安装为 uv tool：

```powershell
uv tool install -e packages/m2k-skills-tools
m2k-skills-tools --target codex
```

## Features

- 中文交互式菜单和漂亮终端输出。
- 支持 Codex、Claude、当前目录和自定义绝对目录。
- 显示本地安装状态、安装时间、本地版本和线上版本。
- 选择目标目录后在首页后台预热安装状态和环境检查，进入页面后优先使用会话缓存。
- 安装/更新合并为统一操作页，支持全选/取消全选；最新项不可选，状态固定显示在右侧。
- 安装/更新、详情、配置列表支持 `/` 聚焦筛选框并按名称、状态、描述、标签和依赖筛选。
- 每个 skill 选项下方展示简介和依赖。
- 安装和更新时自动备份旧目录，并恢复 `*.local.json` / `*.local.jsonc` 本地配置。
- 打开已安装 skill 的配置文件或所在目录。
- 检查 Python、uv、Git、PowerShell、Node、npx 和 GitHub manifest 访问状态。

## Commands

```powershell
m2k-skills-tools
m2k-skills-tools status
m2k-skills-tools add ai-worklog
m2k-skills-tools update all
m2k-skills-tools info ai-worklog
m2k-skills-tools config ai-worklog
m2k-skills-tools doctor
```
