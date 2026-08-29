@echo off
setlocal EnableExtensions
cd /d "%~dp0"

rem ============================================================
rem PlotDigitizer - Windows one-click launcher
rem Place this file in the PlotDigitizer repository root.
rem ============================================================

set "PD_ROOT=%CD%"
set "PD_RUN_DIR=%PD_ROOT%\.run"

set "PD_BACKEND_HOST=127.0.0.1"
set "PD_BACKEND_PORT=8000"
set "PD_FRONTEND_HOST=127.0.0.1"
set "PD_FRONTEND_PORT=5173"

set "PD_BACKEND_EXE=%PD_ROOT%\backend\.venv\Scripts\uvicorn.exe"
set "PD_BACKEND_PID=%PD_RUN_DIR%\backend.windows.pid"
set "PD_FRONTEND_PID=%PD_RUN_DIR%\frontend.windows.pid"

set "PD_BACKEND_LOG=%PD_RUN_DIR%\backend.windows.log"
set "PD_BACKEND_ERR=%PD_RUN_DIR%\backend.windows.err.log"
set "PD_FRONTEND_LOG=%PD_RUN_DIR%\frontend.windows.log"
set "PD_FRONTEND_ERR=%PD_RUN_DIR%\frontend.windows.err.log"

set "PD_APP_URL=http://%PD_FRONTEND_HOST%:%PD_FRONTEND_PORT%"
set "PD_HEALTH_URL=http://%PD_BACKEND_HOST%:%PD_BACKEND_PORT%/health"

if not exist "%PD_RUN_DIR%" mkdir "%PD_RUN_DIR%" >nul 2>&1

echo ========================================
echo PlotDigitizer
echo ========================================

if not exist "%PD_BACKEND_EXE%" (
    echo [ERROR] Backend executable not found:
    echo         "%PD_BACKEND_EXE%"
    echo.
    echo The existing Python environment appears incomplete.
    pause
    exit /b 1
)

if not exist "%PD_ROOT%\frontend\node_modules" (
    echo [ERROR] frontend\node_modules not found.
    echo The existing frontend environment appears incomplete.
    pause
    exit /b 1
)

where npm >nul 2>&1
if errorlevel 1 (
    echo [ERROR] npm was not found on PATH.
    pause
    exit /b 1
)

call :url_ok "%PD_HEALTH_URL%"
set "BACKEND_OK=%ERRORLEVEL%"
call :url_ok "%PD_APP_URL%"
set "FRONTEND_OK=%ERRORLEVEL%"

if "%BACKEND_OK%"=="0" if "%FRONTEND_OK%"=="0" (
    echo PlotDigitizer is already running.
    echo Opening %PD_APP_URL%
    start "" "%PD_APP_URL%"
    exit /b 0
)

if not "%FRONTEND_OK%"=="0" (
    call :frontend_needs_build
    if errorlevel 1 (
        echo [1/3] Building frontend...
        pushd "%PD_ROOT%\frontend"
        call npm run build
        if errorlevel 1 (
            popd
            echo.
            echo [ERROR] Frontend build failed.
            pause
            exit /b 1
        )
        popd
    )
)

if not "%BACKEND_OK%"=="0" (
    echo [2/3] Starting backend...
    powershell -NoProfile -ExecutionPolicy Bypass -Command ^
      "$p = Start-Process -FilePath $env:PD_BACKEND_EXE -ArgumentList @('app.main:app','--host',$env:PD_BACKEND_HOST,'--port',$env:PD_BACKEND_PORT) -WorkingDirectory (Join-Path $env:PD_ROOT 'backend') -WindowStyle Hidden -RedirectStandardOutput $env:PD_BACKEND_LOG -RedirectStandardError $env:PD_BACKEND_ERR -PassThru; Set-Content -LiteralPath $env:PD_BACKEND_PID -Value $p.Id"
    if errorlevel 1 (
        echo [ERROR] Failed to launch backend.
        pause
        exit /b 1
    )

    powershell -NoProfile -ExecutionPolicy Bypass -Command ^
      "$deadline=(Get-Date).AddSeconds(15); do { try { $r=Invoke-WebRequest -Uri $env:PD_HEALTH_URL -UseBasicParsing -TimeoutSec 1; if($r.StatusCode -ge 200 -and $r.StatusCode -lt 400){exit 0} } catch {}; Start-Sleep -Milliseconds 300 } while((Get-Date) -lt $deadline); exit 1"
    if errorlevel 1 (
        echo.
        echo [ERROR] Backend did not become healthy.
        echo See:
        echo   "%PD_BACKEND_LOG%"
        echo   "%PD_BACKEND_ERR%"
        pause
        exit /b 1
    )
)

call :url_ok "%PD_APP_URL%"
if errorlevel 1 (
    echo [3/3] Starting frontend...
    powershell -NoProfile -ExecutionPolicy Bypass -Command ^
      "$p = Start-Process -FilePath 'cmd.exe' -ArgumentList @('/d','/s','/c','npm run preview -- --host ' + $env:PD_FRONTEND_HOST + ' --port ' + $env:PD_FRONTEND_PORT) -WorkingDirectory (Join-Path $env:PD_ROOT 'frontend') -WindowStyle Hidden -RedirectStandardOutput $env:PD_FRONTEND_LOG -RedirectStandardError $env:PD_FRONTEND_ERR -PassThru; Set-Content -LiteralPath $env:PD_FRONTEND_PID -Value $p.Id"
    if errorlevel 1 (
        echo [ERROR] Failed to launch frontend.
        pause
        exit /b 1
    )

    powershell -NoProfile -ExecutionPolicy Bypass -Command ^
      "$deadline=(Get-Date).AddSeconds(20); do { try { $r=Invoke-WebRequest -Uri $env:PD_APP_URL -UseBasicParsing -TimeoutSec 1; if($r.StatusCode -ge 200 -and $r.StatusCode -lt 400){exit 0} } catch {}; Start-Sleep -Milliseconds 300 } while((Get-Date) -lt $deadline); exit 1"
    if errorlevel 1 (
        echo.
        echo [ERROR] Frontend did not become ready.
        echo See:
        echo   "%PD_FRONTEND_LOG%"
        echo   "%PD_FRONTEND_ERR%"
        pause
        exit /b 1
    )
)

echo.
echo PlotDigitizer started successfully.
echo Opening %PD_APP_URL%
start "" "%PD_APP_URL%"
exit /b 0


:url_ok
set "PD_CHECK_URL=%~1"
powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "try { $r=Invoke-WebRequest -Uri $env:PD_CHECK_URL -UseBasicParsing -TimeoutSec 1; if($r.StatusCode -ge 200 -and $r.StatusCode -lt 400){exit 0}else{exit 1} } catch { exit 1 }"
exit /b %ERRORLEVEL%


:frontend_needs_build
if not exist "%PD_ROOT%\frontend\dist\index.html" exit /b 1

powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "$dist=(Get-Item -LiteralPath (Join-Path $env:PD_ROOT 'frontend\dist\index.html')).LastWriteTime; $newer=Get-ChildItem -LiteralPath (Join-Path $env:PD_ROOT 'frontend\src') -File -Recurse -ErrorAction SilentlyContinue | Where-Object { $_.LastWriteTime -gt $dist } | Select-Object -First 1; if($null -ne $newer){exit 1}else{exit 0}"
exit /b %ERRORLEVEL%
