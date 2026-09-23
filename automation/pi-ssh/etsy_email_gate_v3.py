#!/usr/bin/env python3
"""Stage 1 (v3): real keystroke typing into email, click CLG-BUTTON Sign in,
classify next step: PASSWORD | EMAIL_LINK | EMAIL_LINK_SENT | DATADOME | UNKNOWN.
"""
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from cdp import launch, nap, wait_for_js

EMAIL = "" + os.environ.get("ETSY_EMAIL", "") + ""
SHOTS = "/config/etsy-browser/shots"
os.makedirs(SHOTS, exist_ok=True)
RESULT = os.path.join(SHOTS, "email_gate_result.json")

WALK_JS = """(function() {
  const out = [];
  function walk(root) {
    try { root.querySelectorAll('*').forEach(el => out.push(el)); } catch(e) {}
    try { root.querySelectorAll('*').forEach(el => { if (el.shadowRoot) walk(el.shadowRoot); }); } catch(e) {}
  }
  walk(document);
  return out;
})()"""

STATE_JS = """(() => {
  const out = [];
  function walk(root) {
    try { root.querySelectorAll('*').forEach(el => out.push(el)); } catch(e) {}
    try { root.querySelectorAll('*').forEach(el => { if (el.shadowRoot) walk(el.shadowRoot); }); } catch(e) {}
  }
  walk(document);
  const txt = document.body ? document.body.innerText.slice(0, 3000) : '';
  const low = txt.toLowerCase();
  const inputs = out.filter(el => el.tagName === 'INPUT').map(el => ({
    type: el.type, name: el.name, id: el.id,
    placeholder: (el.placeholder||'').slice(0,60), visible: !!(el.offsetParent)}));
  const buttons = out.filter(el => /BUTTON$/.test(el.tagName)).map(el => ({
    tag: el.tagName, text: (el.innerText || '').slice(0, 80).trim(),
    disabled: !!el.disabled, visible: !!(el.offsetParent)}));
  const datadome = low.includes('datadome') || low.includes('slide right')
    || low.includes('device check') || low.includes('verify you are human');
  return {title: document.title, url: location.href, bodyStart: txt.slice(0,1500),
          inputs, buttons: buttons.slice(0,25), datadome};
})()"""

def snap(cdp, name):
    cdp.screenshot(os.path.join(SHOTS, name))

def rect_of(cdp, js_expr):
    return cdp.evaluate(js_expr)

def mouse_click(cdp, x, y):
    cdp.call("Input.dispatchMouseEvent",
             {"type": "mousePressed", "x": x, "y": y, "button": "left", "clickCount": 1})
    nap(0.1, 0.25)
    cdp.call("Input.dispatchMouseEvent",
             {"type": "mouseReleased", "x": x, "y": y, "button": "left", "clickCount": 1})

def classify(state):
    if state["datadome"]:
        return "DATADOME"
    low = state["bodyStart"].lower()
    types = [i["type"] for i in state["inputs"] if i.get("visible")]
    btn_texts = " | ".join(b["text"] for b in state["buttons"])
    if "password" in types:
        return "PASSWORD"
    if "email me a sign-in link" in btn_texts.lower() or "send me a sign-in link" in btn_texts.lower():
        return "EMAIL_LINK"
    if "check your email" in low or "sent you an email" in low or "sign-in link" in low or "we've sent" in low:
        return "EMAIL_LINK_SENT"
    return "UNKNOWN"

