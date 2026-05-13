@echo off
echo ╔═══════════════════════════════════╗
echo ║   JARVIS - Instalador             ║
echo ╚═══════════════════════════════════╝
echo.

echo [1/3] Instalando dependencias Python...
pip install sounddevice numpy edge-tts requests pygame yt-dlp pywin32

echo.
echo [2/3] Instalando ffmpeg (necesario para descargar la musica)...
winget install --id Gyan.FFmpeg -e --silent
if %ERRORLEVEL% NEQ 0 (
    echo    ffmpeg ya instalado o no disponible via winget. Continando...
)

echo.
echo [3/3] Todo listo!
echo.
echo  Para iniciar Jarvis:        doble clic en  iniciar.bat
echo  Para que arranque con Windows: doble clic en  agregar_inicio_windows.bat
echo.
pause
