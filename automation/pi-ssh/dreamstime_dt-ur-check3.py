#!/usr/bin/env python3
"""Under-review + refused verification using .upload-item cards (b05-proven pattern)."""
import json, sys, time, urllib.request
sys.path.insert(0, "/config/etsy-browser")
from cdp import CDP, nap

def http_put(url, timeout=10):
    req = urllib.request.Request(url, data=b"", method="PUT")
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()

ITEMS_JS = """(function(){
  var out = [];
  Array.prototype.slice.call(document.querySelectorAll('.upload-item')).forEach(function(d){
    var fm = (d.innerText||'').match(/b\\d\\d-\\d+\\.jpg/i);
    if (fm) out.push(fm[0].toLowerCase());
  });
  return out;
})()"""

FIND_TAB_JS = """(function(){
  var out = [];
  Array.prototype.slice.call(document.querySelectorAll('*')).forEach(function(el){
    var t = (el.innerText||'').trim();
    if (/^__TAB__$/i.test(t)) {
      var r = el.getBoundingClientRect();
      if (r.width > 50) out.push({x: r.x+r.width/2, y: r.y+r.height/2});
    }
  });
  return out;
})()"""

def new_tab():
    nt = json.loads(http_put("http://127.0.0.1:9225/json/new?url=about%3Ablank"))
    return CDP(nt["webSocketDebuggerUrl"]), nt["id"]

def close_tab(cdp, tid):
    try: urllib.request.urlopen("http://127.0.0.1:9225/json/close/%s" % tid, timeout=10)
    except Exception: pass
    try: cdp.close()
    except Exception: pass

def real_click(cdp, x, y):
    cdp.call("Input.dispatchMouseEvent", {"type":"mousePressed","x":x,"y":y,"button":"left","clickCount":1})
    time.sleep(0.15)
    cdp.call("Input.dispatchMouseEvent", {"type":"mouseReleased","x":x,"y":y,"button":"left","clickCount":1})

def read_tab(cdp, tabname):
    cdp.navigate("https://www.dreamstime.com/upload")
    nap(5, 6)
    tabs = cdp.evaluate(FIND_TAB_JS.replace("__TAB__", tabname))
    if not tabs:
        return {"tab": tabname, "error": "tab not found"}
    real_click(cdp, tabs[0]["x"], tabs[0]["y"])
    # wait for cards to load (AJAX)
    files = []
    for _ in range(12):
        nap(2, 3)
        files = cdp.evaluate(ITEMS_JS)
        if files:
            break
    st = cdp.evaluate("(function(){return {url:location.href, signedIn:/tangziyi001/i.test(document.body?document.body.innerText:'')};})()")
    return {"tab": tabname, "url": st["url"], "n": len(files), "files": sorted(files), "signedIn": st["signedIn"]}

cdp, tid = new_tab()
try:
    ur = read_tab(cdp, "Under review")
    print("UNDER-REVIEW:", json.dumps(ur)[:800])
    rf = read_tab(cdp, "Refused files")
    print("REFUSED:", json.dumps(rf)[:800])
finally:
    close_tab(cdp, tid)
print("DONE_MARKER")
