#!/usr/bin/env python3
"""Stage 2: Etsy email-OTP login.
1. signin -> type email (real keys) -> click Sign in -> "Confirm it's you"
2. click "Try another method" -> click "Send code to email"
3. wait for /config/etsy-browser/shots/otp_code.txt (up to 5 min), then fill code -> Submit
4. verify https://www.etsy.com/your/shops/me/dashboard shows signed-in
"""
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from cdp import launch, nap, wait_for_js

EMAIL = os.environ.get("ETSY_EMAIL", "")
SHOTS = "/config/etsy-browser/shots"
OTP_FILE = os.path.join(SHOTS, "otp_code.txt")
RESULT = os.path.join(SHOTS, "otp_login_result.json")
os.makedirs(SHOTS, exist_ok=True)

def els_js():
    return """(function(){const o=[];function w(r){
      try{r.querySelectorAll('*').forEach(e=>o.push(e))}catch(e){}
      try{r.querySelectorAll('*').forEach(e=>{if(e.shadowRoot)w(e.shadowRoot)})}catch(e){}}
      w(document);return o})()"""

def state_js():
    return """(function(){
      const els = """ + els_js() + """;
      const txt = document.body ? document.body.innerText.slice(0, 3000) : '';
      const low = txt.toLowerCase();
      const inputs = els.filter(el => el.tagName === 'INPUT').map(el => ({
        type: el.type, name: el.name, id: el.id, visible: !!(el.offsetParent)}));
      const buttons = els.filter(el => /BUTTON$/.test(el.tagName)).map(el => ({
        tag: el.tagName, text: (el.innerText || '').slice(0, 60).trim(),
        disabled: !!el.disabled, visible: !!(el.offsetParent)}));
      const signedIn = !!document.querySelector('[data-login], [data-testid=\"user-nav\"]')
        || /your shops|shop manager/i.test(txt);
      const datadome = low.includes('datadome') || low.includes('slide right')
        || low.includes('verify you are human');
      return {title: document.title, url: location.href, bodyStart: txt.slice(0,1500),
              inputs, buttons: buttons.slice(0,25), datadome, signedIn};
    })()"""

def snap(cdp, name):
    cdp.screenshot(os.path.join(SHOTS, name))

def mouse_click(cdp, x, y):
    cdp.call("Input.dispatchMouseEvent",
             {"type": "mousePressed", "x": x, "y": y, "button": "left", "clickCount": 1})
    nap(0.1, 0.25)
    cdp.call("Input.dispatchMouseEvent",
             {"type": "mouseReleased", "x": x, "y": y, "button": "left", "clickCount": 1})

def find_el(cdp, tag_sub, text_sub, visible=True):
    """Case-insensitive substring match; no regex escaping pitfalls."""
    return cdp.evaluate("""(function(){
      const els = """ + els_js() + """;
      const el = els.find(e => (e.tagName||'').toUpperCase().indexOf(""" + json.dumps(tag_sub.upper()) + """) >= 0
        && (e.innerText||'').toLowerCase().indexOf(""" + json.dumps(text_sub.lower()) + """) >= 0
        && (""" + ("true" if visible else "false") + """ ? !!e.offsetParent : true));
      if (!el) return null;
      const b = el.getBoundingClientRect();
      return {x: b.x + b.width/2, y: b.y + b.height/2, disabled: !!el.disabled};
    })()""")

