# 数据模型与任务身份

## 术语

- **当前记录区**：`.handover/` 顶层的任务文件。
- **活跃状态**：in-progress / pending / blocked / paused。
- **已结束状态**：completed / cancelled。
- **归档区**：`.handover/archive/`。
- **记录组**：任务 Markdown 与它的指纹 sidecar；两者通过同一个 `snapshot_id` 绑定，归档/恢复时作为同一组处理。
- **待识别记录**：status 缺失或 unknown、YAML 解析失败、未支持 schema、重复 task-id、文件名与 task_id 不一致的记录。

## 数据布局

- `handover.md`：精简项目入口，使用“任务列表”列出所有任务、项目资料链接、必要的跨任务风险和归档链接。不写唯一的“当前任务”或全局 last-active 指针；单任务时列表只有一项，也不把它当作恢复授权。
- `.handover/<task-id>.md`：当前记录区任务文件，顶部使用统一 YAML frontmatter。
- `.handover/<task-id>.fingerprint.json`：可选的现场指纹 sidecar，由 `scripts/handover.py fingerprint` 生成。
- `.handover/archive/<task-id>-<小写 UTC 时间戳>.md`：归档任务；保留原 task-id、最后实质更新时间和归档时间。
- `.handover/archive/<task-id>-<小写 UTC 时间戳>.fingerprint.json`：归档任务的指纹 sidecar；与归档 Markdown 使用同一 stem，作为同一记录组移动。
- `.handover/config.yaml`（可选）：项目级配置，例如 `stale_after_days: 14`。缺失时使用默认 14。

## task-id 与 archive-id

- task-id 必须匹配 `^[a-z0-9][a-z0-9-]{0,63}$`。禁止路径分隔符、点路径、shell 字符；不把未经验证的参数拼接进命令。
- 保留字 save / load / brief / list / archive / restore / analysis（大小写不敏感）不得作为 task-id。
- archive-id 必须匹配 `^[a-z0-9][a-z0-9-]{0,80}$`，且不得包含路径分隔符或点路径。
- task-id 是任务身份，窗口不是身份。已存在 ID 但目标不一致时停止覆盖，提示换 ID。无 ID save 不得把 completed/cancelled/archived 任务当作目标；默认新建 active 任务。
- 一个任务跨窗口可沿用同一 ID，但不允许无协调地同时写同一文件。不同并行任务使用不同 ID；并行修改代码建议独立 worktree。
- 不同项目允许使用相同 task-id。

## YAML frontmatter

至少包含：`schema`、`snapshot_id`（可空）、`task_id`、`title`、`status`、`updated_at`（ISO 8601 含时区或 null）、`migrated_at`（可空）、`archived_at`（可空）、`restored_at`（可空）、`project_root`、`branch`、`head`、`worktree`、`fingerprint_file`（可空）、`fingerprint_sha256`（可空）、`fingerprint_scope`（默认 relevant-files+git）、`fingerprint_checked_at`（可空）、`body_sha256`（可空）、`goal_sha256`（可空）。

- frontmatter 使用受限的扁平 YAML：每行一个 `key: value`，不支持嵌套、序列、锚点/别名/标签、块标量或多行值。重复键、缩进行、缺少 `: ` 分隔符、未闭合引号等是解析错误 → unknown，不静默忽略。
- 行内注释 `# ...` 在引号外且前面是空白时会被移除。值本身包含 `#` 或 `: ` 时用引号包裹（如 `title: "Fix: login"`）；数值字段（`schema`、`stale_after_days`）按十进制数字校验，其他全数字值保持字符串，避免 task-id/commit hash 被误转成整数。
- 缺失或无法解析时标 unknown；`title` 例外：缺失时 `list` 回退显示 task-id，下一次 save 补齐，不批量改写旧任务。
- 缺失值统一用 `null`，不用空字符串或字符串 "unknown" 充当缺失值。
- 日期必须是含时区的 ISO 8601 字符串；否则视为无效。
- `schema` 是文件格式版本，不是 Skill 版本；未支持的 schema 只读并告警，不自动降级覆盖。
- `stale_after_days` 必须是合法正整数；无效配置告警后使用默认 14。
- `scope_root_mode`：`direct`/`declared`（默认）/`tracked`；控制根目录 git 状态范围：direct 全部直属条目，declared 仅显式声明文件，tracked 额外含已跟踪条目修改；新未跟踪根目录文件计为范围外。无效值告警并使用默认。

