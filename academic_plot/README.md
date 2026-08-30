# academic_plot

科研验证时序图工具。项目侧负责准备标准 CSV 与 JSON；工具负责稳定的视觉语法、固定物理几何、方向变量断线、范围越界检查和 SVG 输出。

## 两种绘图模式

| 脚本 | 适用数据组织 | 典型用途 |
|---|---|---|
| `plot_validation.py` | 多站点 × 单变量 | 多浮标风速、气压、波高等同变量验证 |
| `plot_multivariable.py` | 单事件 × 多变量 | 同一事件的 Pmin/Vmax、Hs/Tp/波向等组合图 |

两个脚本共享 `plot_common.py` 中的字体、几何、图例、圆周断线和范围审计逻辑。

## 稳定视觉语法

- 正式输出 SVG，文字保持文本对象（`svg.fonttype=none`）。
- 参考/实测：深红色虚线 `#8B0000`；模拟：黑色实线。
- 图例默认嵌入主图，不再单独输出。
- 一列布局：图例位于第一行图正上方中央。
- 两列及以上布局：图例位于第一行整个 panel block 正上方中央。
- 白色背景、无网格、完整矩形坐标框、刻度向内，顶部和右侧保留刻度。
- 风向/波向等圆周变量可启用断线，避免跨 0/360° 画出伪长线。
- 工具不自动补造缺失数据，不隐式插值，不对参考值做平滑拟合。
- 实测时刻可保留小数小时，例如 `3.1 h` 就按 `3.1 h` 绘制。

## 代码结构

```text
academic_plot/
├─ README.md
├─ plot_common.py             # 共享字体、几何、图例、圆周断线、范围审计
├─ plot_validation.py         # 多站点 × 单变量
├─ plot_multivariable.py      # 单事件 × 多变量
├─ requirements.txt
├─ example/
│  ├─ config.json
│  ├─ input.csv
│  ├─ config_1col_a4.json
│  ├─ config_2col.json
│  ├─ multivariable_config.json
│  └─ multivariable_input.csv
└─ docs/
   └─ MANUAL_TESTING.md
```

## 固定几何布局与可调参数

推荐使用毫米几何，而不是依赖 `wspace/hspace`。

```json
"layout": {
  "rows": 4,
  "cols": 1,
  "geometry": {
    "profile": "academic_mm_v1",
    "panel_size_mm": [168, 50],
    "gap_mm": [0, 8],
    "margin_mm": {
      "left": 26,
      "right": 8,
      "bottom": 14,
      "top": 12
    }
  }
}
```

用户可直接调：

- `panel_size_mm = [宽, 高]`
- `gap_mm = [横向图框间距, 纵向图框间距]`
- `margin_mm.left/right/bottom/top`
- `station_label.x/y` 或 `panel_label_position.x/y`
- `legend.anchor_x_mm`
- `legend.anchor_y_mm`
- `legend.shift_x_mm`
- `legend.shift_y_mm`
- `legend.fontsize`
- `style.observed_line_width`
- `style.simulated_line_width`
- `style.tick_fontsize`
- `style.axis_label_fontsize`

如果多张图要后续拼接，应固定完全相同的 `panel_size_mm`、`gap_mm` 与 `margin_mm`。

## 图例

默认配置：

```json
"legend": {
  "enabled": true,
  "labels": ["实测", "模拟"],
  "fontsize": 14,
  "shift_x_mm": 0,
  "shift_y_mm": 0
}
```

固定几何模式下，代码会自动计算第一行 panel block 的水平中心。通常只需要微调 `shift_y_mm`。

`plot_validation.py --legend-output ...` 仅为旧流程兼容保留。新图不要使用。

## 原始实测时刻

`plot_validation.py` 支持参考值和模拟值使用不同的 x 列：

```json
"x_col": "time_h",
"reference_x_col": "obs_time_h",
"simulation_x_col": "sim_time_h"
```

因此可以保留实测原始时间：

```text
station,obs_time_h,sim_time_h,reference,simulation
A1,3.1,,12.3,
A1,,3.0,,12.1
```

也可以把参考/模拟放在同一 `time_h` 列的不同稀疏行中。核心原则是不把 `3.1 h` 强制改成 `3 h`。

## 坐标范围保护

过去固定 y 轴时容易出现真实数据超出图框。现在可启用：

```json
"range_guard": {
  "mode": "error"
}
```

选项：

- `error`：发现越界直接停止绘图，适合正式出图。
- `warn`：发出 warning 后继续。
- `off`：不检查。

推荐正式出图使用 `error`。

## 1. 多站点 × 单变量

运行：

```bash
python plot_validation.py \
  --input example/input.csv \
  --config example/config_1col_a4.json \
  --output validation.svg
```

兼容旧配置：

- `observed_col` → `reference_col`
- `simulated_col` → `simulation_col`
- `style.line_width` 同时作用于两条曲线

## 2. 单事件 × 多变量

运行：

```bash
python plot_multivariable.py \
  --input example/multivariable_input.csv \
  --config example/multivariable_config.json \
  --output multivariable.svg
```

每个 panel 可以独立设置：

- `reference_col`
- `simulation_col`
- `y_axis`
- `circular`
- `reference_valid`
- `simulation_valid`
- `panel_label`

## 人工测试

详细流程见：

```text
docs/MANUAL_TESTING.md
```

人工检查重点包括：

1. 数据 min/max 是否落在轴范围内。
2. 实测原始时间是否被改写。
3. 图例是否位于第一行图框上方中央且不与图框重叠。
4. 一列、两列布局能否保持严格对齐。
5. 方向变量是否正确断开 0/360° 伪跳变。
6. SVG 画布尺寸是否随着不同数据内容保持不变。

## 安装

```bash
cd academic_plot
python -m pip install -r requirements.txt
```

## 维护约束

- 不在核心代码中写具体课题路径、事件时间或站点真值。
- 不自动补造缺失数据，不隐式插值。
- 参考值曲线的连线只表示相邻原始点的视觉连接，不代表数学拟合。
- 视觉语法修改视为版本变更，并尽量保持旧配置可运行。

## 横轴时间标注统一规则

默认不显示横轴数值刻度标签，只保留坐标轴框、刻度线和最底行的 `时间(h)` 轴标题。
如果确实需要数字刻度，可显式设置：

```json
"x_axis": {
  "show_tick_labels": true
}
```

每张组合图只显示一次时间起点，位于最底行左侧、靠近 x=0 的下方，并与 `时间(h)` 保持紧凑的同一视觉带：

```json
"x_axis": {
  "label": "时间(h)",
  "show_tick_labels": false,
  "origin_timestamp": {
    "enabled": true,
    "text": "2014-09-15 00:00",
    "fontsize": 9,
    "x": 0.0,
    "y": -0.16
  }
}
```

时间戳只写绝对时间，不加“起始时间”“起始：”等前缀。

当项目侧截断时间窗时，应同时重新定义相对时间零点。例如从
`2014-09-15 00:00` 开始，则截掉此前数据并将该时刻记为 `0 h`，
同时把 `origin_timestamp.text` 更新为 `2014-09-15 00:00`。
