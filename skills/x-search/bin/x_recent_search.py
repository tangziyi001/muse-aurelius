#!/usr/bin/env python3
"""Search recent posts on X via the X API v2 recent search endpoint.

Usage:
    x_recent_search.py --query "robotics policy model" [--max-results 25]
                       [--hours-back 48] [--lang en]

Prints a JSON array of posts: id, text, created_at, author username/name,
like/repost counts, and a direct URL for each post.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
import urllib.parse
import urllib.request

sys.path.insert(0, "/opt/hatch/skills/skill-creator/bin")
import dynamic_credentials as dc

CREDENTIAL_NAME = "custom.x"
ALLOWED_HOSTS = ["api.x.com"]
BASE_URL = "https://api.x.com/2/tweets/search/recent"


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Search recent X posts (v2 recent search).")
    p.add_argument("--query", required=True, help="X search query (operators allowed).")
    p.add_argument("--max-results", type=int, default=25,
                   help="Posts per call, 10-100 (default 25).")
    p.add_argument("--hours-back", type=float, default=48,
                   help="Look back this many hours (default 48).")
    p.add_argument("--lang", default=None, help="Restrict language, e.g. en.")
    return p.parse_args()


def build_query(query: str, lang: str | None) -> str:
    q = query.strip()
    if lang and "lang:" not in q:
        q = f"{q} lang:{lang}"
    # Exclude pure reposts noise is optional; keep originals+quotes+replies.
    return q


def main() -> int:
    args = parse_args()
    max_results = max(10, min(100, args.max_results))
    end = dt.datetime.now(dt.timezone.utc)
    start = end - dt.timedelta(hours=args.hours_back)

    params = {
        "query": build_query(args.query, args.lang),
        "max_results": str(max_results),
        "start_time": start.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "end_time": end.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "tweet.fields": "created_at,public_metrics,author_id,lang",
        "expansions": "author_id",
        "user.fields": "username,name",
    }
    url = BASE_URL + "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, method="GET")
    req.add_header("User-Agent", "muse-x-search/1.0")
    try:
        dc.add_surrogate_to_request(
            req, CREDENTIAL_NAME, allowed_hosts=ALLOWED_HOSTS
        )
    except dc.DynamicCredentialError as exc:
        print(json.dumps({"error": f"credential error: {exc}"}), file=sys.stderr)
        return 2

    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            payload = dc.read_json_response(resp)
    except Exception as exc:  # urllib.error.HTTPError etc.
        body = ""
        if hasattr(exc, "read"):
            try:
                body = exc.read().decode("utf-8", errors="replace")[:2000]
            except Exception:
                pass
        print(json.dumps({"error": f"request failed: {exc}", "body": body}),
              file=sys.stderr)
        return 1

    users = {u["id"]: u for u in payload.get("includes", {}).get("users", [])}
    out = []
    for t in payload.get("data", []):
        author = users.get(t.get("author_id", ""), {})
        username = author.get("username", "")
        metrics = t.get("public_metrics", {})
        out.append({
            "id": t.get("id"),
            "text": t.get("text"),
            "created_at": t.get("created_at"),
            "author_username": username,
            "author_name": author.get("name", ""),
            "url": f"https://x.com/{username}/status/{t.get('id')}" if username else None,
            "likes": metrics.get("like_count", 0),
            "reposts": metrics.get("retweet_count", 0),
            "replies": metrics.get("reply_count", 0),
            "lang": t.get("lang"),
        })
    print(json.dumps(out, ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
