@echo off
rem Instala/configura a Mesa neste PC. "Instalar.bat --chaves" so troca as chaves do Spotify/Discord.
cd /d "%~dp0"
title Mesa - instalar
chcp 65001 >nul
where py >nul 2>nul
if %errorlevel%==0 (
  py -3 instalar.py %*
) else (
  where python >nul 2>nul || (echo Python nao encontrado. Instale em https://www.python.org/downloads/ marcando "Add python.exe to PATH". & pause & exit /b 1)
  python instalar.py %*
)
pause
