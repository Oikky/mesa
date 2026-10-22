"use strict";

const $ = (id) => document.getElementById(id);
const deviceEl = $("device");
const tpl = $("strip-tpl");
const SPRITE = "/icons/sprite.svg";
const icon = (name) => `<svg aria-hidden="true"><use href="${SPRITE}#i-${name}"/></svg>`;
const store = {
  get(k) { try { return localStorage.getItem(k); } catch { return null; } },
  set(k, v) { try { localStorage.setItem(k, v); } catch { /* sem armazenamento */ } },
};

// ------------------------------------------------------------ conexão
let ws = null;
let retry = 0;

function connect() {
  if (ws && ws.readyState <= 1) return;
  ws = new WebSocket(`${location.protocol === "https:" ? "wss" : "ws"}://${location.host}/ws`);
  ws.onopen = () => { retry = 0; setLink(true); };
  ws.onclose = () => {
    setLink(false);
    setTimeout(connect, Math.min(4000, 400 * 2 ** retry++));
  };
  ws.onmessage = (e) => {
    const msg = JSON.parse(e.data);
    if (msg.t === "mix") renderMix(msg.d);
    else if (msg.t === "lvl") setLevels(msg.d);
    else if (msg.t === "media") renderMedia(msg.d);
    else if (msg.t === "pads") renderPads(msg.d);
    else if (msg.t === "padResult") padResult(msg.d);
    else if (msg.t === "video") renderVideo(msg.d);
    else if (msg.t === "ver") checkVersion(msg.d);
    else if (msg.t === "panel") panelData(msg.d.app, msg.d.data);
    else if (msg.t === "ytq") panelData("youtube", msg.d);
    else if (msg.t === "discord") panelData("discord", msg.d);
    else if (msg.t === "tabs") renderTabs(msg.d);
    else if (msg.t === "cfg") renderCfg(msg.d);
    else if (msg.t === "upd") renderUpd(msg.d);
    else if (msg.t === "spnow") { spnow = msg.d || {}; autoPanel(); }
    else if (msg.t === "toast") toast(msg.d);
  };
}

// versão do app que está carregada; se o notebook tiver uma mais nova, recarrega
const loadedVer = new URL(document.querySelector('script[src*="app.js"]').src).searchParams.get("v");
function checkVersion(v) {
  if (loadedVer && v && v !== loadedVer) location.reload();
}

function send(obj) {
  if (ws && ws.readyState === 1) ws.send(JSON.stringify(obj));
}

function setLink(on) {
  deviceEl.classList.toggle("is-online", on);
  deviceEl.classList.toggle("is-offline", !on);
  $("link").title = on ? "Conectado" : "Reconectando";
}

// ------------------------------------------------------------ modos
const calm = matchMedia("(prefers-reduced-motion: reduce)");

function setMode(mode) {
  const changed = deviceEl.dataset.page !== mode;
  deviceEl.dataset.page = mode;
  if (changed && deviceEl.dataset.layout === "d") screenOn(mode);
  document.querySelectorAll(".mode").forEach((b) => {
    const on = b.dataset.mode === mode;
    b.classList.toggle("is-active", on);
    b.setAttribute("aria-current", on ? "page" : "false");
  });
  store.set("mesa.mode", mode);
  closePop();
  closeIconPop();
}
document.querySelectorAll(".mode").forEach((b) => b.addEventListener("click", () => setMode(b.dataset.mode)));

// Palco central: trocar de modo "troca o canal" da tela, como monitor de tubo ligando
function screenOn(mode) {
  const el = mode === "mixer" ? $("lcd") : document.querySelector(`.page[data-page="${mode}"]`);
  if (!el?.animate || calm.matches) return;
  el.animate([
    { clipPath: "inset(49.5% 0 49.5% 0)", filter: "brightness(2.2)", offset: 0 },
    { clipPath: "inset(49.5% 0 49.5% 0)", filter: "brightness(2.2)", offset: .18 },
    { clipPath: "inset(0 0 0 0)", filter: "brightness(1.15)", offset: .7 },
    { clipPath: "inset(0 0 0 0)", filter: "brightness(1)" },
  ], { duration: 420, easing: "cubic-bezier(.16, 1, .3, 1)" });
}

$("master-mute").addEventListener("click", (e) => {
  const on = e.currentTarget.getAttribute("aria-pressed") !== "true";
  e.currentTarget.setAttribute("aria-pressed", String(on));
  send({ t: "mute", id: "master", m: on });
});

// ------------------------------------------------------------ canais
let mix = null;
const strips = new Map(); // id -> strip

function makeStrip(data, kind) {
  const el = tpl.content.firstElementChild.cloneNode(true);
  const s = {
    id: data.id, kind, el, v: data.vol, mute: data.mute, db: null,
    dragging: false, holdUntil: 0, level: 0, target: 0, peak: 0, peakAt: 0, litShown: -1,
    track: el.querySelector(".track"),
    readout: el.querySelector(".readout"),
    muteBtn: el.querySelector(".mute"),
    meter: el.querySelector(".meter"),
    name: el.querySelector(".strip-name"),
    chip: el.querySelector(".chip"),
    iconBtn: el.querySelector(".strip-icon"),
    iconSpec: null, iconKey: null,
  };
  s.muteBtn.addEventListener("click", () => {
    s.mute = !s.mute;
    paintStrip(s);
    if (s.kind === "dc") send({ t: "dcuser", user: s.user, mute: s.mute });
    else send({ t: s.kind === "tab" ? "tabmute" : "mute", id: s.id, m: s.mute });
  });
  // toque no nome: o painel da direita mostra esse app (no navegador, as abas dele)
  s.name.addEventListener("click", () => {
    if (s.kind === "app") showPanel(`app:${s.id}`);
    else if (s.kind === "tab" && tabsState.browser) showPanel(`app:${tabsState.browser}`);
    else if (s.kind === "mic") showPanel("mic");
  });
  s.chip.addEventListener("click", (e) => chipAction(s, e.currentTarget));
  s.iconBtn.addEventListener("click", () => openIconPop(s));
  bindFader(s);
  return s;
}

function paintStrip(s) {
  s.el.style.setProperty("--v", s.v);
  s.el.classList.toggle("is-muted", s.mute);
  s.muteBtn.setAttribute("aria-pressed", String(s.mute));
  const pct = Math.round(s.v * (s.kind === "dc" ? 200 : 100));
  s.track.setAttribute("aria-valuenow", pct);
  if (s.db != null && !s.dragging) {
    s.readout.innerHTML = `${s.db <= -60 ? "−∞" : s.db.toFixed(1).replace("-", "−")}<small> dB</small>`;
  } else {
    s.readout.textContent = pct;
  }
}

function updateStrip(s, data) {
  // enquanto o dedo está no fader (e logo depois), o valor local manda
  if (!s.dragging && performance.now() > s.holdUntil) s.v = data.vol;
  s.mute = data.mute;
  s.db = s.kind === "app" ? null : data.db;
  const devShort = (id) => { const d = mix.devices.find((x) => x.device === id); return d && nm(d.id, d.short); };

  s.el.classList.toggle("is-sub", s.kind === "tab" || s.kind === "dc");
  s.el.classList.toggle("is-dc", s.kind === "dc");
  if (s.kind === "dc") {
    s.user = data.user;
    s.speaking = data.speaking;
    s.el.classList.toggle("is-speaking", data.speaking);
    s.name.textContent = nm(data.id, data.name);
    s.chip.textContent = "Call";
    s.chip.disabled = true;
    s.chip.title = "Volume desta pessoa só pra você";
  } else if (s.kind === "mic") {
    s.name.textContent = nm(data.id, data.short);
    s.chip.textContent = data.default ? "Padrão" : "Usar";
    s.chip.classList.toggle("is-default", data.default);
    s.chip.title = data.default ? "Mic padrão do Windows" : "Tornar o mic padrão";
  } else if (s.kind === "tab") {
    s.name.textContent = nm(siteKey(data), data.name);
    const sink = data.sink && mix.devices.find((d) => d.name === data.sink);
    s.chip.textContent = data.sinkSt && data.sinkSt !== "ok" ? "Sem acesso" : sink ? nm(sink.id, sink.short) : "Aba";
    s.chip.classList.toggle("is-set", !!sink && (!data.sinkSt || data.sinkSt === "ok"));
    s.chip.disabled = !data.ctrl;
    s.chip.title = "Saída desta aba";
    s.el.classList.toggle("is-noctl", !data.ctrl);
    s.el.title = data.ctrl ? data.title : `${data.title}\nDê F5 nessa aba pra controlar o volume`;
  } else if (s.kind === "app") {
    s.name.textContent = nm(data.id, data.name);
    const out = data.output && devShort(data.output);
    s.chip.textContent = out || "Padrão";
    s.chip.classList.toggle("is-set", !!out);
    s.chip.disabled = !mix.routing || data.id === "system";
    s.chip.title = "Saída deste app";
  } else if (s.kind === "master") {
    s.name.textContent = nm("master", "Main");
    s.chip.textContent = nm(data.id === "master" ? `dev:${data.device}` : data.id, data.short);
    s.chip.classList.add("is-set");
    s.chip.title = "Saída padrão do Windows";
  } else {
    s.name.textContent = nm(data.id, data.short);
    s.chip.textContent = data.default ? "Padrão" : "Usar";
    s.chip.classList.toggle("is-default", data.default);
    s.chip.title = data.default ? "Saída padrão" : "Tornar saída padrão";
  }
  s.track.setAttribute("aria-label", `Volume ${s.name.textContent}`);
  s.iconSpec = s.kind === "master" ? "sliders-vertical" : s.kind === "tab" ? data.icon || "globe"
    : s.kind === "dc" ? data.icon || "users" : s.kind === "mic" ? "mic" : data.icon || "app";
  paintIcon(s);
  paintStrip(s);
}

// ícone do canal: o do .exe, um Lucide, uma imagem minha ou nada (config/channels.json)
const isFileIcon = (spec) => /[\\/:]/.test(spec || "");
const iconUrl = (s) => `/icon/${encodeURIComponent(s.id)}?v=${mix?.iconv ?? 0}`;

function paintIcon(s) {
  const spec = s.iconSpec;
  const key = `${spec}|${mix?.iconv}`;
  if (s.iconKey === key) return;
  s.iconKey = key;
  const b = s.iconBtn;
  b.disabled = s.kind === "master" || s.kind === "tab" || s.kind === "dc" || s.kind === "mic";
  b.classList.toggle("is-none", spec === "none");
  b.classList.remove("is-img");
  if (spec === "none") return b.replaceChildren();
  if (spec === "app" || isFileIcon(spec)) {
    const img = new Image();
    img.alt = "";
    img.draggable = false;
    const fallback = s.kind === "tab" ? "globe" : s.kind === "dc" ? "users" : s.kind === "app" ? "app-window" : "speaker";
    img.onerror = () => { b.classList.remove("is-img"); b.innerHTML = icon(fallback); };
    img.src = s.kind === "tab" || s.kind === "dc" ? spec : iconUrl(s);
    b.classList.add("is-img");
    b.replaceChildren(img);
  } else {
    b.innerHTML = icon(spec);
  }
}

