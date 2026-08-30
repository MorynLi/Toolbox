# academic_plot 人工测试与调试指南

## 1. 数据先于版式

正式出图前至少检查：

- reference / simulation 的 `x_min / x_max / y_min / y_max / N`
- 有可靠性标记时，过滤后的有效 N 与首尾时刻
- `x_axis.range` 与 `y_axis.range`

正式出图推荐：

```json
"range_guard": {"mode": "error"}
```

任何真实数据越过 y 轴范围都应直接失败，不允许静默裁切。

## 2. 原始实测时间

构造：

```text
2.0, 3.1, 4.05, 5.0
```

输入、内部数据和 SVG 横坐标都必须保持原值；工具不得 round/floor/ceil。

## 3. 布局调参顺序

按以下顺序修改，避免同时改变多个自由度：

1. `panel_size_mm`
2. `gap_mm`
3. `margin_mm`
4. `x_axis.bottom_band.y_mm`
5. `legend.anchor_y_mm` / `legend.shift_y_mm`
6. `legend.shift_x_mm`
7. 字号与线宽

需要拼版的图应固定前 4 项。

## 4. 横轴数字

稳定规则：`tick_label_policy=bottom`。

人工回归：

- `4 × 1`：仅第 4 行显示横轴数字。
- `2 × 2`：仅第 2 行两个 panel 显示横轴数字。
- `1 × 1`：保留横轴数字。
- `1 × 2`：两个 panel 都保留横轴数字。

## 5. 时间戳与“时间(h)”硬性标准

每张组合图只显示一次时间戳。固定毫米布局下：

1. 时间戳与 `时间(h)` 使用完全相同的 `bottom_band.y_mm` 竖直中心线。
2. 时间戳字号小于主横轴标签字号。
3. 时间戳下边缘不得低于 `时间(h)` 下边缘。
4. 时间戳上边缘不得高于 `时间(h)` 上边缘。
5. 不同图使用相同 `bottom_band.y_mm`，保证纵向位置固定。
6. 时间戳不加“起始”“起始时间”等前缀。

建议默认：

```json
"bottom_band": {"y_mm": 8.5}
```

## 6. 固定截断 + 新起点归零

```json
"x_window": {
  "mode": "fixed",
  "start": 24,
  "end": 96,
  "rebase_to_zero": true,
  "tick_step": 24
}
```

预期：

- 24 h 前数据完全不进入图。
- 原 24 h 变为新 0 h。
- 原 27.1 h 变成 3.1 h，而不是 3 h。

## 7. 有效交集时间窗

构造：

```text
reference: 6, 12, 18, ..., 72
simulation(valid): 12, 13, ..., 66
```

`x_window.mode=common_valid` 后，窗口应为 `[12, 66]`；若 `rebase_to_zero=true`，显示为 `[0, 54]`。

如果 `simulation_valid` 排除了前期点，交集起点必须相应后移，不能按未经 QC 的模拟首时刻裁图。

## 8. 圆周变量

测试：

```text
355, 358, 2, 5
```

开启 `circular=true` 后，358° 与 2° 之间必须断线，不能跨整张图画伪长线。

## 9. 图例

- 一列：位于第一行单 panel 正上方中央。
- 两列及以上：位于第一行整个 panel block 正上方中央。
- 改变横向 `gap_mm[0]` 后仍应自动居中。

## 10. SVG 几何一致性

用相同布局生成两张不同数据的 SVG：

- width/height 必须一致。
- 每个 panel 的 x/y/width/height 必须一致。
- 图例、时间戳、`时间(h)` 的绝对位置不应随曲线内容移动。
- 固定几何模式不得使用 `bbox_inches="tight"`。

## 11. 最小回归测试集合

每次核心代码变更至少跑：

1. `1 × 1`
2. `4 × 1`
3. `1 × 2`
4. `2 × 2`
5. 圆周变量
6. 非整点实测时间
7. `fixed + rebase_to_zero`
8. `common_valid`
9. 故意越界并期望报错

可先运行：

```bash
python tests/smoke_test.py
```

## 12. 常见问题定位

- 图例压图框：先增加 `margin_mm.top`，再调 `legend.shift_y_mm`。
- 时间戳高低不一致：只调统一的 `bottom_band.y_mm`，不要对不同图分别用 axes 相对坐标。
- 横轴数字重复：确认 `tick_label_policy=bottom`。
- 两张图拼不齐：逐项核对 `panel_size_mm / gap_mm / margin_mm / bottom_band.y_mm`。
- 数据被裁：开启 `range_guard=error`。
- 实测曲线太折：这是原始点的直线连接，不能为了好看而拟合。
