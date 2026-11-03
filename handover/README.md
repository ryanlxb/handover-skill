# Handover Skill

版本：1.1.0-rc.1

用途：把当前会话的任务状态保存到项目本地，让新会话核验后继续，或只加载背景开始新任务。不是聊天记录备份，也不是代码备份。

## 设计不变量

- 手动循环：`save` → 确认保存成功 → `/clear` → 手动 `load`。
- 不自动保存、不自动删除、不自动 `/clear`、不自动 commit。
- 项目独立存储；不跨项目扫描；不写全局 last-active 指针，也不写唯一的“当前任务”作为恢复授权。
- 历史与现场分离：旧记录只作线索，`load` 必须核验当前代码现场。
- `load` 始终只读；不改变 status 或 `updated_at`。

## 安装

解压后把整个 handover 文件夹复制到以下位置之一（不要把内容直接散放到 skills 根目录）：

- 全局：`~/.claude/skills/handover/`
- 单项目：`<项目>/.claude/skills/handover/`

最终必须存在 `.../skills/handover/SKILL.md`。不要再套一层 handover。若已有同名 Skill，先自行备份再替换。

**安装 1.1.0-rc.1 时建议先备份现有 Skill；若要并行试用，可用项目级安装或临时改 name，不要直接覆盖正在使用的稳定版。**

全局安装只是所有项目共用规则；任务数据仍分别存放在各项目，不存入全局 Skill 目录。

## 日常使用

```text
/handover save login
/handover list
/handover load login
/handover brief
/handover archive login
/handover restore login-20261102t103000z
/handover load --archived login-20261102t103000z
/handover analysis
```

- save：保存当前会话中该任务的目标、状态和证据，不保存完整窗口。成功后输出精确的 `/handover load <task-id>`。
- list：默认只列活跃状态；`--all` 含已结束与归档，并显示被隐藏数量；另有“待识别记录”区域。标题取 frontmatter 的 `title`，缺失时回退显示 task-id（不读正文）。
- load：只恢复并核验，不自动继续开发；不改变 status 或 `updated_at`。
- brief：了解当前项目背景 + 摘要级项目状态（任务列表标题/status、近期 commit/工作树），不执行旧任务，不读任务正文。
- archive：默认只归档 completed/cancelled；不删除，更新入口链接。
- restore：恢复归档到当前记录区，状态为 paused；需重新 `load` 核验后再继续。
- analysis：只读审计当前会话的 context 使用，按 system prompt、MCP 工具 schema、transcript、磁盘配置分组给出建议；不改变任务或配置，不自动关闭 MCP server。
- 不带参数默认 save；不带 ID 的 load 仅在“唯一 in-progress 任务且 freshness=fresh”时自动选择；多个 in-progress、stale/unknown、或只有 pending/blocked/paused 时列候选，不自动选择；只有 completed/cancelled/归档（或没有任何任务）时提示没有进行中任务。fresh 只允许自动选择，不跳过 consistency 核验，也不自动开发。
- task-id 允许 1–64 位小写字母、数字和短横线，首位必须是字母或数字。保留字 save/load/brief/list/archive/restore/analysis 不能作为 task-id。
- `/handover login` 是 `/handover save login` 的简写。

## 上下文预算与按需读取

- `brief`/`load` 默认先读索引和摘要，再按需读正文；不重复读已在上下文中的文件。
- `brief` 默认读取：项目入口（任务列表标题/status）+ README/背景文档开头 +（如指定任务或入口只有一个任务）快速接手摘要 + git 状态 + 近期 commit；证据读取默认 ≤ 4k tokens。
- `load` 默认读取：项目入口 + task frontmatter + 快速接手摘要 + 当前进度 + 下一步 + 并行与依赖 + `check` 摘要 + “接手必读”索引；证据读取默认 ≤ 6k tokens（不含 SKILL.md、模式 reference 和 `check` 输出）。
- “接手必读”是索引：`path#symbol` / `path:start-end`；不整文件读取；默认 ≤ 1.5k tokens。
- 大文件用 Grep 或 Read offset；`git diff` 先 `--stat`，再按相关路径读取。
- 需要完整细节时，先读用户点名的章节；报告“已读/未读/截断”。
- 模式细节在 `references/` 中按需加载；`SKILL.md` 保持轻量。
- Token 卫生：只写 delta，不重复状态；紧凑 Markdown；避免宽表格；不粘贴代码/diff；必要的空格/标点不删。结构化小块可用 TSV/TOON，任务文档主体仍用 Markdown。