function syncStrips(container, list, kind, keep = list) {
  const seen = new Set(keep.map((d) => d.id));
  // tira primeiro quem saiu, pra não bagunçar a ordem dos que ficam
  for (const [id, s] of strips) {
    if (s.el.parentElement === container && !seen.has(id)) {
      strips.delete(id);
      s.el.classList.add("is-leaving");
      setTimeout(() => s.el.remove(), 260);
    }
  }
  list.forEach((data, i) => {
    let s = strips.get(data.id);
    if (!s) {
      s = makeStrip(data, data.kind || kind);
      strips.set(data.id, s);
    }
    const live = [...container.children].filter((el) => !el.classList.contains("is-leaving"));
    if (live[i] !== s.el) container.insertBefore(s.el, live[i] || null);
    updateStrip(s, data);
  });
}

// ------------------------------------------------------------ abas do navegador e faders visíveis
// A extensão manda as abas com som; cada uma vira um sub-fader logo depois do canal do navegador.
let tabsState = { browser: null, tabs: [] };
const siteKey = (t) => `site:${t.host || t.title}`;
const siteName = (host) => (host || "").replace(/\.(com|net|org|tv|gg|io|app)(\.[a-z]{2})?$/, "") || "aba";
const tabStrip = (t) => ({ ...t, kind: "tab", name: siteName(t.host) });
// pessoa na call: fader 0–200% do Discord (o fader inteiro = 200)
const dcStrip = (m) => ({ id: `dc:${m.id}`, kind: "dc", user: m.id, name: m.name, vol: m.volume / 200, mute: m.mute,
  icon: m.avatar, speaking: !!m.speaking && !m.mute });
const DISCORD_EXE = "discord.exe";

// Config dos canais (nome meu, escondido) fica no notebook, em config/channels.json:
// sobrevive a limpar o tablet e vale pra qualquer aparelho. Chaves: .exe, "master", "dev:<id>", "site:<domínio>".
let cfg = {};
const hidden = new Set();
const nm = (key, fallback) => cfg[key]?.name || fallback;

function renderCfg(d) {
  cfg = d || {};
  hidden.clear();
  for (const [k, v] of Object.entries(cfg)) if (v?.hidden) hidden.add(k);
  // o que eu tinha escondido só neste tablet (versão anterior) vai pro notebook uma vez
  let old = [];
  try { old = JSON.parse(store.get("mesa.hidden") || "[]"); } catch { /* nada */ }
  if (old.length) {
    for (const k of old) if (!hidden.has(k)) { hidden.add(k); send({ t: "chhide", id: k, hidden: true }); }
    store.set("mesa.hidden", "[]");
  }
  if (mix) renderMix(mix);
  for (const k of panel.keys) if (k !== "faders") renderSlot(k);
}

function renderTabs(d) {
  tabsState = d?.tabs ? d : { browser: null, tabs: [] };
  if (mix) renderMix(mix);
}

// o que aparece no mixer: canais e abas, tirando o que escondi no painel "Faders"
function mixerList(state) {
  const out = [];
  let placed = false;
  const addTabs = () => {
    placed = true;
    for (const t of tabsState.tabs) if (!hidden.has(siteKey(t))) out.push(tabStrip(t));
  };
  const dc = panel.data.discord;
  const callers = dc?.status === "ok" && dc.channel ? dc.members.map(dcStrip).filter((m) => !hidden.has(m.id)) : [];
  let dcPlaced = false;
  for (const ch of state.channels) {
    if (!hidden.has(ch.id)) out.push(ch);
    if (ch.id === tabsState.browser) addTabs();
    if (ch.id === DISCORD_EXE) { out.push(...callers); dcPlaced = true; }
  }
  if (!placed) addTabs();
  if (!dcPlaced) out.push(...callers);
  return out;
}

function setHidden(key, hide) {
  if (hide) hidden.add(key); else hidden.delete(key);
  send({ t: "chhide", id: key, hidden: hide });
  if (mix) renderMix(mix);
}

function setName(key, name) {
  cfg[key] = { ...cfg[key], name: name || undefined };
  send({ t: "chname", id: key, name });
  if (mix) renderMix(mix);
}

function renderMix(state) {
  mix = state;
  const list = mixerList(state);
  // Palco central: metade dos apps em cada asa, em volta da tela
  const split = deviceEl.dataset.layout === "d" ? Math.ceil(list.length / 2) : list.length;
  syncStrips($("apps"), list.slice(0, split), "app", list);
  syncStrips($("apps-r"), list.slice(split), "app", list);
  const mm = $("master-mute");
  mm.setAttribute("aria-pressed", String(!!state.master?.mute));
  mm.disabled = !state.master;
  syncStrips($("main"), state.master && !hidden.has("master") ? [state.master] : [], "master");
  syncStrips($("outputs"), state.devices, "output");
  syncStrips($("mics"), (state.mics || []).filter((m) => !hidden.has(m.id)), "mic");
  document.querySelector(".page-mixer").classList.toggle("is-empty", list.length === 0 && hidden.has("master"));
  $("apps-empty").textContent = state.channels.length || tabsState.tabs.length
    ? "Todos os faders estão escondidos." : "Nenhum app tocando som agora.";
  if (state.master && !knob.dragging && performance.now() > knob.holdUntil) setKnob(state.master.vol);
  if (routeFor) openRoute(routeFor.s, routeFor.anchor); // mantém o popover atualizado
  for (const k of panel.keys) if (k.startsWith("app:") || k === "mic") renderSlot(k);
  if (slots.has("faders") && !panel.renaming && fadersSig() !== panel.fadersSig) renderSlot("faders");
}

// Dois bancos na coluna dos faders, como os bancos de uma controladora: o de som (apps, abas,
// call, Main) e o dos microfones. Arrastar pra baixo fora das capas troca; os LEDs na borda mostram
// em qual banco está (e tocam pra trocar também).
const mixerPage = document.querySelector(".page-mixer");
function setBank(b) {
  mixerPage.dataset.bank = b;
  document.querySelectorAll(".bank-led").forEach((l) => l.setAttribute("aria-pressed", String(l.dataset.bank === b)));
}
{
  let start = null;
  mixerPage.addEventListener("pointerdown", (e) => {
    if (e.target.closest("button, .chip, .pop")) return;
    start = { x: e.clientX, y: e.clientY, id: e.pointerId };
  });
  mixerPage.addEventListener("pointermove", (e) => {
    if (!start || e.pointerId !== start.id) return;
    if ([...strips.values()].some((x) => x.dragging)) { start = null; return; }
    const dx = e.clientX - start.x, dy = e.clientY - start.y;
    if (Math.abs(dx) > 24 && Math.abs(dx) > Math.abs(dy)) { start = null; return; } // é rolagem pro lado
    if (Math.abs(dy) < 56) return;
    start = null;
    const mics = mixerPage.dataset.bank === "mic";
    if (dy > 0 && !mics && mix?.mics?.length) setBank("mic");
    else if (dy < 0 && mics) setBank("main");
    else if (dy > 0 && mics) setBank("main");
  });
  const end = () => { start = null; };
  mixerPage.addEventListener("pointerup", end);
  mixerPage.addEventListener("pointercancel", end);
  document.querySelectorAll(".bank-led").forEach((l) => l.addEventListener("click", () => setBank(l.dataset.bank)));
  setBank("main");
}

// Arrasto relativo e só pegando na capa: encostar no trilho não mexe em nada, então dá pra
// rolar os faders pro lado passando o dedo por cima deles.
const CAP_GRAB = 26; // px do centro da capa (ela tem 30 de altura) que ainda contam como "pegou"

function bindFader(s) {
  let startY = 0, startV = 0, lastSent = 0, pending = null, timer = 0;
  const travel = s.track.querySelector(".travel");
  const onCap = (y) => {
    const r = travel.getBoundingClientRect();
    return Math.abs(y - (r.top + (1 - s.v) * r.height)) <= CAP_GRAB;
  };
  // dedo na capa: o navegador não rola a fileira (fora dela, rola normal)
  s.track.addEventListener("touchstart", (e) => {
    if (e.touches.length === 1 && onCap(e.touches[0].clientY)) e.preventDefault();
  }, { passive: false });

  const flush = () => {
    timer = 0;
    if (pending == null) return;
    if (s.kind === "dc") send({ t: "dcuser", user: s.user, volume: Math.round(pending * 200) });
    else send({ t: s.kind === "tab" ? "tabvol" : "vol", id: s.id, v: pending });
    pending = null;
    lastSent = performance.now();
  };
  const queue = (v) => {
    pending = v;
    const wait = 40 - (performance.now() - lastSent);
    if (wait <= 0) flush();
    else if (!timer) timer = setTimeout(flush, wait);
  };

  s.track.addEventListener("pointerdown", (e) => {
    if (!onCap(e.clientY)) return;
    s.track.setPointerCapture(e.pointerId);
    s.dragging = true;
    s.el.classList.add("is-dragging");
    startY = e.clientY;
    startV = s.v;
    paintStrip(s);
  });
  s.track.addEventListener("pointermove", (e) => {
    if (!s.dragging) return;
    const h = s.track.querySelector(".travel").clientHeight || 1;
    const v = Math.min(1, Math.max(0, startV + (startY - e.clientY) / h));
    if (v === s.v) return;
    s.v = v;
    paintStrip(s);
    if (s.id === "master") setKnob(v);
    queue(v);
  });
  const end = () => {
    if (!s.dragging) return;
    s.dragging = false;
    s.holdUntil = performance.now() + 600;
    s.el.classList.remove("is-dragging");
    if (timer) { clearTimeout(timer); flush(); }
    paintStrip(s);
  };
  s.track.addEventListener("pointerup", end);
  s.track.addEventListener("pointercancel", end);

  s.track.addEventListener("keydown", (e) => {
    const step = { ArrowUp: .02, ArrowRight: .02, ArrowDown: -.02, ArrowLeft: -.02, PageUp: .1, PageDown: -.1 }[e.key];
    if (step == null) return;
    e.preventDefault();
    s.v = Math.min(1, Math.max(0, s.v + step));
    s.holdUntil = performance.now() + 600;
    paintStrip(s);
    queue(s.v);
  });
}

// fileira que rola: esmaece a borda onde tem mais fader escondido
function edgeFade(el) {
  const paint = () => {
    el.classList.toggle("more-l", el.scrollLeft > 4);
    el.classList.toggle("more-r", el.scrollLeft + el.clientWidth < el.scrollWidth - 4);
  };
  el.addEventListener("scroll", paint, { passive: true });
  new ResizeObserver(paint).observe(el);
  new MutationObserver(paint).observe(el, { childList: true });
}
edgeFade($("apps"));
edgeFade($("mics"));

// ------------------------------------------------------------ knob do volume geral
const knob = { el: $("knob"), v: 0, dragging: false, holdUntil: 0 };
const DOTS = 21;
for (let i = 0; i < DOTS; i++) {
  const d = document.createElement("i");
  d.style.setProperty("--a", `${-135 + (270 * i) / (DOTS - 1)}deg`);
  d.style.setProperty("--r", "calc(var(--knob-r, 56px))");
  $("knob-ring").append(d);
}
new ResizeObserver(() => knob.el.style.setProperty("--knob-r", `${knob.el.clientWidth / 2 - 3}px`)).observe(knob.el);

