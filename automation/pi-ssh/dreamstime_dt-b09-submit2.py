#!/usr/bin/env python3
"""Dreamstime batch-09 run #2: submit the 8 files missed by run #1 (b09-01..08).
Mapping pages through ALL Unfinished pages via input.changepage, then fills +
submits only the 8 target files (12 already in Under review are excluded)."""
import csv
import json
import os
import sys
import time
import urllib.request

sys.path.insert(0, "/config/etsy-browser")
from cdp import CDP, nap, wait_for_js  # noqa: E402

SHOTS = "/config/dreamstime-browser/shots"
RESULT = os.path.join(SHOTS, "dt-b09-submit2-result.json")
os.makedirs(SHOTS, exist_ok=True)

TARGETS = ["b09-%02d.jpg" % i for i in range(1, 9)]
META = {}
with open("/config/ftp-runner/outbox/dreamstime/dreamstime-meta.csv") as f:
    for row in csv.DictReader(f):
        if row["filename"] in TARGETS:
            META[row["filename"]] = row
assert len(META) == 8, "meta rows: %d" % len(META)


def http_put(url, timeout=10):
    req = urllib.request.Request(url, data=b"", method="PUT")
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def new_tab():
    new_t = json.loads(http_put("http://127.0.0.1:9225/json/new?url=about%3Ablank"))
    return CDP(new_t["webSocketDebuggerUrl"]), new_t["id"]


def close_tab(cdp, tid):
    try:
        urllib.request.urlopen(
            "http://127.0.0.1:9225/json/close/%s" % tid, timeout=10)
    except Exception:
        pass
    try:
        cdp.close()
    except Exception:
        pass


def real_click(cdp, x, y):
    cdp.call("Input.dispatchMouseEvent",
             {"type": "mousePressed", "x": x, "y": y,
              "button": "left", "clickCount": 1})
    time.sleep(0.15)
    cdp.call("Input.dispatchMouseEvent",
             {"type": "mouseReleased", "x": x, "y": y,
              "button": "left", "clickCount": 1})


STATE_JS = """(function(){
  var txt = document.body ? document.body.innerText.slice(0, 6000) : '';
  var low = txt.toLowerCase();
  return {
    signedIn: /tangziyi001/i.test(txt) && !document.querySelector('input[type="password"]'),
    botWall: low.indexOf('press & hold') !== -1 || low.indexOf('datadome') !== -1,
    text: txt.slice(0, 300)
  };
})()"""

MAP_JS = """(function(){
  var out = {};
  Array.prototype.slice.call(document.querySelectorAll('a')).forEach(function(a){
    var h = a.getAttribute('href') || '';
    var idx = h.indexOf('/upload/edit');
    if (idx >= 0) {
      var pid = h.slice(idx + 12).replace(/\\D/g, '');
      var node = a, txt = '';
      for (var d = 0; d < 5 && node; d++) {
        node = node.parentElement;
        if (!node) break;
        txt = (node.innerText || '').toLowerCase();
        var fi = txt.indexOf('filename: b');
        if (fi >= 0) {
          var start = fi + 10;
          var end = txt.indexOf('.jpg', start) + 4;
          if (end > start) { out[txt.slice(start, end)] = pid; }
          break;
        }
      }
    }
  });
  return out;
})()"""

PAGEMAX_JS = """(function(){
  var inp = document.querySelector('input.changepage');
  return inp ? parseInt(inp.getAttribute('max') || inp.max || '1', 10) : 1;
})()"""

GOTO_PAGE_JS = """(function(p){
  var inp = document.querySelector('input.changepage');
  if (!inp) return false;
  var desc = Object.getOwnPropertyDescriptor(inp, 'value');
  if (desc && desc.set) desc.set.call(inp, String(p)); else inp.value = String(p);
  inp.dispatchEvent(new Event('input', {bubbles:true}));
  inp.dispatchEvent(new KeyboardEvent('keydown', {key:'Enter', keyCode:13, bubbles:true}));
  inp.dispatchEvent(new KeyboardEvent('keyup', {key:'Enter', keyCode:13, bubbles:true}));
  return true;
})()"""

FILL_JS = """(function(){
  var out = {ok: true, errors: []};
  function setVal(el, text) {
    var desc = Object.getOwnPropertyDescriptor(el, 'value');
    if (desc && desc.set) { desc.set.call(el, text); } else { el.value = text; }
    el.dispatchEvent(new Event('input', {bubbles: true}));
    el.dispatchEvent(new Event('change', {bubbles: true}));
  }
  try {
    setVal(document.getElementById('title'), __TITLE__);
    setVal(document.getElementById('description'), __DESC__);
    var ai = document.getElementById('js-af_ai_contributor');
    if (ai && !ai.checked) { ai.click(); }
    out.aiChecked = ai ? ai.checked : 'no-el';
    var kwStr = __KWS__.join(',');
    try { jQuery('#keywords').importTags(kwStr); out.added = __KWS__.length; }
    catch (e) { out.errors.push('kw: ' + String(e).slice(0,100)); }
    out.kwVal = (jQuery('#keywords').val() || '').slice(0, 120);
  } catch(e) { out.ok = false; out.errors.push(String(e).slice(0,200)); }
  return out;
})()"""

