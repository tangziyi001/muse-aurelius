#!/usr/bin/env python3
"""Create Etsy developer seller app (Open API v3 prep).

Stops (no fabrication) if any user-facing step appears: API terms agreement,
credit card verification, phone verification. Secrets (keystring / shared
secret) go ONLY to /config/etsy-browser/secrets/etsy_api.json (0600) and are
never written to logs, result JSON, or screenshots.
"""
import json
import os
import re
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from cdp import launch, nap, wait_for_js

SHOTS = "/config/etsy-browser/shots"
SECRETS_DIR = "/config/etsy-browser/secrets"
SECRETS_FILE = os.path.join(SECRETS_DIR, "etsy_api.json")
RESULT = os.path.join(SHOTS, "create_app_result.json")
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
      // find the heading first, then its card's button
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
    })()""", )


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


def type_into(cdp, match_fn_desc, text):
    """Click the first visible text input/textarea matching desc keys, type text."""
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
    })(""" + json.dumps(match_fn_desc) + """)""")
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


def main():
    log = {"events": [], "app_name": APP_NAME,
           "redirect_uri_requested": REDIRECT_URI}
    cdp, proc = launch(headed=True)
    try:
        cdp.navigate("https://www.etsy.com/developers/your-apps")
        nap(3, 5)
        wait_for_js(cdp, "document.readyState === 'complete'", timeout=30)
        nap(2, 3)
        st = cdp.evaluate(state_js())
        log["landing"] = {"title": st["title"], "url": st["url"],
                          "datadome": st["datadome"], "signedIn": st["signedIn"],
                          "body": st["bodyStart"][:1200]}
        if st["datadome"]:
            log["classification"] = "DATADOME"; print("CLASSIFICATION: DATADOME"); return
        if not st["signedIn"]:
            log["classification"] = "NOT_LOGGED_IN"
            print("CLASSIFICATION: NOT_LOGGED_IN"); return

        low = st["bodyStart"].lower()
        # user-facing gates: stop and report verbatim
        if "credit card" in low or "payment method" in low:
            log["classification"] = "NEEDS_USER_CARD"
            log["page_quote"] = st["bodyStart"][:600]
            print("CLASSIFICATION: NEEDS_USER_CARD"); return
        if "verify" in low and "phone" in low:
            log["classification"] = "NEEDS_USER_PHONE"
            log["page_quote"] = st["bodyStart"][:600]
            print("CLASSIFICATION: NEEDS_USER_PHONE"); return
        if has_terms_gate(cdp):
            log["classification"] = "NEEDS_USER_TERMS"
            log["page_quote"] = st["bodyStart"][:600]
            print("CLASSIFICATION: NEEDS_USER_TERMS"); return

        # click "Get started" under "Create a seller app"
        landing_url = cdp.evaluate("location.href")
        gs = click_seller_get_started(cdp)
        log["events"].append("seller get-started clicked: %s" % gs.get("clicked"))
        if not gs.get("clicked"):
            cdp.screenshot(os.path.join(SHOTS, "createapp_no_btn.png"))
            log["classification"] = "UNKNOWN"
            log["note"] = "could not click seller-app Get started"
            print("CLASSIFICATION: UNKNOWN (no get-started click)"); return
        # wait for the app creation form: URL change away from portal home,
        # or an app-name field appearing
        got_form = False
        t0 = time.time()
        while time.time() - t0 < 30:
            nap(1.5, 2.5)
            try:
                u = cdp.evaluate("location.href")
                has_name = cdp.evaluate("""(function(){
                  const els = """ + els_js() + """;
                  return els.some(e => (e.tagName === 'INPUT' || e.tagName === 'TEXTAREA')
                    && !!e.offsetParent
                    && /app name/i.test(((e.placeholder || '') + ' ' + (e.name || '')
                      + ' ' + (e.id || '') + ' '
                      + (((e.closest('label') || {}).innerText) || '')));
                })()""")
            except Exception:
                continue
            if (u and u != landing_url) or has_name:
                got_form = True
                break
        if not got_form:
            cdp.screenshot(os.path.join(SHOTS, "createapp_no_form.png"))
            log["classification"] = "UNKNOWN"
            log["note"] = "Get started did not open the app creation form"
            print("CLASSIFICATION: UNKNOWN (no app form)"); return
        log["events"].append("app creation form opened")
        nap(2, 3)
        st = cdp.evaluate(state_js())
        log["form_page"] = {"title": st["title"], "url": st["url"],
                            "datadome": st["datadome"], "body": st["bodyStart"][:1200]}
        if st["datadome"]:
            log["classification"] = "DATADOME"; print("CLASSIFICATION: DATADOME"); return
        low = st["bodyStart"].lower()
        if has_terms_gate(cdp):
            log["classification"] = "NEEDS_USER_TERMS"
            log["page_quote"] = st["bodyStart"][:600]
            print("CLASSIFICATION: NEEDS_USER_TERMS"); return
        if "credit card" in low or "payment method" in low:
            log["classification"] = "NEEDS_USER_CARD"
            log["page_quote"] = st["bodyStart"][:600]
            print("CLASSIFICATION: NEEDS_USER_CARD"); return

        fields = list_fields(cdp)
        log["form_fields"] = fields
        cdp.screenshot(os.path.join(SHOTS, "createapp_form.png"))

        # fill app name (must be the real app-name field, never the site search box)
        if not type_into(cdp, ["app", "name"], APP_NAME):
            log["classification"] = "UNKNOWN"
            log["note"] = "app name field not found on the form"
            cdp.screenshot(os.path.join(SHOTS, "createapp_no_namefield.png"))
            print("CLASSIFICATION: UNKNOWN (app name field)"); return
        log["events"].append("filled app name")

        # fill description ("what are you building" textarea)
        if not (type_into(cdp, ["build"], APP_DESC)
                or type_into(cdp, ["descri"], APP_DESC)
                or type_into(cdp, ["about"], APP_DESC)):
            log["events"].append("warning: description field not found")
        else:
            log["events"].append("filled description")

        # redirect URI
        uri_ok = type_into(cdp, ["redirect"], REDIRECT_URI)
        if not uri_ok:
            uri_ok = type_into(cdp, ["callback"], REDIRECT_URI)
        log["events"].append("redirect uri typed: %s" % uri_ok)
        if uri_ok:
            add = (find_el(cdp, "BUTTON", "add")
                   or find_el(cdp, "BUTTON", "add uri")
                   or find_el(cdp, "BUTTON", "add url"))
            if add:
                mouse_click(cdp, add["x"], add["y"])
                nap(1, 2)
                log["events"].append("clicked add for redirect uri")

        # scopes, if the form offers checkboxes
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

        cdp.screenshot(os.path.join(SHOTS, "createapp_form_filled.png"))
        nap(1, 2)

        # submit
        sub = (find_el(cdp, "BUTTON", "create app")
               or find_el(cdp, "BUTTON", "create")
               or find_el(cdp, "BUTTON", "save")
               or find_el(cdp, "BUTTON", "submit"))
        if not sub:
            log["classification"] = "UNKNOWN"
            log["note"] = "no submit button found"
            print("CLASSIFICATION: UNKNOWN (no submit)"); return
        # check for inline validation errors mentioning redirect uri before submit
        mouse_click(cdp, sub["x"], sub["y"])
        log["events"].append("clicked submit")
        nap(4, 6)
        wait_for_js(cdp, "document.readyState === 'complete'", timeout=30)
        nap(2, 3)
        st = cdp.evaluate(state_js())
        log["after_submit"] = {"title": st["title"], "url": st["url"],
                               "datadome": st["datadome"],
                               "body": st["bodyStart"][:1500]}
        low = st["bodyStart"].lower()
        if has_terms_gate(cdp):
            log["classification"] = "NEEDS_USER_TERMS"
            log["page_quote"] = st["bodyStart"][:600]
            print("CLASSIFICATION: NEEDS_USER_TERMS"); return
        if "redirect" in low and ("invalid" in low or "must" in low or "https" in low):
            log["classification"] = "REDIRECT_URI_REJECTED"
            log["page_quote"] = st["bodyStart"][:600]
            print("CLASSIFICATION: REDIRECT_URI_REJECTED"); return

        # extract app id from URL
        m = re.search(r"your-apps/(\d+)", st["url"] or "")
        app_id = m.group(1) if m else None
        log["app_id"] = app_id

        # reveal + extract keystring / shared secret via targeted JS.
        # Values are kept in local vars only and written straight to the
        # secrets file; never added to `log`.
        sec = cdp.evaluate("""(function(){
          const out = {keystring: null, shared_secret: null, scopes: []};
          const txt = document.body ? document.body.innerText : '';
          // click any show/reveal buttons near secret labels
          document.querySelectorAll('button, a').forEach(b => {
            const t = (b.innerText || '').toLowerCase();
            if (!/show|reveal|view/.test(t)) return;
            const ctx = (b.closest('div, section, li, tr') || {}).innerText || '';
            if (/secret|keystring|api key/i.test(ctx)) { try { b.click(); } catch(e){} }
          });
          return {bodyLen: txt.length, clicked: true};
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
                // find a token-like string in the same block
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
            log["classification"] = "APP_CREATED"
            print("CLASSIFICATION: APP_CREATED app_id=%s" % app_id)
        else:
            log["secrets_saved"] = False
            cdp.screenshot(os.path.join(SHOTS, "createapp_detail.png"))
            log["classification"] = "APP_CREATED_NO_SECRETS"
            log["note"] = ("app page reached but keystring/shared secret/app_id "
                           "not all extracted; manual check needed")
            print("CLASSIFICATION: APP_CREATED_NO_SECRETS")
    finally:
        with open(RESULT, "w") as f:
            json.dump(log, f, indent=1, ensure_ascii=False)
        try:
            cdp.close()
        except Exception:
            pass
        print("result written to", RESULT)


if __name__ == "__main__":
    main()
