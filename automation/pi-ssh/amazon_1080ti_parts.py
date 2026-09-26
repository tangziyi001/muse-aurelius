#!/usr/bin/env python3
"""Amazon product discovery via Pi browser: PSU + Dell OptiPlex MT host for a GTX 1080 Ti.

Runs ON the Pi. Discovery only: no login, no cart, no purchase.
Output: /config/pi-browser/shots/amazon_1080ti_raw.json + screenshots.

Category A - PSU: 550W+, EVGA/Corsair/Thermaltake/SeaSonic, 8-pin(6+2)+6-pin PCIe,
  80+ Bronze preferred, target $35-65.
Category B - refurb desktop: Dell OptiPlex MT (mini tower ONLY; SFF/USFF/Micro excluded),
  i5/i7 4th-gen+, 8GB+ preferred, target $90-160.
"""
import os
import re
import sys
import json

sys.path.insert(0, "/config/etsy-browser")
import cdp as cdpmod

cdpmod.PROFILE_DIR = "/config/pi-browser/profile"
cdpmod.DEBUG_PORT = 9223

SHOTS = "/config/pi-browser/shots"
OUT = os.path.join(SHOTS, "amazon_1080ti_raw.json")
os.makedirs(SHOTS, exist_ok=True)
os.makedirs("/config/pi-browser/profile", exist_ok=True)

WALL_JS = """(function(){
  var t = (document.body ? document.body.innerText : '').slice(0, 3000);
  var low = t.toLowerCase();
  return {
    url: location.href,
    title: document.title,
    wall: low.indexOf('enter the characters') >= 0 || low.indexOf('not a robot') >= 0 ||
          low.indexOf('captcha') >= 0 || low.indexOf('verify you are human') >= 0 ||
          low.indexOf('unauthorized') >= 0,
    head: t.slice(0, 400)
  };
})()"""

SEARCH_JS = """(function(){
  var items = [];
  var els = document.querySelectorAll('div[data-component-type="s-search-result"]');
  for (var i = 0; i < els.length; i++) {
    var el = els[i];
    var a = el.querySelector('h2 a');
    if (!a) continue;
    var priceEl = el.querySelector('.a-price .a-offscreen');
    var href = a.getAttribute('href') || '';
    if (href.charAt(0) === '/') href = 'https://www.amazon.com' + href;
    items.push({
      title: (a.innerText || '').trim(),
      url: href.split('?')[0],
      price: priceEl ? priceEl.innerText.trim() : null
    });
  }
  return items;
})()"""

PRODUCT_JS = """(function(){
  var out = {url: location.href};
  var m = location.href.match(/\\/dp\\/([A-Z0-9]{10})/);
  out.asin = m ? m[1] : null;
  if (out.asin) out.canon = 'https://www.amazon.com/dp/' + out.asin;
  var t = document.getElementById('productTitle');
  out.title = t ? t.innerText.trim().replace(/\\s+/g, ' ') : document.title;
  var p = document.querySelector('.a-price .a-offscreen');
  out.price = p ? p.innerText.trim() : null;
  var av = document.querySelector('#availability .a-size-medium');
  out.availability = av ? av.innerText.trim().replace(/\\s+/g, ' ') : null;
  out.addable = !!document.querySelector('#add-to-cart-button');
  var by = document.getElementById('bylineInfo');
  out.brandline = by ? by.innerText.trim().replace(/\\s+/g, ' ') : null;
  out.bullets = [];
  var bl = document.querySelectorAll('#feature-bullets li');
  for (var i = 0; i < bl.length; i++) {
    var s = bl[i].innerText.trim().replace(/\\s+/g, ' ');
    if (s) out.bullets.push(s.slice(0, 300));
  }
  out.specs = {};
  var rows = document.querySelectorAll(
    '#productDetails_techSpec_section_1 tr, #productDetails_detailBullets_sections1 tr');
  for (var j = 0; j < rows.length; j++) {
    var th = rows[j].querySelector('th'), td = rows[j].querySelector('td');
    if (th && td) out.specs[th.innerText.trim()] = td.innerText.trim().slice(0, 200);
  }
  var img = document.querySelector('#landingImage');
  out.image = img ? (img.getAttribute('data-old-hires') || img.getAttribute('src')) : null;
  return out;
})()"""

SCROLL_JS = "window.scrollTo(0, document.body.scrollHeight); 'done:' + document.body.scrollHeight;"

PSU_BRANDS = ["evga", "corsair", "thermaltake", "seasonic"]
WATT_RE = re.compile(r"\b(450|500|550|600|650|700|750|850)\s?W\b", re.I)


def parse_price(s):
    if not s:
        return None
    s = s.replace(",", "")
    m = re.search(r"\$(\d+\.\d{2})", s)
    if m:
        return float(m.group(1))
    m = re.search(r"\$(\d+)", s)
    return float(m.group(1)) if m else None


