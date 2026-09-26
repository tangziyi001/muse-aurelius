#!/usr/bin/env python3
"""Dreamstime audit step 3: personal messages / notifications probe (read-only)."""
import json
import os
import sys
import time
import urllib.request
import urllib.parse

sys.path.insert(0, "/config/etsy-browser")
from cdp import CDP  # noqa: E402

DEBUG_PORT = 9225
SHOTS = "/config/dreamstime-browser/shots"
OUT = {}

NOTIF_JS = """(function(){
  var txt = document.body ? document.body.innerText.slice(0, 5000) : '';
  var links = [];
  var as = document.querySelectorAll('a');
  for (var i=0;i<as.length;i++){
    var t=(as[i].innerText||'').replace(/\\s+/g,' ').trim().toLowerCase();
    if (/(my messages|private message|inbox|notification|comment|pending approval|agreement|terms)/.test(t) && t.length<60){
      links.push({text: as[i].innerText.trim().replace(/\\s+/g,' '), href: as[i].href});
    }
  }
  var badges = [];
  document.querySelectorAll('.badge,.unread,.count,.notify,[class*=notif]').forEach(function(el){
    var t=(el.innerText||'').trim();
    if (t.length>0 && t.length<20) badges.push(t);
  });
  return {url: location.href, title: document.title, head: txt.slice(0, 1500),
          links: links.slice(0, 30), badges: badges.slice(0, 10)};
})()"""


def http_get(url, timeout=10):
    with urllib.request.urlopen(url, timeout=timeout) as r:
        return r.read()


def http_put_new(base):
    req = urllib.request.Request(
        base + "/json/new?" + urllib.parse.urlencode({"url": "about:blank"}),
        method="PUT")
    with urllib.request.urlopen(req, timeout=10) as r:
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


def visit(cdp, name, url, sleep=4):
    cdp.navigate(url)
    wait_ready(cdp)
    time.sleep(sleep)
    dump = cdp.evaluate(NOTIF_JS) or {}
    shot = os.path.join(SHOTS, "step3-%s.png" % name)
    cdp.screenshot(shot)
    OUT[name] = dump
    print("[notif] %s -> %s links=%d badges=%s"
          % (name, dump.get("url"), len(dump.get("links") or []),
             json.dumps(dump.get("badges"))), flush=True)
    return dump


def main():
    base = "http://127.0.0.1:%d" % DEBUG_PORT
    json.loads(http_get(base + "/json/list"))
    new_t = json.loads(http_put_new(base))
    target_id = new_t["id"]
    cdp = None
    try:
        cdp = CDP(new_t["webSocketDebuggerUrl"])
        cdp.call("Page.enable")
        d1 = visit(cdp, "account2", "https://www.dreamstime.com/account")
        print("[notif] links found: %s" % json.dumps(d1.get("links"), ensure_ascii=False), flush=True)
        # follow any personal message/inbox links found
        for ln in (d1.get("links") or []):
            t = (ln.get("text") or "").lower()
            if "message" in t or "inbox" in t or "comment" in t:
                visit(cdp, "follow-%s" % t[:20].replace(" ", "_"), ln["href"])
        with open(os.path.join(SHOTS, "step3-notif.json"), "w") as f:
            json.dump(OUT, f, indent=2, ensure_ascii=False)
        print("[notif] wrote json", flush=True)
        return 0
    finally:
        if cdp is not None:
            try:
                cdp.close()
            except Exception:
                pass
        try:
            req = urllib.request.Request(
                base + "/json/close/%s" % target_id, method="DELETE")
            urllib.request.urlopen(req, timeout=10).read()
        except Exception as e:
            print("[notif] close tab failed: %s" % e, flush=True)


if __name__ == "__main__":
    sys.exit(main())
