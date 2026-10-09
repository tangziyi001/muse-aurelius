#!/usr/bin/env python3
"""Under-review changepage pager + refused tab text dump."""
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
    if (/^__TAB__$/i.test(t)) {
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

PAGER_INFO_JS = """(function(){
  var inp = document.querySelector('input.changepage');
  var info = {hasInput: !!inp};
  if (inp) { info.val = inp.value; info.max = inp.getAttribute('max') || inp.max || null; }
  var txt = document.body ? document.body.innerText.slice(0, 3000) : '';
  var m = txt.match(/page\\s*\\d+\\s*of\\s*\\d+/i);
  info.pageText = m ? m[0] : null;
  var m2 = txt.match(/(\\d+)\\s*(?:files?|images?|items?)/i);
  info.countHint = m2 ? m2[0] : null;
  return info;
})()"""

cdp, tid = new_tab()
try:
    cdp.navigate("https://www.dreamstime.com/upload")
    nap(5, 6)
    tabs = cdp.evaluate(FIND_TAB_JS.replace("__TAB__", "Under review"))
    real_click(cdp, tabs[0]["x"], tabs[0]["y"])
    nap(5, 6)
    print("PAGER:", json.dumps(cdp.evaluate(PAGER_INFO_JS)))
    # try changepage input -> page 2
    r = cdp.evaluate("""(function(){
      var inp = document.querySelector('input.changepage');
      if (!inp) return {ok:false};
      var desc = Object.getOwnPropertyDescriptor(inp, 'value');
      if (desc && desc.set) desc.set.call(inp, '2'); else inp.value = '2';
      inp.dispatchEvent(new Event('input', {bubbles:true}));
      inp.dispatchEvent(new KeyboardEvent('keydown', {key:'Enter', keyCode:13, bubbles:true}));
      inp.dispatchEvent(new KeyboardEvent('keyup', {key:'Enter', keyCode:13, bubbles:true}));
      return {ok:true};
    })()""")
    print("changepage->2:", json.dumps(r))
    nap(6, 8)
    p2 = cdp.evaluate(ITEMS_JS)
    print("UR page2 files:", len(p2), sorted(p2))
    print("PAGER after:", json.dumps(cdp.evaluate(PAGER_INFO_JS)))
    # refused tab text dump
    cdp.navigate("https://www.dreamstime.com/upload")
    nap(5, 6)
    rtabs = cdp.evaluate(FIND_TAB_JS.replace("__TAB__", "Refused files"))
    real_click(cdp, rtabs[0]["x"], rtabs[0]["y"])
    nap(6, 8)
    rd = cdp.evaluate("""(function(){
      var txt = document.body ? document.body.innerText.slice(0, 4000) : '';
      var cards = document.querySelectorAll('.upload-item, [class*=item], .thumb, figure').length;
      return {url: location.href, cards: cards, text: txt.slice(0, 1200)};
    })()""")
    print("REFUSED url:", rd["url"], "cards:", rd["cards"])
    print("REFUSED text:", repr(rd["text"][:900]))
finally:
    close_tab(cdp, tid)
print("DONE_MARKER")