def psu_ok(title, price):
    if price is None or not (35 <= price <= 65):
        return False
    t = title.lower()
    if not any(b in t for b in PSU_BRANDS):
        return False
    if not WATT_RE.search(title):
        return False
    if any(x in t for x in ["tester", "cable", "adapter", "bracket", "extension"]):
        return False
    return True


def opti_ok(title, price):
    if price is None or not (90 <= price <= 160):
        return False
    tu = title.upper()
    if "OPTIPLEX" not in tu:
        return False
    tokens = re.split(r"[\s\-/(),]+", tu)
    is_mt = "MT" in tokens or "MINI TOWER" in tu or "MINI-TOWER" in tu
    if not is_mt:
        return False
    if any(x in tu for x in ["SFF", "USFF", "MICRO", "ALL-IN-ONE", "AIO"]):
        return False
    return True


def do_search(cdp, name, search_url, ok_fn, max_visit, shot_prefix, state):
    print("SEARCH %s: %s" % (name, search_url), flush=True)
    cdp.navigate(search_url)
    cdpmod.nap(4, 6)
    cdpmod.wait_for_js(cdp, "document.readyState === 'complete'", timeout=40)
    for _ in range(2):
        cdp.evaluate(SCROLL_JS)
        cdpmod.nap(2, 3)
    wall = cdp.evaluate(WALL_JS)
    if wall.get("wall"):
        cdp.screenshot(os.path.join(SHOTS, shot_prefix + "_wall.png"))
        state["blocked"] = True
        state["wall_info"] = wall
        print("WALL detected on %s search, stopping" % name, flush=True)
        return []
    items = cdp.evaluate(SEARCH_JS) or []
    cdp.screenshot(os.path.join(SHOTS, shot_prefix + "_search.png"))
    print("SEARCH %s: raw=%d" % (name, len(items)), flush=True)
    seen, cands = set(), []
    for it in items:
        u = it.get("url") or ""
        if not u or u in seen:
            continue
        pr = parse_price(it.get("price"))
        if not ok_fn(it.get("title", ""), pr):
            continue
        seen.add(u)
        cands.append({"search_title": it.get("title"), "search_price": it.get("price"),
                      "price_num": pr, "url": u})
        if len(cands) >= max_visit:
            break
    print("SEARCH %s: filtered=%d" % (name, len(cands)), flush=True)
    visited = []
    for i, it in enumerate(cands):
        try:
            cdp.navigate(it["url"])
            cdpmod.nap(4, 6)
            cdpmod.wait_for_js(cdp, "document.readyState === 'complete'", timeout=40)
            cdpmod.nap(2, 3)
            prod = cdp.evaluate(PRODUCT_JS) or {}
            prod["search_title"] = it["search_title"]
            prod["search_price_num"] = it["price_num"]
            wall2 = cdp.evaluate(WALL_JS)
            if wall2.get("wall"):
                prod["wall"] = True
                state["blocked"] = True
                cdp.screenshot(os.path.join(SHOTS, shot_prefix + "_prod%d_wall.png" % i))
                print("WALL on product page, stopping visits", flush=True)
                visited.append(prod)
                break
            visited.append(prod)
            cdp.screenshot(os.path.join(SHOTS, shot_prefix + "_prod%d.png" % i))
            print("VISIT %s %d: price=%s addable=%s" %
                  (name, i, prod.get("price"), prod.get("addable")), flush=True)
        except Exception as e:
            visited.append({"url": it.get("url"), "error": str(e)})
            print("VISIT %s %d ERROR: %s" % (name, i, e), flush=True)
    return visited


def main():
    state = {"phase": "started", "blocked": False, "psu": [], "optiplex": []}
    cdp = None
    proc = None
    try:
        cdp, proc = cdpmod.launch(headed=True)
        cdp.navigate("https://www.amazon.com/")
        cdpmod.nap(4, 6)
        cdpmod.wait_for_js(cdp, "document.readyState === 'complete'", timeout=40)
        cdpmod.nap(2, 3)
        wall = cdp.evaluate(WALL_JS)
        state["home_wall"] = wall
        cdp.screenshot(os.path.join(SHOTS, "amazon_home.png"))
        print("HOME wall=%s title=%s" % (wall.get("wall"), wall.get("title")), flush=True)
        if wall.get("wall"):
            state["phase"] = "blocked_home"
        else:
            state["psu"] = do_search(
                cdp, "psu",
                "https://www.amazon.com/s?k=550W+80%2B+Bronze+power+supply",
                psu_ok, 3, "amz_psu", state)
            if not state["blocked"]:
                state["optiplex"] = do_search(
                    cdp, "optiplex",
                    "https://www.amazon.com/s?k=Dell+OptiPlex+MT+desktop+renewed",
                    opti_ok, 3, "amz_opti", state)
            state["phase"] = "blocked" if state["blocked"] else "done"
    except Exception as e:
        state["phase"] = "error"
        state["error"] = str(e)
        print("ERROR: %s" % e, flush=True)
    finally:
        with open(OUT, "w") as f:
            json.dump(state, f, indent=1)
        print("WROTE %s phase=%s" % (OUT, state["phase"]), flush=True)
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
