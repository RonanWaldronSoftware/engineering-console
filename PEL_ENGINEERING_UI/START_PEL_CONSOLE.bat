@echo off
setlocal
cd /d "%~dp0"
if not exist "%~dp0PEL_CONSOLE\PEL_Engineering_Console.hta" (
  echo PEL Engineering Console files are missing.
  pause
  exit /b 1
)
start "PEL Engineering Console" mshta.exe "%~dp0PEL_CONSOLE\PEL_Engineering_Console.hta"
exit /b 0
