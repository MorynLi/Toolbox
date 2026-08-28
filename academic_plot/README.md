# academic_plot

长期维护的科研“实测—模拟”验证图工具。项目侧只负责准备标准 CSV 与 JSON；本工具负责稳定的学术版式和 SVG 输出。

## 稳定视觉语法

- 正式输出：SVG，文字保持文本对象。
- 实测：深红色虚线 `#8B0000`。
- 模拟：黑色实线。
- 主图默认不放图例；图例可单独输出 SVG。
- 站点标签位于图框内部左上。
- 默认不使用 `(a)(b)(c)(d)`。
- 第一行不重复横轴标题；非首列不重复纵轴标题。
- 无网格、完整矩形坐标框、刻度向内。
- 风向等圆周变量可启用断线处理，避免跨 0/360° 画出伪长线。

## 输入 CSV

至少包含 4 列：

```text
time_h,station,observed,simulated
0,A1,1006.2,
0.25,A1,1006.4,
1,A1,1007.0,1006.8
```

观测与模拟允许不同采样频率；缺失值独立保留，不要求强制插值。

默认字段名可在 JSON 中通过 `x_col`、`station_col`、`observed_col`、`simulated_col` 修改。

## JSON 配置

最小结构见 `example/config.json`。项目级内容放在配置里：

- 子图行列数与尺寸；
- 站点顺序；
- x/y 轴范围、刻度与标签；
- 是否为圆周变量；
- 单独图例文字；
- 少量必要的视觉参数覆盖。

## 安装与运行

```bash
cd academic_plot
python -m pip install -r requirements.txt
python plot_validation.py \
  --input example/input.csv \
  --config example/config.json \
  --output validation.svg \
  --legend-output legend.svg
```

Windows PowerShell 可写为一行：

```powershell
python plot_validation.py --input example/input.csv --config example/config.json --output validation.svg --legend-output legend.svg
```

## 约束

- 不在代码中写具体课题路径、时间窗或站点数据。
- 不自动补造缺失数据，不隐式插值。
- 站点数量不得超过 `rows × cols`；配置或字段错误会直接报出。
- 修改颜色、线型、站点标签位置、坐标框规则等稳定视觉语法时，应视为版本升级。
