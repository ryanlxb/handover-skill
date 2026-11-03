# Archive 与 Restore

归档和恢复把任务 Markdown 与它的指纹 sidecar 视为同一个记录组；两者通过同一 `snapshot_id` 绑定。

## 前置检查

移动前运行 `python3 -I "<skill-dir>/scripts/handover.py" ignore-check --root <root>`（若可用），确认 `.handover/` 与 `handover.md` 为 `ignored, not-tracked`；warning/unknown 时报告，不自动修改 `.gitignore`，不执行 `git rm`。`<skill-dir>` 是 Skill 安装目录。

## 安全移动顺序（archive/restore 共用）

1. 先确认目标文件不存在；目标同名不覆盖。
2. 先复制任务 Markdown 到目标路径并回读；再复制 sidecar 到同 stem 的 `.fingerprint.json`，核对 `snapshot_id`。
3. 只有任务和 sidecar 都已在目标位置且回读通过后，才删除源文件。
4. 删除源失败：保留源文件，报告“目标副本已存在、源仍在”，不宣称移动完成；不要为了清理而删除唯一副本。
5. 不要先删除源再复制；不要在目标未验证时删除源。
6. 入口更新最后执行；入口失败不回滚文件，报告实际位置和已完成步骤。

该顺序是降低记录丢失的操作规则，不是原子移动或并发锁。

## Archive

1. 指定 task-id；默认只允许 completed/cancelled。stale 的活跃任务只提示复核，不自动归档。用户明确要求归档其他状态时，必须在归档记录中写明原因；仍不自动执行。
2. 识别记录组：任务 Markdown + 可选 fingerprint sidecar。sidecar 存在时，先核对 sidecar 的 `snapshot_id` 与任务 frontmatter 一致；不一致则停止并报告，不把两组不同次保存的文件一起归档。
3. 移动前校验源文件存在、目标文件不存在；移动后回读。目标同名不覆盖；冲突停止并报告。
4. 归档文件移到 `.handover/archive/<task-id>-<小写 UTC 时间戳>.md`；sidecar 同步移到同 stem 的 `.fingerprint.json`，并把归档任务 frontmatter 的 `fingerprint_file` 指向归档 sidecar；`fingerprint_sha256` 保持不变，不重新生成基线。
5. 若 sidecar 缺失：只归档任务 Markdown，`fingerprint_file`/`fingerprint_sha256` 置 null，并在报告中说明 consistency 将为 unknown。
6. 若任务或 sidecar 只有一个移动成功：报告两者实际位置、已完成步骤和不完整状态；任务文件是事实来源，不删除任务文件，不宣称全部成功。
7. 归档任务 frontmatter 增加 `archived_at`；归档不改变 `updated_at`。保留原 task-id、最后实质更新时间和归档时间。
8. 更新 `handover.md`：从当前记录区的活跃/已结束列表移除，加入 archived 链接；不能移动后留下旧路径死链。入口更新失败时报告文件实际位置和已完成步骤，不删除任务文件，不宣称全部成功。
9. 归档记录不参与无 ID 自动选择；显式查看用 `load --archived <archive-id>`。

## Restore

1. 指定 archive-id；检查当前记录区是否已有同名 task-id 或同名 sidecar；任一存在则停止，不覆盖。
2. 识别归档记录组：归档任务 Markdown + 可选归档 sidecar。sidecar 存在时核对 `snapshot_id` 与任务 frontmatter 一致；不一致则停止并报告。
3. 移回当前记录区；任务 Markdown 与 sidecar 作为同一组移回，并把 `fingerprint_file` 指回 `.handover/<task-id>.fingerprint.json`；`fingerprint_sha256` 保持不变，不重新生成基线冒充现场一致。
4. 状态设为 paused；`restored_at` 记录当前时间；`updated_at` 保持不变；保留 `archived_at` 历史。
5. 若 sidecar 缺失：只恢复任务 Markdown，`fingerprint_file`/`fingerprint_sha256` 置 null，报告 consistency 将为 unknown。
6. 若任务或 sidecar 只有一个移动成功：按 ARCHIVE 的失败规则报告实际位置和不完整状态，不删除任务文件。
7. 更新入口链接。移动或入口更新失败时，按 ARCHIVE 的失败规则报告。
8. restore 不是激活；load 只读；用户明确继续后，下一次 save 才记录 in-progress。
