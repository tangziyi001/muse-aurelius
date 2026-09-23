#!/usr/bin/env python3
"""Scroll the employment form down. Usage: scroll_form.py <pixels>"""
import sys, json, urllib.request
sys.path.insert(0, "/config/etsy-browser")
from cdp import CDP

px = int(sys.argv[1]) if len(sys.argv) > 1 else 600

targets = json.loads(urllib.request.urlopen("http://127.0.0.1:9224/json/list", timeout=8).read())
pages = [t for t in targets if t.get("type") == "page" and "employment-history" in t.get("url", "")]
c = CDP(pages[0]["webSocketDebuggerUrl"])

JS = """
(function(PX){
  try {
    var els = document.querySelectorAll('div');
    for (var i=0;i<els.length;i++){
      var t = els[i].textContent || '';
      if (t.indexOf('Who is your employer') > -1 && els[i].scrollHeight > els[i].clientHeight + 30){
        els[i].scrollTop = els[i].scrollTop + PX;
        return 'scrolled:' + PX;
      }
    }
    // fallback: scroll the modal
    var m = document.querySelector('[role=dialog], .modal, .popup');
    if (m) { m.scrollTop = m.scrollTop + PX; return 'scrolled modal'; }
    return 'notfound';
  } catch(e){ return 'err:'+e.message; }
})
"""
try:
    r = c.evaluate("(%s)(%d)" % (JS, px), timeout=15)
    print(r)
except Exception as e:
    print("FAIL:", str(e)[:80])
c.close()
