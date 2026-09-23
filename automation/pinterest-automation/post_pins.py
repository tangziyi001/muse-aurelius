#!/usr/bin/env python3
"""Daily Pinterest poster for ZenPixelWalls.

Gates (quiet no-op unless ALL true):
  - tokens exist (~/.config/pinterest-automation/tokens.json)
  - Standard access approved (touch ~/.config/pinterest-automation/standard_approved)
Posts up to --count unposted pins from the queue (default 3/day), records pin_ids.
Never posts the same queue item twice (posted_pins.json).

Usage: post_pins.py [--count N] [--queue PATH] [--board NAME] [--dry-run]
"""
import argparse
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import config
from client import PinterestClient, PinterestError

PROMO_DIR = os.path.expanduser("~/workspace/pinterest-promo")
DEFAULT_QUEUE = os.path.join(PROMO_DIR, "pin_queue_batch1.json")
POSTED_FILE = os.path.join(PROMO_DIR, "posted_pins.json")
LOG_FILE = os.path.join(PROMO_DIR, "post_log.txt")
DEFAULT_BOARD = "ZenPixelWalls | Phone Wallpapers"


def log(msg):
    line = f"{time.strftime('%Y-%m-%d %H:%M:%S')} {msg}"
    print(line)
    with open(LOG_FILE, "a") as f:
        f.write(line + "\n")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--count", type=int, default=3)
    ap.add_argument("--queue", default=DEFAULT_QUEUE)
    ap.add_argument("--board", default=DEFAULT_BOARD)
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()

    if config.load_tokens() is None:
        log("GATE: no tokens yet (one-time OAuth pending) -> quiet exit")
        return 0
    if not config.is_standard_approved():
        log("GATE: Standard access not approved yet (Trial pins are sandbox-invisible) -> quiet exit")
        return 0

    queue = json.load(open(a.queue))
    posted = json.load(open(POSTED_FILE)) if os.path.exists(POSTED_FILE) else {}
    todo = [q for q in queue if q["listing_key"] not in posted][: a.count]
    if not todo:
        log("nothing new to post (queue exhausted)")
        return 0

    client = PinterestClient()
    board = client.ensure_board(a.board, "Calm, pixel-perfect phone wallpapers — instant download on Etsy.")
    board_id = board["id"]
    log(f"board: {board.get('name')} id={board_id}")

    for q in todo:
        if a.dry_run:
            log(f"DRY-RUN would post {q['listing_key']} -> {q['link']}")
            continue
        try:
            pin = client.create_pin(
                board_id=board_id, image_path=q["image_path"],
                title=q["title"], description=q["description"],
                link=q["link"], alt_text=q.get("alt_text", ""),
            )
            posted[q["listing_key"]] = {
                "pin_id": pin.get("id"), "posted_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
                "link": q["link"],
            }
            json.dump(posted, open(POSTED_FILE, "w"), indent=1)
            log(f"POSTED {q['listing_key']} pin_id={pin.get('id')}")
            time.sleep(5)  # gentle pacing; Standard limit is 100/min
        except PinterestError as e:
            log(f"FAILED {q['listing_key']}: {e}")
            return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
