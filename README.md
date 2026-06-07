# Markitdown · Contexto para IA

Webapp local para convertir cualquier archivo a Markdown y armar contexto rápido para alimentar a tu modelo.

- **Documentos** (PDF, DOCX, XLSX, PPTX, HTML, TXT, CSV, imágenes, etc.) → [markitdown](https://github.com/microsoft/markitdown)
- **Audio y video** (MP3, WAV, M4A, MP4, MOV, MKV, …) → [whisper](https://github.com/openai/whisper) (transcripción)
- Drag and drop, conversión individual, **botón "Combinar"** que junta todo en un solo `.md`
- **Doble click** en un archivo de la lista → vuelve a convertirlo (útil si lo modificaste)
- **Doble click en `actualizar.command` / `actualizar.bat` / `actualizar.sh`** → sube tus cambios a GitHub sin abrir terminal

## Requisitos

- Python 3.10+
- `git` (para los scripts de actualizar)
- `ffmpeg` instalado y en el `PATH` (whisper lo necesita para audio/video)

En Mac: `brew install ffmpeg git`
En Ubuntu: `sudo apt install ffmpeg git python3-venv`
En Windows: instalá Python desde python.org marcando "Add to PATH" y ffmpeg desde [ffmpeg.org](https://ffmpeg.org/download.html).

## Arrancar la webapp

### Doble click (la forma fácil)

- **Mac:** doble click en `iniciar.command`
- **Windows:** doble click en `iniciar.bat`
- **Linux:** doble click en `iniciar.sh` (puede pedir "permitir ejecución")

La primera vez crea un entorno virtual `.venv/` e instala todo. Luego abre `http://127.0.0.1:8000` automáticamente.

### A mano

```bash
python3 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python -m uvicorn app:app --host 127.0.0.1 --port 8000
```

## Subir cambios a GitHub (doble click)

Después de modificar archivos:

- **Mac:** doble click en `actualizar.command`
- **Windows:** doble click en `actualizar.bat`
- **Linux:** doble click en `actualizar.sh`

El script te muestra qué cambió, te pide un mensaje de commit (ENTER usa la fecha) y hace `git add -A`, `git commit`, `git push -u origin <rama-actual>`.

> Necesitás tener `git` configurado con tus credenciales (SSH o credential helper). Si nunca lo hiciste, hacelo una vez en cualquier terminal con `git config --global user.name "Tu Nombre"` y `git config --global user.email "tu@email"`.

## Cómo usar la webapp

1. Arrastrá uno o varios archivos a la zona de drop (o hacé click para elegir).
2. Cada archivo se convierte automáticamente al subirlo.
3. **Click** en un archivo ya convertido → vista previa lateral.
4. **Doble click** en un archivo → vuelve a convertirlo (si modificaste el original, primero borralo y volvelo a soltar, ya que el original queda en `uploads/` con un id único).
5. **Combinar en un solo MD** → arma `output/_combined.md` con todo el contexto.
6. **Descargar combinado** → te lo bajás listo para pegar en tu chat de IA.

## Modelo de Whisper

Por defecto usa `base`. Si querés otra calidad, exportá la variable antes de iniciar:

```bash
WHISPER_MODEL=small python -m uvicorn app:app
# opciones: tiny, base, small, medium, large
```

## Estructura

```
app.py              Backend FastAPI
static/             Frontend (HTML + CSS + JS)
uploads/            Archivos originales (creada al usar)
output/             Markdowns generados (creada al usar)
index.json          Índice interno de archivos
iniciar.*           Doble click para arrancar la app
actualizar.*        Doble click para pushear a GitHub
```

## Licencia

MIT.
