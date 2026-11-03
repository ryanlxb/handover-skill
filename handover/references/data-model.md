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

至少包含：`schema`、`snapshot_id`（可空）、`task_id`、`title`、`status`、`updated_at`（ISO 8601 含时区或 null）、`migrated_at`（可空）、`archived_at`（可空）、`restored_at`（可空）、`project_root`、`branch`、`head`、`worktree`、`fingerprint_file`（可空）、`fingerprint_sha256`（可空）、`fingerprint_scope`（默认 relevant-files+git）、`fingerprint_checked_at`（可空）。

- 缺失或无法解析时标 unknown；`title` 例外：缺失时 `list` 回退显示 task-id，下一次 save 补齐，不批量改写旧任务。
- 缺失值统一用 `null`，不用空字符串或字符串 "unknown" 充当缺失值。
- 日期必须是含时区的 ISO 8601 字符串；否则视为无效。
- `schema` 是文件格式版本，不是 Skill 版本；未支持的 schema 只读并告警，不自动降级覆盖。
- `stale_after_days` 必须是合法正整数；无效配置告警后使用默认 14。
- 模板中的示例日期仅作格式示例，不得原样写入真实任务。

## 状态、freshness、consistency

- `status`：in-progress / pending / blocked / paused / completed / cancelled。`unknown` 只用于缺失、损坏或无法识别的记录，不是用户可选状态。阻塞、等待和暂停分别写明原因。
- 新建任务默认 `in-progress`；`completed` 只在用户明确确认完成且验收证据存在时写入，声明与证据冲突时用 `blocked`。save 无 ID 时只复用 active 任务；completed/cancelled/archived 不是 save 目标，默认新建任务。只有用户明确说“重开 `<task-id>`”才可重开，并用 `status-guard` 核验。
- `freshness`：fresh / stale / unknown。age = now - updated_at；age >= stale_after_days 为 stale；age < stale_after_days 为 fresh；updated_at 为 null、无效或未来时间等异常为 unknown。stale 只表示需要复核，不覆盖 status，不触发删除。
- `consistency`：matched / changed / unknown，只在 load 时计算。必须先核对任务 frontmatter 的 `schema`、`task_id`、`project_root`、`snapshot_id`、`fingerprint_file`、`fingerprint_sha256` 与当前项目/sidecar 一致；任一缺失或不匹配 → unknown。
- 指纹包含两部分：声明文件的内容 SHA-256，以及相关范围的 git 现场（branch、HEAD、status 条目）。声明范围 = 任务相关文件 + “接手必读”路径 + 显式提到的路径 + 这些路径所在目录；排除 `.handover/`、`handover.md`、`.claude/` 和 `.git/`。
- 目录范围：子目录按子树覆盖；项目根目录按直属文件覆盖（不递归），避免一个根目录文件把整个仓库都算进 matched。`--scope-dir .` 表示根目录直属文件。
- 没有任何可声明文件时不得生成空基线；`fingerprint` 返回错误，consistency 为 unknown。
- 当前版本默认排除整个 `.claude/`：这表示 `.claude/` 下的项目配置变化不在一致性检查范围内，不等于断言所有项目配置都不属于任务现场；后续版本可考虑允许显式纳入与任务相关的配置。
- git 现场覆盖声明范围内的新增、删除、重命名、暂存/未暂存状态变化；范围外的改动只计数，不参与 matched 判断。
- 结果优先级：已发现明确差异（内容或 git）→ changed，并注明检查是否不完整；未发现明确差异但检查不完整 → unknown；检查完整且无差异 → matched。
- matched 只表示“声明的检查范围内一致”，不是整个项目一致。
- `updated_at` 只在实质 save 时更新；list/load 不刷新。
- 这些检查只在命令调用时发生，没有后台计时器。

## 过期、复核与语义陈旧

- `freshness`（时间）和 `consistency`（内容/git）是自动计算的信号；没有后台计时器，只在 list/load 等命令调用时计算。
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
- 迁移只补 frontmatter，不改变任务状态，不把旧记录“洗新”：
  - 能可靠解析旧更新时间则保留；否则 `updated_at = null`，freshness = unknown。
  - 写入 `migrated_at = now`，与 `updated_at` 分开。
  - status 无法确认时写 unknown，不默认 in-progress。
  - 迁移不是实质核验；不更新 `updated_at`。
- 未支持 schema 只读并告警；不自动降级覆盖。
- archive/restore 只处理 schema 1；旧文件必须先按上述规则完成迁移，再执行 archive/restore。用户授权不能替代格式和路径校验。
- 报告使用“正文内容保留”；只有实际做过字节比较时才可写“字节一致”。
