#!/usr/bin/env python3
"""Scrape online-files pages 1-7, extract (File ID, title) per file."""
import json, os, re, sys, urllib.request, urllib.parse

sys.path.insert(0, "/config/etsy-browser")
from cdp import CDP, nap, wait_for_js

PORT = 9225
DUMP_JS = """(function(){
  var txt = document.body ? document.body.innerText : '';
  return { url: location.href, text: txt };
})()"""


def new_tab(url):
    q = urllib.parse.quote(url, safe='')
    req = urllib.request.Request("http://127.0.0.1:%d/json/new?%s" % (PORT, q), method="PUT")
    with urllib.request.urlopen(req, timeout=15) as r:
        info = json.loads(r.read())
    return info["webSocketDebuggerUrl"]


def main():
    all_files = []
    for pg in range(1, 8):
        url = ("https://www.dreamstime.com/account/online-files"
               "?orderc=&itemstype=all&orderm=&srch=&pg=%d" % pg)
        ws = new_tab(url)
        cdp = CDP(ws)
        try:
            wait_for_js(cdp, "document.readyState === 'complete'", timeout=60)
            nap(3, 4)
            d = cdp.evaluate(DUMP_JS)
            pairs = re.findall(r"([^\n]{10,200}?)\n\n0 downloads[\s\S]*?File ID (\d+)", d["text"])
            for title, fid in pairs:
                all_files.append({"id": fid, "title": title.strip()})
            print("pg", pg, "->", len(pairs), "files", flush=True)
        except Exception as e:
            print("pg", pg, "FAILED:", str(e)[:150], flush=True)
        finally:
            try:
                cdp.close()
            except Exception:
                pass
    ids = sorted(set(f["id"] for f in all_files))
    out = {"files": all_files, "ids": ids}
    with open("/tmp/dt-online-2026-09-28.json", "w") as f:
        json.dump(out, f, indent=1)
    print("TOTAL_UNIQUE_IDS:", len(ids))
    print("IDS:", ",".join(ids))
    print("DONE_MARKER")


if __name__ == "__main__":
    main()
