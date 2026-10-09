#!/usr/bin/env python3
"""Online-files census + statistics page."""
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
    nap(4, 5)

cdp, tid = new_tab()
try:
    st = visit(cdp, "https://www.dreamstime.com/account/statistics")
    txt = cdp.evaluate("document.body ? document.body.innerText.slice(0, 3000) : ''")
    print("STATISTICS text:")
    print(txt[:1500])
    print("=====")
    st2 = visit(cdp, "https://www.dreamstime.com/account/online-files")
    txt2 = cdp.evaluate("""(function(){
      var txt = document.body ? document.body.innerText.slice(0, 6000) : '';
      var fns = [];
      var re = /b\\d\\d-\\d+\\.jpg/gi, m;
      while ((m = re.exec(txt)) !== null) { if (fns.indexOf(m[0].toLowerCase()) < 0) fns.push(m[0].toLowerCase()); }
      var cnt = null;
      var cm = txt.match(/(\\d[\\d,]*)\\s*(?:online\\s*files?|files?\\s*online)/i);
      if (cm) cnt = cm[1];
      return {url: location.href, title: document.title, countHint: cnt, b09: fns, head: txt.slice(0, 500)};
    })()""")
    print("ONLINE url:", txt2["url"])
    print("ONLINE countHint:", txt2["countHint"])
    print("ONLINE b09 found:", len(txt2["b09"]), json.dumps(sorted(txt2["b09"]))[:400])
    print("head:", repr(txt2["head"][:400]))
finally:
    close_tab(cdp, tid)
print("DONE_MARKER")
