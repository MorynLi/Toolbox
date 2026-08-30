# academic_plot 人工测试与调试指南

## 1. 先检查数据，不先调图

每次正式绘图前至少打印：

- reference 的 `x_min / x_max / y_min / y_max / N`
- simulation 的 `x_min / x_max / y_min / y_max / N`
- 配置的 `x_axis.range`
- 配置的 `y_axis.range`

对于实测原始时间，随机抽查 5–10 个非整点。例如原值是 `3.1 h`，输入 CSV 和 SVG 对应位置都必须仍是 `3.1 h`。

正式出图建议：

```json
"range_guard": {"mode": "error"}
```

这样任何数值越过 y 轴范围都会直接报错，而不是被静默裁剪。

## 2. 布局调试顺序

不要同时改很多参数。按以下顺序：

1. `panel_size_mm`
2. `gap_mm`
3. `margin_mm`
4. `legend.anchor_y_mm` 或 `legend.shift_y_mm`
5. `legend.shift_x_mm`
6. 字号和线宽

如果两个独立 SVG 需要拼接，前三项必须完全一致。

## 3. 一列布局人工检查

目标：图例位于第一行图框正上方中央。

检查：

- 图例中心是否与单列 panel 中心一致。
- 图例是否压住第一行上边框。
- 增大图例字号后是否仍有顶部空间。
- A1/A2/A3/A4 左右边界是否完全一致。

建议先调 `margin_mm.top`，再调 `legend.shift_y_mm`。

## 4. 两列布局人工检查

目标：图例位于第一行两个 panel 共同上方中央。

检查：

- 不是左图中心，也不是右图中心，而是整个两列 panel block 中心。
- 两列之间 `gap_mm[0]` 改变后，图例中心仍正确。
- 左右 y 标签长度不应改变 panel 本身的位置。

## 5. 圆周变量

对风向/波向构造人工测试：

```text
355, 358, 2, 5
```

开启：

```json
"circular": true
```

预期：358° 与 2° 之间断线，不能跨整张图画一条长线。

## 6. 范围保护

人为把一个值改成超出 y 轴，例如：

```text
axis = [0, 25]
data = 31
```

在 `range_guard.mode=error` 下应停止并报告数据范围，不应生成裁切后的正式图。

## 7. 原始时间

构造：

```text
2.0, 3.1, 4.05, 5.0
```

检查 x 坐标必须保持原值；工具不得 round/floor/ceil。

## 8. SVG 几何一致性

生成两张相同布局、不同数据的 SVG：

- 检查 SVG width/height 相同。
- 检查每个坐标框的 x/y/width/height 相同。
- 固定几何输出不使用 `bbox_inches="tight"`。

## 9. 回归测试最小集合

每次代码变更至少人工跑：

1. `1 × 1`
2. `4 × 1`
3. `1 × 2`
4. `2 × 2`
5. 一个圆周变量
6. 一个有非整点实测时间的变量
7. 一个故意越界并期望报错的 case

## 10. 常见问题定位

- 图例压住图框：增大 `margin_mm.top` 或调整 `legend.shift_y_mm`。
- 左侧标签被裁：增大 `margin_mm.left`。
- 底部标签被裁：增大 `margin_mm.bottom`。
- 两张图拼不齐：核对 `panel_size_mm / gap_mm / margin_mm` 是否逐项一致。
- 数据被裁：开启 `range_guard=error`，不要靠肉眼发现。
- 实测曲线显得太折：这是原始离散点的直线连接，不应为了平滑而拟合。
