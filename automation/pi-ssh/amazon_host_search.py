#!/usr/bin/env python3
"""Phase 1: Amazon search for budget gaming desktops (1080 Ti host candidates).
Runs ON the Pi. Writes state JSON + screenshot to /config/pi-browser/shots/."""
import os, sys, json

sys.path.insert(0, "/config/etsy-browser")
import cdp as cdpmod

# own profile + debug port: do NOT touch the etsy-browser session (9222)
cdpmod.PROFILE_DIR = "/config/pi-browser/profile"
cdpmod.DEBUG_PORT = 9223

SHOTS = "/config/pi-browser/shots"
os.makedirs(SHOTS, exist_ok=True)
os.makedirs("/config/pi-browser/profile", exist_ok=True)

STATE_JS = (
    "(function(){"
    "  var items = [];"
    "  document.querySelectorAll('div[data-component-type=\"s-search-result\"]').forEach(function(el){"
    "    var a = el.querySelector('h2 a');"
    "    if (!a) return;"
    "    var priceEl = el.querySelector('.a-price .a-offscreen');"
    "    var ratingEl = el.querySelector('.a-icon-alt');"
    "    var href = a.getAttribute('href') || '';"
    "    if (href.charAt(0) === '/') href = 'https://www.amazon.com' + href;"
    "    items.push({"
    "      title: (a.innerText || '').trim(),"
    "      url: href.split('?')[0],"
    "      price: priceEl ? priceEl.innerText.trim() : null,"
    "      rating: ratingEl ? ratingEl.innerText.trim() : null"
    "    });"
    "  });"
    "  var bodyTxt = document.body ? document.body.innerText.slice(0, 2000) : '';"
    "  return {"
    "    url: location.href,"
    "    title: document.title,"
    "    botWall: /not a robot|enter the characters|unauthorized|captcha|verify you are human|continue shopping/i.test(bodyTxt + ' ' + document.title),"
    "    bodyHead: bodyTxt.slice(0, 500),"
    "    count: items.length,"
    "    items: items.slice(0, 20)"
    "  };"
    "})()"
)

def main():
    status_path = os.path.join(SHOTS, "amazon_search_state.json")
    cdp = None
    proc = None
    try:
        cdp, proc = cdpmod.launch(headed=True)
        cdp.navigate("https://www.amazon.com/s?k=STGAubron+gaming+PC")
        cdpmod.nap(4, 6)
        cdpmod.wait_for_js(cdp, "document.readyState === 'complete'", timeout=30)
        cdpmod.nap(2, 4)
        st = cdp.evaluate(STATE_JS)
        cdp.screenshot(os.path.join(SHOTS, "amazon_search.png"))
        st["phase"] = "search_done"
        with open(status_path, "w") as f:
            json.dump(st, f, indent=1)
        print("SEARCH_DONE count=" + str(st["count"]) + " botWall=" + str(st["botWall"]), flush=True)
    except Exception as e:
        with open(status_path, "w") as f:
            json.dump({"phase": "error", "error": str(e)}, f, indent=1)
        print("ERROR " + str(e), flush=True)
    finally:
        try:
            if cdp:
                cdp.close()
        except Exception:
            pass
        try:
            if proc:
                proc.terminate()
        except Exception:
            pass

if __name__ == "__main__":
    main()
