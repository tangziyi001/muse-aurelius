#!/usr/bin/env python3
"""One-off: screenshot the Dreamstime wall state for the 2026-10-31 watch."""
import json, sys, urllib.request
sys.path.insert(0, "/config/etsy-browser")
from cdp import CDP, nap

def http_put(url, timeout=10):
    req = urllib.request.Request(url, data=b"", method="PUT")
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()

nt = json.loads(http_put("http://127.0.0.1:9225/json/new?url=about%3Ablank"))
cdp = CDP(nt["webSocketDebuggerUrl"])
try:
    cdp.navigate("https://www.dreamstime.com/upload")
    nap(6, 8)
    txt = cdp.evaluate("document.body ? document.body.innerText.slice(0, 400) : ''")
    print("TEXT:", txt[:300].replace("\n", " | "))
    cdp.screenshot("/config/dreamstime-browser/shots/dreamstime-2026-10-31-wall.png")
    print("SHOT_OK")
finally:
    try:
        urllib.request.urlopen("http://127.0.0.1:9225/json/close/%s" % nt["id"], timeout=10)
    except Exception:
        pass
