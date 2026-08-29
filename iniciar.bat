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

REM Detectar GPU NVIDIA (nvidia-smi lo instala el driver, no hace falta CUDA toolkit aparte)
set "HAS_NVIDIA=0"
where nvidia-smi >nul 2>nul && set "HAS_NVIDIA=1"
if "%HAS_NVIDIA%"=="1" (
  echo GPU NVIDIA detectada: Whisper va a usar GPU automaticamente.
) else (
  echo No se detecto GPU NVIDIA: Whisper va a usar CPU.
)
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

REM Si ya se instalo antes, solo confirmamos que el torch instalado matchee
REM la GPU detectada (por si la vez pasada quedo la version CPU) y arrancamos.
if exist ".venv\.installed" (
  call :ensure_torch_device
  goto :run
)

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

call :ensure_torch_device

echo.
echo Instalando openai-whisper...
python -m pip install --no-build-isolation openai-whisper==20240930
if errorlevel 1 (
  echo ERROR: fallo la instalacion de openai-whisper.
  pause
  exit /b 1
)

echo.
echo Instalando el resto de las dependencias...
python -m pip install -r requirements.txt
if errorlevel 1 (
  echo.
  echo ERROR: fallo la instalacion de dependencias.
  echo Revisa los mensajes arriba.
  pause
  exit /b 1
)

echo done > ".venv\.installed"
goto :run

REM ---------------------------------------------------------------
REM Se asegura de que PyTorch use la GPU si hay una NVIDIA presente.
REM Si no hay GPU, solo garantiza que exista una version CPU.
REM No pregunta nada: decide solo en base a lo que detecto arriba.
REM ---------------------------------------------------------------
:ensure_torch_device
echo Verificando PyTorch / GPU...
if "%HAS_NVIDIA%"=="1" (
  python -c "import torch,sys;sys.exit(0 if torch.cuda.is_available() else 1)" 2>nul
  if errorlevel 1 (
    echo Instalando PyTorch con soporte CUDA - unos 2-3 GB, puede tardar...
    python -m pip uninstall -y torch >nul 2>nul
    python -m pip install torch --index-url https://download.pytorch.org/whl/cu121
    if errorlevel 1 (
      echo AVISO: fallo la instalacion de la version CUDA. Sigo con CPU como respaldo.
      python -m pip install torch
    )
  ) else (
    echo PyTorch ya esta configurado para usar GPU.
  )
) else (
  python -c "import torch" 2>nul
  if errorlevel 1 (
    echo Instalando PyTorch ^(CPU^)...
    python -m pip install torch
  )
)
exit /b 0

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
