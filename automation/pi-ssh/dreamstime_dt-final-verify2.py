#!/usr/bin/env python3
"""Under-review census with proper wait loops per page (changepage pager)."""
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

def real_click(cdp, x, y):
    cdp.call("Input.dispatchMouseEvent", {"type":"mousePressed","x":x,"y":y,"button":"left","clickCount":1})
    time.sleep(0.15)
    cdp.call("Input.dispatchMouseEvent", {"type":"mouseReleased","x":x,"y":y,"button":"left","clickCount":1})

FIND_TAB_JS = """(function(){
  var out = [];
  Array.prototype.slice.call(document.querySelectorAll('*')).forEach(function(el){
    var t = (el.innerText||'').trim();
    if (/^under review$/i.test(t)) {
      var r = el.getBoundingClientRect();
      if (r.width > 50) out.push({x: r.x+r.width/2, y: r.y+r.height/2});
    }
  });
  return out;
})()"""

ITEMS_JS = """(function(){
  var out = [];
  Array.prototype.slice.call(document.querySelectorAll('.upload-item')).forEach(function(d){
    var fm = (d.innerText||'').match(/b\\d\\d-\\d+\\.jpg/i);
    if (fm) out.push(fm[0].toLowerCase());
  });
  return out;
})()"""

PAGEMAX_JS = """(function(){
  var inp = document.querySelector('input.changepage');
  return inp ? parseInt(inp.getAttribute('max') || inp.max || '1', 10) : 1;
})()"""

GOTO_JS = """(function(p){
  var inp = document.querySelector('input.changepage');
  if (!inp) return false;
  var desc = Object.getOwnPropertyDescriptor(inp, 'value');
  if (desc && desc.set) desc.set.call(inp, String(p)); else inp.value = String(p);
  inp.dispatchEvent(new Event('input', {bubbles:true}));
  inp.dispatchEvent(new KeyboardEvent('keydown', {key:'Enter', keyCode:13, bubbles:true}));
  inp.dispatchEvent(new KeyboardEvent('keyup', {key:'Enter', keyCode:13, bubbles:true}));
  return true;
})()"""

def read_items_wait(cdp, timeout=30):
    t0 = time.time()
    items = []
    while time.time() - t0 < timeout:
        items = cdp.evaluate(ITEMS_JS)
        if items:
            break
        time.sleep(2)
    return items

cdp, tid = new_tab()
try:
    cdp.navigate("https://www.dreamstime.com/upload")
    nap(5, 6)
    tabs = cdp.evaluate(FIND_TAB_JS)
    real_click(cdp, tabs[0]["x"], tabs[0]["y"])
    nap(5, 6)
    pmax = cdp.evaluate(PAGEMAX_JS)
    print("under-review pages:", pmax)
    seen = set()
    pages = {}
    for pg in range(1, pmax + 1):
        if pg > 1:
            cdp.evaluate(GOTO_JS.replace("(p)", "(%d)" % pg))
            nap(4, 5)
        items = read_items_wait(cdp)
        pages[pg] = len(items)
        seen.update(items)
        print("page %d: %d items" % (pg, len(items)))
    b09 = sorted(f for f in seen if f.startswith("b09"))
    print("TOTAL under-review:", len(seen), "b09:", len(b09))
    print("b09:", json.dumps(b09))
    missing = ["b09-%02d.jpg" % i for i in range(1, 21) if "b09-%02d.jpg" % i not in b09]
    print("b09 MISSING:", json.dumps(missing))
finally:
    close_tab(cdp, tid)
print("DONE_MARKER")
