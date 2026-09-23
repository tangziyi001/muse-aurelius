#!/usr/bin/env python3
"""Fill employment entry via JS. Usage: fill_emp.py <entry-json>
Sets: status value, month, year, current-checkbox. Dispatches change/input for Angular."""
import sys, json, urllib.request
sys.path.insert(0, "/config/etsy-browser")
from cdp import CDP

data = json.loads(sys.argv[1])
# data: {status: "U", month: "05", year: "2026", current: true}

targets = json.loads(urllib.request.urlopen("http://127.0.0.1:9224/json/list", timeout=8).read())
pages = [t for t in targets if t.get("type") == "page" and "employment-history" in t.get("url", "")]
c = CDP(pages[0]["webSocketDebuggerUrl"])

js_set = """(function(d){
  function fire(el, type){
    var e = document.createEvent('HTMLEvents');
    e.initEvent(type, true, true);
    el.dispatchEvent(e);
    // Angular2+ needs the newer Event too
    try { el.dispatchEvent(new Event(type, {bubbles:true})); } catch(_){}
  }
  var out = [];
  // 1. employment status select (the focused one or first .form-select)
  var sel = document.activeElement && document.activeElement.tagName==='SELECT'
    ? document.activeElement
    : document.querySelector('select.form-select');
  if (sel && d.status) {
    sel.value = d.status; fire(sel,'input'); fire(sel,'change');
    out.push('status='+sel.value);
  }
  // 2. current checkbox
  var boxes = document.querySelectorAll('input[type=checkbox]');
  for (var i=0;i<boxes.length;i++){
    var lab = boxes[i].closest('label');
    var t = lab ? (lab.innerText||'') : '';
    if (/current employment status/i.test(t)) {
      if (boxes[i].checked !== d.current) { boxes[i].click(); }
      out.push('current='+boxes[i].checked);
      break;
    }
  }
  // 3. month / year
  var sels = document.querySelectorAll('select');
  for (var i=0;i<sels.length;i++){
    if (sels[i] === sel) continue;
    var opts = Array.from(sels[i].options).map(function(o){return o.text;}).join(',');
    if (/jan/i.test(opts) && d.month) {
      // month select: find option containing the month
      for (var j=0;j<sels[i].options.length;j++){
        if (sels[i].options[j].text.indexOf(d.month) >= 0 || sels[i].options[j].value === d.month) {
          sels[i].selectedIndex = j; fire(sels[i],'input'); fire(sels[i],'change');
          out.push('month='+sels[i].options[j].text); break;
        }
      }
    }
  }
  var inputs = document.querySelectorAll('input[type=text], input:not([type])');
  for (var i=0;i<inputs.length;i++){
    var ph = (inputs[i].getAttribute('placeholder')||'');
    var lab2 = inputs[i].closest('label');
    var lt = lab2 ? (lab2.innerText||'') : '';
    if (/year/i.test(ph) || /year/i.test(lt)) {
      if (/^\d{4}$/.test(d.year||'')) {
        inputs[i].focus();
        inputs[i].value = d.year; fire(inputs[i],'input'); fire(inputs[i],'change');
        out.push('year='+inputs[i].value);
      }
      break;
    }
  }
  return out.join(' | ');
})(%s)""" % json.dumps(data)

try:
    r = c.evaluate(js_set, timeout=20)
    print("SET:", r)
except Exception as e:
    print("SET FAIL:", str(e)[:120])
c.close()
