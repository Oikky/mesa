"""Vídeo do YouTube que está tocando no notebook (vem da extensão em extension/).

A extensão manda, de cada aba do YouTube: id do vídeo, tempo atual, velocidade, se está tocando
e se é propaganda. O tablet abre o mesmo vídeo, mudo, e vai seguindo esse tempo.
"""
import time

STALE = 75  # s sem notícia de uma aba = ela fechou ou saiu do YouTube


class Video:
    def __init__(self):
        self.tabs = {}    # id da aba -> estado + "at" (monotonic de quando chegou)
        self.queues = {}  # id da aba -> fila/playlist lida da página

    def update(self, msg):
        tab = msg.get("tab")
        if tab is None:
            return
        if msg.get("kind") == "queue":
            q = msg.get("list") or {}
            self.queues[tab] = {
                "title": str(q.get("title") or "")[:200],
                "kind": q.get("kind") if q.get("kind") in ("playlist", "next", "queue") else "next",
                "items": [{"id": str(i.get("id") or "")[:20], "title": str(i.get("title") or "")[:200],
                           "sub": str(i.get("sub") or "")[:120], "current": bool(i.get("current"))}
                          for i in (q.get("items") or [])[:40] if i.get("id")],
            }
            return
        if msg.get("gone") or not msg.get("id"):
            self.tabs.pop(tab, None)
            self.queues.pop(tab, None)
            return
        self.tabs[tab] = {
            "id": str(msg["id"])[:20],
            "t": float(msg.get("t") or 0),
            "dur": float(msg.get("dur") or 0),
            "rate": float(msg.get("rate") or 1),
            "playing": bool(msg.get("playing")),
            "ad": bool(msg.get("ad")),
            "title": str(msg.get("title") or "")[:300],
            "at": time.monotonic(),
        }

    def prune(self):
        now = time.monotonic()
        gone = [k for k, v in self.tabs.items() if now - v["at"] > STALE]
        for k in gone:
            del self.tabs[k]
            self.queues.pop(k, None)
        return bool(gone)

    def best_tab(self):
        if not self.tabs:
            return None
        return max(self.tabs, key=lambda k: (self.tabs[k]["playing"], self.tabs[k]["at"]))

    def queue(self):
        tab = self.best_tab()
        q = self.queues.get(tab) if tab is not None else None
        return {**q, "tab": tab} if q else None

    def snapshot(self):
        """A aba que importa: a que está tocando (a mais recente), senão a última que mexeu."""
        if not self.tabs:
            return None
        best = max(self.tabs.values(), key=lambda v: (v["playing"], v["at"]))
        st = {k: v for k, v in best.items() if k != "at"}
        if best["playing"] and not best["ad"]:
            st["t"] = round(best["t"] + (time.monotonic() - best["at"]) * best["rate"], 2)
        return st
