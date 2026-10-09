#!/usr/bin/env python3
"""Quick Dreamstime session-state probe on the Pi shared Chromium."""
import json, sys, time, urllib.request, urllib.parse
sys.path.insert(0, "/config/etsy-browser")
from cdp import CDP

def http_put(url, timeout=10):
    req = urllib.request.Request(url, data=b"", method="PUT")
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()

STATE_JS = """(function(){
  var txt = document.body ? document.body.innerText.slice(0, 6000) : '';
  var low = txt.toLowerCase();
  return {
    url: location.href, title: document.title,
    hasMyAccount: /my account/i.test(txt),
    hasUsername: /tangziyi001/i.test(txt),
    hasLoginForm: !!document.querySelector('input[type="password"]'),
    hasSignOut: /sign out|log out/i.test(txt),
    contributorish: /my uploads|upload files|pending approval|contributor/i.test(txt),
    isMarketing: /become a contributor/i.test(txt),
    botWall: low.indexOf('press & hold') !== -1 || low.indexOf('datadome') !== -1,
    text: txt.slice(0, 900)
  };
})()"""

def new_tab():
    nt = json.loads(http_put("http://127.0.0.1:9225/json/new?url=about%3Ablank"))
    return CDP(nt["webSocketDebuggerUrl"]), nt["id"]

def close_tab(cdp, tid):
    try: urllib.request.urlopen("http://127.0.0.1:9225/json/close/%s" % tid, timeout=10)
    except Exception: pass
    try: cdp.close()
    except Exception: pass

def visit(cdp, url):
    cdp.navigate(url)
    t0 = time.time()
    while time.time() - t0 < 30:
        try:
            if cdp.evaluate("document.readyState", timeout=10) == "complete": break
        except Exception: pass
        time.sleep(1)
    time.sleep(3)
    return cdp.evaluate(STATE_JS)

cdp, tid = new_tab()
try:
    for url in ["https://www.dreamstime.com/", "https://www.dreamstime.com/upload"]:
        st = visit(cdp, url)
        print("URL:", st["url"])
        print("  title:", st["title"][:60])
        print("  myAccount:", st["hasMyAccount"], "| username:", st["hasUsername"],
              "| loginForm:", st["hasLoginForm"], "| signOut:", st["hasSignOut"])
        print("  contributorish:", st["contributorish"], "| marketing:", st["isMarketing"],
              "| botWall:", st["botWall"])
        print("  text:", repr(st["text"][:400]))
        print()
finally:
    close_tab(cdp, tid)
print("DONE_MARKER")
