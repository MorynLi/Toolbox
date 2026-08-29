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
└── file_scan/
    ├── README.md
    └── scan_directory.py
```

## 工具

| 目录 | 用途 | 依赖 |
|---|---|---|
| `academic_plot/` | 学术验证时序图；支持“多站点 × 单变量”和“单事件 × 多变量”，正式输出 SVG | Python 3.9+；NumPy、Pandas、Matplotlib |
| `file_scan/` | 生成目录树、文件清单和扫描摘要 | Python 3.9+ 标准库 |

## 设计原则

1. **项目与工具解耦**：项目只准备标准输入和配置；通用逻辑留在本仓库。
2. **接口稳定**：已有 CLI、输入字段和默认输出语义保持向后兼容；确需破坏性修改时升级主版本。
3. **配置优先**：时间窗、坐标范围、站点名、变量标签、QC 规则等写入配置，不写死在核心代码。
4. **跨环境**：统一使用 `pathlib`；不依赖固定盘符、工作目录或单一操作系统。
5. **低依赖**：能用标准库或现有依赖解决的任务，不额外引入包。
6. **可检查**：每个工具保留最小 smoke test 示例；错误应显式报出，不静默生成错误结果。
7. **不臃肿**：不同数据组织模式可分脚本，但不为少量逻辑无故拆分模块。

## AI / 人工维护约束

- 修改前先阅读本文件和目标工具的 `README.md`。
- 不把具体课题名称、绝对路径、站点真值、事件日期或模型案例写进通用核心代码。
- 新功能优先通过可选配置增加，避免破坏旧配置。
- 绘图工具的视觉语法属于稳定接口；项目级差异优先通过 JSON 调整。
- 数据质量规则用于筛选数据，不应自动在主图内生成长说明文字。
- 新依赖必须有明确收益，并同步更新 `requirements.txt`。

## 环境建议

推荐 Python 3.9–3.13。Windows、Linux、macOS 均可使用；字体不存在时绘图工具会回退到可用字体。
