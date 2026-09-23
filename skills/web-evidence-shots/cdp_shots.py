#!/usr/bin/env python3
"""Capture full-page screenshots via CDP for the 8 evidence URLs."""
import json, time, base64, urllib.request, sys
import websocket

URLS = [
    ("1-aitana-fastcompany", "https://www.fastcompany.com/91546466/she-has-400000-instagram-followers-and-major-brand-deals-shes-also-ai"),
    ("2-aitana-livemint", "https://www.livemint.com/ai/artificial-intelligence/we-created-a-monster-meet-spains-first-ai-model-who-earns-upto-9-lakh-per-month-11700969097600.html"),
    ("3-emily-hart-wiki", "https://en.wikipedia.org/wiki/Emily_Hart_(virtual_influencer)"),
    ("4-biracial-psypost", "https://www.psypost.org/evolutionary-psychology-study-finds-biracial-individuals-are-perceived-more-positively-across-cultures/"),
    ("5-similarity-mdpi", "https://www.mdpi.com/2071-1050/17/13/6187"),
    ("6-frontiers-virtual-idol", "https://www.frontiersin.org/journals/psychology/articles/10.3389/fpsyg.2026.1854829/full"),
    ("7-meta-borderline-aubrium", "https://aubrium.com/blog/meta-borderline-content-reduced-distribution"),
    ("8-creator-guide", "https://github.com/thaddeusmercy/thaddeus-fe/blob/HEAD/components/guides/ai-influencer-three-files/content/growth.md"),
]

OUT = "/tmp/shots2"
import os
os.makedirs(OUT, exist_ok=True)

def new_target():
    req = urllib.request.Request("http://127.0.0.1:9222/json/new", method="PUT")
    with urllib.request.urlopen(req, timeout=20) as r:
        return json.load(r)["webSocketDebuggerUrl"]

class CDP:
    def __init__(self, ws_url):
        self.ws = websocket.create_connection(ws_url, timeout=60)
        self.i = 0
    def cmd(self, method, params=None, timeout=60):
        self.i += 1
        self.ws.send(json.dumps({"id": self.i, "method": method, "params": params or {}}))
        end = time.time() + timeout
        while time.time() < end:
            m = json.loads(self.ws.recv())
            if m.get("id") == self.i:
                if "error" in m:
                    raise RuntimeError(f"{method}: {m['error']}")
                return m.get("result", {})
        raise TimeoutError(method)
    def close(self):
        self.ws.close()

for name, url in URLS:
    print(f"--- {name}", flush=True)
    try:
        ws_url = new_target()
        cdp = CDP(ws_url)
        cdp.cmd("Page.enable")
        cdp.cmd("Page.navigate", {"url": url})
        # wait for load: poll readyState + network quiet-ish
        for _ in range(40):
            time.sleep(1.5)
            r = cdp.cmd("Runtime.evaluate", {"expression": "document.readyState + '|' + document.title", "returnByValue": True})
            v = r["result"]["value"]
            print(f"    ready={v}", flush=True)
            if v.startswith("complete|"):
                time.sleep(3)  # let late JS settle
                break
        m = cdp.cmd("Page.getLayoutMetrics")
        h = int(m["cssContentSize"]["height"]) if "cssContentSize" in m else int(m["contentSize"]["height"])
        h = min(max(h, 600), 12000)
        print(f"    height={h}", flush=True)
        cdp.cmd("Emulation.setDeviceMetricsOverride", {"width": 1280, "height": h, "deviceScaleFactor": 1, "mobile": False})
        time.sleep(1)
        shot = cdp.cmd("Page.captureScreenshot", {"format": "png"}, timeout=120)
        data = base64.b64decode(shot["data"])
        p = f"{OUT}/{name}.png"
        open(p, "wb").write(data)
        print(f"    OK {p} {len(data)} bytes", flush=True)
        cdp.cmd("Page.close")
        cdp.close()
    except Exception as e:
        print(f"    ERROR {e}", flush=True)
print("done")
