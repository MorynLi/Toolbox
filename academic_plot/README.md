# academic_plot

科研验证时序图工具。项目侧负责准备标准 CSV 与 JSON；工具负责稳定的视觉语法、数据有效性筛选和 SVG 输出。

## 两种绘图模式

| 脚本 | 适用数据组织 | 典型用途 |
|---|---|---|
| `plot_validation.py` | 多站点 × 单变量 | 多浮标风速、气压、波高等同变量验证 |
| `plot_multivariable.py` | 单事件 × 多变量 | 同一事件的 Pmin/Vmax、Hs/Tp/波向等纵向组合图 |

两个脚本使用同一套视觉语法，但不强行共享同一种数据结构。

## 稳定视觉语法

- 正式输出为 SVG，文字保持文本对象（`svg.fonttype=none`）。
- 参考/实测：深红色虚线 `#8B0000`；模拟：黑色实线。
- **主图文件中不放图例对象；图例须单独输出为独立 SVG。**
- 白色背景、无网格、完整矩形坐标框、刻度向内，顶部和右侧保留刻度。
- 默认不重复使用 `(a)(b)(c)(d)`。
- 多站点模式中，第一行不重复横轴标题、非首列不重复纵轴标题。
- 图框内标签只在确有区分意义时使用。纵轴已经表达物理量时，不再在图内重复写同义标题。
- 数据质量说明、可靠性说明和事件时间基准由正文或图注解释；主图只负责呈现数据。
- 风向等圆周变量可启用断线处理，避免跨 0/360° 画出伪长线。

### 语言与字体

中文论文或中文汇报默认使用中文语义文字，包括坐标轴语义标签、图例和必要注释；变量符号、单位、模型名、标准缩写和数字保留原形式。字体优先中文宋体类、英文与数字 Times New Roman；缺失时按跨平台候选字体回退。

## 参考值与模拟值的语义

工具内部推荐使用 `reference` / `simulation`。`reference` 可以是实测、最佳路径、再分析、实验或其他独立基准，不限定为现场观测。

`plot_validation.py` 为兼容旧配置，仍接受：

- `observed_col` → `reference_col`
- `simulated_col` → `simulation_col`

旧 CSV 与旧 JSON 无需修改即可继续运行。

## 1. 多站点 × 单变量

最小 CSV：

```text
time_h,station,observed,simulated
0,A1,1006.2,1006.5
6,A1,1003.0,1003.4
```

运行：

```bash
python plot_validation.py \
  --input example/input.csv \
  --config example/config.json \
  --output validation.svg \
  --legend-output legend.svg
```

站点标签默认显示，可通过：

```json
"station_label": {"enabled": false}
```

关闭。

### 可选 QC 筛选

参考值或模拟值可各自设置有效性条件：

```json
"simulation_valid": {
  "column": "sim_ok",
  "values": [1]
}
```

QC 只控制哪些点进入曲线，不自动在主图中添加说明文字。

## 2. 单事件 × 多变量

`plot_multivariable.py` 允许每个 panel 使用独立的纵轴、数据列、QC 条件和圆周变量规则。

最小配置见 `example/multivariable_config.json`，运行：

```bash
python plot_multivariable.py \
  --input example/multivariable_input.csv \
  --config example/multivariable_config.json \
  --output multivariable.svg \
  --legend-output multivariable_legend.svg
```

每个 panel 至少包含：

```json
{
  "reference_col": "pressure_reference",
  "simulation_col": "pressure_simulation",
  "y_axis": {
    "range": [990, 1010],
    "ticks": [990, 995, 1000, 1005, 1010],
    "label": "P（hPa）"
  }
}
```

`panel_label` 默认为空；仅当站点名、方案名等信息确有必要时才设置。

### 绝对时间转相对时间

若 CSV 保存真实时间，可在配置中直接转换为相对时间：

```json
"time_transform": {
  "datetime_col": "time_utc",
  "origin": "2020-01-01 00:00:00",
  "unit": "h"
}
```

这样数据保留真实时间，图上可统一使用 `时间（h）`。支持 `s`、`min`、`h`、`d`。

## 安装

```bash
cd academic_plot
python -m pip install -r requirements.txt
```

## 维护约束

- 不在核心代码中写具体课题路径、事件时间、站点数据或最佳路径真值。
- 不自动补造缺失数据，不隐式插值。
- 视觉语法修改应视为版本变更；数据接口新增应优先保持向后兼容。
- `reference` 的名称可由图例配置成“实测”“最佳路径”“再分析”等；核心代码不绑定具体来源。
- 单文件逻辑能够清楚表达时保持单文件，不为形式上的“架构”增加层级。
