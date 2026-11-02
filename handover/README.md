# Handover Skill

版本：1.1.0-draft

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

**测试 1.1 草稿时建议项目级安装，或临时把 name 改为 `handover-v11`，不要覆盖正在使用的 1.0.0。**

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
```

- save：保存当前会话中该任务的目标、状态和证据，不保存完整窗口。成功后输出精确的 `/handover load <task-id>`。
- list：默认只列活跃状态；`--all` 含已结束与归档，并显示被隐藏数量；另有“待识别记录”区域。
- load：只恢复并核验，不自动继续开发；不改变 status 或 `updated_at`。
- brief：了解当前项目背景，不执行旧任务。
- archive：默认只归档 completed/cancelled；不删除，更新入口链接。
- restore：恢复归档到当前记录区，状态为 paused；需重新 `load` 核验后再继续。
- 不带参数默认 save；不带 ID 的 load 仅在“唯一活跃任务且 freshness=fresh”时自动选择，多个或 stale/unknown 时列候选。
- task-id 允许 1–64 位小写字母、数字和短横线，首位必须是字母或数字。保留字 save/load/brief/list/archive/restore 不能作为 task-id。
- `/handover login` 是 `/handover save login` 的简写。

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
- `updated_at` 只在实质 save 时更新；list/load 不刷新。
- 这些检查只在命令调用时发生，没有后台计时器。

### 现场指纹（consistency 的证据）

仅比较 branch/HEAD/worktree/dirty 状态不足以证明内容一致：同一 branch、同一 HEAD、同样“有未提交修改”，文件内容仍可能已经变化。因此 v1.1 使用内容指纹：

- 保存时记录声明范围内文件的内容 SHA-256，以及相关 git 现场（branch、HEAD、status 条目），写入 `.handover/<task-id>.fingerprint.json`；sidecar 的 SHA-256 写入任务 frontmatter 的 `fingerprint_sha256`。
- 声明范围 = 任务相关文件 + `接手必读` 路径 + 显式提到路径 + 这些路径所在目录；排除 `.handover/`、`handover.md`、`.claude/` 和 `.git/`，避免 save 自己或 Skill 安装目录改变现场。
- git 现场覆盖声明范围内的新增、删除、重命名、暂存/未暂存状态变化；范围外改动只计数，不参与 matched 判断。
- 任务 frontmatter 与 sidecar 共享 `snapshot_id`。`check` 先核对 `snapshot_id`、`fingerprint_file`、`fingerprint_sha256` 是否属于同一次保存；不匹配 → unknown。正文已更新但指纹仍是旧值时，不会伪装成 matched。
- 指纹生成后必须再跑一次 `check`，确认正文写完到指纹生成之间代码没有被再次修改；若返回 changed，报告“快照期间代码变化”，不要宣称干净保存。
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
- `list` 只读任务 frontmatter（当前是指令；如需确定性，使用 `scripts/handover.py list`）。
- 不要把 `handover.md` 用 `@handover.md` import 进 `CLAUDE.md`；不要在 `SessionStart` hook 注入全文；最多注入一行“有 in-progress 任务，是否 load”。
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
- `archive`/`restore` 只处理 schema 1；旧文件先按上述规则迁移，或由用户明确选择并承担校验。

## YAML 与配置校验

- 缺失值统一用 `null`，不用空字符串或字符串 `"unknown"` 充当缺失值。
- 日期必须是含时区的 ISO 8601 字符串；否则视为无效。
- `schema` 是文件格式版本，不是 Skill 版本；未支持的 schema 只读并告警，不自动降级覆盖。
- `stale_after_days` 必须是合法正整数；无效配置告警后使用默认 14。
- 模板中的示例日期仅作格式示例，不得原样写入真实任务。

## 待验证项（v1.1-draft）

- 模板路径：`SKILL.md` 仍使用 `references/task-template.md` 内联引用。2026-11-02 的最小 E2E 从非 Skill 所在目录启动，仍生成了完整模板结构，说明模板读取很可能成功；但该次运行禁用了会话持久化，没有保留精确工具调用，因此仍标为“待确认”。若后续失败，再改成 Markdown 链接或 `${CLAUDE_SKILL_DIR}`。本 draft 不预设修改。
- 文档长度：先观察真实任务文档的行数与内容；只有确实重复 specs/diffs/代码或明显膨胀时，才加软性 guideline。本 draft 不设硬性 100–200 行限制。
- 固定 token 阈值：本 draft 不采用；60% 仅作个人提醒。
- archive/restore 仍是指令型操作，尚未脚本化；记录组规则已写明，但文件移动与入口更新的真实失败行为需在端到端验收中确认。

## 测试声明

当前完成设计评审、结构/静态检查、脚本 fixture 测试，以及最小 Claude Code E2E（save → load → 改代码 → load 检出变化）；结果见 `VALIDATION.md`、`FIXTURE_TEST_RESULTS.md`、`E2E_TEST_RESULTS.md`。archive/restore、项目隔离、旧文件迁移、并发尚未执行，不能把已有结果当作完整端到端通过。

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

这是指令型 Skill，不是后台服务或确定性状态机。效果依赖 Claude Code 的工具权限、模型执行及当前可访问上下文。不能恢复从未保存且已不可访问的历史；不能自动备份未提交代码；不保证多写者并发安全；不自动跨 worktree 同步；不会自动清理或归档；`freshness` 只是基于 `updated_at` 的启发式，不是任务有效性的证明；`consistency` 依赖可用的指纹基线，没有基线或文件不可读时为 unknown。

## 文件

- `SKILL.md`：主流程与安全边界。
- `references/task-template.md`：任务文档结构（YAML frontmatter + 正文）。
- `CHECKLIST.md`：首次使用验收场景。
- `SOURCES.md`：官方参考链接。
- `scripts/handover.py`：可选的 list / fingerprint / check 工具。
- `VALIDATION.md`：结构/静态检查结果。
- `FIXTURE_TEST_RESULTS.md`：脚本 fixture 测试结果（与 Claude Code 端到端测试分开）。
- `E2E_TEST_RESULTS.md`：Claude Code 真实 save/load/change 链路结果（与 fixture 测试分开）。
