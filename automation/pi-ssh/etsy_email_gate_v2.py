#!/usr/bin/env python3
"""Stage 1 (v2): Etsy email gate with shadow-DOM piercing.
Fill email, click "Sign in", record what happens next.
Logs JSON state to /config/etsy-browser/shots/email_gate_result.json
CLASSIFICATION: PASSWORD | EMAIL_LINK | EMAIL_LINK_SENT | DATADOME | UNKNOWN
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
EMAIL_JS = json.dumps(EMAIL)

PIERCE_JS = """(() => {
  const out = [];
  function walk(root) {
    try { root.querySelectorAll('*').forEach(el => out.push(el)); } catch(e) {}
    try { root.querySelectorAll('*').forEach(el => { if (el.shadowRoot) walk(el.shadowRoot); }); } catch(e) {}
  }
  walk(document);
  window.__etsyEls = out;
  const email = out.find(el => el.tagName === 'INPUT' && (el.name === 'email' || /email/i.test(el.id||''))) || null;
  const btn = out.find(el => el.tagName === 'BUTTON' && el.offsetParent && /\\bsign\\s*in\\b/i.test(el.innerText||'')) || null;
  return {emailFound: !!email, emailId: email ? email.id : null, emailType: email ? email.type : null,
          btnFound: !!btn, btnText: btn ? (btn.innerText||'').slice(0,40) : null, totalEls: out.length};
})()"""

FILL_JS = """(() => {
  const els = window.__etsyEls || [];
  const email = els.find(el => el.tagName === 'INPUT' && (el.name === 'email' || /email/i.test(el.id||'')));
  if (!email) return {ok:false, reason:'no-email-input'};
  email.focus();
  let setter = null, p = email;
  while (p && !setter) { const d = Object.getOwnPropertyDescriptor(p, 'value'); if (d && d.set) setter = d.set; p = Object.getPrototypeOf(p); }
  if (setter) setter.call(email, EMAILVAL); else email.value = EMAILVAL;
  email.dispatchEvent(new Event('input', {bubbles:true}));
  email.dispatchEvent(new Event('change', {bubbles:true}));
  email.dispatchEvent(new KeyboardEvent('keyup', {bubbles:true}));
  return {ok:true, id: email.id, name: email.name, val: email.value};
})()""".replace("EMAILVAL", EMAIL_JS)

CLICK_SIGNIN_JS = """(() => {
  const els = window.__etsyEls || [];
  const btn = els.find(el => el.tagName === 'BUTTON' && el.offsetParent && /\\bsign\\s*in\\b/i.test(el.innerText||''));
  if (!btn) return {ok:false,
    buttons: els.filter(el => el.tagName === 'BUTTON').map(b => (b.innerText||'').slice(0,40).trim()).filter(Boolean)};
  btn.scrollIntoView({block:'center'});
  btn.focus(); btn.click();
  return {ok:true, text: (btn.innerText||'').slice(0,60)};
})()"""

STATE_JS = """(() => {
  const out = [];
  function walk(root) {
    try { root.querySelectorAll('*').forEach(el => out.push(el)); } catch(e) {}
    try { root.querySelectorAll('*').forEach(el => { if (el.shadowRoot) walk(el.shadowRoot); }); } catch(e) {}
  }
  walk(document);
  window.__etsyEls = out;
  const txt = document.body ? document.body.innerText.slice(0, 3000) : '';
  const low = txt.toLowerCase();
  const inputs = out.filter(el => el.tagName === 'INPUT').map(el => ({
    type: el.type, name: el.name, id: el.id,
    placeholder: (el.placeholder||'').slice(0,60), visible: !!(el.offsetParent)}));
  const buttons = out.filter(el => el.tagName === 'BUTTON').map(el => ({
    type: el.type, text: (el.innerText || '').slice(0, 80).trim(),
    id: el.id, visible: !!(el.offsetParent)}));
  const datadome = low.includes('datadome') || low.includes('slide right')
    || low.includes('device check') || low.includes('verify you are human');
  return {title: document.title, url: location.href, bodyStart: txt.slice(0,1200),
          inputs, buttons: buttons.slice(0,25), datadome};
})()"""

def snap(cdp, name):
    cdp.screenshot(os.path.join(SHOTS, name))

def classify(state):
    if state["datadome"]:
        return "DATADOME"
    low = state["bodyStart"].lower()
    vis_inputs = [i for i in state["inputs"] if i.get("visible")]
    types = [i["type"] for i in vis_inputs]
    btns = " | ".join(b["text"] for b in state["buttons"] if b.get("visible"))
    if "password" in types:
        return "PASSWORD"
    if "email me a sign-in link" in btns.lower() or "send me a sign-in link" in btns.lower():
        return "EMAIL_LINK"
    if "check your email" in low or "sent you an email" in low or "sign-in link" in low:
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
        pierce = cdp.evaluate(PIERCE_JS)
        log["pierce"] = pierce
        snap(cdp, "gate2_signin.png")
        st0 = cdp.evaluate(STATE_JS)
        log["initial"] = {"title": st0["title"], "url": st0["url"], "datadome": st0["datadome"]}
        if st0["datadome"]:
            snap(cdp, "gate2_datadome.png")
            log["classification"] = "DATADOME"
            print("CLASSIFICATION: DATADOME")
            return
        fill = cdp.evaluate(FILL_JS)
        log["fill"] = fill
        snap(cdp, "gate2_email_filled.png")
        if not fill.get("ok"):
            log["classification"] = "UNKNOWN"
            print("CLASSIFICATION: UNKNOWN (fill failed)")
            return
        nap(1, 2)
        pierce2 = cdp.evaluate(PIERCE_JS)
        log["pierce_after_fill"] = pierce2
        clk = cdp.evaluate(CLICK_SIGNIN_JS)
        log["click_signin"] = clk
        if not clk.get("ok"):
            snap(cdp, "gate2_no_signin_btn.png")
            log["classification"] = "UNKNOWN"
            print("CLASSIFICATION: UNKNOWN (no sign-in button)")
            return
        t0 = time.time()
        st1 = None
        prev_url = st0["url"]
        while time.time() - t0 < 25:
            time.sleep(2)
            st1 = cdp.evaluate(STATE_JS)
            if st1["url"] != prev_url:
                break
        nap(1, 2)
        st1 = cdp.evaluate(STATE_JS)
        snap(cdp, "gate2_after_signin.png")
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
