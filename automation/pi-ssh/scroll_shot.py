#!/usr/bin/env python3
"""Scroll the TTP tab with mouse wheel and screenshot. Usage: scroll_shot.py <url-sub> <name> <wheel-clicks> <deltaY>"""
import sys, json, time, urllib.request
sys.path.insert(0, "/config/etsy-browser")
from cdp import CDP

substr, name = sys.argv[1], sys.argv[2]
clicks = int(sys.argv[3]) if len(sys.argv) > 3 else 0
delta = int(sys.argv[4]) if len(sys.argv) > 4 else -120

targets = json.loads(urllib.request.urlopen("http://127.0.0.1:9224/json/list", timeout=8).read())
pages = [t for t in targets if t.get("type") == "page" and substr in t.get("url", "")]
if not pages:
    print("NO_PAGE", file=sys.stderr)
    sys.exit(1)
c = CDP(pages[0]["webSocketDebuggerUrl"])
for _ in range(clicks):
    try:
        c.call("Input.dispatchMouseEvent",
               {"type": "mouseWheel", "x": 682, "y": 312, "deltaX": 0, "deltaY": delta},
               timeout=10)
    except Exception as e:
        print("wheel fail:", e, file=sys.stderr)
        break
    time.sleep(0.4)
time.sleep(1)
path = "/config/global-entry/shots/%s.png" % name
try:
    c.screenshot(path)
    print("OK " + path)
except Exception as e:
    print("shot fail:", e, file=sys.stderr)
    sys.exit(2)
c.close()
