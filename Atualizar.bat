@echo off
rem Baixa a versao nova da Mesa (git pull), atualiza as dependencias e reinicia o servidor.
rem Suas configuracoes (.env, config\pads.json, channels.json, certificados) nao sao tocadas.
cd /d "%~dp0"
title Mesa - atualizar
chcp 65001 >nul
if not exist ".venv\Scripts\python.exe" (
  echo Primeira vez: rodando o instalador.
  call Instalar.bat
  exit /b
)
for /f %%h in ('git rev-parse HEAD') do set OLD=%%h
git pull --ff-only
if errorlevel 1 (
  echo.
  echo Nao deu pra atualizar ^(veja a mensagem acima^).
  if not "%1"=="--silencioso" pause
  exit /b 1
)
".venv\Scripts\python.exe" -m pip install -q --disable-pip-version-check -r requirements.txt
git diff --quiet %OLD% HEAD -- extension
if errorlevel 1 (
  echo.
  echo A EXTENSAO MUDOU: abra edge://extensions e clique em recarregar no card da Mesa, depois F5 nas abas.
  echo extensao > logs\extensao-mudou.txt
)
call "Parar Mesa.bat" >nul
start "" ".venv\Scripts\pythonw.exe" "%~dp0server\app.py"
echo.
echo Mesa atualizada e reiniciada.
if not "%1"=="--silencioso" pause
