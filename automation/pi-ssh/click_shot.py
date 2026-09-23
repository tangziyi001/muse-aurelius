#!/usr/bin/env python3
"""Click at (x,y) CSS pixels on the TTP tab, wait, screenshot. Usage: click_shot.py <url-sub> <name> <x> <y> [wait_s]"""
import sys, json, time, urllib.request
sys.path.insert(0, "/config/etsy-browser")
from cdp import CDP

substr, name = sys.argv[1], sys.argv[2]
x, y = int(sys.argv[3]), int(sys.argv[4])
wait_s = int(sys.argv[5]) if len(sys.argv) > 5 else 4

targets = json.loads(urllib.request.urlopen("http://127.0.0.1:9224/json/list", timeout=8).read())
pages = [t for t in targets if t.get("type") == "page" and substr in t.get("url", "")]
if not pages:
    print("NO_PAGE", file=sys.stderr)
    sys.exit(1)
c = CDP(pages[0]["webSocketDebuggerUrl"])
c.call("Input.dispatchMouseEvent", {"type": "mouseMoved", "x": x, "y": y}, timeout=10)
time.sleep(0.3)
c.call("Input.dispatchMouseEvent", {"type": "mousePressed", "x": x, "y": y, "button": "left", "clickCount": 1}, timeout=10)
time.sleep(0.2)
c.call("Input.dispatchMouseEvent", {"type": "mouseReleased", "x": x, "y": y, "button": "left", "clickCount": 1}, timeout=10)
time.sleep(wait_s)
path = "/config/global-entry/shots/%s.png" % name
try:
    c.screenshot(path)
    print("OK " + path)
except Exception as e:
    print("shot fail (click done):", e, file=sys.stderr)
c.close()
