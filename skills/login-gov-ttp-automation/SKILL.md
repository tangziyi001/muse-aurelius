---
name: "login-gov-ttp-automation"
description: "Fill and self-review Global Entry (TTP) applications end-to-end via login.gov on the home Raspberry Pi browser: login with MFA, navigate the 8-section TTP form, fill every field from a prepared data file, verify with 'no errors found' on Final Review, and stop before certify/submit/pay. Use when the user asks to prepare or file a Global Entry application."
---

# Login.gov + TTP Global Entry Automation

Fill a Global Entry (TTP) application on the home Raspberry Pi's hardened Chromium, which exits through the residential IP that login.gov and ttp.cbp.dhs.gov accept. This skill codifies the full flow proven on 2026-09-20 (ZIYI TANG, Application ID 138134175 — 8 sections, 0 errors, draft saved, not submitted).

## Environment (fixed)

- **Pi Chromium profile:** `/config/global-entry/profile` (persistent — session survives reboots)
- **DevTools/CDP port:** `9223`
- **Screenshots:** `/config/global-entry/shots/`, prefix new shots with `ge7-`
- **Pi SSH:** always port **2222** (see `pi-browser` skill for the exact command)
- **Data source of truth:** `/home/hatch/workspace/global-entry/applications.md`
- **Review report:** `/home/hatch/workspace/global-entry/review-report-<date>.md`
- TTP is a **SPA** — never refresh the page or restart the browser mid-flow; it loses form state.

## Credentials

- **Never ask the user for passwords.** Read login.gov credentials from the user's designated Google Doc ("FTP信息", anonymously readable link — see memory `2026-09-20.md#L257`). Per the user's standing rule: "以后你自己去doc里拿密码，别问我。"
- **Never write passwords, OTPs, or sensitive values** into logs, screenshots, memory files, checkpoints, or chat replies.
- Each applicant uses their **own** login.gov/TTP account.

## Login flow

1. Resume the Pi Chromium session if alive; otherwise launch via the standard Pi-browser pattern.
2. Go to login.gov sign-in for TTP. If the DHS consent modal (`#security-warn`) appears, click **CONSENT & CONTINUE**.
3. Type the username/password from the Doc into the real fields (transient use, never logged).
4. **MFA rule (user-standing):** only request the newest SMS code **after the page has actually triggered a new SMS**. Ask the user once, for the latest code only. Never switch to voice-call MFA without the user's explicit confirmation.
5. Radio buttons / checkboxes **must be clicked via real CDP clicks**, then verified twice: visually (screenshot) and in the DOM.
6. Known quirk: selecting country **CHINA** can clear the residency field — afterwards always re-confirm **U.S. Lawful Permanent Resident** is still selected.

## Fill order (one section at a time, save + screenshot each)

