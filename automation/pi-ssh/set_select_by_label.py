#!/usr/bin/env python3
"""Set a SELECT by its label text, within the visible form. Usage: set_select_by_label.py <label_sub> <option_text_sub>"""
import sys, json, urllib.request
sys.path.insert(0, "/config/etsy-browser")
from cdp import CDP

label_sub = sys.argv[1]
opt_sub = sys.argv[2]

targets = json.loads(urllib.request.urlopen("http://127.0.0.1:9224/json/list", timeout=8).read())
pages = [t for t in targets if t.get("type") == "page" and "employment-history" in t.get("url", "")]
c = CDP(pages[0]["webSocketDebuggerUrl"])

JS = """
(function(LABEL, OPT){
  try {
    function fire(el, type){
      try { el.dispatchEvent(new Event(type, {bubbles:true})); } catch(_){}
      var e = document.createEvent('HTMLEvents');
      e.initEvent(type, true, true);
      el.dispatchEvent(e);
    }
    var labels = document.querySelectorAll('label');
    for (var i=0;i<labels.length;i++){
      var lt = (labels[i].innerText||'');
      if (lt.indexOf(LABEL)===-1) continue;
      var container = labels[i].parentElement;
      var sel = null;
      if (container) sel = container.querySelector('select');
      if (!sel){
        var sib = labels[i].nextElementSibling;
        if (sib && sib.tagName==='SELECT') sel = sib;
      }
      if (!sel && container && container.parentElement){
        sel = container.parentElement.querySelector('select');
      }
      if (sel){
        for (var j=0;j<sel.options.length;j++){
          var ot = sel.options[j].text||'';
          if (ot.toLowerCase().indexOf(OPT.toLowerCase())>-1){
            sel.selectedIndex = j;
            fire(sel,'input'); fire(sel,'change');
            return 'set:'+ot;
          }
        }
        return 'noopt';
      }
    }
    return 'nolabel';
  } catch(e){ return 'err:'+e.message; }
})
"""
try:
    r = c.evaluate("(%s)(%s,%s)" % (JS, json.dumps(label_sub), json.dumps(opt_sub)), timeout=20)
    print(r)
except Exception as e:
    print("FAIL:", str(e)[:100])
c.close()
