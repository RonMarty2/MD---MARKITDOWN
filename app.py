import hashlib
import json
import mimetypes
import os
import re
import shutil
import subprocess
import tempfile
import threading
import time
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse

from fastapi import FastAPI, HTTPException, UploadFile, File
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

BASE_DIR = Path(__file__).parent.resolve()
UPLOAD_DIR = BASE_DIR / "uploads"
OUTPUT_DIR = BASE_DIR / "output"
STATIC_DIR = BASE_DIR / "static"
INDEX_FILE = BASE_DIR / "index.json"
SETTINGS_FILE = BASE_DIR / "settings.json"

UPLOAD_DIR.mkdir(exist_ok=True)
OUTPUT_DIR.mkdir(exist_ok=True)

AUDIO_EXTS = {".mp3", ".wav", ".m4a", ".ogg", ".flac", ".aac", ".wma", ".opus"}
VIDEO_EXTS = {".mp4", ".mov", ".mkv", ".webm", ".avi", ".flv", ".wmv", ".m4v"}

DEFAULT_SETTINGS = {
    "whisper_model": os.environ.get("WHISPER_MODEL", "base"),
    "whisper_language": None,
    "whisper_translate": False,
    "watch_folder": None,
    "watch_enabled": False,
    "order": [],
}

_index_lock = threading.Lock()
_settings_lock = threading.Lock()
_whisper_locks: dict[str, threading.Lock] = {}
_whisper_models: dict[str, object] = {}
_watch_thread: Optional[threading.Thread] = None
_watch_stop = threading.Event()
_watch_seen: set[str] = set()


def load_json(path: Path, default):
    if not path.exists():
        return default
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default


def save_json(path: Path, data, lock: threading.Lock):
    with lock:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)


def load_index() -> dict:
    return load_json(INDEX_FILE, {})


def save_index(index: dict) -> None:
    save_json(INDEX_FILE, index, _index_lock)


def update_entry(file_id: str, **kwargs) -> dict:
    with _index_lock:
        index = load_json(INDEX_FILE, {})
        entry = index.get(file_id, {})
        entry.update(kwargs)
        index[file_id] = entry
        with open(INDEX_FILE, "w", encoding="utf-8") as f:
            json.dump(index, f, ensure_ascii=False, indent=2)
        return entry


def load_settings() -> dict:
    base = dict(DEFAULT_SETTINGS)
    base.update(load_json(SETTINGS_FILE, {}))
    return base


def save_settings(data: dict) -> None:
    save_json(SETTINGS_FILE, data, _settings_lock)


def get_whisper_model(model_name: str):
    if model_name not in _whisper_locks:
        _whisper_locks[model_name] = threading.Lock()
    with _whisper_locks[model_name]:
        if model_name not in _whisper_models:
            import whisper
            _whisper_models[model_name] = whisper.load_model(model_name)
        return _whisper_models[model_name]


def is_audio(name: str) -> bool: return Path(name).suffix.lower() in AUDIO_EXTS
def is_video(name: str) -> bool: return Path(name).suffix.lower() in VIDEO_EXTS
def is_media(name: str) -> bool: return is_audio(name) or is_video(name)


def file_hash(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def count_tokens(text: str) -> int:
    try:
        import tiktoken
        enc = tiktoken.get_encoding("cl100k_base")
        return len(enc.encode(text, disallowed_special=()))
    except Exception:
        return max(1, len(text) // 4)


def media_duration(path: Path) -> Optional[float]:
    try:
        out = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration",
             "-of", "default=noprint_wrappers=1:nokey=1", str(path)],
            capture_output=True, text=True, timeout=15,
        )
        if out.returncode == 0:
            return float(out.stdout.strip())
    except Exception:
        pass
    return None


