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
   via `instagram-cli post-feed --account-id 17841421372905519 --file reel.mp4 --cover cover.jpg --caption "$(cat caption.txt)"`
   (post-feed handles video; there is no post-reel command), then verify
   (post count +1, caption matches, correct account).

## Iron rules (permanent)

- Music, copy, visuals share one mood; real music only.
- **Music bar = 10x the visual bar (user standing order 2026-09-21, permanent).** Act like a musician: melody, rhythm, instrumentation meticulously chosen, every candidate actually listened to. Source classic high-end material — classical, orchestral, jazz, psychedelic electronic, gospel, etc. — fresh and refined, never cheap/formulaic/lo-fi-cliché. Music is the first variable: if a track doesn't elevate the reel, keep searching; never settle. 2026-09-21 lesson: user rejected 3 of 4 Kevin MacLeod-style tracks as "cheap" after hearing drafts — default royalty-free libraries are guilty until proven innocent.
- **When unsure, use established classics (user order 2026-09-21, permanent):** don't gamble on obscure library tracks — use famous public-domain masterpieces (Debussy, Satie, Bach, traditional gospel hymns, etc.) with openly licensed recordings (e.g. Musopen CC0/public-domain recordings). Never rip commercial label recordings.
- **Classic ≠ fitting (2026-09-28 lesson, user veto):** an ink-wash reel scored with Mussorgsky's *Promenade* (grand symphonic brass) was rejected — "东方水墨配大交响？". Instrumentation and cultural texture must match the visuals, not just the energy level: serene East-Asian ink-wash needs sparse, restrained, East-Asian-appropriate timbres (guqin/shakuhachi/koto-type or equivalent restraint), never grand European orchestral forces. When the visual has a strong cultural identity, the music's cultural identity must agree.
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
- 2026-09-23: UI-transition history (condensed — all superseded by v3 below).
  v1 baked per-slot ADAPTED UI geometry before xfade => ghosting (date doubled
  at two positions mid-fade). v2 then overlaid one UI track AFTER xfade with
  hard cuts at transition midpoints => date popped mid-dissolve, perceived as
  random/unsynced (user: "日期的切换完全random"). Root-cause insight: v1's
  ghosting came from per-slot ADAPTED GEOMETRY, not from baking itself.
  Related fixes that remain valid: overlay `enable` only gates compositing,
  not the secondary stream's clock — always shift it with setpts (fixed the
  1.6s-early UI bug); NEVER use `-loop 1 -t` for image inputs in a
  multi-input graph — use single-frame input + loop filter (fixed the
  non-deterministic UI segment frame counts 66/54/66/54/60).
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
- 2026-09-23 (v3, AUTHORITATIVE — supersedes all UI/xfade entries above).
  User rejected v2 ("日期没渐变，卡点也不对，日期的切换完全random"):
  the post-xfade UI track with hard cuts at transition midpoints made the
  date POP mid-dissolve while the wallpaper was still fading — deterministic
  in code (frame diff 37-45 exactly at midpoints) but perceived as random/
  unsynced. Root-cause insight: v1's ghosting ("还没渐变") came from
  PER-SLOT ADAPTED UI GEOMETRY (different time_y/size/position per
  wallpaper) baked before xfade — not from baking itself. Final architecture:
  bake the UI onto each slot clip BEFORE the xfade chain
  ([raw{i}][ui_i]overlay -> xfade), with ONE FIXED geometry for all slots
  (UI_TIME_Y/UI_DATE_Y/UI_TIME_SIZE/UI_DATE_SIZE + single UI_STYLE font —
  user: "就一个格式"); only the text color adapts to wallpaper brightness
  for readability. Identical geometry => mid-fade the date either holds
  perfectly still (same color both sides) or crossfades cleanly in place —
  it can never jump position or double up. The date goes through the same
  0.8s fade as the wallpaper ("日期跟着壁纸一起渐变"); the 卡点 IS the
  transition, synced by construction. No post-xfade UI track, no ui_start,
  no enable/setpts/eof_action UI overlay. build_video_cmd returns (fc, offs).
  Tests rewritten (18 tests): UI bake present before first xfade, no v2 UI
  track remnants, byte-identical UI layout across colors, fixed geometry
  constants. Verified on dark-beings: date-region frame diff 0.4-0.9 across
  the transition (was 37-45), contact sheet shows the date locked while the
  wallpaper dissolves behind it, and the date fades in with the wallpaper on
  motto->slot0.
