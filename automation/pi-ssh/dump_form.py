#!/usr/bin/env python3
"""Dump labels and input names in the visible employment form."""
import sys, json, urllib.request
sys.path.insert(0, "/config/etsy-browser")
from cdp import CDP

targets = json.loads(urllib.request.urlopen("http://127.0.0.1:9224/json/list", timeout=8).read())
pages = [t for t in targets if t.get("type") == "page" and "employment-history" in t.get("url", "")]
c = CDP(pages[0]["webSocketDebuggerUrl"])

JS = """
(function(){
  try {
    var modals = document.querySelectorAll('[role=dialog], .modal-content, .popup-content');
    var form = null;
    for (var i=0;i<modals.length;i++){
      var r = modals[i].getBoundingClientRect();
      if (r.width > 100 && r.height > 100){ form = modals[i]; break; }
    }
    if (!form) return 'noform';
    var out = [];
    var labels = form.querySelectorAll('label');
    for (var i=0;i<labels.length;i++){
      out.push('LABEL: ' + (labels[i].innerText||'').trim().substring(0,40));
    }
    var inputs = form.querySelectorAll('input, select');
    for (var i=0;i<inputs.length;i++){
      var inp = inputs[i];
      out.push('INPUT: tag='+inp.tagName+' type='+(inp.type||'')+' name='+(inp.name||'')+' value='+(inp.value||'').substring(0,30));
    }
    return out.join('\\n');
  } catch(e){ return 'err:'+e.message; }
})
"""
try:
    r = c.evaluate(JS, timeout=20)
    print(r)
except Exception as e:
    print("FAIL:", str(e)[:100])
c.close()
