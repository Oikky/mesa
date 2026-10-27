@echo off
rem Checa o codigo da Mesa sem ligar nada: lint do Python (ruff), testes (pytest) e lint do JS (ESLint).
rem Nao toca som, nao mexe no config\ de verdade, nao precisa do servidor ligado.
rem Primeira vez: instala as ferramentas de dev (ruff, pytest e, se tiver Node, o ESLint).
cd /d "%~dp0"
title Mesa - checar
chcp 65001 >nul
set PY=.venv\Scripts\python.exe
if not exist "%PY%" (
  echo Falta o .venv: rode o Instalar.bat primeiro.
  exit /b 1
)
"%PY%" -m ruff --version >nul 2>&1 || "%PY%" -m pip install -q -r requirements-dev.txt
set FALHOU=0

echo == Python: ruff
"%PY%" -m ruff check . || set FALHOU=1

echo == Python: testes
"%PY%" -m pytest -q || set FALHOU=1

echo == JS: ESLint
where npm >nul 2>&1
if errorlevel 1 (
  echo Sem Node instalado: pulando o ESLint.
) else (
  if not exist "node_modules\.bin\eslint.cmd" call npm install --no-fund --no-audit --silent
  call npx eslint web extension || set FALHOU=1
)

echo.
if "%FALHOU%"=="1" (
  echo ALGO FALHOU - ver acima.
  exit /b 1
)
echo Tudo certo.