def main():
    log = {"events": []}
    # remove stale otp file
    if os.path.exists(OTP_FILE):
        os.remove(OTP_FILE)
    cdp, proc = launch(headed=True)
    try:
        cdp.navigate("https://www.etsy.com/signin")
        nap(3, 5)
        wait_for_js(cdp, "document.readyState === 'complete'", timeout=30)
        nap(2, 3)
        st = cdp.evaluate(state_js())
        log["initial_datadome"] = st["datadome"]
        if st["datadome"]:
            snap(cdp, "otp_datadome.png")
            log["classification"] = "DATADOME"; print("CLASSIFICATION: DATADOME"); return

        # type email with real keystrokes
        er = cdp.evaluate("""(function(){
          const els = """ + els_js() + """;
          const em = els.find(e => e.tagName === 'INPUT' && e.name === 'email');
          if (!em) return null;
          const b = em.getBoundingClientRect();
          return {x: b.x + b.width/2, y: b.y + b.height/2};
        })()""")
        if not er:
            log["classification"] = "UNKNOWN"; print("CLASSIFICATION: UNKNOWN (no email input)"); return
        mouse_click(cdp, er["x"], er["y"])
        nap(0.4, 0.8)
        cdp.call("Input.dispatchKeyEvent", {"type": "keyDown", "modifiers": 2, "key": "a", "code": "KeyA", "windowsVirtualKeyCode": 65})
        cdp.call("Input.dispatchKeyEvent", {"type": "keyUp", "modifiers": 2, "key": "a", "code": "KeyA", "windowsVirtualKeyCode": 65})
        cdp.call("Input.dispatchKeyEvent", {"type": "keyDown", "key": "Backspace", "code": "Backspace", "windowsVirtualKeyCode": 8})
        cdp.call("Input.dispatchKeyEvent", {"type": "keyUp", "key": "Backspace", "code": "Backspace", "windowsVirtualKeyCode": 8})
        cdp.call("Input.insertText", {"text": EMAIL})
        nap(1.0, 1.6)
        br = find_el(cdp, "CLG-BUTTON", "sign in")
        if not br:
            snap(cdp, "otp_no_btn.png")
            log["classification"] = "UNKNOWN"; print("CLASSIFICATION: UNKNOWN (no sign-in btn)"); return
        mouse_click(cdp, br["x"], br["y"])
        log["events"].append("clicked sign-in, email typed")
        # wait for "Confirm it's you"
        t0 = time.time(); ok = False
        while time.time() - t0 < 30:
            time.sleep(2)
            st = cdp.evaluate(state_js())
            if "confirm" in st["bodyStart"].lower() and "code" in st["bodyStart"].lower():
                ok = True; break
            if st["datadome"]:
                break
        snap(cdp, "otp_confirm.png")
        log["confirm_state"] = {"ok": ok, "body": st["bodyStart"][:800], "datadome": st["datadome"]}
        if st["datadome"]:
            log["classification"] = "DATADOME"; print("CLASSIFICATION: DATADOME"); return
        if not ok:
            log["classification"] = "UNKNOWN"; print("CLASSIFICATION: UNKNOWN (no confirm page)"); return

        # click "Try another method"
        mr = find_el(cdp, "CLG-BUTTON", "try another method")
        if not mr:
            log["classification"] = "UNKNOWN"; print("CLASSIFICATION: UNKNOWN (no try-another)"); return
        mouse_click(cdp, mr["x"], mr["y"])
        log["events"].append("clicked try-another-method")
        nap(2, 3)
        # click "Send code to email" (visible or not)
        sr = find_el(cdp, "CLG-BUTTON", "send code to email", visible=False)
        if not sr:
            snap(cdp, "otp_no_emailopt.png")
            st = cdp.evaluate(state_js())
            log["methods"] = st["buttons"]
            log["classification"] = "UNKNOWN"; print("CLASSIFICATION: UNKNOWN (no send-code-to-email option)"); return
        # if hidden, click via JS
        if sr.get("disabled") is None:
            pass
        cdp.evaluate("""(function(){
          const els = """ + els_js() + """;
          const el = els.find(e => /CLG-BUTTON$/.test(e.tagName) && /send code to email/i.test(e.innerText||''));
          if (el) el.click();
          return !!el;
        })()""")
        log["events"].append("clicked send-code-to-email")
        nap(2, 4)
        snap(cdp, "otp_email_sent.png")
        st = cdp.evaluate(state_js())
        log["sent_state"] = {"body": st["bodyStart"][:1000], "inputs": st["inputs"], "buttons": st["buttons"]}
        log["classification"] = "CODE_TO_EMAIL_SENT"
        print("CLASSIFICATION: CODE_TO_EMAIL_SENT")
        print("WAITING_FOR_OTP_FILE:", OTP_FILE)

        # wait for OTP code file (up to 15 min)
        code = None
        t0 = time.time()
        while time.time() - t0 < 900:
            if os.path.exists(OTP_FILE):
                code = open(OTP_FILE).read().strip()
                if code:
                    break
            time.sleep(5)
        if not code:
            log["classification"] = "CODE_TIMEOUT"; print("CLASSIFICATION: CODE_TIMEOUT"); return
        log["events"].append("otp file received, len=%d" % len(code))
        snap(cdp, "otp_before_submit.png")
        # fill the visible text input with the code
        filled = cdp.evaluate("""(function(code){
          const els = """ + els_js() + """;
          const inp = els.find(e => e.tagName === 'INPUT' && e.type === 'text' && !!e.offsetParent);
          if (!inp) return {ok:false};
          inp.focus();
          let setter = null, p = inp;
          while (p && !setter) { const d = Object.getOwnPropertyDescriptor(p, 'value'); if (d && d.set) setter = d.set; p = Object.getPrototypeOf(p); }
          if (setter) setter.call(inp, code); else inp.value = code;
          inp.dispatchEvent(new Event('input', {bubbles:true}));
          inp.dispatchEvent(new Event('change', {bubbles:true}));
          return {ok:true, name: inp.name, id: inp.id, val: inp.value};
        })(""" + json.dumps(code) + """)""")
        log["code_fill"] = filled
        nap(1, 2)
        sub = find_el(cdp, "CLG-BUTTON", "submit")
        if not sub:
            log["classification"] = "UNKNOWN"; print("CLASSIFICATION: UNKNOWN (no submit btn)"); return
        cdp.evaluate("""(function(){
          const els = """ + els_js() + """;
          const el = els.find(e => /CLG-BUTTON$/.test(e.tagName) && /submit/i.test(e.innerText||''));
          if (el) { el.scrollIntoView({block:'center'}); el.click(); }
          return !!el;
        })()""")
        log["events"].append("submitted otp")
        nap(3, 5)
        st = cdp.evaluate(state_js())
        snap(cdp, "otp_after_submit.png")
        log["after_submit"] = {"title": st["title"], "url": st["url"], "body": st["bodyStart"][:800], "datadome": st["datadome"]}
        # verify dashboard
        cdp.navigate("https://www.etsy.com/your/shops/me/dashboard")
        nap(3, 5)
        wait_for_js(cdp, "document.readyState === 'complete'", timeout=30)
        nap(2, 3)
        dst = cdp.evaluate(state_js())
        snap(cdp, "otp_dashboard.png")
        log["dashboard"] = {"title": dst["title"], "url": dst["url"],
                            "body": dst["bodyStart"][:1000], "datadome": dst["datadome"],
                            "signedIn": dst["signedIn"]}
        if dst["datadome"]:
            log["classification"] = "LOGGED_IN_DATADOME"; print("CLASSIFICATION: LOGGED_IN_DATADOME")
        elif dst["signedIn"] or "dashboard" in dst["url"]:
            log["classification"] = "LOGGED_IN"; print("CLASSIFICATION: LOGGED_IN")
            # dump cookies
            cookies = cdp.call("Network.getAllCookies", {})
            log["cookie_count"] = len(cookies.get("cookies", []))
            log["cookie_names"] = [c["name"] for c in cookies.get("cookies", [])]
        else:
            log["classification"] = "LOGIN_FAILED"; print("CLASSIFICATION: LOGIN_FAILED")
    finally:
        # shred otp file if it exists
        try:
            if os.path.exists(OTP_FILE):
                with open(OTP_FILE, "wb") as f:
                    f.write(b"\x00" * 64)
                os.remove(OTP_FILE)
        except Exception:
            pass
        with open(RESULT, "w") as f:
            json.dump(log, f, indent=1, ensure_ascii=False)
        cdp.close()
        print("result written to", RESULT)

if __name__ == "__main__":
    main()
