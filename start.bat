@echo off
cd /d "%~dp0"
uv run --project backend python scripts\run.py %*
exit /b %ERRORLEVEL%
