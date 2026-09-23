#!/usr/bin/env python3
"""Probe: is the Pi Etsy session alive? Check homepage, shop dashboard,
and the direct seller-app creation URL."""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from cdp import launch, nap, wait_for_js

SHOTS = "/config/etsy-browser/shots"
RESULT = os.path.join(SHOTS, "session_probe.json")

ELS = """(function(){const o=[];function w(r){
  try{r.querySelectorAll('*').forEach(e=>o.push(e))}catch(e){}
  try{r.querySelectorAll('*').forEach(e=>{if(e.shadowRoot)w(e.shadowRoot)})}catch(e){}}
  w(document);return o})()"""


def state_js():
    return """(function(){
      const els = """ + ELS + """;
      const txt = document.body ? document.body.innerText.slice(0, 2500) : '';
      const low = txt.toLowerCase();
      const signedIn = !!document.querySelector('[data-login], [data-testid="user-nav"]')
        || /your shops|shop manager/i.test(txt);
      const datadome = low.includes('datadome') || low.includes('slide right')
        || low.includes('verify you are human');
      const isSignin = /special starts on etsy|email address/i.test(txt)
        && /sign in/i.test(txt);
      return {title: document.title, url: location.href,
              bodyStart: txt.slice(0, 900), datadome, signedIn, isSignin};
    })()"""


def main():
    out = {"checks": []}
    cdp, proc = launch(headed=True)
    try:
        for name, url, shot in [
            ("homepage", "https://www.etsy.com/", "probe_home.png"),
            ("shop_dashboard", "https://www.etsy.com/your/shops/me/dashboard", "probe_dash.png"),
            ("dev_new_app", "https://www.etsy.com/developers/your-apps/new", "probe_newapp.png"),
        ]:
            cdp.navigate(url)
            nap(3, 5)
            wait_for_js(cdp, "document.readyState === 'complete'", timeout=30)
            nap(2, 3)
            st = cdp.evaluate(state_js())
            out["checks"].append({"name": name, "url": st["url"],
                                  "title": st["title"], "signedIn": st["signedIn"],
                                  "isSignin": st["isSignin"], "datadome": st["datadome"],
                                  "body": st["bodyStart"][:700]})
            cdp.screenshot(os.path.join(SHOTS, shot))
            print("%s -> url=%s signedIn=%s isSignin=%s datadome=%s" % (
                name, st["url"], st["signedIn"], st["isSignin"], st["datadome"]))
    finally:
        with open(RESULT, "w") as f:
            json.dump(out, f, indent=1, ensure_ascii=False)
        try:
            cdp.close()
        except Exception:
            pass
        print("written", RESULT)


if __name__ == "__main__":
    main()
