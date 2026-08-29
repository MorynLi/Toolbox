# file_scan

面向 AI / LLM 的轻量目录索引生成器。递归扫描一个目录后，生成低上下文成本、可分层检索的文件系统索引。仅使用 Python 标准库。

> v2.0 是一次有意的主版本升级：默认输出目录、输出文件名和索引字段发生变化。原有命令行入口仍保持不变。

## 典型用途

当一个科研、工程或代码目录包含大量文件时，不要把完整目录树直接塞给 AI。先运行 `file_scan`，再让 AI 按以下顺序读取：

1. `_file_scan/summary.md`：先建立整体认知。
2. `_file_scan/tree.txt`：需要目录结构时再看。
3. `_file_scan/files.csv`：需要精确定位文件时检索。
4. `_file_scan/manifest.json`：脚本或 AI 需要机器可读扫描元数据时使用。

## 运行

Windows：

```bash
python scan_directory.py "D:\data\MASCS"
```

Linux / macOS：

```bash
python scan_directory.py /data/MASCS
```

默认在被扫描目录内创建独立结果目录：

```text
目标目录/
├── 原始文件...
└── _file_scan/
    ├── summary.md
    ├── tree.txt
    ├── files.csv
    └── manifest.json
```

`_file_scan/` 会自动从扫描内容中排除，因此重复扫描不会把上一次的扫描结果重新索引。

如果希望把结果写到其他位置：

```bash
python scan_directory.py /data/MASCS --output-dir ./scan_result
```

`--output-dir` 指定的是**最终输出目录本身**，不会再自动追加 `_file_scan`。

## 输出

### `summary.md`

AI 的第一读取入口，包含：

- 扫描根目录、开始/结束时间、工具版本；
- 文件数、包含文件的目录数、总大小、错误数；
- 一级目录文件量与体量分布；
- 通用文件类别统计；
- 扩展名统计；
- 常见入口文件和配置文件；
- 最大文件列表；
- 推荐 AI 读取顺序。

该文件用于快速建立目录认知，而不是替代精确文件索引。

### `tree.txt`

默认生成**紧凑目录树**。

以下低价值或高体量目录只显示统计信息，不递归展开：

```text
.git
.venv
venv
env
node_modules
__pycache__
.pytest_cache
.mypy_cache
.ruff_cache
.cache
cache
dist
build
```

示例：

```text
├── [dir] frontend/
│   ├── [dir] src/
│   └── [dir] node_modules/ [folded: low-value directory; 7032 files; 168.40 MB]
```

默认最多展开 4 层目录。更深目录仍会显示，但内容折叠并附带文件数和大小。

调整深度：

```bash
python scan_directory.py /data/MASCS --max-depth 6
```

需要完整目录树时：

```bash
python scan_directory.py /data/MASCS --full-tree
```

`--full-tree` 会关闭默认目录折叠和深度限制，超大目录慎用。

### `files.csv`

完整文件级索引。即使 `.venv`、`node_modules` 等目录在 `tree.txt` 中被折叠，其中的文件仍然保留在 `files.csv`，除非用户通过 `--exclude` 明确排除。

字段：

| 字段 | 含义 |
|---|---|
| `relative_path` | 相对扫描根目录的路径，统一使用 `/` |
| `parent_folder` | 父目录 |
| `file_name` | 文件名 |
| `extension` | 小写扩展名 |
| `size_bytes` | 字节数；读取失败时为 `-1` |
| `size_readable` | 人类可读大小 |
| `modified_time` | 本机时区的 ISO 8601 修改时间 |
| `depth` | 文件父目录相对扫描根目录的深度；根目录文件为 `0` |
| `category` | 通用文件类别 |

通用类别：

```text
source
document
data
config
image
archive
binary
dependency
generated
other
```

分类仅用于 AI 快速筛选，不代表科研领域语义，也不会写入具体课题名称、模型类型或事件信息。

CSV 使用 UTF-8 with BOM，便于 Windows Excel 直接打开，同时保持标准 CSV 格式。

### `manifest.json`

机器可读扫描清单，记录：

- `schema_version`
- `tool_version`
- 扫描根目录与输出目录
- 扫描开始/结束时间
- 文件数、目录数、总字节数、错误数
- 排除规则
- 符号链接策略
- tree 模式、最大深度与折叠目录
- `files.csv` 字段定义

后续若增加扫描结果 diff、增量扫描或其他 AI 工具链，可直接基于该文件判断索引版本和扫描状态。

## 排除规则

`--exclude` 可重复使用：

```bash
python scan_directory.py /data/MASCS \
  --exclude "*.tmp" \
  --exclude "*.log" \
  --exclude "raw_backup"
```

排除规则同时作用于 `summary.md`、`tree.txt`、`files.csv` 和 `manifest.json` 中的统计结果。

注意：

- 默认的“折叠”不等于“排除”；
- `.venv`、`node_modules` 等默认仍进入完整 `files.csv`；
- 只有 `--exclude` 才会真正让文件退出索引。

## 符号链接

默认不跟随目录符号链接，避免循环扫描：

```bash
python scan_directory.py /data/MASCS
```

确实需要跟随时：

```bash
python scan_directory.py /data/MASCS --follow-symlinks
```

## v2.0 相对 v1.0 的主要变化

1. 默认输出从扫描根目录的三个散装文件改为 `_file_scan/` 独立目录。
2. 输出改为 `summary.md`、`tree.txt`、`files.csv`、`manifest.json`。
3. `summary.md` 改为面向 AI 的首要入口，而不再只是文件数和扩展名统计。
4. `tree.txt` 默认采用紧凑模式，对依赖、缓存、构建产物和过深目录进行折叠。
5. `files.csv` 增加修改时间、目录深度和通用类别，同时保留原有核心路径/大小字段。
6. 新增 `manifest.json`，提供稳定的机器可读扫描元数据。
7. 增加 `--max-depth` 与 `--full-tree`。
8. 默认扫描结果目录自动排除自身，重复扫描不会污染索引。
9. 文件状态读取改用兼容 Python 3.9+ 的 `stat()/lstat()` 路径。

## 行为约定

- 不修改被扫描的原始文件。
- 默认不跟随目录符号链接。
- 文件顺序稳定，便于后续做 diff。
- 单个文件或目录无权限不会终止整个扫描；错误会进入 `summary.md` 和 `manifest.json` 统计。
- 相对路径统一使用 `/`，便于 Windows、Linux、macOS 和 AI 统一处理。
- 不把具体课题语义写进通用分类逻辑。
- 仅使用 Python 标准库，无额外依赖。

## 最小检查

查看版本：

```bash
python scan_directory.py --version
```

语法检查：

```bash
python -m py_compile scan_directory.py
```

对一个小目录执行 smoke test 后，应至少确认：

```text
_file_scan/summary.md
_file_scan/tree.txt
_file_scan/files.csv
_file_scan/manifest.json
```

均存在，并且 `files.csv` 中不存在 `_file_scan/` 自身生成文件。
