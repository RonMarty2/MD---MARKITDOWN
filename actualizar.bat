@echo off
REM Doble click en Windows: sube los cambios locales a GitHub.
setlocal enabledelayedexpansion
cd /d "%~dp0"

echo.
echo ============================================
echo   Actualizando GitHub desde esta carpeta
echo ============================================
echo.
echo Carpeta: %cd%
echo.

where git >nul 2>nul
if errorlevel 1 (
  echo ERROR: git no esta instalado.
  pause
  exit /b 1
)

if not exist ".git" (
  echo ERROR: esta carpeta no es un repositorio git.
  pause
  exit /b 1
)

for /f "tokens=*" %%i in ('git rev-parse --abbrev-ref HEAD') do set BRANCH=%%i
if "!BRANCH!"=="" (
  echo ERROR: no estas en una rama.
  pause
  exit /b 1
)
if "!BRANCH!"=="HEAD" (
  echo ERROR: no estas en una rama.
  pause
  exit /b 1
)

echo Rama actual: !BRANCH!
echo.
echo Cambios pendientes:
git status --short
echo.

for /f %%i in ('git status --porcelain') do set HASCHANGES=1

if defined HASCHANGES (
  set /p MSG=Mensaje del commit (ENTER usa fecha actual):
  if "!MSG!"=="" set MSG=update %DATE% %TIME%
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
git push -u origin !BRANCH!
if errorlevel 1 (
  echo.
  echo ERROR: el push fallo.
) else (
  echo.
  echo Listo. Cambios publicados en GitHub.
)

echo.
pause
endlocal
