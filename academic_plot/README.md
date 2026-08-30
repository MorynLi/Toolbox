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

## 固定几何布局

新图推荐使用固定物理几何，而不是 `wspace` / `hspace` 相对间距。这样不同数据、不同坐标文字生成的 SVG 在相同布局下具有完全一致的画布尺寸、图框尺寸和图框间距，便于后续在 Word、PPT、Illustrator 或 Inkscape 中拼接。

启用标准布局：

```json
"layout": {
  "rows": 2,
  "cols": 2,
  "geometry": {
    "profile": "academic_mm_v1"
  }
}
```

`academic_mm_v1` 使用毫米作为底层几何单位：

- 单个图框：`90 × 65 mm`；
- 水平图框间距：`18 mm`；
- 垂直图框间距：`15 mm`；
- 外边距：左 `22 mm`、右 `6 mm`、下 `18 mm`、上 `6 mm`。

因此标准画布尺寸为：

| 布局 | SVG 基准画布尺寸 |
|---|---|
| `1 × 1` | `118 × 89 mm` |
| `1 × 2` | `226 × 89 mm` |
| `2 × 1` | `118 × 169 mm` |
| `2 × 2` | `226 × 169 mm` |

SVG 可以整体任意缩放。只要两个独立生成的图使用同一几何配置，并在排版时缩放到相同宽度，同列图框就会保持严格对齐。例如两张独立的 `1 × 2` 图上下拼接时，左右图框位置和中间间距完全一致。

固定几何模式下不使用 `bbox_inches="tight"`，避免坐标文字长度改变 SVG 外边界。坐标文字过长导致外边距不足时，应显式增大外边距，而不是重新启用自动裁剪。

### 自定义几何

标准 profile 可局部覆盖：

```json
"geometry": {
  "profile": "academic_mm_v1",
  "panel_size_mm": [95, 68],
  "gap_mm": [20, 16],
  "margin_mm": {
    "left": 24,
    "right": 7,
    "bottom": 19,
    "top": 7
  }
}
```

若多张图需要后续拼接，应使用完全相同的 `geometry` 配置。不同布局仍按同一单图框尺寸和间距规则推导总画布尺寸。

### 旧配置兼容

未提供 `layout.geometry` 时，仍沿用原来的：

```json
"figsize_in": [10.6, 7.55],
"subplot_adjust": {
  "wspace": 0.16,
  "hspace": 0.12
}
```

旧配置无需修改即可运行，但新图不建议继续依赖相对 `wspace` / `hspace` 做跨图拼接。

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
