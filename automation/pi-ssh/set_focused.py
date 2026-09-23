#!/usr/bin/env python3
"""Set value on ONLY the focused element (document.activeElement). Safe for multi-form pages.
Usage: set_focused.py <select|month> <value>
  select: set select value (e.g. U, E)
  month: set month select by matching option text (e.g. 05, 04, 06)"""
import sys, json, urllib.request
sys.path.insert(0, "/config/etsy-browser")
from cdp import CDP

mode, value = sys.argv[1], sys.argv[2]

targets = json.loads(urllib.request.urlopen("http://127.0.0.1:9224/json/list", timeout=8).read())
pages = [t for t in targets if t.get("type") == "page" and "employment-history" in t.get("url", "")]
c = CDP(pages[0]["webSocketDebuggerUrl"])

if mode == "select":
    JS = """(function(V){
      var el = document.activeElement;
      if (!el || el.tagName !== 'SELECT') return 'NOT_SELECT:'+(el?el.tagName:'none');
      function fire(e,t){ try{e.dispatchEvent(new Event(t,{bubbles:true}));}catch(_){}
        var ev=document.createEvent('HTMLEvents'); ev.initEvent(t,true,true); e.dispatchEvent(ev); }
      el.value = V; fire(el,'input'); fire(el,'change');
      return 'OK:'+el.value;
    })"""
    r = c.evaluate("(%s)(%s)" % (JS, json.dumps(value)), timeout=15)
elif mode == "month":
    JS = """(function(V){
      var el = document.activeElement;
      if (!el || el.tagName !== 'SELECT') return 'NOT_SELECT:'+(el?el.tagName:'none');
      function fire(e,t){ try{e.dispatchEvent(new Event(t,{bubbles:true}));}catch(_){}
        var ev=document.createEvent('HTMLEvents'); ev.initEvent(t,true,true); e.dispatchEvent(ev); }
      for (var j=0;j<el.options.length;j++){
        var txt = el.options[j].text||'';
        if (txt.indexOf(V)===0 || txt===V) {
          el.selectedIndex=j; fire(el,'input'); fire(el,'change');
          return 'OK:'+txt;
        }
      }
      return 'NO_MATCH';
    })"""
    r = c.evaluate("(%s)(%s)" % (JS, json.dumps(value)), timeout=15)
else:
    r = "BAD_MODE"
print(r)
c.close()
