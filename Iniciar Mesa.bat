@echo off
cd /d "%~dp0"
title Mesa
".venv\Scripts\python.exe" server\app.py
pause
