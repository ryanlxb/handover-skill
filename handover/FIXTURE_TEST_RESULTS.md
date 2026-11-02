# v1.1.0-rc.1 Fixture Test Results

- Date (UTC): 2026-11-02T09:13:49+00:00
- Script: `handover/scripts/handover.py`
- Scope: fixture-level script tests only; no Claude Code skill execution.
- Cases: 19, passed: 19, failed: 0

| # | case | expected | actual | result |
|---:|---|---|---|---|
| 1 | 完整基线，无变化 | matched, exit 0 | consistency: matched | PASS |
| 2 | 任务与 sidecar 的 snapshot_id 不一致 | unknown, exit 2 | consistency: unknown | PASS |
| 3 | 声明文件内容变化 | changed, content_changed | consistency: changed | PASS |
| 4 | 声明目录内新增文件 | changed, git_changed | consistency: changed | PASS |
| 5 | 声明文件被删除 | changed, missing | consistency: changed | PASS |
| 6 | 声明文件被重命名 | changed | consistency: changed | PASS |
| 7 | 文件内容不变，暂存状态变化 | changed, git_changed, no content_changed | consistency: changed | PASS |
| 8 | HEAD 变化，声明文件内容相同 | changed, git_changed | consistency: changed | PASS |
| 9 | 部分基线不可检查 + 已知内容变化 | changed, incomplete: true | consistency: changed | PASS |
| 10 | 部分基线不可检查 + 无明确变化 | unknown, exit 2 | consistency: unknown | PASS |
| 11 | 非 git 项目，无 git 基线 | unknown, exit 2 | consistency: unknown | PASS |
| 12 | 任务 fingerprint_sha256 与 sidecar 不一致 | unknown, exit 2 | consistency: unknown | PASS |
| 13 | 排除 .claude/ 与 .git/ | skipped_excluded; sidecar only src/login.ts | exit 0 | PASS |
| 14 | list 读取 frontmatter title | title column contains Login task | exit 0 | PASS |
| 15 | title 缺失时回退 task-id | title falls back to no-title | exit 0 | PASS |
| 16 | ignore-check: 已忽略且未跟踪 | ok, exit 0 | exit 0 | PASS |
| 17 | ignore-check: 未忽略 | warning, exit 1 | exit 1 | PASS |
| 18 | ignore-check: 已跟踪的任务数据 | warning, exit 1 | exit 1 | PASS |
| 19 | ignore-check: 非 Git 项目 | not-git, exit 0 | exit 0 | PASS |

## Not covered by these fixture tests

- Claude Code skill installation, `/handover` invocation, `/clear`, and reload.
- Archive/restore file moves and entry-link updates.
- Concurrent writers and real permission behavior.
