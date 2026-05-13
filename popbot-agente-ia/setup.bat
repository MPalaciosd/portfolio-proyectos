@echo off
chcp 65001 >nul
title Barbershop Agent — Setup Automatizado

echo.
echo  ╔══════════════════════════════════════════════════════╗
echo  ║   🔱 BARBERSHOP AGENT — Instalando Setup...         ║
echo  ╚══════════════════════════════════════════════════════╝
echo.

cd /d "%~dp0"

:: Instalar dependencias del setup
echo  [1/3] Instalando dependencias del setup...
cd setup
call npm install --silent
if errorlevel 1 (
    echo  ❌ Error al instalar dependencias
    pause
    exit /b 1
)

:: Instalar browsers de Playwright
echo  [2/3] Instalando navegador Chromium para automatización...
call npx playwright install chromium --with-deps 2>nul || call npx playwright install chromium
if errorlevel 1 (
    echo  ⚠️  No se pudo instalar Chromium automáticamente.
    echo      El script intentará usar el Chrome que tengas instalado.
)

:: Ejecutar el setup
echo  [3/3] Iniciando setup automatizado...
echo.
cd /d "%~dp0\setup"
node index.js

pause
