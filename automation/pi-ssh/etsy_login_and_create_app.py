#!/usr/bin/env python3
"""One-session: Etsy email-OTP login + developer seller app creation.

Why one session: the login session proved short-lived across browser restarts,
so login and app creation now happen in a single browser process.

Flow:
  1. signin -> email -> Confirm it's you -> Try another method -> Send code to email
  2. wait for otp_code.txt (up to 15 min), fill code, Submit
  3. verify shop dashboard shows signed in
  4. developers portal -> Create a seller app -> Get started -> fill form -> submit
  5. extract keystring / shared secret / app id / scopes
     -> /config/etsy-browser/secrets/etsy_api.json (0600)

Stops (no fabrication) on: DataDome, API-terms gate, credit-card or phone
verification. Secrets never touch logs, result JSON, or screenshots.
"""
import json
import os
import re
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from cdp import launch, nap, wait_for_js

EMAIL = os.environ.get("ETSY_EMAIL", "")
SHOTS = "/config/etsy-browser/shots"
SECRETS_DIR = "/config/etsy-browser/secrets"
SECRETS_FILE = os.path.join(SECRETS_DIR, "etsy_api.json")
OTP_FILE = os.path.join(SHOTS, "otp_code.txt")
RESULT = os.path.join(SHOTS, "login_and_create_app_result.json")
os.makedirs(SHOTS, exist_ok=True)
os.makedirs(SECRETS_DIR, exist_ok=True)
os.chmod(SECRETS_DIR, 0o700)

APP_NAME = "ZenPixelWalls Automation"
APP_DESC = ("Personal automation for my own Etsy shop ZenPixelWalls: create and "
            "manage listings, upload images and digital files, and handle "
            "inventory via the Etsy Open API v3.")
REDIRECT_URI = "http://localhost:8080/etsy/callback"
WANT_SCOPES = ["listings_r", "listings_w", "shops_r", "shops_w"]


def els_js():
    return """(function(){const o=[];function w(r){
      try{r.querySelectorAll('*').forEach(e=>o.push(e))}catch(e){}
      try{r.querySelectorAll('*').forEach(e=>{if(e.shadowRoot)w(e.shadowRoot)})}catch(e){}}
      w(document);return o})()"""


def state_js():
    return """(function(){
      const els = """ + els_js() + """;
      const txt = document.body ? document.body.innerText.slice(0, 4000) : '';
      const low = txt.toLowerCase();
      const signedIn = !!document.querySelector('[data-login], [data-testid="user-nav"]')
        || /your shops|shop manager/i.test(txt);
      const datadome = low.includes('datadome') || low.includes('slide right')
        || low.includes('verify you are human');
      return {title: document.title, url: location.href,
              bodyStart: txt.slice(0, 1800), datadome, signedIn};
    })()"""


def find_el(cdp, tag_sub, text_sub, visible=True):
    return cdp.evaluate("""(function(){
      const els = """ + els_js() + """;
      const el = els.find(e => (e.tagName||'').toUpperCase().indexOf(""" + json.dumps(tag_sub.upper()) + """) >= 0
        && (e.innerText||'').toLowerCase().indexOf(""" + json.dumps(text_sub.lower()) + """) >= 0
        && (""" + ("true" if visible else "false") + """ ? !!e.offsetParent : true));
      if (!el) return null;
      const b = el.getBoundingClientRect();
      return {x: b.x + b.width/2, y: b.y + b.height/2, disabled: !!el.disabled};
    })()""")


def mouse_click(cdp, x, y):
    cdp.call("Input.dispatchMouseEvent",
             {"type": "mousePressed", "x": x, "y": y, "button": "left", "clickCount": 1})
    nap(0.1, 0.25)
    cdp.call("Input.dispatchMouseEvent",
             {"type": "mouseReleased", "x": x, "y": y, "button": "left", "clickCount": 1})


def snap(cdp, name):
    cdp.screenshot(os.path.join(SHOTS, name))


