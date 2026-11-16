# Token 效率原则（save / brief / load）

交接内容主要给模型读取。目标：在有限 context 中装最多可核验的信息。

保留：
- 结构必需：标题、列表标记、frontmatter 分隔符、key/value 分隔符、代码围栏、必要换行。
- 语义必需：目标、验收、状态、决策与原因、失败尝试、验证命令/结果、风险、下一步、来源。

删除：
- 装饰性空格、对齐空格、行尾空格、连续空行（>1）、水平分隔线（`---` / `***` / `___`）、emoji/ASCII 装饰。
- 为“好看”增加的空行、缩进、表格 padding。
- 重复内容保留一处权威位置，其他引用。
- 可直接从代码/git/spec/commit 读取的内容用 `path#symbol` / hash / URL 引用。
- 宽表格；用 `key: value` 或 TSV。

边界：
- 不删必要结构；不做 zero-space minify；不要为了省 token 牺牲可解析性。
- YAML frontmatter / JSON sidecar 保持 schema；不为 token 改格式。
- `README` / `CHECKLIST` / `E2E_TEST_RESULTS` 是给人看的，不参与模型上下文，保持可读。
- 先测量：用 `stats` 看章节占比；优先砍高占比的重复/无关内容，而不是空格。
- 任务文档软预算 4k tokens；`task-lint` 默认上限 6k tokens，超过时先压缩/拆分再保存。
