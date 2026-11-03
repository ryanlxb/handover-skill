---
schema: 1
snapshot_id: null
task_id: <task-id>
title: <任务标题>
status: in-progress
updated_at: 2026-11-02T10:30:00+08:00
migrated_at: null
archived_at: null
restored_at: null
project_root: <absolute path>
branch: <branch>
head: <full sha>
worktree: <absolute path>
fingerprint_file: .handover/<task-id>.fingerprint.json
fingerprint_sha256: null
fingerprint_scope: relevant-files+git
fingerprint_checked_at: null
---

# <任务标题>

> 状态默认：新建任务用 `in-progress`。`completed` 只在用户明确确认完成且验收证据存在时使用；`save`、`/clear`、context 阈值、测试通过都不等于完成确认。声明与证据冲突时用 `blocked`。
>
> 读取预算：任务文档建议 ≤ 200 行 / ≤ 4k tokens；只写代码/git 里读不到的 delta。`load` 默认只读“快速接手摘要 + 当前进度 + 下一步 + 并行与依赖”，其余按需。
>
> Token 卫生：只写高信号 delta；单空行、无装饰分隔线、无行尾空格；避免宽表格；不粘贴代码/diff；必要的空格和标点不要删。同一状态/风险/验证命令只写一处；跨文件重复优先用引用。
>
> Frontmatter：受限扁平 YAML，每行一个 `key: value`；不支持嵌套、序列、锚点/标签、块标量或多行值。值含 `#` 或 `: ` 时用引号；重复键、缩进行、未闭合引号是解析错误。

## 阅读指引
- `load` 默认读取：快速接手摘要、当前进度、下一步、并行与依赖。
- 其他章节（验证证据、决策与尝试、已尝试方案等）按需读取。
- “接手必读”只写索引，不写整文件清单。
- 详细读取预算见 [SKILL.md](../SKILL.md) 与 [brief-load.md](brief-load.md)。

## 快速接手摘要（≤ 20 行）
不要逐字重复 frontmatter 的 status；只写新会话必须知道的变化。

- 目标：
- 当前阶段：
- 最大风险：
- 建议第一步：
- 已尝试方案与重试条件：

## 元信息补充（机读字段见 frontmatter）
- 安全的项目/仓库标识：
- 覆盖范围与历史缺口：
- 其他说明：

## 目标与边界
用户明确要求、验收标准、追加需求、硬约束、范围外事项、需求/设计资料路径。

## 当前进度
分别记录已实现、已验证、已验收；进行中、待办、阻塞、等待、暂停、取消。没有证据就标记未验证。不重复快速摘要；只写细节、差异和证据。

## 代码与运行现场
相关文件与符号、修改目的、暂存/未暂存/未跟踪状态、修改归属、临时代码、环境前提。服务与进程只记录最后观察状态。

## 验证证据
每项记录：命令、执行位置、时间、结果、当时代码状态、验证后是否修改、当前是否需要重验。未知就写未知。同一命令/结果只写一次；其他章节引用本节。

## 决策与尝试
决策及原因、备选方案、适用条件、批准状态；失败尝试、错误现象、根因确认程度、重新尝试条件；被替代结论及原因。

## 已尝试方案与重试条件
记录已尝试但未采用的方案、当时证据、失败原因，以及什么条件下值得重试。不要把历史失败写成永久禁令。

## 用户偏好与纠正
只记录与当前项目/当前任务有关、且用户明确表达过的偏好或纠正。不要推断未表达的个人偏好。

## 并行与依赖
相关任务、共享文件、工作区、潜在冲突、外部等待。未知就标记未知。

## 下一步
按优先级记录具体动作、目标文件、前提、完成判定；区分低风险工作和需要授权的操作。

## 接手必读（索引，不是全量阅读清单）
只写新会话真正需要的路径、符号或行号范围；不要贴大段代码或敏感日志。

- `path/to/file#symbol` — 用途；只读该符号/章节。
- `path/to/file:120-180` — 用途；只读该范围。
- 外部 issue、设计文档等只记录链接，不自动访问。
- 如果确实需要整文件读取，写明原因和建议的 token/行数预算。

## 建议下一个会话调用的 Skill（可选）
仅在确认该 Skill 存在时记录，例如 `/tdd`、`/code-review`，并写明原因；不要假定一定可用。

## 指纹说明
`snapshot_id` / `fingerprint_file` / `fingerprint_sha256` 由 `scripts/handover.py fingerprint` 生成，并由 `check` 核对三者是否属于同一次保存。指纹包含声明文件的内容 SHA-256 与相关 git 现场（branch/HEAD/status）；内容哈希只覆盖明确列出的文件，目录范围只筛选 git status，不代表目录内所有文件都被哈希。`check` 不计算正文摘要，单独修改正文不会自动变成 unknown。默认排除 `.handover/`、`handover.md`、`.claude/` 和 `.git/`。脚本不可用、路径不可读、文件过大或无 git 基线时保持为 null，`consistency` 必须为 unknown；不得用 branch/HEAD 代替内容指纹。归档时任务 Markdown 与同 stem 的 `.fingerprint.json` 作为同一记录组移动，不重新生成基线。模板中的示例日期仅作格式示例，不要原样复制到真实任务。
