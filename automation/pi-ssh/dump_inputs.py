#!/usr/bin/env python3
"""Dump all text inputs and their nearby labels on the page (visible only)."""
import sys, json, urllib.request
sys.path.insert(0, "/config/etsy-browser")
from cdp import CDP

targets = json.loads(urllib.request.urlopen("http://127.0.0.1:9224/json/list", timeout=8).read())
pages = [t for t in targets if t.get("type") == "page" and "employment-history" in t.get("url", "")]
c = CDP(pages[0]["webSocketDebuggerUrl"])

JS = """
(function(){
  try {
    var out = [];
    var inputs = document.querySelectorAll('input[type=text], input:not([type])');
    for (var i=0;i<inputs.length;i++){
      var inp = inputs[i];
      var r = inp.getBoundingClientRect();
      if (r.width===0 || r.height===0) continue;
      // find label text: check parent, previous sibling, or associated label
      var labelText = '';
      var p = inp.parentElement;
      if (p){
        var lab = p.querySelector('label');
        if (lab) labelText = (lab.innerText||'').trim().substring(0,40);
        if (!labelText){
          var prev = inp.previousElementSibling;
          if (prev) labelText = (prev.innerText||'').trim().substring(0,40);
        }
      }
      var lbl = inp.closest('label');
      if (lbl && !labelText) labelText = (lbl.innerText||'').trim().substring(0,40);
      out.push('['+labelText+'] value="'+(inp.value||'').substring(0,25)+'"');
    }
    return out.join('\\n');
  } catch(e){ return 'err:'+e.message; }
})
"""
try:
    r = c.evaluate(JS, timeout=20)
    print(r if r else "(empty)")
except Exception as e:
    print("FAIL:", str(e)[:100])
c.close()
