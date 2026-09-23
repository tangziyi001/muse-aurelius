"""建 10 个店铺 sections 并把现有 20 个 listings 指派进去。

2026-09-20 用户批准执行（一次到位）。
- 空 section 不在公开店铺页显示，可先建（3 个新系列）。
- 创建顺序即店铺页展示顺序（API 不支持拖拽排序）。
- section_id 存到 goal hidden_files/stats/sections.json，供第二波发布时用。
- 末尾读回核验每个 listing 的 shop_section_id。
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from client import EtsyClient

SHOP_ID = 68131115
SECTIONS = [
    ("y2k-chrome", "Y2K Chrome Wallpapers",
     [4579050273, 4579067138, 4579067526]),
    ("gradient-healing", "Gradient Wallpapers",
     [4579050669, 4579051433, 4579068400]),
    ("cream-korean", "Cream Korean Aesthetic",
     [4579052787, 4579069690, 4579070012]),
    ("ink-wabi", "Wabi-Sabi Ink Wash",
     [4579049515, 4579049853, 4579050001, 4579053157]),
    ("dark-moody", "Dark Moody Wallpapers",
     [4579069278, 4579069416, 4579069538]),
    ("nature-boho", "Botanical Boho",
     [4579051827, 4579053411]),
    ("bauhaus-geo", "Bauhaus Geometric",
     [4579068788, 4579069134]),
    ("dark-living", "Dark Living Beings", []),
    ("ink-oriental", "Oriental Ink Wash", []),
    ("chrome-objects", "Liquid Chrome Objects", []),
]
OUT = os.path.expanduser(
    "~/workspace/goals/etsy-zenpixelwalls-30/hidden_files/stats/sections.json")


def _results(resp):
    if isinstance(resp, dict):
        return resp.get("results", [])
    return resp


def main():
    c = EtsyClient()
    existing = _results(c.get_shop_sections(SHOP_ID))
    by_title = {s["title"]: s["shop_section_id"] for s in existing}
    print(f"现有 sections: {len(existing)}")
    mapping = {}
    for key, title, lids in SECTIONS:
        assert len(title) <= 24, f"标题超 24 字符: {title}"
        if title in by_title:
            sid = by_title[title]
            print(f"复用 [{title}] id={sid}")
        else:
            s = c.create_shop_section(SHOP_ID, title)
            sid = s.get("shop_section_id")
            print(f"新建 [{title}] id={sid}")
        mapping[key] = {"shop_section_id": sid, "title": title}
        for lid in lids:
            c.update_listing(SHOP_ID, lid, shop_section_id=sid)
            print(f"  listing {lid} -> section {sid}")
    with open(OUT, "w") as f:
        json.dump(mapping, f, indent=2, ensure_ascii=False)
    print(f"section 映射已存: {OUT}")
    # 读回核验
    bad = []
    total = 0
    for key, title, lids in SECTIONS:
        sid = mapping[key]["shop_section_id"]
        for lid in lids:
            total += 1
            got = c.get_listing(lid, includes=()).get("shop_section_id")
            if got != sid:
                bad.append((lid, sid, got))
    if bad:
        print("核验失败:", bad)
        sys.exit(1)
    print(f"核验通过：{total} 个 listings 的 section 指派全部正确")


if __name__ == "__main__":
    main()
