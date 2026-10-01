#!/usr/bin/env python3
"""Dreamstime review watch 2026-10-01 (read-only; submission step skips itself).

Attaches to the shared pi-browser chromium (port 9225), opens a NEW tab,
probes Dreamstime login state, collects counts (online census via File ID text
pattern per 9/30 lesson), under-review, unfinished, refused, stats, tax,
payout, notifications, and saves screenshots + JSON dumps.
Hard rules: never click validate/verify; never touch b04-05.jpg shell;
never submit anything (no new files expected); NEEDS_LOGIN -> stop, no login.
"""
import json, os, re, sys, urllib.request, urllib.parse

sys.path.insert(0, "/config/etsy-browser")
from cdp import CDP, nap, wait_for_js

PORT = 9225
SHOTS = "/config/dreamstime-browser/shots"
PREFIX = "dreamstime-2026-10-01-"
os.makedirs(SHOTS, exist_ok=True)

STATE_JS = r"""(function(){
  var txt = document.body ? document.body.innerText.slice(0, 6000) : '';
  var low = txt.toLowerCase();
  return {
    url: location.href,
    title: document.title,
    signedIn: /sign\s*out|tangziyi001/i.test(txt),
    loginForm: !!document.querySelector('input[type="password"]'),
    botWall: low.indexOf('datadome') >= 0 || low.indexOf('verify you are human') >= 0
             || /slide.{0,10}right/.test(low),
    validatePrompt: /validate (your )?email|verify (your )?email/i.test(txt)
  };
})()"""

DUMP_JS = r"""(function(){
  var txt = document.body ? document.body.innerText : '';
  var rows = Array.prototype.map.call(
    document.querySelectorAll('table tr'),
    function(tr){ return tr.innerText.replace(/\s+/g,' ').trim(); }
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
    text: txt.slice(0, 20000),
    rows: rows.slice(0, 400),
    links: links.slice(0, 400),
    imgs: imgs.slice(0, 200)
  };
})()"""

FILEID_JS = r"""(function(){
  var txt = document.body ? document.body.innerText : '';
  var ids = [];
  var re = /File ID\s*(\d+)/gi, m;
  while ((m = re.exec(txt)) !== null) ids.push(m[1]);
  var hint = null, hm = txt.match(/(\d+)\s+images/i);
  if (hm) hint = parseInt(hm[1], 10);
  return {ids: ids, countHint: hint, url: location.href, title: document.title};
})()"""


def new_tab(url):
    q = urllib.parse.quote(url, safe='')
    req = urllib.request.Request("http://127.0.0.1:" + str(PORT) + "/json/new?" + q, method="PUT")
    with urllib.request.urlopen(req, timeout=15) as r:
        info = json.loads(r.read())
    return info["webSocketDebuggerUrl"]


def visit(cdp, out, name, url, shot, nap_lo=2, nap_hi=4, fileids=False):
    try:
        cdp.navigate(url)
        wait_for_js(cdp, "document.readyState === 'complete'", timeout=60)
        nap(nap_lo, nap_hi)
        d = cdp.evaluate(DUMP_JS)
        d["url"] = url
        out["pages"][name] = d
        cdp.screenshot(os.path.join(SHOTS, PREFIX + shot))
        if fileids:
            out["fileid_" + name] = cdp.evaluate(FILEID_JS)
        return d
    except Exception as e:
        out.setdefault("errors", []).append({"page": name, "error": str(e)})
        return None


def main():
    out = {"pages": {}, "status": "UNKNOWN"}
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
            return

        # Tabs: upload (unfinished), under-review, refused, online-files census, stats, tax, payout
        visit(cdp, out, "upload", "https://www.dreamstime.com/upload", "upload.png")
        visit(cdp, out, "under_review", "https://www.dreamstime.com/upload/under-review", "under-review.png", fileids=True)
        visit(cdp, out, "refused", "https://www.dreamstime.com/upload/refused-files", "refused.png", fileids=True)

        # Online-files census: paginate &pg=N, File ID text pattern
        census = {"pages": {}, "ids": [], "countHint": None}
        seen = set()
        for pg in range(1, 12):
            u = "https://www.dreamstime.com/account/online-files?pg=" + str(pg)
            cdp.navigate(u)
            wait_for_js(cdp, "document.readyState === 'complete'", timeout=60)
            nap(1, 2)
            f = cdp.evaluate(FILEID_JS)
            census["pages"][str(pg)] = len(f["ids"])
            if census["countHint"] is None:
                census["countHint"] = f["countHint"]
            new = [i for i in f["ids"] if i not in seen]
            seen.update(new)
            census["ids"].extend(new)
            # stop rule: empty page after a full page, or reached countHint
            if len(f["ids"]) == 0 and pg > 1:
                break
            if census["countHint"] and len(seen) >= census["countHint"]:
                break
        out["online_census"] = {"pages": census["pages"], "ids": census["ids"],
                                "countHint": census["countHint"], "count": len(census["ids"])}
        cdp.screenshot(os.path.join(SHOTS, PREFIX + "online-files.png"))

        visit(cdp, out, "statistics", "https://www.dreamstime.com/account/statistics", "statistics.png")
        visit(cdp, out, "tax", "https://www.dreamstime.com/account/tax-center", "tax-center.png")
        visit(cdp, out, "payout", "https://www.dreamstime.com/account/request-payment", "payout.png")
        visit(cdp, out, "notifications", "https://www.dreamstime.com/account/notifications", "notifications.png")
        out["status"] = "OK"
    except Exception as e:
        out["status"] = "FAILED"
        out["fatal"] = str(e)
    finally:
        cdp.close()

    with open(os.path.join(SHOTS, PREFIX + "dump.json"), "w") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    summ = {"status": out.get("status"), "signedIn": out["home"]["signedIn"],
            "botWall": out["home"]["botWall"], "validatePrompt": out["home"]["validatePrompt"],
            "online": out.get("online_census", {}).get("count"),
            "online_hint": out.get("online_census", {}).get("countHint"),
            "pages": list(out.get("pages", {}).keys()), "errors": out.get("errors")}
    print(json.dumps(summ, ensure_ascii=False))
    print("DONE_MARKER")


if __name__ == "__main__":
    main()