## 任务正文完整性（body_sha256 / goal_sha256）

- `seal` 在任务正文写完后运行：校验必需章节、状态、frontmatter 和 token 上限，然后把 `body_sha256`（frontmatter 之后的完整正文）与 `goal_sha256`（规范化后的 `## 目标与边界` 章节）写入 frontmatter。
- `task-lint --require-seal` 独立复核；`check` 报告 `task_body` / `task_goal`：
  - `matched`：正文/目标与 frontmatter 哈希一致；
  - `changed`：seal 后正文/目标被改写，`consistency` 仍可能是 matched，但 `check` 返回 **exit 3**（integrity changed）；
  - `unknown`：旧任务没有 `body_sha256` / `goal_sha256`，不声称完整。
- `body_sha256`/`goal_sha256` 只证明“与 seal 时一致”，不证明正文语义正确；仍要对照代码现场和用户要求。
- `seal` 不改变 `updated_at`、status、snapshot 绑定；归档/恢复时这两个字段随任务保留，不重新生成。
- `goal-guard --old-file <old> --new-file <new>` 比较两个任务的 `## 目标与边界` 规范化哈希：`goal-unchanged` exit 0；`goal-changed` exit 1；`goal-change-authorised` exit 0。save 在覆盖 active 任务前必须运行它。

## 状态、freshness、consistency

- `status`：in-progress / pending / blocked / paused / completed / cancelled。`unknown` 只用于缺失、损坏或无法识别的记录，不是用户可选状态。阻塞、等待和暂停分别写明原因。
- 新建任务默认 `in-progress`；`completed` 只在用户明确确认完成且验收证据存在时写入，声明与证据冲突时用 `blocked`。save 无 ID 时只复用 active 任务；completed/cancelled/archived 不是 save 目标，默认新建任务。只有用户明确说“重开 `<task-id>`”才可重开，并用 `status-guard` 核验。
- `status-guard` 校验 task_id、schema、project_root 和 status。exit 0 只表示身份/格式/状态允许复用，不是写锁，也不校验正文。旧 1.0.0 记录（无 frontmatter）默认 exit 2；只有显式使用 `status-guard --legacy-migration` 且文件是可识别的 Markdown 旧记录时返回 exit 3（`legacy-migration-required`）。迁移 frontmatter、回读后必须重新运行不带该参数的 `status-guard`，exit 0 才能继续写入；损坏、未闭合 frontmatter、非 Markdown 或未支持 schema 仍 exit 2。
- `freshness`：fresh / stale / unknown。age = now - updated_at；age >= stale_after_days 为 stale；age < stale_after_days 为 fresh；updated_at 为 null、无效或未来时间等异常为 unknown。stale 只表示需要复核，不覆盖 status，不触发删除。
- `consistency`：matched / changed / unknown，在 load 或 save 的 `check` 步骤中计算。必须先核对任务 frontmatter 的 `schema`、`task_id`、`project_root`、`snapshot_id`、`fingerprint_file`、`fingerprint_sha256` 与当前项目/sidecar 一致；任一缺失或不匹配 → unknown。
- `check` 先核对 frontmatter 与 sidecar 绑定，再核对 `body_sha256`/`goal_sha256`；正文/目标被改写时 `consistency` 可仍为 matched，但 `check` 返回 exit 3（integrity changed）。旧任务没有 seal 字段时 `task_body`/`task_goal` 为 unknown，不声称完整。
- 指纹包含两部分：声明文件的内容 SHA-256，以及相关范围的 git 现场（branch、HEAD、status 条目）。声明范围 = 任务相关文件 + “接手必读”路径 + 显式提到的路径 + 这些路径所在目录；排除 `.handover/`、`handover.md`、`.claude/` 和 `.git/`。
- 内容哈希只覆盖 `files` 中明确列出的文件。目录范围只筛选 git status，不对目录内未列出的文件做内容哈希；同目录未声明文件的内容变化若没有改变 git 状态条目，可能不被发现。
- 目录范围：子目录按子树覆盖；根目录由 `scope_root_mode` 控制：`direct` 匹配所有根目录直属条目；`declared`（默认）只匹配显式声明的根目录文件；`tracked` 额外匹配已跟踪根目录条目的修改。`--scope-dir .` 表示根目录直属文件。
- 没有任何可声明文件时不得生成空基线；`fingerprint` 返回错误，consistency 为 unknown。
- 当前版本默认排除整个 `.claude/`：这表示 `.claude/` 下的项目配置变化不在一致性检查范围内，不等于断言所有项目配置都不属于任务现场；后续版本可考虑允许显式纳入与任务相关的配置。
- git 现场覆盖声明范围内的新增、删除、重命名、暂存/未暂存状态变化；范围外的改动只计数，不参与 matched 判断。
- 结果优先级：已发现明确差异（内容或 git）→ changed，并注明检查是否不完整；未发现明确差异但检查不完整 → unknown；检查完整且无差异 → matched。
- matched 只表示“声明的检查范围内一致”：列出的文件内容哈希 + 声明目录的 git 状态。不是整个项目一致，也不是任务正文未被改写。
- `updated_at` 只在实质 save 时更新；list/load 不刷新。
- 这些检查只在命令调用时发生，没有后台计时器。

