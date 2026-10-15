# academic_plot

科研出图工具：验证时序图 + 经纬度场地图。项目侧准备标准 CSV/NetCDF + JSON 图规格；工具负责出版样式档、固定物理几何、原始时间保留、圆周变量断线、有效时间窗裁剪、范围审计与文字排版 QC。

## 出版样式档（profile）

图规格写 `"profile": "thesis_zh"` 或 `"journal_en"`，字体、字号、线宽、标目写法、宽度档、导出格式全部由样式档决定，图规格本身不写字号。

| | `thesis_zh`（大工硕士论文） | `journal_en`（Elsevier 基准） |
|---|---|---|
| 宽度档 mm | full 150 / half 74 | single 90 / onehalf 140 / full 190 |
| 字体 | 宋体 + Times New Roman | Times New Roman |
| 图内字号 pt | 9（小五），注记 7.5 | 刻度 7，标目 8 |
| 标目 | `有效波高 Hs/m`（GB 3102，量/单位） | `Hs (m)` |
| 导出 | PDF + SVG + PNG 600 dpi | PDF + SVG + PNG 1000 dpi |

规则：

- **按成品尺寸出图，插入文档时 100% 不缩放**（题注片段里已写好 mm 宽度）。
- **图题不画进图里**。图规格写 `caption.zh/en`，渲染时生成同名 `.tex`（论文用 `\bicaption`，期刊用 `\caption`）；Word 里用题注样式插入同样的文字。
- 标目写语义：`{"quantity": {"zh": "有效波高", "en": "Significant wave height"}, "symbol": "H_s", "unit": "m"}`，同一份规格切换 profile 即得中/英两版。
- 几何写宽度档：`"geometry": {"profile": "academic_mm_v1", "width": "full", "panel_aspect": 0.55}`。边距与字号绑定在样式档里，同一宽度档的图文字几何完全一致。显式 `panel_size_mm` 仍可用。
- 多列时非首列自动隐藏 y 刻度数字；子图编号 (a)(b)… 自动添加。
- 不写 `profile` 的旧配置行为与 1.4 版完全一致（只出 SVG）。

### 字体：final / draft

- 默认 **final**：样式档字体必须真实加载，否则报错，不静默回退。
- 字体文件位置：`--font-dir <文件夹>` 或环境变量 `ACADEMIC_PLOT_FONT_DIR`。Windows 下为 `C:\Windows\Fonts`（`times*.ttf`、`simsun.ttc`）；WSL 下 `/mnt/c/Windows/Fonts`。
- **draft**（`--draft`）：缺哪个字体就用等度量替代（Liberation Serif ≈ Times New Roman；Noto Serif CJK 与宋体同为 1 em 汉字宽），排版几何与终稿一致，PNG 角标 DRAFT。适合没有商业字体的云端预览。
- 商业字体不得提交进仓库（`.gitignore` 已排除 `*.ttf/*.ttc/*.otf`）。

### 文字排版 QC

带 profile 出图时自动检查：文字间距 < 1 mm 或超出画布即报错（`"qc": {"text": "warn"|"off", "min_gap_mm": 1.0}` 可调）。同一坐标轴自身的 x/y 刻度在角点相邻不计。

## 地图（plot_map.py）

```bash
python plot_map.py --config example/map_config.json --output out/map.svg --font-dir C:/Windows/Fonts
```

- 投影为等经纬度（Plate Carrée）。panel 宽高比由 `map.extent` 自动推出，地图框与 mm 几何严格一致，不会被内缩。
- 输入：NetCDF（`input` + `var`，需 xarray）或 CSV 长表（`lon, lat, value`）。
- 色标：`field.levels`、`field.ticks`、`field.extend` 固定写在规格里；同一变量的多张图必须共用同一套 levels。数据超出 levels 且未 extend → 报错。
- `colorbar.position`：`bottom`（多图共用，默认）/ `right` / `none`。
- 陆地：`map.land.source` = `natural_earth`（需 cartopy 及已缓存的 Natural Earth 数据）/ GeoJSON 文件路径 / `none`。
- 填色层在 PDF/SVG 中栅格化（分辨率 = 样式档 dpi），文字与线条保持矢量。
- `display_smoothing` 默认关闭；开启（重采样 + 归一化高斯平滑）仅用于显示，必须在图题中说明。
- 经度刻度不要贴在 extent 边缘（相邻 panel 的刻度会相撞，QC 会拒绝）。
- `display_smoothing.blank_missing: true`：CSV 中“有行但无值”的格点（如样本不足、未拟合的海上格点）在平滑后整格留白，不被邻格填补；CSV 中没有的格点（陆地）不受影响。
- `field.contour_color`（默认 `"0.2"`）；等值线线宽和数值字号用 `style.contour_line_width`、`style.annotation_fontsize` 覆盖。
- `field.label` 为空字符串时色标不加文字标注；`colorbar.tick_direction`（默认 `in`）；`map.tick_direction: "out"` 时刻度朝外，且只在左侧和下方。
- `export: {"formats": [...], "png_dpi": N}` 覆盖样式档的导出格式；有 `caption` 时另写 `<stem>.caption.txt`（Word 题注文字）。每个文件的元数据记录引擎版本和样式档。
- 项目侧锁定样式的用法：把完整 spec（除 panels/caption/色阶外）存为项目内模板，项目脚本只填数据和图题，参见 south-china-sea 项目 `绘图/scs_map.py`。

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
├─ style.py                  # 样式档、字体、标目、导出、题注片段、文字 QC
├─ profiles/
│  ├─ thesis_zh.json
│  └─ journal_en.json
├─ plot_validation.py        # 多站点 × 单变量
├─ plot_multivariable.py     # 单事件 × 多变量
├─ plot_map.py               # 经纬度场地图
├─ requirements.txt
├─ example/
│  ├─ config_1col_a4.json
│  ├─ config_2col.json
│  ├─ config_profile_thesis.json
│  └─ map_config.json
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
python plot_validation.py --input example/input.csv --config example/config_profile_thesis.json --output out/pressure.svg --font-dir C:/Windows/Fonts
python plot_map.py --config example/map_config.json --output out/map.svg --draft
python tests/smoke_test.py
```

人工检查与调参顺序见 `docs/MANUAL_TESTING.md`。

## 维护约束

- 核心代码不写具体课题路径、事件时间或站点真值。
- 不自动补造缺失数据，不隐式插值。
- 固定毫米布局输出不得使用 `bbox_inches="tight"`，避免数据内容改变 SVG 外框。
- 视觉语法变更视为版本变更，并尽量保持旧配置可运行。
