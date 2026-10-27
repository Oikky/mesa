// Repassa o estado das abas do YouTube pro servidor da Mesa no próprio notebook, e recebe
// de volta os comandos do tablet (tocar um item da fila, volume/mute de uma aba). Fica aqui (e
// não no content script) porque a extensão tem permissão pro 127.0.0.1; a página não tem.
const MESA = "http://127.0.0.1:8070";
const MESA_WS = "ws://127.0.0.1:8070/ext";

function post(path, body) {
  fetch(MESA + path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  }).catch(() => { /* Mesa desligada: tudo bem */ });
}

// canal de volta: a Mesa manda comandos por aqui. O ping a cada 20 s mantém este service worker
// acordado; se ele dormir, a próxima mensagem de uma aba acorda e reabre a conexão.
let ws = null;
function link() {
  if (ws && ws.readyState <= 1) return;
  try { ws = new WebSocket(MESA_WS); } catch { return; }
  ws.onopen = () => report();
  ws.onmessage = (e) => {
    let cmd;
    try { cmd = JSON.parse(e.data); } catch { return; }
    if (cmd.tab == null) return;
    if (cmd.cmd === "tabvol") setTabVol(cmd.tab, cmd.v);
    else if (cmd.cmd === "tabsink") setTabSink(cmd.tab, cmd.name);
    else if (cmd.cmd === "tabbal") setTabBal(cmd.tab, cmd.b);
    else if (cmd.cmd === "tabmute") chrome.tabs.update(cmd.tab, { muted: !!cmd.m }).catch(() => {});
    else chrome.tabs.sendMessage(cmd.tab, cmd).catch(() => {});
  };
  ws.onclose = () => { ws = null; };
}
setInterval(() => {
  if (ws?.readyState === 1) ws.send("ping");
  else link();
}, 20000);

// ------------------------------------------------------------ volume por aba
// Estado guardado na sessão do navegador: o service worker pode ser desligado a qualquer hora.
const LINGER = 20000; // aba que parou de tocar continua na lista por 20 s (pausa rápida não some)
let st = null;        // { vols, bals, heard, ctrl, sinks: {aba: nome da saída}, sinkSt: {aba: ok|perm|denied|notfound} }
const ready = chrome.storage.session.get("tabvol").then((r) => {
  st = r.tabvol || {};
  for (const k of ["vols", "bals", "heard", "ctrl", "sinks", "sinkSt"]) st[k] ||= {};
});
const save = () => chrome.storage.session.set({ tabvol: st });

const browser = /Edg\//.test(navigator.userAgent) ? "msedge.exe"
  : /OPR\//.test(navigator.userAgent) ? "opera.exe" : "chrome.exe";

const host = (url) => {
  try { return new URL(url).hostname.replace(/^www\./, ""); } catch { return ""; }
};

async function setTabVol(tab, v) {
  await ready;
  v = Math.min(1, Math.max(0, Number(v) || 0));
  if (v >= 0.995) delete st.vols[tab]; else st.vols[tab] = v;
  save();
  chrome.tabs.sendMessage(tab, { cmd: "tabgain", gain: v }).catch(() => {});
  report();
}

async function setTabBal(tab, b) {
  await ready;
  b = Math.min(1, Math.max(-1, Number(b) || 0));
  if (Math.abs(b) < 0.01) delete st.bals[tab]; else st.bals[tab] = b;
  save();
  chrome.tabs.sendMessage(tab, { cmd: "tabbal", b }).catch(() => {});
  report();
}

let levels = {};
let lvlTimer = 0;
function flushLevels() {
  lvlTimer = 0;
  if (ws?.readyState === 1) ws.send(JSON.stringify({ lvl: levels }));
  else link();
  levels = {};
}

async function setTabSink(tab, name) {
  await ready;
  if (name) st.sinks[tab] = String(name); else delete st.sinks[tab];
  delete st.sinkSt[tab];
  save();
  chrome.tabs.sendMessage(tab, { cmd: "tabsink", name: name || "" }).catch(() => {});
  report();
}

let reportTimer = 0;
function report() {
  clearTimeout(reportTimer);
  reportTimer = setTimeout(sendReport, 120);
}

async function sendReport() {
  await ready;
  const now = Date.now();
  const all = await chrome.tabs.query({});
  const list = [];
  let lingering = false;
  for (const t of all) {
    if (t.audible) st.heard[t.id] = now;
    const heard = st.heard[t.id] || 0;
    const muted = !!t.mutedInfo?.muted;
    const v = st.vols[t.id] ?? 1;
    const recent = now - heard < LINGER;
    // volume 0 não faz barulho (deixa de ser "audible"), mas continua na lista pra dar pra subir
    if (!t.audible && !(heard && (recent || muted || v === 0))) continue;
    if (!t.audible && recent) lingering = true;
    let icon = t.favIconUrl || "";
    if (icon.length > 30000 || !/^(https?:|data:image\/)/.test(icon)) icon = "";
    list.push({
      tab: t.id, title: (t.title || "").slice(0, 200), host: host(t.url || t.pendingUrl || ""),
      icon, v, bal: st.bals[t.id] || 0, mute: muted, audible: !!t.audible, ctrl: !!st.ctrl[t.id], active: !!t.active,
      sink: st.sinks[t.id] || null, sinkSt: st.sinkSt[t.id] || null,
    });
  }
  // limpa o que ficou de abas que já fecharam
  const open = new Set(all.map((t) => String(t.id)));
  for (const k of ["vols", "bals", "heard", "ctrl", "sinks", "sinkSt"]) for (const id of Object.keys(st[k])) if (!open.has(id)) delete st[k][id];
  save();
  post("/tabs", { browser, tabs: list });
  if (lingering) reportTimer = setTimeout(sendReport, 5000);
}

chrome.tabs.onUpdated.addListener((id, info) => {
  if ("audible" in info || "mutedInfo" in info || "title" in info || "favIconUrl" in info) {
    link();
    report();
  }
});

chrome.tabs.onRemoved.addListener((tab) => {
  post("/yt", { tab, gone: true });
  report();
});

chrome.runtime.onMessage.addListener((msg, sender, reply) => {
  link();
  const tab = sender.tab?.id;
  if (tab == null) return;
  if (msg?.kind === "tablvl") {
    // vários frames da mesma aba: vale o maior; manda junto a cada 100 ms pelo WebSocket
    levels[tab] = Math.max(levels[tab] || 0, msg.v || 0);
    if (!lvlTimer) lvlTimer = setTimeout(flushLevels, 100);
    return;
  }
  if (msg?.kind === "tabsink-st") {
    ready.then(() => { st.sinkSt[tab] = msg.st; save(); report(); });
    return;
  }
  if (msg?.kind === "tabvol-hello") {
    ready.then(() => {
      reply({ gain: st.vols[tab] ?? 1, bal: st.bals[tab] || 0, sink: st.sinks[tab] || null });
      if (sender.frameId === 0 && !st.ctrl[tab]) { st.ctrl[tab] = true; save(); report(); }
    });
    return true; // resposta assíncrona
  }
  post("/yt", { ...msg, tab });
});

link();
report();
