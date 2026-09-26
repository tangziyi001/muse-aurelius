#!/usr/bin/env python3
"""Dreamstime audit step 1: login-state probe on existing Pi browser (9225)."""
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
os.makedirs(SHOTS, exist_ok=True)

STATE_JS = """(function(){
  var txt = document.body ? document.body.innerText.slice(0, 6000) : '';
  var low = txt.toLowerCase();
  return {
    url: location.href,
    title: document.title,
    hasUsername: /Tangziyi001/i.test(txt),
    signedIn: /Tangziyi001/i.test(txt)
              || /sign out|log out|log me out/i.test(txt),
    botWall: low.indexOf('press & hold') >= 0
             || low.indexOf('press and hold') >= 0
             || low.indexOf('datadome') >= 0
             || low.indexOf('verify you are a human') >= 0,
    head: txt.slice(0, 300)
  };
})()"""


def http_get(url, timeout=10):
    with urllib.request.urlopen(url, timeout=timeout) as r:
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


def main():
    base = "http://127.0.0.1:%d" % DEBUG_PORT
    json.loads(http_get(base + "/json/list"))  # sanity: browser alive
    new_t = json.loads(http_put_new(base))
    target_id = new_t["id"]
    cdp = None
    try:
        cdp = CDP(new_t["webSocketDebuggerUrl"])
        cdp.call("Page.enable")
        results = {}
        for name, url in [("home", "https://www.dreamstime.com/"),
                          ("account", "https://www.dreamstime.com/account")]:
            cdp.navigate(url)
            wait_ready(cdp)
            time.sleep(4)
            st = cdp.evaluate(STATE_JS) or {}
            shot = os.path.join(SHOTS, "step1-%s.png" % name)
            cdp.screenshot(shot)
            results[name] = st
            print("[probe] %s -> url=%s title=%s signedIn=%s hasUser=%s botWall=%s"
                  % (name, st.get("url"), st.get("title"),
                     st.get("signedIn"), st.get("hasUsername"), st.get("botWall")),
                  flush=True)
        print("[probe] RESULT_JSON_BEGIN")
        print(json.dumps(results, ensure_ascii=False))
        print("[probe] RESULT_JSON_END")
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
            print("[probe] close tab failed: %s" % e, flush=True)


def http_put_new(base):
    req = urllib.request.Request(
        base + "/json/new?" + urllib.parse.urlencode({"url": "about:blank"}),
        method="PUT")
    with urllib.request.urlopen(req, timeout=10) as r:
        return r.read()


if __name__ == "__main__":
    sys.exit(main())
