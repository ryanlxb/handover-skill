# 指纹与忽略检查

## 指纹（可选脚本）

- 优先使用 Skill 安装目录下的脚本；用 harness 在 Skill 内容开头给出的 base directory 拼绝对路径，替换下面的 `<skill-dir>`：
  - `python3 -I "<skill-dir>/scripts/handover.py" fingerprint --root <root> --task <id> --paths <paths-file> [--snapshot-id <id>] [--scope-dir <dir> ...]`：写入 `.handover/<id>.fingerprint.json`，输出 `snapshot_id`、sidecar SHA-256、文件与 git 状态。
  - `python3 -I "<skill-dir>/scripts/handover.py" check --root <root> --task <id> --task-file <task.md> [--expected-sha256 <hash>]`：先核对任务 frontmatter 与 sidecar 的 `snapshot_id`/`fingerprint_file`/`fingerprint_sha256`，再重新计算文件与 git 现场，返回 matched/changed/unknown。
- 如果无法确定 Skill 安装目录，按 `.claude/skills/handover/scripts/handover.py` 或用户实际安装目录解析；不要把相对路径当作项目路径。
- `snapshot_id` 用于把“这一次交接”的正文与 sidecar 绑定：正文已更新但指纹仍是旧值时，不匹配 → unknown。
- 指纹生成后必须再运行一次 `check`，确认检查时现场与刚生成的基线一致，并确认任务文件与 sidecar 的 `snapshot_id`/SHA 绑定一致；若返回 changed，报告“检查时现场与基线不一致”，不要宣称干净保存。`check` 不证明正文语义与代码一致，也不证明从读取代码到写入正文期间代码未变。
- 脚本不可用、无法确定相关文件或任一相关文件不可读时，`snapshot_id`/`fingerprint_file`/`fingerprint_sha256` 置 null，consistency 必须为 unknown；不得用 branch/HEAD 代替内容指纹。
- 外部 paths 文件规则：只使用用户明确提供、或本次 save 自己创建的清单；不自动搜索外部清单；不执行清单内容；清单中的目标路径必须位于项目内，相对路径以项目根目录为基准。
- 指纹只覆盖声明的检查范围；不声称覆盖整个项目。

### 指纹范围

- 声明范围 = 任务相关文件 + “接手必读”路径 + 显式提到的路径 + 这些路径所在目录。
- 排除 `.handover/`、`handover.md`、`.claude/` 和 `.git/`。
- 当前版本默认排除整个 `.claude/`：这表示 `.claude/` 下的项目配置变化不在一致性检查范围内，不等于断言所有项目配置都不属于任务现场；后续版本可考虑允许显式纳入与任务相关的配置。
- git 现场覆盖声明范围内的新增、删除、重命名、暂存/未暂存状态变化；范围外的改动只计数，不参与 matched 判断。

## 忽略检查（可选脚本）

- `python3 -I "<skill-dir>/scripts/handover.py" ignore-check --root <root>`：同时检查 `.handover/` 与 `handover.md` 是否被 Git 忽略、是否已被跟踪。
  - exit 0：两者均为 `ignored, not-tracked`，或当前不是 Git 项目（`result: not-git`）。
  - exit 1：至少一个为 `not-ignored` 或 `tracked`（`result: warning`）；提醒用户加入 `.gitignore` 或处理已跟踪文件，但不自动修改 `.gitignore`，不执行 `git rm`。
  - exit 2：无法判断（`result: unknown`）；如实报告，不宣称安全。
- `save`/`archive`/`restore` 前应运行；脚本不可用时按 SKILL.md “通用安全与真实性”的忽略检查要求人工确认。
