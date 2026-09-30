@echo off
rem Punto de entrada: sync de Canvas -> calendario -> temario -> guia.
rem Uso: estudiar.bat [--curso "Ramo"] [--sin-descarga] [--solo-sync] [--dry-run]
chcp 65001 >nul
set PYTHONUTF8=1
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
    echo No encuentro el entorno .venv en %~dp0
    echo Crealo con:  python -m venv .venv  y  .venv\Scripts\python -m pip install -r requirements.txt
    pause
    exit /b 1
)
".venv\Scripts\python.exe" src\main.py %*
echo.
pause
