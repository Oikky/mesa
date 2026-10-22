// Roda dentro das abas do YouTube: conta qual vídeo está aberto, em que tempo e se está tocando.
const HEARTBEAT = 2000;

function videoId() {
  const u = new URL(location.href);
  if (u.pathname === "/watch") return u.searchParams.get("v");
  const m = u.pathname.match(/^\/(?:shorts|live|embed)\/([\w-]{11})/);
  return m ? m[1] : null;
}

function mainVideo() {
  return document.querySelector("#movie_player video") || document.querySelector("video");
}

function title() {
  const t = navigator.mediaSession?.metadata?.title;
  if (t) return t;
  return document.title.replace(/^\(\d+\)\s*/, "").replace(/\s+-\s+YouTube( Music)?$/, "");
}

let last = "";
let lastAt = 0;

function report() {
  const id = videoId();
  const v = mainVideo();
  let msg;
  if (!id || !v) {
    msg = { gone: true };
  } else {
    const player = document.getElementById("movie_player");
    if (player && player !== watched) {
      adWatch.disconnect();
      adWatch.observe(player, { attributes: true, attributeFilter: ["class"] });
      watched = player;
    }
    msg = {
      id,
      t: v.currentTime,
      dur: Number.isFinite(v.duration) ? v.duration : 0,
      rate: v.playbackRate,
      playing: !v.paused && !v.ended,
      ad: !!player?.classList.contains("ad-showing"),
      title: title(),
    };
  }
  // não repete mensagem igual (sem vídeo, pausado) a não ser no pulso
  const key = JSON.stringify({ ...msg, t: msg.playing ? 0 : msg.t });
  const now = Date.now();
  if (key === last && now - lastAt < HEARTBEAT - 100) return;
  last = key;
  lastAt = now;
  try {
    chrome.runtime.sendMessage(msg);
  } catch {
    // extensão recarregada: esta aba ficou órfã até recarregar a página
    clearInterval(timer);
  }
}

// eventos de mídia não sobem na árvore, mas dá pra ouvir na captura
for (const ev of ["play", "playing", "pause", "seeked", "ratechange", "loadedmetadata", "ended", "emptied"]) {
  document.addEventListener(ev, () => { last = ""; report(); }, true);
}
document.addEventListener("yt-navigate-finish", () => { last = ""; report(); });
// propaganda começa/termina sem evento de mídia confiável: olha a classe do player
const adWatch = new MutationObserver(() => report());
let watched = null;
const timer = setInterval(() => { last = ""; report(); }, HEARTBEAT);
report();

// ------------------------------------------------------------ fila / playlist (painel da Mesa)
const idOf = (href) => {
  try { return new URL(href, location.origin).searchParams.get("v"); } catch { return null; }
};
const text = (el) => (el?.textContent || "").replace(/\s+/g, " ").trim();

// fila pelos dados do YouTube (yt-data.js, no mundo da página); a tela fica de reserva
let fromData = null;
document.addEventListener("__mesa_ytq", (e) => {
  try { fromData = JSON.parse(e.detail); } catch { fromData = null; }
});
function readQueue() {
  if (location.hostname === "www.youtube.com") {
    fromData = null;
    document.dispatchEvent(new CustomEvent("__mesa_ytq_req"));
    if (fromData?.items?.length) return fromData;
  }
  return readQueueDom();
}

function readQueueDom() {
  const current = videoId();
  // YouTube Music: a fila do player
  const music = [...document.querySelectorAll("ytmusic-player-queue-item")];
  if (music.length) {
    return {
      kind: "queue", title: "Fila",
      items: music.map((el) => ({
        id: idOf(el.querySelector("a[href*='watch']")?.href || "") || el.dataset.videoId || el.getAttribute("video-id"),
        title: text(el.querySelector(".song-title")),
        sub: text(el.querySelector(".byline")),
        current: el.hasAttribute("selected") || el.getAttribute("play-button-state") === "playing",
      })).filter((i) => i.id),
    };
  }
  // playlist aberta ao lado do vídeo
  const pl = document.querySelector("ytd-playlist-panel-renderer:not([hidden]) #items");
  const plItems = pl ? [...pl.querySelectorAll("ytd-playlist-panel-video-renderer")] : [];
  if (plItems.length) {
    // playlist grande: manda os itens em volta do que está tocando
    const at = Math.max(0, plItems.findIndex((el) => el.hasAttribute("selected")));
    const win = plItems.slice(Math.max(0, at - 8), at + 32);
    return {
      kind: "playlist",
      title: text(document.querySelector("ytd-playlist-panel-renderer .title")) || "Playlist",
      items: win.map((el) => ({
        id: idOf(el.querySelector("a#wc-endpoint, a[href*='watch']")?.href || ""),
        title: text(el.querySelector("#video-title")),
        sub: text(el.querySelector("#byline")),
        current: el.hasAttribute("selected"),
      })).filter((i) => i.id),
    };
  }
  // senão: os "a seguir" da coluna da direita
  const side = document.querySelector("#secondary") || document;
  const seen = new Map();
  for (const a of side.querySelectorAll("a[href*='/watch?v=']")) {
    const id = idOf(a.href);
    if (!id || id === current) continue;
    const t = a.getAttribute("title") || text(a.querySelector("#video-title, h3, .yt-lockup-metadata-view-model__title")) || text(a);
    const box = a.closest("ytd-compact-video-renderer, yt-lockup-view-model, ytd-rich-item-renderer");
    const sub = text(box?.querySelector("#channel-name #text, .yt-content-metadata-view-model__metadata-text, ytd-channel-name"));
    const old = seen.get(id);
    if (!old || t.length > old.title.length) seen.set(id, { id, title: t, sub: sub || old?.sub || "", current: false });
    if (seen.size >= 20) break;
  }
  return { kind: "next", title: "A seguir", items: [...seen.values()].filter((i) => i.title) };
}

let lastQueue = "";
let lastQueueAt = 0;
function reportQueue() {
  if (!videoId()) return;
  const q = readQueue();
  const key = JSON.stringify(q);
  if (key === lastQueue && Date.now() - lastQueueAt < 15000) return;
  lastQueue = key;
  lastQueueAt = Date.now();
  try { chrome.runtime.sendMessage({ kind: "queue", list: q }); } catch { /* extensão recarregada */ }
}
setInterval(reportQueue, 3000);
document.addEventListener("yt-navigate-finish", () => setTimeout(reportQueue, 1500));

// comandos que vêm do tablet (pela Mesa): tocar um item da fila
chrome.runtime.onMessage.addListener((cmd) => {
  if (cmd?.cmd !== "ytplay" || !cmd.id) return;
  const link = [...document.querySelectorAll(`a[href*="v=${CSS.escape(cmd.id)}"]`)]
    .find((a) => a.closest("ytd-playlist-panel-video-renderer, ytmusic-player-queue-item, #secondary"));
  const item = document.querySelector(`ytmusic-player-queue-item [href*="${cmd.id}"]`)?.closest("ytmusic-player-queue-item");
  if (item) item.querySelector(".song-title, ytmusic-play-button-renderer")?.click();
  else if (link) link.click();
  else location.assign(`/watch?v=${cmd.id}`);
  setTimeout(() => { lastQueue = ""; reportQueue(); }, 2000);
});
