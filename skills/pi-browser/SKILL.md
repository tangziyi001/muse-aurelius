---
name: "pi-browser"
description: "Drive a logged-in, bot-resistant Chromium on the home Raspberry Pi for browser automation. Use when a task needs a persistent login session, a residential (non-datacenter) egress IP, or a site that throws DataDome / 'verify you are human' walls at the cloud browser — e.g. contributor-portal uploads. (Etsy shop work goes through the official Open API, not this browser — see the etsy-open-api skill.) Do NOT use for public pages or plain search; those stay on the cloud browser."
---

# Pi Browser

## Purpose

Run browser automation on the home Raspberry Pi (Raspberry Pi 5, 16GB RAM, on the same Tailscale tailnet as the cloud VM) instead of the cloud. The Pi exits through the home residential network, which is what lets login sessions survive on bot-sensitive sites where the cloud browser is challenged on sight. The Pi is the "identity host": login-gated work lives there; heavy compute and public reads stay in the cloud.

## When to use Pi vs cloud browser

- **Pi:** any flow needing a login session; sites that serve DataDome/slider/"verify you are human" to datacenter IPs; sessions you want to keep warm across runs.
- **Cloud:** public pages, search, anything without login or bot checks. Faster to start, no SSH hop.
- **Rule of thumb:** if the cloud browser hits a bot wall on the site's homepage, switch to Pi immediately — do not fight the wall from the cloud.

## One-time human setup (human steps)

Everything in this section must be done **by the human on their own devices**. The agent cannot do it: each step needs an interactive login, a consent click, or access to the home network UI. Everything after this section is agent-runnable.

### 1. Tailscale: join the tailnet

