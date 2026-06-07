const $ = (s) => document.querySelector(s);
const $$ = (s) => [...document.querySelectorAll(s)];

const state = {
  files: [],
  selected: new Set(),
  filter: "",
  previewId: null,
  previewTab: "render",
  combined: null,
  settings: null,
};

let pollTimer = null;
let sortable = null;

// ---------- utils ----------
function showToast(msg, kind = "", ms = 2200) {
  const t = $("#toast");
  t.textContent = msg;
  t.className = `toast ${kind}`;
  clearTimeout(showToast._t);
  showToast._t = setTimeout(() => t.classList.add("hidden"), ms);
}

function fmtBytes(n) {
  if (n == null) return "";
  const u = ["B", "KB", "MB", "GB"];
  let i = 0;
  while (n >= 1024 && i < u.length - 1) { n /= 1024; i++; }
  return `${n.toFixed(n < 10 && i > 0 ? 1 : 0)} ${u[i]}`;
}
function fmtTokens(n) {
  if (n == null) return "—";
  if (n < 1000) return `${n}`;
  if (n < 1_000_000) return `${(n/1000).toFixed(n < 10000 ? 1 : 0)}k`;
  return `${(n/1_000_000).toFixed(1)}M`;
}
function fmtTime(sec) {
  if (sec == null) return "";
  sec = Math.floor(sec);
  const m = Math.floor(sec / 60), s = sec % 60;
  return `${String(m).padStart(2,"0")}:${String(s).padStart(2,"0")}`;
}
function escapeHtml(s) {
  return (s || "").replace(/[&<>"']/g, (c) => ({ "&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;" }[c]));
}

async function api(path, opts = {}) {
  const res = await fetch(path, opts);
  if (!res.ok) {
    let msg = res.statusText;
    try { const j = await res.json(); msg = j.detail || msg; } catch {}
    throw new Error(msg || `HTTP ${res.status}`);
  }
  const ct = res.headers.get("content-type") || "";
  return ct.includes("json") ? res.json() : res.text();
}

async function copyToClipboard(text) {
  try {
    await navigator.clipboard.writeText(text);
    return true;
  } catch {
    const ta = document.createElement("textarea");
    ta.value = text; document.body.appendChild(ta); ta.select();
    const ok = document.execCommand("copy");
    document.body.removeChild(ta);
    return ok;
  }
}

// ---------- file icons ----------
function iconForFile(f) {
  const ext = (f.name || "").toLowerCase().split(".").pop();
  if (f.source === "url" || f.source === "youtube") {
    return { cls: "web", glyph: f.source === "youtube" ? "▶" : "🌐" };
  }
  if (["mp3","wav","m4a","ogg","flac","aac","wma","opus"].includes(ext)) return { cls:"audio", glyph:"♪" };
  if (["mp4","mov","mkv","webm","avi","flv","wmv","m4v"].includes(ext)) return { cls:"video", glyph:"▶" };
  if (["jpg","jpeg","png","gif","webp","bmp","tif","tiff"].includes(ext)) return { cls:"image", glyph:"🖼" };
  if (ext === "pdf") return { cls:"doc", glyph:"📕" };
  if (["doc","docx"].includes(ext)) return { cls:"doc", glyph:"📘" };
  if (["xls","xlsx","csv"].includes(ext)) return { cls:"doc", glyph:"📊" };
  if (["ppt","pptx"].includes(ext)) return { cls:"doc", glyph:"📙" };
  return { cls:"doc", glyph:"📄" };
}

// ---------- rendering ----------
function render(files) {
  state.files = files;
  const list = $("#file-list");
  list.innerHTML = "";

  const filtered = files.filter((f) =>
    !state.filter || (f.name || "").toLowerCase().includes(state.filter.toLowerCase())
  );

  for (const f of filtered) list.appendChild(renderItem(f));

  $("#files-count").textContent = filtered.length === files.length ? files.length
    : `${filtered.length}/${files.length}`;
  $("#empty-hint").style.display = files.length ? "none" : "";

  const totalTokens = files.reduce((acc, f) => acc + (f.tokens || 0), 0);
  $("#tokens-total").textContent = fmtTokens(totalTokens);

  const anyProcessing = files.some((f) => f.status === "processing");
  if (anyProcessing && !pollTimer) {
    pollTimer = setInterval(refresh, 1200);
  } else if (!anyProcessing && pollTimer) {
    clearInterval(pollTimer); pollTimer = null;
  }

  if (!sortable) initSortable();
}

function renderItem(f) {
  const li = document.createElement("li");
  li.className = "file" + (state.selected.has(f.id) ? " selected" : "");
  li.dataset.id = f.id;
  li.title = "Doble click: re-convertir · Click: previsualizar · Arrastrá para reordenar";

  const handle = document.createElement("span");
  handle.className = "handle"; handle.textContent = "⋮⋮";

  const cb = document.createElement("input");
  cb.type = "checkbox"; cb.checked = state.selected.has(f.id);
  cb.onclick = (e) => {
    e.stopPropagation();
    if (cb.checked) state.selected.add(f.id); else state.selected.delete(f.id);
    li.classList.toggle("selected", cb.checked);
  };

  const ic = iconForFile(f);
  const icon = document.createElement("div");
  icon.className = `file-icon ${ic.cls}`; icon.textContent = ic.glyph;

  const body = document.createElement("div"); body.className = "body";
  const sourceBadge = f.source === "youtube" ? `<span class="badge url">YouTube</span>`
    : f.source === "url" ? `<span class="badge url">URL</span>` : "";
  const tokenBadge = f.tokens != null ? `<span class="badge tokens" title="${f.tokens} tokens">${fmtTokens(f.tokens)} tok</span>` : "";
  const kindBadge = `<span class="badge ${f.is_media ? "media" : "doc"}">${f.is_media ? "whisper" : "markitdown"}</span>`;

  let sub;
  if (f.error) {
    sub = `<span class="sub" style="color:var(--err)">${escapeHtml(f.error)}</span>`;
  } else {
    const parts = [];
    if (f.size) parts.push(fmtBytes(f.size));
    if (f.size_md) parts.push(`→ ${fmtBytes(f.size_md)} md`);
    if (f.duration_sec) parts.push(`${fmtTime(f.duration_sec)}`);
    sub = `<span class="sub">${parts.join(" · ")} ${kindBadge} ${sourceBadge} ${tokenBadge}</span>`;
  }
  body.innerHTML = `<div class="name">${escapeHtml(f.name)}</div>${sub}`;

  if (f.status === "processing") {
    const wrap = document.createElement("div"); wrap.className = "progress-wrap";
    const bar = document.createElement("div");
    bar.className = "progress-bar" + (f.progress == null ? " indeterminate" : "");
    if (f.progress != null) bar.style.width = `${Math.round(f.progress * 100)}%`;
    wrap.appendChild(bar);
    body.appendChild(wrap);
    if (f.elapsed_sec != null) {
      const span = document.createElement("span"); span.className = "muted-sm";
      span.textContent = `transcribiendo… ${fmtTime(f.elapsed_sec)}${f.duration_sec ? " / ~" + fmtTime(f.duration_sec) : ""}`;
      body.appendChild(span);
    }
  }

  const status = document.createElement("span");
  status.className = `status ${f.status}`;
  const label = ({pending:"pendiente", processing:"convirtiendo", done:"listo", error:"error"})[f.status] || f.status;
  status.innerHTML = (f.status === "processing" ? `<span class="spinner"></span>` : "") + label;

  const actions = document.createElement("div"); actions.className = "row-actions";

  if (f.status === "done") {
    const btnCopy = document.createElement("button");
    btnCopy.className = "iconbtn"; btnCopy.textContent = "⧉"; btnCopy.title = "Copiar MD";
    btnCopy.onclick = async (e) => {
      e.stopPropagation();
      try {
        const md = await api(`/api/markdown/${f.id}`);
        const ok = await copyToClipboard(md);
        showToast(ok ? "Copiado al portapapeles" : "No pude copiar", ok ? "ok" : "err");
      } catch (e) { showToast("Error: " + e.message, "err"); }
    };
    actions.appendChild(btnCopy);

    const btnDl = document.createElement("a");
    btnDl.className = "iconbtn"; btnDl.textContent = "⬇"; btnDl.title = "Descargar .md";
    btnDl.href = `/api/download/${f.id}`;
    btnDl.onclick = (e) => e.stopPropagation();
    actions.appendChild(btnDl);
  }

  const btnConvert = document.createElement("button");
  btnConvert.className = "iconbtn"; btnConvert.textContent = "↻"; btnConvert.title = "Re-convertir";
  btnConvert.onclick = (e) => { e.stopPropagation(); convertOne(f.id); };
  actions.appendChild(btnConvert);

  const btnDel = document.createElement("button");
  btnDel.className = "iconbtn danger"; btnDel.textContent = "✕"; btnDel.title = "Eliminar";
  btnDel.onclick = (e) => { e.stopPropagation(); removeFiles([f.id]); };
  actions.appendChild(btnDel);

  li.appendChild(handle);
  li.appendChild(cb);
  li.appendChild(icon);
  li.appendChild(body);
  li.appendChild(status);
  li.appendChild(actions);

  li.addEventListener("dblclick", (e) => {
    if (e.target.closest("input,button,a")) return;
    convertOne(f.id);
  });
  li.addEventListener("click", (e) => {
    if (e.target.closest("input,button,a,.handle")) return;
    if (f.status === "done") openPreview(f.id, f.name);
  });

  return li;
}

function initSortable() {
  const list = $("#file-list");
  sortable = Sortable.create(list, {
    handle: ".handle",
    animation: 150,
    ghostClass: "sortable-ghost",
    chosenClass: "sortable-chosen",
    onEnd: async () => {
      const ids = [...list.children].map((el) => el.dataset.id);
      try { await api("/api/order", { method: "POST", headers: {"content-type":"application/json"}, body: JSON.stringify({ ids }) }); }
      catch (e) { showToast("Error guardando orden: " + e.message, "err"); }
    },
  });
}

// ---------- data ----------
async function refresh() {
  try {
    const data = await api("/api/files");
    render(data.files);
  } catch (e) { showToast("Error: " + e.message, "err"); }
}

async function convertOne(id) {
  try {
    await api(`/api/convert/${id}`, { method: "POST" });
    showToast("Conversión iniciada");
    refresh();
  } catch (e) { showToast("Error: " + e.message, "err"); }
}

async function removeFiles(ids) {
  if (!ids.length) return;
  if (!confirm(ids.length === 1 ? "¿Eliminar este archivo?" : `¿Eliminar ${ids.length} archivos?`)) return;
  try {
    await api("/api/delete", { method: "POST", headers: {"content-type":"application/json"}, body: JSON.stringify({ ids }) });
    ids.forEach((id) => state.selected.delete(id));
    if (ids.includes(state.previewId)) $("#preview").classList.add("hidden");
    refresh();
  } catch (e) { showToast("Error: " + e.message, "err"); }
}

async function uploadFiles(fileList) {
  if (!fileList.length) return;
  const fd = new FormData();
  for (const f of fileList) fd.append("files", f, f.name);
  showToast(`Subiendo ${fileList.length} archivo(s)…`);
  try {
    await api("/api/upload", { method: "POST", body: fd });
    refresh();
  } catch (e) { showToast("Error subiendo: " + e.message, "err"); }
}

async function ingestUrl(url) {
  try {
    await api("/api/ingest-url", { method: "POST", headers: {"content-type":"application/json"}, body: JSON.stringify({ url }) });
    showToast("URL agregada");
    refresh();
  } catch (e) { showToast("Error: " + e.message, "err"); }
}

async function openPreview(id, name) {
  try {
    const data = await api(`/api/preview/${id}`);
    state.previewId = id;
    $("#preview-title").textContent = `${name} · ${fmtTokens(data.tokens)} tokens`;
    $("#preview-body-raw").textContent = data.markdown;
    $("#preview-body-render").innerHTML = marked.parse(data.markdown);
    $("#preview-download").href = `/api/download/${id}`;
    $("#preview").classList.remove("hidden");
    showPreviewTab(state.previewTab);
  } catch (e) { showToast("Error: " + e.message, "err"); }
}

function showPreviewTab(tab) {
  state.previewTab = tab;
  $$(".preview-tabs .tab").forEach((t) => t.classList.toggle("active", t.dataset.tab === tab));
  $("#preview-body-render").classList.toggle("hidden", tab !== "render");
  $("#preview-body-raw").classList.toggle("hidden", tab !== "raw");
}

// ---------- combine ----------
async function combineSelected() {
  const ids = state.selected.size
    ? state.files.filter((f) => state.selected.has(f.id) && f.status === "done").map((f) => f.id)
    : state.files.filter((f) => f.status === "done").map((f) => f.id);
  if (!ids.length) return showToast("No hay archivos convertidos para combinar", "err");
  try {
    const r = await api("/api/combine", { method: "POST", headers: {"content-type":"application/json"}, body: JSON.stringify({ ids }) });
    state.combined = r;
    $("#combined-info").textContent = `· ${r.count} archivo(s) · ${fmtBytes(r.size)} · ${fmtTokens(r.tokens)} tokens`;
    showToast(`Combinados ${r.count} archivos`, "ok");
  } catch (e) { showToast("Error: " + e.message, "err"); }
}

async function copyCombined() {
  try {
    const md = await api("/api/combined");
    const ok = await copyToClipboard(md);
    showToast(ok ? "Combinado copiado al portapapeles" : "No pude copiar", ok ? "ok" : "err");
  } catch (e) { showToast("Aún no hay combinado. Combiná primero.", "err"); }
}

// ---------- settings ----------
async function loadSettings() {
  try {
    const s = await api("/api/settings");
    state.settings = s;
    $("#set-whisper-model").value = s.whisper_model || "base";
    $("#set-whisper-language").value = s.whisper_language || "";
    $("#set-whisper-translate").checked = !!s.whisper_translate;
    $("#set-watch-folder").value = s.watch_folder || "";
    $("#set-watch-enabled").checked = !!s.watch_enabled;
  } catch (e) {}
}

async function saveSettings() {
  const body = {
    whisper_model: $("#set-whisper-model").value,
    whisper_language: $("#set-whisper-language").value.trim() || null,
    whisper_translate: $("#set-whisper-translate").checked,
    watch_folder: $("#set-watch-folder").value.trim() || null,
    watch_enabled: $("#set-watch-enabled").checked,
  };
  try {
    await api("/api/settings", { method: "POST", headers: {"content-type":"application/json"}, body: JSON.stringify(body) });
    showToast("Ajustes guardados", "ok");
  } catch (e) { showToast("Error: " + e.message, "err"); }
}

// ---------- health ----------
async function refreshHealth() {
  try {
    const h = await api("/api/health");
    const map = [
      ["ffmpeg", "ffmpeg"],
      ["ffprobe", "ffprobe"],
      ["whisper", "whisper"],
      ["markitdown", "markitdown"],
      ["yt_dlp", "yt-dlp"],
      ["tiktoken", "tiktoken"],
    ];
    $("#health").innerHTML = map.map(([k, label]) =>
      `<span class="h-dot ${h[k] ? "ok" : "no"}" title="${label}: ${h[k] ? "OK" : "FALTA"}"></span>`
    ).join("");
    $("#settings-health").innerHTML = map.map(([k, label]) =>
      `<div class="item"><span class="dot ${h[k] ? "ok" : "no"}"></span>${label}</div>`
    ).join("");
  } catch (e) {}
}

// ---------- theme ----------
function setTheme(t) {
  document.documentElement.setAttribute("data-theme", t);
  try { localStorage.setItem("md-theme", t); } catch {}
}
function initTheme() {
  let t = "dark";
  try { t = localStorage.getItem("md-theme") || (window.matchMedia("(prefers-color-scheme: light)").matches ? "light" : "dark"); } catch {}
  setTheme(t);
}

// ---------- events ----------
function setupEvents() {
  // dropzone
  const dz = $("#dropzone");
  dz.addEventListener("click", () => $("#file-input").click());
  $("#file-input").addEventListener("change", (e) => {
    if (e.target.files.length) uploadFiles(e.target.files);
    e.target.value = "";
  });
  ["dragenter","dragover"].forEach((ev) => dz.addEventListener(ev, (e) => { e.preventDefault(); dz.classList.add("drag"); }));
  ["dragleave","drop"].forEach((ev) => dz.addEventListener(ev, (e) => { e.preventDefault(); dz.classList.remove("drag"); }));
  dz.addEventListener("drop", (e) => {
    const files = [...(e.dataTransfer?.files || [])];
    if (files.length) uploadFiles(files);
  });

  // global drop
  window.addEventListener("dragover", (e) => e.preventDefault());
  window.addEventListener("drop", (e) => {
    e.preventDefault();
    const files = [...(e.dataTransfer?.files || [])];
    if (files.length) uploadFiles(files);
  });

  // URL
  $("#btn-url-add").onclick = () => {
    const u = $("#url-input").value.trim();
    if (u) { ingestUrl(u); $("#url-input").value = ""; }
  };
  $("#url-input").addEventListener("keydown", (e) => {
    if (e.key === "Enter") $("#btn-url-add").click();
  });

  // toolbar
  $("#btn-convert-all").onclick = async () => {
    try { await api("/api/convert-all", { method: "POST" }); refresh(); showToast("Convirtiendo pendientes…"); }
    catch (e) { showToast("Error: " + e.message, "err"); }
  };
  $("#btn-combine").onclick = combineSelected;
  $("#btn-copy-combined").onclick = copyCombined;

  $("#btn-clear").onclick = async () => {
    if (!confirm("Borrar todos los archivos y conversiones?")) return;
    try {
      await api("/api/clear", { method: "POST" });
      state.selected.clear();
      $("#preview").classList.add("hidden");
      $("#combined-info").textContent = "";
      refresh();
    } catch (e) { showToast("Error: " + e.message, "err"); }
  };

  $("#search").addEventListener("input", (e) => { state.filter = e.target.value; render(state.files); });
  $("#btn-select-all").onclick = () => {
    const all = state.files.length && state.files.every((f) => state.selected.has(f.id));
    if (all) state.selected.clear();
    else state.files.forEach((f) => state.selected.add(f.id));
    render(state.files);
  };
  $("#btn-delete-selected").onclick = () => removeFiles([...state.selected]);

  // preview
  $$(".preview-tabs .tab").forEach((t) => t.onclick = () => showPreviewTab(t.dataset.tab));
  $("#preview-close").onclick = () => $("#preview").classList.add("hidden");
  $("#preview-copy").onclick = async () => {
    if (!state.previewId) return;
    try {
      const md = await api(`/api/markdown/${state.previewId}`);
      const ok = await copyToClipboard(md);
      showToast(ok ? "Copiado al portapapeles" : "No pude copiar", ok ? "ok" : "err");
    } catch (e) { showToast("Error: " + e.message, "err"); }
  };

  // settings
  $("#btn-settings").onclick = () => {
    loadSettings();
    refreshHealth();
    $("#settings").classList.remove("hidden");
    $("#overlay").classList.remove("hidden");
  };
  $("#settings-close").onclick = closeDrawers;
  $("#overlay").onclick = closeDrawers;
  $("#btn-save-settings").onclick = saveSettings;

  // theme
  $("#btn-theme").onclick = () => {
    const cur = document.documentElement.getAttribute("data-theme") || "dark";
    setTheme(cur === "dark" ? "light" : "dark");
  };

  // shortcuts
  window.addEventListener("keydown", (e) => {
    const inField = ["INPUT","TEXTAREA","SELECT"].includes(document.activeElement?.tagName);
    if (e.key === "Escape") { closeDrawers(); $("#preview").classList.add("hidden"); }
    if (inField) return;
    if (e.key === "/") { e.preventDefault(); $("#search").focus(); }
    if (e.key === "Delete" || e.key === "Backspace") {
      if (state.selected.size) { e.preventDefault(); removeFiles([...state.selected]); }
    }
    if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "a") {
      e.preventDefault(); $("#btn-select-all").click();
    }
  });

  // paste URL anywhere
  window.addEventListener("paste", (e) => {
    if (["INPUT","TEXTAREA"].includes(document.activeElement?.tagName)) return;
    const text = (e.clipboardData || window.clipboardData).getData("text").trim();
    if (/^https?:\/\//i.test(text)) ingestUrl(text);
  });
}

function closeDrawers() {
  $("#settings").classList.add("hidden");
  $("#overlay").classList.add("hidden");
}

// ---------- boot ----------
initTheme();
setupEvents();
refresh();
loadSettings();
refreshHealth();
setInterval(refreshHealth, 30000);
