"""端到端演示：listings.csv 的一行 → 创建 download 草稿 → 上传首图。

默认只建草稿（不产生上架费）。加 --publish --deliverable <zip> 才会先传
交付文件再激活（激活产生 $0.20/listing 上架费）。

用法：
    python3 demo.py [--row N] [--taxonomy-id ID] [--publish --deliverable PATH]
"""
import argparse
import csv
import glob
import os
import sys

from config import load_env
from client import EtsyClient

CSV_PATH = os.path.expanduser("~/workspace/your_files/etsy-wallpapers/listings.csv")
ASSETS_DIR = os.path.expanduser("~/workspace/your_files/etsy-wallpapers")
IMAGE_EXTS = ("*.jpg", "*.jpeg", "*.png", "*.webp")


def load_row(path, index):
    with open(path, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    if not rows:
        raise RuntimeError("listings.csv 为空")
    if not (0 <= index < len(rows)):
        raise RuntimeError(f"--row 越界：共 {len(rows)} 行")
    return rows[index]


def first_image(image_dir):
    for ext in IMAGE_EXTS:
        hits = sorted(glob.glob(os.path.join(image_dir, ext)))
        if hits:
            return hits[0]
    raise RuntimeError(f"{image_dir} 里没有找到图片")


def resolve_taxonomy(client, env):
    if env.get("ETSY_TAXONOMY_ID"):
        return int(env["ETSY_TAXONOMY_ID"]), "env 指定"
    hits = client.find_seller_taxonomy("digital")
    if not hits:
        raise RuntimeError("taxonomy 搜索无结果，请用 --taxonomy-id 指定")
    print("taxonomy 候选（关键词 digital）：")
    for tid, path in hits[:10]:
        print(f"  {tid}  {path}")
    tid, path = hits[0]
    print(f"→ 采用第一个：{tid} {path}（不对就用 --taxonomy-id 覆盖）")
    return tid, path


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--row", type=int, default=0, help="listings.csv 行号（0 起）")
    ap.add_argument("--taxonomy-id", type=int, default=None)
    ap.add_argument("--publish", action="store_true", help="建完直接激活（收 $0.20 上架费）")
    ap.add_argument("--deliverable", default=None, help="--publish 时的数字交付文件")
    args = ap.parse_args()

    env = load_env()
    try:
        client = EtsyClient(env)
    except RuntimeError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(2)

    shop_id = client.get_shop_id()
    print(f"shop_id = {shop_id}")

    if args.taxonomy_id:
        taxonomy_id = args.taxonomy_id
        print(f"taxonomy_id = {taxonomy_id}（命令行指定）")
    else:
        taxonomy_id, _ = resolve_taxonomy(client, env)

    row = load_row(CSV_PATH, args.row)
    tags = [t.strip() for t in row["tags"].split(";") if t.strip()]
    image_dir = os.path.join(ASSETS_DIR, row["image_dir"])
    img = first_image(image_dir)
    price = "4.99"  # 测试价；批量上架时按定价策略覆盖

    print(f"行 {args.row}: {row['title'][:60]}…")
    print(f"首图: {img}")

    listing = client.create_draft_listing(
        shop_id,
        title=row["title"],
        description=row["description"],
        price=price,
        taxonomy_id=taxonomy_id,
        tags=tags,
        materials=["digital file", "wallpaper"],
        quantity=999,
        listing_type="download",
    )
    listing_id = listing["listing_id"]
    print(f"草稿已创建：listing_id={listing_id} state={listing.get('state')}")

    up = client.upload_listing_image(shop_id, listing_id, img, rank=1)
    print(f"首图已上传：image_id={up.get('listing_image_id')}")

    if args.publish:
        if not args.deliverable:
            print("ERROR: --publish 需要 --deliverable 指定数字交付文件",
                  file=sys.stderr)
            sys.exit(1)
        client.publish_listing(shop_id, listing_id, args.deliverable)
        print(f"已激活（产生 $0.20 上架费）：listing_id={listing_id}")
    else:
        print("保持草稿状态（未激活，未产生上架费）。")
        print(f"卖家后台编辑页：https://www.etsy.com/your/shops/me/dashboard/listings"
              f"/{listing_id}")


if __name__ == "__main__":
    main()
