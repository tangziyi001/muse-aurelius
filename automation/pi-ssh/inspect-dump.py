import json, sys
path = sys.argv[1]
d = json.load(open(path))
for k, v in d.items():
    if isinstance(v, dict):
        url = v.get('url', '')
        title = v.get('title', '')
        nlinks = len(v.get('links', [])) if isinstance(v.get('links'), list) else 0
        print("PAGE:", k, "|", url, "|", title, "| links:", nlinks)
        if isinstance(v.get('links'), list):
            for l in v['links']:
                ll = l.lower()
                if any(x in ll for x in ("refused", "statistics", "earnings",
                                         "online-files", "payment", "tax",
                                         "notification", "under-review", "uploaded")):
                    print("   ", l[:150])
    else:
        print("KEY:", k, "|", str(v)[:100])
