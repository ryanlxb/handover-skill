# 指纹与忽略检查

## 指纹（可选脚本）

- 优先使用 Skill 安装目录下的脚本；用 harness 在 Skill 内容开头给出的 base directory 拼绝对路径，替换下面的 `<skill-dir>`：
  - `python3 -I "<skill-dir>/scripts/handover.py" fingerprint --root <root> --task <id> --paths <paths-file> [--snapshot-id <id>] [--scope-dir <dir> ...]`：写入 `.handover/<id>.fingerprint.json`，输出 `snapshot_id`、sidecar SHA-256、文件与 git 状态。
  - `python3 -I "<skill-dir>/scripts/handover.py" check --root <root> --task <id> --task-file <task.md> [--expected-sha256 <hash>]`：先核对任务 frontmatter 与 sidecar 的 `snapshot_id`/`fingerprint_file`/`fingerprint_sha256`，再重新计算文件与 git 现场，返回 matched/changed/unknown。
- 如果无法确定 Skill 安装目录，按 `.claude/skills/handover/scripts/handover.py` 或用户实际安装目录解析；不要把相对路径当作项目路径。
- `snapshot_id` 只绑定任务 frontmatter 与 sidecar，不是正文内容哈希。保存流程更新或清空 `snapshot_id`/`fingerprint_sha256` 时，旧记录才会不匹配 → unknown；如果只改任务正文并保留原 frontmatter/sidecar，`check` 仍可能返回 matched。不要把 matched 当作正文未被改写的证明。
- `check` 要求任务 frontmatter 的 `schema`、`task_id`、`project_root`、`snapshot_id`、`fingerprint_file`、`fingerprint_sha256` 全部存在且与当前项目/sidecar 一致；任一缺失或不匹配 → unknown。不要用“文件里有 sidecar 路径”代替完整绑定。
- 指纹生成后必须再运行一次 `check`，确认检查时现场与刚生成的基线一致，并确认任务文件与 sidecar 的 `snapshot_id`/SHA 绑定一致；若返回 changed，报告“检查时现场与基线不一致”，不要宣称干净保存。`check` 不证明正文语义与代码一致，也不证明从读取代码到写入正文期间代码未变。
- 脚本不可用、无法确定相关文件或任一相关文件不可读时，`snapshot_id`/`fingerprint_file`/`fingerprint_sha256` 置 null，consistency 必须为 unknown；不得用 branch/HEAD 代替内容指纹。
- 拒绝空基线：声明路径去重并排除 `.handover/`、`handover.md`、`.claude/`、`.git/` 后若没有任何文件，`fingerprint` 返回错误，不生成“0 文件 matched”的 sidecar。save 应把绑定字段置 null，并说明 consistency=unknown；`check` 对 `files` 为空的旧 sidecar 也返回 unknown。
- 输出安全：默认只写 `.handover/<task-id>.fingerprint.json`。显式 `--out` 必须直接位于 `.handover/` 或 `.handover/archive/` 下，文件名必须是 `<task-id>.fingerprint.json` 或 `<task-id>-<timestamp>.fingerprint.json`；目标已存在时，必须是同一项目、同一 task-id、schema 受支持且结构完整的 sidecar，否则拒绝覆盖。业务文件、任务 Markdown、其他扩展名和项目外路径一律拒绝。`sidecar` 目标或 `.handover` 本身是符号链接时也拒绝写入；不要通过符号链接覆盖业务文件。
- 外部 paths 文件规则：只使用用户明确提供、或本次 save 自己创建的清单；不自动搜索外部清单；不执行清单内容；清单中的目标路径必须位于项目内，相对路径以项目根目录为基准。
- 指纹只覆盖声明的检查范围；不声称覆盖整个项目。

### 指纹范围

- 声明范围 = 任务相关文件 + “接手必读”路径 + 显式提到的路径 + 这些路径所在目录。
- 目录范围：子目录按子树覆盖；项目根目录按直属文件覆盖（不递归），避免一个根目录文件把整个仓库都算进 matched。需要更宽范围时显式传 `--scope-dir`，`.` 表示根目录直属文件。
- 兼容 v1.1.0 sidecar：若声明了根目录文件但 sidecar 没有 `.`，`check` 会保守地补上根目录直属范围；新 `save` 会显式记录。旧 sidecar 可能因此从 matched 变为 changed，重新 save 一次即可更新基线。
- 排除 `.handover/`、`handover.md`、`.claude/` 和 `.git/`。
- 当前版本默认排除整个 `.claude/`：这表示 `.claude/` 下的项目配置变化不在一致性检查范围内，不等于断言所有项目配置都不属于任务现场；后续版本可考虑允许显式纳入与任务相关的配置。
- git 现场覆盖声明范围内的新增、删除、重命名、暂存/未暂存状态变化；范围外的改动只计数，不参与 matched 判断。`matched` 输出会报告范围外变化计数（`out_of_scope_changes`），避免把“声明范围一致”误读为“整个项目无变化”。
- 内容哈希只覆盖 `files` 中明确列出的文件。目录范围（`scope_dirs`）只用于筛选 git status 条目，不等于对目录内所有文件做内容哈希。
- 同目录内未列入 `files` 的文件，如果内容变化但 git 状态字符串不变（例如基线时已是 ` M`、修改后仍是 ` M`），`check` 可能仍返回 matched。这是声明范围边界，不是目录内容一致的证明；git 不可用时，这些文件没有 git 状态保障。
- `fingerprint` 与 matched 输出分别报告 `content_hashed_files`、`git_status_dirs` 和 `coverage_note`；报告时不要把目录范围读成“目录内所有文件已校验”。

## 忽略检查（可选脚本）

- `python3 -I "<skill-dir>/scripts/handover.py" ignore-check --root <root>`：同时检查 `.handover/` 与 `handover.md` 是否被 Git 忽略、是否已被跟踪。`.handover/` 尚未创建时也按目录规则判断，避免首次 save 前误报 `not-ignored`。
  - exit 0：两者均为 `ignored, not-tracked`，或 Git 明确返回“not a git repository”（`result: not-git`）。只有明确的非 Git 才是 `not-git`；超时、Git 不可执行、权限失败或其他 Git 错误是 `result: unknown`、exit 2，不得当作非 Git 成功。
  - exit 1：至少一个为 `not-ignored` 或 `tracked`（`result: warning`）；提醒用户加入 `.gitignore` 或处理已跟踪文件，但不自动修改 `.gitignore`，不执行 `git rm`。
  - exit 2：无法判断（`result: unknown`）；如实报告，不宣称安全。
- `save`/`archive`/`restore` 前应运行；脚本不可用时按 SKILL.md “通用安全与真实性”的忽略检查要求人工确认。