function setKnob(v) {
  knob.v = v;
  knob.el.style.setProperty("--rot", `${-135 + 270 * v}deg`);
  const lit = Math.round(v * (DOTS - 1));
  [...$("knob-ring").children].forEach((d, i) => d.classList.toggle("is-on", v > 0.004 && i <= lit));
  $("knob-val").textContent = Math.round(v * 100);
  knob.el.setAttribute("aria-valuenow", Math.round(v * 100));
}
{
  let startY = 0, startV = 0, last = 0;
  const push = (v) => {
    setKnob(v);
    const m = strips.get("master");
    if (m) { m.v = v; m.holdUntil = performance.now() + 600; paintStrip(m); }
    if (performance.now() - last > 40) { send({ t: "vol", id: "master", v }); last = performance.now(); }
  };
  knob.el.addEventListener("pointerdown", (e) => {
    knob.el.setPointerCapture(e.pointerId);
    knob.dragging = true;
    knob.el.classList.add("is-dragging");
    startY = e.clientY;
    startV = knob.v;
  });
  knob.el.addEventListener("pointermove", (e) => {
    if (knob.dragging) push(Math.min(1, Math.max(0, startV + (startY - e.clientY) / 220)));
  });
  const end = () => {
    if (!knob.dragging) return;
    knob.dragging = false;
    knob.holdUntil = performance.now() + 600;
    knob.el.classList.remove("is-dragging");
    send({ t: "vol", id: "master", v: knob.v });
  };
  knob.el.addEventListener("pointerup", end);
  knob.el.addEventListener("pointercancel", end);
  knob.el.addEventListener("keydown", (e) => {
    const step = { ArrowUp: .02, ArrowRight: .02, ArrowDown: -.02, ArrowLeft: -.02 }[e.key];
    if (step == null) return;
    e.preventDefault();
    knob.holdUntil = performance.now() + 600;
    push(Math.min(1, Math.max(0, knob.v + step)));
  });
}

// ------------------------------------------------------------ escolher saída
const pop = $("route-pop");
let routeFor = null;

function chipAction(s, anchor) {
  if (!mix) return;
  if (s.kind === "tab") {
    if (routeFor?.s === s) return closePop();
    return openRoute(s, anchor);
  }
  if (s.kind === "mic") {
    const m = mix.mics?.find((x) => x.id === s.id);
    if (m && !m.default) { send({ t: "defaultmic", device: m.device }); toast(`Mic padrão\n${nm(m.id, m.short)}`); }
    return;
  }
  if (s.kind === "output") {
    const dev = mix.devices.find((d) => d.id === s.id);
    if (dev && !dev.default) {
      send({ t: "default", device: dev.device });
      toast(`Saída padrão\n${dev.short}`);
    }
    return;
  }
  if (routeFor?.s === s) return closePop();
  openRoute(s, anchor);
}

function openRoute(s, anchor) {
  routeFor = { s, anchor };
  const list = $("route-list");
  list.replaceChildren();
  const opts = [];
  if (s.kind === "tab") {
    const t = tabsState.tabs.find((x) => x.id === s.id);
    if (!t) return closePop();
    $("route-title").textContent = `Saída · ${nm(siteKey(t), siteName(t.host))}`;
    opts.push({ label: "Padrão do navegador", on: !t.sink, act: () => send({ t: "tabsink", id: t.id, device: null }) });
    for (const d of mix.devices) {
      opts.push({ label: nm(d.id, d.short), on: t.sink === d.name, act: () => { send({ t: "tabsink", id: t.id, device: d.name }); sinkHint(t); } });
    }
  } else if (s.kind === "app") {
    const ch = mix.channels.find((c) => c.id === s.id);
    if (!ch) return closePop();
    $("route-title").textContent = `Saída · ${nm(ch.id, ch.name)}`;
    opts.push({ label: "Padrão do Windows", on: !ch.output, act: () => send({ t: "route", id: s.id, device: null }) });
    for (const d of mix.devices) {
      opts.push({ label: nm(d.id, d.short), on: ch.output === d.device, act: () => send({ t: "route", id: s.id, device: d.device }) });
    }
  } else {
    $("route-title").textContent = "Saída padrão do Windows";
    for (const d of mix.devices) {
      opts.push({ label: nm(d.id, d.short), on: d.default, act: () => send({ t: "default", device: d.device }) });
    }
  }
  for (const o of opts) {
    const b = document.createElement("button");
    b.className = "opt";
    b.setAttribute("aria-pressed", String(o.on));
    b.innerHTML = `<i class="led"></i><span></span>`;
    b.querySelector("span").textContent = o.label;
    b.addEventListener("click", () => { o.act(); closePop(); });
    list.append(b);
  }
  placePop(pop, anchor);
}

// primeira vez num site: o Edge do notebook pede a permissão de microfone pra mostrar as saídas
function sinkHint(t) {
  if (t.sinkSt !== "ok") toast("Se o Edge pedir,\npermita o microfone");
}

function placePop(el, anchor) {
  el.hidden = false;
  const r = anchor.getBoundingClientRect();
  const w = el.offsetWidth, h = el.offsetHeight;
  el.style.left = `${Math.max(12, Math.min(innerWidth - w - 12, r.left + r.width / 2 - w / 2))}px`;
  el.style.top = `${Math.max(12, Math.min(innerHeight - h - 12, r.bottom + 8))}px`;
}

function closePop() {
  routeFor = null;
  pop.hidden = true;
}
document.addEventListener("pointerdown", (e) => {
  if (!pop.hidden && !pop.contains(e.target) && !e.target.closest(".chip")) closePop();
  if (!iconPop.hidden && !iconPop.contains(e.target) && !e.target.closest(".strip-icon")) closeIconPop();
});

// ------------------------------------------------------------ escolher ícone
const iconPop = $("icon-pop");
let iconFor = null;

function openIconPop(s) {
  if (iconFor === s) return closeIconPop();
  closePop();
  iconFor = s;
  $("icon-title").textContent = `Ícone · ${s.name.textContent}`;
  const grid = $("icon-pick");
  grid.replaceChildren();
  const opts = [];
  if (isFileIcon(s.iconSpec)) opts.push({ v: s.iconSpec, label: "Imagem própria", img: true });
  if (s.kind === "app" && s.id !== "system") opts.push({ v: "app", label: "Ícone do app", img: true });
  opts.push({ v: "none", label: "Sem ícone" });
  for (const n of ICONS) opts.push({ v: n, label: n });
  for (const o of opts) {
    const b = document.createElement("button");
    b.type = "button";
    b.setAttribute("aria-label", o.label);
    b.setAttribute("aria-pressed", String(o.v === s.iconSpec));
    if (o.img) {
      const img = new Image();
      img.alt = "";
      img.src = o.v === s.iconSpec ? iconUrl(s) : `/icon/${encodeURIComponent(s.id)}?src=app`;
      img.onerror = () => { b.classList.remove("is-img"); b.innerHTML = icon("app-window"); };
      b.classList.add("is-img");
      b.append(img);
    } else if (o.v === "none") {
      b.innerHTML = `<i class="none-mark"></i>`;
    } else {
      b.innerHTML = icon(o.v);
    }
    b.addEventListener("click", () => {
      s.iconSpec = o.v;
      paintIcon(s);
      send({ t: "icon", id: s.id, icon: o.v });
      closeIconPop();
    });
    grid.append(b);
  }
  placePop(iconPop, s.iconBtn);
}

function closeIconPop() {
  iconFor = null;
  iconPop.hidden = true;
}

// ------------------------------------------------------------ medidores
// Pico (amplitude 0..1) -> posição no medidor em escala de dB (-60..0).
const toMeter = (p) => (p <= 0.001 ? 0 : Math.max(0, 1 + (20 * Math.log10(p)) / 60));
const SEGS = 32;

function setLevels(levels) {
  const mm = slots.get("mic")?.body.querySelector(".mic-meter");
  if (mm && levels[mm.dataset.id] != null) mm.style.setProperty("--l", toMeter(levels[mm.dataset.id]));
  for (const [id, p] of Object.entries(levels)) {
    const s = strips.get(id);
    if (s) { s.target = toMeter(p); s.lvlAt = performance.now(); }
  }
}

let lastFrame = performance.now();
function frame(now) {
  const dt = Math.min(0.1, (now - lastFrame) / 1000);
  lastFrame = now;
  for (const s of strips.values()) {
    // aba: a extensão só manda enquanto tem som; sem notícia, o medidor cai
    if (s.kind === "tab" && now - (s.lvlAt || 0) > 400) s.target = 0;
    if (s.kind === "dc") s.target = s.speaking ? 0.62 + 0.22 * Math.sin(now / 83 + s.user.length) * Math.sin(now / 211) : 0;
    // sobe na hora, desce suave (balística de medidor)
    s.level = s.target > s.level ? s.target : Math.max(s.target, s.level - dt * 1.4);
    if (s.level >= s.peak) { s.peak = s.level; s.peakAt = now; }
    else if (now - s.peakAt > 1200) s.peak = Math.max(s.level, s.peak - dt * 0.6);
    const lit = Math.ceil(s.level * SEGS) / SEGS;
    if (lit !== s.litShown) { s.meter.style.setProperty("--l", lit); s.litShown = lit; }
    s.meter.style.setProperty("--h", Math.ceil(s.peak * SEGS) / SEGS);
    s.meter.style.setProperty("--ho", s.peak > 0.02 ? 1 : 0);
  }
  tickTimeline();
  requestAnimationFrame(frame);
}
requestAnimationFrame(frame);

// ------------------------------------------------------------ tela (mídia)
const lcd = $("lcd");
let media = { active: false };
let mediaAt = performance.now();
let seeking = false;

const fmt = (t) => {
  t = Math.max(0, Math.floor(t));
  const h = Math.floor(t / 3600), m = Math.floor((t % 3600) / 60), s = String(t % 60).padStart(2, "0");
  return h ? `${h}:${String(m).padStart(2, "0")}:${s}` : `${m}:${s}`;
};

function renderMedia(d) {
  const prevArt = media.art;
  const prevTitle = media.title;
  media = d;
  mediaAt = performance.now();
  lcd.dataset.state = d.active ? (d.playing ? "playing" : "paused") : "idle";

  $("title").textContent = d.active ? (d.title || "Sem título") : "Nada tocando";
  $("artist").textContent = d.active ? d.artist : "Dê play no notebook";
  $("source").textContent = d.active ? `${d.source} · ${d.playing ? "Tocando" : "Pausado"}` : "Sem mídia";
  const playIcon = $("play-icon");
  playIcon.setAttribute("href", `${SPRITE}#i-${d.playing ? "pause" : "play"}`);
  playIcon.parentElement.classList.toggle("is-play", !d.playing);
  $("play").setAttribute("aria-label", d.playing ? "Pausar" : "Tocar");
  $("prev").disabled = !d.active || !d.can?.prev;
  $("next").disabled = !d.active || !d.can?.next;
  $("play").disabled = !d.active;
  $("timeline").classList.toggle("is-hidden", !d.duration);
  $("dur").textContent = fmt(d.duration || 0);

  if (d.art !== prevArt) paintArt();
  updateVideo();
  autoPanel();
  if (slots.has("spotify") && d.title !== prevTitle) send({ t: "panel", app: "spotify" });
}

// capa da música; no modo vídeo, a miniatura 16:9 do próprio YouTube enquanto o vídeo carrega
let artShown = null;
function paintArt() {
  const url = lcd.classList.contains("has-video") ? `https://i.ytimg.com/vi/${video.id}/mqdefault.jpg` : media.art;
  if (url === artShown) return;
  artShown = url;
  const art = $("art");
  if (!url) { art.style.backgroundImage = ""; return; }
  const img = new Image();
  img.onload = () => { if (artShown === url) art.style.backgroundImage = `url("${url}")`; };
  img.src = url;
}

function currentPos() {
  if (!media.active) return 0;
  const run = media.playing ? (performance.now() - mediaAt) / 1000 : 0;
  return Math.min(media.duration || Infinity, media.position + run);
}