def list_fields(cdp):
    """Describe visible form fields (labels/placeholders only, never values)."""
    return cdp.evaluate("""(function(){
      const out = [];
      document.querySelectorAll('input, textarea, select').forEach(el => {
        if (el.type === 'hidden') return;
        if (!el.offsetParent && el.type !== 'checkbox') return;
        let label = '';
        if (el.id) { const lb = document.querySelector('label[for="' + el.id + '"]');
          if (lb) label = lb.innerText; }
        if (!label && el.name) {
          const lb = document.querySelector('label[for="' + el.name + '"]');
          if (lb) label = lb.innerText; }
        if (!label) { const lb = el.closest('label'); if (lb) label = lb.innerText; }
        out.push({tag: el.tagName, type: el.type || '', name: el.name || '',
                  id: el.id || '', placeholder: (el.placeholder || '').slice(0, 80),
                  label: (label || '').replace(/\\s+/g, ' ').slice(0, 100).trim(),
                  checked: !!el.checked});
      });
      return out;
    })()""")


def type_into(cdp, desc_keys, text):
    r = cdp.evaluate("""(function(desc){
      const cands = [];
      document.querySelectorAll('input, textarea').forEach(el => {
        if (el.type === 'hidden' || el.type === 'checkbox' || el.type === 'submit') return;
        if (!el.offsetParent) return;
        let label = '';
        if (el.id) { const lb = document.querySelector('label[for="' + el.id + '"]');
          if (lb) label = lb.innerText; }
        if (!label) { const lb = el.closest('label'); if (lb) label = lb.innerText; }
        const hay = ((el.name||'') + ' ' + (el.id||'') + ' ' + (el.placeholder||'') + ' ' + label).toLowerCase();
        if (desc.every(k => hay.indexOf(k) >= 0)) {
          const b = el.getBoundingClientRect();
          cands.push({x: b.x + b.width/2, y: b.y + b.height/2});
        }
      });
      return cands.length ? cands[0] : null;
    })(""" + json.dumps(desc_keys) + """)""")
    if not r:
        return False
    mouse_click(cdp, r["x"], r["y"])
    nap(0.4, 0.8)
    cdp.call("Input.dispatchKeyEvent", {"type": "keyDown", "modifiers": 2, "key": "a", "code": "KeyA", "windowsVirtualKeyCode": 65})
    cdp.call("Input.dispatchKeyEvent", {"type": "keyUp", "modifiers": 2, "key": "a", "code": "KeyA", "windowsVirtualKeyCode": 65})
    cdp.call("Input.dispatchKeyEvent", {"type": "keyDown", "key": "Backspace", "code": "Backspace", "windowsVirtualKeyCode": 8})
    cdp.call("Input.dispatchKeyEvent", {"type": "keyUp", "key": "Backspace", "code": "Backspace", "windowsVirtualKeyCode": 8})
    cdp.call("Input.insertText", {"text": text})
    nap(0.6, 1.2)
    return True


def has_terms_gate(cdp):
    """True only if there is an actual agreement checkbox (not a footer link)."""
    return cdp.evaluate("""(function(){
      const els = """ + els_js() + """;
      return els.some(e => e.tagName === 'INPUT' && e.type === 'checkbox' && !!e.offsetParent
        && /terms/.test((((e.closest('label') || {}).innerText) || '') + ' '
          + (e.name || '') + ' ' + (e.id || '') + ' '
          + ((e.parentElement || {}).innerText || '').slice(0, 200)).toLowerCase());
    })()""")


def click_seller_get_started(cdp):
    """Scroll the 'Create a seller app' card into view and click its button."""
    return cdp.evaluate("""(function(){
      const els = """ + els_js() + """;
      const heads = els.filter(e => /^(H1|H2|H3)$/.test(e.tagName || '')
        && /create a seller app/i.test(e.innerText || ''));
      for (const h of heads) {
        const card = h.closest('section, div');
        if (!card) continue;
        const btn = Array.from(card.querySelectorAll('button, a'))
          .find(b => /get started/i.test(b.innerText || '') && !!b.offsetParent)
          || els.find(e => /^(BUTTON|A)$/.test(e.tagName || '')
            && /get started/i.test(e.innerText || '') && !!e.offsetParent
            && card.contains(e));
        if (btn) {
          btn.scrollIntoView({block: 'center'});
          try { btn.click(); } catch (e) {}
          return {clicked: true, tag: btn.tagName};
        }
      }
      return {clicked: false};
    })()""")


