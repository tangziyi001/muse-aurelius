# Live Wallpaper Pipeline

End-to-end playbook for producing sellable animated ("live") phone wallpapers for Etsy:
static artwork → AI animation → QA → delivery normalization → setup instructions.
Owner: ZenPixelWalls live-wallpaper track. Last updated 2026-09-20 (wave-2 rework).

## When to use

Any task that needs animated lock-screen wallpapers as a product: new live packs,
live variants of existing static themes, or sample batches for review.

## Pipeline

### 1. Static base image

- Generate with `media.generate_image`, vertical 9:16 phone wallpaper.
- Lockscreen composition rules (non-negotiable):
  - clear negative space at the very top for the clock / Dynamic Island;
  - one clear focal subject in the upper-middle;
  - no text, no watermark.
- QA the still before animating: anatomy, texture, exposure, AI-look.

### 2. Animate

- `media.generate_video` with the still as `kind:image` input + a motion prompt.
- Motion prompt recipe: "Animate this still image into a 5-second seamless loop:
  <specific gentle motions>. <mood>. No camera movement. The loop must close
  seamlessly with the last frame matching the first."
- Keep motion subtle and ambient (water ripples, drifting fog, slow cloud drift,
  breathing, liquid flow). Fast or large motions break the loop illusion and look
  cheap on a lock screen.
- Request silence implicitly: output must have no audio track (battery-friendly is
  a selling point).

### 3. QA (AI-look is a red line)

Technical (ffprobe):
- codec H.264, 24 fps, duration, resolution, file size < 20 MB (Etsy per-file cap).

Loop seam:
- extract first and last frames; mean abs diff must be small. Any visible "jump"
  at the loop point = FAIL, regenerate.
- **Do not trust the generator's "seamless loop" claim.** Measured 2026-09-20:
  full-length loop seams were 29–55 mean-abs-diff (clearly visible jumps) on 4 of
  6 samples, and a regenerated leopard loop still measured 18.2.
- **Rule D (loop construction, user-mandated 2026-09-20): fade-to-start and
  cross-dissolve-to-head are BANNED.** The tail fade reads as an abrupt gradient
  on a lock screen ("尾帧的渐变很突兀"). The older fade-to-start recipe below is
  kept for historical reference only — do not use it for new work.
- Allowed loop constructions, in preference order:
  1. **Ping-pong**: take a 2.4 s window, concat forward + reversed
     (drop the duplicated peak frame). Seam is exact by construction; the
     midpoint reversal reads as a natural "breath" for ambient motion
     (fog, clouds, liquid flow, light sheen, slow drift). Measured seams
     0.6–4.0 on 5 wave-2 samples. Total 4.76 s ≤ intoLive's 5 s cap.
  2. **True periodic motion**: only when the generator actually closed the loop
     (measured seam < 10 on the full render) — trim and ship.
  3. **Medium-only motion**: subject perfectly still, only the medium moves
     (water ripples, fog). If the source has subject motion, regenerate with a
     still-subject motion prompt (see leopard case below) rather than
     post-processing around it.
  4. **Lighting cycle**: light sheen sweeping and returning (verified on
     Bauhaus geometric art — zero shape deformation).
