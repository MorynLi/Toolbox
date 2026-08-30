# academic_plot

科研验证时序图工具。项目侧准备标准 CSV + JSON；工具负责稳定的 SVG 视觉语法、固定物理几何、原始时间保留、圆周变量断线、有效时间窗裁剪和范围审计。

## 稳定规则

- 参考/实测：深红色虚线 `#8B0000`；模拟：黑色实线。
- 实测曲线只用直线连接相邻原始点，**不做拟合**。
- 实测时间禁止近似：`3.1 h` 就按 `3.1 h` 绘制。
- 图例嵌入主图：一列位于第一行正上方中央；两列及以上位于第一行整个 panel block 正上方中央。
- 横轴数字默认只显示最下面一行；只有一行时保留该行数字。
- 每张组合图只显示一次绝对起始时间，例如 `2014-09-15 00:00`。
- 时间戳与 `时间(h)` 位于同一固定底部标签带、共用同一竖直中心线；时间戳字号更小。
- 固定毫米布局中，底部标签带使用绝对 mm 定位，不随数据内容变化。
- 风向/波向等圆周变量支持跨 0/360° 断线。
- 不自动补造缺失数据，不隐式插值。
- 正式出图推荐 `range_guard.mode=error`，数据越界直接报错。

## 代码结构

```text
academic_plot/
├─ README.md
├─ plot_common.py
├─ plot_validation.py        # 多站点 × 单变量
├─ plot_multivariable.py     # 单事件 × 多变量
├─ requirements.txt
├─ example/
│  ├─ config_1col_a4.json
│  └─ config_2col.json
├─ docs/
│  └─ MANUAL_TESTING.md
└─ tests/
   └─ smoke_test.py
```

## 布局参数

```json
"layout": {
  "rows": 4,
  "cols": 1,
  "geometry": {
    "profile": "academic_mm_v1",
    "panel_size_mm": [168, 50],
    "gap_mm": [0, 8],
    "margin_mm": {"left": 26, "right": 8, "bottom": 16, "top": 12}
  }
}
```

建议对需要后续拼版的图固定：`panel_size_mm`、`gap_mm`、`margin_mm`、`x_axis.bottom_band.y_mm`。

## 横轴数字与时间戳

```json
"x_axis": {
  "range": [0, 72],
  "ticks": [0, 24, 48, 72],
  "label": "时间(h)",
  "tick_label_policy": "bottom",
  "origin_timestamp": {
    "enabled": true,
    "text": "2014-09-15 00:00",
    "fontsize": 9
  },
  "bottom_band": {"y_mm": 8.5}
}
```

`tick_label_policy`：

- `bottom`：仅最下面一行显示，默认；单行图自然保留。
- `all`：所有行显示。
- `none`：全部隐藏。

时间戳只写绝对时间，不加“起始”“起始时间”等前缀。

## 原始实测时间

`plot_validation.py` 支持参考值和模拟值使用不同 x 列：

```json
"reference_x_col": "obs_time_h",
"simulation_x_col": "sim_time_h"
```

例如：

```text
station,obs_time_h,sim_time_h,reference,simulation
A1,3.1,,12.3,
A1,,3.0,,12.1
```

## 截断并重新归零

```json
"x_window": {
  "mode": "fixed",
  "start": 24,
  "end": 96,
  "rebase_to_zero": true,
  "tick_step": 24,
  "include_endpoint": true
}
```

这会删除 24 h 前的数据，并把原 24 h 重新记为 0 h；不会插值。项目侧同步更新 `origin_timestamp.text`。

## 有效交集时间窗

Pmin、Vmax 等存在无效前后段的数据，使用：

```json
"x_window": {
  "mode": "common_valid",
  "rebase_to_zero": true,
  "tick_step": 12,
  "include_endpoint": true
}
```

定义：

```text
start = max(各有效 reference/simulation 序列首时刻)
end   = min(各有效 reference/simulation 序列末时刻)
```

仅保留 `[start, end]` 的双方有效数据。若有可靠性标记，可先设置：

```json
"simulation_valid": {"column": "Vmax可靠", "values": ["是"]}
```

## 范围保护

```json
"range_guard": {"mode": "error"}
```

`error` 适合正式出图；`warn` 仅警告；`off` 关闭。

## 运行

```bash
python plot_validation.py --input example/input.csv --config example/config_1col_a4.json --output validation.svg
python plot_multivariable.py --input example/multivariable_input.csv --config example/multivariable_config.json --output multivariable.svg
python tests/smoke_test.py
```

人工检查与调参顺序见 `docs/MANUAL_TESTING.md`。

## 维护约束

- 核心代码不写具体课题路径、事件时间或站点真值。
- 不自动补造缺失数据，不隐式插值。
- 固定毫米布局输出不得使用 `bbox_inches="tight"`，避免数据内容改变 SVG 外框。
- 视觉语法变更视为版本变更，并尽量保持旧配置可运行。
