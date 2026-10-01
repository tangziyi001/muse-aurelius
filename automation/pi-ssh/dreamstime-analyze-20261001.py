#!/usr/bin/env python3
import json, re
D = "/config/dreamstime-browser/shots/"
d = json.load(open(D + "dreamstime-2026-10-01-dump.json"))

rf = d["pages"]["refused"]["text"]
ids = sorted(set(re.findall(r"47\d{7}", rf)))
print("refused IDs on page:", ids)
print("info issues count:", rf.lower().count("info issues"))
dates = sorted(set(re.findall(r"\d{2}/\d{2}/\d{4}", rf)))
print("refused dates:", dates)
rsnip = re.sub(r"\s+", " ", rf)
print("refused text[:700]:", rsnip[:700])

up = d["pages"]["upload"]
t = up["text"]
jpg = sorted(set(re.findall(r"b\d{2}-\d{2}\.jpg", t)))
print("upload jpgs mentioned:", jpg)
ids2 = sorted(set(re.findall(r"47\d{7}", t)))
print("upload IDs:", ids2)
idx = t.lower().find("unfinished")
print("unfinished region:", re.sub(r"\s+", " ", t[max(0, idx-300):idx+500])[:800] if idx >= 0 else "NOT FOUND")

ur = d["pages"]["under_review"]
print("under-review text:", re.sub(r"\s+", " ", ur["text"])[:600])

st = d["pages"]["statistics"]
print("stats text:", re.sub(r"\s+", " ", st["text"])[:1200])

tx = d["pages"]["tax"]
print("tax text:", re.sub(r"\s+", " ", tx["text"])[:800])

py = d["pages"]["payout"]
print("payout text:", re.sub(r"\s+", " ", py["text"])[:700])

nt = d["pages"]["notifications"]
print("notifications url:", nt["url"])
print("notifications text:", re.sub(r"\s+", " ", nt["text"])[:600])
print("HOME validatePrompt:", d["home"]["validatePrompt"])
