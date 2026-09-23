"""ZenPixelWalls 批量发布脚本。

用法:
  python3 publish.py --only L01      # 只建 L01 草稿（验证用），不发布
  python3 publish.py --all           # 建全部 20 个并发布（含已存在的草稿就地发布）
  python3 publish.py --verify        # 只读回校验当前店铺 listing 状态

价格策略: $4.99/包（用户批准区间 $2.99-$9.99 中段）。
taxonomy: 2078 (Art & Collectibles > Prints > Digital Prints)。
"""
import argparse
import csv
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from client import EtsyClient, EtsyError

BASE = os.path.expanduser("~/workspace/your_files/etsy-wallpapers")
CSV_PATH = os.path.join(BASE, "listings.csv")
DELIVERY_DIR = os.path.join(BASE, "delivery")
PRICE = "4.99"
TAXONOMY_ID = 2078
STATE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "publish_state.json")

FOOTER = (
    "\n\n// LICENSE & TERMS: This is a DIGITAL download — no physical item will be shipped. "
    "Files are high-resolution JPGs sized for iPhone, Android and desktop monitors "
    "(exact dimensions listed above). For personal use only; no resale or redistribution. "
    "Every design is original to this shop and AI-assisted."
)

# Etsy tag 上限 20 字符：超长的替换为等义短版
TAG_FIXES = {
    "holographic wallpaper": "holographic",
    "mid century wallpaper": "mid century",
}


def load_rows(csv_path=CSV_PATH):
    rows = list(csv.DictReader(open(csv_path, encoding="utf-8")))
    for r in rows:
        tags = [TAG_FIXES.get(t.strip(), t.strip()) for t in r["tags"].split(";")]
        assert len(tags) == 13, (r["listing_id"], len(tags))
        for t in tags:
            assert len(t) <= 20, (r["listing_id"], t)
        r["tags_fixed"] = tags
        r["description_full"] = r["description"].strip() + FOOTER
        d = os.path.expanduser(r["image_dir"])
        matched = sorted(
            os.path.join(d, f) for f in os.listdir(d)
            if f"_{r['listing_id']}_phone_" in f or f"_{r['listing_id']}_desktop_" in f
        )
        if matched:
            r["image_files"] = matched
        else:
            # wave-2 单壁纸: 预览目录下全部 JPG 即 listing 图片
            r["image_files"] = sorted(
                os.path.join(d, f) for f in os.listdir(d) if f.lower().endswith(".jpg"))
        assert len(r["image_files"]) == int(r["total_images"]), (r["listing_id"], len(r["image_files"]))
        zip_name = r.get("zip_name") or f"{r['listing_id']}-{r['theme_slug']}-wallpapers.zip"
        z = os.path.join(DELIVERY_DIR, zip_name)
        assert os.path.exists(z), z
        r["zip_path"] = z
    return rows


def load_state(state_file=STATE_FILE):
    return json.load(open(state_file)) if os.path.exists(state_file) else {}


def save_state(s, state_file=STATE_FILE):
    json.dump(s, open(state_file, "w"), indent=1)


def create_and_fill(c, shop_id, r):
    """建草稿 + 传图 + 传交付文件。返回 listing dict。"""
    draft = c.create_draft_listing(
        shop_id, r["title"], r["description_full"], PRICE, TAXONOMY_ID,
        tags=r["tags_fixed"], materials=["digital file", "JPG"],
    )
    lid = draft["listing_id"]
    for i, img in enumerate(r["image_files"], start=1):
        c.upload_listing_image(shop_id, lid, img, rank=i)
    c.upload_listing_file(shop_id, lid, r["zip_path"])
    return draft


