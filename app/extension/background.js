// background.js — service worker do SuperFast DM (MV3)
// Faz o POST para a API local em 127.0.0.1:7860.
const API = (location.hostname === "localhost")
  ? "http://localhost:7860" : "http://127.0.0.1:7860";

const api = browser.storage.local || chrome.storage.local;

async function addDownload(url, filename, referer, connections) {
  try {
    const r = await fetch(API + "/api/add", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        url, filename: filename || undefined, referer,
        connections: connections || 8
      })
    });
    return await r.json();
  } catch (e) {
    // servidor local fora do ar
    notify("SuperFast DM indisponível", "Suba o servidor: python3 server.py");
    throw e;
  }
}

function notify(title, message) {
  try {
    (browser.notifications || chrome.notifications).create({
      type: "basic", iconUrl: "icon48.png", title, message
    });
  } catch (_) {}
}

// Recebe mensagem do content script (botao SFD)
const onMsg = (browser.runtime || chrome.runtime).onMessage;
onMsg.addListener((msg, sender, sendResponse) => {
  if (msg && msg.type === "sfd-download") {
    addDownload(msg.url, msg.filename, msg.referer, msg.connections)
      .then(res => {
        sendResponse(res);
        if (!res.error) notify("SuperFast DM", "Adicionado: " + (msg.filename || msg.url));
      })
      .catch(() => sendResponse({ error: "servidor fora do ar" }));
    return true; // assíncrono
  }
});

// Captura automática: quando o navegador inicia um download
const DL = (browser.downloads) || (chrome.downloads);
if (DL && DL.onCreated) {
  DL.onCreated.addListener(async (item) => {
    let on = false;
    try { on = !!(await api.get("auto")).auto; } catch (_) {}
    if (!on) return;
    addDownload(item.url, undefined, item.referrer).catch(() => {});
  });
}

// Clique no icone do app: alterna a captura automática
const ACT = (browser.action) || (chrome.action);
if (ACT && ACT.onClicked) {
  ACT.onClicked.addListener(async () => {
    let cur = false;
    try { cur = !!(await api.get("auto")).auto; } catch (_) {}
    const next = !cur;
    await api.set({ auto: next });
    notify("SuperFast DM", "Captura automática: " + (next ? "LIGADA" : "desligada"));
  });
}