function tickTimeline() {
  if (!media.active || !media.duration || seeking) return;
  const pos = currentPos();
  $("bar").style.setProperty("--p", pos / media.duration);
  $("pos").textContent = fmt(pos);
}

// toque na tela alterna capa em preto e branco / colorida
lcd.addEventListener("click", (e) => {
  if (e.target.closest("#bar")) return;
  lcd.classList.toggle("is-color");
  store.set("mesa.color", lcd.classList.contains("is-color") ? "1" : "");
});
if (store.get("mesa.color")) lcd.classList.add("is-color");

let toastTimer = 0;
function toast(text) {
  const t = $("toast");
  t.textContent = text;
  t.style.whiteSpace = "pre-line";
  t.classList.add("is-on");
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => t.classList.remove("is-on"), 1600);
}

$("play").addEventListener("click", () => {
  send({ t: "media", a: "toggle" });
  if (media.active) renderMedia({ ...media, position: currentPos(), playing: !media.playing });
});
$("next").addEventListener("click", () => send({ t: "media", a: "next" }));
$("prev").addEventListener("click", () => send({ t: "media", a: "prev" }));

const bar = $("bar");
const barRatio = (e) => {
  const r = bar.getBoundingClientRect();
  return Math.min(1, Math.max(0, (e.clientX - r.left) / r.width));
};
bar.addEventListener("pointerdown", (e) => {
  if (!media.can?.seek || !media.duration) return;
  seeking = true;
  bar.setPointerCapture(e.pointerId);
  bar.style.setProperty("--p", barRatio(e));
});
bar.addEventListener("pointermove", (e) => {
  if (!seeking) return;
  const r = barRatio(e);
  bar.style.setProperty("--p", r);
  $("pos").textContent = fmt(r * media.duration);
});
bar.addEventListener("pointerup", (e) => {
  if (!seeking) return;
  seeking = false;
  const t = barRatio(e) * media.duration;
  send({ t: "media", a: "seek", v: t });
  renderMedia({ ...media, position: t });
});
bar.addEventListener("pointercancel", () => { seeking = false; });

// ------------------------------------------------------------ vídeo do YouTube
// A extensão do navegador conta qual vídeo está tocando e em que tempo; o tablet abre o
// mesmo vídeo, mudo, e vai corrigindo pra ficar junto do notebook.
let video = null;
let videoAt = 0;
const yt = { player: null, ready: false, id: null, live: null, blocked: null, lastSeek: 0, loading: false };
const videoEl = $("video");

function renderVideo(d) {
  video = d;
  videoAt = performance.now();
  updateVideo();
}

const norm = (t) => (t || "").toLowerCase().replace(/[^\p{L}\p{N}]+/gu, " ").trim();
// só mostra se for o vídeo que está no painel de mídia (senão é outra aba/app tocando)
function videoMatches() {
  if (!video || video.id === yt.blocked) return false;
  if (!media.active) return video.playing;
  const a = norm(media.title), b = norm(video.title);
  return !!a && !!b && (a.includes(b) || b.includes(a));
}

const videoExpected = () =>
  video.t + (video.playing && !video.ad ? ((performance.now() - videoAt) / 1000) * video.rate : 0);

function updateVideo() {
  const on = videoMatches();
  lcd.classList.toggle("has-video", on);
  videoEl.classList.toggle("is-live", on && !video.ad && yt.live === video.id);
  $("video-badge").textContent = on && video.ad ? "Anúncio" : "";
  if (on && !video.ad) loadYT();
  paintArt();
  syncVideo();
}

function loadYT() {
  if (yt.loading) return;
  yt.loading = true;
  window.onYouTubeIframeAPIReady = () => {
    yt.player = new YT.Player("yt", {
      width: 480, height: 270,
      playerVars: {
        autoplay: 0, mute: 1, controls: 0, disablekb: 1, fs: 0, rel: 0, iv_load_policy: 3,
        playsinline: 1, cc_load_policy: 0, cc_lang_pref: "zz", origin: location.origin,
      },
      events: {
        onReady: () => { yt.ready = true; yt.player.mute(); syncVideo(); },
        onStateChange: (e) => {
          // só mostra 4 s depois de começar: é quando o título e os botões do YouTube somem
          if (e.data === YT.PlayerState.PLAYING && yt.live !== yt.id && !yt.liveTimer) {
            const id = yt.id;
            yt.liveTimer = setTimeout(() => {
              yt.liveTimer = 0;
              if (yt.id === id) { yt.live = id; updateVideo(); }
            }, 4000);
          }
          // legenda automática não faz sentido na telinha
          if (e.data === YT.PlayerState.PLAYING) hideCaptions();
          syncVideo();
        },
        // 101/150: o dono do vídeo não deixa tocar fora do YouTube; fica a miniatura
        onError: () => { yt.blocked = yt.id; yt.live = null; updateVideo(); },
      },
    });
  };
  const sc = document.createElement("script");
  sc.src = "https://www.youtube.com/iframe_api";
  sc.onerror = () => { sc.remove(); yt.loading = false; }; // tablet sem internet: tenta de novo depois
  document.head.append(sc);
}

function hideCaptions() {
  const p = yt.player;
  try { p.setOption("captions", "track", {}); } catch { /* sem legenda */ }
  try { p.unloadModule("captions"); p.unloadModule("cc"); } catch { /* sem legenda */ }
}

function syncVideo() {
  const p = yt.player;
  if (!yt.ready || !p?.getPlayerState) return;
  const S = YT.PlayerState;
  const st = p.getPlayerState();
  const want = videoMatches() && !video.ad && document.visibilityState === "visible";
  if (!want) {
    if (st === S.PLAYING || st === S.BUFFERING) p.pauseVideo();
    return;
  }
  const now = performance.now();
  const exp = videoExpected();
  if (yt.id !== video.id) {
    yt.id = video.id;
    yt.live = null;
    yt.lastSeek = now;
    p.loadVideoById({ videoId: video.id, startSeconds: exp + (video.playing ? 0.4 : 0) });
    return;
  }
  if (Math.abs(p.getPlaybackRate() - video.rate) > 0.01) p.setPlaybackRate(video.rate);
  // pausado no notebook: toca até aparecer imagem e então para no ponto certo
  if (video.playing || yt.live !== yt.id) {
    if (st !== S.PLAYING && st !== S.BUFFERING) p.playVideo();
  } else if (st === S.PLAYING || st === S.BUFFERING) {
    p.pauseVideo();
  }
  if (st === S.BUFFERING || now - yt.lastSeek < 2500) return;
  const drift = p.getCurrentTime() - exp;
  if (Math.abs(drift) > (video.playing ? 0.5 : 0.2)) {
    p.seekTo(exp + (video.playing ? 0.3 : 0), true);
    yt.lastSeek = now;
  }
}
setInterval(syncVideo, 1000);

// o player tem 480×270 de verdade (o YouTube não gosta de player minúsculo) e é reduzido na tela
new ResizeObserver(() => $("art").style.setProperty("--vs", $("art").clientWidth / 480)).observe($("art"));

// ------------------------------------------------------------ pads
const SLOTS = 15;
const ICONS = ["music", "video", "globe", "app-window", "folder", "monitor", "speaker", "headphones", "mic", "mic-off",
  "volume-2", "volume-x", "keyboard", "gamepad-2", "message-circle", "camera", "radio", "tv", "terminal",
  "lightbulb", "zap", "star", "house", "coffee", "moon", "sun", "bell", "lock", "play", "pause"];
const padsEl = $("pads");
const padsPage = document.querySelector(".page-pads");
let pads = [];
let editing = false;

const QUICK = 5; // quantos pads cabem na fileira do início

// fundo do pad: imagem enviada pelo tablet (/padimg/...), link da internet ou caminho no notebook
// ou um fundo pronto ("preset:grafite"), desenhado no CSS (styles.css, [data-bg])
const padPreset = (p) => (String(p.bg || "").startsWith("preset:") ? p.bg.slice(7) : null);
const padBg = (p) => (!p.bg || padPreset(p) ? null : /^(\/|https?:)/.test(p.bg) ? p.bg : `/padbg/${encodeURIComponent(p.id)}`);
const PRESETS = [
  ["grafite", "Grafite"], ["pontos", "Pontos"], ["grade", "Grade"], ["listras", "Listras"],
  ["ondas", "Ondas"], ["brilho", "Brilho"], ["marfim", "Marfim"], ["carbono", "Carbono"],
  ["vermelho", "Vermelho"], ["laranja", "Laranja"], ["ambar", "Âmbar"], ["verde", "Verde"],
  ["azul", "Azul"], ["roxo", "Roxo"], ["rosa", "Rosa"], ["ciano", "Ciano"],
];
// imagens prontas (web/pad-presets/, créditos no CREDITOS.txt de lá): o ícone some, como imagem minha
const BG_IMAGES = [
  ["youtube.png", "YouTube"], ["spotify.png", "Spotify"], ["discord.png", "Discord"], ["vscode.png", "VS Code"],
  ["obs.png", "OBS"], ["create.jpg", "Create (Minecraft)"], ["headset.jpg", "Fone"], ["notebook.jpg", "Notebook"],
].map(([f, label]) => [`/pad-presets/${f}`, label]);

function makePad(p, slot) {
  const b = document.createElement("button");
  b.className = "pad";
  b.dataset.slot = slot;
  if (p) {
    b.dataset.id = p.id;
    b.innerHTML = `<i class="led"></i>${icon(p.icon || "zap")}<span class="pad-label"></span>`;
    b.querySelector(".pad-label").textContent = p.label || "";
    b.setAttribute("aria-label", p.label || "Pad");
    const bg = padBg(p);
    const preset = padPreset(p);
    if (preset) {
      b.classList.add("has-preset");
      b.dataset.bg = preset;
    } else if (bg) {
      b.classList.add("has-bg");
      b.style.setProperty("--bg", `url("${bg}")`);
    }
  } else {
    b.classList.add("is-empty");
    b.innerHTML = icon("plus");
    b.setAttribute("aria-label", "Novo pad");
  }
  bindPad(b);
  return b;
}

function renderPads(list) {
  pads = list;
  padsEl.replaceChildren();
  for (let slot = 0; slot < SLOTS; slot++) padsEl.append(makePad(list.find((x) => x.slot === slot), slot));
  const home = list.filter((p) => p.home).sort((a, b) => a.slot - b.slot).slice(0, QUICK);
  $("quick").replaceChildren(...home.map((p) => makePad(p, p.slot)));
  $("quick").dataset.count = home.length;
}

