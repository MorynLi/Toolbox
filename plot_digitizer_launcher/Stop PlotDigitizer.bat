@echo off
setlocal EnableExtensions
cd /d "%~dp0"

rem ============================================================
rem PlotDigitizer - Windows stop launcher
rem Place this file in the PlotDigitizer repository root.
rem ============================================================

set "PD_ROOT=%CD%"
set "PD_RUN_DIR=%PD_ROOT%\.run"
set "PD_BACKEND_PID=%PD_RUN_DIR%\backend.windows.pid"
set "PD_FRONTEND_PID=%PD_RUN_DIR%\frontend.windows.pid"

echo ========================================
echo Stopping PlotDigitizer
echo ========================================

call :kill_tree "Frontend" "%PD_FRONTEND_PID%" "cmd|npm|node"
call :kill_tree "Backend" "%PD_BACKEND_PID%" "uvicorn|python|pythonw"

rem Fallback cleanup for processes started without valid Windows PID files.
rem Only targets command lines that clearly belong to this PlotDigitizer root.
powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "$root=[regex]::Escape($env:PD_ROOT); $self=$PID; Get-CimInstance Win32_Process | Where-Object { $_.ProcessId -ne $self -and $_.CommandLine -and $_.CommandLine -match $root -and ( $_.CommandLine -match 'vite(?:\.js)?\x22?\s+preview' -or $_.CommandLine -match 'uvicorn(?:\.exe)?\x22?\s+app\.main:app' -or $_.CommandLine -match '-m\s+uvicorn\s+app\.main:app' ) } | ForEach-Object { & taskkill.exe /PID $_.ProcessId /T /F 2>$null | Out-Null }" >nul 2>&1

echo.
echo Done.
powershell -NoProfile -ExecutionPolicy Bypass -Command "Start-Sleep -Milliseconds 700" >nul 2>&1
exit /b 0


:kill_tree
set "PD_STOP_NAME=%~1"
set "PD_STOP_PID_FILE=%~2"
set "PD_ALLOWED_NAMES=%~3"

powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "$name=$env:PD_STOP_NAME; $pidFile=$env:PD_STOP_PID_FILE; $allowed=$env:PD_ALLOWED_NAMES.Split('|'); if(-not (Test-Path -LiteralPath $pidFile)){ Write-Host ($name + ': no Windows PID file.'); exit 0 }; $raw=(Get-Content -LiteralPath $pidFile -Raw).Trim(); $procId=0; if(-not [int]::TryParse($raw,[ref]$procId) -or $procId -le 0){ Remove-Item -LiteralPath $pidFile -Force -ErrorAction SilentlyContinue; Write-Host ($name + ': invalid PID file removed.'); exit 0 }; $p=Get-CimInstance Win32_Process -Filter ('ProcessId=' + $procId) -ErrorAction SilentlyContinue; if($null -eq $p){ Remove-Item -LiteralPath $pidFile -Force -ErrorAction SilentlyContinue; Write-Host ($name + ': stale PID file removed.'); exit 0 }; $actual=[IO.Path]::GetFileNameWithoutExtension([string]$p.Name).ToLowerInvariant(); if($allowed -notcontains $actual){ Remove-Item -LiteralPath $pidFile -Force -ErrorAction SilentlyContinue; Write-Host ($name + ': PID ' + $procId + ' belongs to unexpected process ' + $actual + '; stale PID file removed.'); exit 0 }; try { if($p.CreationDate -is [datetime]){ $started=[datetime]$p.CreationDate } else { $started=[Management.ManagementDateTimeConverter]::ToDateTime([string]$p.CreationDate) }; $written=(Get-Item -LiteralPath $pidFile).LastWriteTime; $delta=($written-$started).TotalSeconds } catch { $delta=999999 }; if($delta -lt -5 -or $delta -gt 120){ Remove-Item -LiteralPath $pidFile -Force -ErrorAction SilentlyContinue; Write-Host ($name + ': PID timing mismatch; stale PID file removed.'); exit 0 }; & taskkill.exe /PID $procId /T /F 2>$null | Out-Null; if($LASTEXITCODE -eq 0){ Write-Host ($name + ': stopped (PID ' + $procId + ').') } else { Write-Host ($name + ': process already stopped or could not be terminated.') }; Remove-Item -LiteralPath $pidFile -Force -ErrorAction SilentlyContinue; exit 0"

exit /b 0
