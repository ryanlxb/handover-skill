# Save

`save` 保存当前会话中可明确归属的任务；默认模式。未指定 ID 时：当前会话明确关联某任务则沿用；否则按当前明确目标生成并告知。当前会话含多个目标时只保存可明确归属的当前任务；无法区分则列出候选，避免混写。

## 1. 读取与旧记录核验

- 读取当前项目入口（`handover.md`）、当前任务旧记录和必要项目规范；参考 [task-template.md](task-template.md) 的结构；不要读取其他任务正文。
- 已在上下文中的文件不重复读；大文件用 Grep/offset。
- 如果当前任务已有记录和 sidecar，先运行 `<skill-dir>/scripts/handover.py check --root <root> --task <id> --task-file <task.md>`：
  - `changed`：列出变化路径，和旧记录对账；不要照抄旧结论。
  - `unknown`：说明原因（无 sidecar、基线不完整、无 git）；不要宣称一致。
  - `stale`（按时间）：只读快速摘要和相关章节；重新核验当前事实。
  - `matched`：只表示声明范围一致；仍要结合当前对话更新任务进度。
- 旧记录只作为历史证据；新证据替代旧结论时注明原因和适用条件。旧决策可因需求、版本或证据变化重新评估，不变成永久禁令。
- 如果 task-id 已存在但目标不同，停止覆盖并提示换 ID。
- 如果旧记录是 completed/cancelled，不隐式重开；用 load 显式查看或新建任务。

### 任务选择与状态（无 ID 时必须遵守）

- 无 ID 时只允许沿用 **active** 任务：in-progress / pending / blocked / paused，且必须与当前会话目标明确匹配。
- completed / cancelled / archived 任务**不是 save 目标**。即使当前会话提到它，也默认新建 task-id；只有用户明确说“重开 `<task-id>`”时，才允许把旧任务作为目标并记录重开原因。“继续”“同一个任务”“收尾”不等于重开授权。
- 新建任务默认 `status: in-progress`。`completed` 只在用户明确确认完成且验收证据存在时写入；声明与证据冲突时用 `blocked`，不要用 `completed` 掩盖未验证状态。
- 确定 task-id 后，如果目标文件已存在，先运行 `status-guard`：
  - exit 0：absent 或 active，可继续；
  - exit 1：completed/cancelled，停止写入，报告“新建 task-id 还是明确重开”；
  - exit 2：unknown/错误，停止写入并报告。
- 只有用户明确授权重开时，才使用 `status-guard --reopen-authorised`，并在任务文档“决策与尝试”记录该授权；不要自行推断。
- save 简报必须报告：task_id、status、新建/复用/重开、选择原因。

## 2. 采集现场

- 采集时间及时区、项目/仓库标识、工作区路径、分支、完整 HEAD；检查暂存、未暂存、未跟踪文件。
- 必要时读取近期提交和关键 diff，不只看 diff 统计。
- 非 Git 标记不适用。
- 仓库标识优先使用已有安全项目 ID；可记录经脱敏的 remote 标识，但不得输出含凭证 URL。无法确认时写未知。路径、分支、HEAD 只是核验线索，不是全局唯一身份。

## 3. 对照对话与文件

- 记录目标、追加要求、验收标准、硬约束、范围外事项、进度、决策及原因、失败尝试、阻塞、外部等待、未批准建议。
- 修改归属分为本任务/其他任务/未知，不把全部工作区修改归入当前任务。
- 验证证据记录命令、执行位置、时间、结果、当时代码状态、验证后是否修改。未运行或不可确认时写明；不要伪造命令输出或测试结果。
- 已实现、已测试、已验收分别记录；旧结果不是当前验证。

## 4. 写作

- 优先引用已有 spec、ADR、issue、commit、diff 和代码路径，不重复其内容；不粘贴大段代码、diff 或日志。
- 任务文档只写“代码/git 里读不到”的 delta：决策与原因、失败尝试、验证命令、风险、下一步。
- “接手必读”写成索引：`path#symbol` / `path:start-end` + 用途；不写裸文件清单。
- 遵守 [task-template.md](task-template.md) 的 frontmatter 和章节结构。

### Token 卫生