## Token 效率原则（模型加载内容）

适用于 `SKILL.md`、`references/`、任务文档、`handover.md`、brief/load 输出；目标是有限 context 中装最多可核验信息。

- 保留结构必需：标题、列表标记、frontmatter 分隔符、key/value 分隔符、必要换行。
- 删除装饰性空格/对齐空格/行尾空格、连续空行、水平分隔线、emoji/ASCII 装饰。
- 跨文件去重：`handover.md` 只保留任务索引和真正的跨任务风险；任务摘要/验证证据/任务内风险不复制。
- 同一验证命令只写一次；其他章节引用。
- 用 `path#symbol` / commit hash / URL 引用，不粘贴代码/diff。
- 不做 zero-space minify；不破坏 YAML/JSON schema。
- `README` / `CHECKLIST` / `E2E_TEST_RESULTS` 是给人看的，不参与模型上下文，保持可读。
- 用 `stats` 测量章节占比，优先砍高占比的重复/无关内容。

## Token 统计（可选）

保存后可以查看任务文档的近似 token 分布：

```text
python3 -I scripts/handover.py stats --root <project> --task <task-id>
python3 -I scripts/handover.py stats --root <project> --task <task-id> --json
```

输出 frontmatter 与各 `##` 章节的近似 token、占比、行数，以及空行/行尾空格/装饰性分隔线统计。估算使用 UTF-8 bytes / 3，不是分词器精确值；用于找“最贵的章节”，不要按空格盲目压缩。

## Context 分析（可选）

`/handover analysis` 只读审计当前会话的 context 使用。它读取会话 transcript 的 `api-request-shape`（system prompt + tool schemas）和消息 blob，按 MCP server、消息类别、tool result、磁盘配置分组，并给出建议：

```text
python3 -I scripts/handover.py analysis --root <project> [--session <id>] [--context-window <n>] [--json]
```

报告区分“request prefix（较精确）”“transcript blobs（可能含已压缩历史）”“config on disk（参考，可能重叠）”；`/context` 仍是官方口径。只读，不自动关闭 MCP server。

## 术语

| 术语 | 含义 |
|---|---|
| 当前记录区 | `.handover/` 顶层的任务文件 |
| 活跃状态 | in-progress / pending / blocked / paused |
| 已结束状态 | completed / cancelled |
| 归档区 | `.handover/archive/` |
| 待识别记录 | status 缺失或 unknown、YAML 解析失败、未支持 schema、重复 task-id、文件名与 task_id 不一致 |

未归档的 completed/cancelled 仍在**当前记录区**，但不在**活跃状态**集合中；显式 `load <task-id>` 可以查看，无 ID load 不会选择它们。

## 何时不用 handover

- 同一会话继续：优先 `claude --resume <name>` 或 `claude --continue`；它们恢复完整对话，保真度最高。
- 同一会话太长但不想换：`/compact keep ...`，不必新开窗口。
- 想试不同方案：`/branch <name>`，原会话保留。
- 持久项目知识（架构、规范、命令）：写 `CLAUDE.md`，不要写进 handover。
- handover 只负责跨会话边界：新窗口、新任务、跨工具、跨机器、`/clear` 后、旧上下文不可访问。

## 何时保存

- 60% 是你个人的提醒点，不是强制阈值；没有固定 token 数字。
- 阶段完成、测试通过、出现关键决策、任务阻塞/等待、准备 `/clear`/`/compact`/切换窗口/切换任务时，都可以保存。
- 不要等到接近上限；那时模型可能已经“变钝”，总结质量会下降。
- save 前先对旧记录跑 `check`：`changed` 时列出变化路径并对账，`unknown` 时说明原因，`stale` 时只读摘要/相关章节；不要把旧结论当当前事实。
- 保存后重点检查：目标、未完成项、关键决策、阻塞、验证状态是否齐全。