def transcribe_media(src: Path, file_id: str, settings: dict) -> str:
    model_name = settings.get("whisper_model") or "base"
    language = settings.get("whisper_language") or None
    translate = bool(settings.get("whisper_translate"))
    duration = media_duration(src)
    if duration:
        update_entry(file_id, duration_sec=duration)

    model = get_whisper_model(model_name)

    started = time.time()
    stop_heartbeat = threading.Event()

    def heartbeat():
        while not stop_heartbeat.is_set():
            elapsed = time.time() - started
            progress = None
            if duration:
                progress = min(0.95, elapsed / max(duration, 0.001))
            update_entry(file_id, elapsed_sec=elapsed, progress=progress)
            stop_heartbeat.wait(1.0)

    hb = threading.Thread(target=heartbeat, daemon=True)
    hb.start()

    try:
        kwargs = dict(verbose=False)
        if language:
            kwargs["language"] = language
        if translate:
            kwargs["task"] = "translate"
        result = model.transcribe(str(src), **kwargs)
    finally:
        stop_heartbeat.set()
        hb.join(timeout=2)

    text = (result.get("text") or "").strip()
    segments = result.get("segments") or []
    lang = result.get("language", "?")
    lines = [
        f"# Transcripción: {src.name}",
        "",
        f"- **Archivo:** `{src.name}`",
        f"- **Idioma:** `{lang}`" + (" (traducido a inglés)" if translate else ""),
        f"- **Modelo Whisper:** `{model_name}`",
        f"- **Duración:** {duration:.1f}s" if duration else "- **Duración:** (desconocida)",
        f"- **Segmentos:** {len(segments)}",
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


def convert_url_with_markitdown(url: str, title_hint: Optional[str] = None) -> str:
    from markitdown import MarkItDown
    md = MarkItDown()
    result = md.convert(url)
    text = (getattr(result, "text_content", None) or "").strip()
    title = title_hint or getattr(result, "title", None) or url
    header = f"# {title}\n\nFuente: {url}\n\n"
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

    update_entry(file_id, status="processing", error=None, progress=None, elapsed_sec=0)
    settings = load_settings()

    try:
        current_hash = file_hash(src)
        if is_media(src.name):
            md_text = transcribe_media(src, file_id, settings)
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
            tokens=count_tokens(md_text),
            progress=1.0,
            error=None,
        )
        return updated
    except Exception as e:
        update_entry(file_id, status="error", error=str(e), progress=None)
        raise HTTPException(status_code=500, detail=str(e))


def start_conversion_async(file_id: str):
    t = threading.Thread(target=lambda: _safe_convert(file_id), daemon=True)
    t.start()
    return t


def _safe_convert(file_id: str):
    try:
        perform_conversion(file_id)
    except HTTPException:
        pass
    except Exception as e:
        update_entry(file_id, status="error", error=str(e))


def ensure_order(file_id: str):
    s = load_settings()
    order = list(s.get("order") or [])
    if file_id not in order:
        order.append(file_id)
        s["order"] = order
        save_settings(s)


def remove_from_order(file_id: str):
    s = load_settings()
    order = [i for i in (s.get("order") or []) if i != file_id]
    s["order"] = order
    save_settings(s)


def create_file_entry(source_path: Path, display_name: str, source: str = "upload", url: Optional[str] = None) -> dict:
    file_id = uuid.uuid4().hex
    size = source_path.stat().st_size
    entry = {
        "id": file_id,
        "name": display_name,
        "source_path": str(source_path),
        "size": size,
        "status": "pending",
        "uploaded_at": datetime.utcnow().isoformat() + "Z",
        "converter": None,
        "output_path": None,
        "converted_at": None,
        "hash": None,
        "error": None,
        "tokens": None,
        "progress": None,
        "elapsed_sec": None,
        "duration_sec": None,
        "source": source,
        "url": url,
    }
    with _index_lock:
        index = load_json(INDEX_FILE, {})
        index[file_id] = entry
        with open(INDEX_FILE, "w", encoding="utf-8") as f:
            json.dump(index, f, ensure_ascii=False, indent=2)
    ensure_order(file_id)
    return entry


def is_youtube_url(url: str) -> bool:
    try:
        host = urlparse(url).netloc.lower()
    except Exception:
        return False
    return any(d in host for d in ("youtube.com", "youtu.be", "music.youtube.com"))


