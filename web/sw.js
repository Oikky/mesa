// Guarda a "casca" do app pra abrir rápido; dados ao vivo sempre vêm do WebSocket.
const CACHE = "mesa-v4";
const SHELL = ["/", "/styles.css", "/app.js", "/manifest.webmanifest", "/icons/sprite.svg", "/icons/icon-192.png",
  "/fonts/inter-latin-400-normal.woff2", "/fonts/inter-latin-500-normal.woff2", "/fonts/inter-latin-600-normal.woff2",
  "/fonts/ibm-plex-mono-latin-500-normal.woff2", "/fonts/silkscreen-latin-400-normal.woff2"];

self.addEventListener("install", (e) => {
  e.waitUntil(caches.open(CACHE).then((c) => c.addAll(SHELL)).then(() => self.skipWaiting()));
});

self.addEventListener("activate", (e) => {
  e.waitUntil(caches.keys()
    .then((keys) => Promise.all(keys.filter((k) => k !== CACHE).map((k) => caches.delete(k))))
    .then(() => self.clients.claim()));
});

// rede primeiro (pra pegar atualizações), cache se o notebook estiver fora
self.addEventListener("fetch", (e) => {
  const url = new URL(e.request.url);
  if (e.request.method !== "GET" || url.origin !== location.origin) return;
  if (url.pathname.startsWith("/art/") || url.pathname.startsWith("/icon/")) return;
  e.respondWith(
    // sempre confere com o notebook (sem cache do navegador no meio)
    fetch(e.request.mode === "navigate" ? e.request : new Request(e.request, { cache: "no-cache" }))
      .then((res) => {
        const copy = res.clone();
        caches.open(CACHE).then((c) => c.put(e.request, copy));
        return res;
      })
      .catch(() => caches.match(e.request))
  );
});
