---
name: "instagram-automation"
description: "Operate the ZenPixelWalls brand Instagram account (zen.pixel.walls) via instagram-cli: profile setup, bio/picture updates, publishing (feed/story/reel/carousel), and insights monitoring. Triggers on any ZenPixelWalls Instagram task. Read /opt/hatch/skills/instagram/SKILL.md first for the full CLI contract."
---

# Instagram Automation (ZenPixelWalls)

## Purpose
Run the `zen.pixel.walls` brand account end-to-end from the CLI: profile maintenance, scheduled publishing, and performance monitoring. Never touch the personal account `tangziyi001`.

## Tooling
CLI: `instagram-cli <target> --account-id 17841421372905519 [options]`
Full command reference: `/opt/hatch/skills/instagram/SKILL.md` (always re-read before publishing work).

Brand assets: `~/workspace/your_files/etsy-shop-branding/` (logo `zenpixelwalls-logo-500x500.png`, banner `zenpixelwalls-banner-1600x400.jpg`).
Setup baseline: `~/workspace/instagram-setup/baseline-2026-09-20.json`.

## Auth
- Account must appear in `instagram-cli accounts`. If missing, user links it once via Meta Accounts Center (`instagram-cli connect-url` gives the URL).
- Write commands (`set-profile-picture`, `update-bio`, `post-*`) require a transient user confirmation; the runtime auto-approves per standing approval, surfaced as `userConfirmationStatus: approved`. If a write fails with a grant error, wait ~60s and retry once — do not hammer.

## Operating Rules
1. **Account scoping**: always pass `--account-id 17841421372905519` (zen.pixel.walls). Never run writes against `tangziyi001`.
2. **No posting without explicit approval**: `post-story --draft` renders locally without uploading — always show the draft render to the user and get confirmation before the real post. Never pass `--retries` to any `post-*` command (duplicate risk).
3. **Media must live under `~/workspace/`** — never publish from `/tmp`. Feed images: 4:5 @ 1080x1350 preferred. Reels/stories: 9:16 @ 1080x1920, MP4 needs a matching JPG/PNG cover.
4. **Bio ≤ 150 chars.** Current bio (2026-09-20): `AI phone wallpapers · 4K Ultra HD 📱 New designs weekly ✨ Shop on Etsy 👇 etsy.com/shop/ZenPixelWalls`. Etsy URL verified via Etsy API (`https://www.etsy.com/shop/ZenPixelWalls`) — never guess it.
5. **Rate limits**: budget API calls; >~1000 calls in a task needs scope confirmation. Never poll persistently.
6. **Do not expose FBIDs** or internal IDs to the user; use usernames in reports.

## Workflow: new-account onboarding (done 2026-09-20)
1. `instagram-cli accounts` → confirm `zen.pixel.walls` present, note `is_professional`.
2. `instagram-cli profile --account-id ...` → capture follower/following/posts baseline.
3. `set-profile-picture --file <500x500 PNG logo>` → verify via re-fetch (pic URL changes).
4. `update-bio --bio "..."` (≤150 chars, English, includes Etsy link).
5. Business switch → **manual only** (see below).
6. Validate: `post-story --draft` with a 9:16 test file (renders, no upload). `account-insights` before professional = HTTP 500 (expected).
7. Write baseline JSON to `~/workspace/instagram-setup/`.

## Professional/business switch (manual — no API exists)
Neither `instagram-cli` nor Meta's Graph API can switch account type. The user must do it once in the Instagram mobile app, logged in as `zen.pixel.walls`:
1. Profile → ☰ (top right) → **Settings and privacy**
2. **Account type and tools** → **Switch to professional account** → Continue
3. Pick a category (e.g. Art, or Shopping & retail) → Done
4. Choose **Business** (NOT Creator) → optionally link/skip Facebook Page → Done
After the switch, re-run `instagram-cli accounts` and confirm `is_professional: true`; then `account-insights` becomes available. Status 2026-09-20: user switched in-app, verified `is_professional: true` + `account-insights` returning data (all zeros, new account).

## Publishing preconditions (before any scheduled posting)
- Account shows `is_professional: true` (needed for insights/attribution; posting itself works on personal too).
- At least one 9:16 (1080x1920) reel or 4:5 (1080x1350) image in `~/workspace/`, plus cover for video.
- Caption ≤ 2200 chars, hashtags/mentions allowed.
- Draft-first workflow per SKILL.md; delete superseded drafts by exact path after publishing.

## Monitoring
- Baseline: `~/workspace/instagram-setup/baseline-2026-09-20.json` (0/0/0 on 2026-09-20).
- Track: `Instagram bio clicks → Etsy visits → orders` 30-day funnel (Etsy stats via `~/workspace/skills/etsy-open-api/SKILL.md`).
- Re-check `account-insights` only after business switch.

## Pitfalls hit (2026-09-20)
- `Error: query connector grant` on all data commands right after linking: transient. Wait ~60s, retry with `--retries 2/3` (reads) — recovered on its own.
- `Error: check for expired transient grants` on first `set-profile-picture`: wait ~20s, retry without `--retries` (unsupported on that command) — succeeded.
- `update-bio` has no `--help` and no website-link option; put the shop URL in the bio text itself.
- `account-insights` on a non-professional account fails with HTTP 500, not a clean "not professional" message — check `accounts` → `is_professional` first instead of inferring from the error.
- `post-story --draft` requires `--editor-json` (non-empty array) and renders under `workspace/instagram/stories/` — safe, no upload.
- `post-feed` has NO `--draft` flag (verified 2026-09-20: "unknown post-feed option --draft"). Feed "draft" = prepare image + caption locally and show the user; any successful `post-feed` invocation publishes. Verify with `posts --limit 5` (count 0) after a failed attempt.
- **No delete via API/CLI (verified 2026-09-21)**: neither `instagram-cli` nor Meta's Graph API exposes post deletion. Deleting a published post is app-only: profile → Reels/Posts tab → open the post → ••• → Delete. Never claim you deleted something via CLI.
