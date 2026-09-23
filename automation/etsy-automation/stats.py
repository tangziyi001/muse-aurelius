"""Etsy 每日流量/订单数据拉取（只读，不动上架流程）。

拉取内容：
  1. 全量 active listings 快照：views / num_favorers / price / quantity
     （views 字段存在但 2026-09-20 全为 0——店铺刚开 1 天，与零流量一致；
      该字段是否随真实流量递增【未验证】，周报里必须标注，不许当流量用）
  2. receipts 增量（按 receipt_id 去重，水位 receipts_seen.json）
     需要 transactions_r scope；缺权限时记 meta 不崩溃
  3. reviews 增量（水位 reviews_seen.json）

输出：~/workspace/goals/etsy-zenpixelwalls-30/hidden_files/stats/etsy_YYYY-MM-DD.jsonl
实质变化时打印 "NOTIFY: ..." 行（由 cron worker 转达用户）；平时只记日志。

PII 规则：receipt 里只存 receipt_id / 时间 / listing / 金额，
绝不存 buyer 姓名/邮箱/地址。
"""
import json
import os
import sys
import time
from datetime import datetime
from zoneinfo import ZoneInfo

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from client import EtsyClient, EtsyError

TZ = ZoneInfo("America/New_York")
GOAL = os.path.expanduser("~/workspace/goals/etsy-zenpixelwalls-30")
STATS_DIR = os.path.join(GOAL, "hidden_files", "stats")
os.makedirs(STATS_DIR, exist_ok=True)

RECEIPTS_SEEN = os.path.join(STATS_DIR, "receipts_seen.json")
REVIEWS_SEEN = os.path.join(STATS_DIR, "reviews_seen.json")
FAVORERS_PREV = os.path.join(STATS_DIR, "favorers_prev.json")
RUN_LOG = os.path.join(STATS_DIR, "stats_runs.log")

SHOP_ID = 68131115  # ZenPixelWalls
FAVORER_SPIKE_THRESHOLD = 3  # 单日收藏增量 >= 3 视为突增


def today():
    return datetime.now(TZ).strftime("%Y-%m-%d")


def load_json(path, default):
    if os.path.exists(path):
        try:
            return json.load(open(path))
        except Exception:
            return default
    return default


def save_json(path, obj):
    tmp = path + ".tmp"
    json.dump(obj, open(tmp, "w"), ensure_ascii=False)
    os.replace(tmp, path)


def log(msg):
    line = f"{datetime.now(TZ).strftime('%Y-%m-%d %H:%M:%S')} {msg}"
    print(line, flush=True)
    with open(RUN_LOG, "a") as f:
        f.write(line + "\n")


def notify(msg):
    print(f"NOTIFY: {msg}", flush=True)


def paged_get(client, path, params=None, limit=100):
    out, offset = [], 0
    params = dict(params or {})
    while True:
        params.update({"limit": limit, "offset": offset})
        r = client.get(path, params=params)
        batch = r.get("results", []) or []
        out.extend(batch)
        if len(batch) < limit:
            break
        offset += limit
    return out


def pick_receipt_fields(rc):
    txs = rc.get("transactions", []) or []
    listing_ids = sorted({t.get("listing_id") for t in txs if t.get("listing_id")})
    gt = rc.get("grandtotal", {}) or {}
    amount = gt.get("amount")
    if amount is not None:
        amount = amount / (gt.get("divisor", 100) or 100)
    return {
        "receipt_id": rc.get("receipt_id"),
        "created_timestamp": rc.get("created_timestamp"),
        "listing_ids": listing_ids,
        "quantity": sum(int(t.get("quantity", 1) or 1) for t in txs) or None,
        "total": round(amount, 2) if amount is not None else None,
        "currency": gt.get("currency_code"),
    }