- 2026-09-23 (v3 color-detection fix). Text color is decided from the two
  tight bands the text actually occupies (work coords: date y 380-500, clock
  y 620-830, x 270-1350), using the BRIGHTER of the two: either bright
  (>0.52) => dark-gray text (28,28,28), else white. Never use the old top-60%
  average (misclassified a bright dome as dark => white text washed out on
  chrome-noir slot 3). 22 tests incl. brighter-of-two-bands regression.
- 2026-09-24: `REEL_DATE=YYYY-MM-DD` env override added to render_reel.py
  (`get_render_date()`; 3 new tests, 25 total). Lets a night-before render
  show the posting day's date. 9 reels re-rendered with REEL_DATE=2026-09-25
  for the 9/25 hourly drip (cron zenpixelwalls-reel-drip-v3, 08:00-16:00 EDT,
  queue in ~/workspace/instagram-setup/publish-queue.json); noir-macros
  additionally rendered with REEL_DATE=2026-09-24 for an immediate post the
  night before.
- 2026-09-24 (batch-coordination BUG): the 9/24-dated noir-macros file that
  was ALREADY PUBLISHED got overwritten at 00:55 EDT by the 9/25 batch
  writing to the SAME output path (`noir-macros/reel-gradient-v3.mp4`).
  No harm this time (published + dequeued before the overwrite), but the
  rule is permanent: ONE writer per output path. Never let two batches
  target the same file; if a second version is needed, use a distinct
  filename or confirm the first is consumed before the second writes.
- 2026-09-24 (PERMANENT lessons — gradient & 卡点 red lines, user order:
  never repeat these).
  1. Date and wallpaper MUST share the SAME fade and the SAME timing
     (卡点). v3 architecture: bake the UI onto each slot clip BEFORE the
     xfade chain, ONE fixed geometry for all slots (only text color adapts
     to brightness). Never a post-xfade UI track with its own fades (v2
     bug: the date popped mid-dissolve at transition midpoints, perceived
     as random/unsynced), and never hard cuts unless the user explicitly
     asks for them.
  2. Ambiguous ultra-short creative instruction (e.g. "别改日期，就一个格式"
     — meant: unify the font format, keep the fade) → align in ONE sentence
     BEFORE burning render time. Misreading it as "remove the gradient"
     cost a full 9-reel re-render with hard cuts that had to be redone
     (2026-09-23, the most expensive lesson of this project).
  3. REEL_DATE discipline: night-before renders pin the posting day via
     REEL_DATE=YYYY-MM-DD; invalid dates raise ValueError, never silently
     default. Never re-render solely to change the on-screen date unless
     the date is actually wrong (user 2026-09-24: current date is fine,
     do not re-render).
  4. Text color: BRIGHTER of the two text bands (date y 380-500, clock y
     620-830, x 270-1350) > 0.52 => dark-gray (28,28,28), else white.
     Never average the top-60% brightness (misclassified bright dome as
     dark => washed-out white text on chrome-noir slot 3).
  5. End card shows only `ZenPixelWalls / Link in bio` — no lock-screen UI.

- 2026-09-28: first daily run (cron reel-daily-production). 5 combos, 25 unique
  phone-only images (3 single-pack: b01/b03/b02 + 2 mixes: morandi l01+l02,
  chrome l04+l05+w14), 5 different public-domain classical tracks
  (Holst Neptune / Bach BWV565 organ / Mussorgsky Promenade / Satie Gymnopedie /
  Debussy Clair de lune), all QC-passed. INCIDENT: date-prefixed slugs
  ("2026-09-28/x") made best_music_window write to a bogus nested tmp path
  `/tmp/_vol_2026-09-28/<combo>_<pid>.wav` — ffmpeg failed on all 4 first
  renders (exit codes were masked by `| tail`, so failures looked like
  successes). Fixed: `_music_wav_path()` sanitizes "/"->"_" + 2 regression
  tests (27 tests pass). Lesson: never pipe renders to tail when exit codes
  matter; re-verify output files exist after any render.
