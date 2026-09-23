#!/usr/bin/env python3
"""Phase 2: extract STGAubron listings, then visit product pages and pull PSU specs.
Runs ON the Pi. Output: /config/pi-browser/shots/amazon_candidates.json"""
import os, sys, json

sys.path.insert(0, "/config/etsy-browser")
import cdp as cdpmod

cdpmod.PROFILE_DIR = "/config/pi-browser/profile"
cdpmod.DEBUG_PORT = 9223

SHOTS = "/config/pi-browser/shots"
OUT = os.path.join(SHOTS, "amazon_candidates.json")

SEARCH_JS = (
    "(function(){"
    "  var items = [];"
    "  document.querySelectorAll('div[data-component-type=\"s-search-result\"]').forEach(function(el){"
    "    var a = el.querySelector('h2 a');"
    "    if (!a) return;"
    "    var priceEl = el.querySelector('.a-price .a-offscreen');"
    "    var href = a.getAttribute('href') || '';"
    "    if (href.charAt(0) === '/') href = 'https://www.amazon.com' + href;"
    "    items.push({"
    "      title: (a.innerText || '').trim(),"
    "      url: href.split('?')[0],"
    "      price: priceEl ? priceEl.innerText.trim() : null"
    "    });"
    "  });"
    "  return items;"
    "})()"
)

PRODUCT_JS = (
    "(function(){"
    "  var out = {url: location.href};"
    "  var t = document.getElementById('productTitle');"
    "  out.title = t ? t.innerText.trim() : document.title;"
    "  var p = document.querySelector('.a-price .a-offscreen');"
    "  out.price = p ? p.innerText.trim() : null;"
    "  var av = document.querySelector('#availability .a-size-medium');"
    "  out.availability = av ? av.innerText.trim().replace(/\\s+/g,' ') : null;"
    "  out.addable = !!document.querySelector('#add-to-cart-button');"
    "  out.specs = {};"
    "  document.querySelectorAll('#productDetails_techSpec_section_1 tr, #productDetails_detailBullets_sections1 tr').forEach(function(tr){"
    "    var th = tr.querySelector('th'); var td = tr.querySelector('td');"
    "    if (th && td) out.specs[th.innerText.trim()] = td.innerText.trim().slice(0,200);"
    "  });"
    "  out.bullets = [];"
    "  document.querySelectorAll('#feature-bullets li').forEach(function(li){"
    "    var s = li.innerText.trim(); if (s) out.bullets.push(s.slice(0,300));"
    "  });"
    "  var bodyTxt = document.body.innerText;"
    "  var idx = bodyTxt.toLowerCase().indexOf('power supply');"
    "  out.powerContext = idx >= 0 ? bodyTxt.slice(Math.max(0,idx-150), idx+250).replace(/\\s+/g,' ').trim() : null;"
    "  var img = document.querySelector('#landingImage');"
    "  out.image = img ? (img.getAttribute('data-old-hires') || img.getAttribute('src')) : null;"
    "  return out;"
    "})()"
)

SCROLL_JS = "window.scrollTo(0, document.body.scrollHeight); 'scrolled:' + document.body.scrollHeight;"

def main():
    cdp = None
    proc = None
    result = {"phase": "started", "candidates": []}
    try:
        cdp, proc = cdpmod.launch(headed=True)
        cdp.navigate("https://www.amazon.com/s?k=STGAubron+gaming+PC")
        cdpmod.nap(4, 6)
        cdpmod.wait_for_js(cdp, "document.readyState === 'complete'", timeout=30)
        for _ in range(3):
            cdp.evaluate(SCROLL_JS)
            cdpmod.nap(2, 3)
        items = cdp.evaluate(SEARCH_JS) or []
        result["search_count"] = len(items)
        # keep organic-looking results with a price, dedupe by url
        seen = set()
        cands = []
        for it in items:
            if not it.get("price") or it["url"] in seen:
                continue
            seen.add(it["url"])
            cands.append(it)
            if len(cands) >= 5:
                break
        for it in cands:
            try:
                cdp.navigate(it["url"])
                cdpmod.nap(4, 6)
                cdpmod.wait_for_js(cdp, "document.readyState === 'complete'", timeout=30)
                cdpmod.nap(2, 3)
                prod = cdp.evaluate(PRODUCT_JS) or {}
                prod["search_title"] = it.get("title")
                prod["search_price"] = it.get("price")
                result["candidates"].append(prod)
                cdp.screenshot(os.path.join(SHOTS, "amazon_prod_" + str(len(result["candidates"])) + ".png"))
            except Exception as e:
                result["candidates"].append({"url": it.get("url"), "error": str(e)})
        result["phase"] = "done"
    except Exception as e:
        result["phase"] = "error"
        result["error"] = str(e)
    finally:
        with open(OUT, "w") as f:
            json.dump(result, f, indent=1)
        print("PHASE2 " + result["phase"] + " candidates=" + str(len(result["candidates"])), flush=True)
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
