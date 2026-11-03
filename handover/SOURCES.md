# 官方参考

本包为基于用户需求设计的指令型 Skill，不是 Anthropic 官方发布的插件。以下是可用于核对安装、frontmatter 和会话机制的官方文档入口；产品文档可能更新。

- [Claude Code Skills](https://code.claude.com/docs/en/skills)
- [Claude Code Memory](https://code.claude.com/docs/en/memory)
- [Claude Code Sessions](https://code.claude.com/docs/en/sessions)
- [Claude Code Best Practices](https://code.claude.com/docs/en/best-practices)
- [Claude Code Common Workflows](https://code.claude.com/docs/en/common-workflows)
- [Agent Skills](https://agentskills.io)

设计选择：手动触发；不使用 context: fork；不添加广泛 allowed-tools 预授权；任务数据项目本地化；并发检查为最佳努力，不宣称锁保证；consistency 依赖内容指纹，没有基线时为 unknown。

上下文预算：`SKILL.md` 只保留路由、项目识别、安全边界和读取预算；`brief`/`load` 的流程、默认读取集和质量检查表放在 `references/brief-load.md`，按模式加载。`brief`/`load` 默认先读索引和摘要，不整文件读取；超出预算时报告未读/截断。`context: fork` 仍是未采用项：`load` 需要把任务状态带入主会话，fork 后主会话只拿摘要，细节需再次读取。

Token 优化参考：TOON（Token-Oriented Object Notation，https://toonformat.dev/）是紧凑的 JSON 兼容编码，适合均匀结构化数据；仅作为机器可读块的候选，不替换任务文档的 Markdown 主体。Whitespace/minify 的收益通常很小，优先减少重复和无关内容。

上下文分析：读取 `~/.claude/projects/<encoded-root>/<session>.jsonl` 中的 `api-request-shape`（system + tools）和 `api-request-blob`（消息）；格式可能随 Claude Code 版本变化，缺失时退化为磁盘配置大小分析，并提示使用 `/context`。
