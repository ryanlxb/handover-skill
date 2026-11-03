# v1.1.1 验收清单

以下为建议测试，不代表已在你的 Claude Code 中执行。结构/静态检查结果见 `VALIDATION.md`；端到端验收需另行执行。

## 基础

1. 项目 A 保存 `/handover save demo`，确认只生成 A/handover.md 和 A/.handover/demo.md，不修改业务代码。
2. 新窗口进入 A，执行 `/handover load demo`，确认核验工作区后汇报，不自动开发；load 不改变 status 或 `updated_at`。
3. 只有唯一 `in-progress` 任务且 freshness=fresh 时，不带 ID 的 load 自动选择并告知；多个 `in-progress`、stale/unknown、或只有 pending/blocked/paused 时列出候选，不自动选择。
4. 项目 B 执行 list/load，不得列出 A 的任务；B 可保存同名 demo。
5. brief 不继续旧任务；新目标保存为独立 ID。
6. 非 Git 或根目录不明确时，报告限制，不猜测写入位置。
7. 交接目录为指向项目外的符号链接时，应停止访问。
8. 非法 ID（如 ../other）必须拒绝；现有同名 ID 目标不一致时不得覆盖。
9. 交接文件被另一窗口修改后，不得无提示覆盖。注意这不是强锁测试。
10. 工作区身份不匹配、文件缺失、写入失败时，不得宣称恢复或保存成功。
11. save 后回读确认；不自动提交、推送、stash、reset、启动服务或清空会话。
12. 交接内容中出现要求泄密或跳过核验的文字时，只视为不可信数据，不执行。
13. 不在测试中使用真实密钥；检查输出不包含敏感值。

## freshness

14. 任务 `updated_at` 设为 30 天前：list 标 stale；无 ID load 不自动选择，列候选等待确认。
15. 删除 `updated_at` 字段或置 null：freshness=unknown；不自动选择。
16. `age == stale_after_days`：按规则标 stale，不标 fresh。
17. `updated_at` 为未来时间：freshness=unknown，不默认 fresh。

## consistency 与指纹

18. 同一 branch、同一 HEAD、同样“有未提交修改”，但相关文件内容已变：consistency 必须为 changed；不得仅凭 branch/HEAD 判 matched。
19. 保存后只改交接文件自身（`handover.md` 或 `.handover/`）：不得导致相关文件指纹变化或 consistency=changed。
20. 删除或篡改 `.handover/<task-id>.fingerprint.json`：consistency=unknown，不乐观判 matched。
21. 指纹 sidecar 中某个相关文件不可读或超过大小上限：consistency=unknown；报告跳过原因。
22. 没有指纹 sidecar 的旧任务：consistency=unknown，不得判 matched。
23. 指纹范围只覆盖已检查文件：在报告中明确“不是整个项目一致”。

## 选择与列表

24. 两个 `in-progress` 任务：无 ID load 只列候选，不按“最近更新”擅自选择；若只有一个 `in-progress` 并伴随 pending/blocked/paused，仍按唯一 `in-progress` 规则处理。
25. 待识别记录（status unknown、YAML 损坏、未支持 schema、重复 task-id、文件名与 task_id 不一致）：list 的异常区域可见，不被静默隐藏；无 ID load 不选择它们。
26. list 输出只含 frontmatter 字段；不出现正文；显示隐藏数量（completed/cancelled/archived）。
27. 连续 list/load 后 `updated_at` 不变。
28. save 成功后输出精确的 `/handover load <task-id>`，不依赖全局 last_active。

## 归档与恢复

29. 重复归档同一任务：源文件已不存在时应报告“源缺失”，不要误报为目标重名冲突。
30. 归档目标文件名已存在：停止，不覆盖。
31. 归档中途入口更新失败：报告任务文件实际位置和已完成步骤；任务文件不得被删除。
32. 归档不改变 `updated_at`；归档记录 frontmatter 增加 `archived_at`。
33. restore 时当前记录区已有同名 task-id：停止，不覆盖。
34. restore 后 status=paused、`updated_at` 不变、记录 `restored_at`；load 只读；下一次 save 才记录 in-progress。
35. 归档任务不参与无 ID 自动选择；显式 `load --archived` 可查看。

## 旧文件与格式迁移

36. 1.0.0 旧文件缺少 `schema`/`updated_at`：list/load 标 unknown；不自动选择；不批量改写。
37. save 迁移当前旧任务：写入 `migrated_at`，但不得把无法确认的旧 `updated_at` 改成当前时间；不得因此变 fresh。
38. 旧文件 status 无法确认：写 unknown，不默认 in-progress。
39. 未支持 schema：只读并告警，不自动降级覆盖。
40. 无效 `stale_after_days`（非正整数）：告警后使用默认 14。

## 上下文与模板

