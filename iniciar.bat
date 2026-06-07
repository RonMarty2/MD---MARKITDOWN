@echo off
REM Doble click para iniciar la webapp en localhost:8000
cd /d "%~dp0"

echo.
echo ============================================
echo   Iniciando Markitdown - Contexto para IA
echo ============================================
echo.

where python >nul 2>nul
if errorlevel 1 (
  echo ERROR: no encontre Python. Instalalo desde python.org
  pause
  exit /b 1
)

if not exist ".venv" (
  echo Creando entorno virtual (.venv)...
  python -m venv .venv
)

call .venv\Scripts\activate.bat

echo Instalando dependencias (puede tardar la primera vez)...
python -m pip install --upgrade pip >nul
python -m pip install -r requirements.txt

echo.
echo Abriendo http://127.0.0.1:8000 ...
start "" http://127.0.0.1:8000

python -m uvicorn app:app --host 127.0.0.1 --port 8000
