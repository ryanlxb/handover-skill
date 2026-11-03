# v1.1.2 Fixture Test Results

- Date (UTC): 2026-11-03T10:30:58+00:00
- Script: `handover/scripts/handover.py`
- Scope: fixture-level script tests only; no Claude Code skill execution.
- Cases: 82, passed: 82, failed: 0

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
| 19 | ignore-check: .handover 尚未创建时仍识别目录规则 | ok, exit 0 | exit 0 | PASS |
| 20 | ignore-check: 非 Git 项目 | not-git, exit 0 | exit 0 | PASS |
| 21 | status-guard：任务不存在允许新建 | new-task-allowed, exit 0 | exit 0 | PASS |
| 22 | status-guard：active 任务允许复用 | active-reuse-allowed, exit 0 | exit 0 | PASS |
| 23 | status-guard：completed 任务阻止 save | blocked, exit 1 | exit 1 | PASS |
| 24 | status-guard：cancelled 任务阻止 save | blocked, exit 1 | exit 1 | PASS |
| 25 | status-guard：显式授权后可重开 | reopen-authorised, exit 0 | exit 0 | PASS |
| 26 | status-guard：unknown 状态拒绝 | unknown, exit 2 | exit 2 | PASS |
| 27 | status-guard：任务文件在项目外 | unknown, exit 2 | exit 2 | PASS |
| 28 | stats 文本输出：frontmatter + section 分布 | exit 0, contains sections | exit 0 | PASS |
| 29 | stats --json：合法 JSON，percent 合计约 100 | exit 0, JSON valid | exit 0 | PASS |
| 30 | stats：任务文件缺失 | exit 2, error | exit 2 | PASS |
| 31 | stats：task-file 在项目外 | exit 2, error | exit 2 | PASS |
| 32 | stats：非法 task-id | exit 2, error | exit 2 | PASS |
| 33 | stats：无 frontmatter 的文档 | exit 0, frontmatter=0, decorative=1 | exit 0 | PASS |
| 34 | config.yaml 无分隔符/无闭合分隔符仍生效 | stale, exit 0 | exit 0 | PASS |
| 35 | 无效 config 告警并使用默认 14 | warning + fresh | exit 0 | PASS |
| 36 | 任务缺少 fingerprint_file 绑定 | unknown, exit 2 | consistency: unknown | PASS |
| 37 | 任务缺少 fingerprint_sha256 绑定 | unknown, exit 2 | consistency: unknown | PASS |
| 38 | 任务 frontmatter task_id 不一致 | unknown, exit 2 | consistency: unknown | PASS |
| 39 | 任务 schema 不受支持 | unknown, exit 2 | consistency: unknown | PASS |
| 40 | 任务 schema 为布尔值 | unknown, exit 2 | consistency: unknown | PASS |
| 41 | 任务 project_root 不一致 | unknown, exit 2 | consistency: unknown | PASS |
| 42 | fingerprint 拒绝空声明范围 | exit 2, error | exit 2 | PASS |
| 43 | 根目录声明只覆盖直属文件：子目录新增不触发，根目录新增触发 | subdir matched; root changed | consistency: matched | PASS |
| 44 | sidecar 文件集为空 | unknown, exit 2 | consistency: unknown | PASS |
| 45 | 旧 sidecar 缺根目录 scope 时仍能检测根目录新增 | changed, git_changed | consistency: changed | PASS |
| 46 | list：.handover 指向项目外 | exit 2, not read | exit 2 | PASS |
| 47 | list：单个任务文件指向项目外 | exception, not read | exit 0 | PASS |
| 48 | fingerprint 拒绝写入符号链接 sidecar | exit 2, file unchanged | exit 2 | PASS |
| 49 | matched 输出范围外变化计数 | matched + out_of_scope_changes | consistency: matched | PASS |
| 50 | 文件超过上限但大小已变：判 changed 而非 unknown | changed, size changed | consistency: changed | PASS |
| 51 | list：重复 task_id 可见 | duplicate task_id | exit 0 | PASS |
| 52 | list：重复 ID 的所有记录都进入 EXCEPTIONS | no duplicate in ACTIVE | exit 0 | PASS |
| 53 | list：schema 为布尔值不进入 ACTIVE | exception, not active | exit 0 | PASS |
| 54 | fingerprint --out 不能覆盖业务文件 | exit 2, business file unchanged | exit 2 | PASS |
| 55 | fingerprint --out 不能覆盖任务 Markdown | exit 2, task unchanged | exit 2 | PASS |
| 56 | fingerprint --out 允许 .handover/archive 下的归档 sidecar | exit 0, sidecar written | exit 0 | PASS |
| 57 | fingerprint 拒绝覆盖其他任务的 sidecar | exit 2, existing sidecar unchanged | exit 2 | PASS |
| 58 | fingerprint --out 不能写到项目外 | exit 2, no file | exit 2 | PASS |
| 59 | fingerprint --out 不能通过 archive 符号链接写到项目外 | exit 2, no file | exit 2 | PASS |
| 60 | fingerprint 拒绝保留字 task-id | exit 2, reserved | exit 2 | PASS |
| 61 | analysis 不读取项目 transcript 目录外的符号链接 | not found, no content | exit 0 | PASS |
| 62 | ignore-check：git 执行失败不被当作非 Git | unknown, exit 2 | exit 2 | PASS |
| 63 | status-guard 拒绝不支持/布尔 schema | unknown, exit 2 | exit 2 | PASS |
| 64 | status-guard 拒绝其他项目的记录 | unknown, exit 2 | exit 2 | PASS |
| 65 | status-guard 旧格式迁移分支：仅可识别旧记录 exit 3 | plain exit 2; legacy exit 3; corrupt/unclosed exit 2 | exit 3 | PASS |
| 66 | 受限 YAML：行内注释与引号内 # 正确处理 | list/status-guard succeed | exit 0 | PASS |
| 67 | 受限 YAML：普通标量中的撇号不被当作引号 | list/status-guard succeed | exit 0 | PASS |
| 68 | 受限 YAML：单引号标量中的 '' 转义 | list/status-guard succeed | exit 0 | PASS |
| 69 | 受限 YAML：重复键被拒绝而非后者覆盖 | exception + exit 2 | exit 0 | PASS |
| 70 | 受限 YAML：序列/嵌套映射/缩进/引号尾随内容被拒绝 | exit 2 with parse error | exit 2 | PASS |
| 71 | config 符号链接指向项目外时不读取 | warning + default freshness | exit 0 | PASS |
| 72 | fingerprint 报告内容哈希与 git 状态范围 | coverage lines | exit 0 | PASS |
| 73 | check matched 报告覆盖范围 | coverage lines | consistency: matched | PASS |
| 74 | 目录内未声明文件：同状态内容变化不被内容哈希发现（记录边界） | matched (documented limitation) | consistency: matched | PASS |
| 75 | 只改任务正文不更新 frontmatter：check 仍 matched（记录边界） | matched (documented limitation) | consistency: matched | PASS |
| 76 | check 拒绝布尔 sidecar schema | unknown, exit 2 | consistency: unknown | PASS |
| 77 | analysis 不输出 system/tool 正文片段 | no markers, no head field | exit 0 | PASS |
| 78 | analysis：显式 session 缺失不回退；未指定时才自动选择 | missing exit 2; auto note; invalid exit 2 | exit 2 | PASS |
| 79 | analysis 文本输出：tool schema + shape delta | exit 0, contains groups | exit 0 | PASS |
| 80 | analysis --json：分组和 shape delta | exit 0, JSON valid | exit 0 | PASS |
| 81 | analysis：显式 transcript 缺失 | exit 2, error | exit 2 | PASS |
| 82 | analysis：无 transcript 时仍给出配置报告 | exit 0, not found note | exit 0 | PASS |

## Not covered by these fixture tests

- Claude Code skill installation, `/handover` invocation, `/clear`, and reload.
- Archive/restore file moves and entry-link updates.
- Concurrent writers and real permission behavior.
