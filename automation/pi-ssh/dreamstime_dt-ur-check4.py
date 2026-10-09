#!/usr/bin/env python3
"""Under-review page-2 check + refused tab with broad filename match."""
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

ITEMS_ANY_JS = """(function(){
  var out = [];
  Array.prototype.slice.call(document.querySelectorAll('.upload-item')).forEach(function(d){
    var t = d.innerText || '';
    var fm = t.match(/[a-z0-9_\\-]+\\.jpg/i);
    if (fm) out.push({f: fm[0].toLowerCase(), head: t.slice(0, 220)});
  });
  return out;
})()"""

PAGER_JS = """(function(){
  var a = document.getElementById('js-next');
  if (!a) return null;
  var r = a.getBoundingClientRect();
  return {x: r.x+r.width/2, y: r.y+r.height/2};
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

def goto_tab(cdp, tabname):
    cdp.navigate("https://www.dreamstime.com/upload")
    nap(5, 6)
    tabs = cdp.evaluate(FIND_TAB_JS.replace("__TAB__", tabname))
    if not tabs: return False
    real_click(cdp, tabs[0]["x"], tabs[0]["y"])
    nap(4, 5)
    return True

cdp, tid = new_tab()
try:
    # under-review page 2
    goto_tab(cdp, "Under review")
    p1 = cdp.evaluate(ITEMS_JS)
    print("UR page1:", len(p1), sorted(p1))
    nxt = cdp.evaluate(PAGER_JS)
    print("pager next:", json.dumps(nxt)[:80] if nxt else None)
    if nxt:
        real_click(cdp, nxt["x"], nxt["y"])
        nap(6, 8)
        p2 = cdp.evaluate(ITEMS_JS)
        print("UR page2:", len(p2), sorted(p2))
    # refused tab, broad match
    goto_tab(cdp, "Refused files")
    items = []
    for _ in range(8):
        nap(2, 3)
        items = cdp.evaluate(ITEMS_ANY_JS)
        if items: break
    print("REFUSED n:", len(items))
    for it in items[:10]:
        print(" ", it["f"], "|", it["head"].replace("\n", " ")[:200])
finally:
    close_tab(cdp, tid)
print("DONE_MARKER")
