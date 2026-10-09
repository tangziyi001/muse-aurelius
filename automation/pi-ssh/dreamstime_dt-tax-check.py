#!/usr/bin/env python3
"""Tax center + payout + notifications check."""
import json, sys, time, urllib.request
sys.path.insert(0, "/config/etsy-browser")
from cdp import CDP, nap

def http_put(url, timeout=10):
    req = urllib.request.Request(url, data=b"", method="PUT")
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()

def new_tab():
    nt = json.loads(http_put("http://127.0.0.1:9225/json/new?url=about%3Ablank"))
    return CDP(nt["webSocketDebuggerUrl"]), nt["id"]

def close_tab(cdp, tid):
    try: urllib.request.urlopen("http://127.0.0.1:9225/json/close/%s" % tid, timeout=10)
    except Exception: pass
    try: cdp.close()
    except Exception: pass

def visit(cdp, url):
    cdp.navigate(url)
    t0 = time.time()
    while time.time() - t0 < 30:
        try:
            if cdp.evaluate("document.readyState", timeout=10) == "complete": break
        except Exception: pass
        time.sleep(1)
    nap(3, 4)
    return cdp.evaluate("""(function(){
      var txt = document.body ? document.body.innerText.slice(0, 2500) : '';
      return {url: location.href, title: document.title,
              signedIn: /tangziyi001/i.test(txt), text: txt};
    })()""")

cdp, tid = new_tab()
try:
    for name, url in [("tax", "https://www.dreamstime.com/account/tax-center"),
                      ("payout", "https://www.dreamstime.com/account/request-payment"),
                      ("notifications", "https://www.dreamstime.com/account/notifications")]:
        st = visit(cdp, url)
        print("=== %s (%s) signedIn=%s" % (name, st["url"], st["signedIn"]))
        print(st["text"][:800].replace("\n", " | "))
        print()
finally:
    close_tab(cdp, tid)
print("DONE_MARKER")
