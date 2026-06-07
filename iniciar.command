#!/usr/bin/env bash
# Doble click para iniciar la webapp de Markitdown en localhost:8000.
set -e
cd "$(dirname "$0")"

echo ""
echo "============================================"
echo "  Iniciando Markitdown - Contexto para IA"
echo "============================================"
echo ""

PY=""
for cand in python3 python; do
  if command -v $cand >/dev/null 2>&1; then PY=$cand; break; fi
done
if [ -z "$PY" ]; then
  echo "ERROR: no encontre Python 3. Instalalo desde python.org y volve a intentar."
  read -p "Presiona ENTER para cerrar..."
  exit 1
fi

if [ ! -d ".venv" ]; then
  echo "Creando entorno virtual (.venv)..."
  $PY -m venv .venv
fi

# shellcheck disable=SC1091
source .venv/bin/activate

if [ ! -f ".venv/.installed" ]; then
  echo "Instalando dependencias (puede tardar varios minutos la primera vez)..."
  pip install --upgrade pip >/dev/null
  pip install "setuptools<81" wheel
  echo ""
  echo "Instalando openai-whisper (puede descargar torch, es grande)..."
  pip install --no-build-isolation openai-whisper==20240930
  echo ""
  echo "Instalando el resto..."
  pip install -r requirements.txt
  touch .venv/.installed
fi

echo ""
echo "Abriendo http://127.0.0.1:8000 ..."
( sleep 1.5 && (open "http://127.0.0.1:8000" 2>/dev/null || xdg-open "http://127.0.0.1:8000" 2>/dev/null || true) ) &

python -m uvicorn app:app --host 127.0.0.1 --port 8000