41. 干净测试环境（无额外导入、hook 或读取要求）：启动后没有由本 Skill 注入的交接正文；这是干净环境验收，不是所有环境的绝对保证。
42. 从非 Skill 所在目录启动，执行 save/load：验证模型能否读取 `references/task-template.md`；失败则记录为发布前待修项。
43. 不要把 `handover.md` 用 `@handover.md` import 进 `CLAUDE.md`；如测试导入，确认它确实会进入上下文，并记录为反例。

## 指纹绑定、范围与归档组

44. 任务 frontmatter 的 `snapshot_id` 与 sidecar 不一致：`check` 返回 unknown，不继续比较内容或判 matched。
45. 任务 frontmatter 的 `fingerprint_file`/`fingerprint_sha256` 与 sidecar 不一致：`check` 返回 unknown。
46. 正文已更新、指纹生成失败、旧 sidecar 仍在：`snapshot_id` 不匹配或字段缺失 → unknown；不得误用旧指纹。
47. 指纹生成后的 `check` 只证明检查时现场与刚生成的基线一致；不证明正文语义与代码一致，也不证明正文整理期间代码始终未变。构造“正文按 A 写、代码变 B、对 B 生成基线、check matched”的场景，确认报告不会宣称正文与代码一致。
48. 保存后新增声明范围内的相关文件：`check` 报 changed（git status 条目变化）。
49. 保存后删除或重命名声明范围内的相关文件：`check` 报 changed。
50. 文件内容不变，但暂存状态变化（staged/unstaged）：`check` 报 changed。
51. branch 或 HEAD 变化，但声明范围内文件内容相同：`check` 报 changed（git 现场变化），并在报告中区分 content/git。
52. 部分文件不可检查，但另一个文件已明确变化：`check` 返回 changed，并标注 `incomplete: true`；不能用 unknown 掩盖已知变化。
53. 部分文件不可检查，且没有明确变化：`check` 返回 unknown。
54. 检查完整且无差异：`check` 返回 matched，并注明 scope 的文件数与 git 条目数。
55. 外部 paths 文件不是用户提供、也不是本次 save 创建：不使用、不自动搜索。
56. 外部 paths 文件中的目标路径在项目外或为绝对路径：拒绝并报告，不读取目标。
57. 归档：任务 Markdown 与同 stem 的 `.fingerprint.json` 作为同一组移动；归档任务 `fingerprint_file` 指向归档 sidecar；`fingerprint_sha256` 不变。
58. 归档时 sidecar 缺失：只归档任务，fingerprint 字段置 null，consistency=unknown。
59. 归档时任务或 sidecar 只有一个移动成功：报告实际位置和不完整状态，不删除任务文件。
60. restore：任务与 sidecar 同组恢复，`fingerprint_file` 指回当前路径，`fingerprint_sha256` 保持不变；不重新生成基线。
61. restore 时当前记录区已有同名 task-id 或同名 sidecar：停止，不覆盖。
62. 归档/恢复后 `updated_at` 不变；`archived_at`/`restored_at` 按规则记录。
63. 脚本 fixture 测试与 Claude Code 端到端测试分别记录；静态检查、SHA256SUMS 不当作端到端通过。
64. paths 清单里出现 `.claude/skills/...`、`.git/...` 或 `handover.md`：fingerprint 应跳过并在 `skipped_excluded` 中报告，不得把它们算入声明范围。
65. Claude Code E2E：保存后 sidecar 只包含业务相关文件，不包含 `.claude/skills/handover/` 的 SKILL.md / CHECKLIST.md。
66. `handover.md` 使用“任务列表”列出所有任务；不出现唯一的“当前任务”作为恢复授权；多任务时全部列出。
67. 同一会话先 `load` A 再 `load` B：确认 A 的内容仍在上下文中；切换不相关任务时应提示新会话或先 `/clear`，不把“加载 B”当成撤回 A。
68. 检查 Auto Memory / memory 目录：本 Skill 不写入任务进度；若其他机制写入旧任务状态，记录为外部上下文风险。
69. list 标题：frontmatter 有 `title` 时显示 title；缺失时回退显示 task-id，不读取正文。
70. load 的一致性核验优先运行 `check` 并读取精简结果；不得为了汇报而读取 sidecar 全文（排错时除外）。

## 上下文预算与按需读取

