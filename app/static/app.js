"use strict";
const $ = (id) => document.getElementById(id);

function fmtBytes(n) {
  if (!n && n !== 0) return "—";
  if (n < 0) return "—";
  const u = ["B", "KB", "MB", "GB", "TB"];
  let i = 0;
  n = Number(n) || 0;
  while (n >= 1024 && i < u.length - 1) { n /= 1024; i++; }
  return n.toFixed(n < 10 && i > 0 ? 1 : 0) + " " + u[i];
}
function fmtSpeed(n) {
  if (!n || n <= 0) return "0 B/s";
  return fmtBytes(n) + "/s";
}
function fmtEta(s) {
  if (s === null || s === undefined || !isFinite(s) || s <= 0) return "—";
  s = Math.round(s);
  const h = Math.floor(s / 3600), m = Math.floor((s % 3600) / 60), sec = s % 60;
  if (h) return h + "h " + m + "m";
  if (m) return m + "m " + sec + "s";
  return sec + "s";
}
function esc(s) {
  return String(s == null ? "" : s).replace(/[&<>"]/g, c =>
    ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
}

async function api(path, method, body) {
  const opt = { method: method || "GET" };
  if (body) {
    opt.headers = { "Content-Type": "application/json" };
    opt.body = JSON.stringify(body);
  }
  const r = await fetch(path, opt);
  return r.json();
}

function render(tasks) {
  const list = $("list");
  let aggSpeed = 0, active = 0, queue = 0;
  if (!tasks.length) {
    list.innerHTML = '<div class="empty">Nenhum download. Cole uma URL acima ou use a extensão do navegador.</div>';
  } else {
    list.innerHTML = tasks.map(t => {
      if (t.status === "downloading") { aggSpeed += t.speed || 0; active++; }
      if (t.status === "pending") queue++;
      const statusLabel = { downloading: "Baixando", paused: "Pausado",
        completed: "Concluído", error: "Erro", pending: "Na fila",
        cancelled: "Cancelado" }[t.status] || t.status;
      const sub = t.error && t.status === "error" ? esc(t.error) : (t.connections > 1 ? t.connections + " conexões" : "1 conexão");
      // ações conforme status
      let acts = "";
      if (t.status === "downloading") acts += btn("pause", t.id, "Pausar", "ghost");
      if (t.status === "paused") acts += btn("resume", t.id, "Retomar", "primary");
      if (t.status === "error") acts += btn("resume", t.id, "Retentar", "primary");
      if (["downloading", "paused", "pending", "error"].includes(t.status))
        acts += btn("cancel", t.id, "Cancelar", "ghost");
      if (t.status !== "downloading")
        acts += btn("remove", t.id, "Remover", "ghost danger");
      return `<div class="row">
        <div class="c-name">${esc(t.filename)}<div class="sub">${sub}</div></div>
        <div class="bar"><i class="${t.total ? "" : "indet"}" style="${t.total ? "width:" + t.pct + "%" : "width:100%"}"></i><em>${t.total ? t.pct.toFixed(1) + "%" : (t.status === "completed" ? "100%" : fmtBytes(t.done))}</em></div>
        <div class="cell">${fmtBytes(t.done)}/${t.total ? fmtBytes(t.total) : "?"}</div>
        <div class="cell">${fmtSpeed(t.speed)}</div>
        <div class="cell">${fmtEta(t.eta)}</div>
        <div class="actions"><span class="status ${t.status}">${statusLabel}</span> ${acts}</div>
      </div>`;
    }).join("");
  }
  $("agg-speed").textContent = fmtSpeed(aggSpeed);
  $("agg-active").textContent = active;
  $("agg-queue").textContent = queue;
}

function btn(action, id, label, cls) {
  return `<button class="${cls}" data-act="${action}" data-id="${id}">${label}</button>`;
}

async function tick() {
  try {
    const r = await api("/api/tasks");
    render(r.tasks || []);
  } catch (e) { /* servidor indisponível */ }
}

async function addDownload() {
  const url = $("url").value.trim();
  if (!url) return;
  const body = {
    url,
    filename: $("fname").value.trim() || undefined,
    connections: parseInt($("conns").value, 10) || 8,
  };
  const r = await api("/api/add", "POST", body);
  if (r.error) { alert(r.error); return; }
  $("url").value = ""; $("fname").value = "";
  tick();
}

document.addEventListener("click", async (e) => {
  const b = e.target.closest("button[data-act]");
  if (!b) return;
  const { act, id } = b.dataset;
  await api(`/api/task/${id}/${act}`, "POST", {});
  tick();
});
$("btn-add").addEventListener("click", addDownload);
$("url").addEventListener("keydown", (e) => { if (e.key === "Enter") addDownload(); });

// config/destino
api("/api/config").then(c => { $("dest").textContent = "destino: " + (c.dest_dir || "—"); }).catch(() => {});

tick();
setInterval(tick, 500);
