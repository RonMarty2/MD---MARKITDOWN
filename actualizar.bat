@echo off
setlocal EnableDelayedExpansion
title Markitdown - Actualizar GitHub
cd /d "%~dp0"

echo.
echo ============================================
echo   Actualizando GitHub desde esta carpeta
echo ============================================
echo.
echo Carpeta: %CD%
echo.

where git >nul 2>nul
if errorlevel 1 (
  echo ERROR: no encontre git en el PATH.
  echo Instalalo desde https://git-scm.com/download/win
  pause
  exit /b 1
)

if not exist ".git" (
  echo ERROR: esta carpeta no es un repositorio git.
  pause
  exit /b 1
)

for /f "tokens=*" %%i in ('git rev-parse --abbrev-ref HEAD') do set "BRANCH=%%i"

if "!BRANCH!"=="" (
  echo ERROR: no estas en una rama.
  pause
  exit /b 1
)
if "!BRANCH!"=="HEAD" (
  echo ERROR: estas en estado detached HEAD. Hace git checkout primero.
  pause
  exit /b 1
)

echo Rama actual: !BRANCH!
echo.
echo Cambios pendientes:
git status --short
echo.

set "HASCHANGES="
for /f %%i in ('git status --porcelain') do set "HASCHANGES=1"

if defined HASCHANGES (
  set "MSG="
  set /p "MSG=Mensaje del commit [ENTER usa fecha actual]: "
  if "!MSG!"=="" set "MSG=update %DATE% %TIME%"
  echo.
  echo ^>^> git add -A
  git add -A
  echo ^>^> git commit -m "!MSG!"
  git commit -m "!MSG!"
) else (
  echo No hay cambios locales. Igual probamos push por si hay commits no publicados.
)

echo.
echo ^>^> git push -u origin !BRANCH!
git push -u origin "!BRANCH!"
if errorlevel 1 (
  echo.
  echo ERROR: el push fallo. Revisa el mensaje arriba.
) else (
  echo.
  echo Listo. Cambios publicados en GitHub.
)

echo.
pause
endlocal