FIND_BTN_JS = """(function(){
  var out = [];
  var els = document.querySelectorAll('*');
  for (var i=0;i<els.length;i++){
    var t = (els[i].innerText||'').trim();
    if ((/^save edits$/i.test(t) && /popup-nav__item/.test(els[i].className)) ||
        (/^submit commercial$/i.test(t) && els[i].tagName === 'A')) {
      var r = els[i].getBoundingClientRect();
      if (r.width > 0 && r.height > 0)
        out.push({txt: t, x: r.x + r.width/2, y: r.y + r.height/2});
    }
  }
  return out;
})()"""


def check_session(cdp):
    st = cdp.evaluate(STATE_JS)
    if st.get("botWall"):
        raise RuntimeError("BOT WALL appeared")
    if not st.get("signedIn"):
        raise RuntimeError("session lost")
    return True


def get_mapping(cdp):
    mapping = {}
    cdp.navigate("https://www.dreamstime.com/upload")
    nap(4, 5)
    try:
        wait_for_js(cdp, "document.readyState === 'complete'", timeout=30)
    except Exception:
        pass
    nap(3, 4)
    check_session(cdp)
    pagemax = cdp.evaluate(PAGEMAX_JS) or 1
    print("unfinished pages: %d" % pagemax, flush=True)
    for pg in range(1, pagemax + 1):
        if pg > 1:
            cdp.evaluate(GOTO_PAGE_JS.replace("(p)", "(%d)" % pg))
            nap(5, 7)
            check_session(cdp)
        mapping.update(cdp.evaluate(MAP_JS))
        print("page %d: mapping now %d files" % (pg, len(mapping)), flush=True)
        if all(t in mapping for t in TARGETS):
            break
    return mapping


def process_one(cdp, fname, pid, meta):
    res = {"file": fname, "portal_id": pid}
    kws = [k.strip() for k in meta["keywords"].split(",") if k.strip()][:35]
    fill_js = (FILL_JS
               .replace("__TITLE__", json.dumps(meta["title"]))
               .replace("__DESC__", json.dumps(meta["description"]))
               .replace("__KWS__", json.dumps(kws)))
    cdp.navigate("https://www.dreamstime.com/upload/edit" + pid)
    nap(4, 5)
    try:
        wait_for_js(cdp, "document.readyState === 'complete'", timeout=30)
    except Exception:
        pass
    nap(3, 4)
    check_session(cdp)
    res["fill"] = cdp.evaluate(fill_js)
    nap(2, 3)
    nav_ok = cdp.evaluate("!!document.getElementById('js-savededits')")
    res["nav_ok"] = nav_ok
    if not nav_ok:
        res["error"] = "page nav destroyed after fill"
        return res
    cdp.evaluate("window.scrollTo(0, 0)")
    nap(1, 2)
    btns = cdp.evaluate(FIND_BTN_JS)
    save = next((b for b in btns if b["txt"] == "Save edits"), None)
    if not save:
        res["error"] = "Save edits button not found"
        return res
    real_click(cdp, save["x"], save["y"])
    nap(7, 9)
    res["after_save_url"] = cdp.evaluate("location.href")
    cdp.evaluate("window.scrollTo(0, document.body.scrollHeight)")
    nap(1, 2)
    btns = cdp.evaluate(FIND_BTN_JS)
    sub = next((b for b in btns if b["txt"] == "Submit commercial"), None)
    if not sub:
        res["error"] = "Submit commercial button not found after save"
        return res
    real_click(cdp, sub["x"], sub["y"])
    nap(8, 10)
    st = cdp.evaluate(
        "(function(){return {url: location.href,"
        " body: document.body ? document.body.innerText.slice(0, 500) : ''};})()")
    res["after_submit"] = st
    res["submitted"] = ("under-review" in st["url"].lower()
                        or "under review" in st["body"].lower()
                        or "submitted" in st["body"].lower())
    return res


def main():
    results = []
    out = {"targets": TARGETS, "mapping": {}, "results": []}
    cdp, tid = new_tab()
    try:
        mapping = get_mapping(cdp)
        out["mapping"] = mapping
        print("MAPPING: %d files" % len(mapping), flush=True)
        missing = [t for t in TARGETS if t not in mapping]
        out["missing"] = missing
        if missing:
            print("MISSING: " + str(missing), flush=True)
        for fname in TARGETS:
            if fname not in mapping:
                results.append({"file": fname, "error": "not in uploads list"})
                continue
            print("=== %s (id %s)" % (fname, mapping[fname]), flush=True)
            try:
                r = process_one(cdp, fname, mapping[fname], META[fname])
            except Exception as e:
                r = {"file": fname, "portal_id": mapping[fname],
                     "error": "exception: " + str(e)[:200]}
                if "BOT WALL" in str(e) or "session lost" in str(e):
                    results.append(r)
                    out["results"] = results
                    out["fatal"] = str(e)[:300]
                    with open(RESULT, "w") as f:
                        json.dump(out, f, indent=1)
                    raise
            results.append(r)
            print(json.dumps(r)[:300], flush=True)
            out["results"] = results
            with open(RESULT, "w") as f:
                json.dump(out, f, indent=1)
        cdp.navigate("https://www.dreamstime.com/upload")
        nap(4, 5)
        out["unfinished_after"] = cdp.evaluate(
            "(function(){ var t=document.body?document.body.innerText:''; var m=t.match(/Uploads\\\\s*(\\\\d+)/i); return m?m[1]:null; })()")
        with open(RESULT, "w") as f:
            json.dump(out, f, indent=1)
    finally:
        close_tab(cdp, tid)
    ok = sum(1 for r in results if r.get("submitted"))
    print("DONE: %d/%d submitted (heuristic)" % (ok, len(results)), flush=True)


if __name__ == "__main__":
    main()
