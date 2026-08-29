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

# Detectar GPU NVIDIA (Linux con drivers NVIDIA). En Mac esto no existe
# y se usa CPU sin preguntar nada.
HAS_NVIDIA=0
if command -v nvidia-smi >/dev/null 2>&1; then
  HAS_NVIDIA=1
  echo "GPU NVIDIA detectada: Whisper va a usar GPU automaticamente."
else
  echo "No se detecto GPU NVIDIA: Whisper va a usar CPU."
fi

ensure_torch_device() {
  if [ "$HAS_NVIDIA" = "1" ]; then
    if ! python -c "import torch,sys; sys.exit(0 if torch.cuda.is_available() else 1)" 2>/dev/null; then
      echo "Instalando PyTorch con soporte CUDA (2-3 GB, puede tardar)..."
      pip uninstall -y torch >/dev/null 2>&1 || true
      if ! pip install torch --index-url https://download.pytorch.org/whl/cu121; then
        echo "AVISO: fallo la instalacion CUDA. Sigo con CPU como respaldo."
        pip install torch
      fi
    else
      echo "PyTorch ya esta configurado para usar GPU."
    fi
  else
    if ! python -c "import torch" 2>/dev/null; then
      echo "Instalando PyTorch..."
      pip install torch
    fi
  fi
}

if [ -f ".venv/.installed" ]; then
  ensure_torch_device
else
  echo "Instalando dependencias (puede tardar varios minutos la primera vez)..."
  pip install --upgrade pip >/dev/null
  pip install "setuptools<81" wheel
  ensure_torch_device
  echo ""
  echo "Instalando openai-whisper..."
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
