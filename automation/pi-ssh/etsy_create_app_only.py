#!/usr/bin/env python3
"""Create the Etsy seller app reusing the existing logged-in Pi session.

No OTP: assumes the persistent Chromium profile still holds a valid Etsy
session (from a recent OTP login). If the dashboard shows signed out, exits
with NEEDS_LOGIN instead of burning another OTP.
"""
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from cdp import launch, nap, wait_for_js
import etsy_login_and_create_app as base

RESULT2 = "/config/etsy-browser/shots/create_app_only_result.json"


def main():
    log = {"app_events": [], "app_name": base.APP_NAME,
           "redirect_uri_requested": base.REDIRECT_URI, "mode": "session_reuse"}
    cdp, proc = launch(headed=True)
    try:
        cdp.navigate("https://www.etsy.com/your/shops/me/dashboard")
        nap(3, 5)
        wait_for_js(cdp, "document.readyState === 'complete'", timeout=30)
        nap(2, 3)
        st = cdp.evaluate(base.state_js())
        base.snap(cdp, "cao_dashboard.png")
        if not st["signedIn"]:
            log["classification"] = "NEEDS_LOGIN"
            log["note"] = "session dead; a fresh OTP login is required"
            print("CLASSIFICATION: NEEDS_LOGIN")
            return
        log["app_events"].append("session alive, proceeding to app creation")
        base.do_create_app(cdp, log)
        print("CLASSIFICATION:", log.get("classification", "UNKNOWN"))
    finally:
        with open(RESULT2, "w") as f:
            json.dump(log, f, indent=1, ensure_ascii=False)
        print("result written to", RESULT2)


if __name__ == "__main__":
    main()
