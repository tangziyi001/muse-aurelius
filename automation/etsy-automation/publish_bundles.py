"""ZenPixelWalls bundle 发布脚本（第二波合集 B01/B02/B03）。

用法:
  python3 publish_bundles.py --only B01   # 只建 B01 草稿（验证用），不发布
  python3 publish_bundles.py --all        # 3 个全部建草稿、指派 section、发布并读回核验

价格: $12.99/bundle（用户批准）。taxonomy: 2078。
铁律：发布后必须 API 读回核验 state=active 且 shop_section_id 正确，否则不算成功。
"""
import argparse
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import publish
from publish import load_rows, create_and_fill, verify_draft, load_state, save_state
from client import EtsyClient, EtsyError

publish.PRICE = "12.99"   # bundle 定价；create_and_fill / verify_draft 均读此全局量
TAXONOMY_ID = 2078
BASE = os.path.expanduser("~/workspace/your_files/etsy-wallpapers")
CSV_PATH = os.path.join(BASE, "listings-bundles.csv")
STATE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                          "publish_state_bundles.json")


def verify_published(c, shop_id, r, listing_id):
    """发布后读回：state=active 且 section 指派正确。返回 (ok, [问题])。"""
    problems = []
    got = c.get_listing(listing_id)
    if got.get("state") != "active":
        problems.append(f"state={got.get('state')} (expected active)")
    want_sec = int(r["section_id"])
    got_sec = got.get("shop_section_id")
    if got_sec != want_sec:
        problems.append(f"shop_section_id={got_sec} (expected {want_sec})")
    amt = got.get("price", {}).get("amount") if isinstance(got.get("price"), dict) else got.get("price")
    if str(amt) not in ("12.99", "1299"):
        problems.append(f"price mismatch: {amt!r}")
    return not problems, problems


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", help="只处理单个 bundle id（建草稿+验证，不发布）")
    ap.add_argument("--all", action="store_true", help="全部 3 个建草稿并发布")
    a = ap.parse_args()

    c = EtsyClient()
    shop_id = c.get_shop_id("ZenPixelWalls")
    print(f"shop_id={shop_id}")
    state = load_state(STATE_FILE)

    rows = load_rows(CSV_PATH)
    if a.only:
        rows = [r for r in rows if r["listing_id"] == a.only]
        assert rows, f"unknown id {a.only}"

    for r in rows:
        key = r["listing_id"]
        entry = state.get(key, {})
        listing_id = entry.get("listing_id")
        if not listing_id:
            print(f"[{key}] 创建草稿…")
            try:
                draft = create_and_fill(c, shop_id, r)
            except EtsyError as e:
                print(f"[{key}] 创建失败: {e}")
                state[key] = {"status": "create_failed", "error": str(e)[:200]}
                save_state(state, STATE_FILE)
                continue
            listing_id = draft["listing_id"]
            entry = {"listing_id": listing_id, "status": "draft"}
            print(f"[{key}] 草稿 listing_id={listing_id}")
        else:
            print(f"[{key}] 复用已有 listing {listing_id}（{entry.get('status')}）")

        ok, problems = verify_draft(c, shop_id, r, listing_id)
        # publish.verify_draft 的价格白名单是 ("12.99","4.99","499")；
        # Etsy 实际返回 amount=1299（分，divisor=100）即 $12.99，属正常，过滤该误报。
        problems = [p for p in problems if p != "price mismatch: 1299"]
        ok = not problems
        entry["verify"] = {"ok": ok, "problems": problems}
        print(f"[{key}] 草稿校验: {'通过' if ok else '失败: ' + '; '.join(problems)}")
        state[key] = entry
        save_state(state, STATE_FILE)

        if a.all and ok:
            try:
                # 草稿阶段先指派 section，再发布
                c.update_listing(shop_id, listing_id,
                                 shop_section_id=int(r["section_id"]))
                c.publish_listing(shop_id, listing_id)
                ok2, problems2 = verify_published(c, shop_id, r, listing_id)
                entry["status"] = "active" if ok2 else "publish_unverified"
                entry["publish_verify"] = {"ok": ok2, "problems": problems2}
                print(f"[{key}] 发布核验: {'通过' if ok2 else '失败: ' + '; '.join(problems2)}")
            except EtsyError as e:
                entry["status"] = "publish_failed"
                entry["error"] = str(e)[:200]
                print(f"[{key}] 发布失败: {e}")
            state[key] = entry
            save_state(state, STATE_FILE)
        time.sleep(1)


if __name__ == "__main__":
    main()
