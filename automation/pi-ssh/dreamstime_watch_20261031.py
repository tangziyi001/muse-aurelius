#!/usr/bin/env python3
"""Dreamstime watch census 2026-10-31: session check, tab counts,
unfinished census (all pages), pending census (all pages), refused,
online count, statistics, payout, tax center.
Adapted from dreamstime_watch_20261011.py + dt-b11-verify.py.
Tab names (renamed 2026-10-11): "Unfinished Files N", "Pending Files",
"Refused Files"."""
import json, sys, time, urllib.request
sys.path.insert(0, "/config/etsy-browser")
from cdp import CDP, nap

SHOTS = "/config/dreamstime-browser/shots"

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

STATE_JS = """(function(){
  var txt = document.body ? document.body.innerText.slice(0, 6000) : '';
  var low = txt.toLowerCase();
  return {
    url: location.href,
    signedIn: /tangziyi001/i.test(txt) && !document.querySelector('input[type="password"]'),
    botWall: low.indexOf('press & hold') !== -1 || low.indexOf('datadome') !== -1
             || low.indexOf('verify you are human') !== -1,
    text: txt.slice(0, 500)
  };
})()"""

COUNTS_JS = """(function(){
  var txt = document.body ? document.body.innerText.slice(0, 12000) : '';
  var out = {text: txt.slice(0, 2000)};
  var m;
  m = txt.match(/Unfinished\\s*Files\\s*(\\d*)/i); if (m) out.unfinished = m[1]===''?'tab-present-no-count':parseInt(m[1],10);
  m = txt.match(/Pending\\s*Files\\s*(\\d*)/i); if (m) out.pending = m[1]===''?'tab-present-no-count':parseInt(m[1],10);
  m = txt.match(/Refused\\s*Files\\s*(\\d*)/i); if (m) out.refused = m[1]===''?'tab-present-no-count':parseInt(m[1],10);
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

PAGEMAX_JS = """(function(){
  var inp = document.querySelector('input.changepage');
  return inp ? parseInt(inp.getAttribute('max') || inp.max || '1', 10) : 1;
})()"""

GOTO_JS_TMPL = """(function(){
  var inp = document.querySelector('input.changepage');
  if (!inp) return false;
  var desc = Object.getOwnPropertyDescriptor(inp, 'value');
  if (desc && desc.set) desc.set.call(inp, '__PG__'); else inp.value = '__PG__';
  inp.dispatchEvent(new Event('input', {bubbles:true}));
  inp.dispatchEvent(new KeyboardEvent('keydown', {key:'Enter', keyCode:13, bubbles:true}));
  inp.dispatchEvent(new KeyboardEvent('keyup', {key:'Enter', keyCode:13, bubbles:true}));
  return true;
})()"""

def check_session(cdp):
    st = cdp.evaluate(STATE_JS)
    if st.get("botWall"): raise RuntimeError("BOT WALL: " + str(st.get("text"))[:150])
    if not st.get("signedIn"): raise RuntimeError("session lost: " + str(st.get("text"))[:150])
    return True

def goto(cdp, url):
    cdp.navigate(url); nap(5, 7)
    try: cdp.evaluate("document.readyState === 'complete'")
    except Exception: pass
    nap(2, 3)
    check_session(cdp)

def census_items(cdp):
    seen = set()
    pmax = cdp.evaluate(PAGEMAX_JS)
    for pg in range(1, pmax + 1):
        if pg > 1:
            cdp.evaluate(GOTO_JS_TMPL.replace("__PG__", str(pg)))
            nap(4, 5)
            check_session(cdp)
        t0 = time.time(); items = []
        while time.time() - t0 < 30:
            items = cdp.evaluate(ITEMS_JS)
            if items: break
            time.sleep(2)
        seen.update(items)
    return {"pages": pmax, "total": len(seen), "files": sorted(seen)}

def main():
    out = {}
    cdp, tid = new_tab()
    try:
        goto(cdp, "https://www.dreamstime.com/upload")
        out["tab_counts"] = cdp.evaluate(COUNTS_JS)
        out["unfinished"] = census_items(cdp)
        cdp.screenshot(SHOTS + "/dreamstime-2026-10-31-census-upload.png")

        goto(cdp, "https://www.dreamstime.com/upload/under-review")
        out["pending"] = census_items(cdp)

        goto(cdp, "https://www.dreamstime.com/upload/refused-files")
        out["refused_text"] = cdp.evaluate(
            "document.body ? document.body.innerText.slice(0, 600) : ''")[:600]

        goto(cdp, "https://www.dreamstime.com/account/online-files")
        out["online"] = cdp.evaluate("""(function(){
          var t = document.body ? document.body.innerText : '';
          var m = t.match(/Showing\\s+\\d+\\s*-\\s*\\d+\\s+of\\s+(\\d+)\\s+images/i);
          return m ? m[1] : null;
        })()""")

        goto(cdp, "https://www.dreamstime.com/account/statistics")
        out["statistics"] = cdp.evaluate("""(function(){
          var txt = document.body ? document.body.innerText.slice(0, 4000) : '';
          var rows = [];
          Array.prototype.slice.call(document.querySelectorAll('table tr')).forEach(function(tr){
            var t = (tr.innerText||'').replace(/\\s+/g,' ').trim();
            if (/Oct 26|Oct 2026|Sep 26|Sep 2026|Total/i.test(t)) rows.push(t.slice(0,160));
          });
          return {rows: rows};
        })()""")

        goto(cdp, "https://www.dreamstime.com/account/request-payment")
        out["payout"] = cdp.evaluate(
            "(document.body ? document.body.innerText.slice(0, 1200) : '')")[:1200]

        goto(cdp, "https://www.dreamstime.com/tax-center")
        out["tax"] = cdp.evaluate("""(function(){
          return {url: location.href,
                  text: document.body ? document.body.innerText.slice(0, 1200) : ''};
        })()""")
    finally:
        close_tab(cdp, tid)
    print(json.dumps(out, indent=1))
    with open(SHOTS + "/dreamstime-2026-10-31-census.json", "w") as f:
        json.dump(out, f, indent=1)
    print("DONE_MARKER")

if __name__ == "__main__":
    main()
