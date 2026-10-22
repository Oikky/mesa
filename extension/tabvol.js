// Ponte entre a extensão e o tabvol-page.js (que roda no mundo da página e não fala com a
// extensão): pergunta o volume desta aba ao abrir e repassa quando o tablet muda.
const pass = (g) => document.dispatchEvent(new CustomEvent("__mesa_gain", { detail: g }));

// saída escolhida: "nome da saída\nask" (ask = pode pedir a permissão de microfone agora)
const sink = (name, ask) => document.dispatchEvent(new CustomEvent("__mesa_sink", { detail: `${name || ""}\n${ask ? "ask" : ""}` }));

chrome.runtime.sendMessage({ kind: "tabvol-hello" }).then((r) => {
  if (r && typeof r.gain === "number") pass(r.gain);
  // página recarregou com uma saída escolhida: aplica de novo (sem pedir permissão sozinha)
  if (r?.sink) sink(r.sink, false);
}).catch(() => { /* extensão recarregada */ });

chrome.runtime.onMessage.addListener((cmd) => {
  if (cmd?.cmd === "tabgain" && typeof cmd.gain === "number") pass(cmd.gain);
  // só o frame principal pode pedir a permissão; os de dentro só aplicam
  if (cmd?.cmd === "tabsink") sink(cmd.name, window === top);
});

document.addEventListener("__mesa_sink_st", (e) => {
  if (window !== top) return;
  try { chrome.runtime.sendMessage({ kind: "tabsink-st", st: String(e.detail) }).catch(() => {}); } catch { /* extensão recarregada */ }
});

// medidor da aba: o tabvol-page.js mede, a extensão junta e manda pra Mesa
document.addEventListener("__mesa_lvl", (e) => {
  const v = Number(e.detail);
  if (!Number.isFinite(v)) return;
  try { chrome.runtime.sendMessage({ kind: "tablvl", v }).catch(() => {}); } catch { /* extensão recarregada */ }
});
