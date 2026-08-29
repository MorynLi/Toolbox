# conversation_pack

面向 AI 长对话迁移的上下文打包工具。它不尝试自动理解所有聊天内容，而是把职责拆成两层：

- **AI 负责语义选择**：提炼当前对话中真正需要带走的背景、决定、待办、约束和关键附件。
- **脚本负责确定性打包**：校验文件、复制附件、计算 SHA-256、生成 manifest/QA，并可输出 ZIP。

目标不是保存完整聊天记录，而是让另一个 AI 对话窗口能够以较低上下文成本继续尚未完成的工作。

> 当前版本首先在科研/工程长对话中试验，但协议本身不绑定任何具体项目、学科、模型或 ChatGPT 产品。

## 目录

```text
conversation_pack/
├── README.md
├── PROTOCOL.md
├── build_pack.py
└── example/
    ├── spec.json
    ├── 00_START_HERE.md
    ├── 01_CONTEXT.md
    ├── 02_DECISIONS.md
    ├── 03_OPEN_TASKS.md
    └── 04_ASSETS.md
```

## 一个标准迁移包

```text
conversation_pack_xxx/
├── 00_START_HERE.md
├── 01_CONTEXT.md
├── 02_DECISIONS.md
├── 03_OPEN_TASKS.md
├── 04_ASSETS.md
├── manifest.json
├── QA.md
└── files/
    └── ...关键附件...
```

建议新对话首先只读取 `00_START_HERE.md`，随后按其中指示读取其他文档或附件，避免一次性重新灌入全部历史信息。

## 为什么不做“一键自动总结聊天”

长对话的难点不是文件复制，而是语义取舍。通用脚本无法可靠判断：

- 哪个结论已经被用户明确确认；
- 哪个只是 AI 的临时推测；
- 哪条旧路线已经被放弃；
- 哪些附件对下一步真正必要；
- 哪些一次性要求不应该升级为长期规则。

因此 `conversation_pack` 不内置自由摘要器。AI 先按照 `PROTOCOL.md` 生成 handoff 文档和 `spec.json`，再由 `build_pack.py` 做机械、可检查的打包。

## 使用

准备 handoff 文档和 `spec.json` 后：

```bash
python build_pack.py example/spec.json --zip
```

默认输出到 spec 所在目录下：

```text
_conversation_pack/<pack_name>/
```

并在 `--zip` 时同时生成：

```text
_conversation_pack/<pack_name>.zip
```

指定其他输出目录：

```bash
python build_pack.py spec.json --output-dir ./handoff --zip
```

若目标目录已经存在，脚本默认拒绝覆盖；确需重建时显式使用：

```bash
python build_pack.py spec.json --output-dir ./handoff --force --zip
```

## `spec.json`

最小示例：

```json
{
  "schema_version": "0.1",
  "pack_name": "example_handoff",
  "documents": [
    {
      "source": "00_START_HERE.md",
      "target": "00_START_HERE.md",
      "role": "entrypoint",
      "required": true
    }
  ],
  "assets": [
    {
      "source": "source/example.csv",
      "target": "files/example.csv",
      "role": "reference_data",
      "required": false
    }
  ]
}
```

`source` 相对于 `spec.json` 所在目录解析，也允许绝对路径。`target` 必须是迁移包内的相对路径，禁止 `..` 路径穿越。

脚本不会把本机绝对源路径写入最终 `manifest.json`；manifest 只记录目标路径、原文件名、角色、大小和 SHA-256，降低无意义的本机路径泄露。

## QA 行为

`build_pack.py` 会检查：

- `schema_version` 与 `pack_name`；
- target 是否安全、是否重复；
- `00_START_HERE.md` 是否存在；
- required 文件是否全部存在；
- optional 文件缺失情况；
- 每个已打包文件的 SHA-256 和大小；
- 最终文件数和总大小。

required 文件缺失时直接失败，不生成“看似完整”的迁移包；optional 文件缺失只写入 `QA.md`。

## 设计边界

1. 不保存完整聊天原文作为默认方案。
2. 不让脚本猜测语义重要性。
3. 不修改源文件。
4. 不静默忽略 required 文件。
5. 不把具体科研项目名称、绝对路径或单次任务规则写入通用核心代码。
6. 对话包是**任务连续性工件**，不是长期用户记忆系统。

## 当前状态

当前为 `v0.1` 试验协议。先用真实长对话反复迁移，观察遗漏、冗余和误分类，再决定是否升级为更深度的 GPT/AI 工具集成。