import hashlib
import json
import os
import shutil
import threading
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException, UploadFile, File
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

BASE_DIR = Path(__file__).parent.resolve()
UPLOAD_DIR = BASE_DIR / "uploads"
OUTPUT_DIR = BASE_DIR / "output"
STATIC_DIR = BASE_DIR / "static"
INDEX_FILE = BASE_DIR / "index.json"

UPLOAD_DIR.mkdir(exist_ok=True)
OUTPUT_DIR.mkdir(exist_ok=True)

AUDIO_EXTS = {".mp3", ".wav", ".m4a", ".ogg", ".flac", ".aac", ".wma", ".opus"}
VIDEO_EXTS = {".mp4", ".mov", ".mkv", ".webm", ".avi", ".flv", ".wmv", ".m4v"}

_index_lock = threading.Lock()
_whisper_model = None
_whisper_lock = threading.Lock()


def load_index() -> dict:
    if not INDEX_FILE.exists():
        return {}
    try:
        with open(INDEX_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def save_index(index: dict) -> None:
    with _index_lock:
        with open(INDEX_FILE, "w", encoding="utf-8") as f:
            json.dump(index, f, ensure_ascii=False, indent=2)


def update_entry(file_id: str, **kwargs) -> dict:
    with _index_lock:
        index = load_index()
        entry = index.get(file_id, {})
        entry.update(kwargs)
        index[file_id] = entry
        with open(INDEX_FILE, "w", encoding="utf-8") as f:
            json.dump(index, f, ensure_ascii=False, indent=2)
        return entry


def get_whisper_model(model_name: str = "base"):
    global _whisper_model
    with _whisper_lock:
        if _whisper_model is None:
            import whisper
            _whisper_model = whisper.load_model(model_name)
        return _whisper_model


def is_media(filename: str) -> bool:
    ext = Path(filename).suffix.lower()
    return ext in AUDIO_EXTS or ext in VIDEO_EXTS


def file_hash(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def transcribe_media(src: Path) -> str:
    model = get_whisper_model(os.environ.get("WHISPER_MODEL", "base"))
    result = model.transcribe(str(src), verbose=False)
    text = result.get("text", "").strip()
    segments = result.get("segments", []) or []
    lang = result.get("language", "?")
    lines = [
        f"# Transcripción: {src.name}",
        "",
        f"- **Archivo:** `{src.name}`",
        f"- **Idioma detectado:** `{lang}`",
        f"- **Duración (segmentos):** {len(segments)}",
        "",
        "## Texto",
        "",
        text or "_(sin texto reconocido)_",
    ]
    if segments:
        lines += ["", "## Segmentos con marcas de tiempo", ""]
        for seg in segments:
            start = seg.get("start", 0.0)
            end = seg.get("end", 0.0)
            seg_text = (seg.get("text") or "").strip()
            lines.append(f"- `[{start:7.2f} → {end:7.2f}]` {seg_text}")
    return "\n".join(lines) + "\n"


def convert_with_markitdown(src: Path) -> str:
    from markitdown import MarkItDown
    md = MarkItDown()
    result = md.convert(str(src))
    text = (getattr(result, "text_content", None) or "").strip()
    header = f"# {src.name}\n\n"
    return header + (text if text else "_(sin contenido reconocido)_") + "\n"


def perform_conversion(file_id: str) -> dict:
    index = load_index()
    entry = index.get(file_id)
    if not entry:
        raise HTTPException(status_code=404, detail="Archivo no encontrado")

    src = Path(entry["source_path"])
    if not src.exists():
        update_entry(file_id, status="error", error="Archivo origen no existe")
        raise HTTPException(status_code=404, detail="Archivo origen no existe")

    update_entry(file_id, status="processing", error=None)

    try:
        current_hash = file_hash(src)
        if is_media(src.name):
            md_text = transcribe_media(src)
            converter = "whisper"
        else:
            md_text = convert_with_markitdown(src)
            converter = "markitdown"

        out_path = OUTPUT_DIR / f"{file_id}.md"
        out_path.write_text(md_text, encoding="utf-8")

        updated = update_entry(
            file_id,
            status="done",
            converter=converter,
            output_path=str(out_path),
            hash=current_hash,
            converted_at=datetime.utcnow().isoformat() + "Z",
            size_md=len(md_text.encode("utf-8")),
            error=None,
        )
        return updated
    except Exception as e:
        update_entry(file_id, status="error", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


app = FastAPI(title="MD - Markitdown")


@app.get("/", response_class=HTMLResponse)
def root():
    index_html = STATIC_DIR / "index.html"
    return HTMLResponse(index_html.read_text(encoding="utf-8"))


@app.get("/api/files")
def list_files():
    index = load_index()
    items = []
    for fid, entry in index.items():
        items.append({
            "id": fid,
            "name": entry.get("name"),
            "status": entry.get("status"),
            "converter": entry.get("converter"),
            "uploaded_at": entry.get("uploaded_at"),
            "converted_at": entry.get("converted_at"),
            "size": entry.get("size"),
            "size_md": entry.get("size_md"),
            "error": entry.get("error"),
            "is_media": is_media(entry.get("name", "")),
        })
    items.sort(key=lambda x: x.get("uploaded_at") or "", reverse=True)
    return {"files": items}


@app.post("/api/upload")
async def upload_files(files: list[UploadFile] = File(...)):
    created = []
    index = load_index()
    for up in files:
        file_id = uuid.uuid4().hex
        safe_name = Path(up.filename).name
        stored = UPLOAD_DIR / f"{file_id}__{safe_name}"
        with open(stored, "wb") as out:
            shutil.copyfileobj(up.file, out)
        size = stored.stat().st_size
        entry = {
            "id": file_id,
            "name": safe_name,
            "source_path": str(stored),
            "size": size,
            "status": "pending",
            "uploaded_at": datetime.utcnow().isoformat() + "Z",
            "converter": None,
            "output_path": None,
            "converted_at": None,
            "hash": None,
            "error": None,
        }
        index[file_id] = entry
        created.append({"id": file_id, "name": safe_name, "size": size, "is_media": is_media(safe_name)})
    save_index(index)
    return {"created": created}


@app.post("/api/convert/{file_id}")
def convert(file_id: str):
    entry = perform_conversion(file_id)
    return {"ok": True, "file": entry}


@app.post("/api/convert-all")
def convert_all():
    index = load_index()
    results = []
    for fid, entry in index.items():
        if entry.get("status") != "done":
            try:
                perform_conversion(fid)
                results.append({"id": fid, "ok": True})
            except HTTPException as e:
                results.append({"id": fid, "ok": False, "error": e.detail})
    return {"results": results}


@app.get("/api/download/{file_id}")
def download_one(file_id: str):
    index = load_index()
    entry = index.get(file_id)
    if not entry or not entry.get("output_path"):
        raise HTTPException(status_code=404, detail="MD no disponible")
    out = Path(entry["output_path"])
    if not out.exists():
        raise HTTPException(status_code=404, detail="MD no encontrado")
    name = Path(entry["name"]).stem + ".md"
    return FileResponse(out, media_type="text/markdown", filename=name)


@app.get("/api/preview/{file_id}")
def preview(file_id: str):
    index = load_index()
    entry = index.get(file_id)
    if not entry or not entry.get("output_path"):
        raise HTTPException(status_code=404, detail="MD no disponible")
    out = Path(entry["output_path"])
    if not out.exists():
        raise HTTPException(status_code=404, detail="MD no encontrado")
    text = out.read_text(encoding="utf-8")
    return JSONResponse({"id": file_id, "name": entry["name"], "markdown": text})


@app.post("/api/combine")
def combine(only_ids: Optional[list[str]] = None):
    index = load_index()
    parts = []
    used = []
    for fid, entry in index.items():
        if entry.get("status") != "done":
            continue
        if only_ids and fid not in only_ids:
            continue
        out_path = Path(entry.get("output_path") or "")
        if not out_path.exists():
            continue
        parts.append(f"\n\n---\n\n<!-- Fuente: {entry['name']} -->\n\n" + out_path.read_text(encoding="utf-8"))
        used.append(entry["name"])
    if not parts:
        raise HTTPException(status_code=400, detail="No hay archivos convertidos para combinar")
    header = "# Contexto combinado\n\nArchivos incluidos:\n" + "\n".join(f"- {n}" for n in used)
    combined = header + "".join(parts)
    combined_path = OUTPUT_DIR / "_combined.md"
    combined_path.write_text(combined, encoding="utf-8")
    return {"ok": True, "count": len(used), "path": str(combined_path), "size": len(combined.encode("utf-8"))}


@app.get("/api/download-combined")
def download_combined():
    combined_path = OUTPUT_DIR / "_combined.md"
    if not combined_path.exists():
        raise HTTPException(status_code=404, detail="Aún no hay un combinado. Pulsá 'Combinar' primero.")
    return FileResponse(combined_path, media_type="text/markdown", filename="contexto-combinado.md")


@app.delete("/api/file/{file_id}")
def delete_file(file_id: str):
    with _index_lock:
        index = load_index()
        entry = index.pop(file_id, None)
        if entry:
            for key in ("source_path", "output_path"):
                p = entry.get(key)
                if p and Path(p).exists():
                    try:
                        Path(p).unlink()
                    except Exception:
                        pass
            with open(INDEX_FILE, "w", encoding="utf-8") as f:
                json.dump(index, f, ensure_ascii=False, indent=2)
    return {"ok": True}


@app.post("/api/clear")
def clear_all():
    with _index_lock:
        if INDEX_FILE.exists():
            INDEX_FILE.unlink()
        for d in (UPLOAD_DIR, OUTPUT_DIR):
            for p in d.iterdir():
                try:
                    p.unlink()
                except Exception:
                    pass
    return {"ok": True}


app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


if __name__ == "__main__":
    import uvicorn
    host = os.environ.get("HOST", "127.0.0.1")
    port = int(os.environ.get("PORT", "8000"))
    uvicorn.run("app:app", host=host, port=port, reload=False)