## 过期、复核与语义陈旧

- `freshness`（时间）和 `consistency`（内容/git）是自动计算的信号；没有后台计时器，只在 list/load/save 等命令调用时计算。
- `stale` 只是复核提醒，不是失效或删除；不自动归档、不自动删除。
- `changed` 表示声明的文件/git 范围有明确变化；`unknown` 表示无法核验（无 sidecar、基线缺失、文件不可读、无 git）。
- `matched` 只表示“声明范围内一致”，不表示任务语义仍然正确。
- **语义陈旧**：任务进度/决策/外部依赖变化但未 save，fingerprint 可能完全匹配；只有新的 save 或人工复核能发现。load 的报告和 save 的 pre-check 只能降低风险，不能保证。
- save 前应核验旧记录：changed 时对账，unknown 时说明，stale 时只读摘要/相关章节；不要把旧结论当当前事实。
- 不自动删除过期记录；归档/清理由用户显式执行。

## 归档命名

- `.handover/archive/<task-id>-<小写 UTC 时间戳>.md`
- `.handover/archive/<task-id>-<小写 UTC 时间戳>.fingerprint.json`
- 归档保留原 task-id、最后实质更新时间和归档时间；归档不改变 `updated_at`。

## 旧文件与格式迁移

- 只迁移当前 save 的任务；不批量改写。
- v1.2 新增 seal 字段与项目上下文/未复核章节；旧任务未 seal 时 `task_body`/`task_goal` 为 unknown，`task-lint` 可能因超 6k 或缺章节失败。只在下一次 save 升级当前任务。
- 迁移流程：先运行 `status-guard --legacy-migration` 识别。只有 exit 3（可识别的无 frontmatter Markdown 旧记录）才进入迁移；补 frontmatter 后回读校验 schema/task_id/project_root/status；再运行不带该参数的 `status-guard`，exit 0 才能继续 save。exit 2 表示损坏、未闭合 frontmatter、非 Markdown 或未支持 schema，停止；不要用 `--legacy-migration` 绕过。
- 迁移只补 frontmatter，不改变任务状态，不把旧记录“洗新”：
  - 能可靠解析旧更新时间则保留；否则 `updated_at = null`，freshness = unknown。
  - 写入 `migrated_at = now`，与 `updated_at` 分开。
  - status 无法确认时写 unknown，不默认 in-progress。
  - 迁移不是实质核验；不更新 `updated_at`。
- 未支持 schema 只读并告警；不自动降级覆盖。
- archive/restore 只处理 schema 1；旧文件必须先按上述规则完成迁移，再执行 archive/restore。用户授权不能替代格式和路径校验。
- 报告使用“正文内容保留”；只有实际做过字节比较时才可写“字节一致”。
