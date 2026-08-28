# directory_scanner

跨平台目录扫描器：递归生成**目录树、文件清单、扫描摘要**。仅使用 Python 标准库，适合大型科研数据目录的快速索引。

## 运行

扫描指定目录：

```bash
python scan_directory.py "D:\\data\\MASCS"
```

Linux / macOS：

```bash
python scan_directory.py /data/MASCS
```

默认将输出写入被扫描目录；也可指定独立输出目录：

```bash
python scan_directory.py /data/MASCS --output-dir ./scan_result
```

排除不需要的目录或文件，可重复使用 `--exclude`：

```bash
python scan_directory.py /data/MASCS --exclude "*.tmp" --exclude ".git" --exclude "cache"
```

## 输出

- `目录树.txt`：人工快速阅读目录结构。
- `文件清单.csv`：适合 Excel、Python 或 AI 后续检索。
- `扫描摘要.txt`：文件数、总大小、扩展名统计和读取错误数。

CSV 使用 UTF-8 with BOM，便于 Windows Excel 直接打开。

## 行为约定

- 默认不跟随目录符号链接，避免循环扫描。
- 文件顺序稳定，便于两次扫描做 diff。
- 单个文件/目录无权限不会终止整次扫描；错误计入摘要。
- CSV 中相对路径统一使用 `/`，便于跨平台和 AI 处理。
- 不修改被扫描文件。