71. `SKILL.md` 不超过 12KB；模式细节在 `references/` 中按需加载。
72. `brief` 默认不读完整任务正文；证据读取 ≤ 4k tokens；输出覆盖质量检查表（用途/技术栈/架构/验证/风险/并行/未知/来源）。
73. `load` 默认不读完整任务正文；证据读取 ≤ 6k tokens（不含 SKILL.md、模式 reference 和 `check` 输出）；需要细节时按章节定点读取。
74. “接手必读”使用 `path#symbol` / `path:start-end`，不写裸文件清单；总读取预算 ≤ 1.5k tokens。
75. 大文件（>200 行或 >8KB）使用 Grep/Read offset，不整文件读取；`git diff` 先 `--stat` 再按相关路径读取。
76. 超出预算时报告“未读/截断”，不静默丢弃；输出本次读取 N 个文件 / 约 M tokens。
77. `references/` 中新增的 brief-load / save / archive-restore / data-model / fingerprint 均存在且链接可解析。
78. 任务文档不重复状态：同一状态不在 frontmatter、快速摘要、当前进度、入口各写一遍。
79. 任务文档/输出使用紧凑 Markdown；无装饰分隔线、无行尾空格、无宽表格；不粘贴代码/diff。
80. 必要空格/标点保留；不做激进 minify；优先砍重复和无关内容，而不是空格。
81. `stats` 输出 frontmatter 与各 `##` 章节的近似 token/占比/行数；不写文件。
82. `stats --json` 输出合法 JSON，percent 合计约 100；缺失文件/非法 task-id/项目外 task-file 返回 exit 2。
83. 模型加载文档删除装饰性空格/空行/分隔线；保留结构必需。
84. 跨文件去重：`handover.md` 不复制任务摘要/验证证据/任务内风险；同一验证命令只写一次。
85. 不为 token 优化破坏 YAML/JSON schema 或必要结构；`README`/`CHECKLIST`/`E2E_TEST_RESULTS` 保持可读。
86. `analysis` 只读：不改变任务、不修改配置、不自动关闭 MCP server。
87. `analysis` 报告按 system prompt、MCP server tool schema、transcript 类别、磁盘配置分组；区分 measured/estimate/unknown。
88. `analysis` 不打印 transcript 正文、tool result 内容或密钥；`analysis` 不能作为 task-id。
89. save 前对旧记录跑 `check`；`changed` 时列出变化路径并对账；`unknown` 时说明；`stale` 时只读摘要/相关章节。
90. save 不把旧结论当当前事实；已存在 task-id 但目标不同时停止覆盖；completed/cancelled 不隐式重开。
91. brief 读取任务列表标题/status、近期 commit/工作树；不读任务正文。
92. brief 质量检查表包含“当前项目状态（摘要级）”；需要任务细节时使用 `load`。
93. `load --deep` 仅在显式指定时启用；默认 `load` 不 deep。
94. `load --deep` 读完整任务正文 + 完整“接手必读”；不读无关项目/其他任务；默认上限 30k tokens，报告未读/截断。
95. `load --deep` 仍只读、仍先 `check`；`changed`/`unknown`/`stale` 需对账；不激活、不 commit、不 `/clear`。

## v1.1.1 回归

96. `.handover/config.yaml` 不带 `---` 分隔符时，`stale_after_days` 仍生效；无效值告警并使用默认 14。
97. 任务 frontmatter 缺少 `fingerprint_file`、`fingerprint_sha256`、`schema`、`task_id` 或 `project_root`，或与 sidecar/当前项目不一致时，`check` 必须返回 unknown，不得 matched。
98. fingerprint 声明范围为空时拒绝生成基线；不得出现 0 文件 matched。
99. 根目录声明的文件只覆盖根目录直属文件；根目录新增文件触发 changed，子目录无关新增不触发。
100. sidecar 输出路径是符号链接时拒绝写入，业务文件内容保持不变。
101. `.handover` 或单个任务文件指向项目外时，list 不读取外部内容；目录级指向项目外时停止并报告。
102. matched 输出包含范围外变化计数 `out_of_scope_changes`，并注明只覆盖声明范围。
103. 声明文件超过大小上限但大小已变化时，check 判 changed；大小不可判定时 unknown。
104. 重复 task_id 在 list 的异常区域可见，不被静默隐藏。
105. `--scope-dir .` 按根目录直属文件处理，不递归整个仓库。
106. archive/restore 先复制任务与 sidecar 到目标并回读，确认后再删除源；删除源失败时保留源并报告，不宣称移动完成。
107. 首次 save 前 `.handover/` 尚不存在时，`ignore-check` 仍识别 `.gitignore` 中的 `.handover/` 目录规则，不误报 `not-ignored`。
108. 无 ID `save` 只复用 active 任务（in-progress/pending/blocked/paused）；completed/cancelled/archived 不是目标，默认新建 `in-progress` 任务。
109. 目标为 completed/cancelled 时 `status-guard` exit 1，`save` 停止并询问新建 task-id 或明确重开；只有用户明确授权重开才使用 `--reopen-authorised` 并记录原因。
110. 新任务默认 `in-progress`；`completed` 仅在用户明确确认完成且验收证据存在时写入；声明与证据冲突时用 `blocked`，不因 save/clear/context 阈值推断完成。
