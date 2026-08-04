---
name: skill-dev
description: 中文 Codex skill 开发、更新、版本管理、验证、GitHub 和 PyPI 发布流程。Use when the user asks to create, update, standardize, validate, version, package, document, install, publish, or sync a skill in the m2k-skills repository; when manifest.json, README.md, m2k-skills-tools, PyPI, uv publish, references, scripts, validation, git commit, or GitHub push are involved.
---

# Skill Dev

## 设计理念

所有 skill 的开发和优化遵循围栏模型。详见 `references/design_philosophy.md`。

核心判断：

- **脚本强制执行的，留。给 AI 看的说明文字，删。**
- 围栏用代码保证（raise/exit/硬上限），AI 无法绕过
- 围栏以内完全信任模型能力
- 如果删掉后模型能自己完成，就删
- 外部接口易变时，保留稳定围栏和动态发现入口，不把 API/CLI 参数细节写死

每个 skill 必须有：

| 文件 | 作用 | 受众 |
|---|---|---|
| `SKILL.md` | 围栏规则 + 脚本入口 + 自由区（40-60 行） | AI |
| `DESIGN.md` | 设计理念、实现思路、刻意删掉了什么 | 人 |
| `scripts/` | 围栏代码 + `test_*.py` | 代码 |
| `references/` | 事实性配置/格式说明 | AI 按需读取 |

## 标准流程

1. **识别围栏**：这个 skill 需要代码强制什么？硬上限是什么？
2. **识别自由区**：哪些事交给模型？
3. **实现围栏**：独立模块、零外部依赖、可复用、有审计
4. **写测试**：`scripts/test_*.py`，覆盖通过/拦截/边界
5. **写 SKILL.md**：只有围栏 + 入口 + 自由区
6. **写 DESIGN.md**：给人看的完整设计记录
7. **同步 manifest.json + README.md**：版本递增
8. **验证**：`python scripts/test_*.py` + `python -m json.tool manifest.json`
9. **提交/推送**：需用户确认

## 脚本入口

```bash
python scripts/skill_preflight.py --repo-root <path> --skill <name>
python scripts/sync_manifest.py --repo-root <path> --skill <name> --bump patch
python scripts/sync_package_version.py --repo-root <path> --bump minor
python scripts/validate_skill_repo.py --repo-root <path> --skill <name>
```

## 规则导航

- **设计理念**：`references/design_philosophy.md`
- skill 格式：`references/skill_format.md`
- 仓库约定：`references/repository_conventions.md`

## 安全底线

- 不写入密钥、token、cookie、数据库凭据
- 不提交 `.env`、凭据、`__pycache__`
- 不回退用户已有改动
- 不执行破坏性 Git 操作
- commit/push/PyPI 发布前需用户确认