// Toque dispara. Segurar levanta o pad: arrastar e soltar em outro lugar troca os dois de posição;
// soltar sem arrastar abre o editor. (Na fileira do início, segurar só abre o editor.)
function bindPad(b) {
  let timer = 0, longed = false, start = null, lifted = false, target = null;
  const grid = () => b.closest("#pads");
  const clearTarget = () => { target?.classList.remove("is-target"); target = null; };
  const drop = () => {
    lifted = false;
    b.classList.remove("is-lifted");
    b.style.removeProperty("--dx");
    b.style.removeProperty("--dy");
    grid()?.classList.remove("is-arranging");
    clearTarget();
  };
  b.addEventListener("pointerdown", (e) => {
    longed = false;
    start = { x: e.clientX, y: e.clientY };
    timer = setTimeout(() => {
      longed = true;
      if (!grid() || !b.dataset.id) return openEditor(+b.dataset.slot);
      lifted = true;
      try { b.setPointerCapture(e.pointerId); } catch { /* dedo já saiu */ }
      b.classList.add("is-lifted");
      grid().classList.add("is-arranging");
      navigator.vibrate?.(12);
    }, 450);
  });
  b.addEventListener("pointermove", (e) => {
    if (!start) return;
    const dx = e.clientX - start.x, dy = e.clientY - start.y;
    if (!lifted) {
      if (Math.hypot(dx, dy) > 10) clearTimeout(timer); // mexeu antes de levantar: não é segurar
      return;
    }
    b.style.setProperty("--dx", `${dx}px`);
    b.style.setProperty("--dy", `${dy}px`);
    const over = document.elementsFromPoint(e.clientX, e.clientY)
      .find((el) => el !== b && el.classList?.contains("pad") && el.parentElement === grid());
    if (over !== target) { clearTarget(); target = over || null; target?.classList.add("is-target"); }
  });
  b.addEventListener("pointerup", (e) => {
    clearTimeout(timer);
    if (lifted) {
      const moved = start && Math.hypot(e.clientX - start.x, e.clientY - start.y) > 12;
      const to = target ? +target.dataset.slot : null;
      drop();
      if (moved && to != null) {
        send({ t: "padMove", from: +b.dataset.slot, to });
        toast("Pad movido");
      } else if (!moved) {
        openEditor(+b.dataset.slot);
      }
    }
    start = null;
  });
  b.addEventListener("pointerleave", () => { if (!lifted) clearTimeout(timer); });
  b.addEventListener("pointercancel", () => { clearTimeout(timer); if (lifted) drop(); start = null; });
  b.addEventListener("contextmenu", (e) => e.preventDefault());
  b.addEventListener("click", () => {
    if (longed) return;
    if (editing || !b.dataset.id) return openEditor(+b.dataset.slot);
    send({ t: "pad", id: b.dataset.id });
  });
}

function padResult(r) {
  // o pad pode estar na grade e na fileira do início: acende os dois
  const all = document.querySelectorAll(`.pad[data-id="${CSS.escape(r.id)}"]`);
  if (!all.length) return;
  if (all.length > 1) all.forEach((x) => x !== all[0] && flashPad(x, r.ok));
  const b = all[0];
  const p = pads.find((x) => x.id === r.id);
  if (r.panel) showPanel(r.panel, r.id);
  if (r.ok) {
    b.classList.add("is-fired");
    setTimeout(() => b.classList.remove("is-fired"), 450);
    toast(p ? p.label : "OK");
  } else {
    b.classList.remove("is-error");
    void b.offsetWidth;
    b.classList.add("is-error");
    toast(`Não deu\n${r.error}`);
  }
}

function flashPad(b, ok) {
  if (ok) {
    b.classList.add("is-fired");
    setTimeout(() => b.classList.remove("is-fired"), 450);
  } else {
    b.classList.remove("is-error");
    void b.offsetWidth;
    b.classList.add("is-error");
  }
}

$("edit-toggle").addEventListener("click", (e) => {
  editing = !editing;
  e.currentTarget.setAttribute("aria-pressed", String(editing));
  padsPage.classList.toggle("is-editing", editing);
});

// ------------------------------------------------------------ editor de pad
const editor = $("editor");
const form = $("editor-form");
let draft = null;

function openEditor(slot) {
  const p = pads.find((x) => x.slot === slot);
  draft = p ? structuredClone(p) : { id: `p${Date.now().toString(36)}`, slot, label: "", icon: "zap", action: { type: "open" } };
  $("editor-title").textContent = p ? "Editar pad" : "Novo pad";
  $("editor-delete").hidden = !p;
  form.label.value = draft.label;
  form.target.value = draft.action.type === "open" ? draft.action.target || "" : "";
  form.keys.value = draft.action.type === "keys" ? draft.action.keys || "" : "";
  paintBgPreview();
  $("home-toggle").setAttribute("aria-pressed", String(!!draft.home));

  const grid = $("icon-grid");
  grid.replaceChildren();
  for (const name of ICONS) {
    const b = document.createElement("button");
    b.type = "button";
    b.innerHTML = icon(name);
    b.setAttribute("aria-label", name);
    b.setAttribute("aria-pressed", String(draft.icon === name));
    b.addEventListener("click", () => {
      draft.icon = name;
      grid.querySelectorAll("button").forEach((x) => x.setAttribute("aria-pressed", String(x === b)));
    });
    grid.append(b);
  }
  setActionType(draft.action.type);
  renderEditorDevices();
  editor.showModal();
}

function setActionType(type) {
  draft.action.type = type;
  editor.dataset.type = type;
  document.querySelectorAll("#action-seg button").forEach((b) => b.setAttribute("aria-pressed", String(b.dataset.type === type)));
}
document.querySelectorAll("#action-seg button").forEach((b) => b.addEventListener("click", () => setActionType(b.dataset.type)));

function renderEditorDevices() {
  const list = $("editor-devices");
  list.replaceChildren();
  const want = (draft.action.device || "").toLowerCase();
  for (const d of mix?.devices || []) {
    const b = document.createElement("button");
    b.type = "button";
    b.className = "opt";
    const on = want && (d.device.toLowerCase() === want || d.name.toLowerCase().includes(want));
    b.setAttribute("aria-pressed", String(!!on));
    b.innerHTML = `<i class="led"></i><span></span>`;
    b.querySelector("span").textContent = d.short;
    b.addEventListener("click", () => {
      draft.action.device = d.device;
      list.querySelectorAll(".opt").forEach((x) => x.setAttribute("aria-pressed", String(x === b)));
    });
    list.append(b);
  }
}

editor.addEventListener("close", () => {
  if (editor.returnValue !== "save" || !draft) return;
  const type = draft.action.type;
  const action = { type };
  if (type === "open") action.target = form.target.value.trim();
  if (type === "keys") action.keys = form.keys.value.trim().toLowerCase();
  if (type === "output") action.device = draft.action.device;
  const missing = (type === "open" && !action.target) || (type === "keys" && !action.keys) || (type === "output" && !action.device);
  if (missing) { toast("Pad sem ação\nnão foi salvo"); return; }
  send({ t: "padSave", d: { ...draft, label: form.label.value.trim(), action } });
});

// ------------------------------------------------------------ fundo e "início" do pad
function paintBgPreview() {
  const bg = padBg(draft);
  const preset = padPreset(draft);
  $("bg-presets").querySelectorAll("button").forEach((b) => b.setAttribute("aria-pressed",
    String(b.dataset.img ? b.dataset.img === draft.bg : b.dataset.bg ? b.dataset.bg === preset : !draft.bg)));
  $("bg-preview").dataset.bg = preset || "";
  $("bg-preview").style.backgroundImage = bg ? `url("${bg}")` : "";
  $("bg-preview").classList.toggle("is-set", !!bg);
  $("bg-clear").hidden = !bg && !preset;
}

$("home-toggle").addEventListener("click", (e) => {
  draft.home = !draft.home;
  e.currentTarget.setAttribute("aria-pressed", String(draft.home));
  const others = pads.filter((p) => p.home && p.id !== draft.id).length;
  if (draft.home && others >= QUICK) toast(`Só cabem ${QUICK}\nno início`);
});
$("bg-pick").addEventListener("click", () => $("bg-file").click());
// fundos prontos: um toque escolhe (o "Nenhum" volta pra tecla de borracha normal)
{
  const box = $("bg-presets");
  const add = (id, label) => {
    const b = document.createElement("button");
    b.type = "button";
    b.className = "bg-swatch";
    if (id) b.dataset.bg = id;
    b.setAttribute("aria-label", label);
    b.title = label;
    b.addEventListener("click", () => {
      if (id) draft.bg = `preset:${id}`; else delete draft.bg;
      paintBgPreview();
    });
    box.append(b);
  };
  add(null, "Nenhum");
  for (const [id, label] of PRESETS) add(id, label);
  for (const [url, label] of BG_IMAGES) {
    const b = document.createElement("button");
    b.type = "button";
    b.className = "bg-swatch is-img";
    b.dataset.img = url;
    b.style.backgroundImage = `url("${url}")`;
    b.setAttribute("aria-label", label);
    b.title = label;
    b.addEventListener("click", () => { draft.bg = url; paintBgPreview(); });
    box.append(b);
  }
}
$("bg-clear").addEventListener("click", () => { delete draft.bg; paintBgPreview(); });
$("bg-file").addEventListener("change", async (e) => {
  const file = e.target.files[0];
  e.target.value = "";
  if (!file) return;
  try {
    // reduz no próprio tablet (quadrado, 288 px, igual tecla de Stream Deck) antes de mandar
    const img = await createImageBitmap(file);
    const side = Math.min(img.width, img.height);
    const c = document.createElement("canvas");
    c.width = c.height = 288;
    c.getContext("2d").drawImage(img, (img.width - side) / 2, (img.height - side) / 2, side, side, 0, 0, 288, 288);
    const blob = await new Promise((ok) => c.toBlob(ok, "image/jpeg", 0.88));
    const res = await fetch("/pad-image", { method: "POST", headers: { "Content-Type": "image/jpeg" }, body: blob });
    if (!res.ok) throw new Error(res.status);
    draft.bg = (await res.json()).url;
    paintBgPreview();
  } catch {
    toast("Não deu pra\nusar essa imagem");
  }
});
$("editor-delete").addEventListener("click", () => {
  send({ t: "padDelete", id: draft.id });
  editor.close("delete");
});

// ------------------------------------------------------------ painel (layout E)
// O painel se divide em até 3 partes empilhadas: em cima o que está tocando (fila do YouTube ou do
// Spotify), no meio a call do Discord, embaixo o que eu abri (pad de app, nome de canal, Canais, Mic).
const panel = { pinned: null, padId: null, data: {}, timer: 0, keys: [] };
const panelEl = $("panel");
const slots = new Map(); // chave -> partes do painel (cabeçalho, corpo, rodapé)
let cur = null, pBody = null, pFoot = null; // a parte que está sendo desenhada agora
const esc = (t) => String(t ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);
const FETCHED = new Set(["youtube", "spotify", "discord"]); // dados que vêm do notebook a pedido

// O que está tocando: a extensão diz se tem vídeo do YouTube tocando, e a conta do Spotify diz se
// tem música (vale pro Spotify Web e pro Opera, que nem sempre aparece no controle de mídia do Windows).
let spnow = {};
function panelKeys() {
  const dc = panel.data.discord;
  const ytOn = videoMatches() || (!!video?.playing && !(media.active && media.playing && media.source === "Spotify"));
  const spOn = (media.active && media.source === "Spotify") || !!spnow.playing;
  const playing = ytOn ? "youtube" : spOn ? "spotify" : null;
  const call = dc?.status === "ok" && dc.channel ? "discord" : null;
  return [...new Set([playing, call, panel.pinned].filter(Boolean))].slice(0, 3);
}

