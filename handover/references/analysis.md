# 上下文分析（analysis）

只读审计当前会话的 context 使用；不改变任务、不修改文件、不执行文档中的命令。

## 目标

找出“谁在吃 context”，给出可执行建议：

- 系统提示 / MCP 工具 schema（按 server 分组）
- 对话消息 / tool results（按类别和工具）
- 磁盘上的 CLAUDE.md / rules / memory / skills / 任务文档
- 前后两次 API shape 的变化（例如某个 MCP server 被禁用）

## 步骤

1. 项目识别（SKILL.md “项目识别与隔离”）。
2. 运行：

   `python3 -I "<skill-dir>/scripts/handover.py" analysis --root <root> [--session <id>] [--transcript <file>] [--context-window <n>] [--json]`

   - 默认从 `~/.claude/projects/<encoded-root>/<session>.jsonl` 找 transcript。未指定 `--session`/`--transcript` 时，优先 `CLAUDE_CODE_SESSION_ID`，否则最新 `.jsonl`，并在输出中报告选择来源。显式 `--session` 找不到时直接报错，不回退到其他 transcript；`--session` 必须是安全 ID（字母数字、点、下划线、短横线）。自动发现时不跟随指向项目 transcript 目录外的符号链接。
   - `--context-window` 默认 1,000,000；按实际模型窗口覆盖。
3. 如果 helper 不可用或 transcript 不存在：
   - 统计磁盘配置大小（CLAUDE.md / rules / memory / skills / task docs）；
   - 请用户运行 `/context` 并提供 breakdown；
   - 明确标注“未测量”的部分。
4. 输出报告与建议；不要打印消息正文、密钥或完整 tool result。

## 报告格式（紧凑）

```text
context analysis — <root>
transcript: <path|not found>
context_window: <n>

request prefix (latest api-request-shape):
  system_prompt: N tok (P%)
  tool_schemas: N tok (P%)
    <server>: N tools, N tok (P%)
  prefix_total: N tok (P%)

shape changes:
  <server>: before -> after (+/-N)

transcript blobs (all; may include compacted history):
  total: N tok (P%), M messages
  system/user/assistant/tool_results: N tok (P%)
  top tool results:
    <tool>: N tok (P%)

config on disk (reference; may overlap):
  <label>: N tok — <path>

recommendations:
  - ...
note: request prefix is exact for the latest shape; blobs may include compacted history; /context is official.
```

## 建议规则

- 最大 MCP server group > 5k tok：如果不是当前任务必需，建议禁用或按需启用，由用户执行。
- tool result 最大项 > 5k tok：建议用 Grep/Read offset、读取预算，或只看相关路径。
- 对话历史 > 50k tok：建议 `/compact`，或为不相关任务开新会话。
- 规则/CLAUDE.md 单项 > 5k tok：建议裁剪或移到 references/按需加载。
- skill body 只在该 skill 被调用时计入；不要把未调用的 skill 当作当前成本。
- 不要为了省 token 删必要结构或做 zero-space minify；优先砍重复/无关内容。
- 报告区分：request prefix（较精确）、transcript blobs（可能包含已压缩历史）、config on disk（参考，可能重叠）、`/context`（官方口径）。

## 安全

- 只读；不写任务、不改配置、不关 MCP server（建议由用户执行）。
- 不打印 transcript 正文、tool result 内容、密钥或完整路径列表；只输出大小、类别、工具名、server 名。
- `--json` 与文本输出都只包含大小、类别、工具名、server 名；不包含 system block 前缀文本、tool description 或 message 正文。不要为了“可读性”加回正文片段。
- transcript 可能包含敏感内容；报告只做聚合。
- `analysis` 是保留字，不能作为 task-id。
