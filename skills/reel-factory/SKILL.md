# Reel Factory — ZenPixelWalls Instagram Reel mass production

Mass-produce 17-second iPhone-lockscreen Reels from live Etsy listings for the
brand account `zen.pixel.walls`. One owner agent runs each batch; drafts always
go to the user for approval before publishing.

## Input

A batch brief: list of combos. Each combo = 5 wallpapers + one mood.
Combos may be single-pack or cross-style mixes — user's call per batch.
No wallpaper image reused across reels within a batch (clean A/B).

## Pipeline

1. **Verify listings.** For every pack, read its `listing_id` from
   `~/workspace/instagram-setup/wallpaper-art/index.json`, then call
   `get_listing(listing_id)` (READ-ONLY — never create drafts or modify
   listings) via `~/workspace/etsy-automation/client.py`.
   The listing MUST be active at build time; if it is not active, that pack
   is unavailable — pick another pack. Never use unlisted/draft/local-only
   designs. For clean A/B tests, don't reuse the same image across reels.
2. **Fetch images.** Take phone-orientation wallpapers ONLY from the local
   authoritative library `~/workspace/instagram-setup/wallpaper-art/<pack-slug>/`
   (built 2026-09-23 from the 41 source ZIPs in `~/workspace/up4k_batch/orig_backup/`;
   see `index.json` for the pack→listing_id map and `NOTES.md` for the slug scheme).
   NEVER download the listing's `Images` from Etsy — the listing gallery mixes
   marketing assets into the artwork ("INSTANT DOWNLOAD" / "WHAT'S INSIDE"
   collages, phone mockups with fake 9:41 clocks, spec cards, app-icon grids),
   which contaminated two batches before this rule (2026-09-23). The local
   library holds pure wallpaper art only (eyes-on spot-checked); it is the
   single source of truth. The Etsy API is used ONLY to verify the pack's
   listing is currently active.
3. **Music.** One DIFFERENT real track per reel, mood-matched to the combo.
   Source: incompetech.com (Kevin MacLeod), CC-BY 3.0, commercial OK with
   credit. Preview before choosing — the track must feel like the visuals.
   Never synthesized drones/effects, never a fixed house style. Cut the best
   17s, 0.5s fade in/out, AAC. Write `attribution.txt` per reel
   (title / artist / source URL / license).
4. **Render** (structure evolved from v8.3 `dark-living-beings-lockscreen-v8.3.mp4`;
   batch brief sets wallpaper count — default 5 per reel, 17s total):
   - 0–2s: motto card `Art for your / most-viewed screen` (~1.2s fade-in,
     letter-spacing closing, slight upward settle)
   - 2–14.5s: 5 wallpapers as iPhone lockscreen mockups, 2.5s each
     (2.0–4.5 / 4.5–7.0 / 7.0–9.5 / 9.5–12.0 / 12.0–14.5), status bar +
     clock + date — COMPUTE THE DATE DYNAMICALLY at render time,
     format "Weekday, Month Day" — slow zoom/pan, 0.8s crossfades
   - 14.5–17s: end card `Link in bio ♥` (light serif, Cormorant Garamond style)
   - 1080×1920, 30fps, 17s, H.264 yuv420p + AAC (music: best 17s, 0.5s fades)
   - NO prices, NO clickbait, NO sales CTAs on the visuals. Artist angle only.
   - Render reels IN PARALLEL.
5. **Cover + caption.** `cover.jpg` (1080×1920 still). `caption.txt`: 2–4
   sentence artist-voice story about the combo's mood/inspiration, natural
   `Link in bio` close, then music credit line
   (`Music: <Track> by Kevin MacLeod (incompetech.com) — CC BY 3.0`),
   then ≤8 hashtags including #ZenPixelWalls.
6. **QC.** Extract frames at 1s, ~3.2/5.7/8.2/10.7/13.2s (one per wallpaper
   slot), and 16s per reel and eyeball: text legible, correct images,
   correct date, no glitches. `ffprobe` specs + audio present.
   Never hand off a broken reel.
