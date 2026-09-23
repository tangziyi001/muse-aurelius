#!/usr/bin/env python3
"""Click at (x,y), then type text via insertText. Usage: type_at.py <url-sub> <x> <y> <text>"""
import sys, json, time, urllib.request
sys.path.insert(0, "/config/etsy-browser")
from cdp import CDP

substr = sys.argv[1]
x, y = int(sys.argv[2]), int(sys.argv[3])
text = sys.argv[4]

targets = json.loads(urllib.request.urlopen("http://127.0.0.1:9224/json/list", timeout=8).read())
pages = [t for t in targets if t.get("type") == "page" and substr in t.get("url", "")]
c = CDP(pages[0]["webSocketDebuggerUrl"])
c.call("Input.dispatchMouseEvent", {"type": "mouseMoved", "x": x, "y": y}, timeout=10)
time.sleep(0.2)
c.call("Input.dispatchMouseEvent", {"type": "mousePressed", "x": x, "y": y, "button": "left", "clickCount": 1}, timeout=10)
time.sleep(0.2)
c.call("Input.dispatchMouseEvent", {"type": "mouseReleased", "x": x, "y": y, "button": "left", "clickCount": 1}, timeout=10)
time.sleep(0.5)
# select all + delete to clear, then insert
c.call("Input.dispatchKeyEvent", {"type": "keyDown", "key": "a", "code": "KeyA", "windowsVirtualKeyCode": 65, "modifiers": 2}, timeout=10)
c.call("Input.dispatchKeyEvent", {"type": "keyUp", "key": "a", "code": "KeyA", "windowsVirtualKeyCode": 65, "modifiers": 2}, timeout=10)
time.sleep(0.2)
c.call("Input.dispatchKeyEvent", {"type": "keyDown", "key": "Backspace", "code": "Backspace", "windowsVirtualKeyCode": 8}, timeout=10)
c.call("Input.dispatchKeyEvent", {"type": "keyUp", "key": "Backspace", "code": "Backspace", "windowsVirtualKeyCode": 8}, timeout=10)
time.sleep(0.2)
c.call("Input.insertText", {"text": text}, timeout=10)
time.sleep(0.5)
print("TYPED")
c.close()