function makeSlot(key) {
  const el = document.createElement("section");
  el.className = "pslot";
  el.dataset.key = key.split(":")[0];
  el.innerHTML = `<header class="panel-head"><button class="panel-fold" aria-expanded="true">
      <span class="panel-icon"></span><span class="panel-title"></span><span class="panel-mini" aria-hidden="true"></span>
      <svg class="fold-chev" aria-hidden="true"><use href="${SPRITE}#i-chevron-down"/></svg></button>
    <button class="key key-small" data-act="open" hidden aria-label="Abrir o app no notebook">${icon("external-link")}</button>
    <button class="key key-small" data-act="close" hidden aria-label="Fechar">${icon("x")}</button></header>
    <div class="panel-clip"><div class="panel-body"></div><footer class="panel-foot"></footer></div>`;
  const q = (sel) => el.querySelector(sel);
  const sl = { key, el, icon: q(".panel-icon"), title: q(".panel-title"), mini: q(".panel-mini"), fold: q(".panel-fold"),
    open: q('[data-act="open"]'), close: q('[data-act="close"]'), body: q(".panel-body"), foot: q(".panel-foot") };
  sl.close.addEventListener("click", unpin);
  sl.open.addEventListener("click", () => panel.padId && send({ t: "pad", id: panel.padId, force: true }));
  // toque no cabeçalho minimiza/abre a parte (fica lembrado neste tablet)
  sl.fold.addEventListener("click", () => setFolded(key, !folded.has(foldKey(key))));
  paintFold(sl);
  return sl;
}

// minimizar: só o cabeçalho fica; vale pelo tipo (youtube, discord, app:...) e fica salvo no tablet
const foldKey = (k) => (k.startsWith("app:") ? "app" : k);
const folded = new Set((() => { try { return JSON.parse(store.get("mesa.folded") || "[]"); } catch { return []; } })());
function paintFold(sl) {
  const on = folded.has(foldKey(sl.key));
  sl.el.classList.toggle("is-folded", on);
  sl.fold.setAttribute("aria-expanded", String(!on));
  sl.fold.setAttribute("aria-label", `${on ? "Abrir" : "Minimizar"} ${sl.title.textContent || ""}`);
}
function setFolded(k, on) {
  if (on) folded.add(foldKey(k)); else folded.delete(foldKey(k));
  store.set("mesa.folded", JSON.stringify([...folded]));
  for (const sl of slots.values()) paintFold(sl);
  panelEl.dataset.open = [...slots.values()].filter((x) => !x.el.classList.contains("is-folded")).length;
}

// Arruma as partes (entra/sai/ordem). Desenha só as que acabaram de aparecer, a não ser com `all`.
// Sem nada aberto o painel some e a coluna dele vai pros faders e pros pads.
function renderPanel(all = false) {
  const keys = panelKeys();
  const added = keys.filter((k) => !slots.has(k));
  panel.keys = keys;
  for (const [k, sl] of slots) {
    if (keys.includes(k)) continue;
    slots.delete(k);
    leave(sl.el);
  }
  const live = () => [...panelEl.children].filter((el) => !el.classList.contains("is-leaving"));
  keys.forEach((k, i) => {
    if (!slots.has(k)) slots.set(k, makeSlot(k));
    const el = slots.get(k).el;
    if (live()[i] !== el) panelEl.insertBefore(el, live()[i] || null);
  });
  panelEl.dataset.n = keys.length;
  panelEl.dataset.open = keys.filter((k) => !folded.has(foldKey(k))).length;
  deviceEl.classList.toggle("no-panel", keys.length === 0);
  for (const k of added) if (FETCHED.has(k)) send({ t: "panel", app: k });
  // fila do Spotify: a API não avisa quando muda, então pergunta de tempos em tempos
  if (keys.includes("spotify") && !panel.timer) panel.timer = setInterval(() => send({ t: "panel", app: "spotify" }), 6000);
  if (!keys.includes("spotify") && panel.timer) { clearInterval(panel.timer); panel.timer = 0; }
  for (const k of keys) if (all || added.includes(k)) renderSlot(k);
}

function renderSlot(k) {
  const sl = slots.get(k);
  if (!sl) return;
  cur = sl; pBody = sl.body; pFoot = sl.foot;
  sl.mini.replaceChildren();
  if (k === "youtube") return renderYouTube(panel.data.youtube);
  if (k === "spotify") return renderSpotify(panel.data.spotify);
  if (k === "discord") return renderDiscord(panel.data.discord);
  if (k === "faders") return renderFaders();
  if (k === "mic") return renderMic();
  if (k.startsWith("app:")) return renderApp(k.slice(4));
}

function dockState() {
  deviceEl.dataset.panel = panel.outputs ? "outputs" : "info";
  $("dock-outputs").setAttribute("aria-pressed", String(!!panel.outputs));
  $("dock-faders").setAttribute("aria-pressed", String(!panel.outputs && panel.pinned === "faders"));
  $("dock-mic").setAttribute("aria-pressed", String(!panel.outputs && panel.pinned === "mic"));
}

// abrir algo no painel (pad, nome de canal, teclas do rodapé); "outputs" troca o painel pelas saídas
function showPanel(key, padId = null) {
  if (key === "outputs") { panel.outputs = true; dockState(); return; }
  panel.outputs = false;
  const again = panel.pinned === key;
  panel.pinned = key;
  panel.padId = padId;
  dockState();
  if (again && slots.has(key)) slots.get(key).el.remove(), slots.delete(key); // redesenha do zero
  renderPanel();
  if (slots.has(key)) renderSlot(key); // já estava aberto como automático: atualiza o cabeçalho
}

function unpin() {
  panel.pinned = null;
  panel.padId = null;
  dockState();
  renderPanel();
}

// o que está tocando mudou: pode aparecer/sumir a parte da fila
function autoPanel() { renderPanel(); }

function panelData(key, data) {
  panel.data[key] = data;
  renderPanel();
  if (slots.has(key)) renderSlot(key);
  if (key === "discord" && slots.has("mic")) renderSlot("mic");
  if (key === "discord" && mix) renderMix(mix);
}

$("dock-faders").addEventListener("click", () => (panel.pinned === "faders" && !panel.outputs ? unpin() : showPanel("faders")));
$("dock-mic").addEventListener("click", () => (panel.pinned === "mic" && !panel.outputs ? unpin() : showPanel("mic")));
$("dock-outputs").addEventListener("click", () => {
  if (panel.outputs) { panel.outputs = false; dockState(); } else showPanel("outputs");
});

renderPanel();

// parte do painel saindo: encolhe e some, depois sai do DOM
function leave(el) {
  el.classList.add("is-leaving");
  const done = () => el.remove();
  if (calm.matches || !el.animate) return done();
  el.animate([{ opacity: 1, flexGrow: getComputedStyle(el).flexGrow }, { opacity: 0, flexGrow: 0, flexBasis: "0px", minHeight: "0px" }],
    { duration: 220, easing: "cubic-bezier(.4, 0, 1, 1)" }).finished.then(done, done);
}

function head(kicker, title, iconHtml) {
  cur.title.textContent = title;
  cur.icon.innerHTML = iconHtml || "";
  cur.close.hidden = cur.key !== panel.pinned;
  cur.open.hidden = !panel.padId || cur.key !== panel.pinned;
  paintFold(cur);
}

function note(html) {
  pBody.innerHTML = `<div class="panel-note">${html}</div>`;
  pFoot.replaceChildren();
}

// a faixa atual vai pro meio da lista só quando muda (senão a lista pula enquanto eu rolo)
function centerCurrent(body, sig) {
  if (body.dataset.cur === sig) return;
  body.dataset.cur = sig;
  const it = body.querySelector('[aria-current="true"]');
  if (it) body.scrollTo({ top: it.offsetTop - body.clientHeight / 2 + it.offsetHeight / 2, behavior: calm.matches ? "auto" : "smooth" });
}

// lista de faixas/vídeos: capa, título, subtítulo; a atual com o LED aceso
function trackList(items, onPick, wide = false) {
  const ul = document.createElement("ol");
  ul.className = `tracks${wide ? " is-wide" : ""}`;
  for (const it of items) {
    const li = document.createElement("li");
    const b = document.createElement("button");
    b.className = "track";
    b.setAttribute("aria-current", it.current ? "true" : "false");
    b.innerHTML = `<span class="track-art"${it.img ? ` style="background-image:url('${esc(it.img)}')"` : ""}></span>
      <span class="track-text"><span class="track-title">${esc(it.title)}</span><span class="track-sub">${esc(it.sub)}</span></span>
      <i class="led"></i>`;
    b.addEventListener("click", () => { onPick(it); b.classList.add("is-picked"); });
    li.append(b);
    ul.append(li);
  }
  return ul;
}

function section(title, count) {
  const h = document.createElement("h3");
  h.className = "panel-sec silk";
  h.innerHTML = `<span>${esc(title)}</span>${count != null ? `<b>${count}</b>` : ""}`;
  return h;
}

function renderYouTube(q) {
  head("YouTube", q?.kind === "playlist" ? q.title : q?.kind === "queue" ? "Fila" : "A seguir", icon("video"));
  pFoot.replaceChildren();
  if (!q || !q.items?.length) return note("Nada na fila. Abra um vídeo ou uma playlist no YouTube do notebook (com a extensão da Mesa instalada).");
  const list = trackList(q.items.map((i) => ({ ...i, img: `https://i.ytimg.com/vi/${i.id}/mqdefault.jpg` })),
    (it) => send({ t: "ytplay", id: it.id }), true);
  pBody.replaceChildren(list);
  centerCurrent(pBody, `yt|${q.items.find((i) => i.current)?.id}`);
}

function renderSpotify(d) {
  head("Spotify", d?.context?.name || (d?.now ? "Fila" : "Spotify"), icon("music"));
  pFoot.replaceChildren();
  if (!d) return note("Carregando…");
  if (d.status === "setup") return note(`Falta ligar o Spotify na Mesa.<br>No notebook, siga o passo a passo <b>Spotify</b> do arquivo <code>PROMPT.md</code> (5 min).`);
  if (d.status === "login") {
    note(`Falta autorizar a Mesa na sua conta do Spotify.`);
    const b = document.createElement("button");
    b.className = "key key-lit panel-cta";
    b.textContent = "Autorizar no notebook";
    b.addEventListener("click", () => { send({ t: "splogin" }); toast("Abrindo o Spotify\nno notebook"); });
    pBody.append(b);
    return;
  }
  if (d.status === "error") return note(esc(d.error));
  const nowUri = d.now?.uri;
  const parts = [];
  if (d.context?.items?.length) {
    parts.push(trackList(d.context.items.map((i) => ({ ...i, current: i.uri === nowUri })),
      (it) => send({ t: "spplay", uri: it.uri, context: d.context.uri })));
  }
  if (d.queue?.length) {
    parts.push(section("A seguir"));
    parts.push(trackList(d.queue, (it) => send({ t: "spplay", uri: it.uri })));
  }
  if (!parts.length) return note(d.now ? "Sem fila agora." : "Nada tocando no Spotify.");
  pBody.replaceChildren(...parts);
  centerCurrent(pBody, `sp|${nowUri}`);
}

// slider horizontal de volume (0–max), mandando no máximo a cada 80 ms
function hslider(value, max, onChange, label) {
  const wrap = document.createElement("label");
  wrap.className = "hslider";
  wrap.innerHTML = `<input type="range" min="0" max="${max}" step="1" value="${value}" aria-label="${esc(label)}"><output>${value}%</output>`;
  const input = wrap.querySelector("input"), out = wrap.querySelector("output");
  const paint = () => wrap.style.setProperty("--p", input.value / max);
  let holdT = 0;
  input.addEventListener("pointerdown", () => { clearTimeout(holdT); wrap.dataset.drag = "1"; });
  const release = () => { clearTimeout(holdT); holdT = setTimeout(() => delete wrap.dataset.drag, 700); };
  input.addEventListener("pointerup", release);
  input.addEventListener("pointercancel", release);
  let last = 0, t = 0;
  input.addEventListener("input", () => {
    paint();
    out.textContent = `${input.value}%`;
    clearTimeout(t);
    const go = () => { last = performance.now(); onChange(+input.value); };
    if (performance.now() - last > 80) go(); else t = setTimeout(go, 80);
  });
  paint();
  return wrap;
}

