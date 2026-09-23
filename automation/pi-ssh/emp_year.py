#!/usr/bin/env python3
"""Set year + verify employment form state. Usage: emp_year.py <year>"""
import sys, json, urllib.request
sys.path.insert(0, "/config/etsy-browser")
from cdp import CDP

year = sys.argv[1] if len(sys.argv) > 1 else "2026"

targets = json.loads(urllib.request.urlopen("http://127.0.0.1:9224/json/list", timeout=8).read())
pages = [t for t in targets if t.get("type") == "page" and "employment-history" in t.get("url", "")]
c = CDP(pages[0]["webSocketDebuggerUrl"])

JS = """
(function(YEAR){
  var out = [];
  function fire(el, type){
    try { el.dispatchEvent(new Event(type, {bubbles:true})); } catch(_){}
    var e = document.createEvent('HTMLEvents');
    e.initEvent(type, true, true);
    el.dispatchEvent(e);
  }
  var inputs = document.querySelectorAll('input');
  for (var i=0;i<inputs.length;i++){
    var ph = inputs[i].getAttribute('placeholder')||'';
    var lab = inputs[i].closest('label');
    var lt = lab ? (lab.innerText||'') : '';
    var tp = inputs[i].type||'';
    if (/year/i.test(ph+' '+lt) && (tp==='text'||tp==='')){
      inputs[i].focus();
      inputs[i].value = YEAR;
      fire(inputs[i],'input'); fire(inputs[i],'change');
      out.push('year='+inputs[i].value);
      break;
    }
  }
  var boxes = document.querySelectorAll('input[type=checkbox]');
  for (var i=0;i<boxes.length;i++){
    var lab2 = boxes[i].closest('label');
    var lt2 = lab2 ? (lab2.innerText||'') : '';
    if (/current employment status/i.test(lt2)) {
      out.push('current_checked='+boxes[i].checked);
      break;
    }
  }
  var sel = document.querySelector('select.form-select');
  out.push('status_val='+(sel?sel.value:'?'));
  var msel = null;
  var sels = document.querySelectorAll('select');
  for (var i=0;i<sels.length;i++){
    if (sels[i]!==sel){ msel=sels[i]; break; }
  }
  out.push('month_val='+(msel?msel.options[msel.selectedIndex].text:'?'));
  return out.join(' | ');
})
"""

try:
    r = c.evaluate("(%s)(%s)" % (JS, json.dumps(year)), timeout=20)
    print("STATE:", r)
except Exception as e:
    print("FAIL:", str(e)[:120])
c.close()