- 只写高信号 delta；同一状态不要在 frontmatter、快速摘要、当前进度和入口重复多遍。
- 跨文件去重：`handover.md` 只保留任务索引和真正的跨任务风险；不要把任务摘要、验证证据、任务内风险复制到入口。
- 同一验证命令/结果只写一次；其他章节用“见验证证据”或 `path#symbol` 引用。
- 快速摘要与当前进度不要逐字重复 frontmatter 的 status；frontmatter 是机器索引，摘要/进度只写新会话需要知道的变化。
- 删除装饰性水平分隔线、对齐空格、连续空行和 emoji 装饰。
- 用紧凑 Markdown：单空行、无装饰分隔线、无行尾空格、短标题。
- 避免宽表格；小块结构化数据用 `key: value` 或 TSV；只有需要人读的对比才用表格。
- 不粘贴代码/diff/日志；用 `path#symbol`、`path:start-end`、commit hash 引用。
- 必要的空格、换行和标点是结构，不要删除；不做激进 minify。
- 机器可读的大块统一数据可考虑 TOON/TSV；任务文档主体仍用 Markdown（人读 + 工具兼容）。
- 优先砍重复和无关内容，而不是空格；先测再优化。

## 5. 安全写入

- 写入前重新核对目标文件自读取后是否变化；有变化则停止覆盖并报告。
- 使用同目录临时文件及安全替换（环境支持时），清理自己创建的临时文件；这不构成并发锁。
- 新文件也需避免覆盖刚被其他会话创建的文件。无法安全写入时报告失败，不强行覆盖。
- sidecar 输出路径是符号链接、或默认 `.handover` 是符号链接时，`fingerprint` 会拒绝写入；不要绕过该检查去覆盖业务文件。

## 6. 指纹

- 写入任务文件后，若 Skill 安装目录下的 `scripts/handover.py` 可用且能确定相关文件（用 harness 给出的 base directory 拼绝对路径，替换 `<skill-dir>`）：
  - 生成或接收 `snapshot_id`；
  - 将相关文件路径写入临时文件（用户明确提供或本次 save 创建，优先项目外临时目录）；
  - 运行 `fingerprint` 生成 sidecar；
  - 把 `snapshot_id`、`fingerprint_file`、`fingerprint_sha256`、`fingerprint_scope`、`fingerprint_checked_at` 写入 frontmatter；
  - 清理临时文件；
  - 运行 `check --task-file <task.md> --expected-sha256 <hash>`，确认任务文件与 sidecar 的 `snapshot_id`/SHA 绑定一致，且检查时现场与刚生成的基线一致。
- 若 `check` 返回 changed：报告“检查时现场与基线不一致”，不要宣称干净保存；若 unknown：报告不完整基线。该检查不证明正文语义与代码一致，也不证明正文整理期间代码始终未变。
- 若排除 `.handover/`、`handover.md`、`.claude/`、`.git/` 后没有任何可声明文件，`fingerprint` 会拒绝生成空基线；不要写“0 文件 matched”。这些绑定字段置 null，并明确 consistency 将为 unknown。
- 无法生成时这些字段置 null，并明确 consistency 将为 unknown。
- 详细规则见 [fingerprint.md](fingerprint.md)。

## 7. 更新与回读

- 本次 save 有实质更新时更新 `updated_at`（含时区）；不要更新其他任务的时间。
- 旧 1.0.0 任务文件按 [data-model.md](data-model.md) 的迁移规则处理。
- 根入口仅在新增任务、任务状态变化或必要入口信息变化时更新；保留用户原有内容；不要每次刷新全部任务状态或更新时间。存在共享入口冲突时优先保存独立任务文件并报告入口未更新。
- 回读实际写入文件，检查需求、未完成项、风险、决策、路径、分支、HEAD、验证标记、敏感信息及入口链接。
- 运行 `ignore-check`（若可用），确认 `.handover/` 与 `handover.md` 为 `ignored, not-tracked`；warning/unknown 时报告，不自动修改 `.gitignore`，不执行 `git rm`。文档或入口失败分别报告，不笼统宣称全部成功。
- 可选：运行 `<skill-dir>/scripts/handover.py stats --root <root> --task <id>` 查看 token 分布；优先压缩占比最高的章节，不要按空格盲目压缩。

## 8. 最终简报

- 项目、task_id、`status=...`、新建/复用/重开及原因、保存路径、核验结果、缺口、精确的新会话恢复命令（如 `/handover load login`）。
- 不输出全局 last-active 指针。
- 提醒交接不替代代码保存、提交或备份。
- 不自动 `/clear`。
