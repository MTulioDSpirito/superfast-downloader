@echo off
REM ============================================================
REM  SuperFast DM - launcher (Windows)
REM  Sobe o servidor local e abre o navegador em 127.0.0.1:7860
REM  Para encerrar: feche esta janela  OU  rode stop-superfastdm.bat
REM ============================================================
setlocal
title SuperFast DM
set "URL=http://127.0.0.1:7860/"

REM ja esta rodando? so abre o navegador
curl -s --max-time 2 "%URL%health" 2>nul | findstr /i "true" >nul
if not errorlevel 1 (
    echo O servidor ja esta no ar.
    start "" "%URL%"
    exit /b 0
)

REM acha o python
set "PY="
where python >nul 2>nul && set "PY=python"
if not defined PY ( where python3 >nul 2>nul && set "PY=python3" )
if not defined PY (
    echo.
    echo Python 3 nao encontrado.
    echo Instale em https://www.python.org/downloads/
    echo e marque "Add python.exe to PATH" durante a instalacao.
    echo.
    pause
    exit /b 1
)

REM local do server.py: instalado (mesma pasta) OU portavel (repo: ..\..\app)
set "SRV="
if exist "%~dp0server.py" set "SRV=%~dp0server.py"
if not defined SRV if exist "%~dp0..\..\app\server.py" set "SRV=%~dp0..\..\app\server.py"
if not defined SRV (
    echo server.py nao encontrado proximo a este lancador.
    pause
    exit /b 1
)

set "SFD_OPEN=1"
set "SFD_DEST=%USERPROFILE%\Downloads\superfast-dm"
set "SFD_DATA=%USERPROFILE%\.superfast-dm"

echo Iniciando o servidor do SuperFast DM...
echo UI: %URL%
echo (feche esta janela para encerrar)
echo.
"%PY%" "%SRV%"
endlocal
