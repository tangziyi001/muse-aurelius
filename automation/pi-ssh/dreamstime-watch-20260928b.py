#!/usr/bin/env python3
"""Dreamstime review watch 2026-09-28 part 2: text dumps for all pages +
screenshots for earnings/payout/tax-center. Robust CDP: reconnect per page."""
import json, os, sys, urllib.request, urllib.parse, time

sys.path.insert(0, "/config/etsy-browser")
from cdp import CDP, nap, wait_for_js

PORT = 9225
SHOTS = "/config/dreamstime-browser/shots"
PREFIX = "dreamstime-2026-09-28-"

DUMP_JS = """(function(){
  var txt = document.body ? document.body.innerText : '';
  var rows = Array.prototype.map.call(
    document.querySelectorAll('table tr'),
    function(tr){ return tr.innerText.replace(/\\s+/g,' ').trim(); }
  ).filter(function(s){ return s; });
  var links = Array.prototype.map.call(
    document.querySelectorAll('a'),
    function(a){ return (a.innerText||'').trim() + ' || ' + (a.href||''); }
  ).filter(function(s){ return s.indexOf('||') > 0 && s.length > 6; });
  var imgs = Array.prototype.map.call(
    document.querySelectorAll('img'),
    function(i){ return (i.alt||'').trim() + ' || ' + (i.src||''); }
  ).filter(function(s){ return s.indexOf('||') > 1 && s.length > 8; });
  var txt2 = document.body ? document.body.innerText.slice(0, 25000) : '';
  return { url: location.href, title: document.title,
           text: txt2, rows: rows.slice(0, 400),
           links: links.slice(0, 400), imgs: imgs.slice(0, 200) };
})()"""


def new_tab(url):
    q = urllib.parse.quote(url, safe='')
    req = urllib.request.Request("http://127.0.0.1:%d/json/new?%s" % (PORT, q), method="PUT")
    with urllib.request.urlopen(req, timeout=15) as r:
        info = json.loads(r.read())
    return info["webSocketDebuggerUrl"]


def visit(url, shot=None, timeout=60):
    ws = new_tab(url)
    cdp = CDP(ws)
    try:
        wait_for_js(cdp, "document.readyState === 'complete'", timeout=timeout)
        nap(2, 3)
        d = cdp.evaluate(DUMP_JS)
        if shot:
            cdp.screenshot(os.path.join(SHOTS, PREFIX + shot))
        return d
    finally:
        try:
            cdp.close()
        except Exception:
            pass


def main():
    out = {"pages": {}}
    targets = [
        ("account", "https://www.dreamstime.com/account", None),
        ("upload", "https://www.dreamstime.com/upload", None),
        ("under_review", "https://www.dreamstime.com/upload/under-review", None),
        ("online_files", "https://www.dreamstime.com/account/online-files", None),
    ]
    for name, url, shot in targets:
        out["pages"][name] = visit(url, shot)
        print("VISITED", name, out["pages"][name]["url"][:90], "OK")

    # discover nav links from account page
    link_urls = {}
    for l in out["pages"]["account"].get("links", []):
        low = l.lower()
        url = l.split("||")[-1].strip()
        if "refused" in low and "refused" not in link_urls:
            link_urls["refused"] = url
        if "statistics" in low and "statistics" not in link_urls:
            link_urls["statistics"] = url
        if "notification" in low and "notifications" not in link_urls:
            link_urls["notifications"] = url
        if "earning" in low and "earnings" not in link_urls:
            link_urls["earnings"] = url
        if ("payout" in low or "payment" in low) and "payout" not in link_urls:
            link_urls["payout"] = url
        if "tax" in low and "tax" not in link_urls:
            link_urls["tax"] = url
    out["account_links"] = link_urls
    print("LINKS:", json.dumps(link_urls)[:600])

    extra = []
    if link_urls.get("refused"):
        extra.append(("refused", link_urls["refused"], None))
    if link_urls.get("statistics"):
        extra.append(("statistics", link_urls["statistics"], None))
    if link_urls.get("notifications"):
        extra.append(("notifications", link_urls["notifications"], None))
    if link_urls.get("earnings"):
        extra.append(("earnings", link_urls["earnings"], "earnings.png"))
    if link_urls.get("payout"):
        extra.append(("payout", link_urls["payout"], "payout.png"))
    extra.append(("tax_center", "https://www.dreamstime.com/account/tax-center", "tax-center.png"))
    for name, url, shot in extra:
        try:
            out["pages"][name] = visit(url, shot)
            print("VISITED", name, out["pages"][name]["url"][:90], "OK")
        except Exception as e:
            out["pages"][name] = {"error": str(e)[:200], "requested_url": url}
            print("FAILED", name, str(e)[:150])

    out["status"] = "OK"
    with open(os.path.join(SHOTS, PREFIX + "dump.json"), "w") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    print("DUMP_SAVED")
    print("DONE_MARKER")


if __name__ == "__main__":
    main()
