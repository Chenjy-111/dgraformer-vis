@echo off
setlocal
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0Start-DGraInsight-Audit.ps1" %*
if errorlevel 1 (
  echo.
  echo DGraInsight exited with an error. Review the messages above.
)
echo.
pause
