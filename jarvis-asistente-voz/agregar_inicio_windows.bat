@echo off
set "STARTUP=%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup"
set "VBS_SRC=%~dp0iniciar_oculto.vbs"
set "VBS_DST=%STARTUP%\jarvis.vbs"

copy "%VBS_SRC%" "%VBS_DST%" >nul
if %ERRORLEVEL% EQU 0 (
    echo [OK] Jarvis añadido al inicio de Windows.
    echo      Se activara automaticamente en el proximo arranque.
) else (
    echo [ERROR] No se pudo copiar. Ejecuta como administrador.
)
echo.
pause