def do_login(cdp, log):
    """Email-OTP login. Returns True when the shop dashboard shows signed in."""
    cdp.navigate("https://www.etsy.com/signin")
    nap(3, 5)
    wait_for_js(cdp, "document.readyState === 'complete'", timeout=30)
    nap(2, 3)
    st = cdp.evaluate(state_js())
    if st["datadome"]:
        log["login_classification"] = "DATADOME"; return False
    if st["signedIn"]:
        log["login_events"].append("already signed in, skipping OTP")
        return True

    er = cdp.evaluate("""(function(){
      const els = """ + els_js() + """;
      const em = els.find(e => e.tagName === 'INPUT' && e.name === 'email');
      if (!em) return null;
      const b = em.getBoundingClientRect();
      return {x: b.x + b.width/2, y: b.y + b.height/2};
    })()""")
    if not er:
        log["login_classification"] = "UNKNOWN_NO_EMAIL_INPUT"; return False
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
        log["login_classification"] = "UNKNOWN_NO_SIGNIN_BTN"; return False
    mouse_click(cdp, br["x"], br["y"])
    log["login_events"].append("clicked sign-in, email typed")
    t0 = time.time(); ok = False
    while time.time() - t0 < 30:
        time.sleep(2)
        st = cdp.evaluate(state_js())
        if "confirm" in st["bodyStart"].lower() and "code" in st["bodyStart"].lower():
            ok = True; break
        if st["datadome"]:
            break
    snap(cdp, "lca_otp_confirm.png")
    if st["datadome"]:
        log["login_classification"] = "DATADOME"; return False
    if not ok:
        # maybe we are already in (no 2FA this time)
        dst = cdp.evaluate(state_js())
        if dst["signedIn"]:
            log["login_events"].append("signed in without OTP this time")
            return True
        log["login_classification"] = "UNKNOWN_NO_CONFIRM_PAGE"; return False

    mr = find_el(cdp, "CLG-BUTTON", "try another method")
    if not mr:
        log["login_classification"] = "UNKNOWN_NO_TRY_ANOTHER"; return False
    mouse_click(cdp, mr["x"], mr["y"])
    nap(2, 3)
    cdp.evaluate("""(function(){
      const els = """ + els_js() + """;
      const el = els.find(e => /CLG-BUTTON$/.test(e.tagName) && /send code to email/i.test(e.innerText||''));
      if (el) el.click();
      return !!el;
    })()""")
    log["login_events"].append("clicked send-code-to-email")
    nap(2, 4)
    st = cdp.evaluate(state_js())
    # verify the page actually switched from phone-code to email-code mode;
    # the click can silently fail and leave the phone-code input on screen.
    switched = False
    st = cdp.evaluate(state_js())
    t0 = time.time()
    while time.time() - t0 < 15:
        time.sleep(2)
        st = cdp.evaluate(state_js())
        low = st["bodyStart"].lower()
        if "code" in low and "email" in low and "phone number" not in low:
            switched = True
            break
    snap(cdp, "lca_email_code_page.png")
    if not switched:
        log["login_classification"] = "UNKNOWN_NO_EMAIL_SWITCH"
        log["page_quote"] = st["bodyStart"][:400]
        return False
    log["login_events"].append("email code page confirmed")
    st = cdp.evaluate(state_js())
    log["login_classification"] = "CODE_TO_EMAIL_SENT"
    print("CLASSIFICATION: CODE_TO_EMAIL_SENT")
    print("WAITING_FOR_OTP_FILE:", OTP_FILE)

    code = None
    t0 = time.time()
    while time.time() - t0 < 900:
        if os.path.exists(OTP_FILE):
            code = open(OTP_FILE).read().strip()
            if code:
                break
        time.sleep(5)
    if not code:
        log["login_classification"] = "CODE_TIMEOUT"; return False
    log["login_events"].append("otp file received, len=%d" % len(code))
    # Fill via trusted input events (click + Ctrl+A + Backspace + insertText):
    # Etsy's component only enables Submit on real input events; setting
    # .value via JS leaves the button disabled and the click a no-op.
    if not type_into(cdp, ["6-digit"], code):
        log["login_classification"] = "UNKNOWN_CODE_FILL_FAILED"; return False
    nap(1.5, 2.5)
    snap(cdp, "lca_code_filled.png")
    sub = cdp.evaluate("""(function(){
      const els = """ + els_js() + """;
      const el = els.find(e => /CLG-BUTTON$/.test(e.tagName) && /submit/i.test(e.innerText||''));
      if (!el) return null;
      const b = el.getBoundingClientRect();
      return {x: b.x + b.width/2, y: b.y + b.height/2, disabled: !!el.disabled,
              aria: el.getAttribute('aria-disabled')};
    })()""")
    if not sub:
        log["login_classification"] = "UNKNOWN_NO_SUBMIT_BTN"; return False
    if sub.get("disabled") or sub.get("aria") == "true":
        log["login_events"].append("submit disabled after fill; pressing Enter")
        cdp.call("Input.dispatchKeyEvent", {"type": "keyDown", "key": "Enter", "code": "Enter", "windowsVirtualKeyCode": 13})
        cdp.call("Input.dispatchKeyEvent", {"type": "keyUp", "key": "Enter", "code": "Enter", "windowsVirtualKeyCode": 13})
    else:
        mouse_click(cdp, sub["x"], sub["y"])
    log["login_events"].append("submitted otp")
    # Honest post-submit verification: poll the CURRENT page for a real
    # signed-in state. Never infer login from a URL substring ("dashboard"
    # appears in /signin?from_page=...dashboard too).
    login_ok = False
    rejected = False
    st = cdp.evaluate(state_js())
    t0 = time.time()
    while time.time() - t0 < 30:
        low = (st.get("bodyStart") or "").lower()
        if any(k in low for k in ["incorrect", "wrong code", "try again",
                                 "expired", "invalid code", "doesn't match"]):
            rejected = True
            break
        if st.get("datadome"):
            break
        if st.get("signedIn") and "/signin" not in (st.get("url") or ""):
            login_ok = True
            break
        # left the signin flow without a signed-in signal -> bounced
        if "/signin" not in (st.get("url") or "") and "confirm" not in low:
            break
        time.sleep(3)
        st = cdp.evaluate(state_js())
    snap(cdp, "lca_after_submit.png")
    log["login_dashboard"] = {"title": st["title"], "url": st["url"],
                             "datadome": st["datadome"],
                             "signedIn": st["signedIn"]}
    if st["datadome"]:
        log["login_classification"] = "LOGGED_IN_DATADOME"; return False
    if rejected:
        log["login_classification"] = "CODE_REJECTED"
        log["page_quote"] = st["bodyStart"][:400]
        return False
    if login_ok:
        log["login_classification"] = "LOGGED_IN"
        log["login_events"].append("signed in verified after submit")
        return True
    log["login_classification"] = "LOGIN_FAILED"
    return False


