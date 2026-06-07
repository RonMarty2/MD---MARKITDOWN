#!/usr/bin/env bash
# Doble click: sube los cambios locales a GitHub.
# Compatible con macOS (también funciona en Linux con bash).

set -e
cd "$(dirname "$0")"

echo ""
echo "============================================"
echo "  Actualizando GitHub desde esta carpeta"
echo "============================================"
echo ""
echo "Carpeta: $(pwd)"
echo ""

if ! command -v git >/dev/null 2>&1; then
  echo "ERROR: git no esta instalado."
  read -p "Presiona ENTER para cerrar..."
  exit 1
fi

if [ ! -d ".git" ]; then
  echo "ERROR: esta carpeta no es un repositorio git."
  read -p "Presiona ENTER para cerrar..."
  exit 1
fi

BRANCH=$(git rev-parse --abbrev-ref HEAD 2>/dev/null || echo "")
if [ -z "$BRANCH" ] || [ "$BRANCH" = "HEAD" ]; then
  echo "ERROR: no estas en una rama. Hace 'git checkout <rama>' primero."
  read -p "Presiona ENTER para cerrar..."
  exit 1
fi

echo "Rama actual: $BRANCH"
echo ""
echo "Cambios pendientes:"
git status --short
echo ""

CHANGES=$(git status --porcelain)
if [ -z "$CHANGES" ]; then
  echo "No hay cambios locales. Igual probamos push por si hay commits no publicados."
else
  read -p "Mensaje del commit (ENTER usa fecha actual): " MSG
  if [ -z "$MSG" ]; then
    MSG="update $(date -u '+%Y-%m-%d %H:%M:%S') UTC"
  fi
  echo ""
  echo ">> git add -A"
  git add -A
  echo ">> git commit -m \"$MSG\""
  git commit -m "$MSG" || true
fi

echo ""
echo ">> git push -u origin $BRANCH"
if git push -u origin "$BRANCH"; then
  echo ""
  echo "Listo. Cambios publicados en GitHub."
else
  echo ""
  echo "ERROR: el push fallo. Revisa el mensaje arriba."
fi

echo ""
read -p "Presiona ENTER para cerrar..."