def safe_filename(s: str, fallback: str = "archivo") -> str:
    s = re.sub(r"[\\/:*?\"<>|\n\r\t]+", " ", s or "").strip()
    s = re.sub(r"\s+", " ", s)
    return (s or fallback)[:120]


def download_youtube_audio(url: str) -> tuple[Path, str]:
    out_dir = tempfile.mkdtemp(prefix="ytdl_")
    out_template = str(Path(out_dir) / "%(title).100s.%(ext)s")
    cmd = [
        "yt-dlp", "-x", "--audio-format", "mp3",
        "--no-playlist", "--restrict-filenames",
        "-o", out_template, url,
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or "yt-dlp falló")
    files = sorted(Path(out_dir).glob("*.mp3"))
    if not files:
        raise RuntimeError("yt-dlp no produjo audio")
    audio = files[0]
    target = UPLOAD_DIR / f"{uuid.uuid4().hex}__{safe_filename(audio.stem)}.mp3"
    shutil.move(str(audio), target)
    return target, audio.stem


def health_check() -> dict:
    def cmd_ok(args):
        try:
            r = subprocess.run(args, capture_output=True, text=True, timeout=5)
            return r.returncode == 0
        except Exception:
            return False

    def mod_ok(name):
        try:
            __import__(name)
            return True
        except Exception:
            return False

    return {
        "ffmpeg": cmd_ok(["ffmpeg", "-version"]),
        "ffprobe": cmd_ok(["ffprobe", "-version"]),
        "yt_dlp": cmd_ok(["yt-dlp", "--version"]),
        "markitdown": mod_ok("markitdown"),
        "whisper": mod_ok("whisper"),
        "tiktoken": mod_ok("tiktoken"),
    }


def watch_loop():
    while not _watch_stop.is_set():
        try:
            s = load_settings()
            folder = s.get("watch_folder")
            if folder and s.get("watch_enabled") and Path(folder).is_dir():
                for p in Path(folder).iterdir():
                    if not p.is_file() or p.name.startswith("."):
                        continue
                    key = f"{p}|{p.stat().st_mtime_ns}|{p.stat().st_size}"
                    if key in _watch_seen:
                        continue
                    _watch_seen.add(key)
                    try:
                        target = UPLOAD_DIR / f"{uuid.uuid4().hex}__{p.name}"
                        shutil.copy2(p, target)
                        entry = create_file_entry(target, p.name, source="watch")
                        start_conversion_async(entry["id"])
                    except Exception:
                        pass
        except Exception:
            pass
        _watch_stop.wait(2.0)


def start_watcher_if_needed():
    global _watch_thread
    if _watch_thread and _watch_thread.is_alive():
        return
    _watch_stop.clear()
    _watch_thread = threading.Thread(target=watch_loop, daemon=True)
    _watch_thread.start()


app = FastAPI(title="MD - Markitdown")


@app.on_event("startup")
def on_startup():
    start_watcher_if_needed()


@app.get("/", response_class=HTMLResponse)
def root():
    index_html = STATIC_DIR / "index.html"
    return HTMLResponse(index_html.read_text(encoding="utf-8"))


@app.get("/api/health")
def api_health():
    return health_check()


@app.get("/api/settings")
def api_get_settings():
    return load_settings()


class SettingsBody(BaseModel):
    whisper_model: Optional[str] = None
    whisper_language: Optional[str] = None
    whisper_translate: Optional[bool] = None
    watch_folder: Optional[str] = None
    watch_enabled: Optional[bool] = None


@app.post("/api/settings")
def api_save_settings(body: SettingsBody):
    s = load_settings()
    data = body.model_dump(exclude_none=True)
    s.update(data)
    save_settings(s)
    if s.get("watch_enabled"):
        _watch_seen.clear()
        start_watcher_if_needed()
    return s


def list_files_data() -> list[dict]:
    index = load_index()
    settings = load_settings()
    order = settings.get("order") or []
    items = []
    for fid, entry in index.items():
        e = dict(entry)
        e["is_media"] = is_media(e.get("name", ""))
        items.append(e)

    pos = {fid: i for i, fid in enumerate(order)}
    items.sort(key=lambda x: (pos.get(x["id"], 10_000_000), x.get("uploaded_at") or ""))
    return items


