#!/usr/bin/env python3
"""Dreamstime review-count probe v2 (2026-09-23): real-clicks the
Uploads / Under review / Refused files tabs (JS-void links) and dumps
per-tab card counts, filenames and refusal reasons."""
import json
import os
import sys
import time
import urllib.request
import urllib.parse

sys.path.insert(0, "/config/etsy-browser")
from cdp import CDP  # noqa: E402

SHOTS = "/config/pi-browser/shots"
PREFIX = "dreamstime-2026-09-23-counts2-"
OUT = os.path.join(SHOTS, "dreamstime-2026-09-23-counts2.json")
os.makedirs(SHOTS, exist_ok=True)

result = {"date": "2026-09-23", "tabs": {}}


def log(m):
    print("[counts2] %s" % m, flush=True)


def http_get(url, timeout=10):
    with urllib.request.urlopen(url, timeout=timeout) as r:
        return r.read()


def http_put(url, timeout=10):
    req = urllib.request.Request(url, method="PUT")
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def http_delete(url, timeout=10):
    req = urllib.request.Request(url, method="DELETE")
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def wait_ready(cdp, timeout=40):
    t0 = time.time()
    while time.time() - t0 < timeout:
        try:
            if cdp.evaluate("document.readyState", timeout=15) == "complete":
                return True
        except Exception:
            pass
        time.sleep(1)
    return False


TAB_CENTER_JS = """(function(name){
  var els = document.querySelectorAll('a');
  for (var i=0;i<els.length;i++){
    var t = (els[i].innerText||'').replace(/\\s+/g,' ').trim();
    if (t.toLowerCase().indexOf(name.toLowerCase()) === 0){
      els[i].scrollIntoView({block:'center'});
      var r = els[i].getBoundingClientRect();
      return {x: r.x + r.width/2, y: r.y + r.height/2, label: t};
    }
  }
  return null;
})(%s)"""

CARDS_JS = """(function(){
  var txt = document.body ? document.body.innerText : '';
  var parts = txt.split('Filename:');
  var cards = [];
  for (var i=1; i<parts.length && cards.length<60; i++){
    cards.push(parts[i].slice(0, 400).replace(/\\n+/g,' | ').trim());
  }
  var tabline = '';
  document.querySelectorAll('a').forEach(function(a){
    var t=(a.innerText||'').replace(/\\s+/g,' ').trim();
    if (/^(uploads|under review|refused files)/i.test(t) && t.length<40) tabline += '['+t+'] ';
  });
  return {n_cards: cards.length, cards: cards, tabs: tabline,
          head: txt.slice(0, 500)};
})()"""


def real_click(cdp, x, y):
    cdp.call("Input.dispatchMouseEvent",
             {"type": "mousePressed", "x": x, "y": y,
              "button": "left", "clickCount": 1})
    time.sleep(0.15)
    cdp.call("Input.dispatchMouseEvent",
             {"type": "mouseReleased", "x": x, "y": y,
              "button": "left", "clickCount": 1})


def main():
    json.loads(http_get("http://127.0.0.1:9225/json/list"))
    new_t = json.loads(http_put(
        "http://127.0.0.1:9225/json/new?" +
        urllib.parse.urlencode({"url": "about:blank"})))
    target_id = new_t["id"]
    cdp = None
    try:
        cdp = CDP(new_t["webSocketDebuggerUrl"])
        cdp.call("Page.enable")
        cdp.navigate("https://www.dreamstime.com/upload")
        wait_ready(cdp)
        time.sleep(3)
        for name in ["Under review", "Refused files", "Uploads"]:
            key = name.lower().replace(" ", "_")
            info = cdp.evaluate(TAB_CENTER_JS % json.dumps(name))
            if not info:
                result["tabs"][key] = {"error": "tab link not found"}
                log("%s: tab link NOT FOUND" % name)
                continue
            log("clicking tab '%s' at (%.0f, %.0f)" %
                (info["label"], info["x"], info["y"]))
            real_click(cdp, info["x"], info["y"])
            time.sleep(4)
            shot = os.path.join(SHOTS, PREFIX + key + ".png")
            cdp.screenshot(shot)
            data = cdp.evaluate(CARDS_JS) or {}
            result["tabs"][key] = data
            log("%s -> %d cards; tabs=%s" %
                (name, data.get("n_cards", 0), data.get("tabs", "")))
        with open(OUT, "w") as f:
            json.dump(result, f, indent=2)
        log("wrote %s" % OUT)
        return 0
    finally:
        if cdp is not None:
            try:
                cdp.close()
            except Exception:
                pass
        try:
            http_delete("http://127.0.0.1:9225/json/close/%s" % target_id)
            log("closed own tab; browser left running")
        except Exception as e:
            log("close tab failed: %s" % e)


if __name__ == "__main__":
    sys.exit(main())
