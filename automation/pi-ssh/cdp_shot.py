#!/usr/bin/env python3
"""Take a CDP screenshot of the TTP tab and print base64. Usage: cdp_shot.py <url-substring> <output-name>"""
import sys, json, time, urllib.request
sys.path.insert(0, "/config/etsy-browser")
from cdp import CDP

substr = sys.argv[1] if len(sys.argv) > 1 else "ttp.cbp.dhs.gov"
name = sys.argv[2] if len(sys.argv) > 2 else "shot"

targets = json.loads(urllib.request.urlopen("http://127.0.0.1:9224/json/list", timeout=8).read())
pages = [t for t in targets if t.get("type") == "page" and substr in t.get("url", "")]
if not pages:
    print("NO_PAGE", file=sys.stderr)
    sys.exit(1)
c = CDP(pages[0]["webSocketDebuggerUrl"])
path = "/config/global-entry/shots/%s.png" % name
c.screenshot(path)
print("OK " + path)
c.close()