@app.get("/api/files")
def api_list_files():
    return {"files": list_files_data()}


@app.post("/api/upload")
async def api_upload(files: list[UploadFile] = File(...)):
    created = []
    for up in files:
        file_id = uuid.uuid4().hex
        safe_name = Path(up.filename).name
        stored = UPLOAD_DIR / f"{file_id}__{safe_name}"
        with open(stored, "wb") as out:
            shutil.copyfileobj(up.file, out)
        entry = create_file_entry(stored, safe_name)
        created.append({"id": entry["id"], "name": safe_name, "is_media": is_media(safe_name)})
        start_conversion_async(entry["id"])
    return {"created": created}


class UrlBody(BaseModel):
    url: str


@app.post("/api/ingest-url")
def api_ingest_url(body: UrlBody):
    url = body.url.strip()
    if not url:
        raise HTTPException(status_code=400, detail="URL vacía")
    try:
        if is_youtube_url(url):
            target, title = download_youtube_audio(url)
            entry = create_file_entry(target, f"{title}.mp3", source="youtube", url=url)
        else:
            tmp = UPLOAD_DIR / f"{uuid.uuid4().hex}__url.html"
            tmp.write_text(url, encoding="utf-8")
            entry = create_file_entry(tmp, urlparse(url).netloc or "url", source="url", url=url)
        start_conversion_async(entry["id"])
        return {"ok": True, "file": {"id": entry["id"], "name": entry["name"]}}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


def perform_url_conversion(file_id: str):
    entry = load_index().get(file_id)
    if not entry:
        return
    url = entry.get("url")
    update_entry(file_id, status="processing", error=None, progress=None)
    try:
        text = convert_url_with_markitdown(url, title_hint=entry.get("name"))
        out_path = OUTPUT_DIR / f"{file_id}.md"
        out_path.write_text(text, encoding="utf-8")
        update_entry(
            file_id, status="done", converter="markitdown",
            output_path=str(out_path), converted_at=datetime.utcnow().isoformat() + "Z",
            size_md=len(text.encode("utf-8")), tokens=count_tokens(text), progress=1.0,
        )
    except Exception as e:
        update_entry(file_id, status="error", error=str(e))


@app.post("/api/convert/{file_id}")
def api_convert(file_id: str):
    entry = load_index().get(file_id)
    if not entry:
        raise HTTPException(status_code=404, detail="No existe")
    if entry.get("source") == "url" and entry.get("url") and not is_youtube_url(entry["url"]):
        t = threading.Thread(target=lambda: perform_url_conversion(file_id), daemon=True)
        t.start()
    else:
        start_conversion_async(file_id)
    return {"ok": True}


@app.post("/api/convert-all")
def api_convert_all():
    index = load_index()
    started = []
    for fid, entry in index.items():
        if entry.get("status") not in ("done", "processing"):
            start_conversion_async(fid)
            started.append(fid)
    return {"started": started}


@app.get("/api/download/{file_id}")
def api_download(file_id: str):
    entry = load_index().get(file_id)
    if not entry or not entry.get("output_path"):
        raise HTTPException(status_code=404, detail="MD no disponible")
    out = Path(entry["output_path"])
    if not out.exists():
        raise HTTPException(status_code=404, detail="MD no encontrado")
    name = Path(entry["name"]).stem + ".md"
    return FileResponse(out, media_type="text/markdown", filename=name)


@app.get("/api/markdown/{file_id}", response_class=PlainTextResponse)
def api_markdown(file_id: str):
    entry = load_index().get(file_id)
    if not entry or not entry.get("output_path"):
        raise HTTPException(status_code=404, detail="MD no disponible")
    out = Path(entry["output_path"])
    if not out.exists():
        raise HTTPException(status_code=404, detail="MD no encontrado")
    return PlainTextResponse(out.read_text(encoding="utf-8"), media_type="text/markdown")


