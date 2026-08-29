# Toolbox

面向科研与工程工作的轻量个人工具箱。每个子目录都应能**独立复制、独立运行、独立维护**；仓库只保存通用工具、最小示例和规则，不保存具体课题的大型数据、模型输出或论文真值。

## 目录

```text
Toolbox/
├── README.md
├── .gitignore
├── academic_plot/
│   ├── README.md
│   ├── plot_validation.py
│   ├── plot_multivariable.py
│   ├── requirements.txt
│   └── example/
│       ├── config.json
│       ├── input.csv
│       ├── multivariable_config.json
│       └── multivariable_input.csv
├── conversation_pack/
│   ├── README.md
│   ├── PROTOCOL.md
│   ├── build_pack.py
│   └── example/
│       ├── HANDOFF.md
│       └── spec.json
├── file_scan/
│   ├── README.md
│   └── scan_directory.py
└── plot_digitizer_launcher/
    ├── README.md
    ├── PlotDigitizer.bat
    └── Stop PlotDigitizer.bat
```

## 工具

| 目录 | 用途 | 依赖 |
|---|---|---|
| `academic_plot/` | 学术验证时序图；支持“多站点 × 单变量”和“单事件 × 多变量”，正式输出 SVG | Python 3.9+；NumPy、Pandas、Matplotlib |
| `conversation_pack/` | 长 AI 对话迁移：GPT 盘点当前文件/产物和关键信息，用户筛选，脚本校验并打包为 HANDOFF + 附件 | Python 3.9+ 标准库 |
| `file_scan/` | 为 AI/LLM 生成低上下文成本的目录索引：摘要、紧凑目录树、完整文件清单与机器可读 manifest | Python 3.9+ 标准库 |
| `plot_digitizer_launcher/` | 为已安装的 PlotDigitizer 提供 Windows 一键启动、浏览器打开和安全停止封装 | Windows 10/11、PowerShell；PlotDigitizer 的 Python/Node 环境已完成配置 |

## 设计原则

1. **项目与工具解耦**：项目只准备标准输入和配置；通用逻辑留在本仓库。
2. **接口稳定**：已有 CLI、输入字段和默认输出语义保持向后兼容；确需破坏性修改时升级版本并明确记录。
3. **配置优先**：时间窗、坐标范围、站点名、变量标签、QC 规则等写入配置，不写死在核心代码。
4. **跨环境优先**：Python 工具统一使用 `pathlib`，不依赖固定盘符或工作目录；确需操作系统专用封装时明确平台边界，并继续避免写死绝对路径。
5. **低依赖**：能用标准库或现有依赖解决的任务，不额外引入包。
6. **可检查**：每个工具保留最小 smoke test 或明确的验证记录；错误应显式报出，不静默生成错误结果。
7. **不臃肿**：不同数据组织模式可分脚本，但不为少量逻辑无故拆分模块。
8. **AI 与确定性程序分工**：AI 负责理解和整理语义，用户负责关键裁决；文件复制、校验、hash、打包等机械操作交给脚本。

## AI / 人工维护约束

- 修改前先阅读本文件和目标工具的 `README.md`。
- 不把具体课题名称、绝对路径、站点真值、事件日期或模型案例写进通用核心代码。
- 新功能优先通过可选配置增加，避免破坏旧配置。
- 绘图工具的视觉语法属于稳定接口；项目级差异优先通过 JSON 调整。
- 数据质量规则用于筛选数据，不应自动在主图内生成长说明文字。
- 新依赖必须有明确收益，并同步更新 `requirements.txt`。
- Conversation Pack 在用户确认前只做 Preview；正式 Pack 不默认保存完整聊天原文，也不因文件曾上传或生成过就自动迁移。

## 环境建议

Python 类工具推荐 Python 3.9–3.13；Windows、Linux、macOS 均可使用，字体不存在时绘图工具会回退到可用字体。`plot_digitizer_launcher/` 是明确的 Windows 专用封装，依赖系统 PowerShell 和已配置完成的 PlotDigitizer 环境。
