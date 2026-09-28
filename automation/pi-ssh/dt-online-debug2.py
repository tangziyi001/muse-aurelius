#!/usr/bin/env python3
import json, sys, urllib.request, urllib.parse
sys.path.insert(0, "/config/etsy-browser")
from cdp import CDP, nap, wait_for_js
PORT = 9225

def new_tab(url):
    q = urllib.parse.quote(url, safe='')
    req = urllib.request.Request("http://127.0.0.1:%d/json/new?%s" % (PORT, q), method="PUT")
    with urllib.request.urlopen(req, timeout=15) as r:
        return json.loads(r.read())["webSocketDebuggerUrl"]

ws = new_tab("https://www.dreamstime.com/account/online-files?orderc=&itemstype=all&orderm=&srch=&pg=1")
cdp = CDP(ws)
try:
    wait_for_js(cdp, "document.readyState === 'complete'", timeout=60)
    nap(2, 3)
    t = cdp.evaluate("document.body ? document.body.innerText : ''")
    i = t.find("File ID")
    print(repr(t[i-160:i+220]))
finally:
    cdp.close()