## 数据位置与隔离

```text
project-a/
  handover.md
  .handover/
    config.yaml                  # 可选：stale_after_days: 14
    login.md
    login.fingerprint.json       # 可选：现场指纹 sidecar
    archive/
      login-20261102t103000z.md
project-b/
  handover.md
  .handover/
    login.md
```

两个 login 不冲突。在 A 中不会默认搜索 B。Git 项目默认按当前工作树根目录隔离；monorepo 默认视为一个项目，除非用户明确指定子项目根目录。worktree 默认各用本地文件，不自动同步；需要跨 worktree 时由用户明确搬运并核验 branch/HEAD。

- Git 项目使用本 Skill 时，必须把 `.handover/` 和 `handover.md` 加入项目 `.gitignore`，并确认它们未被 Git 跟踪；仅存在忽略规则不足以证明不会被提交。任务 frontmatter 含本地绝对路径；提交任务数据会泄露本机路径和任务上下文。Skill 不会自动修改 `.gitignore` 或执行 `git rm`，但 `save` 会提醒未忽略或已被跟踪的路径。
- 可用 `scripts/handover.py ignore-check --root <项目根>` 做确定性检查：exit 0 = ok/not-git；1 = warning（至少一个未忽略或已被跟踪）；2 = unknown。该命令只读，不修改 `.gitignore`，也不执行 `git rm`。

## 任务状态

| 状态 | 含义 |
|---|---|
| in-progress | 正在做 |
| pending | 下一步，未开始 |
| blocked | 等待外部依赖/他人 |
| paused | 主动搁置 |
| completed | 完成且已验证 |
| cancelled | 放弃 |
| unknown | 仅用于缺失、损坏或无法识别的记录；不是用户可选状态 |

## 新鲜度与现场一致性

三轴分开记录，不互相替代：

| 维度 | 取值 | 计算方式 |
|---|---|---|
| status | 六种业务状态 + unknown | 文件里记录 |
| freshness | fresh / stale / unknown | `updated_at` 与 `stale_after_days` 比较；缺失/异常 = unknown |
| consistency | matched / changed / unknown | `load` 时按现场指纹重新计算；无基线 = unknown |

- `stale_after_days` 默认 14，可在 `.handover/config.yaml` 按项目调整；它只是提醒阈值，不是技术事实，不代表任务失效。
- 阈值边界：`age >= stale_after_days` 为 stale；`age < stale_after_days` 为 fresh。
- `updated_at` 为 null、无法解析或未来时间等异常时为 unknown，不能默认 fresh。
- `stale` 不覆盖 status，不触发删除。
- `changed` 表示声明范围有明确变化；`unknown` 表示无法核验；`matched` 只表示“声明范围内一致”，不表示任务语义仍然正确。
- **语义陈旧**：任务进度/决策/外部依赖变化但未 save，fingerprint 可能仍匹配；只有新的 save 或人工复核能发现。save 前应先 check 旧记录并对账。
- `updated_at` 只在实质 save 时更新；list/load 不刷新。
- 这些检查只在命令调用时发生，没有后台计时器；不自动删除过期记录。

### 现场指纹（consistency 的证据）

仅比较 branch/HEAD/worktree/dirty 状态不足以证明内容一致：同一 branch、同一 HEAD、同样“有未提交修改”，文件内容仍可能已经变化。因此 v1.1 使用内容指纹：

