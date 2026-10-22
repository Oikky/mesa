"""Abas do navegador com som (vem da extensão em extension/).

A extensão manda a lista inteira sempre que algo muda: cada aba com título, site, favicon,
volume (0..1, aplicado dentro da página), mute (o mute nativo da aba) e se o script da Mesa
está rodando nela (aba aberta antes de instalar/recarregar a extensão só obedece depois de F5).
"""


class Tabs:
    def __init__(self):
        self.browser = None  # .exe do navegador (o canal do mixer onde as abas aparecem)
        self.list = []

    def update(self, msg):
        self.browser = str(msg.get("browser") or "msedge.exe").lower()[:40]
        tabs = []
        for t in (msg.get("tabs") or [])[:30]:
            try:
                tab = int(t["tab"])
            except (KeyError, TypeError, ValueError):
                continue
            icon = str(t.get("icon") or "")
            tabs.append({
                "id": f"tab:{tab}",
                "tab": tab,
                "title": str(t.get("title") or "")[:200],
                "host": str(t.get("host") or "")[:100],
                "icon": icon if len(icon) <= 30000 else "",
                "vol": min(1.0, max(0.0, float(t.get("v") if t.get("v") is not None else 1))),
                "mute": bool(t.get("mute")),
                "audible": bool(t.get("audible")),
                "ctrl": bool(t.get("ctrl")),
                "sink": str(t["sink"])[:200] if t.get("sink") else None,  # nome da saída escolhida
                "sinkSt": str(t.get("sinkSt") or "")[:20] or None,       # ok, perm, denied, notfound
            })
        self.list = tabs

    def get(self, ident):
        return next((t for t in self.list if t["id"] == ident), None)

    def snapshot(self):
        return {"browser": self.browser, "tabs": self.list}
