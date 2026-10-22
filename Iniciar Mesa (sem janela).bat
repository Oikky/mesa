@echo off
rem Liga a Mesa escondida, igual quando o Windows inicia. Log em logs\mesa.log.
cd /d "%~dp0"
start "" ".venv\Scripts\pythonw.exe" "%~dp0server\app.py"