- Install Tailscale on the Pi (Home Assistant OS: the Tailscale add-on) and on the operator machine (cloud VM and/or the user's computer).
- Sign in to the **same** Tailscale account/tailnet on all of them. This is an interactive OAuth flow in a browser — the agent has no way to click through it.
- Record the Pi's tailnet address: IP `100.103.139.55`, hostname `homeassistant`, LAN `192.168.1.176`. That IP is the SSH target in every command below.
- **Auth key expiry: 2027-03-19.** The key used for unattended SSH dies on this date. This is a human calendar item: re-authenticate/renew in the Tailscale admin console before then, or SSH breaks with no warning.

### 2. HA Terminal & SSH add-on: open the 2222→22 mapping

- In Home Assistant → Terminal & SSH add-on → Configuration, map host port **2222** to container port **22**, then restart the add-on. Toggling this requires the HA UI (local-network admin login) — the agent cannot reach it.
- Why 2222: the cloud VM's egress proxy intercepts port 22 and lands on the wrong x86_64 runtime. Port 2222 is the only working SSH path; the agent must never use 22.
- After any add-on update or HA restart, check the mapping is still there. If `ssh -p 2222` suddenly fails, this is the first thing to verify.

### 3. /config is the only durable disk

- On Home Assistant OS, only `/config` survives reboots. Browser profiles (`/config/<project>/profile`), automation scripts, queues, and `secrets/` all live under `/config/`. Nothing to configure — just never put durable state anywhere else.
- `/tmp` is wiped on reboot: screenshots and scratch only.

### Human-owned vs agent-owned (the split)

- **Human, one-time/interactive:** Tailscale install + tailnet login/consent; HA add-on port-mapping toggle + restart; auth-key renewal before 2027-03-19; OTP/2FA relay (paste the newest code once when asked); site-side one-offs — account creation, KYC, tax forms, payment, API-terms acceptance.
- **Agent, repeatable/scripted:** everything from `## Connection` down — SSH on 2222, launching Chromium, probing login state, polling `otp_code.txt`, filling/submitting codes, shredding them, extracting and storing secrets.

Rule for the agent: if a step needs the human's eyes, fingers, or consent, ask **once**, batch all such steps into that one ask, and never ask twice for the same thing.

## Connection

SSH is always on port **2222** (the HA Terminal & SSH add-on maps 2222→22). Port 22 hits the wrong x86_64 runtime — never use it.

```bash
ssh -i /home/hatch/.ssh/id_ed25519 \
  -o ProxyCommand="/home/hatch/workspace/pi-ssh/socat_cmd.sh %h %p" \
  -o BatchMode=yes -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null \
  -p 2222 root@100.103.139.55
```

- The `pihome` alias is the preferred path: defined in `/root/.ssh/config` with the socat ProxyCommand plus `ControlMaster auto` / `ControlPath /tmp/ssh_mux_%h_%p_%r` / `ControlPersist 30m` (first command ~2s establishes the master, follow-ons ~0.3s). Just run `ssh pihome '<cmd>'`.
- **Root-vs-$HOME trap (2026-09-21, real outage):** exec/subagents run as **root**, and ssh resolves the user config from the passwd database, **not** `$HOME`. Aliases written to `/home/hatch/.ssh/config` are silently ignored; ssh falls back to `/etc/ssh/ssh_config`'s global proxy and fails with `Connection reset by 198.19.0.1 port 3128`. Aliases MUST live in `/root/.ssh/config`. Diagnose with `ssh -G <alias>` — if `hostname`/`port`/`proxycommand` don't show your values, you're reading the wrong file.
- **`/root` is ephemeral (2026-09-21, second outage):** files under `/root` (including `/root/.ssh/config`) can disappear on VM reboot/replacement — only `~` (`/home/hatch`) survives. The VM **does** reboot (observed 2026-09-21 05:17). Canonical copy lives at `~/workspace/pi-ssh/pihome-ssh-config`. **Mandatory preflight:** run `~/workspace/pi-ssh/ensure-pihome.sh` before `ssh pihome` in any fresh session — it recreates `/root/.ssh/config` only if `ssh -G pihome` doesn't resolve. If `ssh pihome` says "Could not resolve hostname pihome", the config is gone; run the ensure script.
- The `pi-ha` alias (proxy_cmd.py) flaps with `Connection reset by 198.19.0.1:3128`; the socat ProxyCommand above is the reliable one.
- The egress proxy hiccups: retry the ssh command 2–3 times with a few seconds between attempts before concluding the Pi is down. To tell proxy-flap from Pi-down: raw-socket test — CONNECT through the proxy to 100.103.139.55:2222 should return `HTTP/1.1 200`, and the Pi's SSH banner (`SSH-2.0-OpenSSH_*`) should follow on first read.
- Pass `-i` explicitly when running as root and not using the alias (`~/.ssh` resolves to `/root/.ssh` there).
- Tailscale key expires **2027-03-19** — renew before then or SSH breaks.

## Filesystem conventions (read-only unless the task says otherwise)

- `/config/` — survives reboots. All durable state lives here.
- `/tmp/` — wiped on reboot. Screenshots and scratch only.
- `/config/<project>/shots/` — screenshots, status JSON, and the OTP relay file.
- `/config/<project>/secrets/` — directory `0700`, files `0600`. Secrets never go into logs, screenshots, or result JSON.
- Existing on-Pi reference implementations (read them before writing a new flow):
  - `/config/etsy-browser/cdp.py` — CDP client: `launch()`, `nap()`, `wait_for_js()`, `click_selector()`, `type_text()`
  - `/config/etsy-browser/etsy_session_probe.py` — login-state probe pattern
  - `/config/etsy-browser/etsy_login_and_create_app.py` — full OTP-login + business-flow pattern

## Launching hardened Chromium (standard pattern)

Headed Chromium under Xvfb with a **persistent profile** (cookies/login survive reboots), driven over CDP. The on-Pi helper is `/config/etsy-browser/cdp.py`; `launch()` below mirrors it:

```python
import json, os, subprocess, time, urllib.request

PROFILE_DIR = "/config/pi-browser/profile"  # persistent: one dir per project
DEBUG_PORT = 9222                            # (Etsy automation uses /config/etsy-browser/profile)

def _http_get(url, timeout=5):
    with urllib.request.urlopen(url, timeout=timeout) as r:
        return r.read()

def launch(headed=True):
    """Launch hardened Chromium, return (websocket_url, proc)."""
    os.makedirs(PROFILE_DIR, exist_ok=True)
    env = dict(os.environ)
    env["DISPLAY"] = ":99"               # Xvfb display; ensure Xvfb is running first
    env["TZ"] = "America/New_York"
    flags = [
        "/usr/bin/chromium",
        "--remote-debugging-port=%d" % DEBUG_PORT,
        "--user-data-dir=%s" % PROFILE_DIR,
        "--window-size=1366,768",
        "--disable-blink-features=AutomationControlled",  # hide automation flag
        "--no-sandbox",
        "--disable-dev-shm-usage",
        "--lang=en-US", "--accept-lang=en-US,en",
        "--no-first-run", "--no-default-browser-check",
        "--disable-background-timer-throttling",
        "--disable-backgrounding-occluded-windows",
        "--disable-renderer-backgrounding",
        "--disable-features=TranslateUI",
        "--mute-audio",
        "about:blank",
    ]
    if not headed:
        flags.append("--headless=new")
    proc = subprocess.Popen(flags, env=env,
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    for _ in range(100):  # wait for DevTools endpoint
        try:
            _http_get("http://127.0.0.1:%d/json/version" % DEBUG_PORT)
            break
        except Exception:
            time.sleep(0.3)
    else:
        raise RuntimeError("chromium DevTools endpoint never came up")
    for _ in range(50):  # pick the first page target
        targets = json.loads(_http_get("http://127.0.0.1:%d/json/list" % DEBUG_PORT))
        pages = [t for t in targets if t.get("type") == "page"]
        if pages:
            return pages[0]["webSocketDebuggerUrl"], proc
        time.sleep(0.2)
    raise RuntimeError("no page target found")
```

Driven via CDP websocket afterwards: `navigate(url)`, `evaluate(js)`, `screenshot(path)`, plus CDP `Input.dispatchMouseEvent` for human-like clicks.

## Common patterns

### 1. Screenshot debugging

After every navigation and every critical click, save a screenshot to `shots/` and pull it back to inspect:

```bash
scp -P 2222 <same ssh opts> root@100.103.139.55:/config/<project>/shots/<name>.png /tmp/
```

Screenshots are the reliable progress signal (see pitfalls: stdout buffering).

### 2. Login-state probe (`state_js`)

Never trust a cookie jar blindly — evaluate this after navigation and branch on it:

```js
(function(){
  const txt = document.body ? document.body.innerText.slice(0, 4000) : '';
  const low = txt.toLowerCase();
  return {
    url: location.href,
    title: document.title,
    signedIn: !!document.querySelector('[data-login], [data-testid="user-nav"]')
              || /your shops|shop manager|sign out|log out/i.test(txt),
    botWall: low.includes('datadome') || low.includes('slide right')
             || low.includes('verify you are human'),
  };
})()
```

Adjust the `signedIn` regexes per site. Probe (`etsy_session_probe.py` pattern: homepage → dashboard → sensitive URL) before deciding a fresh login is needed.

### 3. OTP relay (`otp_code.txt` file mode)

The Pi cannot consume the Secure Vault (only the managed cloud browser's `credential_fill` can). For Pi-browser logins the human relays the one-time code by file:

1. Script reaches the code-entry page, prints `WAITING_FOR_OTP_FILE: /config/<project>/shots/otp_code.txt`, then polls for the file (up to 15 min).
2. Coordinator asks the user **once** for the newest code (newest message only — older codes are dead).
3. Coordinator writes it: `printf '<CODE>' > /config/<project>/shots/otp_code.txt && chmod 600 <file>`.
4. Script reads it within seconds, fills it, submits.
5. Script **shreds** the file when done (overwrite with zeros, then delete) — in a `finally` block so it happens even on failure.

Never log the code, never put it in result JSON, never keep the file after the run.

### 4. Secrets handling

- Secrets live only in `/config/<project>/secrets/` (`0700`), files `0600`, written by the script itself after extraction from the page.
- Result JSON carries only metadata (ids, classifications, scopes) — never key material.
- If a flow needs a password the script can't fetch: the human pastes it transiently (chat, used once, never stored) — same relay shape as OTP, or the human does that one step on their own device.

## Known pitfalls

1. **Sessions get reclaimed.** Observed on Etsy: the login session dies between browser restarts, and sometimes even mid-flow when hitting a sensitive page (302 to `/signin`). Fix: do login **and** the business action in **one browser process, one run**; navigate to the sensitive URL as soon as possible after login; verify `signedIn` right before the sensitive step and fail fast (`NEEDS_STEPUP_SIGNIN`) instead of filling forms on a login page.
2. **Stdout buffering lies.** With `nohup … > log 2>&1 &`, Python `print` output is buffered — an empty log does not mean a stuck script. Trust screenshots, status JSON, and `pgrep -f <script>` instead.
3. **Form-detection must check the URL, not just "URL changed".** A 302 to `/signin` also changes the URL. Require the expected path fragment **and** the expected input field before declaring a form open.
4. **`/tmp` vs `/config`.** Anything that must survive a reboot (profiles, secrets, queues) goes under `/config/`. `/tmp` is scratch.
5. **OTP rate limits.** Repeated logins in a short window can trigger send limits. Space out OTP requests; prefer one login per run that does everything.
6. **`/root/.ssh/config` can vanish mid-session, not just on reboot.** Observed 2026-09-22: config was present at session start (ensure-pihome.sh ran clean) but gone ~40 min later with no VM reboot in between. Symptom: `ssh pihome` → `Connection reset by 198.19.0.1 port 3128` while `ssh -G pihome` shows no `controlmaster`/`proxycommand`. Fix: re-run `~/workspace/pi-ssh/ensure-pihome.sh` whenever ssh starts failing, not only in fresh sessions.
7. **Never use heredocs through the ssh chain.** `ssh pihome 'python3 - <<EOF ...'` mangles quotes/backslashes (single quotes around JS strings get stripped). Write scripts locally with the file tools and transfer via `ssh pihome 'cat > /path/file' < localfile` — stdin redirect survives intact.
8. **Avoid `%` string-formatting for JS passed to `cdp.evaluate`.** Build JS with plain string concatenation instead; stray `%` interactions produce silent wrong values (observed: evaluate returning `{}` instead of the clicked button label).

## Site notes: 123RF contributor portal (2026-09-22)

- No DataDome/bot wall from the Pi residential IP. Homepage modal "Log in" **triggers reCAPTCHA after submit**; use the dedicated page **`https://www.123rf.com/login/` → "Continue with Email / Username"** instead — same credentials, no CAPTCHA observed.
- Password in `/config/ftp-runner/secrets/123rf` verified working (login succeeded 2026-09-22).
- Contributor dashboard: `https://www.123rf.com/contrib/` → redirects to `https://www.123rf.com/contributor/dashboard`. Menu: Upload content / Dashboard / Manage content / Manage releases / Account settings / Tax center / Earning details / Upload history / FAQ. Contributor Level 0.
- **Hard gate: ID verification.** `/contrib/account-settings/upload-id/` blocks the whole contributor area until completed: step 1 Personal Information (nationality, country of residence, first/last name, DOB, phone), step 2 ID Card/Passport, step 3 selfie. Human one-time step — cannot be automated (needs the user's real identity data and documents). The web-upload flow cannot proceed until this is done.
- Session persists in the shared profile (`/config/etsy-browser/profile`) across runs; once ID verification is done server-side, the Pi session should pass the gate without re-login.

### AI Images batch upload + metadata + submit (first full success 2026-09-22)

**File delivery path (permanent design):** Pi FTP automation (`/config/ftp-runner/`) delivers files to `outbox/123rf/`; after browser task fills metadata + submits, move originals to `outbox/123rf/sent/`. The browser task never re-uploads; reload the page instead if anything looks stale.

**ID gate bypass (verified):** if a contributor URL wrongly lands on `/contrib/account-settings/upload-id/`, go `/contrib/account-settings/` → `/contributor/dashboard` — the gate clears once server-side verification exists.

**Metadata fill lessons (hard-won):**
1. **Keywords must be added one at a time.** Typing a whole comma-separated string + Enter creates one mega-tag. Per keyword: set input value → dispatch `input` event → send Enter keydown/keyup. Verified 28–42 independent tags per image this way.
2. **Description field is React-controlled.** Must use the React setter: find the DOM property descriptor for `value` on the textarea element itself, get the setter from the element's own descriptor (not HTMLInputElement/HTMLTextAreaElement prototype — prototype chain lookup hits the wrong setter), call `setter.call(el, text)`, then dispatch `input` with `{bubbles:true}`.
3. **"Save draft" must be a real visible click.** JS `button.click()` does NOT trigger the save API. If the button is off-viewport, CDP mouse clicks also fail silently. Required: `scrollIntoView({block:'center'})` → read rect → real `Input.dispatchMouseEvent` click → wait ~8s. Success = `PUT /apicore-contributors/draft_items` in the network log.
4. **Modal overlay trap.** The "What do you want to upload?" modal blocks all card clicks — press Escape to dismiss. Page anomaly → reload, never re-upload.
5. **Bulk mode trap.** If cards are multi-selected, clicking a thumbnail enters bulk mode and the editor won't switch. Fix: if "Clear all" is visible, real-click it first, then click the target card's **checkbox** (checkbox id = 123RF file id, e.g. `ziyitang260900010`).
6. **Bulk "Submit (N) AI images" works when single-item Submit is disabled.** The bulk button submits "only selected AI image(s) with complete metadata". Verified path: "Select all on this page" → click `Submit (N) AI images` (no confirmation dialog observed) → DRAFT 0 / PENDING 10.
7. **Persistence verification.** Server field names differ from the UI: description + keywords live under `kwDesc` in `GET /apicore-contributors/draft_items` (`kwDesc.description`, `kwDesc.keywords[]`). Do NOT trust the UI alone — read back all items via the API after save.
8. **Rules:** description = `title.rstrip(".") + ". A painterly digital illustration."` (≤180 chars, no separate title field); ≥7 keywords; media type must stay **AI Generated Images** (never switch to Photo/Illustration).
9. **`__NEXT_DATA__` mapping:** server id ↔ original filename (`oldFilename`) ↔ `filename` (`ziyitang2609000NN`) is in the page's `__NEXT_DATA__` and the `draft_items` API — build the idmap from there, never guess.

## Minimal example: open a site, screenshot, check login state

Runs **on the Pi** (ssh there, or copy the file over and run it there):

```python
#!/usr/bin/env python3
"""Pi-browser smoke test: open a URL, screenshot it, report login state."""
import os, sys

sys.path.insert(0, "/config/etsy-browser")  # on-Pi CDP helper
from cdp import launch, nap, wait_for_js

SHOTS = "/config/pi-browser/shots"
os.makedirs(SHOTS, exist_ok=True)

STATE_JS = """(function(){
  const txt = document.body ? document.body.innerText.slice(0, 4000) : '';
  const low = txt.toLowerCase();
  return {
    url: location.href,
    title: document.title,
    signedIn: !!document.querySelector('[data-login], [data-testid="user-nav"]')
              || /your shops|shop manager|sign out|log out/i.test(txt),
    botWall: low.includes('datadome') || low.includes('slide right')
             || low.includes('verify you are human'),
  };
})()"""

def main(url):
    cdp, proc = launch(headed=True)
    try:
        cdp.navigate(url)
        nap(3, 5)
        wait_for_js(cdp, "document.readyState === 'complete'", timeout=30)
        nap(2, 3)
        st = cdp.evaluate(STATE_JS)
        cdp.screenshot(os.path.join(SHOTS, "check.png"))
        print("url:      ", st["url"])
        print("title:    ", st["title"])
        print("signedIn: ", st["signedIn"], "| botWall:", st["botWall"])
    finally:
        cdp.close()

if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "https://www.example.com")
```

Run it: `python3 check.py https://www.etsy.com/your/shops/me/dashboard`, then `scp` back `shots/check.png`.
