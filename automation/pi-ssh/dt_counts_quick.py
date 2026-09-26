#!/usr/bin/env python3
"""Quick Dreamstime dashboard counts (read-only). Reusable."""
import json
import sys
import time
import urllib.request
import urllib.parse

sys.path.insert(0, "/config/etsy-browser")
from cdp import CDP  # noqa: E402

DUMP_JS = """(function(){
  var txt = document.body ? document.body.innerText : '';
  return {url: location.href, title: document.title, text: txt.slice(0, 8000)};
})()"""


def main():
    base = "http://127.0.0.1:9225"
    json.loads(urllib.request.urlopen(base + "/json/list", timeout=10).read())
    req = urllib.request.Request(
        base + "/json/new?" + urllib.parse.urlencode({"url": "about:blank"}),
        method="PUT")
    new_t = json.loads(urllib.request.urlopen(req, timeout=10).read())
    tid = new_t["id"]
    cdp = None
    try:
        cdp = CDP(new_t["webSocketDebuggerUrl"])
        cdp.call("Page.enable")
        cdp.navigate("https://www.dreamstime.com/account")
        t0 = time.time()
        while time.time() - t0 < 40:
            try:
                if cdp.evaluate("document.readyState", timeout=15) == "complete":
                    break
            except Exception:
                pass
            time.sleep(1)
        time.sleep(4)
        dump = cdp.evaluate(DUMP_JS) or {}
        print(json.dumps(dump, ensure_ascii=False, indent=1))
        shot = "/config/dreamstime-browser/shots/counts-quick-20260926-1245.png"
        cdp.screenshot(shot)
        print("SHOT " + shot, flush=True)
    finally:
        if cdp is not None:
            try:
                cdp.close()
            except Exception:
                pass
        try:
            req = urllib.request.Request(
                base + "/json/close/%s" % tid, method="DELETE")
            urllib.request.urlopen(req, timeout=10).read()
        except Exception as e:
            print("close tab failed: %s" % e, flush=True)


main()
