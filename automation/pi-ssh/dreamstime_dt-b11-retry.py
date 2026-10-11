#!/usr/bin/env python3
"""Retry failed batch-11 files. Loads dt-b11-submit.py via importlib (hyphenated name)."""
import importlib.util, json, sys
spec = importlib.util.spec_from_file_location("dtb11", "/config/dreamstime-browser/dt-b11-submit.py")
dtb11 = importlib.util.module_from_spec(spec)
sys.modules["dtb11"] = dtb11
spec.loader.exec_module(dtb11)

TARGETS = ["b11-07.jpg", "b11-08.jpg"]
def main():
    cdp, tid = dtb11.new_tab()
    try:
        mapping, counts = dtb11.get_mapping(cdp)
        print("mapping files:", len(mapping), flush=True)
        for fname in TARGETS:
            pid = mapping.get(fname)
            if not pid:
                print(fname, "NOT in unfinished mapping - skipping", flush=True)
                continue
            print("=== retry %s (id %s)" % (fname, pid), flush=True)
            try:
                r = dtb11.process_one(cdp, fname, pid, dtb11.META[fname])
            except Exception as e:
                r = {"file": fname, "portal_id": pid, "error": "exception: " + str(e)[:200]}
            print(json.dumps(r)[:400], flush=True)
            d = json.load(open(dtb11.RESULT))
            d["results"] = [x for x in d.get("results", []) if x.get("file") not in TARGETS] + [r]
            json.dump(d, open(dtb11.RESULT, "w"), indent=1)
    finally:
        dtb11.close_tab(cdp, tid)
    print("RETRY DONE")
if __name__ == "__main__":
    main()
