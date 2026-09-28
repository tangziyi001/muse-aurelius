#!/usr/bin/env python3
import json, re, sys, urllib.request, urllib.parse
sys.path.insert(0, "/config/etsy-browser")
from cdp import CDP, nap, wait_for_js
PORT = 9225

def new_tab(url):
    q = urllib.parse.quote(url, safe='')
    req = urllib.request.Request("http://127.0.0.1:%d/json/new?%s" % (PORT, q), method="PUT")
    with urllib.request.urlopen(req, timeout=15) as r:
        return json.loads(r.read())["webSocketDebuggerUrl"]

for attempt in (1, 2):
    ws = new_tab("https://www.dreamstime.com/account/online-files?orderc=&itemstype=all&orderm=&srch=&pg=5")
    cdp = CDP(ws)
    try:
        wait_for_js(cdp, "document.readyState === 'complete'", timeout=60)
        nap(4, 5)
        t = cdp.evaluate("document.body ? document.body.innerText : ''")
        hdr = t[t.find("Showing"):t.find("Showing")+40]
        pairs = re.findall(r"([^\n]{10,200}?)\n\n0 downloads[\s\S]*?File ID (\d+)", t)
        print("attempt", attempt, "hdr:", hdr.replace("\n", " "))
        for title, fid in pairs:
            print("  ", fid, "|", title.strip()[:80])
    finally:
        try:
            cdp.close()
        except Exception:
            pass
