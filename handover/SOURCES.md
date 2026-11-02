# 官方参考

本包为基于用户需求设计的指令型 Skill，不是 Anthropic 官方发布的插件。以下是可用于核对安装、frontmatter 和会话机制的官方文档入口；产品文档可能更新。

- [Claude Code Skills](https://code.claude.com/docs/en/skills)
- [Claude Code Memory](https://code.claude.com/docs/en/memory)
- [Claude Code Sessions](https://code.claude.com/docs/en/sessions)
- [Claude Code Best Practices](https://code.claude.com/docs/en/best-practices)
- [Claude Code Common Workflows](https://code.claude.com/docs/en/common-workflows)
- [Agent Skills](https://agentskills.io)

设计选择：手动触发；不使用 context: fork；不添加广泛 allowed-tools 预授权；任务数据项目本地化；并发检查为最佳努力，不宣称锁保证；consistency 依赖内容指纹，没有基线时为 unknown。
