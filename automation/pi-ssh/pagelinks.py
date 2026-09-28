import json, sys
d = json.load(open(sys.argv[1]))
p = d["pages"]["online_files"]
t = p.get("text", "")
i = t.find("Showing 1")
print(t[i:i+400])
print("=== all links mentioning online-files ===")
for l in p.get("links", []):
    u = l.split("||")[-1].strip()
    if "online-files" in u:
        print(u[:200])
print("=== select/option/pager text near bottom ===")
i2 = t.find("63 images")
print(t[i2:i2+800])