7. **Review gate.** Hand back `reel.mp4 + cover.jpg + caption.txt +
   attribution.txt` per combo. PUBLISH ONLY on the user's explicit approval,
   via `instagram-cli post-reel --account-id 17841421372905519`, then verify
   (post count +1, caption matches, correct account).

## Iron rules (permanent)

- Music, copy, visuals share one mood; real music only.
- **Music bar = 10x the visual bar (user standing order 2026-09-21, permanent).** Act like a musician: melody, rhythm, instrumentation meticulously chosen, every candidate actually listened to. Source classic high-end material — classical, orchestral, jazz, psychedelic electronic, gospel, etc. — fresh and refined, never cheap/formulaic/lo-fi-cliché. Music is the first variable: if a track doesn't elevate the reel, keep searching; never settle. 2026-09-21 lesson: user rejected 3 of 4 Kevin MacLeod-style tracks as "cheap" after hearing drafts — default royalty-free libraries are guilty until proven innocent.
- **When unsure, use established classics (user order 2026-09-21, permanent):** don't gamble on obscure library tracks — use famous public-domain masterpieces (Debussy, Satie, Bach, traditional gospel hymns, etc.) with openly licensed recordings (e.g. Musopen CC0/public-domain recordings). Never rip commercial label recordings.
- Images only from the local `wallpaper-art/` library, and only from packs whose
  Etsy listing is API-verified active at build time (re-verify every batch).
  Never pull images from a listing's gallery.
- Drafts → user approval → publish. Never auto-publish.
- Motto is `Art for your most-viewed screen`; never the old BORING line.
- Only post to `zen.pixel.walls`; never the personal account.
- Don't surface internal media IDs to the user.

## Batch log

- 2026-09-20: first batch — 10 combos A/B test (single-pack + cross-style mixes),
  10 different tracks. Owner: reel-factory coordinator.
- 2026-09-21: batch rebuilt to 17s / 5 wallpapers per reel (user: "don't cram").
  Renderer: `~/workspace/instagram-setup/ab-test/render_reel.py`
  (config `combos.json`). 10 combos: 5 single-pack
  (chrome-static, prism-drift, ink-silence, retro-rhythm, abyssal-calm) +
  5 mixes (midnight-trio, night-smoke, golden-hour, soft-minimal,
  ink-and-paper); 50 unique listing images, 10 distinct Kevin MacLeod tracks.
  Pipeline lessons: xfade needs matched timebases (settb=AVTB on all legs);
  zoompan needs ONE still input (no -loop, d=N frames); overlay PNG fade needs
  a looped/timed input or fade never progresses; force mpeg range
  (scale=out_range=mpeg) or output lands yuvj420p; 1400k VBR ≈ 3MB/17s.
- 2026-09-22: creative direction pivot (user decision). If saves/views stay
  weak, move toward fine-art direction — e.g. Renaissance / art-history
  elements — with much more detailed prompts, zero AI-look. Per the research
  iron rule: research the niche's winning formats first, form a playbook,
  THEN produce. No publishing without explicit approval.
- 2026-09-23: transition UI ghosting bug FIXED in render_reel.py (root cause:
  per-slot lockscreen UI was composited onto each slot clip BEFORE the xfade
  chain, so the 0.8s fade showed two different date/clock fonts overlapping).
  Fix: slot UIs are concatenated into one UI video track (each held for its
  slot dwell) and overlaid AFTER xfade with hard cuts at transition midpoints;
  per-slot font rotation preserved. Backup of the old
  renderer: render_reel.py.bak-20260923. Rule: never bake overlay graphics
  into clips that go through a crossfade — composite them after.