def main():
    log = {"events": []}
    cdp, proc = launch(headed=True)
    try:
        cdp.navigate("https://www.etsy.com/signin")
        nap(3, 5)
        wait_for_js(cdp, "document.readyState === 'complete'", timeout=30)
        nap(2, 3)
        st0 = cdp.evaluate(STATE_JS)
        log["initial"] = {"title": st0["title"], "url": st0["url"], "datadome": st0["datadome"]}
        if st0["datadome"]:
            snap(cdp, "gate3_datadome.png")
            log["classification"] = "DATADOME"
            print("CLASSIFICATION: DATADOME")
            return

        # 1) focus email input with real mouse click
        r = cdp.evaluate("""(() => {
          const els = """ + WALK_JS + """;
          const em = els.find(el => el.tagName === 'INPUT' && el.name === 'email');
          if (!em) return null;
          const b = em.getBoundingClientRect();
          return {x: b.x + b.width/2, y: b.y + b.height/2};
        })()""")
        log["email_rect"] = r
        if not r:
            print("CLASSIFICATION: UNKNOWN (email input not found)")
            log["classification"] = "UNKNOWN"
            return
        mouse_click(cdp, r["x"], r["y"])
        nap(0.4, 0.8)
        # 2) select-all + delete (clear any residue), then real typing
        cdp.call("Input.dispatchKeyEvent", {"type": "keyDown", "modifiers": 2, "key": "a", "code": "KeyA", "windowsVirtualKeyCode": 65})
        cdp.call("Input.dispatchKeyEvent", {"type": "keyUp", "modifiers": 2, "key": "a", "code": "KeyA", "windowsVirtualKeyCode": 65})
        cdp.call("Input.dispatchKeyEvent", {"type": "keyDown", "key": "Backspace", "code": "Backspace", "windowsVirtualKeyCode": 8})
        cdp.call("Input.dispatchKeyEvent", {"type": "keyUp", "key": "Backspace", "code": "Backspace", "windowsVirtualKeyCode": 8})
        cdp.call("Input.insertText", {"text": EMAIL})
        nap(1.0, 1.6)
        val = cdp.evaluate("""(() => {
          const els = (function(){const o=[];function w(r){try{r.querySelectorAll('*').forEach(e=>o.push(e))}catch(e){}try{r.querySelectorAll('*').forEach(e=>{if(e.shadowRoot)w(e.shadowRoot)})}catch(e){}}w(document);return o})();
          const em = els.find(el => el.tagName === 'INPUT' && el.name === 'email');
          const btn = els.find(el => el.tagName === 'CLG-BUTTON' && /sign\\s*in/i.test(el.innerText||''));
          return {val: em ? em.value : null, btnDisabled: btn ? !!btn.disabled : null};
        })()""")
        log["after_type"] = val
        snap(cdp, "gate3_email_typed.png")
        if val.get("btnDisabled") is not False:
            # button still disabled: try blur + enter key on field
            cdp.call("Input.dispatchKeyEvent", {"type": "keyDown", "key": "Tab", "code": "Tab", "windowsVirtualKeyCode": 9})
            cdp.call("Input.dispatchKeyEvent", {"type": "keyUp", "key": "Tab", "code": "Tab", "windowsVirtualKeyCode": 9})
            nap(1, 1.5)

        # 3) click the Sign in button (CLG-BUTTON)
        br = cdp.evaluate("""(() => {
          const els = (function(){const o=[];function w(r){try{r.querySelectorAll('*').forEach(e=>o.push(e))}catch(e){}try{r.querySelectorAll('*').forEach(e=>{if(e.shadowRoot)w(e.shadowRoot)})}catch(e){}}w(document);return o})();
          const btn = els.find(el => el.tagName === 'CLG-BUTTON' && /sign\\s*in/i.test(el.innerText||''));
          if (!btn) return null;
          const b = btn.getBoundingClientRect();
          return {x: b.x + b.width/2, y: b.y + b.height/2, disabled: !!btn.disabled};
        })()""")
        log["btn_rect"] = br
        snap(cdp, "gate3_before_click.png")
        if not br:
            print("CLASSIFICATION: UNKNOWN (sign-in button not found)")
            log["classification"] = "UNKNOWN"
            return
        mouse_click(cdp, br["x"], br["y"])
        log["events"].append("clicked sign-in at %.0f,%.0f disabled=%s" % (br["x"], br["y"], br.get("disabled")))
        nap(2, 3)
        # 4) wait for change
        t0 = time.time()
        prev_url = st0["url"]
        st1 = None
        while time.time() - t0 < 30:
            time.sleep(2)
            st1 = cdp.evaluate(STATE_JS)
            if st1["url"] != prev_url or st1["datadome"]:
                break
        nap(1, 2)
        st1 = cdp.evaluate(STATE_JS)
        snap(cdp, "gate3_after_click.png")
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