1. Program selection → Global Entry
2. Personal Information (English only: surname, given name, DOB, birthplace, email, mobile, gender, eye color, height, other names; KTN if the user provided one)
3. Documents: foreign passport (number, issued, expires) + Permanent Resident Card (USCIS number, category, resident-since, expires, citizenship)
4. Driver's License: country of issuance = **UNITED STATES** (never the birth country), state, number, class, issued, expires, DOB (required field — fill it), EDL/CDL (confirm with user, don't guess from the card's look)
5. Vehicle (optional): state, plate, make/model/year, VIN, owner, color (optional — leave blank is fine)
6. Address: current address + start month/year; flag anything that looks like website/USPS standardization (e.g. `4507 COURT SQ` vs the user's `5 Court Square`) as **to-confirm** in the review package — never silently "fix" it
7. Employment: full 5-year history. Start **month/year** must come from evidence (e.g. the offer letter's Anticipated Start Date), never from a year-only recollection. Include employer phone + address. Mark unemployed gaps explicitly if the form supports it.
8. Travel History: **country names only, last 5 years, excludes US/Canada/Mexico**. Add a country even if it was only a short trip (Italy was missed once — recheck against the data file). Pure airport transit: do not list unless the page asks for transit.
9. Additional Information: the 4 yes/no questions (criminal conviction, inadmissibility waiver, customs-law violation, immigration-law violation) — **confirm answers with the user, never default them**.
10. Capture Photo (if the page offers expedited processing): handle only with the user's explicit go-ahead. If the page needs a live webcam and the Pi has none: save a screenshot of the requirements and hand the step to the user on their phone. Never fake a photo.

## After every section

- Save a clear, readable `ge7-` screenshot.
- Re-read the page and cross-check every field against `applications.md`.
- Update `applications.md` if the user confirmed a correction.

## Final Review gate (mandatory, twice)

1. **Assistant self-review:** open Final Review, confirm **all 8 sections show "no errors found"**, screenshot everything, write the review report (every field, blanks + reasons, screenshots, anomalies, inferences, uncertainties).
2. **User review:** hand the user the full package. They review before anything else moves.
3. **Hard stops — never without the user's explicit approval:**
   - No certify / oath / truthfulness clicks.
   - No submit.
   - No payment — and even after submit approval, payment needs **one more separate explicit authorization**.
4. Finish applicant #1's double review **completely** before starting applicant #2.

## Update rule

This file is the living doc for this flow. Every new quirk discovered (selector changes, new validation errors, new MFA behavior) gets appended here — never start a second file.

## Lessons 2026-09-20 (Yue's run)

- **login.gov "Send another code" resend link:** CDP synthetic mouse clicks do NOT trigger navigation. Read the link's href and navigate to it directly.
- **LPR program-selection chain:** `areCitizen=No` → `countryOfCitizenship=CHINA` → `residencyStatus=LPR` → `tppOption` → **must also select the actual program card** (`#globalEntry`), then answer `imminentIntlTravel` Yes/No — all required before NEXT works.
- **Off-viewport clicks:** CDP `dispatchMouseEvent` clicks do not register on elements outside the viewport — always `scrollIntoView({block:"center"})` and verify the rect is in viewport first.
- **TTP program cards** are `label.btn-radio[role=button]` — mouse clicks may not toggle them; focus the label + press **Enter** via CDP keyboard events instead (verified on `#globalEntry`).
- **OTP relay race:** when writing the OTP to the Pi relay file, confirm it hasn't already been consumed by a polling flow before assuming it's still there. Codes expire in 10 minutes — relay fast, submit fast.

## Lessons 2026-09-21 (Yue's run, second session)

- **Password extraction:** the login.gov password in the `pw` doc is 19 chars — always extract programmatically and verify exact length before typing. Hand-transcribing got 16 chars and caused one failed login (lockout risk).
- **Never close the last TTP tab** via the debugger — it kills the whole Chromium process and port 9224 goes dark; relaunch with the correct profile (`/config/global-entry-yue/profile`), never the etsy profile.
- After a Chromium relaunch the TTP session is typically gone, but login.gov SSO often restores login without a fresh MFA challenge.
- Right after login, deep-URL navigation can bounce to a logged-out homepage; safer path: Dashboard → Continue Application → section nav.
- For masked password fields, `Input.insertText` char-by-char with length verification before submit avoids truncation.

## Lessons 2026-09-21 (Yue's run, third session — vehicle + address correction round)

- **"License state/province of Issuance" is a `<select>`, not a text input** — typing into it silently does nothing. Enumerate `options` and use `selectedIndex` (or `selectOption`) to set NEW YORK, then verify `selectedOptions[0].text`.
- **"U.S. government issued license plate?"** is its own required radio pair (ids `vehicle0GovtLicensePlateYes/No`) — a plain NY state plate answers **No**.
- **The ADD VEHICLE dialog has no SAVE button** — only CLOSE; the vehicle is added to the page list on dialog close. Confirm via the vehicle card on the page, then SAVE PROGRESS at page level.
- **Session fragility:** TTP session dies frequently (direct `/dashboard` navigation bounces to a logged-out homepage, CDP navigations wedge the renderer). Recovery recipe: close the wedged tab → new tab → `ttp.cbp.dhs.gov` → close app modal → Log In → CONSENT & CONTINUE → login.gov SSO restores the dashboard with **no password/MFA**. After recovery, always enter via Dashboard → Continue Application (deep-URL navigation to sections is fine once logged in).
- **Verify Addresses modal:** after SAVE & CONTINUE on Address, a "Verify Addresses" confirmation modal appears — clicking OK merely dismisses it; a **second** SAVE & CONTINUE is what actually advances to Employment.
- **Renderer wedge signature:** a CDP call hangs in `recv_msg` `TimeoutError` — the tab is dead; recover with the recipe above rather than retrying. Reading the tracker must be done on the freshly loaded application page (dashboard → Continue), never from a stale tab.