- 2026-09-23: UI-track sync bug FIXED (user caught it: "date switch not synced
  with wallpaper"). Root cause: overlay's framesync consumes the secondary
  (UI) input from t=0 even while enable='gte(t,1.6)' is false, so the whole UI
  timeline ran 1.6s EARLY — the date hard-cut ~1.2s before the wallpaper
  transition even started, and the last slot's final 1.2s had no UI at all.
  Fix: [uiv]setpts=PTS+<ui_start>/TB delays the UI track so its local t=0
  aligns with the first transition midpoint on the output timeline. Rule:
  overlay `enable` only gates compositing, it does NOT delay the secondary
  stream — always shift the secondary stream itself with setpts when you need
  a delayed overlay.
- 2026-09-23: `-loop 1 -t {dur}` image-input RACE fixed (the true root cause
  behind the "date switch" complaint). With many inputs, the image2 demuxer's
  `-t` cutoff vs `-loop 1` timing is NON-DETERMINISTIC: measured UI segment
  frame counts of 66/54/66/54/60 instead of 60/60/60/60/60, shifting UI
  segment boundaries by up to 0.2s (date cut landed at output frame #114
  instead of #108). Fix: feed SINGLE frames (no -loop, no -t) and expand
  with the loop filter — `format=rgba,loop=loop={N-2}:size=1:start=0`
  yields exactly N frames, deterministically (empirically verified).
  Rule: NEVER use `-loop 1 -t` for image inputs in a multi-input graph;
  always use single-frame input + loop filter (or another deterministic
  frame-count method). Applies to UI segments AND the end-card text input.
- 2026-09-23: authoritative pure-wallpaper library built at
  ~/workspace/instagram-setup/wallpaper-art/ (41 packs, 156 pure JPGs from
  the 41 orig_backup ZIPs, index.json maps every pack to its Etsy listing_id).
  Renderer takes content images ONLY from this library; Etsy API is used only
  to verify the listing is active. Never download a listing's gallery images
  again (marketing/mockup images in galleries were the root cause of two
  2026-09-23 contamination incidents).
- 2026-09-23: x264 preset benchmark (solo run, chrome-noir, same input).
  CORRECTION: the 83.7s/64.7s numbers first reported were shell `time` USER
  CPU time, not wall-clock. Process-observed wall-clock: medium ~63.1s vs
  veryfast ~51.0s — ~1.24x (about 19% faster), 2.476MB vs 2.436MB (~1.6%
  smaller), side-by-side frames visually identical. Full benchmark (SSIM/VMAF,
  motion/transition frames, IG recompression) still pending before switching
  future production to veryfast. (Earlier "near 2x" guess was wrong: most
  build time is Python/PIL + single-threaded zoompan, not x264.)
- 2026-09-23: user rule — ALL code must have unit tests (permanent).
  render_reel.py was refactored: ffmpeg command construction extracted into
  pure function `build_video_cmd(cfg, tmp, n, dwells, clip_ds, motions)`
  (no side effects, no ffmpeg run). Tests in
  `~/workspace/instagram-setup/ab-test/test_render_reel.py` (13 tests,
  `python3 -m pytest test_render_reel.py -v`): no `-loop 1 -t` on UI/end-text
  inputs (race regression), loop filter counts, xfade offset math, ui_start,
  filtergraph structure (concat→setpts order, eof_action=pass). Run tests
  before any render_reel.py change.

- 2026-09-23: creative redesign (user feedback on second-wave drafts).
  Two changes: (1) SINGLE static lockscreen UI for the whole reel — the
  per-slot font rotation (5 typography styles) looked wrong/jarring when the
  font visibly changed between wallpapers. Now one Inter Light style, one
  date, no changes. (2) HARD CUTS between wallpaper slots — the 0.8s
  crossfades looked bad (muddy mid-fade). xfade chain replaced with concat.
  Total duration now 15.3s (2.0 motto + 10.0 wallpapers + 3.3 end card, no XF
  subtraction). `build_video_cmd` returns (fc, total_d). Tests rewritten:
  12 tests covering no-xfade, concat hard cuts, single ui.png, static UI
  enable window [MOTTO_D, MOTTO_D+sum(dwells)).
