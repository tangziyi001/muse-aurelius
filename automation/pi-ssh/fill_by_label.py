#!/usr/bin/env python3
"""Fill a text input by label text, ONLY within the visible open form/modal.
Finds the label containing <label_text>, then the input right after it in the same form.
Usage: fill_by_label.py <label_substring> <value>"""
import sys, json, urllib.request
sys.path.insert(0, "/config/etsy-browser")
from cdp import CDP

label_sub = sys.argv[1]
value = sys.argv[2]

targets = json.loads(urllib.request.urlopen("http://127.0.0.1:9224/json/list", timeout=8).read())
pages = [t for t in targets if t.get("type") == "page" and "employment-history" in t.get("url", "")]
c = CDP(pages[0]["webSocketDebuggerUrl"])

JS = """
(function(LABEL, VAL){
  try {
    function fire(el, type){
      try { el.dispatchEvent(new Event(type, {bubbles:true})); } catch(_){}
      var e = document.createEvent('HTMLEvents');
      e.initEvent(type, true, true);
      el.dispatchEvent(e);
    }
    // Find the visible modal (the open form)
    var modals = document.querySelectorAll('[role=dialog], .modal-content, .popup-content');
    var form = null;
    for (var i=0;i<modals.length;i++){
      var r = modals[i].getBoundingClientRect();
      if (r.width > 100 && r.height > 100 && r.top < window.innerHeight && r.bottom > 0){
        form = modals[i]; break;
      }
    }
    if (!form){
      // fallback: find container with the label that's visible
      var all = document.querySelectorAll('*');
      for (var i=0;i<all.length;i++){
        var t = (all[i].innerText||'');
        if (t.indexOf(LABEL)>-1 && t.indexOf('Who is your employer')>-1){
          var r2 = all[i].getBoundingClientRect();
          if (r2.width>200 && r2.height>200){ form = all[i]; break; }
        }
      }
    }
    if (!form) return 'noform';
    // Find label with LABEL text, then the input after it
    var labels = form.querySelectorAll('label');
    for (var i=0;i<labels.length;i++){
      var lt = (labels[i].innerText||'');
      if (lt.indexOf(LABEL)>-1){
        var inp = labels[i].querySelector('input');
        if (!inp){
          var sib = labels[i].nextElementSibling;
          if (sib) inp = sib.querySelector('input') || (sib.tagName==='INPUT'?sib:null);
        }
        if (!inp){
          // try parent container
          var p = labels[i].parentElement;
          if (p) inp = p.querySelector('input[type=text], input:not([type])');
        }
        if (inp){
          inp.focus(); inp.value = VAL; fire(inp,'input'); fire(inp,'change');
          return 'filled:'+VAL;
        }
        return 'noinput';
      }
    }
    return 'nolabel';
  } catch(e){ return 'err:'+e.message; }
})
"""
try:
    r = c.evaluate("(%s)(%s,%s)" % (JS, json.dumps(label_sub), json.dumps(value)), timeout=20)
    print(r)
except Exception as e:
    print("FAIL:", str(e)[:100])
c.close()
