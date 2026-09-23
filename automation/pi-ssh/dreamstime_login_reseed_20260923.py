#!/usr/bin/env python3
"""Dreamstime contributor login re-seed (2026-09-23, one-shot).

Attaches to the shared pi-browser Chromium (port 9225, profile
/config/pi-browser/profile) -- does NOT launch or kill any browser.
Creates a fresh tab for its own work, leaves all other tabs untouched.

Reads the Dreamstime password from /config/ftp-runner/secrets/dreamstime
ON THE PI ONLY, uses it in-process to fill the login form, and never
prints/logs/stores it anywhere.

Fail-fast: on DataDome/verify-human, reCAPTCHA, email-verification wall,
or any OTP/2FA step -> STOP immediately and report NEEDS_USER.
Only ONE login submit attempt; no retry loop.
NEVER clicks "Validate email" / "Verify email" or re-sends any link.
"""
import base64
import json
import os
import sys
import time
import urllib.request
import urllib.parse

sys.path.insert(0, "/config/etsy-browser")  # on-Pi CDP helper (no-Origin ws handshake)
from cdp import CDP  # noqa: E402  (raw-socket ws; passes Chromium origin check)

SHOTS = "/config/pi-browser/shots"
SECRET_PATH = "/config/ftp-runner/secrets/dreamstime"
USERNAME = "Tangziyi001"
PREFIX = "dreamstime-2026-09-23-login-"
RESULT_JSON = os.path.join(SHOTS, PREFIX + "result.json")

os.makedirs(SHOTS, exist_ok=True)

result = {
    "date": "2026-09-23",
    "signed_in": False,
    "dashboard_loaded": False,
    "challenge": "none",
    "needs_user": False,
    "needs_user_reason": "",
    "login_attempted": False,
    "review_counts": {},
    "notes": [],
}


def log(msg):
    print("[reseed] %s" % msg, flush=True)


def save_result():
    try:
        with open(RESULT_JSON, "w") as f:
            json.dump(result, f, indent=2)
    except Exception as e:
        log("could not write result json: %s" % e)


def http_get(url, timeout=10):
    with urllib.request.urlopen(url, timeout=timeout) as r:
        return r.read()


def http_put(url, timeout=10):
    req = urllib.request.Request(url, method="PUT")
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def http_delete(url, timeout=10):
    req = urllib.request.Request(url, method="DELETE")
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


# CDP class comes from /config/etsy-browser/cdp.py (imported above).
# Thin adapter adding the real_click helper used below.
class CDPWithClick(CDP):
    def real_click(self, x, y):
        self.call("Input.dispatchMouseEvent",
                  {"type": "mousePressed", "x": x, "y": y, "button": "left",
                   "clickCount": 1})
        time.sleep(0.15)
        self.call("Input.dispatchMouseEvent",
                  {"type": "mouseReleased", "x": x, "y": y, "button": "left",
                   "clickCount": 1})


STATE_JS = """(function(){
  var txt = document.body ? document.body.innerText.slice(0, 6000) : '';
  var low = txt.toLowerCase();
  return {
    url: location.href,
    title: document.title,
    signedIn: /sign out|log out/i.test(txt) || /${DREAMSTIME_USER}/i.test(txt),
    botWall: low.indexOf('datadome') !== -1
             || low.indexOf('verify you are human') !== -1
             || low.indexOf('slide right') !== -1
             || low.indexOf('please verify') !== -1,
    captcha: /recaptcha|i'm not a robot|i am not a robot/.test(low),
    emailWall: /validate your email|verify your email|verification email|confirm your email/i.test(txt),
    otp: /verification code|enter the code|two-factor|two factor|authenticator/i.test(txt),
    hasLoginForm: !!document.querySelector('input[type="password"]'),
    text: txt.slice(0, 1200)
  };
})()"""