def verify_draft(c, shop_id, r, listing_id):
    """远程读回并校验全部字段。返回 (ok, [问题])。"""
    import html
    problems = []
    got = c.get_listing(listing_id, includes=("Images",))
    if got.get("title") != r["title"]:
        problems.append("title mismatch")
    if html.unescape(got.get("description", "")) != r["description_full"]:
        problems.append("description mismatch")
    amt = got.get("price", {}).get("amount") if isinstance(got.get("price"), dict) else got.get("price")
    if str(amt) not in (PRICE, "4.99", "499"):
        problems.append(f"price mismatch: {amt!r}")
    if sorted(got.get("tags", [])) != sorted(r["tags_fixed"]):
        problems.append(f"tags mismatch: {got.get('tags')}")
    if got.get("taxonomy_id") != TAXONOMY_ID:
        problems.append(f"taxonomy mismatch: {got.get('taxonomy_id')}")
    imgs = got.get("images") or got.get("Images") or []
    if len(imgs) != len(r["image_files"]):
        problems.append(f"image count {len(imgs)} != {len(r['image_files'])}")
    if got.get("listing_type") != "download":
        problems.append(f"listing_type={got.get('listing_type')}")
    # 数字交付文件
    files = c.get(f"/v3/application/shops/{shop_id}/listings/{listing_id}/files")
    flist = files.get("results", files if isinstance(files, list) else [])
    if not flist:
        problems.append("no digital files attached")
    for req in ("digital download", "personal use only", "no resale",
                "Every design is original to this shop and AI-assisted"):
        if req.lower() not in html.unescape(got.get("description", "")).lower():
            problems.append(f"copy missing: {req}")
    return not problems, problems


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", help="只处理单个 listing_id（建草稿+验证，不发布）")
    ap.add_argument("--all", action="store_true", help="全部 20 个建草稿并发布")
    ap.add_argument("--verify", action="store_true", help="只读回校验店铺 listing 状态")
    ap.add_argument("--csv", default=CSV_PATH, help="listing CSV 路径（默认第一波）")
    ap.add_argument("--state", default=STATE_FILE, help="状态文件路径（默认第一波）")
    a = ap.parse_args()

    c = EtsyClient()
    shop_id = c.get_shop_id("ZenPixelWalls")
    print(f"shop_id={shop_id}")
    state = load_state(a.state)

    if a.verify:
        act = c.get_shop_listings(shop_id, state="active", limit=100)
        dra = c.get_shop_listings(shop_id, state="draft", limit=100)
        for s, res in (("active", act), ("draft", dra)):
            items = res.get("results", [])
            print(f"{s}: {res.get('count', len(items))}")
            for it in items:
                print(f"  {it['listing_id']} {it.get('state')} {it.get('title','')[:60]}")
        return

    rows = load_rows(a.csv)
    if a.only:
        rows = [r for r in rows if r["listing_id"] == a.only]
        assert rows, f"unknown id {a.only}"

    for r in rows:
        lid_key = r["listing_id"]
        entry = state.get(lid_key, {})
        listing_id = entry.get("listing_id")
        if not listing_id:
            print(f"[{lid_key}] 创建草稿…")
            try:
                draft = create_and_fill(c, shop_id, r)
            except EtsyError as e:
                print(f"[{lid_key}] 创建失败: {e}")
                state[lid_key] = {"status": "create_failed", "error": str(e)[:200]}
                save_state(state, a.state)
                continue
            listing_id = draft["listing_id"]
            entry = {"listing_id": listing_id, "status": "draft"}
            print(f"[{lid_key}] 草稿 listing_id={listing_id}")
        else:
            print(f"[{lid_key}] 复用已有 listing {listing_id}（{entry.get('status')}）")

        ok, problems = verify_draft(c, shop_id, r, listing_id)
        entry["verify"] = {"ok": ok, "problems": problems}
        print(f"[{lid_key}] 校验: {'通过' if ok else '失败: ' + '; '.join(problems)}")
        state[lid_key] = entry
        save_state(state, a.state)

        if a.all and ok:
            try:
                c.publish_listing(shop_id, listing_id)
                got = c.get_listing(listing_id)
                entry["status"] = got.get("state")
                print(f"[{lid_key}] 发布后状态: {got.get('state')}")
            except EtsyError as e:
                entry["status"] = "publish_failed"
                entry["error"] = str(e)[:200]
                print(f"[{lid_key}] 发布失败: {e}")
            state[lid_key] = entry
            save_state(state, a.state)
        time.sleep(1)


if __name__ == "__main__":
    main()