@app.get("/api/preview/{file_id}")
def api_preview(file_id: str):
    entry = load_index().get(file_id)
    if not entry or not entry.get("output_path"):
        raise HTTPException(status_code=404, detail="MD no disponible")
    out = Path(entry["output_path"])
    if not out.exists():
        raise HTTPException(status_code=404, detail="MD no encontrado")
    text = out.read_text(encoding="utf-8")
    return JSONResponse({
        "id": file_id, "name": entry["name"], "markdown": text,
        "tokens": count_tokens(text),
    })


class CombineBody(BaseModel):
    ids: Optional[list[str]] = None


@app.post("/api/combine")
def api_combine(body: CombineBody):
    index = load_index()
    settings = load_settings()
    order = body.ids if body.ids is not None else (settings.get("order") or list(index.keys()))

    parts = []
    used = []
    total_tokens = 0
    for fid in order:
        entry = index.get(fid)
        if not entry or entry.get("status") != "done":
            continue
        out_path = Path(entry.get("output_path") or "")
        if not out_path.exists():
            continue
        text = out_path.read_text(encoding="utf-8")
        parts.append(f"\n\n---\n\n<!-- Fuente: {entry['name']} -->\n\n" + text)
        used.append(entry["name"])
        total_tokens += count_tokens(text)

    if not parts:
        raise HTTPException(status_code=400, detail="No hay archivos convertidos para combinar")

    header = "# Contexto combinado\n\nArchivos incluidos:\n" + "\n".join(f"- {n}" for n in used)
    combined = header + "".join(parts)
    combined_path = OUTPUT_DIR / "_combined.md"
    combined_path.write_text(combined, encoding="utf-8")
    return {
        "ok": True,
        "count": len(used),
        "size": len(combined.encode("utf-8")),
        "tokens": count_tokens(combined),
    }


@app.get("/api/combined", response_class=PlainTextResponse)
def api_combined_text():
    p = OUTPUT_DIR / "_combined.md"
    if not p.exists():
        raise HTTPException(status_code=404, detail="Aún no hay combinado")
    return PlainTextResponse(p.read_text(encoding="utf-8"), media_type="text/markdown")


@app.get("/api/download-combined")
def api_download_combined():
    p = OUTPUT_DIR / "_combined.md"
    if not p.exists():
        raise HTTPException(status_code=404, detail="Aún no hay combinado. Pulsá 'Combinar' primero.")
    return FileResponse(p, media_type="text/markdown", filename="contexto-combinado.md")


class OrderBody(BaseModel):
    ids: list[str]


@app.post("/api/order")
def api_set_order(body: OrderBody):
    s = load_settings()
    s["order"] = list(body.ids)
    save_settings(s)
    return {"ok": True}


class DeleteBody(BaseModel):
    ids: list[str]


@app.post("/api/delete")
def api_delete_many(body: DeleteBody):
    deleted = []
    with _index_lock:
        index = load_json(INDEX_FILE, {})
        for fid in body.ids:
            entry = index.pop(fid, None)
            if entry:
                deleted.append(fid)
                for key in ("source_path", "output_path"):
                    p = entry.get(key)
                    if p and Path(p).exists():
                        try: Path(p).unlink()
                        except Exception: pass
        with open(INDEX_FILE, "w", encoding="utf-8") as f:
            json.dump(index, f, ensure_ascii=False, indent=2)
    s = load_settings()
    s["order"] = [i for i in (s.get("order") or []) if i not in deleted]
    save_settings(s)
    return {"ok": True, "deleted": deleted}


@app.delete("/api/file/{file_id}")
def api_delete_one(file_id: str):
    return api_delete_many(DeleteBody(ids=[file_id]))


@app.post("/api/clear")
def api_clear():
    with _index_lock:
        if INDEX_FILE.exists():
            INDEX_FILE.unlink()
        for d in (UPLOAD_DIR, OUTPUT_DIR):
            for p in d.iterdir():
                try: p.unlink()
                except Exception: pass
    s = load_settings()
    s["order"] = []
    save_settings(s)
    return {"ok": True}


app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


if __name__ == "__main__":
    import uvicorn
    host = os.environ.get("HOST", "127.0.0.1")
    port = int(os.environ.get("PORT", "8000"))
    uvicorn.run("app:app", host=host, port=port, reload=False)
