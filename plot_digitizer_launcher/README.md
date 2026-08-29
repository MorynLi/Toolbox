# plot_digitizer_launcher

Windows 下的 PlotDigitizer 一键启动/停止封装。它不复制或修改 PlotDigitizer 上游源码，只解决已经完成 Python/Node 环境配置后的日常启动摩擦：**双击启动，自动打开网页；双击停止，安全清理进程。**

上游项目：`https://github.com/valentinognev/PlotDigitizer`

## 适用场景

PlotDigitizer 本体已经能正常运行，但每次手工启动需要记住后端、前端和网页地址。上游 `start.sh` / `kill.sh` 采用 Bash/Linux 路径约定，而 Windows 虚拟环境通常位于 `.venv\Scripts\`。

本工具将日常操作固定为：

```text
双击 PlotDigitizer.bat
    ↓
检查现有环境
    ↓
必要时构建 frontend/dist
    ↓
启动 FastAPI :8000
    ↓
启动 Vite preview :5173
    ↓
等待健康检查
    ↓
自动打开 http://127.0.0.1:5173
```

停止时双击 `Stop PlotDigitizer.bat`。

## 文件

```text
plot_digitizer_launcher/
├── README.md
├── PlotDigitizer.bat
└── Stop PlotDigitizer.bat
```

## 部署

前提：上游 PlotDigitizer 已经完成依赖安装，至少应存在：

```text
PlotDigitizer/
├── backend/
│   └── .venv/
│       └── Scripts/
│           └── uvicorn.exe
└── frontend/
    ├── package.json
    └── node_modules/
```

将本目录中的两个 `.bat` 文件复制到 **PlotDigitizer 仓库根目录**，即与 `backend/`、`frontend/` 同级。脚本通过 `%~dp0`/当前脚本目录解析根路径，不写死盘符或安装位置。

随后直接双击：

```text
PlotDigitizer.bat
```

关闭：

```text
Stop PlotDigitizer.bat
```

## 启动器行为

`PlotDigitizer.bat`：

- 检查 Windows 后端入口 `backend\.venv\Scripts\uvicorn.exe`、`frontend\node_modules` 和 `npm`。
- 若前后端已经可访问，不重复创建进程，只打开浏览器。
- `frontend/dist/index.html` 不存在或 `frontend/src` 更新后，才执行 `npm run build`。
- 构建后立即使用 `if errorlevel 1` 判断真实退出码，避免 `cmd.exe` 括号块中 `%变量%` 预展开导致“构建成功却误报失败”。
- 后端使用 `uvicorn app.main:app --host 127.0.0.1 --port 8000`。
- 前端使用 `npm run preview -- --host 127.0.0.1 --port 5173`。
- 启动后检查 `http://127.0.0.1:8000/health` 与前端 URL，就绪后自动打开浏览器。
- PID 与日志写入 PlotDigitizer 根目录下的 `.run/`，正常启动不要求用户手工管理终端窗口。

## 停止器的安全策略

`Stop PlotDigitizer.bat` 不直接信任旧 PID 文件。停止前依次检查：

1. PID 内容必须为正整数；
2. PID 当前对应的进程名必须属于预期进程类型；
3. 进程启动时间必须与 PID 文件写入时间处于合理窗口，降低 PID 被系统复用后误杀其他程序的风险。

如果 PID 文件缺失或已陈旧，脚本会再扫描命令行，只清理同时满足以下条件的进程：

- 命令行属于当前 PlotDigitizer 根目录；
- 后端匹配 `uvicorn ... app.main:app`，或前端匹配 Vite `preview`；
- Vite 兜底正则兼容 Windows 命令行中 `vite.js" preview` 的闭合引号形式。

等待使用 PowerShell `Start-Sleep`，不依赖 `timeout` 的交互式输入，因此可避免重定向/非交互终端下的 `Input redirection is not supported`。

## 日志与排错

运行后可检查：

```text
.run/
├── backend.windows.log
├── backend.windows.err.log
├── frontend.windows.log
├── frontend.windows.err.log
├── backend.windows.pid
└── frontend.windows.pid
```

若启动失败，优先查看两个 `*.err.log`。

## 已验证行为

2026-08-29 的完整验证覆盖了原故障路径：

- 删除现有 `frontend/dist` 后强制重建，`npm run build` 成功且启动器继续正常启动，不再误报 `Frontend build failed`。
- 后端 `/health` 返回 HTTP 200，前端 `:5173` 返回 HTTP 200。
- 正常停止后前后端进程树、PID 文件和 8000/5173 监听均清除。
- 人工移走前端 PID 文件后，兜底扫描仍能识别并停止 Vite 进程。
- 程序已停止时再次执行停止脚本保持退出码 0，不产生残留。
- 强制重建前后的 `dist` 逐文件 SHA-256 一致：5 个文件，差异数 0。

## 边界

- 本工具是 **Windows 启动封装**，不是 PlotDigitizer 的 fork。
- 不在 Toolbox 中保存上游 `backend/`、`frontend/`、虚拟环境或 `node_modules`。
- 不负责首次安装 PlotDigitizer 依赖；首次安装仍按上游项目说明执行。
- 不修改 PlotDigitizer 网页内部操作流程和数据格式。
