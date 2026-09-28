import json, sys, re
d = json.load(open(sys.argv[1]))

def show(name, max_text=2500):
    p = d["pages"].get(name)
    if not p:
        print("###", name, "-> MISSING"); return
    if "error" in p:
        print("###", name, "-> ERROR:", p["error"]); return
    print("###", name, "|", p.get("url"), "|", p.get("title"))
    t = p.get("text", "")
    print(t[:max_text])
    print()

for n in ["account", "upload", "under_review", "online_files", "refused",
          "statistics", "notifications", "payout", "tax_center"]:
    show(n)
