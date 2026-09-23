#!/usr/bin/env python3
"""Press a key N times on the TTP tab, then screenshot. Usage: key_shot.py <url-sub> <name> <key> <count>"""
import sys, json, time, urllib.request
sys.path.insert(0, "/config/etsy-browser")
from cdp import CDP

KEYCODES = {"Home": 36, "End": 35, "PageUp": 33, "PageDown": 34, "Up": 38, "Down": 40, "Tab": 9, "Enter": 13, "Escape": 27}

substr, name = sys.argv[1], sys.argv[2]
key = sys.argv[3] if len(sys.argv) > 3 else "Home"
count = int(sys.argv[4]) if len(sys.argv) > 4 else 1
vk = KEYCODES.get(key, 36)

targets = json.loads(urllib.request.urlopen("http://127.0.0.1:9224/json/list", timeout=8).read())
pages = [t for t in targets if t.get("type") == "page" and substr in t.get("url", "")]
if not pages:
    print("NO_PAGE", file=sys.stderr)
    sys.exit(1)
c = CDP(pages[0]["webSocketDebuggerUrl"])
for _ in range(count):
    try:
        c.call("Input.dispatchKeyEvent", {"type": "keyDown", "key": key, "code": key, "windowsVirtualKeyCode": vk}, timeout=10)
        c.call("Input.dispatchKeyEvent", {"type": "keyUp", "key": key, "code": key, "windowsVirtualKeyCode": vk}, timeout=10)
    except Exception as e:
        print("key fail:", e, file=sys.stderr)
        break
    time.sleep(0.5)
time.sleep(1)
path = "/config/global-entry/shots/%s.png" % name
try:
    c.screenshot(path)
    print("OK " + path)
except Exception as e:
    print("shot fail:", e, file=sys.stderr)
    sys.exit(2)
c.close()
