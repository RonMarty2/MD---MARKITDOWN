const $ = (sel) => document.querySelector(sel);
const dropzone = $("#dropzone");
const fileInput = $("#file-input");
const list = $("#file-list");
const emptyHint = $("#empty-hint");
const countEl = $("#files-count");
const toast = $("#toast");
const preview = $("#preview");
const previewBody = $("#preview-body");
const previewTitle = $("#preview-title");
const previewDownload = $("#preview-download");

let pollTimer = null;
let processing = new Set();

function showToast(msg, isError = false, ms = 2500) {
  toast.textContent = msg;
  toast.classList.remove("hidden");
  toast.classList.toggle("err", !!isError);
  clearTimeout(showToast._t);
  showToast._t = setTimeout(() => toast.classList.add("hidden"), ms);
}

function fmtBytes(n) {
  if (n == null) return "";
  const u = ["B", "KB", "MB", "GB"];
  let i = 0;
  while (n >= 1024 && i < u.length - 1) { n /= 1024; i++; }
  return `${n.toFixed(n < 10 && i > 0 ? 1 : 0)} ${u[i]}`;
}

function fmtDate(iso) {
  if (!iso) return "";
  try {
    const d = new Date(iso);
    return d.toLocaleString();
  } catch { return iso; }
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

async function refresh() {
  try {
    const data = await api("/api/files");
    render(data.files);
  } catch (e) { showToast("Error: " + e.message, true); }
}

function render(files) {
  list.innerHTML = "";
  countEl.textContent = files.length;
  emptyHint.style.display = files.length ? "none" : "";
  for (const f of files) list.appendChild(renderItem(f));
  const anyProcessing = files.some((f) => f.status === "processing");
  if (anyProcessing && !pollTimer) {
    pollTimer = setInterval(refresh, 1500);
  } else if (!anyProcessing && pollTimer) {
    clearInterval(pollTimer);
    pollTimer = null;
  }
}

function renderItem(f) {
  const li = document.createElement("li");
  li.className = "file";
  li.dataset.id = f.id;
  li.title = "Doble click para volver a convertir";

  const meta = document.createElement("div");
  meta.className = "meta";
  const kindBadge = `<span class="badge ${f.is_media ? "media" : "doc"}">${f.is_media ? "whisper" : "markitdown"}</span>`;
  const sizeStr = `${fmtBytes(f.size)}${f.size_md ? " → " + fmtBytes(f.size_md) + " md" : ""}`;
  const sub = f.error
    ? `<span class="sub" style="color:var(--err)">${escapeHtml(f.error)}</span>`
    : `<span class="sub">${sizeStr}${f.converted_at ? " · " + fmtDate(f.converted_at) : ""}</span>`;
  meta.innerHTML = `
    ${kindBadge}
    <div style="min-width:0">
      <div class="name">${escapeHtml(f.name)}</div>
      ${sub}
    </div>
  `;

  const status = document.createElement("span");
  status.className = `status ${f.status}`;
  status.textContent = ({
    pending: "pendiente",
    processing: "convirtiendo…",
    done: "listo",
    error: "error",
  })[f.status] || f.status;

  const actions = document.createElement("div");
  actions.className = "row-actions";

  const btnConvert = document.createElement("button");
  btnConvert.className = "iconbtn";
  btnConvert.textContent = f.status === "done" ? "Re-convertir" : "Convertir";
  btnConvert.onclick = (e) => { e.stopPropagation(); convertOne(f.id); };
  actions.appendChild(btnConvert);

  if (f.status === "done") {
    const btnDl = document.createElement("a");
    btnDl.className = "iconbtn";
    btnDl.textContent = "MD";
    btnDl.href = `/api/download/${f.id}`;
    btnDl.onclick = (e) => e.stopPropagation();
    actions.appendChild(btnDl);
  }

  const btnDel = document.createElement("button");
  btnDel.className = "iconbtn danger";
  btnDel.textContent = "✕";
  btnDel.title = "Eliminar";
  btnDel.onclick = (e) => { e.stopPropagation(); removeFile(f.id); };
  actions.appendChild(btnDel);

  li.appendChild(meta);
  li.appendChild(status);
  li.appendChild(actions);

  li.addEventListener("dblclick", () => convertOne(f.id));
  li.addEventListener("click", () => {
    if (f.status === "done") openPreview(f.id, f.name);
  });

  return li;
}

function escapeHtml(s) {
  return (s || "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
}

async function convertOne(id) {
  if (processing.has(id)) return;
  processing.add(id);
  try {
    await api(`/api/convert/${id}`, { method: "POST" });
    showToast("Convertido");
  } catch (e) {
    showToast("Error: " + e.message, true, 4000);
  } finally {
    processing.delete(id);
    refresh();
  }
}

async function removeFile(id) {
  if (!confirm("¿Eliminar este archivo?")) return;
  try {
    await api(`/api/file/${id}`, { method: "DELETE" });
    if (preview.dataset.id === id) preview.classList.add("hidden");
    refresh();
  } catch (e) { showToast("Error: " + e.message, true); }
}

async function openPreview(id, name) {
  try {
    const data = await api(`/api/preview/${id}`);
    preview.dataset.id = id;
    previewTitle.textContent = name;
    previewBody.textContent = data.markdown;
    previewDownload.href = `/api/download/${id}`;
    preview.classList.remove("hidden");
  } catch (e) { showToast("Error: " + e.message, true); }
}

$("#preview-close").onclick = () => preview.classList.add("hidden");

async function uploadFiles(fileList) {
  const fd = new FormData();
  for (const f of fileList) fd.append("files", f, f.name);
  showToast(`Subiendo ${fileList.length} archivo(s)…`);
  let created;
  try {
    const res = await api("/api/upload", { method: "POST", body: fd });
    created = res.created;
  } catch (e) {
    showToast("Error subiendo: " + e.message, true, 4000);
    return;
  }
  await refresh();
  for (const c of created) {
    convertOne(c.id);
  }
}

dropzone.addEventListener("click", () => fileInput.click());
fileInput.addEventListener("change", (e) => {
  if (e.target.files.length) uploadFiles(e.target.files);
  fileInput.value = "";
});

["dragenter", "dragover"].forEach((ev) =>
  dropzone.addEventListener(ev, (e) => {
    e.preventDefault();
    dropzone.classList.add("drag");
  })
);
["dragleave", "drop"].forEach((ev) =>
  dropzone.addEventListener(ev, (e) => {
    e.preventDefault();
    dropzone.classList.remove("drag");
  })
);
dropzone.addEventListener("drop", (e) => {
  const files = [...(e.dataTransfer?.files || [])];
  if (files.length) uploadFiles(files);
});

window.addEventListener("dragover", (e) => e.preventDefault());
window.addEventListener("drop", (e) => e.preventDefault());

$("#btn-convert-all").onclick = async () => {
  showToast("Convirtiendo pendientes…");
  try {
    await api("/api/convert-all", { method: "POST" });
    showToast("Listo");
  } catch (e) { showToast("Error: " + e.message, true); }
  refresh();
};

$("#btn-combine").onclick = async () => {
  try {
    const r = await api("/api/combine", { method: "POST" });
    showToast(`Combinado: ${r.count} archivo(s) · ${fmtBytes(r.size)}`);
  } catch (e) { showToast("Error: " + e.message, true, 4000); }
};

$("#btn-clear").onclick = async () => {
  if (!confirm("Borrar todos los archivos y conversiones?")) return;
  try {
    await api("/api/clear", { method: "POST" });
    preview.classList.add("hidden");
    refresh();
  } catch (e) { showToast("Error: " + e.message, true); }
};

refresh();