- 保存时记录声明范围内文件的内容 SHA-256，以及相关 git 现场（branch、HEAD、status 条目），写入 `.handover/<task-id>.fingerprint.json`；sidecar 的 SHA-256 写入任务 frontmatter 的 `fingerprint_sha256`。
- 声明范围 = 任务相关文件 + `接手必读` 路径 + 显式提到路径 + 这些路径所在目录；排除 `.handover/`、`handover.md`、`.claude/` 和 `.git/`，避免 save 自己或 Skill 安装目录改变现场。当前版本默认排除整个 `.claude/`：`.claude/` 下的项目配置变化不在一致性检查范围内；这不是“所有项目配置都不属于任务现场”的断言。
- git 现场覆盖声明范围内的新增、删除、重命名、暂存/未暂存状态变化；范围外改动只计数，不参与 matched 判断。
- 任务 frontmatter 与 sidecar 共享 `snapshot_id`。`check` 先核对 `snapshot_id`、`fingerprint_file`、`fingerprint_sha256` 是否属于同一次保存；不匹配 → unknown。正文已更新但指纹仍是旧值时，不会伪装成 matched。
- 指纹生成后必须再跑一次 `check`，确认检查时现场与刚生成的基线一致，并确认任务文件与 sidecar 的 `snapshot_id`/SHA 绑定一致；若返回 changed，报告“检查时现场与基线不一致”，不要宣称干净保存。它不证明正文语义与代码一致，也不证明正文整理期间代码始终未变。
- 结果优先级：已发现明确差异（内容或 git）→ changed，并注明检查是否不完整；未发现明确差异但检查不完整 → unknown；检查完整且无差异 → matched。
- `matched` 只表示“声明的检查范围内一致”，不是整个项目一致。
- 优先用 `scripts/handover.py` 生成和核对；脚本不可用时 `snapshot_id`/`fingerprint_file`/`fingerprint_sha256` 置 null，consistency 必须为 unknown，不得用 branch/HEAD 代替内容指纹。
- 外部 paths 文件：只使用用户明确提供、或本次 save 自己创建的清单；不自动搜索外部清单，不执行清单内容；清单中的目标路径必须位于项目内，相对路径以项目根目录为基准。

## 清理与归档

- 本 Skill 不会自动删除任何 handover；completed/cancelled 会一直保留，直到你手动 archive 或删除。
- v1.1 不提供永久删除；`archive` 是可逆的。
- `archive` 默认只允许 completed/cancelled；stale 的活跃任务只提示复核，不自动归档。用户明确要求归档其他状态时，必须写明原因。
- 同名归档不覆盖；使用 `<task-id>-<小写 UTC 时间戳>`，冲突停止。
- 归档会更新 `handover.md` 链接；归档记录不参与无 ID 自动选择。
- 记录组 = 任务 Markdown + 可选 fingerprint sidecar；归档/恢复时作为同一组移动，归档 sidecar 与归档 Markdown 使用同一 stem 的 `.fingerprint.json`。
- 归档前核对 sidecar 的 `snapshot_id` 与任务 frontmatter 一致；不一致则停止，不把不同次保存的文件一起归档。
- 归档时把归档任务 frontmatter 的 `fingerprint_file` 指向归档 sidecar；`fingerprint_sha256` 保持不变，不重新生成基线。
- sidecar 缺失时只归档/恢复任务 Markdown，`fingerprint_file`/`fingerprint_sha256` 置 null，consistency 为 unknown。
- 任务或 sidecar 只有一个移动成功时，报告实际位置、已完成步骤和不完整状态；任务文件是事实来源，入口只是导航，不删除任务文件。
- 任务文件是事实来源，入口只是导航。移动前校验源/目标，移动后回读；入口更新失败时报告文件实际位置和已完成步骤，不删除任务文件。
- `archive` 不改变 `updated_at`；`restore` 也不让记录自动变 fresh。

## 恢复闭环

`restore` → `load` → 继续工作 → 下一次 `save`：

