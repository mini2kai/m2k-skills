# Discussions

[中文版](./README_cn.md)

This directory records open discussions before they become stable design decisions. Entries are ordered by timestamp and may later be distilled into `thoughts/`, skill design documents, or installation docs.

## 2026-07-14 14:10:19 +0800 | Can general Git MCPs replace the local Git skill?

### Background

Moving database access from local `postgres-query` scripts toward database MCP has noticeably improved the daily experience: access is more direct, queries feel smoother, and the trade-off of losing some local script features such as local logs and script-level audit can be acceptable for normal use.

The next question is whether version-control workflows can follow the same path: MCP-first, or even replacing `git-trunk-workflow` with a general Git/version-control MCP.

### Questions

1. Can the current version-management skill be optimized into MCP?
   - Survey mature Git / GitHub / GitLab / Gitee MCP servers.
   - Identify which capabilities fit MCP: local Git, remote issues, PR/MR, review, CI, releases.
   - Identify which capabilities should not be replaced blindly: protected branches, explicit staging, force-push prevention, and audit trails.

2. How should Code / Codex / Claude share a common setup?
   - Avoid repeating different configuration styles for every client and every project.
   - Separate user-level and project-level configuration.
   - Decide where tokens, DSNs, and private base URLs belong.

### Current judgement

- Database MCP shows that MCP can outperform local skill scripts when the server boundary is clear, the protocol is stable, and the operation is mostly read-only.
- Git should be split:
  - GitHub/GitLab/Gitee platform objects are good MCP-first candidates.
  - Local `branch/stage/commit/push` mutates repository state and needs stronger guarantees around fences, audit, and branch protection.
- Do not mark `git-trunk-workflow` as low priority yet. First build a capability matrix and then decide whether to adjust the skill positioning.

### To investigate

- Maturity, maintenance, permission boundaries, and risks of general local Git MCPs.
- Official/community GitHub MCP capabilities.
- Official/community GitLab MCP capabilities.
- Whether Gitee has usable MCP support, or only API/CLI-based alternatives.
- MCP configuration differences across Claude Code, Codex, and ZCode, and whether a shared template is possible.

## 2026-07-14 14:22:26 +0800 | Initial research: platform objects fit MCP; local Git writes should not be replaced yet

### Sources

- GitHub official MCP Server: `https://github.com/github/github-mcp-server`
- MCP reference/community servers: `https://github.com/modelcontextprotocol/servers`
- Python local Git MCP: `https://pypi.org/project/mcp-server-git/`
- MCP Git reference server: `https://github.com/modelcontextprotocol/servers/tree/main/src/git`
- Gitee MCP Server: `https://gitee.com/oschina/mcp-gitee`
- Archived GitLab reference server: `https://github.com/modelcontextprotocol/servers-archived/tree/main/src/gitlab`
- Mature GitLab community option: `https://github.com/zereight/gitlab-mcp`
- Claude Code MCP docs: `https://code.claude.com/docs/en/mcp`
- Codex config reference entry: `https://developers.openai.com/codex/config-reference`

The old GitLab reference server is archived and should not be used for new projects. `zereight/gitlab-mcp` appears to be the more mature community option, but it is not an official GitLab guarantee and should be enabled conservatively with readonly mode, tool allowlists, and narrow token scopes.

### Capability matrix

| Capability | Observed MCP option | Initial judgement |
|---|---|---|
| GitHub issues / PRs / reviews / actions / releases | GitHub official MCP Server | Mature enough for MCP-first platform workflows |
| Gitee issues / PRs / releases / repo objects | `oschina/mcp-gitee`, including remote MCP | Candidate for Gitee platform objects |
| GitLab issues / MRs / pipelines | `zereight/gitlab-mcp` community option; archived old reference server | Use cautiously; readonly + allowlist first |
| Local `status/diff/log/branch/checkout/add/commit` | `mcp-server-git` / MCP Git reference server | Usable, but beta/reference-like |
| Local `push` | Not clearly covered by the observed Git reference tools | Not enough to replace delivery workflow |
| Protected branches, force-push prevention, explicit staging allowlist, commit prefix validation, audit | Not seen as built-in policy in generic Git MCPs | Should not replace `git-trunk-workflow` directly |

### Initial conclusion

Version management should not be treated exactly like database MCP. Database access is often read-only and has a clear server boundary; local Git writes mutate repository state and concentrate risk around staging scope, branch protection, commit quality, push behavior, and audit trails.

Recommended path:

1. Prefer MCP for GitHub/GitLab/Gitee platform objects.
2. Consider MCP for local Git read-only operations such as status, diff, log, and show.
3. Keep local Git writes in `git-trunk-workflow` for now.
4. If replacement is desired later, use or build a policy-aware Git MCP rather than directly exposing a generic Git MCP:
   - protected branch denylist;
   - force-push prevention;
   - explicit path staging;
   - commit message prefix validation;
   - confirmation before push;
   - JSON audit log;
   - no fallback to native commands after MCP/script failure.

### Common configuration direction

MCP JSON differs between clients, but the shared rules can be consistent:

- Project-level config should contain only secret-free templates, server names, purposes, and team conventions.
- User-level config should contain real tokens, DSNs, and private base URLs.
- GitHub/GitLab/Gitee tokens must not be committed.
- Database DSNs must not be committed.
- For MCPs supporting toolsets/read-only/disabled tools, default to a narrow tool surface.
- High-risk operations such as merge, release, branch deletion, push, and file writes still require explicit user confirmation even when executed through MCP.

Do not mark `git-trunk-workflow` as low priority yet. The next step should be a MCP configuration template and capability matrix: platform objects go MCP-first, while local Git writes stay in the guarded skill.
