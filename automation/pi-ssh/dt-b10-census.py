#!/usr/bin/env python3
"""Dreamstime watch census 2026-10-10: tab counts, under-review census,
refused census, online-files census, statistics, payout, tax center."""
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

def real_click(cdp, x, y):
    cdp.call("Input.dispatchMouseEvent", {"type":"mousePressed","x":x,"y":y,"button":"left","clickCount":1})
    time.sleep(0.15)
    cdp.call("Input.dispatchMouseEvent", {"type":"mouseReleased","x":x,"y":y,"button":"left","clickCount":1})

def goto(cdp, url):
    cdp.navigate(url)
    nap(5, 7)
    try: cdp.evaluate("document.readyState === 'complete'")
    except Exception: pass
    nap(2, 3)

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
  m = txt.match(/Uploads\\s*(\\d+)/i); if (m) out.unfinished = parseInt(m[1], 10);
  m = txt.match(/Under review\\s*(\\d*)/i); if (m) out.under_review_tab = m[1] === '' ? 'tab-present-no-count' : parseInt(m[1], 10);
  m = txt.match(/Refused[^\\d]*(\\d+)/i); if (m) out.refused = parseInt(m[1], 10);
  return out;
})()"""

FIND_TAB_JS = """(function(){
  var out = [];
  Array.prototype.slice.call(document.querySelectorAll('*')).forEach(function(el){
    var t = (el.innerText||'').trim();
    if (/^__TAB__$/i.test(t)) {
      var r = el.getBoundingClientRect();
      if (r.width > 50) out.push({x: r.x+r.width/2, y: r.y+r.height/2});
    }
  });
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

def read_items_wait(cdp, timeout=30):
    t0 = time.time(); items = []
    while time.time() - t0 < timeout:
        items = cdp.evaluate(ITEMS_JS)
        if items: break
        time.sleep(2)
    return items

def check_session(cdp):
    st = cdp.evaluate(STATE_JS)
    if st.get("botWall"): raise RuntimeError("BOT WALL: " + str(st.get("text"))[:150])
    if not st.get("signedIn"): raise RuntimeError("session lost: " + str(st.get("text"))[:150])
    return True

def census_tab(cdp, tab_name):
    """Click a tab on /upload and census .upload-item filenames across pages."""
    tabs = cdp.evaluate(FIND_TAB_JS.replace("__TAB__", tab_name))
    if not tabs: return {"error": "tab not found: " + tab_name}
    real_click(cdp, tabs[0]["x"], tabs[0]["y"])
    nap(5, 6)
    check_session(cdp)
    pmax = cdp.evaluate(PAGEMAX_JS)
    seen = set(); pages = {}
    for pg in range(1, pmax + 1):
        if pg > 1:
            cdp.evaluate(GOTO_JS_TMPL.replace("__PG__", str(pg)))
            nap(4, 5)
        items = read_items_wait(cdp)
        pages[pg] = len(items); seen.update(items)
    return {"pages": pmax, "per_page": pages, "total": len(seen),
            "files": sorted(seen)}

def main():
    out = {}
    cdp, tid = new_tab()
    try:
        goto(cdp, "https://www.dreamstime.com/upload")
        check_session(cdp)
        out["tab_counts"] = cdp.evaluate(COUNTS_JS)
        cdp.screenshot(SHOTS + "/dreamstime-2026-10-10-census-upload.png")

        out["unfinished"] = census_tab(cdp, "Uploads")
        out["under_review"] = census_tab(cdp, "Under review")
        out["refused"] = census_tab(cdp, "Refused files")

        # online files
        goto(cdp, "https://www.dreamstime.com/account/online-files")
        check_session(cdp)
        online = cdp.evaluate("""(function(){
          var txt = document.body ? document.body.innerText : '';
          var m = txt.match(/Showing\\s+\\d+\\s*-\\s*\\d+\\s+of\\s+(\\d+)\\s+images/i);
          var ids = [], mm, re = /File ID\\s*(\\d+)/g;
          while ((mm = re.exec(txt)) !== null) ids.push(mm[1]);
          var inp = document.querySelector('input.changepage');
          return {count_text: m ? m[0] : null, total: m ? parseInt(m[1],10) : null,
                  page_ids: ids, pages: inp ? parseInt(inp.getAttribute('max')||inp.max||'1',10) : 1};
        })()""")
        out["online_page1"] = online

        # statistics
        goto(cdp, "https://www.dreamstime.com/contributor_statistics.php")
        check_session(cdp)
        out["statistics"] = cdp.evaluate("""(function(){
          var txt = document.body ? document.body.innerText.slice(0, 4000) : '';
          var rows = [];
          Array.prototype.slice.call(document.querySelectorAll('table tr')).forEach(function(tr){
            var t = (tr.innerText||'').replace(/\\s+/g,' ').trim();
            if (/Oct 26|Oct 2026|Sep 26|Sep 2026|Total/i.test(t)) rows.push(t.slice(0,160));
          });
          return {text: txt.slice(0, 1500), rows: rows};
        })()""")

        # payout
        goto(cdp, "https://www.dreamstime.com/account/request-payment")
        check_session(cdp)
        out["payout"] = cdp.evaluate("""(function(){
          var txt = document.body ? document.body.innerText.slice(0, 2500) : '';
          return {text: txt.slice(0, 1200)};
        })()""")

        # tax center
        goto(cdp, "https://www.dreamstime.com/tax-center")
        check_session(cdp)
        out["tax"] = cdp.evaluate("""(function(){
          var txt = document.body ? document.body.innerText.slice(0, 2500) : '';
          return {url: location.href, text: txt.slice(0, 1200)};
        })()""")
    finally:
        close_tab(cdp, tid)
    print(json.dumps(out, indent=1))
    with open(SHOTS + "/dreamstime-2026-10-10-census.json", "w") as f:
        json.dump(out, f, indent=1)
    print("DONE_MARKER")

if __name__ == "__main__":
    main()
