#!/usr/bin/env python3
"""Dreamstime review watch 2026-09-28 (read-only unless new submissions found).
Attaches to the shared pi-browser chromium (port 9225), opens a NEW tab,
probes Dreamstime login state, dumps review counts and saves screenshots.
Never clicks validate/verify links. Never logs in.
"""
import json, os, sys, urllib.request, urllib.parse

sys.path.insert(0, "/config/etsy-browser")
from cdp import CDP, nap, wait_for_js

PORT = 9225
SHOTS = "/config/dreamstime-browser/shots"
PREFIX = "dreamstime-2026-09-28-"
os.makedirs(SHOTS, exist_ok=True)

STATE_JS = """(function(){
  var txt = document.body ? document.body.innerText.slice(0, 6000) : '';
  var low = txt.toLowerCase();
  return {
    url: location.href,
    title: document.title,
    signedIn: /sign\\s*out|tangziyi001/i.test(txt),
    loginForm: !!document.querySelector('input[type="password"]'),
    botWall: low.indexOf('datadome') >= 0 || low.indexOf('verify you are human') >= 0
             || /slide.{0,10}right/.test(low),
    validatePrompt: /validate (your )?email|verify (your )?email/i.test(txt)
  };
})()"""

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
  return {
    url: location.href,
    title: document.title,
    text: txt.slice(0, 15000),
    rows: rows.slice(0, 400),
    links: links.slice(0, 400),
    imgs: imgs.slice(0, 200)
  };
})()"""


def new_tab(url):
    q = urllib.parse.quote(url, safe='')
    req = urllib.request.Request("http://127.0.0.1:%d/json/new?%s" % (PORT, q), method="PUT")
    with urllib.request.urlopen(req, timeout=15) as r:
        info = json.loads(r.read())
    return info["webSocketDebuggerUrl"]


def main():
    out = {"pages": {}}
    ws = new_tab("https://www.dreamstime.com/")
    cdp = CDP(ws)
    try:
        wait_for_js(cdp, "document.readyState === 'complete'", timeout=45)
        nap(2, 3)
        st = cdp.evaluate(STATE_JS)
        out["home"] = {k: st[k] for k in ("url", "title", "signedIn", "loginForm", "botWall", "validatePrompt")}
        out["home_text"] = cdp.evaluate("document.body ? document.body.innerText.slice(0,4000) : ''")
        cdp.screenshot(os.path.join(SHOTS, PREFIX + "home.png"))

        if not st["signedIn"]:
            out["status"] = "NEEDS_LOGIN"
            with open(os.path.join(SHOTS, PREFIX + "dump.json"), "w") as f:
                json.dump(out, f, ensure_ascii=False, indent=1)
            print("STATUS: NEEDS_LOGIN")
            print("NEEDS_LOGIN_MARKER")
            return

        def visit(name, url, shot, nap_lo=2, nap_hi=4):
            cdp.navigate(url)
            wait_for_js(cdp, "document.readyState === 'complete'", timeout=60)
            nap(nap_lo, nap_hi)
            d = cdp.evaluate(DUMP_JS)
            out["pages"][name] = d
            cdp.screenshot(os.path.join(SHOTS, PREFIX + shot))
            return d

        # Account page first: harvest real link URLs for refused/statistics/notifications
        acct = visit("account", "https://www.dreamstime.com/account", "account.png")
        link_urls = {}
        for l in acct.get("links", []):
            low = l.lower()
            if "refused" in low:
                link_urls["refused"] = l.split("||")[-1].strip()
            if "statistics" in low:
                link_urls["statistics"] = l.split("||")[-1].strip()
            if "notification" in low and "notification" not in link_urls:
                link_urls["notifications"] = l.split("||")[-1].strip()
            if "online" in low and "files" in low and "online_files" not in link_urls:
                link_urls["online_files"] = l.split("||")[-1].strip()
            if "earning" in low and "earnings" not in link_urls:
                link_urls["earnings"] = l.split("||")[-1].strip()
            if "tax" in low and "tax" not in link_urls:
                link_urls["tax"] = l.split("||")[-1].strip()
            if ("payout" in low or "payment" in low) and "payout" not in link_urls:
                link_urls["payout"] = l.split("||")[-1].strip()
        out["account_links"] = link_urls

        visit("upload", "https://www.dreamstime.com/upload", "upload.png")
        visit("under_review", "https://www.dreamstime.com/upload/under-review", "under-review.png")
        visit("online_files", "https://www.dreamstime.com/account/online-files", "online-files.png")
        if link_urls.get("refused"):
            visit("refused", link_urls["refused"], "refused.png")
        if link_urls.get("statistics"):
            visit("statistics", link_urls["statistics"], "statistics.png")
        if link_urls.get("notifications"):
            visit("notifications", link_urls["notifications"], "notifications.png")
        if link_urls.get("earnings"):
            visit("earnings", link_urls["earnings"], "earnings.png")
        if link_urls.get("payout"):
            visit("payout", link_urls["payout"], "payout.png")
        visit("tax_center", "https://www.dreamstime.com/account/tax-center", "tax-center.png")

        out["status"] = "OK"
    finally:
        cdp.close()

    with open(os.path.join(SHOTS, PREFIX + "dump.json"), "w") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    print(json.dumps({"status": out.get("status"),
                      "home": out.get("home"),
                      "account_links": out.get("account_links", {}),
                      "pages": {n: {"url": p["url"], "title": p["title"]} for n, p in out["pages"].items()}},
                     ensure_ascii=False)[:3000])
    print("DONE_MARKER")


if __name__ == "__main__":
    main()
