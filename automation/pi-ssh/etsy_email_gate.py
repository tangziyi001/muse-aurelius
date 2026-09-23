#!/usr/bin/env python3
"""Stage 1: Etsy email gate. Fill email, click Continue, record what happens next.
Logs JSON state to /config/etsy-browser/shots/email_gate_result.json
Exits 0 with classification: PASSWORD | EMAIL_LINK | DATADOME | UNKNOWN
"""
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from cdp import launch, nap, wait_for_js

EMAIL = os.environ.get("ETSY_EMAIL", "")
SHOTS = "/config/etsy-browser/shots"
os.makedirs(SHOTS, exist_ok=True)
RESULT = os.path.join(SHOTS, "email_gate_result.json")

STATE_JS = """(() => {
  const txt = document.body ? document.body.innerText.slice(0, 3000) : '';
  const low = txt.toLowerCase();
  const inputs = [...document.querySelectorAll('input')].map(el => ({
    type: el.type, name: el.name, id: el.id,
    placeholder: (el.placeholder||'').slice(0,60), visible: !!(el.offsetParent)
  }));
  const buttons = [...document.querySelectorAll('button')].map(el => ({
    type: el.type, text: (el.innerText || '').slice(0, 80).trim(),
    id: el.id, visible: !!(el.offsetParent)
  }));
  const datadome = low.includes('datadome') || low.includes('slide right')
    || low.includes('device check') || low.includes('captcha');
  return {title: document.title, url: location.href, bodyStart: txt.slice(0,1200),
          inputs, buttons: buttons.slice(0,25), datadome};
})()"""

EMAIL_JS = json.dumps(EMAIL)

FILL_JS = """(() => {
  const inputs = [...document.querySelectorAll('input')];
  const email = inputs.find(i => i.type === 'email')
    || inputs.find(i => /email|login/i.test(i.name||''))
    || inputs.find(i => /email|login/i.test(i.id||''));
  if (!email) return {ok:false, reason:'no-email-input',
    seen: inputs.map(i=>({type:i.type,name:i.name,id:i.id}))};
  email.focus();
  let setter = null;
  let p = email;
  while (p && !setter) {
    const d = Object.getOwnPropertyDescriptor(p, 'value');
    if (d && d.set) setter = d.set;
    p = Object.getPrototypeOf(p);
  }
  if (setter) setter.call(email, %s); else email.value = %s;
  email.dispatchEvent(new Event('input', {bubbles:true}));
  email.dispatchEvent(new Event('change', {bubbles:true}));
  return {ok:true, id: email.id, name: email.name, val: email.value};
})()""" % (EMAIL_JS, EMAIL_JS)

CLICK_CONTINUE_JS = """(() => {
  const norm = s => (s||'').replace(/\\s+/g,' ').trim().toLowerCase();
  let btn = [...document.querySelectorAll('button')]
    .find(b => b.offsetParent && /continue/.test(norm(b.innerText)));
  if (!btn) btn = [...document.querySelectorAll('input[type=submit]')]
    .find(b => b.offsetParent && /continue/i.test(b.value||''));
  if (!btn) return {ok:false, buttons: [...document.querySelectorAll('button')]
    .map(b => (b.innerText||'').slice(0,40).trim()).filter(Boolean)};
  btn.focus(); btn.click();
  return {ok:true, text: (btn.innerText||'').slice(0,60)};
})()"""

def snap(cdp, name):
    cdp.screenshot(os.path.join(SHOTS, name))

def classify(state):
    if state["datadome"]:
        return "DATADOME"
    low = state["bodyStart"].lower()
    types = [i["type"] for i in state["inputs"] if i.get("visible")]
    btns = " | ".join(b["text"] for b in state["buttons"])
    if "password" in types:
        return "PASSWORD"
    if "email me a sign-in link" in btns.lower() or "send me a sign-in link" in btns.lower():
        return "EMAIL_LINK"
    if "didn't receive" in low or "check your email" in low or "sign-in link" in low:
        return "EMAIL_LINK_SENT"
    return "UNKNOWN"

def main():
    log = {"events": []}
    cdp, proc = launch(headed=True)
    try:
        log["events"].append("browser launched")
        cdp.navigate("https://www.etsy.com/signin")
        nap(3, 5)
        wait_for_js(cdp, "document.readyState === 'complete'", timeout=30)
        nap(2, 3)
        snap(cdp, "gate_signin.png")
        st0 = cdp.evaluate(STATE_JS)
        log["initial"] = {"title": st0["title"], "url": st0["url"],
                          "datadome": st0["datadome"]}
        if st0["datadome"]:
            snap(cdp, "gate_datadome.png")
            log["classification"] = "DATADOME"
            print("CLASSIFICATION: DATADOME")
            return
        fill = cdp.evaluate(FILL_JS)
        log["fill"] = fill
        snap(cdp, "gate_email_filled.png")
        if not fill.get("ok"):
            log["classification"] = "UNKNOWN"
            print("CLASSIFICATION: UNKNOWN (fill failed)")
            return
        clk = cdp.evaluate(CLICK_CONTINUE_JS)
        log["click_continue"] = clk
        if not clk.get("ok"):
            snap(cdp, "gate_no_continue.png")
            log["classification"] = "UNKNOWN"
            print("CLASSIFICATION: UNKNOWN (no continue button)")
            return
        # wait for page to change: url change or new state
        t0 = time.time()
        st1 = None
        while time.time() - t0 < 25:
            time.sleep(2)
            st1 = cdp.evaluate(STATE_JS)
            if st1["url"] != st0["url"]:
                break
        nap(1, 2)
        st1 = cdp.evaluate(STATE_JS)
        snap(cdp, "gate_after_continue.png")
        log["after"] = st1
        cls = classify(st1)
        log["classification"] = cls
        print("CLASSIFICATION:", cls)
    finally:
        with open(RESULT, "w") as f:
            json.dump(log, f, indent=1, ensure_ascii=False)
        cdp.close()
        print("result written to", RESULT)

if __name__ == "__main__":
    main()