function renderDiscord(d) {
  const st = d?.status;
  if (st !== "ok") pFoot.replaceChildren();
  if (st !== "ok") {
    head("Discord", "Discord", icon("message-circle"));
    if (st === "setup") return note(`Falta ligar o Discord na Mesa.<br>No notebook, siga o passo a passo <b>Discord</b> do arquivo <code>PROMPT.md</code> (5 min).`);
    if (st === "off" || !st) return note("Abra o Discord no notebook.");
    if (d.waiting) return note("Aprove a Mesa na janela que abriu no Discord do notebook.");
    note(`Falta autorizar a Mesa no seu Discord.${d.error ? `<br><small>${esc(d.error)}</small>` : ""}`);
    const b = document.createElement("button");
    b.className = "key key-lit panel-cta";
    b.textContent = "Conectar";
    b.addEventListener("click", () => send({ t: "dcauth" }));
    pBody.append(b);
    return;
  }
  if (d.channel) {
    head("Discord", d.channel.name, icon("users"));
    renderCall(d);
  } else {
    head("Discord", "Mensagens", icon("message-circle"));
    if (!d.notes?.length) note("Nenhuma mensagem nova desde que a Mesa ligou. Menções e DMs aparecem aqui.");
    else {
      const ul = document.createElement("ul");
      ul.className = "notes";
      for (const n of d.notes) {
        const li = document.createElement("li");
        li.className = "note-item";
        li.innerHTML = `<span class="avatar"${n.icon ? ` style="background-image:url('${esc(n.icon)}')"` : ""}></span>
          <span class="track-text"><span class="track-title">${esc(n.title)}</span><span class="note-body">${esc(n.body)}</span></span>
          <time>${ago(n.at)}</time>`;
        ul.append(li);
      }
      pBody.replaceChildren(ul);
    }
  }
  discordFoot(d);
}

// meu microfone e meu fone, sempre embaixo (só refaz quando muda: a call manda atualização toda hora)
function discordFoot(d) {
  const sig = `dc|${!!d.me?.mute}|${!!d.me?.deaf}`;
  if (pFoot.dataset.sig === sig && pFoot.isConnected && pFoot.children.length) return;
  pFoot.dataset.sig = sig;
  const mic = document.createElement("button");
  mic.className = "key panel-self";
  mic.setAttribute("aria-pressed", String(!!d.me?.mute));
  mic.innerHTML = `${icon(d.me?.mute ? "mic-off" : "mic")}<span>${d.me?.mute ? "Mic mudo" : "Mic"}</span>`;
  mic.addEventListener("click", () => send({ t: "dcself", mute: !d.me?.mute }));
  const deaf = document.createElement("button");
  deaf.className = "key panel-self";
  deaf.setAttribute("aria-pressed", String(!!d.me?.deaf));
  deaf.innerHTML = `${icon(d.me?.deaf ? "headphone-off" : "headphones")}<span>${d.me?.deaf ? "Ensurdecido" : "Áudio"}</span>`;
  deaf.addEventListener("click", () => send({ t: "dcself", deaf: !d.me?.deaf }));
  pFoot.replaceChildren(mic, deaf);
}

// Call: as fotos de quem está na call, com anel pulsando em quem fala. O DOM fica montado e só
// as classes mudam (falar/parar chega várias vezes por segundo; refazer tudo reiniciaria a animação).
const call = { el: null, sig: "", people: new Map(), sel: null };

function renderCall(d) {
  const sig = `${d.channel.id}|${d.members.map((m) => m.id).join(",")}`;
  if (!call.el || call.sig !== sig || !pBody.contains(call.el)) {
    call.sig = sig;
    call.people.clear();
    call.el = document.createElement("div");
    call.el.className = "call";
    const stage = document.createElement("div");
    stage.className = "call-stage";
    stage.dataset.n = Math.min(d.members.length, 9);
    for (const m of d.members) {
      const b = document.createElement("button");
      b.className = "caller";
      b.innerHTML = `<span class="caller-av"><i class="caller-ring"></i><span class="avatar"></span><span class="caller-badge"></span></span><span class="caller-name"></span>`;
      b.addEventListener("click", () => {
        call.sel = call.sel === m.id ? null : m.id;
        renderSlot("discord");
      });
      stage.append(b);
      call.people.set(m.id, b);
    }
    const detail = document.createElement("div");
    detail.className = "call-detail";
    call.el.append(stage, detail);
    pBody.replaceChildren(call.el);
  }
  for (const m of d.members) {
    const b = call.people.get(m.id);
    b.classList.toggle("is-speaking", !!m.speaking && !m.mute);
    b.classList.toggle("is-muted", !!m.mute);
    b.classList.toggle("is-off", !!(m.self_mute || m.self_deaf));
    b.setAttribute("aria-pressed", String(call.sel === m.id));
    b.setAttribute("aria-label", `${m.name}${m.speaking ? ", falando" : ""}`);
    const av = b.querySelector(".avatar");
    const bg = m.avatar ? `url("${m.avatar}")` : "";
    if (av.style.backgroundImage !== bg) av.style.backgroundImage = bg;
    av.textContent = m.avatar ? "" : (m.name[0] || "?").toUpperCase();
    b.querySelector(".caller-name").textContent = m.name;
    const badge = m.self_deaf ? "headphone-off" : m.self_mute ? "mic-off" : m.mute ? "volume-x" : "";
    const bEl = b.querySelector(".caller-badge");
    if (bEl.dataset.icon !== badge) { bEl.dataset.icon = badge; bEl.innerHTML = badge ? icon(badge) : ""; }
  }
  cur.mini.replaceChildren(...d.members.slice(0, 6).map((m) => {
    const i = document.createElement("i");
    i.className = `mini-av${m.speaking && !m.mute ? " is-speaking" : ""}`;
    if (m.avatar) i.style.backgroundImage = `url("${m.avatar}")`;
    return i;
  }));
  // quem eu toquei: volume e mute só pra mim
  const detail = call.el.querySelector(".call-detail");
  const m = d.members.find((x) => x.id === call.sel);
  if (!m) { detail.replaceChildren(); return; }
  const dsig = `${m.id}|${m.volume}|${m.mute}`;
  if (detail.dataset.sig === dsig || detail.querySelector(".hslider[data-drag]")) return;
  detail.dataset.sig = dsig;
  const name = document.createElement("span");
  name.className = "call-detail-name";
  name.textContent = m.name;
  const mute = document.createElement("button");
  mute.className = "key key-small person-mute";
  mute.setAttribute("aria-pressed", String(m.mute));
  mute.setAttribute("aria-label", `Mutar ${m.name} só pra você`);
  mute.innerHTML = icon(m.mute ? "volume-x" : "volume-2");
  mute.addEventListener("click", () => send({ t: "dcuser", user: m.id, mute: !m.mute }));
  detail.replaceChildren(name, hslider(m.volume, 200, (v) => send({ t: "dcuser", user: m.id, volume: v }), `Volume de ${m.name}`), mute);
}

// Microfone: qual é o padrão do Windows (com volume, mute e medidor) e o que o Discord usa.
function renderMic() {
  head("Áudio", "Microfone", icon("mic"));
  pFoot.replaceChildren();
  if (pBody.querySelector(".hslider[data-drag]")) return; // não atrapalha quem está arrastando
  const parts = [];
  const opts = (rows) => {
    const box = document.createElement("div");
    box.className = "pop-list";
    for (const r of rows) {
      const b = document.createElement("button");
      b.className = "opt";
      b.setAttribute("aria-pressed", String(r.on));
      b.innerHTML = `<i class="led"></i><span>${esc(r.label)}</span>`;
      b.addEventListener("click", r.act);
      box.append(b);
    }
    return box;
  };
  const mics = mix?.mics || [];
  const def = mics.find((m) => m.default);
  parts.push(section("Windows · mic padrão", mics.length || null));
  if (def) {
    const row = document.createElement("div");
    row.className = "app-vol";
    const mute = document.createElement("button");
    mute.className = "key mute app-mute";
    mute.setAttribute("aria-pressed", String(def.mute));
    mute.innerHTML = `<i class="led"></i>Mute`;
    mute.addEventListener("click", () => send({ t: "mute", id: def.id, m: !def.mute }));
    row.append(hslider(Math.round(def.vol * 100), 100, (v) => send({ t: "vol", id: def.id, v: v / 100 }), `Volume de ${def.short}`), mute);
    const lvl = document.createElement("div");
    lvl.className = "mic-meter";
    lvl.dataset.id = def.id;
    lvl.innerHTML = "<i></i>";
    parts.push(row, lvl);
  }
  parts.push(opts(mics.map((m) => ({ label: nm(m.id, m.short), on: m.default, act: () => send({ t: "defaultmic", device: m.device }) }))));
  const dc = panel.data.discord;
  if (dc?.status === "ok" && dc.me?.input) {
    const inp = dc.me.input, out = dc.me.output || {};
    parts.push(section("Discord · mic"));
    if (inp.volume != null) parts.push(hslider(Math.round(inp.volume), 100, (v) => send({ t: "dcio", kind: "input", volume: v }), "Volume do mic no Discord"));
    if (inp.devices?.length) parts.push(opts(inp.devices.map((d) => ({ label: d.name, on: d.id === inp.device, act: () => send({ t: "dcio", kind: "input", device: d.id }) }))));
    parts.push(section("Discord · saída"));
    if (out.volume != null) parts.push(hslider(Math.round(out.volume), 200, (v) => send({ t: "dcio", kind: "output", volume: v }), "Volume do Discord"));
    if (out.devices?.length) parts.push(opts(out.devices.map((d) => ({ label: d.name, on: d.id === out.device, act: () => send({ t: "dcio", kind: "output", device: d.id }) }))));
  } else {
    const n = document.createElement("div");
    n.className = "panel-note";
    n.textContent = "Com o Discord aberto e conectado na Mesa, o mic e a saída dele aparecem aqui.";
    parts.push(n);
  }
  pBody.replaceChildren(...parts);
}

const ago = (t) => {
  const s = Math.max(0, Date.now() / 1000 - t);
  return s < 60 ? "agora" : s < 3600 ? `${Math.floor(s / 60)} min` : `${Math.floor(s / 3600)} h`;
};

// app qualquer (jogo etc.): o volume, o mute e a saída dele
function renderApp(id) {
  const ch = mix?.channels.find((c) => c.id === id);
  pFoot.replaceChildren();
  if (!ch) {
    head("App", id.replace(/\.exe$/, ""), icon("app-window"));
    return note("Esse app não está tocando som agora. Quando tocar, o volume e a saída dele aparecem aqui.");
  }
  const s = strips.get(id);
  head("App aberto", nm(id, ch.name), s?.iconBtn.innerHTML || icon("app-window"));
  if (pBody.querySelector(".hslider[data-drag]")) return; // não atrapalha quem está arrastando
  const vol = hslider(Math.round(ch.vol * 100), 100, (v) => send({ t: "vol", id, v: v / 100 }), `Volume de ${ch.name}`);
  const mute = document.createElement("button");
  mute.className = "key mute app-mute";
  mute.setAttribute("aria-pressed", String(ch.mute));
  mute.innerHTML = `<i class="led"></i>Mute`;
  mute.addEventListener("click", () => send({ t: "mute", id, m: !ch.mute }));
  const row = document.createElement("div");
  row.className = "app-vol";
  row.append(vol, mute);
  const outs = document.createElement("div");
  outs.className = "pop-list";
  const opt = (label, on, act) => {
    const b = document.createElement("button");
    b.className = "opt";
    b.setAttribute("aria-pressed", String(on));
    b.innerHTML = `<i class="led"></i><span>${esc(label)}</span>`;
    b.disabled = !mix.routing;
    b.addEventListener("click", act);
    outs.append(b);
  };
  opt("Padrão do Windows", !ch.output, () => send({ t: "route", id, device: null }));
  for (const d of mix.devices) opt(nm(d.id, d.short), ch.output === d.device, () => send({ t: "route", id, device: d.device }));
  pBody.replaceChildren(row, outs);
  if (id === tabsState.browser && tabsState.tabs.length) pBody.append(tabRows());
}

