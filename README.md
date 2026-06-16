# Markitdown · Contexto para IA

Webapp local para convertir cualquier archivo a Markdown y armar contexto rápido para alimentar a tu modelo.

- **Documentos** (PDF, DOCX, XLSX, PPTX, HTML, TXT, CSV, imágenes…) → [markitdown](https://github.com/microsoft/markitdown)
- **Audio y video** (MP3, WAV, M4A, MP4, MOV, MKV…) → [whisper](https://github.com/openai/whisper)
- **URLs / artículos** → markitdown
- **YouTube** → yt-dlp + whisper

## Funcionalidades

### Contexto para IA
- **Conteo de tokens** por archivo y total (usa `cl100k_base` de tiktoken).
- **Copiar al portapapeles** por archivo y del combinado, listo para pegar en el chat.
- **Combinar selectivo y ordenable**: marcá checkboxes y arrastrá filas para definir el orden del contexto.
- **Preview renderizado** del Markdown con toggle "Render / Crudo".

### Multimedia / Whisper
- Selector de modelo Whisper (`tiny`/`base`/`small`/`medium`/`large`).
- Idioma del audio (auto o fijo) y opción "traducir a inglés".
- Ingesta por URL pegando un link (web, artículo o YouTube).
- Conversión en background con barra de progreso y tiempo transcurrido.
- Health check: indicadores en la barra superior y panel de ajustes para `ffmpeg`, `ffprobe`, `whisper`, `markitdown`, `yt-dlp`, `tiktoken`.

### Comodidad / Visual
- **Tema claro / oscuro** (toggle, persistido en el navegador).
- Iconos por tipo de archivo (PDF, audio, video, imagen, YouTube, URL…).
- Buscar / filtrar la lista.
- Seleccionar todo y borrar en bloque.
- **Atajos de teclado**: `/` busca, `Ctrl/Cmd+A` selecciona todo, `Del` borra, `Esc` cierra panel, pegar URL con `Ctrl/Cmd+V` la importa.
- **Carpeta watch**: configurá una carpeta y todo lo nuevo que pongas ahí se convierte automáticamente.
- Drag global: soltar archivos en cualquier parte de la ventana.
- **Doble click** en un archivo → re-convierte.
- **Doble click** en `actualizar.command` / `.bat` / `.sh` → sube tus cambios a GitHub.

## Requisitos

- Python 3.10+
- `git` (para los scripts de actualizar)
- `ffmpeg` y `ffprobe` en el `PATH` (whisper / duración real)

**Mac:** `brew install ffmpeg git`
**Ubuntu:** `sudo apt install ffmpeg git python3-venv`
**Windows:** Python desde [python.org](https://python.org) marcando "Add to PATH" + ffmpeg desde [ffmpeg.org](https://ffmpeg.org/download.html).

## Arrancar

### Windows sin consola

En Windows, usa doble click:

- `INICIAR_MARKITDOWN.vbs` arranca la app en segundo plano y abre el navegador.
- `ACTUALIZAR_MARKITDOWN.vbs` hace commit y push a GitHub con mensaje automatico.
- `DETENER_MARKITDOWN.vbs` detiene el servidor iniciado en segundo plano.

Los logs quedan en `logs/`. La primera ejecucion puede tardar varios minutos porque crea `.venv/` e instala dependencias.

### Doble click (fácil)
- **Mac:** `iniciar.command`
- **Windows:** `iniciar.bat`
- **Linux:** `iniciar.sh`

La primera vez crea `.venv/`, instala dependencias y abre `http://127.0.0.1:8000`.

### A mano
```bash
python3 -m venv .venv
source .venv/bin/activate            # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python -m uvicorn app:app --host 127.0.0.1 --port 8000
```

## Subir cambios a GitHub (doble click)

- **Mac:** `actualizar.command`
- **Windows:** `actualizar.bat`
- **Linux:** `actualizar.sh`

El script muestra los cambios, pide mensaje de commit (ENTER usa fecha) y hace `git add -A && git commit && git push -u origin <rama-actual>`.

> Necesitás `git` configurado con tus credenciales. Una vez: `git config --global user.name "Tu Nombre"` y `git config --global user.email "tu@email"`.

## Flujo típico

1. Arrancás con `iniciar.command` y se abre el navegador.
2. Soltás PDFs / audios / videos, o pegás URLs (incluyendo YouTube).
3. Cada item se convierte solo en background. Ves el progreso y los tokens estimados.
4. Reordenás arrastrando, marcás los que querés incluir.
5. **Combinar seleccionados** → **Copiar combinado** → pegás en tu chat de IA.

## Estructura

```
app.py              Backend FastAPI (rutas + jobs + watcher)
static/             Frontend (HTML + CSS + JS)
uploads/            Archivos originales (gitignored)
output/             Markdowns generados (gitignored)
index.json          Índice interno de archivos (gitignored)
settings.json       Ajustes persistidos (gitignored)
iniciar.*           Doble click para arrancar la app
actualizar.*        Doble click para pushear a GitHub
```

## Variables de entorno

- `WHISPER_MODEL=base` — modelo Whisper por defecto (también ajustable en la UI).
- `HOST=127.0.0.1` y `PORT=8000` — bind del servidor.

## Notas

- Los modelos de Whisper se descargan la primera vez que los usás (cachean en `~/.cache/whisper`).
- `large` es más preciso pero requiere bastante RAM/VRAM. Si tu máquina sufre, usá `small` o `medium`.
- La transcripción de YouTube respeta los términos de la plataforma — usalo con contenido propio o permitido.

## Licencia

MIT.
