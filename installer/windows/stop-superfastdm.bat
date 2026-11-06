@echo off
REM Encerra o servidor do SuperFast DM (porta 7860)
set "FOUND="
for /f "tokens=5" %%a in ('netstat -ano ^| findstr :7860 ^| findstr LISTENING') do (
    taskkill /F /PID %%a >nul 2>nul
    set "FOUND=1"
)
if defined FOUND (
    echo Servidor do SuperFast DM encerrado.
) else (
    echo Nenhum servidor do SuperFast DM em execucao.
)
timeout /t 2 >nul
