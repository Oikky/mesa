// Roda no mundo da página do YouTube: lê a fila/playlist/"a seguir" dos dados que o próprio
// YouTube carrega (ytd-watch-flexy.data). Não depende do que está desenhado na tela (a coluna da
// direita só monta aos poucos e nem monta em aba de fundo). O content.js pede por um evento e
// recebe a resposta na hora (JSON em texto, porque objeto não atravessa de um mundo pro outro).
(() => {
  const txt = (t) => (typeof t === "string" ? t : "") || t?.simpleText || t?.content || (t?.runs || []).map((r) => r.text).join("") || "";

  function read() {
    const d = document.querySelector("ytd-watch-flexy")?.data || window.ytInitialData;
    const two = d?.contents?.twoColumnWatchNextResults;
    if (!two) return null;
    const pl = two.playlist?.playlist;
    if (pl?.contents?.length) {
      const all = pl.contents.map((c) => c.playlistPanelVideoRenderer).filter(Boolean);
      const at = Math.max(0, all.findIndex((v) => v.selected));
      return {
        kind: "playlist", title: txt(pl.title) || "Playlist",
        items: all.slice(Math.max(0, at - 8), at + 32).map((v) => ({
          id: v.videoId, title: txt(v.title), sub: txt(v.shortBylineText || v.longBylineText), current: !!v.selected,
        })),
      };
    }
    const cur = new URL(location.href).searchParams.get("v");
    const res = (two.secondaryResults?.secondaryResults?.results || [])
      .flatMap((r) => (r.itemSectionRenderer ? r.itemSectionRenderer.contents || [] : [r]));
    const items = [];
    for (const r of res) {
      const lv = r.lockupViewModel;
      if (lv && lv.contentType === "LOCKUP_CONTENT_TYPE_VIDEO") {
        const md = lv.metadata?.lockupMetadataViewModel;
        const rows = md?.metadata?.contentMetadataViewModel?.metadataRows || [];
        items.push({ id: lv.contentId, title: txt(md?.title), sub: txt(rows[0]?.metadataParts?.[0]?.text), current: false });
      }
      const cv = r.compactVideoRenderer;
      if (cv) items.push({ id: cv.videoId, title: txt(cv.title), sub: txt(cv.longBylineText || cv.shortBylineText), current: false });
    }
    const list = items.filter((i) => i.id && i.id !== cur && i.title).slice(0, 20);
    return list.length ? { kind: "next", title: "A seguir", items: list } : null;
  }

  document.addEventListener("__mesa_ytq_req", () => {
    let out = null;
    try { out = read(); } catch { /* formato mudou: o content.js usa a tela */ }
    document.dispatchEvent(new CustomEvent("__mesa_ytq", { detail: JSON.stringify(out) }));
  });
})();
