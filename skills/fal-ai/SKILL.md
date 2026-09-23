---
name: "fal_ai"
description: "Use Fal Ai when the user asks for Fal Ai or this provider's API."
---

# Fal Ai

## Purpose
Use Fal Ai with the user-connected `custom.fal-ai` credential.

## Tooling
CLI: `~/workspace/skills/fal-ai/bin/fal.py` with subcommands
`submit <endpoint-id> --input-json input.json` (queue API, prints request_id +
status_url + response_url), `status --url`, `wait --url --timeout 1800 --poll 30`
(polls to COMPLETED/FAILED), `download --url <result-file> --out <path>`,
`upload <file>` (currently disabled, see Auth).

Verified endpoints (re-check https://fal.ai/models before new use):
- `fal-ai/kling-video/o1/standard/reference-to-video` — Kling O1 Standard, ~$0.42/5s, 9:16 ok
- `fal-ai/kling-video/o1/reference-to-video` — Kling O1 Pro, ~$0.56/5s
- `bytedance/seedance-2.5/image-to-video` — Seedance fallback (note: its
  reference-to-video 422-rejects ultra-realistic virtual faces)

Hard-won rules (real runs 2026-09-20, do not "fix" these):
- Use status_url/response_url EXACTLY as fal returns them. Never rebuild from the
  endpoint id: fal truncates 4-segment ids and rebuilt URLs 405.
- Kling reference-to-video `elements[]` must carry BOTH `frontal_image_url` AND a
  non-empty `reference_image_urls`. Empty reference_image_urls -> phantom job that
  "completes" in <1s with no render.
- Kling O1 reference-to-video (queue) wants `prompt/duration/aspect_ratio/elements`
  at the HTTP body TOP LEVEL, not under `{"input": {...}}` (verified 2026-09-20:
  nested body "COMPLETES" in <1s with inference_time ~0.2s, $0 charged, and the
  real 422 `missing body.prompt` only surfaces on the response_url GET).
  Use `fal.py submit --raw --input-json <top-level-fields.json>` for this endpoint.
- Namespace prefixes are literal: bytedance/* lives at
  `https://fal.run/bytedance/...`, NOT `https://fal.run/fal-ai/bytedance/...`.
- Write loop-safe prompts positively; `negative_prompt` is not a schema field.
- Spend: single jobs around $0.42 are pre-approved territory (user ran Kling
  benchmarks at this price twice). Flag before anything over ~$2.
- `fal-ai/esrgan` (Real-ESRGAN upscaler, verified 2026-09-20): schema is
  NON-STANDARD — fields go at body top level, NOT under `{"input": {...}}`
  (the wrapper 422s with "Field required: body.image_url"). Input:
  `{"image_url": "...", "upscale_factor": 2}`. Queue API
  (queue.fal.run) returns phantom COMPLETED in ~0.04s with no retrievable
  result — use the SYNC endpoint `POST https://fal.run/fal-ai/esrgan`
  instead (~5s real inference for 1170x2532 -> 2340x5064). Output PNG
  2340x5064 (~7-16MB). Cost ~$0.00111/compute-sec ≈ $0.01/image. Note:
  input must be a public URL (fal.py upload is disabled); temp-host on
  catbox.moe works for validation.
- FLUX dev custom sizes (verified 2026-09-20): requesting
  `image_size: {width: 944, height: 2048}` usually returns exactly 944x2048
  but SOMETIMES returns a wrong ratio — always verify with PIL and
  center-crop to the exact target ratio before use.
- fal CDN downloads can truncate mid-stream (verified 2026-09-20): use
  resumable curl (`-C - --retry 8 --retry-all-errors`) and ALWAYS
  `Image.open(path).load()` to force a full decode before trusting a file.
- ESRGAN batch pipeline (verified 2026-09-20, script:
  `~/workspace/skills/fal-ai/bin/esrgan_upscale.py`): center-crop raw to the
  exact phone ratio -> resize to 1170x2532 -> temp-host on catbox.moe
  (`-F reqtype=fileupload -F fileToUpload=@f https://catbox.moe/user/api.php`;
  0x0.st/transfer.sh/file.io timed out through the egress proxy, catbox
  worked) -> `POST https://fal.run/fal-ai/esrgan`
  `{"image_url": <catbox>, "upscale_factor": 2}` (sync, top-level fields) ->
  download the returned `image.url` PNG, verify 2340x5064 + full decode.
  ~20s/image end to end. Response shape: `{"image": {"url": ...}}`.
- fal.run sync slowness (2026-09-20): when fal is slow, the sync endpoint can
  drop connections ("Remote end closed connection without response") even
  for prompts that succeed minutes later. Retry with backoff (8s+); a
  reworded simpler prompt can also succeed where a longer one kept failing.
  Failed (dropped) attempts cost $0 — only COMPLETED generations bill.
- FLUX.1 dev billing (verified 2026-09-20 via fal.ai model page): $0.025 per
  megapixel, rounded UP to the nearest MP. A 944x2048 image = 1.93MP -> 2MP
  -> $0.05/image. Budget ~$0.05 per phone-wallpaper generation.
- /tmp is ephemeral: generation/finish scripts die with the VM. Keep reusable
  pipeline scripts in `~/workspace/skills/fal-ai/bin/`.

## Auth
The credential is already stored; nothing here collects one. Never ask the user to paste a raw key in chat, set a secret environment variable, pass a secret flag, or write an auth file.

fal quirk (verified 2026-09-20): fal requires `Authorization: Key <key>`, but the
connector can only place the stored value verbatim as the whole header. So the
STORED VALUE MUST ALREADY INCLUDE THE PREFIX — the user must enter
`Key <their-key>` (with the space) in the setup card, not the bare key. A bare
key 401s with "Cannot access application ... Authentication is required".
CLIs must send the bare surrogate (`add_surrogate_to_request` as scaffolded);
do NOT prepend "Key " client-side — the egress proxy only swaps exact
surrogate values.

The connector allows authenticated requests to fal.run and queue.fal.run only.
fal's file-upload API lives on rest.alpha.fal.ai (`POST
/storage/upload/initiate`), which is outside that allowlist, so `fal.py upload`
is disabled until the connector is expanded via
`credentials.request_api_access` with `reconnect=true` (same provider, scheme,
placement, plus `rest.alpha.fal.ai` in api_hosts; user re-completes the card
once). Until then, avoid uploads: generate stills with a fal text-to-image
model and pass the returned `v3.fal.media` URL straight into video models.

A 401 or 403 is a question about the request before it is a question about the key. Check that the credential was attached at all: a request built without the helpers named under Tooling carries nothing, and that looks exactly like a wrong or under-scoped token. Only once a request that did carry the credential is still rejected, call `credentials.request_api_access` with `reconnect` to replace it. The connector is stored as `custom.fal-ai`.

## Operating Rules
1. Use this skill when the user asks for Fal Ai or this provider's API.
2. Restrict authenticated requests to: fal.run, queue.fal.run.
3. Do not print, log, or persist raw credentials.
4. If auth is missing or rejected, follow the Auth section rather than asking for a key.

## Maya / Kling O1 ultra-realistic video pipeline (validated 2026-09-20)

The proven cheap route for a fictional ultra-realistic persona video.
Do not improvise a different model for this use case without a new benchmark.

### Route status
- VALIDATED: Kling O1 Standard reference-to-video
  `fal-ai/kling-video/o1/standard/reference-to-video`, ~$0.42/5s, 9:16 ok,
  silent output. Kling's policy passes ultra-realistic fictional faces.
- DEAD: `bytedance/seedance-2.5/reference-to-video` — ByteDance content policy
  422-rejects ultra-realistic fictional faces at validation ("reference image
  may contain a real person's portrait"). $0 spent, not retryable by
  rewording; the more realistic the face, the harder it gets blocked.

### Reference image (output ceiling = reference realism)
- Enhance the still first: visible pores, faint freckles, mild digital noise,
  no beautification. Photoreal reference = photoreal video ceiling.
- Bake in identity anchors and verify them every run. Maya's three anchors:
  small mole above left eyebrow, thin silver hoop in right ear, thin
  wave-line tattoo on left wrist.
- Pass as base64 data URL inside elements[] (proven), or a fal.media URL.
  elements[] MUST carry BOTH `frontal_image_url` AND a non-empty
  `reference_image_urls`; empty reference_image_urls -> phantom job that
  "COMPLETES" in <1s with no render.

### Gold prompt (benchmark 6, validated 2026-09-20)
"Photorealistic candid iPhone street selfie video of Maya Sato, 27-year-old
Brazilian-Japanese mixed woman, freelance photographer, mid-shot framing from
waist up, both hands in frame, holding a smartphone, walking down a sunny city
sidewalk. BRISK NATURAL MOTION, REAL-TIME SPEED, NOT slow motion, no dreamy
slow drift: natural walking cadence, subtle handheld phone shake, quick candid
glance toward the camera, slight head turn, natural blink. Small mole above
left eyebrow, thin silver hoop in right ear, thin wave-line tattoo on left
wrist. Visible skin pores and faint freckles, mild digital noise, candid not
staged, no beautification filter, SOFT WARM GOLDEN-HOUR DAYLIGHT, soft
diffused shadows, gentle warm backlight, shallow depth of field, vertical
9:16 phone footage aesthetic."
duration "5", aspect_ratio "9:16". Submit with `--raw` (top-level fields).

### Iteration protocol (the user's rule: one variable at a time)
- Before any paid run, report: the single variable, the single-run cost,
  the total cost. Wait for explicit approval before spending.
- Validated variables, ranked by measured effect:
  1. Lighting wording (b6): "natural daylight" ->
     "SOFT WARM GOLDEN-HOUR DAYLIGHT, soft diffused shadows, gentle warm
     backlight". Solved the user's "over-sharpened, doesn't look human"
     complaint (b5 -> b6, blurmean 5.61 -> 6.32, softer).
  2. Motion wording (b4): "BRISK NATURAL MOTION, REAL-TIME SPEED, NOT slow
     motion, no dreamy slow drift". Killed the slomo feel (b3 -> b4).
  3. Realism wording (b2): "visible skin pores and faint freckles, mild
     digital noise, candid not staged, no beautification filter".
     Cut the AI look vs the polished b1.
- Seed lottery is real: the same prompt can draw harsh noon light (b5) or
  soft golden hour (b2/b4). If a run looks off on lighting, rerun the same
  prompt before changing any wording.

### QC gates (every run, before delivering to the user)
1. Integrity: `nb_read_frames` == 121 (24fps x 5.04s), full decode, no
   truncation (resumable curl + `Image.open(path).load()`-style full read).
2. Identity: all three anchors present and stable across early/mid/late
   frames; no face drift.
3. Hands + phone: hands natural, iPhone camera module sane.
4. Sharpness: ffmpeg `blurdetect` mean (HIGHER = softer). Never judge
   "over-sharpened" by eye alone — compare to baselines:
   b2 5.84 / b3 5.41 / b4 6.83 / b5 5.61 / b6 6.32. The "crispy" complaint
   is usually harsh lighting/high local contrast (a seed draw), not
   measured sharpness.
5. Ending: subject should keep facing the camera; flag a full turn-away
   walk-off (b4 did it, b5/b6 didn't).
6. Judder: flag regular frame-spike patterns. b4 had periodic spikes every
   4 frames (bad seed, one-off); b5 with the same prompt was clean.
   Fix = 48fps interpolation, not a prompt change.

### Interpolation (free post-process for judder)
`ffmpeg -i in.mp4 -vf "minterpolate=fps=48:mi_mode=mci:mc_mode=aobmc:me_mode=bidir:vsbmc=1" -c:v libx264 -crf 18 -preset medium -pix_fmt yuv420p -an out-smooth48.mp4`
-> 239 frames at 48fps. Verify full decode after.

### Cost discipline
- ~$0.42 per Standard run. Flag the user before anything over ~$2.
- Phantom check: COMPLETED with inference_time < 1s = no real render, $0
  charged. Real renders show inference_time of several hundred seconds.
- Record every fal.media file_url in the samples sidecar JSON to avoid
  re-uploads. Never persist a user-transient fal key.