FIND_FIELDS_JS = """(function(){
  function q(sels){ for (var i=0;i<sels.length;i++){ var el=document.querySelector(sels[i]); if(el) return el; } return null; }
  var user = q(['input[name="username"]','input[name="email"]','input[name="login"]',
                'input[id*="user" i]','input[id*="email" i]','input[id*="login" i]',
                'input[type="text"]','input:not([type])']);
  var pass = q(['input[name="password"]','input[type="password"]','input[id*="pass" i]']);
  var btn = q(['button[type="submit"]','input[type="submit"]']);
  if(!btn){
    var btns = Array.prototype.slice.call(document.querySelectorAll('button'));
    for (var i=0;i<btns.length;i++){
      if(/log ?in|sign ?in|submit/i.test(btns[i].innerText||'')){ btn=btns[i]; break; }
    }
  }
  function rect(el){ if(!el) return null; el.scrollIntoView({block:'center'}); var r=el.getBoundingClientRect();
    return {x:r.x+r.width/2, y:r.y+r.height/2, w:r.width, h:r.height}; }
  return {
    user: rect(user), pass: rect(pass), btn: rect(btn),
    userTag: user?user.outerHTML.slice(0,120):null,
    passTag: pass?pass.outerHTML.slice(0,120):null,
    btnTag: btn?btn.outerHTML.slice(0,160):null
  };
})()"""

# NOTE: password value is interpolated here on the Pi only; never logged.
FILL_JS_TEMPLATE = """(function(){
  var userVal = __USER_JSON__;
  var passVal = __PASS_JSON__;
  function q(sels){ for (var i=0;i<sels.length;i++){ var el=document.querySelector(sels[i]); if(el) return el; } return null; }
  function setNative(el, val){
    el.focus();
    var desc = Object.getOwnPropertyDescriptor(el, 'value')
            || Object.getOwnPropertyDescriptor(Object.getPrototypeOf(el), 'value')
            || Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value');
    if (desc && desc.set) { desc.set.call(el, val); } else { el.value = val; }
    el.dispatchEvent(new Event('input', {bubbles:true}));
    el.dispatchEvent(new Event('change', {bubbles:true}));
  }
  var user = q(['input[name="username"]','input[name="email"]','input[name="login"]',
                'input[id*="user" i]','input[id*="email" i]','input[id*="login" i]',
                'input[type="text"]','input:not([type])']);
  var pass = q(['input[name="password"]','input[type="password"]','input[id*="pass" i]']);
  if(!user || !pass) return {ok:false, reason:'fields not found'};
  setNative(user, userVal);
  setNative(pass, passVal);
  return {ok:true, userLen: user.value.length, passLen: pass.value.length};
})()"""

CLICK_BTN_JS = """(function(){
  function q(sels){ for (var i=0;i<sels.length;i++){ var el=document.querySelector(sels[i]); if(el) return el; } return null; }
  var btn = q(['button[type="submit"]','input[type="submit"]']);
  if(!btn){
    var btns = Array.prototype.slice.call(document.querySelectorAll('button'));
    for (var i=0;i<btns.length;i++){
      if(/log ?in|sign ?in|submit/i.test(btns[i].innerText||'')){ btn=btns[i]; break; }
    }
  }
  if(!btn) return null;
  btn.scrollIntoView({block:'center'});
  var r = btn.getBoundingClientRect();
  return {x: r.x + r.width/2, y: r.y + r.height/2};
})()"""

DASHBOARD_JS = """(function(){
  var txt = document.body ? document.body.innerText : '';
  var low = txt.toLowerCase();
  var isMarketing = /become a contributor|sell your (photos|images)|start selling/i.test(txt)
                    && !/my uploads|pending|upload files/i.test(txt);
  var counts = {};
  var m;
  var patterns = [
    [/([\\d,]+)\\s*(?:files?\\s+)?(?:in\\s+review|under\\s+review|pending\\s+(?:review|approval))/i, 'in_review'],
    [/([\\d,]+)\\s*(?:files?\\s+)?(?:approved|accepted)/i, 'accepted'],
    [/([\\d,]+)\\s*(?:files?\\s+)?(?:rejected|refused|declined)/i, 'refused']
  ];
  for (var i=0;i<patterns.length;i++){
    m = low.match(patterns[i][0]);
    if(m) counts[patterns[i][1]] = m[1];
  }
  var reasons = [];
  var rm = txt.match(/(?:reject|refus|declin)[^\\n]{0,120}/gi);
  if(rm) reasons = rm.slice(0,5);
  return {url: location.href, title: document.title,
          isMarketing: isMarketing,
          contributorish: /my uploads|upload files|pending approval|contributor/i.test(txt),
          counts: counts, reasons: reasons,
          text: txt.slice(0, 2500)};
})()"""


