// Roda no mundo da própria página (todas as abas, todos os frames), antes do site.
// Volume da aba = um ganho (0..1) aplicado por cima do que o site faz:
// - <video>/<audio>: o volume real vira (volume que o site pediu × ganho); o site continua
//   lendo o valor dele, então o player do site não percebe nada.
// - WebAudio: tudo que liga no alto-falante do AudioContext passa antes por um GainNode nosso.
// O ganho chega do tabvol.js (mundo isolado da extensão) por um evento no document.
// Medidor: mede o pico do som da aba (depois do volume) e manda pro tabvol.js 10x por segundo.
(() => {
  if (window.__mesaTabVol) return;
  window.__mesaTabVol = true;

  let gain = 1;
  const MP = HTMLMediaElement.prototype;
  const volDesc = Object.getOwnPropertyDescriptor(MP, "volume");
  const siteVol = new WeakMap();   // elemento -> volume que o site pediu
  const viaGraph = new WeakSet();  // elementos ligados num AudioContext (o ganho é aplicado lá)
  const known = new Set();         // WeakRef dos elementos que já tocaram (pega os fora do DOM)

  const apply = (el) => {
    const want = siteVol.has(el) ? siteVol.get(el) : volDesc.get.call(el);
    if (!siteVol.has(el)) siteVol.set(el, want);
    try { volDesc.set.call(el, viaGraph.has(el) ? want : want * gain); } catch { /* fora de 0..1 */ }
  };

  Object.defineProperty(MP, "volume", {
    configurable: true,
    enumerable: volDesc.enumerable,
    get() { return siteVol.has(this) ? siteVol.get(this) : volDesc.get.call(this); },
    set(v) {
      volDesc.set.call(this, v); // valida (lança o mesmo erro que o original)
      siteVol.set(this, Number(v));
      apply(this);
    },
  });

  const play = MP.play;
  MP.play = function (...args) {
    known.add(new WeakRef(this));
    apply(this);
    sinkTo(this);
    return play.apply(this, args);
  };
  // elemento com autoplay não chama play(): pega no evento
  document.addEventListener("play", (e) => {
    if (e.target instanceof HTMLMediaElement) { known.add(new WeakRef(e.target)); apply(e.target); }
  }, true);

  // ---------- medidor dos <video>/<audio>
  // captureStream() dá uma cópia do som do elemento (antes do volume) sem mexer no que toca;
  // ela vai pra um AudioContext só nosso, que não sai no alto-falante.
  const meters = new Set();
  const tapped = new WeakSet();
  let meterCtx = null;
  function meterContext() {
    if (!meterCtx) {
      try { meterCtx = new (window.AudioContext || window.webkitAudioContext)(); } catch { return null; }
    }
    if (meterCtx.state === "suspended") meterCtx.resume().catch(() => {});
    return meterCtx;
  }
  function tap(el) {
    if (tapped.has(el) || viaGraph.has(el) || typeof el.captureStream !== "function") return;
    let stream;
    try { stream = el.captureStream(); } catch { return; } // protegido (DRM) ou outro site
    tapped.add(el);
    const hook = () => {
      if (!stream.getAudioTracks().length) return false;
      const ctx = meterContext();
      if (!ctx) return true;
      try {
        const an = ctx.createAnalyser();
        an.fftSize = 512;
        connect.call(ctx.createMediaStreamSource(stream), an);
        meters.add({
          an, buf: new Float32Array(an.fftSize),
          scale: () => (el.paused || el.muted ? 0 : (siteVol.has(el) ? siteVol.get(el) : 1) * gain),
        });
      } catch { /* sem medidor */ }
      return true;
    };
    if (!hook()) stream.addEventListener("addtrack", function once() { if (hook()) stream.removeEventListener("addtrack", once); });
  }
  document.addEventListener("playing", (e) => { if (e.target instanceof HTMLMediaElement) tap(e.target); }, true);

  let lastSent = 0;
  setInterval(() => {
    if (!meters.size) return;
    let peak = 0;
    for (const m of meters) {
      const k = m.scale();
      if (!k) continue;
      m.an.getFloatTimeDomainData(m.buf);
      let p = 0;
      for (let i = 0; i < m.buf.length; i++) { const v = Math.abs(m.buf[i]); if (v > p) p = v; }
      peak = Math.max(peak, p * k);
    }
    peak = Math.min(1, Math.round(peak * 1000) / 1000);
    if (peak < 0.002 && lastSent < 0.002) return; // silêncio: não manda nada
    lastSent = peak;
    document.dispatchEvent(new CustomEvent("__mesa_lvl", { detail: peak }));
  }, 100);

  // ---------- WebAudio
  const AC = window.AudioContext || window.webkitAudioContext;
  const gains = new WeakMap(); // contexto -> GainNode nosso
  const contexts = new Set();  // WeakRef dos contextos
  const connect = AudioNode.prototype.connect;
  const disconnect = AudioNode.prototype.disconnect;
  const isOffline = (ctx) => typeof OfflineAudioContext !== "undefined" && ctx instanceof OfflineAudioContext;

  function gainFor(ctx) {
    let g = gains.get(ctx);
    if (!g) {
      g = ctx.createGain();
      g.gain.value = gain;
      connect.call(g, ctx.destination);
      gains.set(ctx, g);
      // medidor do WebAudio: escuta depois do nosso ganho (não precisa ligar no alto-falante)
      try {
        const an = ctx.createAnalyser();
        an.fftSize = 512;
        connect.call(g, an);
        meters.add({ an, buf: new Float32Array(an.fftSize), scale: () => 1 });
      } catch { /* sem medidor */ }
      contexts.add(new WeakRef(ctx));
      sinkTo(ctx);
    }
    return g;
  }

  AudioNode.prototype.connect = function (dest, ...rest) {
    if (dest instanceof AudioDestinationNode && !isOffline(dest.context) && this !== gains.get(dest.context)) {
      connect.call(this, gainFor(dest.context), ...rest);
      return dest;
    }
    return connect.call(this, dest, ...rest);
  };
  AudioNode.prototype.disconnect = function (dest, ...rest) {
    if (dest instanceof AudioDestinationNode && gains.has(dest.context) && this !== gains.get(dest.context)) {
      return disconnect.call(this, gains.get(dest.context), ...rest);
    }
    return disconnect.apply(this, arguments);
  };

  if (AC) {
    const mes = AC.prototype.createMediaElementSource;
    if (mes) {
      AC.prototype.createMediaElementSource = function (el) {
        viaGraph.add(el);
        apply(el);
        return mes.call(this, el);
      };
    }
  }

  // ---------- saída de áudio da aba
  // O Edge só mostra os nomes das saídas pra um site com permissão de microfone: na primeira vez
  // que eu escolho uma saída pra um site, ele pede a permissão (uma vez); depois fica liberado.
  let sinkId = "";
  const sinkTo = (target) => {
    if (typeof target.setSinkId !== "function" || target.sinkId === sinkId) return;
    target.setSinkId(sinkId).catch(() => {});
  };
  const report = (st) => document.dispatchEvent(new CustomEvent("__mesa_sink_st", { detail: st }));
  async function setSink(name, ask) {
    if (!name) { sinkId = ""; applySink(); return report("ok"); }
    const md = navigator.mediaDevices;
    if (!md?.enumerateDevices) return report("unsupported");
    const outs = async () => (await md.enumerateDevices()).filter((d) => d.kind === "audiooutput");
    let list = await outs();
    if (!list.some((d) => d.label)) {
      if (!ask) return report("perm");
      try {
        const st = await md.getUserMedia({ audio: true });
        st.getTracks().forEach((t) => t.stop());
      } catch { return report("denied"); }
      list = await outs();
    }
    const low = name.toLowerCase();
    const short = low.includes("(") ? low.slice(low.indexOf("(") + 1, low.lastIndexOf(")")) : low;
    const real = list.filter((d) => d.deviceId !== "default" && d.deviceId !== "communications");
    const dev = real.find((d) => d.label.toLowerCase() === low) || real.find((d) => d.label.toLowerCase().includes(short));
    if (!dev) return report("notfound");
    sinkId = dev.deviceId;
    applySink();
    report("ok");
  }
  function applySink() {
    for (const ref of known) { const el = ref.deref(); if (el) sinkTo(el); }
    document.querySelectorAll("video, audio").forEach(sinkTo);
    for (const ref of contexts) { const ctx = ref.deref(); if (ctx) sinkTo(ctx); }
  }
  document.addEventListener("__mesa_sink", (e) => {
    const [name, ask] = String(e.detail || "").split("\n");
    setSink(name, ask === "ask");
  });

  // ---------- ganho novo
  function setGain(g) {
    gain = Math.min(1, Math.max(0, g));
    for (const ref of known) {
      const el = ref.deref();
      if (el) apply(el); else known.delete(ref);
    }
    document.querySelectorAll("video, audio").forEach(apply);
    for (const ref of contexts) {
      const ctx = ref.deref();
      const g = ctx && gains.get(ctx);
      if (!g) { contexts.delete(ref); continue; }
      try { g.gain.setTargetAtTime(gain, ctx.currentTime, 0.015); } catch { g.gain.value = gain; }
    }
  }
  document.addEventListener("__mesa_gain", (e) => {
    const g = Number(e.detail);
    if (Number.isFinite(g)) setGain(g);
  });
})();