def do_create_app(cdp, log):
    """Create the seller app in the already-logged-in session. Returns True on
    APP_CREATED with secrets saved."""
    cdp.navigate("https://www.etsy.com/developers/your-apps")
    nap(3, 5)
    wait_for_js(cdp, "document.readyState === 'complete'", timeout=30)
    nap(2, 3)
    st = cdp.evaluate(state_js())
    log["dev_landing"] = {"title": st["title"], "url": st["url"],
                         "datadome": st["datadome"], "signedIn": st["signedIn"]}
    if st["datadome"]:
        log["classification"] = "DATADOME"; return False
    if not st["signedIn"]:
        log["classification"] = "NOT_LOGGED_IN"; return False
    low = st["bodyStart"].lower()
    if "credit card" in low or "payment method" in low:
        log["classification"] = "NEEDS_USER_CARD"
        log["page_quote"] = st["bodyStart"][:600]; return False
    if "verify" in low and "phone" in low:
        log["classification"] = "NEEDS_USER_PHONE"
        log["page_quote"] = st["bodyStart"][:600]; return False
    if has_terms_gate(cdp):
        log["classification"] = "NEEDS_USER_TERMS"
        log["page_quote"] = st["bodyStart"][:600]; return False

    # Entry: developers portal landing -> "Create a seller app" -> Get started.
    # (/developers/your-apps/new is a 404 when hit directly; the click path lands
    # on /developers/register-seller-app.)
    cdp.navigate("https://www.etsy.com/developers/")
    nap(3, 5)
    wait_for_js(cdp, "document.readyState === 'complete'", timeout=30)
    nap(2, 3)
    st = cdp.evaluate(state_js())
    log["dev_landing"] = {"title": st["title"], "url": st["url"],
                          "datadome": st["datadome"], "signedIn": st["signedIn"]}
    if st["datadome"]:
        log["classification"] = "DATADOME"; return False
    if not st["signedIn"]:
        log["classification"] = "NOT_LOGGED_IN"; return False
    low = st["bodyStart"].lower()
    if "credit card" in low or "payment method" in low:
        log["classification"] = "NEEDS_USER_CARD"
        log["page_quote"] = st["bodyStart"][:600]; return False
    if "verify" in low and "phone" in low:
        log["classification"] = "NEEDS_USER_PHONE"
        log["page_quote"] = st["bodyStart"][:600]; return False
    if has_terms_gate(cdp):
        log["classification"] = "NEEDS_USER_TERMS"
        log["page_quote"] = st["bodyStart"][:600]; return False
    gs = click_seller_get_started(cdp)
    log["app_events"].append("seller get-started clicked: %s" % gs.get("clicked"))
    if not gs.get("clicked"):
        log["classification"] = "UNKNOWN_NO_GET_STARTED"; return False
    got_form = False
    t0 = time.time()
    while time.time() - t0 < 30:
        nap(1.5, 2.5)
        try:
            u = cdp.evaluate("location.href") or ""
        except Exception:
            continue
        if "/signin" in u:
            snap(cdp, "lca_stepup_signin.png")
            log["classification"] = "NEEDS_STEPUP_SIGNIN"
            log["page_quote"] = "register-seller-app bounced to /signin: session reclaimed or step-up auth required"
            return False
        url_ok = "register-seller-app" in u
        try:
            has_name = cdp.evaluate(
                "(function(){"
                "const els=[];function w(r){try{r.querySelectorAll('*').forEach(e=>els.push(e))}catch(e){}"
                "try{r.querySelectorAll('*').forEach(e=>{if(e.shadowRoot)w(e.shadowRoot)})}catch(e){}}"
                "w(document);"
                "return els.some(e=>(e.tagName==='INPUT'||e.tagName==='TEXTAREA')&&!!e.offsetParent"
                "&&/app name/i.test((e.placeholder||'')+' '+(e.name||'')+' '+(e.id||'')));"
                "})()")
        except Exception:
            continue
        if url_ok and has_name:
            got_form = True
            break
    if not got_form:
        snap(cdp, "lca_no_form.png")
        log["classification"] = "UNKNOWN_NO_APP_FORM"; return False
    log["app_events"].append("app creation form opened")
    nap(2, 3)
    st = cdp.evaluate(state_js())
    log["form_page"] = {"title": st["title"], "url": st["url"],
                       "datadome": st["datadome"]}
    if st["datadome"]:
        log["classification"] = "DATADOME"; return False
    if has_terms_gate(cdp):
        log["classification"] = "NEEDS_USER_TERMS"
        log["page_quote"] = st["bodyStart"][:600]; return False
    low = st["bodyStart"].lower()
    if "credit card" in low or "payment method" in low:
        log["classification"] = "NEEDS_USER_CARD"
        log["page_quote"] = st["bodyStart"][:600]; return False

    fields = list_fields(cdp)
    log["form_fields"] = fields
    snap(cdp, "lca_form.png")

    if not type_into(cdp, ["app", "name"], APP_NAME):
        log["classification"] = "UNKNOWN_NO_NAME_FIELD"
        snap(cdp, "lca_no_namefield.png"); return False
    log["app_events"].append("filled app name")
    if not (type_into(cdp, ["build"], APP_DESC)
            or type_into(cdp, ["descri"], APP_DESC)
            or type_into(cdp, ["about"], APP_DESC)):
        log["app_events"].append("warning: description field not found")
    else:
        log["app_events"].append("filled description")

    uri_ok = type_into(cdp, ["redirect"], REDIRECT_URI) or type_into(cdp, ["callback"], REDIRECT_URI)
    log["app_events"].append("redirect uri typed: %s" % uri_ok)
    if uri_ok:
        add = (find_el(cdp, "BUTTON", "add")
               or find_el(cdp, "BUTTON", "add uri")
               or find_el(cdp, "BUTTON", "add url"))
        if add:
            mouse_click(cdp, add["x"], add["y"])
            nap(1, 2)
            log["app_events"].append("clicked add for redirect uri")

    scopes_clicked = cdp.evaluate("""(function(want){
      const hit = [];
      document.querySelectorAll('input[type="checkbox"]').forEach(el => {
        if (!el.offsetParent) return;
        let label = '';
        if (el.id) { const lb = document.querySelector('label[for="' + el.id + '"]');
          if (lb) label = lb.innerText; }
        if (!label) { const lb = el.closest('label'); if (lb) label = lb.innerText; }
        const hay = ((el.name||'') + ' ' + (el.value||'') + ' ' + label).toLowerCase();
        for (const s of want) {
          if (hay.indexOf(s.replace('_',' ')) >= 0 || hay.indexOf(s) >= 0) {
            if (!el.checked) el.click();
            hit.push(s);
          }
        }
      });
      return hit;
    })(""" + json.dumps(WANT_SCOPES) + """)""")
    log["scopes_clicked_on_form"] = scopes_clicked
    snap(cdp, "lca_form_filled.png")
    nap(1, 2)

    sub = (find_el(cdp, "BUTTON", "create app")
           or find_el(cdp, "BUTTON", "create")
           or find_el(cdp, "BUTTON", "save")
           or find_el(cdp, "BUTTON", "submit"))
    if not sub:
        log["classification"] = "UNKNOWN_NO_SUBMIT"; return False
    mouse_click(cdp, sub["x"], sub["y"])
    log["app_events"].append("clicked submit")
    nap(4, 6)
    wait_for_js(cdp, "document.readyState === 'complete'", timeout=30)
    nap(2, 3)
    st = cdp.evaluate(state_js())
    log["after_submit"] = {"title": st["title"], "url": st["url"],
                          "datadome": st["datadome"]}
    low = st["bodyStart"].lower()
    if has_terms_gate(cdp):
        log["classification"] = "NEEDS_USER_TERMS"
        log["page_quote"] = st["bodyStart"][:600]; return False
    if "redirect" in low and ("invalid" in low or "must" in low or "https" in low):
        log["classification"] = "REDIRECT_URI_REJECTED"
        log["page_quote"] = st["bodyStart"][:600]; return False

    m = re.search(r"your-apps/(\d+)", st["url"] or "")
    app_id = m.group(1) if m else None
    log["app_id"] = app_id

    # reveal secrets via targeted JS; values stay in local vars only
    cdp.evaluate("""(function(){
      document.querySelectorAll('button, a').forEach(b => {
        const t = (b.innerText || '').toLowerCase();
        if (!/show|reveal|view/.test(t)) return;
        const ctx = (b.closest('div, section, li, tr') || {}).innerText || '';
        if (/secret|keystring|api key/i.test(ctx)) { try { b.click(); } catch(e){} }
      });
      return true;
    })()""")
    nap(1, 2)
    sec = cdp.evaluate("""(function(){
      const out = {keystring: null, shared_secret: null, scopes: []};
      const rows = [];
      document.querySelectorAll('*').forEach(el => {
        if (el.children.length === 0 && el.innerText) rows.push(el);
      });
      function near(labelRe) {
        for (const el of rows) {
          if (labelRe.test(el.innerText || '')) {
            const p = el.parentElement;
            if (!p) continue;
            const sib = p.innerText || '';
            const toks = sib.match(/[A-Za-z0-9_\\-]{16,}/g) || [];
            for (const t of toks) {
              if (!labelRe.test(t) && !/^(show|hide|reveal|copy|etsy|http)/i.test(t)) return t;
            }
          }
        }
        return null;
      }
      out.keystring = near(/keystring|api key/i);
      out.shared_secret = near(/shared secret/i);
      const low = (document.body.innerText || '').toLowerCase();
      ['listings_r','listings_w','shops_r','shops_w','inventory_r','inventory_w',
       'transactions_r','transactions_w'].forEach(s => {
        if (low.indexOf(s.replace('_',' ')) >= 0 || low.indexOf(s) >= 0) out.scopes.push(s);
      });
      return {keystring_len: out.keystring ? out.keystring.length : 0,
              shared_secret_len: out.shared_secret ? out.shared_secret.length : 0,
              scopes: out.scopes, _k: out.keystring, _s: out.shared_secret};
    })()""")
    keystring = sec.pop("_k", None)
    shared_secret = sec.pop("_s", None)
    log["secret_lengths"] = {"keystring_len": sec.get("keystring_len"),
                             "shared_secret_len": sec.get("shared_secret_len")}
    log["scopes_seen"] = sec.get("scopes", [])

    if keystring and shared_secret and app_id:
        payload = {"app_id": app_id, "app_name": APP_NAME,
                   "keystring": keystring, "shared_secret": shared_secret,
                   "redirect_uri": REDIRECT_URI,
                   "created_at": time.strftime("%Y-%m-%dT%H:%M:%S%z")}
        with open(SECRETS_FILE, "w") as f:
            json.dump(payload, f, indent=1)
        os.chmod(SECRETS_FILE, 0o600)
        log["secrets_saved"] = True
        log["redirect_uri_registered"] = REDIRECT_URI
        log["classification"] = "APP_CREATED"
        print("CLASSIFICATION: APP_CREATED app_id=%s" % app_id)
        return True
    log["secrets_saved"] = False
    log["classification"] = "APP_CREATED_NO_SECRETS"
    log["note"] = "app page reached but keystring/shared secret/app_id not all extracted"
    print("CLASSIFICATION: APP_CREATED_NO_SECRETS")
    return False


def main():
    log = {"login_events": [], "app_events": [], "app_name": APP_NAME,
           "redirect_uri_requested": REDIRECT_URI}
    if os.path.exists(OTP_FILE):
        os.remove(OTP_FILE)
    cdp, proc = launch(headed=True)
    try:
        if not do_login(cdp, log):
            log["classification"] = log.get("login_classification", "LOGIN_FAILED")
            print("CLASSIFICATION:", log["classification"])
            return
        log["app_events"].append("login ok, proceeding to app creation")
        do_create_app(cdp, log)
        print("CLASSIFICATION:", log.get("classification", "UNKNOWN"))
    finally:
        try:
            if os.path.exists(OTP_FILE):
                with open(OTP_FILE, "wb") as f:
                    f.write(b"\x00" * 64)
                os.remove(OTP_FILE)
        except Exception:
            pass
        with open(RESULT, "w") as f:
            json.dump(log, f, indent=1, ensure_ascii=False)
        try:
            cdp.close()
        except Exception:
            pass
        print("result written to", RESULT)


if __name__ == "__main__":
    main()
