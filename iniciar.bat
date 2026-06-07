@echo off
setlocal EnableDelayedExpansion
title Markitdown - Iniciar
cd /d "%~dp0"

echo.
echo ============================================
echo   Markitdown - Contexto para IA
echo ============================================
echo.
echo Carpeta: %CD%
echo.

REM Detectar Python: primero "python", despues "py"
set "PY="
where python >nul 2>nul && set "PY=python"
if not defined PY (
  where py >nul 2>nul && set "PY=py -3"
)

if not defined PY (
  echo ERROR: no encontre Python en el PATH.
  echo.
  echo Instalalo desde https://python.org marcando "Add Python to PATH".
  echo Despues cerra esta ventana y volve a hacer doble click.
  echo.
  pause
  exit /b 1
)

echo Python detectado: %PY%
echo.

REM Crear venv si no existe
if not exist ".venv\Scripts\activate.bat" (
  echo Creando entorno virtual .venv ...
  %PY% -m venv .venv
  if errorlevel 1 (
    echo ERROR: no pude crear el entorno virtual.
    pause
    exit /b 1
  )
)

echo Activando entorno virtual...
call ".venv\Scripts\activate.bat"
if errorlevel 1 (
  echo ERROR: no pude activar el entorno virtual.
  pause
  exit /b 1
)

REM Marcador para saltearse la instalacion en arranques posteriores
if exist ".venv\.installed" goto :run

echo.
echo Instalando dependencias - puede tardar varios minutos la primera vez...
echo.

python -m pip install --upgrade pip
python -m pip install "setuptools<81" wheel
if errorlevel 1 (
  echo ERROR: fallo la instalacion de setuptools/wheel.
  pause
  exit /b 1
)

echo.
echo Instalando openai-whisper - puede descargar torch ^(grande^)...
python -m pip install --no-build-isolation openai-whisper==20240930
if errorlevel 1 (
  echo ERROR: fallo la instalacion de openai-whisper.
  pause
  exit /b 1
)

echo.
echo Instalando el resto...
python -m pip install -r requirements.txt
if errorlevel 1 (
  echo.
  echo ERROR: fallo la instalacion de dependencias.
  echo Revisa los mensajes arriba.
  pause
  exit /b 1
)

echo done > ".venv\.installed"

:run
echo.
echo ============================================
echo   Servidor corriendo en http://127.0.0.1:8000
echo   Cerra esta ventana para detenerlo.
echo ============================================
echo.

start "" http://127.0.0.1:8000
python -m uvicorn app:app --host 127.0.0.1 --port 8000

echo.
echo === El servidor se detuvo ===
pause
endlocal
