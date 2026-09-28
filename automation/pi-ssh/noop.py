import json, sys
d = json.load(open("/tmp/dt-online-2026-09-28.json"))
print("file count:", len(d["files"]))
