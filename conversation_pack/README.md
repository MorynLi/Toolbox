# conversation_pack

面向 AI 长对话迁移的轻量打包工具。

它解决的问题是：

> 当前对话尚未结束，但窗口已经过长，需要迁移到新对话继续；如何把真正需要继承的信息和文件带过去，而不是重新灌入全部聊天历史。

核心逻辑：

> **GPT 负责盘点，用户负责筛选，脚本负责搬运。**

当前版本不建立复杂节点图、不自动给信息打分，也不保存完整聊天原文。

## 工作流

### 1. Preview

用户提出“总结一下 / 准备换对话”后，GPT 先只输出候选框架：

- 当前任务、状态、下一步；
- 当前对话涉及的文件 / 数据 / 产物类型和具体名称；
- 建议继承的关键信息；
- 无法确定的文件标记为待确认。

这一步**不生成 ZIP**。

### 2. 用户筛选

用户决定最终迁移什么，例如：

```text
只留验证数据、当前模型结果和最终 SVG 绘图流程。
统计结果也留，中间调试图不要。
```

用户不需要自己记住精确文件名；GPT 应根据当前对话把这些类别解析成实际文件。

### 3. Build

确认后，GPT 准备：

```text
HANDOFF.md
spec.json
```

`HANDOFF.md` 只保存用户确认后的有效状态；`spec.json` 只列用户确认要携带的实际文件。

然后运行：

```bash
python build_pack.py spec.json --zip
```

脚本只执行确定性工作：文件检查、复制、SHA-256、manifest、QA 和 ZIP。

## 最终包结构

```text
conversation_pack_xxx/
├── HANDOFF.md
├── manifest.json
├── QA.md
└── files/
    └── ...用户确认的文件...
```

新对话先读取 `HANDOFF.md`，再按需要读取 `files/`。

## `HANDOFF.md`

推荐保持简短：

```markdown
# Handoff

## 当前任务

## 当前状态

## 需要继承的关键信息

## 已确认规则 / 结论

## 下一步

## 携带文件说明
```

不默认保存用户 / GPT 的逐轮原话。

## `spec.json`

v0.2 示例：

```json
{
  "schema_version": "0.2",
  "pack_name": "example_handoff",
  "handoff": "HANDOFF.md",
  "assets": [
    {
      "source": "source/current_truth.xlsx",
      "target": "files/current_truth.xlsx",
      "label": "当前真值数据",
      "role": "validation_data",
      "required": true
    }
  ]
}
```

`source` 相对于 `spec.json` 所在目录解析，也允许绝对路径；最终 `manifest.json` 不记录本机绝对源路径。

## 文件选择原则

文件是否迁移，最终由用户决定。GPT 只负责盘点和轻量建议。

通常值得列入候选：

- 用户明确要求后续继续使用的文件 / 文件类别；
- 下一对话仍需使用的输入数据；
- 当前对话生成且后续仍需复用的结果；
- 已成为当前工作基线的脚本、配置或图表。

通常不迁移：

- 仅用于一次排错、后续无用的截图 / 日志；
- 被新版本完全覆盖的旧文件；
- 后续不再使用的中间产物；
- 新 GPT 可直接重新完成的普通问题解决过程；
- 完整聊天原文。

**文件不可复现并不等于必须保留；后续还会不会用，才是关键。**

## QA 行为

`build_pack.py` 会检查：

- schema 和 pack name；
- `HANDOFF.md` 是否存在；
- target 是否安全、是否重复；
- required 文件是否存在；
- 每个打包文件的 SHA-256 和大小；
- optional 文件缺失情况；
- 最终文件数和总大小。

默认不覆盖已有输出，使用 `--force` 才会重建。

## 设计边界

1. GPT 不应在用户确认前直接生成正式 Pack。
2. 用户负责最终筛选，GPT 不替用户做复杂价值判断。
3. 脚本不理解聊天语义。
4. 不保存完整聊天原文作为默认方案。
5. 不修改源文件。
6. 不把单次对话规则升级为长期 AI 记忆。

完整协议见 [`PROTOCOL.md`](./PROTOCOL.md)。

当前为 **v0.2 试验版**，先在真实长对话中验证后再继续扩展。