1. `restore <archive-id>`：检查当前记录区无同名 task-id 或同名 sidecar；核对归档任务与 sidecar 的 `snapshot_id`；把两者作为同一组移回，`fingerprint_file` 指回当前路径，`fingerprint_sha256` 保持不变，不重新生成基线。status 设为 paused，记录 `restored_at`，`updated_at` 保持不变。
2. `load <task-id>`：只读核验，不改变 status 或 `updated_at`；先核对任务/sidecar 的 `snapshot_id` 绑定，再比较内容与 git 现场。
3. 用户明确要求继续后，开始工作；下一次 `save` 根据实际情况记录为 in-progress。
4. 没有单独的 `activate` 命令；`load` 不会自动激活，README 也不暗示它会。
5. 如果 sidecar 缺失，恢复任务本身，但 consistency 必须为 unknown；如果任一文件移动失败，报告实际位置和不完整状态，不删除任务文件。

## 上下文边界

- 本 Skill 不配置启动时注入，也不主动批量加载交接记录；其他项目指令、导入、hook 或用户要求仍可能导致文件被读取。
- `handover.md` 是普通文件，不是 `CLAUDE.md`/`AGENTS.md`；Claude Code 不会仅因它存在而通过本 Skill 加载它。
- `save`/`brief`/`load` 在各自流程中会按需读取相关任务文件；这不是权限隔离。
- `list` 只读任务 frontmatter（当前是指令；如需确定性，使用 `scripts/handover.py list`）；标题取 frontmatter `title`，缺失时回退显示 task-id，不读正文。
- `load` 的一致性核验优先运行 `scripts/handover.py check`，只读取其精简结果；完整 sidecar 留在磁盘，排错时再读。
- 本 Skill 不主动把任务进度写入长期记忆（Auto Memory / memory 文件）；但 Auto Memory、`CLAUDE.md`、其他规则和 hook 仍可能把旧信息带入新会话，需另行检查。
- 同一会话连续 `load` 不同任务时，先前任务正文仍在上下文中；切换不相关任务优先新会话或先 `/clear` 再 `load`。归档、删除任务文件或加载另一任务都不会撤回已读内容。
- 不要把 `handover.md` 用 `@handover.md` import 进 `CLAUDE.md`；不要在 `SessionStart` hook 注入全文；最多注入一行“有 in-progress 任务，是否 load”。
- `brief`/`load` 有默认读取预算；超出时报告未读/截断，不静默丢弃。详细读取集见 `references/brief-load.md`。
- 没有后台计时器；所有检查只在命令调用时发生。
- 干净测试环境的验收：在没有额外导入、hook 或读取要求时，启动后没有由本 Skill 注入的交接正文；这不构成对所有环境的绝对保证。

## 旧文件与格式迁移

- 只迁移当前 save 的任务；不批量改写。
- 迁移只补 frontmatter，不改变任务状态，不把旧记录“洗新”：
  - 能可靠解析旧更新时间则保留；否则 `updated_at = null`，freshness = unknown。
  - 写入 `migrated_at = now`，与 `updated_at` 分开。
  - status 无法确认时写 unknown，不默认 in-progress。
  - 迁移不是实质核验；不更新 `updated_at`。
- 未支持 schema 只读并告警；不自动降级覆盖。
- `archive`/`restore` 只处理 schema 1；旧文件必须先按上述规则完成迁移，再执行 archive/restore。用户授权不能替代格式和路径校验。
- 报告使用“正文内容保留”；只有实际做过字节比较时才可写“字节一致”。

## YAML 与配置校验

- 缺失值统一用 `null`，不用空字符串或字符串 `"unknown"` 充当缺失值。
- 日期必须是含时区的 ISO 8601 字符串；否则视为无效。
- `schema` 是文件格式版本，不是 Skill 版本；未支持的 schema 只读并告警，不自动降级覆盖。
- `stale_after_days` 必须是合法正整数；无效配置告警后使用默认 14。
- 模板中的示例日期仅作格式示例，不得原样写入真实任务。

## 待验证项（v1.1.0-rc.1）

