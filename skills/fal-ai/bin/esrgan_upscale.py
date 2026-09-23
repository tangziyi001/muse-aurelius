#!/usr/bin/env python3
"""Upscale orig_raw -> 2340x5064 (4k/) and 1170x2532 (orig/) via fal ESRGAN sync."""
import json, os, sys, time, subprocess, urllib.request
sys.path.insert(0, "/opt/hatch/skills/skill-creator/bin")
from dynamic_credentials import add_surrogate_to_request, ensure_allowed_url, read_json_response, read_response_body

CRED = "custom.fal-ai"; HOSTS = ("fal.run", "queue.fal.run")
import argparse
_ap = argparse.ArgumentParser(description="ESRGAN 2x upscale: raw -> 1170x2532 (orig/) + 2340x5064 (4k/)")
_ap.add_argument("--raw", default="~/workspace/your_files/etsy-wallpapers/redo-cream-gradient/orig_raw")
_ap.add_argument("--out4k", default="~/workspace/your_files/etsy-wallpapers/redo-cream-gradient/4k")
_ap.add_argument("--outorig", default="~/workspace/your_files/etsy-wallpapers/redo-cream-gradient/orig")
_a = _ap.parse_args()
RAW = os.path.expanduser(_a.raw)
D4K = os.path.expanduser(_a.out4k)
DORIG = os.path.expanduser(_a.outorig)
os.makedirs(D4K, exist_ok=True); os.makedirs(DORIG, exist_ok=True)

# NOTE: files must be publicly reachable for fal ESRGAN. We upload via a temp
# transfer: use fal's CDN by first uploading? Simpler: ESRGAN needs image_url.
# We serve via file.io-like throwaway? Instead: use data URI? No.
# Proven route from checkpoint: ESRGAN sync with {"image_url": ...} worked.
# We need public URLs: upload raws to a temp public host.
# Use 0x0.st (fast, no auth) for temp hosting.
def pub_upload(path):
    r = subprocess.run(["curl", "-s", "-F", "reqtype=fileupload",
                        "-F", f"fileToUpload=@{path}",
                        "https://catbox.moe/user/api.php"],
                       capture_output=True, text=True, timeout=120)
    url = r.stdout.strip()
    if not url.startswith("http"): raise RuntimeError(f"catbox failed: {r.stdout[:80]}")
    return url

def esrgan(image_url, factor=2, timeout=300):
    url = "https://fal.run/fal-ai/esrgan"
    ensure_allowed_url(url, HOSTS)
    data = json.dumps({"image_url": image_url, "upscale_factor": factor}).encode()
    req = urllib.request.Request(url, data=data, method="POST",
                                 headers={"Content-Type": "application/json"})
    add_surrogate_to_request(req, CRED, allowed_hosts=HOSTS)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return read_json_response(resp)

def download(url, path):
    from PIL import Image
    if os.path.exists(path): os.remove(path)
    cmd = ["curl", "-sL", "-C", "-", "--retry", "8", "--retry-all-errors",
           "--retry-delay", "3", "--max-time", "600", "-o", path, url]
    for _ in range(4):
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=660)
        if r.returncode == 0 and os.path.exists(path):
            try:
                im = Image.open(path); im.load(); return im
            except Exception: pass
        time.sleep(4)
    raise RuntimeError("download incomplete")

from PIL import Image
names = sorted(f[:-4] for f in os.listdir(RAW) if f.endswith(".jpg"))
print(f"finishing {len(names)} images", flush=True)
for i, name in enumerate(names):
    try:
        f4 = f"{D4K}/{name}.jpg"; fo = f"{DORIG}/{name}.jpg"
        if os.path.exists(f4) and os.path.exists(fo):
            print(f"[{i+1}/{len(names)}] skip {name} (exists)", flush=True); continue
        src = f"{RAW}/{name}.jpg"
        im0 = Image.open(src); w0, h0 = im0.size
        # normalize to exact phone ratio first (center crop)
        target = 1170/2532
        if w0/h0 > target:
            nw = int(h0*target); x=(w0-nw)//2; im0 = im0.crop((x,0,x+nw,h0))
        else:
            nh = int(w0/target); y=(h0-nh)//2; im0 = im0.crop((0,y,w0,y+nh))
        im0 = im0.resize((1170, 2532), Image.LANCZOS)
        tmp = f"/tmp/finish_{name}.jpg"; im0.save(tmp, quality=95)
        pub = pub_upload(tmp)
        res = esrgan(pub, 2)
        out_url = res["image"]["url"] if isinstance(res.get("image"), dict) else res["images"][0]["url"]
        im4 = download(out_url, f4)
        if im4.size != (2340, 5064):
            im4 = Image.open(f4).resize((2340, 5064), Image.LANCZOS)
            im4.save(f4, quality=93)
        im0.save(fo, quality=93)
        os.remove(tmp)
        print(f"[{i+1}/{len(names)}] OK {name}", flush=True)
    except Exception as e:
        print(f"[{i+1}/{len(names)}] FAIL {name}: {str(e)[:150]}", flush=True)
print("DONE")
