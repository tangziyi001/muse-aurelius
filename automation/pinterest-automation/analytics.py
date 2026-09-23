"""Pinterest pin analytics 每日拉取（只读）。

无 token（Trial 未批 / OAuth 未完成）时静默跳过，exit 0，不打扰。
有 token 后：按 posted_pins.json 里的 pin_id 拉取近 7 天
impressions / saves / outbound_clicks，归因到 listing -> 系列。

输出：~/workspace/goals/etsy-zenpixelwalls-30/hidden_files/stats/pinterest_YYYY-MM-DD.jsonl
Pinterest analytics 通常有 1-2 天延迟，近 2 天数据可能为 0/缺失，属正常。
"""
import json
import os
import sys
import time
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

TZ = ZoneInfo("America/New_York")
GOAL = os.path.expanduser("~/workspace/goals/etsy-zenpixelwalls-30")
STATS_DIR = os.path.join(GOAL, "hidden_files", "stats")
SERIES_MAP = os.path.join(STATS_DIR, "series_map.json")
POSTED_FILE = os.path.expanduser("~/workspace/pinterest-promo/posted_pins.json")
TOKEN_FILE = os.path.expanduser("~/.config/pinterest-automation/tokens.json")
RUN_LOG = os.path.join(STATS_DIR, "pinterest_runs.log")

METRIC_TYPES = "IMPRESSION,SAVE,OUTBOUND_CLICK"


def today():
    return datetime.now(TZ).strftime("%Y-%m-%d")


def log(msg):
    line = f"{datetime.now(TZ).strftime('%Y-%m-%d %H:%M:%S')} {msg}"
    print(line, flush=True)
    os.makedirs(STATS_DIR, exist_ok=True)
    with open(RUN_LOG, "a") as f:
        f.write(line + "\n")


def resolve_series(listing_id, title=""):
    try:
        sm = json.load(open(SERIES_MAP))
    except Exception:
        return "unmapped"
    if str(listing_id) in sm.get("listing_series", {}):
        return sm["listing_series"][str(listing_id)]
    tl = (title or "").lower()
    for rule in sm.get("keyword_rules", []):
        if any(k in tl for k in rule.get("keywords", [])):
            return rule["series"]
    return "unmapped"


def main():
    day = today()
    if not os.path.exists(TOKEN_FILE):
        log("SKIP: no pinterest tokens yet (Trial/OAuth pending)")
        return
    if not os.path.exists(POSTED_FILE):
        log("SKIP: posted_pins.json not found, nothing posted yet")
        return
    posted = json.load(open(POSTED_FILE))
    if not posted:
        log("SKIP: no pins posted yet")
        return

    from client import PinterestClient, PinterestError
    client = PinterestClient()

    os.makedirs(STATS_DIR, exist_ok=True)
    out = open(os.path.join(STATS_DIR, f"pinterest_{day}.jsonl"), "a")
    start = (datetime.now(TZ) - timedelta(days=6)).strftime("%Y-%m-%d")

    pulled, failed = 0, 0
    for key, info in posted.items():
        pin_id = info.get("pin_id") if isinstance(info, dict) else None
        listing_id = (info.get("listing_id") if isinstance(info, dict)
                      else info.get("listing_id") if isinstance(info, dict) else None)
        if not pin_id:
            continue
        try:
            r = client._request(
                "GET",
                f"/pins/{pin_id}/analytics?start_date={start}"
                f"&end_date={day}&metric_types={METRIC_TYPES}")
        except PinterestError as e:
            failed += 1
            log(f"pin {pin_id} analytics failed: {str(e)[:150]}")
            continue
        # v5 返回 [{"date":..., "metrics": {"IMPRESSION":..,"SAVE":..,"OUTBOUND_CLICK":..}}]
        rows = r if isinstance(r, list) else r.get("all_time", r.get("data", []))
        if isinstance(rows, dict):
            rows = [rows]
        for row in rows or []:
            d = row.get("date") or day
            m = row.get("metrics", {}) if isinstance(row, dict) else {}
            out.write(json.dumps({
                "type": "pin_day",
                "pull_date": day,
                "date": d,
                "pin_id": pin_id,
                "listing_key": key,
                "listing_id": listing_id,
                "series": resolve_series(listing_id),
                "impressions": m.get("IMPRESSION", 0) or 0,
                "saves": m.get("SAVE", 0) or 0,
                "outbound_clicks": m.get("OUTBOUND_CLICK", 0) or 0,
            }, ensure_ascii=False) + "\n")
        pulled += 1
    out.close()
    log(f"pinterest analytics: {pulled} pins pulled, {failed} failed")


if __name__ == "__main__":
    main()
