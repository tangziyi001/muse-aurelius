---
name: "pinterest-api"
description: "Post Pinterest pins fully automatically via the official Pinterest API v5: developer-app onboarding, OAuth 2.0, token refresh, board management, image_pin creation (base64, no public hosting needed). Use for any Pinterest promotion automation — never drive Pinterest through a browser. Reference implementation: ~/workspace/pinterest-automation/client.py."
---

# Pinterest API v5

Post pins via the official Pinterest API v5 (pure stdlib Python, no browser).
Reference implementation lives in `~/workspace/pinterest-automation/`
(`oauth.py` auth-URL + code exchange, `client.py` API client, `config.py` credential store,
`post_pins.py` daily gated poster).

## Measured rules (all verified 2026-09-20, do not re-derive)

1. **Official generated-client docs are the ground truth for params.** Verified from
   `pinterest/pinterest-python-generated-api-client` `docs/PinsApi.md`, `docs/PinCreate.md`,
   `docs/PinMediaSourceImageBase64.md` (2026-09-20):
   - `POST https://api.pinterest.com/v5/pins` with JSON body:
     `board_id`, `title` (≤100 chars), `description` (≤500 chars, hashtags OK),
     `link` (public mobile-friendly URL), `alt_text` (≤500),
     `media_source: {source_type: "image_base64", content_type, data}`.
   - `image_base64` needs **no public image hosting** — the image bytes ride in the request.
     (Alternative `image_url` mode requires a publicly reachable URL.)
   - Boards: `GET /boards` (list), `POST /boards` (`name`, `description`, `privacy: PUBLIC`).
2. **OAuth 2.0 authorization-code flow** (not PKCE):
   - Authorize: `https://www.pinterest.com/oauth/?client_id=…&redirect_uri=…&response_type=code&scope=…&state=…`
   - Token: `POST https://api.pinterest.com/v5/oauth/token`, HTTP Basic auth
     `base64(app_id:app_secret)`, form fields `grant_type`/`code`/`redirect_uri`
     (or `grant_type=refresh_token&refresh_token=…`).
   - Scopes for pin posting: `boards:read, boards:write, pins:read, pins:write`.
3. **Token model: access_token ~30 days (`expires_in: 2592000`), refresh_token rotates.**
   Every refresh response carries a NEW refresh token; the old one dies immediately.
   Always persist the newest response. Refresh when `expires_at - 120s < now`.
   (Community reports disagree on refresh-token lifetime — 60d vs 1y — so design for
   "refresh at least once every 30 days", which the daily poster does naturally.)
4. **Trial access = sandbox.** New apps start on Trial; pins/boards created on Trial are
   **visible only to the creator** (official: "only visible to their creator as Sandbox entities").
   Public posting requires **Standard access** via app review (Upgrade button on the app card).
   Review needs: a screen recording of the app using the API (official docs explicitly accept
   a terminal/Postman recording, and explicitly cover the "sole user is yourself" case).
   Review turnaround is not officially committed (community: days, not weeks).
5. **Privacy-policy URL validation (measured 2026-09-20, 3 failed attempts + community cases).**
   The inline check requires ALL of: (a) the URL string contains the company name,
   (b) its host matches the "Company website or App link" host (third-party hosts like
   telegra.ph fail even with the name in the path — community reports the same for
   own-domain and free-subdomain hosts, so the check is buggy/strict),
   (c) it must NOT be the exact same URL as the company website
   ("Whoops, you've entered the same URL as your company/app's site").
   For an Etsy-shop company site, `https://www.etsy.com/search?q=<CompanyName>` passes
   all three and unblocks app creation. This is a Trial-stage placeholder only —
   swap in the real policy URL (ideally on an owned domain) before Standard review.
5. **Rate limits** (official `/docs/reference/rate-limits/`): pin writes are `org_write` —
   Trial 300 req/day/app, Standard 100 req/min/user/app. 3–5 pins/day is nowhere near either.
6. **Credential storage:** `~/.config/pinterest-automation/env` (mode 600),
   `~/.config/pinterest-automation/tokens.json` (mode 600).
   **Never print tokens/app secret** in chat, logs, memory, or reports.

## One-time human setup (irreducible, batch into ONE ask)

1. Human creates (or converts to) a **Pinterest Business account** (brand name).
2. Human creates the app at developers.pinterest.com (name/description/use-case),
   records App ID + App Secret (secure channel to agent), registers an HTTPS redirect URI
   (recommend a one-off `https://webhook.site/<uuid>` URL), submits the Trial access request.
3. Agent prints the authorize URL; human opens it, approves scopes, pastes the `code`
   from the redirect URL back **once**. Agent exchanges code → tokens; refresh is unattended after.
4. After Trial is granted: agent creates sandbox pins via API and records a terminal
   session of it; human uploads the recording on the app card (Upgrade → Standard) and
   waits for the approval email. Agent then touches
   `~/.config/pinterest-automation/standard_approved` and the daily poster goes live.

## Daily poster (post_pins.py)

- Gates: exits quietly (log line only) unless tokens exist AND `standard_approved` flag is set.
- Idempotent board: `ensure_board()` creates "ZenPixelWalls | Phone Wallpapers" once.
- Posts up to `--count` (default 3) unposted queue items per run; `posted_pins.json`
  guarantees no double-posts; 5s pacing between posts.
- Queue format: `[{listing_key, listing_id, image_path, title, description, link, alt_text}]`.
  Links must be real Etsy listing URLs (from `~/workspace/etsy-automation/publish_state.json`
  via the Etsy API `url` field) — never fabricate.

## Pinterest vs TikTok (2026-09-20 decision)

- **Pinterest first**: lowest one-time cost (~30–60 min human), day-scale review,
  officially supports self-use, image pins map 1:1 to wallpaper assets, `link` goes
  straight to the Etsy listing.
- **TikTok deferred**: Content Posting API needs audit (2–4 weeks), requires privacy-policy
  + terms + public website + domain verification, and an unverified community claim says
  "apps must not be for private/personal use" — that clause is the go/no-go gate and was
  NOT verified against the official App Review Guidelines. Verify before spending anything.