// uma linha por aba: favicon, título, volume e mute (o mute é o da própria aba no navegador)
function tabRows() {
  const ul = document.createElement("ul");
  ul.className = "people tab-rows";
  for (const t of tabsState.tabs) {
    const li = document.createElement("li");
    li.className = "person tab-row";
    li.classList.toggle("is-muted", t.mute);
    li.innerHTML = `<span class="avatar tab-fav"${t.icon ? ` style="background-image:url('${esc(t.icon)}')"` : ""}>${t.icon ? "" : icon("globe")}</span>
      <span class="person-name"><span class="tab-title">${esc(t.title || t.host)}</span></span>`;
    const mute = document.createElement("button");
    mute.className = "key key-small person-mute";
    mute.setAttribute("aria-pressed", String(t.mute));
    mute.setAttribute("aria-label", `Mutar a aba ${t.title}`);
    mute.innerHTML = icon(t.mute ? "volume-x" : "volume-2");
    mute.addEventListener("click", () => send({ t: "tabmute", id: t.id, m: !t.mute }));
    let vol;
    if (t.ctrl) {
      vol = hslider(Math.round(t.vol * 100), 100, (v) => send({ t: "tabvol", id: t.id, v: v / 100 }), `Volume da aba ${t.title}`);
    } else {
      vol = document.createElement("span");
      vol.className = "tab-hint";
      vol.textContent = "Dê F5 nessa aba pra controlar o volume";
    }
    li.append(vol, mute);
    ul.append(li);
  }
  return ul;
}

// ------------------------------------------------------------ painel: quais faders aparecem
const appName = (id) => nm(id, mix?.channels.find((c) => c.id === id)?.name || id.replace(/\.exe$/, ""));

function fadersSig() {
  return JSON.stringify([mix?.channels.map((c) => c.id), mix?.devices.map((d) => d.id), tabsState.tabs.map(siteKey), cfg]);
}

// Painel "Canais": olho pra mostrar/esconder o fader e lápis pra dar outro nome.
function renderFaders() {
  head("Mixer", "Canais", icon("eye"));
  pFoot.replaceChildren();
  panel.fadersSig = fadersSig();
  panel.renaming = false;
  const list = (rows, canHide = true) => {
    const box = document.createElement("div");
    box.className = "pop-list";
    for (const r of rows) {
      const row = document.createElement("div");
      row.className = "ch-row";
      const label = `<span>${esc(nm(r.key, r.label))}${r.sub || cfg[r.key]?.name ? `<small>${esc(r.sub || r.label)}</small>` : ""}</span>`;
      const b = document.createElement("button");
      b.className = "opt opt-eye";
      if (canHide) {
        const on = !hidden.has(r.key);
        b.setAttribute("aria-pressed", String(on));
        b.setAttribute("aria-label", `${on ? "Esconder" : "Mostrar"} ${nm(r.key, r.label)}`);
        b.innerHTML = `<i class="led"></i>${label}${icon(on ? "eye" : "eye-off")}`;
        b.addEventListener("click", () => { setHidden(r.key, on); renderSlot("faders"); });
      } else {
        b.setAttribute("aria-pressed", "true");
        b.disabled = true;
        b.innerHTML = label;
      }
      const pen = document.createElement("button");
      pen.className = "key key-small ch-rename";
      pen.setAttribute("aria-label", `Renomear ${nm(r.key, r.label)}`);
      pen.innerHTML = icon("pencil");
      pen.addEventListener("click", () => renameRow(row, r));
      row.append(b, pen);
      box.append(row);
    }
    return box;
  };
  const apps = (mix?.channels || []).map((c) => ({ key: c.id, label: c.name }));
  // escondidos que não estão tocando agora: ficam aqui pra dar pra mostrar de novo
  const away = [...hidden].filter((k) => !k.startsWith("site:") && k !== "master" && !apps.some((a) => a.key === k))
    .map((k) => ({ key: k, label: k.replace(/\.exe$/, ""), sub: "sem som agora" }));
  const sites = new Map();
  for (const t of tabsState.tabs) if (!sites.has(siteKey(t))) sites.set(siteKey(t), { key: siteKey(t), label: siteName(t.host), sub: t.host });
  for (const k of hidden) if (k.startsWith("site:") && !sites.has(k)) sites.set(k, { key: k, label: siteName(k.slice(5)), sub: "sem som agora" });
  const parts = [section("Geral"), list([{ key: "master", label: "Main" }])];
  parts.push(section("Apps", apps.length), list([...apps, ...away]));
  parts.push(section(`Abas · ${tabsState.browser ? appName(tabsState.browser) : "navegador"}`, sites.size || null));
  if (sites.size) parts.push(list([...sites.values()]));
  else {
    const n = document.createElement("div");
    n.className = "panel-note";
    n.textContent = "Nenhuma aba com som agora. As abas aparecem aqui e no mixer quando tocam (precisa da extensão da Mesa).";
    parts.push(n);
  }
  const dcm = panel.data.discord?.channel ? panel.data.discord.members || [] : [];
  if (dcm.length) parts.push(section("Call do Discord", dcm.length), list(dcm.map((m) => ({ key: `dc:${m.id}`, label: m.name }))));
  if (mix?.mics?.length) parts.push(section("Microfones", mix.mics.length), list(mix.mics.map((m) => ({ key: m.id, label: m.short }))));
  if (mix?.devices.length) parts.push(section("Saídas", mix.devices.length), list(mix.devices.map((d) => ({ key: d.id, label: d.short })), false));
  const tip = document.createElement("div");
  tip.className = "panel-note";
  tip.textContent = "Fica salvo no notebook (config/channels.json). Nome vazio volta pro original.";
  parts.push(tip);
  pBody.replaceChildren(...parts);
}

// troca a linha por um campo de texto; Enter ou sair do campo salva, Esc desiste
function renameRow(row, r) {
  panel.renaming = true;
  const input = document.createElement("input");
  input.className = "ch-input";
  input.value = cfg[r.key]?.name || "";
  input.placeholder = r.label;
  input.maxLength = 40;
  input.setAttribute("aria-label", `Novo nome pra ${r.label}`);
  input.enterKeyHint = "done";
  let done = false;
  const finish = (save) => {
    if (done) return;
    done = true;
    const v = input.value.trim();
    if (save && v !== (cfg[r.key]?.name || "")) setName(r.key, v === r.label ? "" : v);
    renderSlot("faders");
  };
  input.addEventListener("keydown", (e) => {
    if (e.key === "Enter") { e.preventDefault(); finish(true); }
    else if (e.key === "Escape") finish(false);
  });
  input.addEventListener("blur", () => finish(true));
  row.replaceChildren(input);
  input.focus();
  input.select();
}

// ------------------------------------------------------------ atualização
// Versão nova no repositório: aparece a tecla de atualizar no rodapé (LED aceso). Tocar roda o
// Atualizar.bat no PC; a Mesa reinicia e o tablet recarrega sozinho.
let updSeen = false;
function renderUpd(d) {
  const b = $("dock-update");
  b.hidden = !d?.behind;
  b.title = d?.behind ? `${d.behind} novidade${d.behind > 1 ? "s" : ""} pra baixar` : "";
  if (d?.behind && !updSeen) { updSeen = true; toast("Tem versão nova\nda Mesa"); }
  if (d?.ext) toast("A extensão mudou:\nrecarregue no navegador");
}
$("dock-update").addEventListener("click", () => {
  send({ t: "update" });
  $("dock-update").classList.add("is-busy");
  toast("Atualizando…\njá volta");
});

// ------------------------------------------------------------ rodapé: computador
document.querySelectorAll("[data-system]").forEach((b) => {
  const a = b.dataset.system;
  if (a === "lock") {
    b.addEventListener("click", () => { send({ t: "system", a }); toast("PC bloqueado"); });
    return;
  }
  // reiniciar/desligar: segurar 1,2 s (o anel enche); toque rápido só explica
  let timer = 0, done = false;
  const cancel = () => { clearTimeout(timer); b.classList.remove("is-holding"); };
  b.addEventListener("pointerdown", () => {
    done = false;
    b.classList.add("is-holding");
    timer = setTimeout(() => {
      done = true;
      b.classList.remove("is-holding");
      send({ t: "system", a, confirm: true });
      toast(a === "restart" ? "Reiniciando\no PC" : "Desligando\no PC");
    }, 1200);
  });
  b.addEventListener("pointerup", () => { if (!done) toast(a === "restart" ? "Segure pra\nreiniciar" : "Segure pra\ndesligar"); cancel(); });
  b.addEventListener("pointerleave", cancel);
  b.addEventListener("pointercancel", cancel);
  b.addEventListener("contextmenu", (e) => e.preventDefault());
});

// ------------------------------------------------------------ tablet
async function keepAwake() {
  try { await navigator.wakeLock?.request("screen"); } catch { /* sem suporte */ }
}
document.addEventListener("visibilitychange", () => {
  if (document.visibilityState === "visible") {
    keepAwake();
    connect();
    for (const k of panel.keys) if (FETCHED.has(k)) send({ t: "panel", app: k });
  }
  syncVideo();
});
keepAwake();

if ("serviceWorker" in navigator) navigator.serviceWorker.register("/sw.js").catch(() => {});

// ------------------------------------------------------------ layouts (fase de escolha)
// Toque na marca MESACONTROL pra passar pelos layouts; o escolhido fica salvo neste aparelho.
const LAYOUTS = [
  ["o", "Original"],
  ["a", "A · Barra no topo"],
  ["b", "B · Trilho lateral"],
  ["c", "C · Master à direita"],
  ["d", "D · Palco central"],
  ["e", "E · Painel"],
];
const portrait = matchMedia("(orientation: portrait)");

function setLayout(id) {
  if (!LAYOUTS.some(([k]) => k === id)) id = "o";
  deviceEl.dataset.layout = id;
  // tela "larga" (numa barra) ou "estreita" (numa coluna): muda como o vídeo se arruma
  const wide = id === "a" || id === "b" || (portrait.matches && (id === "o" || id === "c"));
  deviceEl.classList.toggle("lcd-wide", wide);
  store.set("mesa.layout3", id);
  if (mix) renderMix(mix);
}
portrait.addEventListener("change", () => setLayout(deviceEl.dataset.layout));
$("wordmark").addEventListener("click", () => {
  const i = LAYOUTS.findIndex(([k]) => k === deviceEl.dataset.layout);
  const [id, name] = LAYOUTS[(i + 1) % LAYOUTS.length];
  setLayout(id);
  toast(`Layout\n${name}`);
});
setLayout(new URLSearchParams(location.search).get("layout") || store.get("mesa.layout3") || "e");

setMode(store.get("mesa.mode") || "mixer");
setLink(false);
connect();
