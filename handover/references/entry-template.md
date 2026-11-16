# handover.md 入口模板

`handover.md` 只是导航，不是任务事实来源。任务正文在 `.handover/<task-id>.md`。

```markdown
# <project> — handover

- 项目根：`<absolute path>`
- 项目资料：[CLAUDE.md](CLAUDE.md)、[README.md](README.md)

## 任务列表

- [task-id](.handover/task-id.md) — <title> — <status> — <updated_at>

## 跨任务风险

- <真正的跨任务风险；没有就写“无”>

## 归档

- [archive-id](.handover/archive/archive-id-<utc>.md) — <status> — <archived_at>
```

规则：

- 任务列表每行只写 task-id、链接、title、status、updated_at；**不写任务摘要、验证证据或下一步**，这些只在任务正文。
- 链接使用项目根相对路径，必须是 `.handover/<task-id>.md`；不要链接业务文件或项目外路径。
- 每个当前记录区任务必须出现一次；重复链接、死链、漏登记由 `entry-lint` 报告。
- 归档任务只在“归档”区链接；不要混入任务列表。
- `entry-lint --root <root>`：exit 0 = ok；1 = 死链/重复/漏登记；2 = 入口缺失或不可读。