- 模板路径：`SKILL.md` 不再内联模板内容；`references/save.md` 通过相对路径 `task-template.md` 引用，`SKILL.md` 通过 Markdown 链接路由到 `references/`。2026-11-02 的最小 E2E 验证的是旧版内联路径；新版尚未重新 E2E，读取模板的真实行为仍标为“待确认”。若失败，按 harness 给出的 Skill base directory 解析。
- 文档长度：初始 draft 不设硬性限制；后续观察到 `brief`/`load` 上下文成本过高，现已改为按需读取 + 软性预算（任务文档建议 ≤ 200 行 / ≤ 4k tokens；`SKILL.md` ≤ 12KB）。该预算不改变任务语义，只限制默认读取范围。
- 固定 token 阈值：本 draft 不采用；60% 仅作个人提醒。
- archive/restore 仍是指令型操作，尚未脚本化；记录组规则已写明，但文件移动与入口更新的真实失败行为需在端到端验收中确认。

## 测试声明

当前完成设计评审、结构/静态检查、脚本 fixture 测试、最小 Claude Code E2E（save → load → 改代码 → load 检出变化），以及受控夹具验收（无 ID load 矩阵、多轮交接、A/B 隔离、archive/restore、1.0 风格迁移）；结果见 `VALIDATION.md`、`FIXTURE_TEST_RESULTS.md`、`E2E_TEST_RESULTS.md`。受控夹具验收不是真实业务项目试用；真实业务项目、真实 1.0.0 制品、并发/真实权限模式与完整 70 项 checklist 尚未执行，不能把已有结果当作完整端到端通过。

- `SHA256SUMS.txt` 只证明列入清单的文件与对应摘要一致，不证明逻辑正确、安装成功、权限安全或真实行为。
- 截断标记检查是启发式，不等于自然语言绝无残句；聊天输出可能被截断，以磁盘文件和真实调用结果为准。
- 脚本 fixture 测试与 Claude Code 端到端测试分开记录，不能互相替代。

## 下一轮验收顺序

先冻结功能，按以下顺序验证；每项记录命令、预期、实际结果、文件变化和是否通过：

1. **真实主链路**：`save` → 确认任务文件与指纹 → `/clear` → `load` → 修改代码 → `load` 检出变化 → `save`。
2. **项目隔离**：A、B 项目使用同名 task-id，确认互不展示、互不读取。
3. **生命周期**：`completed` → `archive`（任务 + sidecar 同组）→ 查看历史 → `restore`（同组）→ `load` → 继续工作 → `save`。
4. **兼容与失败**：真实 1.0.0 文件迁移；指纹生成失败；入口更新失败；归档目标冲突；sidecar 缺失。

## 限制

这是指令型 Skill，不是后台服务或确定性状态机。效果依赖 Claude Code 的工具权限、模型执行及当前可访问上下文。不能恢复从未保存且已不可访问的历史；不能自动备份未提交代码；不保证多写者并发安全；不自动跨 worktree 同步；不会自动清理或归档；`freshness` 只是基于 `updated_at` 的启发式，不是任务有效性的证明；`consistency` 依赖可用的指纹基线，没有基线或文件不可读时为 unknown；`matched` 只表示声明范围内一致，不表示任务语义仍然正确。

## 文件

- `SKILL.md`：轻量路由、项目识别、安全边界与读取预算。
- `references/task-template.md`：任务文档结构（YAML frontmatter + 正文）。
- `references/brief-load.md`：`brief`/`load` 的默认读取集、质量检查表和输出。
- `references/save.md`：`save` 流程。
- `references/archive-restore.md`：`archive`/`restore` 记录组规则。
- `references/data-model.md`：数据布局、task-id、YAML、状态轴、旧格式迁移。
- `references/fingerprint.md`：指纹与忽略检查。
- `references/analysis.md`：只读 context 审计的步骤、报告格式和安全边界。
- `CHECKLIST.md`：首次使用验收场景。
- `SOURCES.md`：官方参考链接。
- `scripts/handover.py`：可选的 list / fingerprint / check / ignore-check / stats 工具。
- `VALIDATION.md`：结构/静态检查结果。
- `FIXTURE_TEST_RESULTS.md`：脚本 fixture 测试结果（与 Claude Code 端到端测试分开）。
- `E2E_TEST_RESULTS.md`：Claude Code 真实 save/load/change 链路结果（与 fixture 测试分开）。
