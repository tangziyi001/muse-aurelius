#!/usr/bin/env python3
"""Dreamstime audit step 2: banners, tax center, messages — read-only."""
import json
import os
import re
import sys
import time
import urllib.request
import urllib.parse

sys.path.insert(0, "/config/etsy-browser")
from cdp import CDP  # noqa: E402

DEBUG_PORT = 9225
SHOTS = "/config/dreamstime-browser/shots"
os.makedirs(SHOTS, exist_ok=True)

OUT = {}

PAGE_DUMP_JS = """(function(){
  var txt = document.body ? document.body.innerText : '';
  var links = [];
  var as = document.querySelectorAll('a');
  for (var i=0;i<as.length;i++){
    var t=(as[i].innerText||'').replace(/\\s+/g,' ').trim();
    var h=as[i].getAttribute('href')||'';
    if (t.length>0 && t.length<80) links.push({text:t, href:h});
  }
  var banners = [];
  var sel = '.alert,.banner,.notification,.notice,.warning,.msg,.message,[role=alert]';
  document.querySelectorAll(sel).forEach(function(el){
    var t=(el.innerText||'').replace(/\\s+/g,' ').trim();
    if (t.length>0) banners.push(t);
  });
  return {url: location.href, title: document.title,
          body_head: txt.slice(0, 4000), links: links.slice(0, 120),
          banners: banners.slice(0, 20)};
})()"""

TAX_LINK_JS = """(function(){
  var as = document.querySelectorAll('a');
  for (var i=0;i<as.length;i++){
    var t=(as[i].innerText||'').replace(/\\s+/g,' ').trim().toLowerCase();
    if (t.indexOf('tax')>=0 || t.indexOf('fill your tax')>=0){
      return {text: as[i].innerText.trim(), href: as[i].href};
    }
  }
  return null;
})()"""

MSG_LINK_JS = """(function(){
  var as = document.querySelectorAll('a');
  for (var i=0;i<as.length;i++){
    var t=(as[i].innerText||'').replace(/\\s+/g,' ').trim().toLowerCase();
    if (t.indexOf('message')>=0 || t.indexOf('inbox')>=0){
      return {text: as[i].innerText.trim(), href: as[i].href};
    }
  }
  return null;
})()"""


def http_get(url, timeout=10):
    with urllib.request.urlopen(url, timeout=timeout) as r:
        return r.read()


def http_put_new(base):
    req = urllib.request.Request(
        base + "/json/new?" + urllib.parse.urlencode({"url": "about:blank"}),
        method="PUT")
    with urllib.request.urlopen(req, timeout=10) as r:
        return r.read()


def wait_ready(cdp, timeout=40):
    t0 = time.time()
    while time.time() - t0 < timeout:
        try:
            if cdp.evaluate("document.readyState", timeout=15) == "complete":
                return True
        except Exception:
            pass
        time.sleep(1)
    return False


def visit(cdp, name, url, sleep=4):
    cdp.navigate(url)
    wait_ready(cdp)
    time.sleep(sleep)
    dump = cdp.evaluate(PAGE_DUMP_JS) or {}
    shot = os.path.join(SHOTS, "step2-%s.png" % name)
    cdp.screenshot(shot)
    OUT[name] = {"url": dump.get("url"), "title": dump.get("title"),
                 "body_head": dump.get("body_head"),
                 "banners": dump.get("banners"),
                 "links": dump.get("links"),
                 "shot": shot}
    print("[audit] %s -> %s banners=%d" %
          (name, dump.get("url"), len(dump.get("banners") or [])), flush=True)
    return dump


def main():
    base = "http://127.0.0.1:%d" % DEBUG_PORT
    json.loads(http_get(base + "/json/list"))
    new_t = json.loads(http_put_new(base))
    target_id = new_t["id"]
    cdp = None
    try:
        cdp = CDP(new_t["webSocketDebuggerUrl"])
        cdp.call("Page.enable")
        dash = visit(cdp, "dashboard", "https://www.dreamstime.com/account")
        tax = cdp.evaluate(TAX_LINK_JS)
        print("[audit] tax link: %s" % json.dumps(tax), flush=True)
        OUT["tax_link"] = tax
        msg = cdp.evaluate(MSG_LINK_JS)
        print("[audit] msg link: %s" % json.dumps(msg), flush=True)
        OUT["msg_link"] = msg
        if tax and tax.get("href"):
            visit(cdp, "taxcenter", tax["href"])
        if msg and msg.get("href"):
            visit(cdp, "messages", msg["href"])
        # also probe the uploads page for any agreement banners
        visit(cdp, "uploads", "https://www.dreamstime.com/upload")
        with open(os.path.join(SHOTS, "step2-audit.json"), "w") as f:
            json.dump(OUT, f, indent=2, ensure_ascii=False)
        print("[audit] wrote audit json", flush=True)
        return 0
    finally:
        if cdp is not None:
            try:
                cdp.close()
            except Exception:
                pass
        try:
            req = urllib.request.Request(
                base + "/json/close/%s" % target_id, method="DELETE")
            urllib.request.urlopen(req, timeout=10).read()
        except Exception as e:
            print("[audit] close tab failed: %s" % e, flush=True)


if __name__ == "__main__":
    sys.exit(main())
