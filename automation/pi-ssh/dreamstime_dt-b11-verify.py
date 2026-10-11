#!/usr/bin/env python3
"""Ground-truth verification after batch-11 submission."""
import json, sys, time, urllib.request
sys.path.insert(0, "/config/etsy-browser")
from cdp import CDP, nap
SHOTS = "/config/dreamstime-browser/shots"
def http_put(url, timeout=10):
    req = urllib.request.Request(url, data=b"", method="PUT")
    with urllib.request.urlopen(req, timeout=timeout) as r: return r.read()
nt = json.loads(http_put("http://127.0.0.1:9225/json/new?url=about%3Ablank"))
cdp = CDP(nt["webSocketDebuggerUrl"]); tid = nt["id"]
out = {}
try:
    cdp.navigate("https://www.dreamstime.com/upload"); nap(6,8)
    out["upload_tabs"] = cdp.evaluate("""(function(){var t=document.body?document.body.innerText.slice(0,4000):'';var o={};var m=t.match(/Uploads\\s*(\\d+)/i);if(m)o.unfinished=m[1];m=t.match(/Pending[^\\d]*(\\d*)/i);if(m)o.pending=m[1];m=t.match(/Refused[^\\d]*(\\d*)/i);if(m)o.refused=m[1];return o;})()""")
    # pending files census
    cdp.navigate("https://www.dreamstime.com/upload/under-review"); nap(6,8)
    pend = cdp.evaluate("""(function(){var names=[];Array.prototype.slice.call(document.querySelectorAll('.upload-item')).forEach(function(d){var m=(d.innerText||'').match(/b\\d\\d-\\d+\\.jpg/i);if(m)names.push(m[0].toLowerCase());});var inp=document.querySelector('input.changepage');return {page_names:names,pages:inp?parseInt(inp.getAttribute('max')||inp.max||'1',10):1};})()""")
    out["pending_page1"] = pend
    # unfinished census
    cdp.navigate("https://www.dreamstime.com/upload"); nap(6,8)
    unf = cdp.evaluate("""(function(){var names=[];Array.prototype.slice.call(document.querySelectorAll('.upload-item')).forEach(function(d){var m=(d.innerText||'').match(/b\\d\\d-\\d+\\.jpg/i);if(m)names.push(m[0].toLowerCase());});return names;})()""")
    out["unfinished_names"] = unf
    # refused
    cdp.navigate("https://www.dreamstime.com/upload/refused-files"); nap(5,7)
    out["refused_text"] = cdp.evaluate("document.body?document.body.innerText.slice(0,600):''")[:600]
    # online count
    cdp.navigate("https://www.dreamstime.com/account/online-files"); nap(5,7)
    out["online"] = cdp.evaluate("""(function(){var t=document.body?document.body.innerText:'';var m=t.match(/Showing\\s+\\d+\\s*-\\s*\\d+\\s+of\\s+(\\d+)\\s+images/i);return m?m[1]:null;})()""")
    cdp.screenshot(SHOTS + "/dreamstime-2026-10-11-verify.png")
finally:
    try: urllib.request.urlopen("http://127.0.0.1:9225/json/close/%s" % tid, timeout=10)
    except Exception: pass
    try: cdp.close()
    except Exception: pass
print(json.dumps(out, indent=1))
json.dump(out, open(SHOTS + "/dreamstime-2026-10-11-verify.json","w"), indent=1)
print("VERIFY DONE")
