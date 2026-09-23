#!/usr/bin/env python3
"""Dreamstime review-count probe (2026-09-23, bonus follow-up to login re-seed).

Attaches to shared Chromium on 9225, new tab only. Reads the Uploads /
Under review / Refused files tabs and dumps counts + filenames + reasons.
No credentials used (relies on the persisted session).
"""
import json
import os
import sys
import time
import urllib.request
import urllib.parse

sys.path.insert(0, "/config/etsy-browser")
from cdp import CDP  # noqa: E402

SHOTS = "/config/pi-browser/shots"
PREFIX = "dreamstime-2026-09-23-counts-"
OUT = os.path.join(SHOTS, "dreamstime-2026-09-23-counts.json")
os.makedirs(SHOTS, exist_ok=True)

result = {"date": "2026-09-23", "tabs": {}, "cards": {}}


def log(m):
    print("[counts] %s" % m, flush=True)


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


TABS_JS = """(function(){
  var out = [];
  var seen = {};
  document.querySelectorAll('a').forEach(function(a){
    var t = (a.innerText||'').replace(/\\s+/g,' ').trim();
    if (/^(uploads|under review|refused files)/i.test(t) && !seen[t] && t.length < 40){
      seen[t] = 1;
      out.push({label: t, href: a.href});
    }
  });
  return out;
})()"""

CARDS_JS = """(function(){
  var txt = document.body ? document.body.innerText : '';
  var parts = txt.split('Filename:');
  var cards = [];
  for (var i=1; i<parts.length && cards.length<60; i++){
    cards.push(parts[i].slice(0, 350).replace(/\\n+/g,' | ').trim());
  }
  return {n_cards: cards.length, cards: cards, head: txt.slice(0, 800)};
})()"""


def main():
    targets = json.loads(http_get("http://127.0.0.1:9225/json/list"))
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
        tabs = cdp.evaluate(TABS_JS) or []
        log("tabs found: %s" % tabs)
        result["tabs"]["strip"] = tabs
        for tab in tabs:
            label = tab["label"]
            href = tab.get("href") or "https://www.dreamstime.com/upload"
            key = label.lower().replace(" ", "_")[:24]
            log("opening tab: %s -> %s" % (label, href))
            cdp.navigate(href)
            wait_ready(cdp)
            time.sleep(3)
            shot = os.path.join(SHOTS, PREFIX + key + ".png")
            cdp.screenshot(shot)
            log("screenshot: %s" % shot)
            data = cdp.evaluate(CARDS_JS) or {}
            result["cards"][key] = data
            log("%s: %d cards" % (label, data.get("n_cards", 0)))
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
