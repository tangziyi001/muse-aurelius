#!/usr/bin/env python3
"""fal.ai queue API CLI. Auth goes through the stored connector credential.

Subcommands:
  upload <file>                      Upload an image to fal storage, print file_url
  submit <endpoint> --input-json F    Submit a queue job, print request_id + urls
  status --url URL                    Print job status JSON
  wait --url URL --out F [--timeout S]  Poll until done, print result JSON
  download --url URL --out F          Download a result file (public URL, no auth)

Known-good endpoints (verify against fal.ai/models before new use):
  fal-ai/kling-video/o1/standard/reference-to-video   Kling O1 Standard, ~$0.42/5s
  fal-ai/kling-video/o1/reference-to-video            Kling O1 Pro, ~$0.56/5s
  bytedance/seedance-2.5/image-to-video               Seedance fallback

Pitfalls baked in from real runs (2026-09-20):
- Use the status_url/response_url EXACTLY as fal returns them. Do NOT rebuild
  them from the endpoint id: fal truncates 4-segment ids (e.g. fal-ai/kling-video
  becomes fal-ai/kling-video) and reconstructed URLs 405.
- Kling reference-to-video elements[] MUST carry both frontal_image_url AND a
  non-empty reference_image_urls. Empty reference_image_urls -> phantom job that
  "completes" in <1s with no real render.
- Namespace prefixes matter: bytedance/* endpoints live at
  https://fal.run/bytedance/... (NOT https://fal.run/fal-ai/bytedance/...).
  A wrong prefix yields phantom IN_QUEUE/COMPLETED jobs or 404s.
"""
import argparse
import json
import mimetypes
import os
import sys
import time
import urllib.parse
import urllib.request

sys.path.insert(0, "/opt/hatch/skills/skill-creator/bin")
from dynamic_credentials import (  # noqa: E402
    add_surrogate_to_request,
    ensure_allowed_url,
    read_json_response,
    read_response_body,
    DynamicCredentialError,
)

CRED = "custom.fal-ai"
HOSTS = ("fal.run", "queue.fal.run")


def _post(url, payload, timeout=60):
    ensure_allowed_url(url, HOSTS)
    data = json.dumps(payload).encode()
    req = urllib.request.Request(url, data=data, method="POST",
                                 headers={"Content-Type": "application/json"})
    add_surrogate_to_request(req, CRED, allowed_hosts=HOSTS)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return read_json_response(resp)
    except urllib.error.HTTPError as e:
        body = e.read(4000).decode("utf-8", "replace")
        raise DynamicCredentialError(f"HTTP {e.code} on {url}: {body}") from e


def _get(url, timeout=60):
    ensure_allowed_url(url, HOSTS)
    req = urllib.request.Request(url, method="GET")
    add_surrogate_to_request(req, CRED, allowed_hosts=HOSTS)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return read_json_response(resp)
    except urllib.error.HTTPError as e:
        body = e.read(4000).decode("utf-8", "replace")
        raise DynamicCredentialError(f"HTTP {e.code} on {url}: {body}") from e


def cmd_upload(args):
    # fal storage lives on rest.alpha.fal.ai, which is NOT in this connector's
    # allowed hosts (fal.run, queue.fal.run). Until the connector is expanded,
    # this command cannot run. To enable: credentials.request_api_access with
    # reconnect=true, same provider/auth_scheme/placement, api_hosts plus
    # "rest.alpha.fal.ai"; the user re-completes the card once.
    # Workaround that needs no upload: generate the still with a fal
    # text-to-image model via `submit`, then feed its v3.fal.media URL straight
    # into the video model.
    sys.exit(
        "upload unavailable: connector custom.fal-ai only allows fal.run and "
        "queue.fal.run; fal storage needs rest.alpha.fal.ai. "
        "Expand via credentials.request_api_access(reconnect=true), or avoid "
        "upload by generating stills with a fal text-to-image model and "
        "passing the returned file URL directly."
    )


def cmd_submit(args):
    with open(args.input_json) as f:
        payload = json.load(f)
    if args.raw:
        body = payload  # POST the JSON file verbatim (endpoints like Kling O1
                        # that want fields at the HTTP body top level)
    else:
        body = {"input": payload.get("input", payload)}
    res = _post(f"https://queue.fal.run/{args.endpoint}", body, timeout=120)
    out = {
        "request_id": res.get("request_id"),
        "status_url": res.get("status_url"),
        "response_url": res.get("response_url"),
    }
    print(json.dumps(out, indent=2))


def cmd_status(args):
    print(json.dumps(_get(args.url), indent=2))


def cmd_wait(args):
    deadline = time.time() + args.timeout
    last = None
    while time.time() < deadline:
        st = _get(args.url, timeout=60)
        status = st.get("status")
        if status != last:
            print(f"[{time.strftime('%H:%M:%S')}] status={status}", file=sys.stderr)
            last = status
        if status == "COMPLETED":
            print(json.dumps(st, indent=2))
            return
        if status in ("FAILED", "CANCELLED"):
            sys.exit(f"job ended: {status}\n{json.dumps(st, indent=2)[:2000]}")
        time.sleep(args.poll)
    sys.exit(f"timed out after {args.timeout}s waiting on {args.url}")


def cmd_download(args):
    # Result file URLs (CDN) are signed/public; no auth header.
    req = urllib.request.Request(args.url, method="GET")
    with urllib.request.urlopen(req, timeout=300) as resp:
        blob = read_response_body(resp)
    os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
    with open(args.out, "wb") as f:
        f.write(blob)
    print(f"saved {len(blob)} bytes -> {args.out}")


def main():
    p = argparse.ArgumentParser(description="fal.ai queue API CLI")
    sub = p.add_subparsers(dest="cmd", required=True)

    u = sub.add_parser("upload"); u.add_argument("file"); u.set_defaults(fn=cmd_upload)

    s = sub.add_parser("submit"); s.add_argument("endpoint")
    s.add_argument("--input-json", required=True)
    s.add_argument("--raw", action="store_true",
                   help="POST the JSON file verbatim without the {\"input\"} wrapper "
                        "(for endpoints like Kling O1 that want top-level fields)")
    s.set_defaults(fn=cmd_submit)

    t = sub.add_parser("status"); t.add_argument("--url", required=True)
    t.set_defaults(fn=cmd_status)

    w = sub.add_parser("wait"); w.add_argument("--url", required=True)
    w.add_argument("--out", default=None)
    w.add_argument("--timeout", type=int, default=1800)
    w.add_argument("--poll", type=int, default=30)
    w.set_defaults(fn=cmd_wait)

    d = sub.add_parser("download"); d.add_argument("--url", required=True)
    d.add_argument("--out", required=True); d.set_defaults(fn=cmd_download)

    args = p.parse_args()
    try:
        args.fn(args)
    except DynamicCredentialError as e:
        sys.exit(f"fal error: {e}")


if __name__ == "__main__":
    main()