- **Directional locomotion cannot be looped in post.** Measured: a leopard
  walking toward camera has no still window across 10 s; ping-pong would read
  as walking backwards (unnatural motion = red line). Fix: regenerate via
  `media.generate_video` with an explicit still-subject prompt ("the leopard
  stands perfectly still ..., only gentle water ripples ... and thin mist drift.
  The leopard's body and head do not move at all."), then ping-pong the result.
  Same rule applies to any subject with articulated/translation motion
  (swimming fish crossing frame, walking animals).

Visual (extract first / middle / last frames, view at full size):
- motion naturalness: no morphing, no melting edges, no teleporting details;
- living subjects: check anatomy frame-by-frame (limbs, faces, tails);
- continuity: ripples/reflections consistent, no flicker bands.

FAIL policy: regenerate the video (optionally with a tightened motion prompt);
never ship a compromise.

### 4. Delivery normalization (post-processing, ffmpeg)

The media pipeline does NOT reliably control duration/resolution. Normalize:

```bash
# 720p delivery: 720px wide, aspect preserved, 5s (intoLive cap), H.264
ffmpeg -y -i in.mp4 -t 5 -vf "scale=720:-2" -r 24 -c:v libx264 \
  -pix_fmt yuv420p -crf 20 -preset medium -an out_delivery.mp4
```

Debanding (2026-09-20 lesson — dark gradients + 8-bit yuv420p H.264 = visible
banding on OLED phones; the phone is NOT at fault, the encode is; and the
banding is often baked into the AI-generated source itself). Grain alone is
NOT enough — v2 (noise=alls=5) still showed banding on OLED. The working
recipe is the `deband` filter (actually smooths the contour steps) + light
temporal grain as dither, CRF 18. Verified on live-liquid-chrome-orb v4:
100%-crop shows no concentric steps, grain invisible at normal distance.
```bash
ffmpeg -y -i in.mp4 -vf "deband=1thr=0.02:2thr=0.02:3thr=0.02:4thr=0.02:range=16:blur=1,noise=alls=6:allf=t" \
  -c:v libx264 -crf 18 -preset medium -pix_fmt yuv420p -r 24 -an out_delivery.mp4
```
Note: grain is temporal, so first/last frame differ by grain only — negligible
at alls=6 against the ping-pong seam. Grain inflates bitrate on dark videos:
watch the 20 MB Etsy cap (v4 measured ~19 MB for 4.8 s at CRF 18; use CRF 20
if needed). Final user confirmation on OLED still pending.

Ping-pong loop (Rule D construction #1 — the default for ambient motion):
```bash
T0=1.0  # start of the calmest 2.4 s window
ffmpeg -y -i in.mp4 -filter_complex \
 "[0:v]trim=start=${T0}:duration=2.4,setpts=PTS-STARTPTS,fps=24,scale=720:-2[v1];\
  [0:v]trim=start=${T0}:duration=2.4,setpts=PTS-STARTPTS,fps=24,scale=720:-2,reverse,trim=start=0.042,setpts=PTS-STARTPTS[v2];\
  [v1][v2]concat=n=2:v=1:a=0,format=yuv420p[v]" \
 -map "[v]" -c:v libx264 -preset medium -crf 20 -an out_delivery.mp4
# v2 drops the first reversed frame (= last forward frame) so the peak is not
# duplicated; total 4.76 s, seam exact by construction (measured 0.6–4.0).
```

Frame-accurate seam QA (measured 2026-09-20):
- `-ss` BEFORE `-i` seeks to the nearest keyframe — NOT frame-accurate. A QA
  script using it measured a false seam of 8.6 on a clip whose true seam was
  4.0, and once compared the wrong frames entirely.
- Always measure with the select filter on full decode:
  `-vf "select='eq(n,0)',scale=180:391"` for frame 0 and `eq(n,N-1)` (N from
  `ffprobe -count_frames`) for the last frame; mean-abs-diff on grayscale.
  Pass threshold: < 10. Also view a first-vs-last side-by-side strip.
- For motion scouting (finding the calmest 2.4 s window), `-ss`-before-`-i`
  thumbnails at 0.5–1 s steps are fine; confirm the chosen window visually.

Loop-seam hardening — HISTORICAL, DO NOT USE (banned by Rule D 2026-09-20):
- Best-segment search alone left seams of 30–58 on fast directional motion
  (fish, chrome flow) — no 3–6 s sub-segment resembled frame 0.
- xfade tail↔head helps only when the 0.5 s natural drift is small.
- Fade-to-start (deterministic, worked on any motion): split the chosen
  E-frame segment into body `[0,E-X)` + tail `[E-X,E)`; alpha-fade the tail out
  over a still of frame 0 (X=15 frames ≈ 0.6 s); concat. The loop point becomes
  exact by construction (final seam 3–5 on the two worst clips). The brief
  dissolve reads as a gentle "breath", not a glitch — verified frame-by-frame.
  BANNED because the tail gradient reads as abrupt on a lock screen.
  Recipe (reference only): `trim`+`setpts`, tail `format=rgba,fade=t=out:alpha=1`,
  head still via `trim`+`tpad=stop_mode=clone`, `overlay`, `concat`.

- Deliverable per wallpaper: `*_delivery.mp4` (5s, 720p, silent) + hi-res JPG still.
- NEVER claim native 720p/1080p. If asked, say "720p HD (upscaled in post)".
- Keep the original full-length render alongside for review.

### 5. Setup instructions (buyer-facing)

Ship `SETUP-GUIDE.pdf` with every pack:
- iPhone: save MP4 → intoLive (free, App Store) → trim ≤5s → Save Live Photo →
  Settings → Wallpaper → Add New Wallpaper → Live Photos. iOS 17+ auto-plays on
  Lock Screen; earlier iOS uses press-and-hold. Home Screen shows the still.
- Android: system Video Wallpaper option or a Video Live Wallpaper app.
- State: MP4 H.264 720p, ~5s seamless loop, no audio by design; personal use only.

Template: `~/workspace/your_files/etsy-wallpapers/live/setup-guide.html`
(render to PDF with weasyprint).

### 6. Real-device test checklist (human step)

`~/workspace/your_files/etsy-wallpapers/live/真机测试清单.md` — the user runs this
on a real iPhone before any listing claims "Live Photo compatible". Never claim
device validation without it.

## No-app Live Photo pair delivery (免 App 直装, 2026-09-20)

Goal: buyer gets a real Live Photo with NO third-party app (intoLive).
A Live Photo = JPEG still + MOV video sharing one UUID "ContentIdentifier".
Status: metadata recipe implemented and structurally verified; **real-iPhone
pairing + wallpaper-usability NOT yet confirmed — never claim it works until
the user validates on device** (see test checklist in step 4).

### 1. Metadata recipe (publicly verified, 3 requirements)

1. JPEG: EXIF Apple MakerNote tag `0x0011` (ContentIdentifier) = UUID string
   (uppercase, 36 chars with dashes). Two independent sources confirm tag 17:
   honye/scripting-scripts `documentation/live_photo/en.md` (2026-09) and
   LimitPoint/LivePhoto (`kCGImagePropertyMakerAppleDictionary[17]`).
2. MOV: QuickTime Keys `(mdta) com.apple.quicktime.content.identifier` = same UUID.
3. The `still-image-time` timed metadata track is NOT required for Photos
   *import* pairing: makelive (RhetTbull, the reference tool) doesn't write it
   either, and its pairs import as Live Photos. We don't write it.
   The paired video MUST be `.mov` — the photo library rejects `.mp4` as a
   paired video (honye doc).

MakerNote binary layout (reverse-engineered from exiftool
`lib/Image/ExifTool/MakerNotes.pm` + `Apple.pm`, structurally validated by
exiftool read-back on 2026-09-20):
- bytes 0–9: `b"Apple iOS\x00"`; bytes 10–13: `b"II*\x00"` (mini TIFF header);
- bytes 14+: little-endian TIFF IFD, offsets relative to MakerNote start:
  1 entry: tag=0x0011, type=ASCII(2), count=37, value_offset → UUID+NUL.
- exiftool can WRITE `QuickTime:ContentIdentifier` to a MOV (verified), but
  CANNOT create the JPEG MakerNote tag from scratch ("if tag exists" only) —
  hence the hand-rolled MakerNote above.

### 2. Build

Script: `~/workspace/skills/live-wallpaper-pipeline/bin/build_livephoto_pair.py`
```bash
# 1) cover still from the delivery video (any good frame; 720x1276 to match)
ffmpeg -y -ss 1 -i live-liquid-chrome-orb_delivery_v4.mp4 -frames:v 1 -q:v 2 cover.jpg
# 2) remux delivery mp4 -> mov (paired video MUST be .mov; -c:v copy = lossless)
ffmpeg -y -i live-liquid-chrome-orb_delivery_v4.mp4 -c:v copy -movflags faststart pair_src.mov
# 3) build the pair (writes MakerNote to JPG via piexif, CID to MOV via exiftool)
CID=$(python3 -c "import uuid; print(str(uuid.uuid4()).upper())")
python3 bin/build_livephoto_pair.py <workdir> cover.jpg pair_src.mov <base_name> "$CID"
# -> <base_name>.JPG + <base_name>.MOV, identical basenames (required for pairing)
```
Requires: python3, piexif, ffmpeg, exiftool ≥13.59
(`git clone https://github.com/exiftool/exiftool` if apt lacks it).

### 3. QC checklist (all must pass before shipping to the user for device test)

- `exiftool -s -G1 -ContentIdentifier <base>.JPG <base>.MOV` → both show
  `[Apple]` / `[Keys] ContentIdentifier` with the IDENTICAL UUID.
- JPG opens valid at video resolution (720×1276); MOV plays, H.264 yuv420p.
- Basenames identical except extension; video extension is `.MOV` not `.mp4`.
- Total ZIP < 20 MB (Etsy per-file cap). If the MOV is close to the cap,
  re-encode the video a touch smaller BEFORE pairing (CRF 20–21) — grain at
  CRF 18 inflates dark videos (~19 MB for 4.8 s measured).

### 4. Real-iPhone acceptance test (user runs; the ONLY gate that matters)

1. Safari download ZIP → Files → unzip.
2. Files: select BOTH .JPG + .MOV → Share → Save to Photos.
   (Documented working import path: 0xjoex0/live-photo-merger "Method 3".)
3. Photos → Albums → Media Types → Live Photos: the item appears with LIVE badge.
4. Long-press plays the 4.8 s loop smoothly.
5. Settings → Wallpaper → Add New Wallpaper → Live Photos → pick it → set as
   Lock Screen → long-press Lock Screen plays.
Known risk to watch: makelive's author warns its pairs "may not work as Live
Wallpapers" (video format/length suspicion). If pairing works but wallpaper
doesn't, investigate intoLive's output format as the reference.

## Etsy live-wallpaper best practices (verified 2026-09-20)

From live Etsy listings (market pages + individual listings, prices observed):

| Practice | Evidence |
|---|---|
| Format: MP4 (+ matching JPG/PNG still) | "Format: MP4", "2 Video Files (MP4), 5s & 10s loop" |
| Seamless loop, 9:16, no sound | "Seamless Loop Animation", "No Sound (battery-friendly)" |
| Delivery: instant download, sometimes ZIP | "Digital file type(s): 1 PDF, 1 ZIP" |
| Setup via live-wallpaper app (intoLive on iPhone) | "Use a Live Wallpaper app (Android/iPhone)" |
| Pricing: $1.99–$6.99 | singles $2.99–$5.94; 7-pack (7 anim + 7 static 4K) $4.99; Y2K single $6.50 |

Observed listings: Dark Fantasy Knight Live Wallpapers Pack (7+7, $4.99, 5★);
Sheep-and-Ghost loop video (5s+10s MP4, $5.94, 5★); Cozy Winter Coffee live
wallpapers (MP4+PNG, $1.99–$2.99). Sources: etsy.com market pages
`animated_wallpaper_for_iphone`, `animated_iphone_wallpaper`, `4k_live_wallpaper`
(crawled Sep 2026).

## Known pipeline limits

- `media.generate_video` output so far: 640×1392 or 704×1248, 24fps H.264,
  5–10s, silent. Duration and resolution are NOT controllable — always normalize
  in step 4.
- Living subjects MORPH mid-video unless constrained: a silver fish gained
  mackerel stripes; a Bauhaus arc warped. Fix: put identity-lock constraints in
  the motion prompt ("must keep its exact ... body — must NOT gain stripes...").
  For geometric art, safest motion is a slow light sheen only (zero deformation).
- Mirror symmetry is a cheap-tell on geometric art: hard left-right mirroring
  reads as a cheap mirrored collage with a visible center crease. Use
  asymmetric balance instead (verified on the Bauhaus v2 sample 2026-09-20).
- True iPhone Live Photo pairing metadata CAN now be produced by this pipeline
  (Apple MakerNote tag 0x0011 + MOV mdta content identifier, see "No-app Live
  Photo pair delivery" above; structurally verified 2026-09-20). Real-iPhone
  pairing and wallpaper-usability are NOT yet confirmed — intoLive remains the
  fallback buyer route until the user validates on device.
- Kling O1 via fal.ai is the fallback for photoreal human-subject video
  (see MEMORY.md 2026-09-20); not needed for wallpaper loops.