def wait_ready(cdp, timeout=40):
    t0 = time.time()
    while time.time() - t0 < timeout:
        try:
            v = cdp.evaluate("document.readyState", timeout=15)
            if v == "complete":
                return True
        except Exception:
            pass
        time.sleep(1)
    return False


def nap(a=2, b=3):
    time.sleep(a + (b - a) / 2.0)


def need_user(reason, challenge):
    result["needs_user"] = True
    result["needs_user_reason"] = reason
    result["challenge"] = challenge
    result["notes"].append("STOPPED: " + reason)
    log("NEEDS_USER: %s" % reason)
    save_result()


def main():
    log("attaching to shared Chromium on 9225 (no launch, no kill)")
    try:
        targets = json.loads(http_get("http://127.0.0.1:9225/json/list"))
    except Exception as e:
        log("FATAL: cannot reach DevTools on 9225: %s" % e)
        result["notes"].append("DevTools 9225 unreachable: %s" % e)
        save_result()
        return 2
    pages = [t for t in targets if t.get("type") == "page"]
    log("existing page targets: %d (leaving untouched)" % len(pages))
    for t in pages:
        log("  existing tab: %s | %s" % (t.get("title", "")[:50],
                                         t.get("url", "")[:70]))

    new_t = json.loads(http_put(
        "http://127.0.0.1:9225/json/new?" +
        urllib.parse.urlencode({"url": "about:blank"})))
    target_id = new_t["id"]
    ws_url = new_t["webSocketDebuggerUrl"]
    log("created own tab: %s" % target_id)
    cdp = None
    try:
        cdp = CDPWithClick(ws_url)
        cdp.call("Page.enable")

        # 1. homepage first: check bot wall + whether already signed in
        log("navigating to dreamstime homepage")
        cdp.navigate("https://www.dreamstime.com/")
        wait_ready(cdp)
        nap()
        cdp.screenshot(os.path.join(SHOTS, PREFIX + "01-homepage.png"))
        st = cdp.evaluate(STATE_JS)
        log("home: signedIn=%s botWall=%s url=%s" %
            (st["signedIn"], st["botWall"], st["url"]))
        if st["botWall"] or st["captcha"]:
            cdp.screenshot(os.path.join(SHOTS, PREFIX + "01b-botwall.png"))
            need_user("bot wall on homepage: %s" % st["text"][:200], "datadome/bot-wall")
            return 3
        if st["emailWall"]:
            need_user("email-verification wall on homepage", "email-verification")
            return 3
        if st["otp"]:
            need_user("OTP/2FA step on homepage", "otp-2fa")
            return 3

        if st["signedIn"]:
            log("already signed in via persisted profile -- skipping login form")
        else:
            # 2. login page
            log("navigating to login page")
            cdp.navigate("https://www.dreamstime.com/login")
            wait_ready(cdp)
            nap()
            cdp.screenshot(os.path.join(SHOTS, PREFIX + "02-loginpage.png"))
            st = cdp.evaluate(STATE_JS)
            log("login page: signedIn=%s botWall=%s hasLoginForm=%s url=%s" %
                (st["signedIn"], st["botWall"], st["hasLoginForm"], st["url"]))
            if st["botWall"] or st["captcha"]:
                need_user("bot wall / captcha on login page", "datadome/captcha")
                return 3
            if st["emailWall"]:
                need_user("email-verification wall on login page (NOT clicking validate)",
                          "email-verification")
                return 3
            if st["otp"]:
                need_user("OTP/2FA step on login page", "otp-2fa")
                return 3
            if st["signedIn"]:
                log("signed in (redirected while loading login page)")
            elif not st["hasLoginForm"]:
                need_user("no login form found; page text: %s" % st["text"][:200],
                          "unknown-login-page")
                return 3
            else:
                # 3. fill + submit ONCE
                try:
                    with open(SECRET_PATH, "r") as f:
                        password = f.read().strip()
                except Exception as e:
                    need_user("could not read on-Pi secret: %s" % e, "secret-unreadable")
                    return 3
                if not password:
                    need_user("on-Pi secret file is empty", "secret-empty")
                    return 3
                log("secret loaded: yes")
                fill_js = (FILL_JS_TEMPLATE
                           .replace("__USER_JSON__", json.dumps(USERNAME))
                           .replace("__PASS_JSON__", json.dumps(password)))
                password = None  # drop reference ASAP
                fr = cdp.evaluate(fill_js)
                log("fill result: %s" % {k: v for k, v in (fr or {}).items()
                                         if k in ("ok", "reason")})
                if not (fr and fr.get("ok")):
                    need_user("could not fill login fields: %s" % (fr or {}),
                              "form-fill-failed")
                    return 3
                nap(1, 2)
                cdp.screenshot(os.path.join(SHOTS, PREFIX + "02b-filled.png"))
                btn = cdp.evaluate(CLICK_BTN_JS)
                if not btn:
                    need_user("submit button not found", "submit-not-found")
                    return 3
                log("clicking submit ONCE at (%.0f, %.0f)" % (btn["x"], btn["y"]))
                result["login_attempted"] = True
                cdp.real_click(btn["x"], btn["y"])
                # wait for redirect / settle
                for _ in range(15):
                    time.sleep(2)
                    try:
                        cur = cdp.evaluate(
                            "(function(){return {url:location.href, rs:document.readyState};})()",
                            timeout=15)
                    except Exception:
                        continue
                    if cur and cur.get("rs") == "complete" and \
                       "/login" not in (cur.get("url") or ""):
                        break
                nap(2, 3)
                cdp.screenshot(os.path.join(SHOTS, PREFIX + "03-after-submit.png"))
                st = cdp.evaluate(STATE_JS)
                log("after submit: signedIn=%s url=%s botWall=%s captcha=%s emailWall=%s otp=%s" %
                    (st["signedIn"], st["url"], st["botWall"], st["captcha"],
                     st["emailWall"], st["otp"]))
                if st["botWall"] or st["captcha"]:
                    need_user("bot wall / captcha appeared after submit",
                              "datadome/captcha")
                    return 3
                if st["emailWall"]:
                    need_user("email-verification wall after submit (NOT clicking validate)",
                              "email-verification")
                    return 3
                if st["otp"]:
                    need_user("OTP/2FA step after submit", "otp-2fa")
                    return 3
                if not st["signedIn"]:
                    # ONE attempt only -- no retry loop
                    result["notes"].append(
                        "login submit did not sign in; page said: %s" % st["text"][:200])
                    log("login FAILED (single attempt, not retrying)")
                    save_result()
                    return 4

        result["signed_in"] = True
        log("SIGNED IN as %s" % USERNAME)

        # 4. contributor upload dashboard
        log("navigating to contributor upload dashboard")
        cdp.navigate("https://www.dreamstime.com/upload")
        wait_ready(cdp)
        nap(3, 4)
        cdp.screenshot(os.path.join(SHOTS, PREFIX + "04-upload.png"))
        d = cdp.evaluate(DASHBOARD_JS)
        log("upload page: url=%s title=%s contributorish=%s isMarketing=%s" %
            (d["url"], d["title"], d["contributorish"], d["isMarketing"]))
        if d["isMarketing"]:
            result["notes"].append("upload URL rendered marketing page, not dashboard")
            log("WARNING: marketing page instead of dashboard")
        else:
            result["dashboard_loaded"] = True
        if d["counts"]:
            result["review_counts"] = d["counts"]
            log("review counts found: %s" % d["counts"])
        else:
            result["notes"].append("no review counts parsed from upload page text")
        if d["reasons"]:
            result["review_counts"]["refusal_reasons_seen"] = d["reasons"]
        result["notes"].append("upload page text head: %s" % d["text"][:400])
        save_result()
        log("DONE: signed_in=True dashboard_loaded=%s" % result["dashboard_loaded"])
        return 0
    finally:
        if cdp is not None:
            try:
                cdp.close()
            except Exception:
                pass
        try:
            http_delete("http://127.0.0.1:9225/json/close/%s" % target_id)
            log("closed own tab %s; browser left running" % target_id)
        except Exception as e:
            log("could not close own tab: %s" % e)
        save_result()


if __name__ == "__main__":
    sys.exit(main())
