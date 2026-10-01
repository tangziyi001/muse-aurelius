#!/usr/bin/env python3
import json, re
D = "/config/dreamstime-browser/shots/"
d = json.load(open(D + "dreamstime-2026-10-01-dump.json"))

st = re.sub(r"\s+", " ", d["pages"]["statistics"]["text"])
m = re.search(r"Apr 26.*", st)
print("stats table:", m.group(0)[:1500] if m else st[:1500])

py = re.sub(r"\s+", " ", d["pages"]["payout"]["text"])
print("PAYOUT:", py[py.find("Request Payment") + 14:py.find("Request Payment") + 600])

nt = d["pages"]["notifications"]
ntx = re.sub(r"\s+", " ", nt["text"])
print("NOTIF len:", len(ntx))
i = ntx.find("Notifications")
print("NOTIF:", ntx[i:i + 1200] if i >= 0 else ntx[:1200])

tx = re.sub(r"\s+", " ", d["pages"]["tax"]["text"])
i = tx.find("Provide your tax profile information")
print("TAX:", tx[i:i + 450])

ur_rows = d["pages"]["under_review"].get("rows", [])
print("UR rows:", len(ur_rows))