def main():
    day = today()
    out_path = os.path.join(STATS_DIR, f"etsy_{day}.jsonl")
    out = open(out_path, "a")

    def emit(rec):
        out.write(json.dumps(rec, ensure_ascii=False) + "\n")

    client = EtsyClient()
    log(f"stats run for {day}")

    # ---- 1. listings 快照 ----
    listings = paged_get(
        client, f"/v3/application/shops/{SHOP_ID}/listings",
        {"state": "active"})
    snap = []
    for l in listings:
        p = l.get("price") or {}
        price = p.get("amount")
        if price is not None:
            price = round(price / (p.get("divisor") or 100), 2)
        snap.append({
            "listing_id": l.get("listing_id"),
            "title": (l.get("title") or "")[:120],
            "state": l.get("state"),
            "price": price,
            "currency": p.get("currency_code"),
            "views": l.get("views", 0),
            "num_favorers": l.get("num_favorers", 0),
            "quantity": l.get("quantity"),
            "url": l.get("url"),
        })
    emit({"type": "snapshot", "date": day, "shop_id": SHOP_ID,
          "active_count": len(snap), "listings": snap})
    log(f"snapshot: {len(snap)} active listings")

    # ---- 2. receipts 增量 ----
    receipts_seen = set(load_json(RECEIPTS_SEEN, []))
    first_run = not os.path.exists(RECEIPTS_SEEN)
    prior_count = len(receipts_seen)
    receipts_ok, receipts_err, new_receipts = True, None, []
    try:
        receipts = paged_get(
            client, f"/v3/application/shops/{SHOP_ID}/receipts",
            {"was_paid": "true"})
        for rc in receipts:
            rid = rc.get("receipt_id")
            if rid in receipts_seen:
                continue
            receipts_seen.add(rid)
            new_receipts.append(pick_receipt_fields(rc))
    except EtsyError as e:
        receipts_ok, receipts_err = False, str(e)[:200]
        log(f"receipts pull failed: {receipts_err}")
    emit({"type": "meta", "date": day, "receipts_ok": receipts_ok,
          "receipts_error": receipts_err})
    for r in new_receipts:
        emit({"type": "receipt", "date": day, "receipt": r})
    save_json(RECEIPTS_SEEN, sorted(receipts_seen))
    if new_receipts:
        rev = sum((r["total"] or 0) for r in new_receipts)
        titles = []
        for r in new_receipts:
            for lid in r["listing_ids"]:
                t = next((s["title"] for s in snap if s["listing_id"] == lid), str(lid))
                titles.append(t[:40])
        if first_run:
            notify(f"流量基线：首次拉到 receipts，共 {len(new_receipts)} 笔历史订单"
                   f"，金额 ${rev:.2f}")
        else:
            if prior_count == 0:
                notify(f"首单达成！ZenPixelWalls 第一笔订单到账：{len(new_receipts)} 笔，"
                       f"金额 ${rev:.2f}：" + "；".join(titles[:5]))
            else:
                notify(f"新订单 {len(new_receipts)} 笔，金额 ${rev:.2f}："
                       + "；".join(titles[:5]))
    log(f"receipts: {len(new_receipts)} new (ok={receipts_ok})")

    # ---- 3. reviews 增量 ----
    reviews_seen = set(load_json(REVIEWS_SEEN, []))
    new_reviews = []
    try:
        reviews = paged_get(client, f"/v3/application/shops/{SHOP_ID}/reviews")
        for rv in reviews:
            rid = rv.get("review_id")
            key = str(rid)
            if key in reviews_seen:
                continue
            reviews_seen.add(key)
            new_reviews.append({
                "review_id": rid,
                "listing_id": rv.get("listing_id"),
                "rating": rv.get("rating"),
                "review": (rv.get("review") or "")[:300],
                "created_timestamp": rv.get("create_timestamp") or rv.get("created_timestamp"),
            })
    except EtsyError as e:
        log(f"reviews pull failed: {str(e)[:200]}")
    for r in new_reviews:
        emit({"type": "review", "date": day, "review": r})
    save_json(REVIEWS_SEEN, sorted(reviews_seen))
    if new_reviews:
        rs = ", ".join(f"{r['rating']}星" for r in new_reviews)
        notify(f"新评价 {len(new_reviews)} 条（{rs}）")
    log(f"reviews: {len(new_reviews)} new")

    # ---- 4. 收藏突增 ----
    prev = load_json(FAVORERS_PREV, {})
    cur = {str(s["listing_id"]): s["num_favorers"] for s in snap}
    save_json(FAVORERS_PREV, cur)
    if prev:  # 首轮只建基线，不告警
        for lid, n in cur.items():
            d = (n or 0) - (prev.get(lid) or 0)
            if d >= FAVORER_SPIKE_THRESHOLD or (prev.get(lid) in (0, None) and (n or 0) >= 2):
                t = next((s["title"] for s in snap if str(s["listing_id"]) == lid), lid)
                notify(f"收藏突增：「{t[:40]}」今日 +{d}（累计 {n}）")
    log("done")
    out.close()


if __name__ == "__main__":
    main()
